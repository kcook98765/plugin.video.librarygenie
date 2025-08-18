"""Context Menu Builder for LibraryGenie - handles both native and ListItem context menus"""

import xbmc
from resources.lib.utils import utils
from urllib.parse import quote_plus


class ContextMenuBuilder:
    """Centralized context menu building with authentication and context awareness"""

    def __init__(self):
        pass

    def _is_authenticated(self):
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


# Global instance
_context_menu_builder = None


def get_context_menu_builder():
    """Get global context menu builder instance"""
    global _context_menu_builder
    if _context_menu_builder is None:
        _context_menu_builder = ContextMenuBuilder()
    return _context_menu_builder