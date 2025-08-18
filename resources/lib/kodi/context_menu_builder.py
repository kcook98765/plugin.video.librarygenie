"""Context Menu Builder for LibraryGenie - handles both native and ListItem context menus"""

import xbmc
from resources.lib.kodi.menu.registry import for_item
from resources.lib.data.models import MediaItem
from resources.lib.utils import utils


class ContextMenuBuilder:
    """Legacy wrapper - delegates to new menu registry"""

    def __init__(self):
        pass

    def build_context_menu(self, media_dict):
        """Build context menu items for a media item - delegates to new registry"""
        try:
            # Convert media_dict to MediaItem for registry
            media_item = MediaItem(
                id=media_dict.get('id', 0),
                media_type=media_dict.get('media_type', 'movie'),
                title=media_dict.get('title', 'Unknown'),
                imdb=media_dict.get('imdb') or media_dict.get('imdbnumber', ''),
                tmdb=media_dict.get('tmdb', ''),
                is_folder=media_dict.get('is_folder', False)
            )

            # Use new registry to build menu
            return for_item(media_item)

        except Exception as e:
            utils.log(f"Error in legacy ContextMenuBuilder: {str(e)}", "ERROR")
            return []

    def build_video_context_menu(self, media_info, context=None):
        """Build context menu for video items - now returns empty since we use native context only

        All context menu functionality has been moved to the native context menu
        in addon.xml and handled by resources/lib/context.py
        """
        # Return empty context menu since we're using native context only
        return []

    def build_list_context_menu(self, list_info, context=None):
        """Build context menu for list items - now returns empty since we use native context only"""
        # Return empty context menu since we're using native context only
        return []

    def build_folder_context_menu(self, folder_info, context=None):
        """Build context menu for folder items - now returns empty since we use native context only"""
        # Return empty context menu since we're using native context only
        return []

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
_context_menu_builder = None


def get_context_menu_builder():
    """Get global context menu builder instance"""
    global _context_menu_builder
    if _context_menu_builder is None:
        _context_menu_builder = ContextMenuBuilder()
    return _context_menu_builder