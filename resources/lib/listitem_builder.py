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
import re
import os

__all__ = ['set_info_tag', 'set_art']

VALID_SCHEMES = {'image', 'http', 'https', 'file', 'smb', 'nfs', 'ftp', 'ftps', 'plugin', 'special'}

def _is_valid_art_url(u: str) -> bool:
    if not u:
        return False
    # Accept Kodi image wrapper directly
    if u.startswith("image://"):
        return True
    # Accept Kodi default icons (bare filenames work best across all skins)
    if u.startswith("Default") and u.endswith(".png"):
        return True
    # Accept local file paths (Windows and Unix)

    if os.path.isabs(u) and os.path.exists(u):
        return True

    # For special:// paths, try to check if the file exists by converting to real path
    if u.startswith("special://home/addons/plugin.video.librarygenie/"):
        from resources.lib.addon_ref import get_addon
        addon = get_addon()
        # Convert special:// path to real file path
        relative_path = u.replace("special://home/addons/plugin.video.librarygenie/", "")
        real_path = os.path.join(addon.getAddonInfo('path'), relative_path)
        file_exists = os.path.exists(real_path)
        return file_exists

    p = urlparse(u)
    return (p.scheme in VALID_SCHEMES) or (u.startswith("special://"))

def _wrap_for_kodi_image(u: str) -> str:
    """
    If already 'image://', return as-is.
    For special:// paths, return directly without image:// wrapper.
    Otherwise wrap raw URL/path into Kodi's image://<percent-encoded>/
    """
    if not u:
        return u
    if u.startswith("image://"):
        # Ensure trailing slash; Kodi expects it
        return u if u.endswith("/") else (u + "/")
    if u.startswith("special://"):
        # Use special:// paths directly - no image:// wrapper needed
        return u
    # For other URLs/paths, wrap with image:// and encode
    enc = quote(u, safe=":/%?&=#,+@;[]()!*._-")
    return f"image://{enc}/"

def _get_addon_artwork_fallbacks() -> dict:
    """Return addon artwork that can be used as fallbacks"""
    # Use Kodi's special:// protocol which is the native way
    def make_addon_media_path(filename):
        # Use special://home/addons/ path which is the cleanest Kodi native approach
        return f"special://home/addons/plugin.video.librarygenie/resources/media/{filename}"

    fallback_dict = {
        'icon': make_addon_media_path('icon.jpg'),
        'thumb': make_addon_media_path('thumb.jpg'),
        'poster': make_addon_media_path('icon.jpg'),
        'fanart': make_addon_media_path('fanart.jpg'),
        'banner': make_addon_media_path('banner.jpg'),
        'landscape': make_addon_media_path('landscape.jpg'),
        'clearart': make_addon_media_path('clearart.jpg'),
        'clearlogo': make_addon_media_path('clearlogo.png')
    }

    return fallback_dict

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

    for k, v in art.items():
        if not v:
            continue
        vv = v.strip()

        # Accept image:// as-is, wrap others when valid (http/file/smb/etc.)
        if vv.startswith("image://"):
            wrapped = _wrap_for_kodi_image(vv)  # add trailing slash if missing
            out[k] = wrapped
            continue

        if vv.startswith("special://"):
            wrapped = _wrap_for_kodi_image(vv)  # returns special:// path directly
            out[k] = wrapped
            continue

        if _is_valid_art_url(vv):
            wrapped = _wrap_for_kodi_image(vv)
            out[k] = wrapped
        else:
            # Last resort: if it *looks* like a URL but urlparse fails, try wrapping anyway
            if "://" in vv:
                wrapped = _wrap_for_kodi_image(vv)
                out[k] = wrapped

    return out


class ListItemBuilder:
    _item_cache = {}

    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}

        # Generate cache key from stable fields
        cache_key = str(media_info.get('title', '')) + str(media_info.get('year', '')) + str(media_info.get('kodi_id', ''))
        if cache_key in ListItemBuilder._item_cache:
            utils.log(f"Using cached ListItem for: {media_info.get('title', 'Unknown')}", "DEBUG")
            return ListItemBuilder._item_cache[cache_key]

        # Create ListItem with proper string title
        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)

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
                utils.log(f"Error getting poster URL: {str(e)}", "ERROR")
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

        # Use the specialized set_art function with improved normalization but NO fallbacks for movies
        # We want to show the actual movie artwork, not addon fallbacks
        art_dict = _normalize_art_dict(art_dict, use_fallbacks=False)
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

            except Exception:
                info_dict['cast'] = []

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

        ListItemBuilder._item_cache[cache_key] = list_item
        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem with folder-specific artwork"""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)

        # Set folder-specific artwork using Kodi's special:// protocol
        folder_art = {
            'icon': 'special://home/addons/plugin.video.librarygenie/resources/media/list_folder_icon.png',
            'thumb': 'special://home/addons/plugin.video.librarygenie/resources/media/list_folder_icon.png',
            'poster': 'special://home/addons/plugin.video.librarygenie/resources/media/list_folder_icon.png',
            'fanart': 'special://home/addons/plugin.video.librarygenie/resources/media/fanart.jpg'
        }

        folder_art = _normalize_art_dict(folder_art)
        if folder_art:
            set_art(list_item, folder_art)

        return list_item

    @staticmethod
    def build_list_item(name, is_folder=True, list_data=None):
        """Build a list ListItem with list-specific artwork and enhanced metadata"""

        # Check if this is a search history list and enhance the label
        display_name = name
        label2_text = ""
        
        if list_data:
            from resources.lib.database_manager import DatabaseManager
            from resources.lib.config_manager import Config

            config = Config()
            db_manager = DatabaseManager(config.db_path)

            # Get list item count
            list_id = list_data.get('id')
            item_count = 0
            if list_id:
                item_count = db_manager.get_list_media_count(list_id)

            # Get creation date from database
            created_at = list_data.get('created_at', '')
            date_str = ""
            if created_at:
                # Extract just the date part from the timestamp
                try:
                    from datetime import datetime
                    dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    date_str = dt.strftime('%Y-%m-%d')
                except:
                    from datetime import datetime
                    date_str = datetime.now().strftime('%Y-%m-%d')
            else:
                from datetime import datetime
                date_str = datetime.now().strftime('%Y-%m-%d')

            # Check if this list is in the Search History folder
            search_history_folder_id = db_manager.get_folder_id_by_name("Search History")
            if list_data.get('folder_id') == search_history_folder_id:
                # For search history, enhance the display name with metadata
                display_name = f"{name} ({date_str}) ({item_count} items)"
                label2_text = f"Search created on {date_str} • {item_count} movies found"
            else:
                # For regular lists, keep original name but set informative label2
                label2_text = f"Created {date_str} • {item_count} movies"

        list_item = xbmcgui.ListItem(label=display_name)
        
        # Set label2 for enhanced display information
        if label2_text:
            list_item.setLabel2(label2_text)
        else:
            # Fallback label2 for lists without data
            list_item.setLabel2("Movie List")
        
        # Set additional properties that are more likely to be displayed in GUI
        if list_data:
            # Set plot/description property (often displayed in info panels)
            if label2_text:
                list_item.setProperty('plot', label2_text)
                list_item.setProperty('description', label2_text)
            
            # Set item count as a separate property
            if item_count > 0:
                list_item.setProperty('totalepisodes', str(item_count))  # Often used for counts
                list_item.setProperty('size', f"{item_count} movies")
            
            # Set date information
            if date_str:
                list_item.setProperty('dateadded', date_str)
                list_item.setProperty('date', date_str)
        else:
            # Fallback properties for lists without data
            list_item.setProperty('plot', "Movie collection")
            list_item.setProperty('description', "Movie collection")
        
        list_item.setIsFolder(is_folder)

        # Set list-specific artwork using Kodi's special:// protocol
        list_art = {
            'icon': 'special://home/addons/plugin.video.librarygenie/resources/media/list_playlist_icon.png',
            'thumb': 'special://home/addons/plugin.video.librarygenie/resources/media/list_playlist_icon.png',
            'poster': 'special://home/addons/plugin.video.librarygenie/resources/media/list_playlist_icon.png',
            'fanart': 'special://home/addons/plugin.video.librarygenie/resources/media/fanart.jpg'
        }

        list_art = _normalize_art_dict(list_art)
        if list_art:
            set_art(list_item, list_art)

        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)