from typing import TYPE_CHECKING
from ...utils.utils import log
from ...data.models import MediaItem
# Assuming xbmcgui and other necessary imports are available in the environment
# For demonstration purposes, we'll define placeholder functions if they are not
try:
    import xbmcgui
except ImportError:
    class MockListItem:
        def __init__(self):
            self._art = {}
        def setArt(self, art_dict):
            self._art = art_dict
            print(f"MockListItem setArt called with: {art_dict}")
    class xbmcgui:
        ListItem = MockListItem
    print("xbmcgui not found, using mock objects.")

# Placeholder for _is_valid_art_url and _get_addon_fallbacks if they are not defined elsewhere
def _is_valid_art_url(url: str) -> bool:
    """Mock validation for art URLs."""
    return bool(url and (url.startswith('http') or url.startswith('resource')))

def _get_addon_fallbacks():
    """Mock function to get addon fallbacks."""
    return {
        'poster': 'resource://path/fallback_poster.png',
        'fanart': 'resource://path/fallback_fanart.png',
    }

def apply_art(item: MediaItem, list_item: xbmcgui.ListItem) -> None:
    """Apply art mapping from MediaItem to ListItem"""
    try:
        log(f"=== ART_MAPPER: Starting for '{item.title}' ===", "DEBUG")
        log(f"=== ART_MAPPER: Available art keys: {list(item.art.keys())} ===", "DEBUG")

        # Start with addon fallbacks for missing art
        art_dict = _get_addon_fallbacks()

        # Update with item's actual art
        art_dict.update(item.art)

        # Check for additional art in extras
        for art_key in ['poster', 'fanart', 'thumb', 'banner', 'landscape', 'clearart', 'clearlogo', 'icon']:
            if art_key in item.extras and item.extras[art_key] and art_key not in art_dict:
                art_dict[art_key] = item.extras[art_key]

        # Apply mappings and validation
        validated_art = {}
        for kodi_key, url in art_dict.items():
            if url and _is_valid_art_url(str(url)):
                validated_art[kodi_key] = str(url)

        # Ensure we have at least basic art
        if not validated_art.get('thumb') and hasattr(item, 'media_type'): # Check if media_type exists
            # Use folder/playlist icons for folders
            from resources.lib.config.addon_ref import get_addon
            addon = get_addon()
            addon_path = addon.getAddonInfo("path")
            if item.media_type == 'folder':
                validated_art['thumb'] = f"{addon_path}/resources/media/list_folder.png"
            else:
                validated_art['thumb'] = f"{addon_path}/resources/media/list_playlist.png"

        if validated_art:
            list_item.setArt(validated_art)
            log(f"=== ART_MAPPER: Applied {len(validated_art)} art items for '{item.title}' ===", "DEBUG")
        else:
            log(f"=== ART_MAPPER: No valid art found for '{item.title}' ===", "DEBUG")

    except Exception as e:
        log(f"Error applying art for '{item.title}': {str(e)}", "ERROR")