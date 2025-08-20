
"""Context Menu Utilities for LibraryGenie - utility methods only

Note: LibraryGenie uses the native Kodi context menu system exclusively (via addon.xml).
This module contains utility methods that may be useful elsewhere in the codebase.
"""

import xbmc
from resources.lib.utils import utils


class ContextMenuUtils:
    """Utility methods for context menu related functionality"""

    def __init__(self):
        pass

    def is_authenticated(self):
        """Check if user is authenticated to the server"""
        try:
            from resources.lib.config.addon_ref import get_addon
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

    def extract_imdb_id(self, media_info):
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

    def clean_title(self, title):
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

    def handle_move_folder_action(self, folder_info):
        """Handle move folder action"""
        try:
            folder_id = folder_info.get('folder_id')
            if not folder_id:
                return

            from resources.lib.config.config_manager import Config
            from resources.lib.data.database_manager import DatabaseManager

            config = Config()
            db_manager = DatabaseManager(config.db_path)

            # Get current folder details
            current_folder = db_manager.fetch_folder_by_id(folder_id)
            if not current_folder:
                xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found', xbmcgui.NOTIFICATION_ERROR)
                return

            # Check for protected folders
            protected_folders = ["Search History", "Imported Lists"]
            if current_folder['name'] in protected_folders:
                xbmcgui.Dialog().notification('LibraryGenie', 'Cannot move protected folder', xbmcgui.NOTIFICATION_ERROR)
                return
        except Exception as e:
            utils.log(f"Error handling move folder action: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Error moving folder', xbmcgui.NOTIFICATION_ERROR)


# Global instance
_context_menu_utils = None


def get_context_menu_utils():
    """Get global context menu utils instance"""
    global _context_menu_utils
    if _context_menu_utils is None:
        _context_menu_utils = ContextMenuUtils()
    return _context_menu_utils


# Backward compatibility aliases (deprecated - use get_context_menu_utils instead)
def get_context_menu_builder():
    """Deprecated: Use get_context_menu_utils() instead"""
    return get_context_menu_utils()


# Legacy ContextMenuBuilder class for backward compatibility
class ContextMenuBuilder(ContextMenuUtils):
    """Deprecated: Use ContextMenuUtils instead"""
    pass
