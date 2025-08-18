"""
ListItem Builder for LibraryGenie
Minimum supported Kodi version: 19 (Matrix)
This module does not support Kodi 18 (Leia) or earlier versions
"""
import json
import xbmcgui
from resources.lib.data.normalize import from_db
from resources.lib.kodi.listitem.factory import build_listitem
from resources.lib.utils import utils

from urllib.parse import quote, urlparse

# __all__ = ['set_info_tag', 'set_art'] # This line is removed as it's no longer directly exposed by this module

VALID_SCHEMES = {'image', 'http', 'https', 'file', 'smb', 'nfs', 'ftp', 'ftps', 'plugin', 'special'}

def _is_valid_art_url(u: str) -> bool:
    if not u:
        return False
    # Accept Kodi image wrapper directly
    if u.startswith("image://"):
        return True
    # Accept special:// paths (including PNG files)
    if u.startswith("special://"):
        return True
    p = urlparse(u)
    return p.scheme in VALID_SCHEMES

def _wrap_for_kodi_image(u: str) -> str:
    """
    If already 'image://', return as-is.
    Otherwise wrap raw URL/path into Kodi's image://<percent-encoded>/
    Avoid double-encoding by keeping '%' safe when source is already encoded.
    """
    if not u:
        return u
    if u.startswith("image://"):
        # Ensure trailing slash; Kodi expects it
        return u if u.endswith("/") else (u + "/")
    # Keep '%' to avoid double-encoding already-encoded inputs;
    # keep common URL reserved chars safe so URLs remain valid.
    enc = quote(u, safe=":/%?&=#,+@;[]()!*._-")
    return f"image://{enc}/"

# This function is no longer directly used by the ListItemBuilder, but might be used elsewhere.
# Keeping it here for now, but could be removed if not needed.
def _get_addon_artwork_fallbacks() -> dict:
    """Return addon artwork that can be used as fallbacks"""
    from resources.lib.config.addon_ref import get_addon
    addon = get_addon()
    addon_path = addon.getAddonInfo("path")
    media = f"{addon_path}/resources/media"

    return {
        'icon': f"{media}/icon.jpg",
        'thumb': f"{media}/thumb.jpg",
        'poster': f"{media}/icon.jpg",
        'fanart': f"{media}/fanart.jpg",
        'banner': f"{media}/banner.jpg",
        'landscape': f"{media}/landscape.jpg",
        'clearart': f"{media}/clearart.jpg",
        'clearlogo': f"{media}/clearlogo.png",
        'folder': f"{media}/list_folder.png",
        'playlist': f"{media}/list_playlist.png"
    }

# This function is no longer directly used by the ListItemBuilder, but might be used elsewhere.
# Keeping it here for now, but could be removed if not needed.
def _normalize_art_dict(art: dict, use_fallbacks: bool = False) -> dict:
    out = {}
    if not isinstance(art, dict):
        art = {}

    # Add addon artwork as fallbacks if requested
    if use_fallbacks:
        fallbacks = _get_addon_artwork_fallbacks()
        for k, v in fallbacks.items():
            if k not in art or not art[k]:
                art[k] = v

    # Use paths directly - let Kodi handle them
    for k, v in art.items():
        if not v:
            continue
        vv = str(v).strip()
        if vv:
            out[k] = vv

    return out


# The old ListItemBuilder class is replaced by a thin wrapper that delegates to the new factory pattern.
class ListItemBuilder:
    """Legacy wrapper - delegates to new factory pattern"""

    def __init__(self):
        pass

    def build_from_media_dict(self, media_dict, view_hint=None):
        """Build a ListItem from a media dictionary - delegates to new factory"""
        try:
            # Convert legacy media_dict to MediaItem via normalization
            if media_dict.get('source') == 'db':
                media_item = from_db(media_dict)
            else:
                # For other sources, treat as raw payload and normalize appropriately
                from resources.lib.data.normalize import from_jsonrpc
                media_item = from_jsonrpc(media_dict)

            # Use new factory to build ListItem
            return build_listitem(media_item, view_hint or 'default')

        except Exception as e:
            utils.log(f"Error in legacy ListItemBuilder: {str(e)}", "ERROR")
            # Use factory for error cases too
            from ...data.models import MediaItem
            from .factory import build_listitem
            error_item = MediaItem(
                id="error",
                media_type="unknown",
                title="Error",
                is_folder=False
            )
            return build_listitem(error_item)

    def build_folder_item(self, title, folder_id=None):
        """Build a basic folder ListItem - creates minimal MediaItem"""
        from resources.lib.data.models import MediaItem

        folder_item = MediaItem(
            id=folder_id or 0,
            media_type='folder',
            title=title,
            is_folder=True
        )

        return build_listitem(folder_item, 'folder')

    def build_list_item(self, title, list_id=None):
        """Build a basic list ListItem - creates minimal MediaItem"""
        from resources.lib.data.models import MediaItem

        list_item = MediaItem(
            id=list_id or 0,
            media_type='folder',
            title=title,
            is_folder=True
        )

        return build_listitem(list_item, 'list')