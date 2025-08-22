
import json
import hashlib
import os
import time
import xbmc
import xbmcvfs
from datetime import datetime
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.config.settings_manager import SettingsManager
from resources.lib.data.query_manager import QueryManager
from resources.lib.integrations.remote_api.favorites_importer import FavoritesImporter

class FavoritesSyncManager:
    def __init__(self):
        self.config = Config()
        self.settings = SettingsManager()
        self.query_manager = QueryManager(self.config.db_path)
        self.favorites_importer = FavoritesImporter()
        self.snapshot_file = os.path.join(self.config.profile, 'fav_snapshot.json')
        self.last_snapshot = {}
        self.load_snapshot()

    def load_snapshot(self):
        """Load the last known favorites snapshot from disk"""
        try:
            if xbmcvfs.exists(self.snapshot_file):
                with open(xbmcvfs.translatePath(self.snapshot_file), 'r', encoding='utf-8') as f:
                    self.last_snapshot = json.load(f)
                utils.log(f"Loaded favorites snapshot with {len(self.last_snapshot.get('items', {}))} items", "DEBUG")
            else:
                utils.log("No existing favorites snapshot found", "DEBUG")
                self.last_snapshot = {'items': {}, 'signature': ''}
        except Exception as e:
            utils.log(f"Error loading favorites snapshot: {str(e)}", "ERROR")
            self.last_snapshot = {'items': {}, 'signature': ''}

    def save_snapshot(self, items, signature):
        """Save the current favorites snapshot to disk"""
        try:
            snapshot_data = {
                'items': items,
                'signature': signature,
                'timestamp': datetime.now().isoformat()
            }
            
            # Ensure addon_data directory exists
            addon_data_dir = xbmcvfs.translatePath(self.config.profile)
            if not os.path.exists(addon_data_dir):
                os.makedirs(addon_data_dir)
            
            with open(xbmcvfs.translatePath(self.snapshot_file), 'w', encoding='utf-8') as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
            
            self.last_snapshot = snapshot_data
            utils.log(f"Saved favorites snapshot with {len(items)} items", "DEBUG")
        except Exception as e:
            utils.log(f"Error saving favorites snapshot: {str(e)}", "ERROR")

    def create_identity_key(self, fav_item):
        """Create a stable identity key for a favorite item"""
        ftype = fav_item.get('type', '')
        path = fav_item.get('path', '')
        window = fav_item.get('window', '')
        windowparameter = fav_item.get('windowparameter', '')
        
        if path:
            return f"{ftype}:{path}"
        elif window and windowparameter:
            return f"{ftype}:{window}:{windowparameter}"
        else:
            # Fallback to title if other identifiers are missing
            title = fav_item.get('title', 'unknown')
            return f"{ftype}:title:{title}"

    def canonicalize_favorite(self, fav_item):
        """Convert a favorite item to its canonical form for comparison"""
        return {
            'identity': self.create_identity_key(fav_item),
            'title': fav_item.get('title', ''),
            'thumbnail': fav_item.get('thumbnail', ''),
            'path': fav_item.get('path', ''),
            'type': fav_item.get('type', ''),
            'window': fav_item.get('window', ''),
            'windowparameter': fav_item.get('windowparameter', '')
        }

    def compute_signature(self, items_dict):
        """Compute a stable signature for the favorites list"""
        # Sort by identity key for stable ordering
        sorted_items = sorted(items_dict.items())
        
        # Create a minimal representation for hashing
        minimal_data = []
        for identity, item in sorted_items:
            minimal_item = {
                'identity': identity,
                'title': item['title'],
                'thumbnail': item['thumbnail'],
                'path': item['path']
            }
            minimal_data.append(minimal_item)
        
        # Compute hash
        data_str = json.dumps(minimal_data, sort_keys=True)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def get_kodi_favorites_list_id(self):
        """Get or create the protected 'Kodi Favorites' list at root level"""
        # Look for existing list at root level (None parent)
        lists = self.query_manager.fetch_lists(None)
        list_name = "Kodi Favorites"
        
        for list_item in lists:
            if list_item['name'] == list_name:
                return list_item['id']
        
        # Create new list at root level
        list_result = self.query_manager.create_list(list_name, None)
        list_id = list_result['id'] if isinstance(list_result, dict) else list_result
        utils.log(f"Created '{list_name}' list with ID: {list_id}", "INFO")
        return list_id

    def sync_favorites(self):
        """Main sync function - checks for changes and updates the Kodi Favorites folder"""
        if not self.settings.is_favorites_sync_enabled():
            utils.log("Favorites sync is disabled", "DEBUG")
            return False

        # Don't sync while media is playing
        if xbmc.Player().isPlaying():
            utils.log("Media is playing, skipping favorites sync", "DEBUG")
            return False

        utils.log("=== Starting Favorites Sync Process ===", "DEBUG")
        start_time = time.time()

        try:
            # Fetch current favorites from Kodi
            current_favorites = self.favorites_importer._fetch_favourites_media()
            if not current_favorites:
                utils.log("No media favorites found in Kodi", "DEBUG")
                return False

            # Canonicalize and index current favorites
            current_items = {}
            for fav in current_favorites:
                canonical = self.canonicalize_favorite(fav)
                current_items[canonical['identity']] = canonical

            # Compute signature of current state
            current_signature = self.compute_signature(current_items)
            
            # Compare with last known signature
            last_signature = self.last_snapshot.get('signature', '')
            if current_signature == last_signature:
                elapsed_time = time.time() - start_time
                utils.log(f"Favorites unchanged, no sync needed (checked in {elapsed_time:.2f}s)", "DEBUG")
                return False

            utils.log(f"Favorites changed - proceeding with sync", "INFO")

            # Analyze differences
            last_items = self.last_snapshot.get('items', {})
            added_items = []
            removed_identities = []
            changed_items = []

            # Find added and changed items
            for identity, current_item in current_items.items():
                if identity not in last_items:
                    added_items.append(current_item)
                else:
                    last_item = last_items[identity]
                    if (current_item['title'] != last_item['title'] or 
                        current_item['thumbnail'] != last_item['thumbnail']):
                        changed_items.append((current_item, last_item))

            # Find removed items
            for identity in last_items:
                if identity not in current_items:
                    removed_identities.append(identity)

            utils.log(f"Sync changes: {len(added_items)} added, {len(removed_identities)} removed, {len(changed_items)} changed", "INFO")

            # Apply changes to LibraryGenie
            if added_items or removed_identities or changed_items:
                self.apply_favorites_changes(added_items, removed_identities, changed_items)

            # Save new snapshot
            self.save_snapshot(current_items, current_signature)

            # Always log completion time
            elapsed_time = time.time() - start_time
            utils.log(f"Favorites sync completed in {elapsed_time:.2f} seconds", "INFO")

            return True

        except Exception as e:
            utils.log(f"Error in favorites sync: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Favorites sync traceback: {traceback.format_exc()}", "ERROR")
            return False

    def apply_favorites_changes(self, added_items, removed_identities, changed_items):
        """Apply the detected changes to the Kodi Favorites folder"""
        try:
            # Get or create the Kodi Favorites list at root level
            list_id = self.get_kodi_favorites_list_id()

            # Process added items
            for item in added_items:
                utils.log(f"Adding favorite: {item['title']}", "DEBUG")
                
                # Find the original favorite data for this item
                original_fav = None
                current_favorites = self.favorites_importer._fetch_favourites_media()
                for fav in current_favorites:
                    if self.create_identity_key(fav) == item['identity']:
                        original_fav = fav
                        break

                if original_fav and self.favorites_importer._is_playable_video(original_fav.get('path', '')):
                    # Convert to media dict and add to list
                    path = original_fav.get("path") or ""
                    title = original_fav.get("title") or ""
                    
                    # Try library matching first
                    kodi_movie = self.favorites_importer._library_match_from_path(path)
                    if not kodi_movie and (path.startswith("videodb://") or not path.startswith(("smb://", "nfs://", "file://"))):
                        kodi_movie = self.favorites_importer.lookup_in_kodi_library(title)

                    filedetails = None if kodi_movie else self.favorites_importer._get_file_details(path)
                    
                    media_dict = self.favorites_importer.convert_favorite_item_to_media_dict(
                        fav=original_fav,
                        filedetails=filedetails,
                        kodi_movie=kodi_movie
                    )
                    
                    self.query_manager.insert_media_item_and_add_to_list(list_id, media_dict)

            # Process removed items
            if removed_identities:
                utils.log(f"Removing {len(removed_identities)} favorites", "DEBUG")
                # For now, we'll clear the list and rebuild it since we don't have
                # a reliable way to match individual items to remove
                # This could be optimized in the future
                self.rebuild_favorites_list(list_id)

            # Process changed items (rename/update metadata)
            for current_item, last_item in changed_items:
                utils.log(f"Updating favorite: {last_item['title']} -> {current_item['title']}", "DEBUG")
                # For simplicity, we'll handle this in the rebuild as well

            # If we had removals or changes, rebuild the entire list
            if removed_identities or changed_items:
                self.rebuild_favorites_list(list_id)

        except Exception as e:
            utils.log(f"Error applying favorites changes: {str(e)}", "ERROR")

    def rebuild_favorites_list(self):
        """Rebuild the entire favorites list from current Kodi favorites"""
        try:
            utils.log("Rebuilding favorites list", "DEBUG")
            
            # Get the favorites list ID
            list_id = self.get_kodi_favorites_list_id()
            
            # Clear existing list contents
            self.query_manager.clear_list_contents(list_id)
            
            # Get current favorites and rebuild
            current_favorites = self.favorites_importer._fetch_favourites_media()
            playable_items = []
            
            for fav in current_favorites:
                path = fav.get("path", "")
                if self.favorites_importer._is_playable_video(path):
                    playable_items.append(fav)

            # Add all playable items back to the list
            for fav in playable_items:
                path = fav.get("path") or ""
                title = fav.get("title") or ""
                
                # Try library matching
                kodi_movie = self.favorites_importer._library_match_from_path(path)
                if not kodi_movie and (path.startswith("videodb://") or not path.startswith(("smb://", "nfs://", "file://"))):
                    kodi_movie = self.favorites_importer.lookup_in_kodi_library(title)

                filedetails = None if kodi_movie else self.favorites_importer._get_file_details(path)
                
                media_dict = self.favorites_importer.convert_favorite_item_to_media_dict(
                    fav=fav,
                    filedetails=filedetails,
                    kodi_movie=kodi_movie
                )
                
                self.query_manager.insert_media_item_and_add_to_list(list_id, media_dict)

            utils.log(f"Rebuilt favorites list with {len(playable_items)} items", "INFO")

        except Exception as e:
            utils.log(f"Error rebuilding favorites list: {str(e)}", "ERROR")

    def force_sync(self):
        """Force a complete sync regardless of changes"""
        utils.log("=== Starting Forced Favorites Sync ===", "INFO")
        
        # Reset snapshot to force full sync
        self.last_snapshot = {'items': {}, 'signature': ''}
        
        # Run full rebuild
        self.rebuild_favorites_list()
        
        # Run sync
        result = self.sync_favorites()
        
        if result:
            utils.log("Forced favorites sync completed successfully", "INFO")
        else:
            utils.log("Forced favorites sync failed or no changes detected", "WARNING")
        
        return result
