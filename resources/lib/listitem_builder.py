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

__all__ = ['set_info_tag', 'set_art']

VALID_SCHEMES = {'image', 'http', 'https', 'file', 'smb', 'nfs', 'ftp', 'ftps', 'plugin', 'special'}

def _is_valid_art_url(u: str) -> bool:
    if not u:
        return False
    # Accept Kodi image wrapper directly
    if u.startswith("image://"):
        return True
    p = urlparse(u)
    return (p.scheme in VALID_SCHEMES) or (u.startswith("special://"))

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
    return {
        'icon': 'special://home/addons/plugin.video.librarygenie/resources/media/icon.jpg',
        'thumb': 'special://home/addons/plugin.video.librarygenie/resources/media/thumb.jpg',
        'poster': 'special://home/addons/plugin.video.librarygenie/resources/media/icon.jpg',
        'fanart': 'special://home/addons/plugin.video.librarygenie/resources/media/fanart.jpg',
        'banner': 'special://home/addons/plugin.video.librarygenie/resources/media/banner.jpg',
        'landscape': 'special://home/addons/plugin.video.librarygenie/resources/media/landscape.jpg',
        'clearart': 'special://home/addons/plugin.video.librarygenie/resources/media/clearart.jpg',
        'clearlogo': 'special://home/addons/plugin.video.librarygenie/resources/media/clearlogo.png'
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

    for k, v in art.items():
        if not v:
            continue
        vv = v.strip()
        # Accept image:// as-is, wrap others when valid (http/file/smb/etc.)
        if vv.startswith("image://"):
            out[k] = _wrap_for_kodi_image(vv)  # add trailing slash if missing
            continue
        if _is_valid_art_url(vv):
            out[k] = _wrap_for_kodi_image(vv)
        else:
            # Last resort: if it *looks* like a URL but urlparse fails, try wrapping anyway
            if "://" in vv or vv.startswith("special://"):
                out[k] = _wrap_for_kodi_image(vv)
            else:
                xbmc.log(f"LibraryGenie [WARNING]: Skipping malformed artwork URL [{k}]: {vv}", xbmc.LOGINFO)
    return out


class ListItemBuilder:
    _item_cache = {}

    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}

        # LOG RAW MOVIE DETAILS
        # utils.log("=== LISTITEMBUILDER.BUILD_VIDEO_ITEM CALLED ===", "INFO")
        # utils.log("=== RAW MOVIE DETAILS START ===", "INFO")
        # utils.log(f"Raw media_info keys: {list(media_info.keys())}", "INFO")
        # utils.log(f"Title: {media_info.get('title', 'NOT_SET')}", "INFO")
        # utils.log(f"Year: {media_info.get('year', 'NOT_SET')}", "INFO")
        # utils.log(f"Plot: {media_info.get('plot', 'NOT_SET')[:200]}...", "INFO")
        # utils.log(f"Genre: {media_info.get('genre', 'NOT_SET')}", "INFO")
        # utils.log(f"Director: {media_info.get('director', 'NOT_SET')}", "INFO")
        # utils.log(f"Rating: {media_info.get('rating', 'NOT_SET')}", "INFO")
        # utils.log(f"Votes: {media_info.get('votes', 'NOT_SET')}", "INFO")
        # utils.log(f"Duration: {media_info.get('duration', 'NOT_SET')}", "INFO")
        # utils.log(f"Kodi ID: {media_info.get('kodi_id', 'NOT_SET')}", "INFO")
        # utils.log(f"Media Type: {media_info.get('media_type', media_info.get('mediatype', 'NOT_SET'))}", "INFO")
        # utils.log(f"Cast type: {type(media_info.get('cast', 'NOT_SET'))}, length: {len(media_info.get('cast', []))}", "INFO")
        # utils.log(f"Art keys: {list(media_info.get('art', {}).keys()) if isinstance(media_info.get('art'), dict) else 'NOT_DICT'}", "INFO")
        # utils.log(f"Poster: {media_info.get('poster', 'NOT_SET')}", "INFO")
        # utils.log(f"Fanart: {media_info.get('fanart', 'NOT_SET')}", "INFO")
        # utils.log(f"Play URL: {media_info.get('play', media_info.get('file', 'NOT_SET'))}", "INFO")
        # utils.log("=== RAW MOVIE DETAILS END ===", "INFO")

        # Generate cache key from stable fields
        cache_key = str(media_info.get('title', '')) + str(media_info.get('year', '')) + str(media_info.get('kodi_id', ''))
        if cache_key in ListItemBuilder._item_cache:
            # utils.log(f"Using cached ListItem for: {media_info.get('title', 'Unknown')}", "DEBUG")
            return ListItemBuilder._item_cache[cache_key]

        # Create ListItem with proper string title
        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)
        # utils.log(f"Created ListItem with title: {title}", "DEBUG")

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
            # utils.log(f"Setting poster paths: {poster_url}", "DEBUG")

        # Set fanart
        fanart = media_info.get('fanart') or media_info.get('info', {}).get('fanart')
        if fanart and str(fanart) != 'None':
            art_dict['fanart'] = fanart
            # utils.log(f"Setting fanart path: {fanart}", "DEBUG")

        # Use the specialized set_art function with improved normalization and fallbacks
        art_dict = _normalize_art_dict(art_dict, use_fallbacks=True)
        if art_dict:
            # utils.log("Setting art for ListItem", "DEBUG")
            set_art(list_item, art_dict)
            # utils.log(f"Art types set: {', '.join(set_art_types)}", "DEBUG")
        else:
            # utils.log("No valid artwork URLs found", "DEBUG")
            pass

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
                # utils.log(f"Converted year to int: {info_dict['year']}", "DEBUG")
            except (ValueError, TypeError):
                # utils.log(f"Failed to convert year: {media_info.get('year')}", "WARNING")
                pass

        if media_info.get('rating'):
            try:
                info_dict['rating'] = float(media_info['rating'])
                # utils.log(f"Converted rating to float: {info_dict['rating']}", "DEBUG")
            except (ValueError, TypeError):
                # utils.log(f"Failed to convert rating: {media_info.get('rating')}", "WARNING")
                pass

        if media_info.get('votes'):
            try:
                info_dict['votes'] = int(media_info['votes'])
                # utils.log(f"Converted votes to int: {info_dict['votes']}", "DEBUG")
            except (ValueError, TypeError):
                # utils.log(f"Failed to convert votes: {media_info.get('votes')}", "WARNING")
                pass

        # Handle cast data
        cast = media_info.get('cast', [])
        if cast:
            try:
                # Handle string-encoded cast data
                if isinstance(cast, str):
                    try:
                        cast = json.loads(cast)
                        # utils.log(f"Decoded cast JSON string, got {len(cast)} members", "DEBUG")
                    except json.JSONDecodeError:
                        # utils.log("Failed to decode cast JSON string", "ERROR")
                        cast = []

                # Ensure cast is a list
                if not isinstance(cast, list):
                    # utils.log(f"Cast is not a list, got type: {type(cast)}", "WARNING")
                    cast = []

                info_dict['cast'] = cast
                # utils.log(f"Processed cast with {len(cast)} members", "DEBUG")

            except Exception as e:
                # utils.log(f"Error processing cast: {str(e)}", "ERROR")
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
        # utils.log(f"Set info tag completed for: {title}", "DEBUG")

        # Set resume point if available
        if 'resumetime' in media_info and 'totaltime' in media_info:
            list_item.setProperty('ResumeTime', str(media_info['resumetime']))
            list_item.setProperty('TotalTime', str(media_info['totaltime']))
            # utils.log(f"Set resume properties - ResumeTime: {media_info['resumetime']}, TotalTime: {media_info['totaltime']}", "DEBUG")

        # Set content properties
        list_item.setProperty('IsPlayable', 'true')
        # utils.log("Set IsPlayable property to true", "DEBUG")

        # Try to get play URL from different possible locations
        play_url = media_info.get('info', {}).get('play') or media_info.get('play') or media_info.get('file')
        if play_url:
            list_item.setPath(play_url)
            # utils.log(f"Setting play URL: {play_url}", "DEBUG")
        else:
            # utils.log("No valid play URL found", "WARNING")
            pass

        # LOG FINAL LISTITEM STATUS
        # utils.log(f"=== FINAL LISTITEM STATUS FOR {title} ===", "INFO")
        # utils.log(f"ListItem Label: {list_item.getLabel()}", "INFO")
        # utils.log(f"ListItem Path: {list_item.getPath()}", "INFO")
        # utils.log(f"IsPlayable Property: {list_item.getProperty('IsPlayable')}", "INFO")
        # utils.log("=== LISTITEM BUILD COMPLETED ===", "INFO")

        ListItemBuilder._item_cache[cache_key] = list_item
        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem with folder-specific artwork"""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)

        # Set folder-specific artwork (using Kodi default folder icon for LibraryGenie folders)
        folder_art = {
            'icon': 'DefaultFolder.png',
            'thumb': 'DefaultFolder.png',
            'poster': 'DefaultFolder.png',
            'fanart': 'special://home/addons/plugin.video.librarygenie/resources/media/fanart.jpg'
        }
        folder_art = _normalize_art_dict(folder_art)
        if folder_art:
            set_art(list_item, folder_art)

        return list_item

    @staticmethod
    def build_list_item(name, is_folder=True):
        """Build a list ListItem with list-specific artwork"""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)

        # Set list-specific artwork (using Kodi default playlist icon for LibraryGenie lists)
        list_art = {
            'icon': 'DefaultPlaylist.png',
            'thumb': 'DefaultPlaylist.png', 
            'poster': 'DefaultPlaylist.png',
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