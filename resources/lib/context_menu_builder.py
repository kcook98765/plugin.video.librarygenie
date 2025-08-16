"""Context Menu Builder for LibraryGenie - handles both native and ListItem context menus"""

import xbmc
from resources.lib import utils
from urllib.parse import quote_plus


class ContextMenuBuilder:
    """Centralized context menu building with authentication and context awareness"""

    def __init__(self):
        pass

    def _is_authenticated(self):
        """Check if user is authenticated to the server"""
        try:
            from resources.lib.addon_ref import get_addon
            addon = get_addon()

            # Check if we have API configuration
            api_url = addon.getSetting('remote_api_url')
            api_key = addon.getSetting('remote_api_key')

            # Also check LGS settings as backup
            lgs_url = addon.getSetting('lgs_upload_url')
            lgs_key = addon.getSetting('lgs_upload_key')

            # User is authenticated if they have either remote API or LGS credentials
            has_remote_api = api_url and api_key
            has_lgs_auth = lgs_url and lgs_key

            return has_remote_api or has_lgs_auth

        except Exception as e:
            utils.log(f"Error checking authentication status: {str(e)}", "ERROR")
            return False

    def build_video_context_menu(self, media_info, context=None):
        """Build context menu for video items

        Args:
            media_info: Media information dictionary
            context: Context information dict with keys:
                - 'current_list_id': ID if viewing list contents
                - 'current_folder_id': ID if viewing folder contents
                - 'view_mode': 'list', 'search_results', 'browse', etc.
                - 'item_source': 'kodi_library', 'remote_search', 'manual_entry'
        """
        if not isinstance(media_info, dict):
            media_info = {}

        if not context:
            context = {}

        context_menu_items = []

        # Always available items
        title = media_info.get('title', 'Unknown')
        formatted_title = self._clean_title(title)

        # Try multiple possible ID fields
        item_id = (media_info.get("id", "") or
                  media_info.get("kodi_id", "") or
                  media_info.get("movieid", "") or
                  media_info.get("media_id", "") or "")

        context_menu_items.append(('Show Details', f'RunPlugin(plugin://plugin.video.librarygenie/?action=show_item_details&title={quote_plus(formatted_title)}&item_id={item_id})'))
        context_menu_items.append(('Information', 'Action(Info)'))

        # Add to List - always available
        context_menu_items.append(('Add to List...', f'RunPlugin(plugin://plugin.video.librarygenie/?action=add_to_list&title={quote_plus(formatted_title)}&item_id={item_id})'))

        # Remove from List - only when viewing list contents (using embedded data)
        viewing_list_id = media_info.get('_viewing_list_id')
        if viewing_list_id:
            media_id = media_info.get('media_id')
            if media_id:
                utils.log(f"Adding 'Remove from List' context menu item: list_id={viewing_list_id}, media_id={media_id}", "DEBUG")
                context_menu_items.append(('Remove from List', f'RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={viewing_list_id}&media_id={media_id})'))
            else:
                utils.log(f"Cannot add 'Remove from List' - missing media_id for list_id={viewing_list_id}", "DEBUG")
        else:
            utils.log("Cannot add 'Remove from List' - not viewing list contents", "DEBUG")

        # Refresh Metadata - always available
        context_menu_items.append(('Refresh Metadata', f'RunPlugin(plugin://plugin.video.librarygenie/?action=refresh_metadata&title={quote_plus(formatted_title)}&item_id={item_id})'))

        # Find Similar Movies - only when authenticated AND has valid IMDb ID
        imdb_id = self._extract_imdb_id(media_info)
        if imdb_id and str(imdb_id).startswith('tt'):
            if self._is_authenticated():
                encoded_title = quote_plus(str(media_info.get('title', 'Unknown')))
                context_menu_items.append(('Find Similar Movies...', f'RunPlugin(plugin://plugin.video.librarygenie/?action=find_similar_from_plugin&imdb_id={imdb_id}&title={encoded_title})'))
            else:
                # Show disabled item with explanation for unauthenticated users
                context_menu_items.append(('Find Similar Movies... (Requires Authentication)', 'Action(Noop)'))

        return context_menu_items

    def build_list_context_menu(self, list_info, context=None):
        """Build context menu for list items"""
        if not isinstance(list_info, dict):
            list_info = {}

        if not context:
            context = {}

        context_menu_items = []
        list_id = list_info.get('list_id', '')

        if list_id:
            # Always available list operations
            context_menu_items.append(('Rename List', f'RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})'))
            context_menu_items.append(('Move List', f'RunPlugin(plugin://plugin.video.librarygenie/?action=move_list&list_id={list_id})'))
            context_menu_items.append(('Delete List', f'RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_id})'))

            # Export List - only when authenticated
            if self._is_authenticated():
                context_menu_items.append(('Export List', f'RunPlugin(plugin://plugin.video.librarygenie/?action=export_list&list_id={list_id})'))
            else:
                context_menu_items.append(('Export List (Requires Authentication)', 'Action(Noop)'))

        return context_menu_items

    def build_folder_context_menu(self, folder_info, context=None):
        """Build context menu for folder items"""
        if not isinstance(folder_info, dict):
            folder_info = {}

        if not context:
            context = {}

        context_menu_items = []
        folder_id = folder_info.get('folder_id', '')

        if folder_id:
            # Always available folder operations
            context_menu_items.append(('Rename Folder', f'RunPlugin(plugin://plugin.video.librarygenie/?action=rename_folder&folder_id={folder_id})'))
            context_menu_items.append(('Move Folder', f'RunPlugin(plugin://plugin.video.librarygenie/?action=move_folder&folder_id={folder_id})'))
            context_menu_items.append(('Delete Folder', f'RunPlugin(plugin://plugin.video.librarygenie/?action=delete_folder&folder_id={folder_id})'))

        return context_menu_items

    def _extract_imdb_id(self, media_info):
        """Extract IMDb ID from media info with proper priority for v19+ compatibility"""
        # First try uniqueid.imdb (most reliable for actual IMDb IDs in v19+)
        if isinstance(media_info.get('uniqueid'), dict):
            uniqueid_imdb = media_info.get('uniqueid', {}).get('imdb', '')
            if uniqueid_imdb and str(uniqueid_imdb).startswith('tt'):
                return uniqueid_imdb

        # Fallback to other sources only if uniqueid.imdb not found
        candidates = [
            media_info.get('imdbnumber', ''),
            media_info.get('info', {}).get('imdbnumber', '') if media_info.get('info') else '',
            media_info.get('imdb_id', '')
        ]

        for candidate in candidates:
            if candidate and str(candidate).startswith('tt'):
                return candidate

        return None

    def _clean_title(self, title):
        """Clean title for URL encoding"""
        import re
        if not title:
            return title

        # Remove emoji characters
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "]+",
            flags=re.UNICODE
        )

        cleaned = emoji_pattern.sub('', title).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned


# Global instance
_context_menu_builder = None


def get_context_menu_builder():
    """Get global context menu builder instance"""
    global _context_menu_builder
    if _context_menu_builder is None:
        _context_menu_builder = ContextMenuBuilder()
    return _context_menu_builder