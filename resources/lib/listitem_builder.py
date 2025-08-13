"""
ListItem Builder for LibraryGenie
Minimum supported Kodi version: 19 (Matrix)
This module does not support Kodi 18 (Leia) or earlier versions
"""
import json
import xbmcgui
import xbmc
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag, set_art
from typing import Dict
from urllib.parse import quote, urlparse


__all__ = ['set_info_tag', 'set_art']

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

def _get_addon_artwork_fallbacks() -> dict:
    """Return addon artwork that can be used as fallbacks"""
    from resources.lib.addon_ref import get_addon
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


class ListItemBuilder:

    @staticmethod
    def _clean_title(title):
        """Remove emoji characters and other problematic Unicode that Kodi can't render"""
        import re
        if not title:
            return title
        
        # Remove emoji characters (covers most emoji ranges)
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
        
        # Remove emojis and clean up extra spaces
        cleaned = emoji_pattern.sub('', title).strip()
        
        # Remove multiple spaces and clean up
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}

        # Detailed logging available for debugging when needed

        # Create ListItem with proper string title (remove emoji characters)
        title = str(media_info.get('title', ''))
        title = ListItemBuilder._clean_title(title)
        
        # Append search score to title if score exists
        search_score = media_info.get('search_score')
        if search_score and search_score > 0:
            title = f"{title} ({search_score:.2f})"
        
        list_item = xbmcgui.ListItem(label=title)
        
        # Set label2 for search history items to show score and IMDB ID
        play_url = media_info.get('play', '')
        if play_url and play_url.startswith('search_history://'):
            imdb_id = play_url.replace('search_history://', '')
            score = media_info.get('search_score', 0)
            if score and score > 0:
                list_item.setLabel2(f"Score: {score}")

        # Prepare artwork dictionary
        art_dict = {}

        # Get poster URL with priority order
        poster_url = None
        for source in [
            lambda: media_info.get('poster'),
            lambda: media_info.get('art', {}).get('poster') if isinstance(media_info.get('art'), dict) else None,
            lambda: media_info.get('info', {}).get('poster'),
            lambda: media_info.get('thumbnail')
        ]:
            try:
                url = source()
                if url and str(url) != 'None':
                    poster_url = url
                    break
            except Exception as e:
                # utils.log(f"Error getting poster URL: {str(e)}", "ERROR")
                continue

        # Handle art data from different sources
        if media_info.get('art'):
            try:
                if isinstance(media_info['art'], str):
                    art_data = json.loads(media_info['art'])
                else:
                    art_data = media_info['art']
                art_dict.update(art_data)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        # Get art dictionary from info if available
        if isinstance(media_info.get('info', {}).get('art'), dict):
            art_dict.update(media_info['info']['art'])

        # Set poster with fallbacks
        if poster_url and str(poster_url) != 'None':
            art_dict['poster'] = poster_url
            art_dict['thumb'] = poster_url
            art_dict['icon'] = poster_url

        # Set fanart
        fanart = media_info.get('fanart') or media_info.get('info', {}).get('fanart')
        if fanart and str(fanart) != 'None':
            art_dict['fanart'] = fanart

        # Use the specialized set_art function with improved normalization and fallbacks
        art_dict = _normalize_art_dict(art_dict, use_fallbacks=True)
        if art_dict:
            set_art(list_item, art_dict)

        # Create info dictionary for InfoTag
        info_dict = {
            'title': title,
            'plot': media_info.get('plot', ''),
            'tagline': media_info.get('tagline', ''),
            'country': media_info.get('country', ''),
            'director': media_info.get('director', ''),
            'genre': media_info.get('genre', ''),
            'mpaa': media_info.get('mpaa', ''),
            'premiered': media_info.get('premiered', ''),
            'studio': media_info.get('studio', ''),
            'trailer': media_info.get('trailer', ''),
            'writer': media_info.get('writer', ''),
            'mediatype': (media_info.get('media_type') or media_info.get('mediatype') or 'movie').lower()
        }

        # Handle numeric fields with proper conversion
        if media_info.get('year'):
            try:
                info_dict['year'] = int(media_info['year'])
            except (ValueError, TypeError):
                pass

        if media_info.get('rating'):
            try:
                info_dict['rating'] = float(media_info['rating'])
            except (ValueError, TypeError):
                pass

        if media_info.get('votes'):
            try:
                info_dict['votes'] = int(media_info['votes'])
            except (ValueError, TypeError):
                pass

        # Handle cast data
        cast = media_info.get('cast', [])
        if cast:
            try:
                # Handle string-encoded cast data
                if isinstance(cast, str):
                    try:
                        cast = json.loads(cast)
                    except json.JSONDecodeError:
                        cast = []

                # Ensure cast is a list
                if not isinstance(cast, list):
                    cast = []

                info_dict['cast'] = cast

            except Exception as e:
                info_dict['cast'] = []

        # LOG PROCESSED INFO_DICT BEFORE SETTING
        # utils.log("=== INFO_DICT TO BE SET START ===", "INFO")
        # for key, value in info_dict.items():
        #     if key == 'cast' and isinstance(value, list):
        #         utils.log(f"  {key}: [{len(value)} cast members]", "INFO")
        #     else:
        #         utils.log(f"  {key}: {value}", "INFO")
        # utils.log("=== INFO_DICT TO BE SET END ===", "INFO")

        # Use the specialized set_info_tag function that handles Kodi version compatibility
        set_info_tag(list_item, info_dict, 'video')

        # Set resume point if available
        if 'resumetime' in media_info and 'totaltime' in media_info:
            list_item.setProperty('ResumeTime', str(media_info['resumetime']))
            list_item.setProperty('TotalTime', str(media_info['totaltime']))

        # Set content properties
        list_item.setProperty('IsPlayable', 'true')

        # Try to get play URL from different possible locations
        play_url = media_info.get('info', {}).get('play') or media_info.get('play') or media_info.get('file')
        if play_url:
            list_item.setPath(play_url)

        # LOG FINAL LISTITEM STATUS
        # utils.log(f"=== FINAL LISTITEM STATUS FOR {title} ===", "INFO")
        # utils.log(f"ListItem Label: {list_item.getLabel()}", "INFO")
        # utils.log(f"ListItem Path: {list_item.getPath()}", "INFO")
        # utils.log(f"IsPlayable Property: {list_item.getProperty('IsPlayable')}", "INFO")
        # utils.log("=== LISTITEM BUILD COMPLETED ===", "INFO")

        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True, item_type='folder', plot=''):
        """Build a folder ListItem with addon artwork
        
        Args:
            name: Display name for the item
            is_folder: Whether this is a folder item
            item_type: Type of item ('folder', 'playlist', 'list') to determine icon
            plot: Plot/description text for the item
        """
        from resources.lib.addon_ref import get_addon
        addon = get_addon()
        addon_path = addon.getAddonInfo("path")
        media = f"{addon_path}/resources/media"
        
        # Clean the name to remove emoji characters
        clean_name = ListItemBuilder._clean_title(name)
        list_item = xbmcgui.ListItem(label=clean_name)
        list_item.setIsFolder(is_folder)

        # Choose appropriate icon based on item type
        if item_type in ['playlist', 'list']:
            icon_path = f"{media}/list_playlist.png"
        else:
            icon_path = f"{media}/list_folder.png"

        # Set folder-appropriate artwork using direct paths
        folder_art = {
            'icon': icon_path,
            'thumb': icon_path,
            'poster': icon_path,
            'fanart': f"{media}/fanart.jpg"
        }
        
        # Set artwork directly without complex processing
        set_art(list_item, folder_art)

        # Set plot information if provided
        if plot:
            info_dict = {
                'plot': plot,
                'mediatype': 'video'
            }
            set_info_tag(list_item, info_dict, 'video')

        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)