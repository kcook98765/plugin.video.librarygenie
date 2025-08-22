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

class FavoritesSyncManager:
    def __init__(self):
        self.config = Config()
        self.settings = SettingsManager()
        self.query_manager = QueryManager(self.config.db_path)
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

    def _fetch_favourites_media(self):
        """Fetch media favorites directly from Kodi JSON-RPC"""
        try:
            req = {
                "jsonrpc": "2.0", 
                "id": 1, 
                "method": "Favourites.GetFavourites",
                "params": {
                    "type": "media",
                    "properties": ["path", "thumbnail", "window", "windowparameter"]
                }
            }

            resp = xbmc.executeJSONRPC(json.dumps(req))
            data = json.loads(resp)

            if "error" in data:
                utils.log(f"JSON-RPC error fetching favorites: {data['error']}", "ERROR")
                return []

            result = data.get("result", {})
            favs = result.get("favourites", []) or []
            utils.log(f"Fetched {len(favs)} media favorites", "DEBUG")
            return favs

        except Exception as e:
            utils.log(f"Error fetching favorites: {str(e)}", "ERROR")
            return []

    def _is_playable_video(self, path):
        """Quick check for playable video paths without heavy RPC calls"""
        if not path:
            return False

        # Plugin video URLs are always playable
        if path.startswith("plugin://plugin.video."):
            return True

        # videodb:// URLs are always playable
        if path.startswith("videodb://"):
            return True

        # Check common video file extensions
        video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts', '.mpg', '.mpeg')
        base_path = path.split('|')[0] if '|' in path else path

        if base_path and any(base_path.lower().endswith(ext) for ext in video_extensions):
            return True

        return False

    def _create_media_dict_from_favorite(self, fav_item):
        """Create media dict directly from favorite item data without external lookups"""
        path = fav_item.get('path', '')
        title = fav_item.get('title', 'Unknown')

        media_dict = {
            'title': title.strip() if title else 'Unknown',
            'year': 0,
            'plot': '',
            'rating': 0.0,
            'duration': 0,
            'genre': '',
            'director': '',
            'cast': '',
            'studio': '',
            'mpaa': '',
            'tagline': '',
            'writer': '',
            'country': '',
            'premiered': '',
            'dateadded': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'votes': 0,
            'trailer': '',
            'path': path,
            'play': path,
            'kodi_id': 0,
            'media_type': 'movie',
            'source': 'favorites_import',
            'imdbnumber': '',
            'thumbnail': fav_item.get('thumbnail', ''),
            'poster': '',
            'fanart': '',
            'art': '',
            'uniqueid': '',
            'stream_url': '',
            'status': 'available'
        }

        return media_dict

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
        """Main sync function - checks for changes and updates the Kodi Favorites list"""
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
            current_favorites = self._fetch_favourites_media()
            if not current_favorites:
                utils.log("No media favorites found in Kodi", "DEBUG")
                return False

            # Filter for playable video items and canonicalize
            current_items = {}
            for fav in current_favorites:
                if fav.get('type') == 'media' and self._is_playable_video(fav.get('path', '')):
                    canonical = self.canonicalize_favorite(fav)
                    current_items[canonical['identity']] = canonical

            # Compute signature of current state
            current_signature = self.compute_signature(current_items)

            # Compare with last known signature
            last_signature = self.last_snapshot.get('signature', '')

            # Check if the list is empty despite having favorites
            list_id = 1 # Use reserved Kodi Favorites list (ID 1)
            current_list_count = self.query_manager.get_list_media_count(list_id)

            # Force rebuild if list is empty but we have favorites
            force_rebuild = (current_list_count == 0 and len(current_items) > 0)

            if current_signature == last_signature and current_list_count > 0 and not force_rebuild:
                elapsed_time = time.time() - start_time
                utils.log(f"Favorites unchanged, no sync needed (checked in {elapsed_time:.2f}s)", "DEBUG")
                return False
            elif force_rebuild:
                utils.log(f"Favorites list is empty but we have {len(current_items)} favorites - forcing rebuild", "INFO")
            elif current_signature != last_signature:
                utils.log(f"Favorites signature changed: {last_signature[:8]}... -> {current_signature[:8]}...", "INFO")

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

            # Apply changes to database
            if added_items or removed_identities or changed_items or current_list_count == 0:
                self._apply_database_changes(list_id, added_items, removed_identities, changed_items, current_favorites)

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

    def _apply_database_changes(self, list_id, added_items, removed_identities, changed_items, current_favorites):
        """Apply changes to the database without any UI dependencies"""
        try:
            # Create lookup for current favorites by identity
            favorites_by_identity = {}
            for fav in current_favorites:
                if fav.get('type') == 'media' and self._is_playable_video(fav.get('path', '')):
                    identity = self.create_identity_key(fav)
                    favorites_by_identity[identity] = fav

            # Get current list contents for matching
            current_list_items = self.query_manager.fetch_list_items_with_details(list_id)
            list_items_by_path = {item.get('path', ''): item for item in current_list_items if item.get('path')}
            list_items_by_title = {item.get('title', '').lower(): item for item in current_list_items if item.get('title')}

            # Process added items
            for item in added_items:
                utils.log(f"Adding new favorite: {item['title']}", "DEBUG")

                original_fav = favorites_by_identity.get(item['identity'])
                if original_fav:
                    path = original_fav.get("path", "")
                    title = original_fav.get("title", "")

                    # Check if item is already in list (by path or title)
                    if path in list_items_by_path or title.lower() in list_items_by_title:
                        utils.log(f"Favorite '{title}' already exists in list, skipping", "DEBUG")
                        continue

                    # Create media dict directly from favorite data
                    media_dict = self._create_media_dict_from_favorite(original_fav)

                    # Insert into database
                    self.query_manager.insert_media_item_and_add_to_list(list_id, media_dict)
                    utils.log(f"Added new favorite '{title}' to list", "INFO")

            # Process removed items (favorites no longer in Kodi)
            if removed_identities:
                utils.log(f"Processing {len(removed_identities)} removed favorites", "DEBUG")

                # Find items in list that correspond to removed favorites
                items_to_remove = []
                for item in current_list_items:
                    item_path = item.get('path', '')
                    item_title = item.get('title', '')

                    # Check if this list item corresponds to a removed favorite
                    item_found_in_kodi = False
                    for fav in current_favorites:
                        if (fav.get('path', '') == item_path or 
                            (fav.get('title', '').lower() == item_title.lower() and item_title)):
                            item_found_in_kodi = True
                            break

                    if not item_found_in_kodi and item.get('source') == 'favorites_import':
                        items_to_remove.append(item)

                # Remove items that are no longer in Kodi favorites
                for item in items_to_remove:
                    try:
                        # Remove from list (but keep media item in database)
                        self.query_manager.remove_media_item_from_list(list_id, item['id'])
                        utils.log(f"Removed '{item.get('title', 'Unknown')}' from favorites list", "INFO")
                    except Exception as e:
                        utils.log(f"Error removing item from list: {str(e)}", "ERROR")

            # Process changed items (update metadata without removing/re-adding)
            for current_item, last_item in changed_items:
                utils.log(f"Processing changed favorite: {last_item['title']} -> {current_item['title']}", "DEBUG")

                # Find the corresponding item in the list
                old_path = last_item.get('path', '')
                new_title = current_item.get('title', '')

                list_item = list_items_by_path.get(old_path)
                if list_item and new_title != list_item.get('title', ''):
                    try:
                        original_fav = favorites_by_identity.get(current_item['identity'])
                        if original_fav:
                            # Get updated media dict
                            updated_media_dict = self._create_media_dict_from_favorite(original_fav)

                            # Update the media item
                            self.query_manager.update_data('media_items', updated_media_dict, 'id = ?', (list_item['id'],))
                            utils.log(f"Updated favorite metadata for '{new_title}'", "INFO")
                    except Exception as e:
                        utils.log(f"Error updating changed item: {str(e)}", "ERROR")

            utils.log("Database changes applied successfully", "INFO")

        except Exception as e:
            utils.log(f"Error applying database changes: {str(e)}", "ERROR")

    def force_sync(self):
        """Force a complete sync regardless of changes"""
        utils.log("=== Starting Forced Favorites Sync ===", "INFO")

        # Reset snapshot to force full sync
        self.last_snapshot = {'items': {}, 'signature': ''}

        # Run sync
        result = self.sync_favorites()

        if result:
            utils.log("Forced favorites sync completed successfully", "INFO")
        else:
            utils.log("Forced favorites sync failed or no changes detected", "WARNING")

        return result