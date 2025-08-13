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
        utils.log(f"Checking special:// file existence: {u} -> {real_path} (exists: {file_exists})", "INFO")
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
    from resources.lib import utils
    from resources.lib.addon_ref import get_addon
    addon = get_addon()
    addon_path = addon.getAddonInfo('path')

    utils.log("=== GETTING ADDON ARTWORK FALLBACKS ===", "INFO")
    utils.log(f"Addon path: {addon_path}", "INFO")

    # Use Kodi's special:// protocol which is the native way
    def make_addon_media_path(filename):
        # Use special://home/addons/ path which is the cleanest Kodi native approach
        path = f"special://home/addons/plugin.video.librarygenie/resources/media/{filename}"
        utils.log(f"Created media path for '{filename}': {path}", "INFO")
        return path

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

    utils.log("=== ADDON ARTWORK FALLBACKS CREATED ===", "INFO")
    for art_type, path in fallback_dict.items():
        utils.log(f"  {art_type}: {path}", "INFO")
    utils.log("=== END ADDON ARTWORK FALLBACKS ===", "INFO")

    return fallback_dict

def _normalize_art_dict(art: dict, use_fallbacks: bool = False) -> dict:
    from resources.lib import utils
    out = {}
    if not isinstance(art, dict):
        art = {}

    utils.log(f"=== NORMALIZING ART DICT (use_fallbacks={use_fallbacks}) ===", "INFO")
    utils.log(f"Input art dict: {art}", "INFO")

    # Add addon artwork as fallbacks if requested
    if use_fallbacks:
        utils.log("Adding fallback artwork...", "INFO")
        fallbacks = _get_addon_artwork_fallbacks()
        for k, v in fallbacks.items():
            if k not in art or not art[k]:
                utils.log(f"Using fallback for '{k}': {v}", "INFO")
                art[k] = v
            else:
                utils.log(f"Keeping existing '{k}': {art[k]}", "INFO")

    utils.log("Processing art URLs...", "INFO")
    for k, v in art.items():
        if not v:
            utils.log(f"Skipping empty value for '{k}'", "INFO")
            continue
        vv = v.strip()
        utils.log(f"Processing '{k}': '{vv}'", "INFO")

        # Accept image:// as-is, wrap others when valid (http/file/smb/etc.)
        if vv.startswith("image://"):
            wrapped = _wrap_for_kodi_image(vv)  # add trailing slash if missing
            out[k] = wrapped
            utils.log(f"  -> Already image:// format, wrapped to: '{wrapped}'", "INFO")
            continue

        if vv.startswith("special://"):
            wrapped = _wrap_for_kodi_image(vv)  # returns special:// path directly
            out[k] = wrapped
            utils.log(f"  -> Using special:// path directly: '{wrapped}'", "INFO")
            continue

        if _is_valid_art_url(vv):
            wrapped = _wrap_for_kodi_image(vv)
            out[k] = wrapped
            utils.log(f"  -> Valid URL, wrapped to: '{wrapped}'", "INFO")
        else:
            # Last resort: if it *looks* like a URL but urlparse fails, try wrapping anyway
            if "://" in vv:
                wrapped = _wrap_for_kodi_image(vv)
                out[k] = wrapped
                utils.log(f"  -> Looks like URL, wrapped anyway to: '{wrapped}'", "INFO")
            else:
                utils.log(f"  -> Skipping malformed artwork URL [{k}]: {vv}", "WARNING")
                xbmc.log(f"LibraryGenie [WARNING]: Skipping malformed artwork URL [{k}]: {vv}", xbmc.LOGINFO)

    utils.log(f"=== FINAL NORMALIZED ART DICT ===", "INFO")
    for art_type, path in out.items():
        utils.log(f"  {art_type}: {path}", "INFO")
    utils.log("=== END ART NORMALIZATION ===", "INFO")

    return out


class ListItemBuilder:
    _item_cache = {}

    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}

        # LOG RAW MOVIE DETAILS
        utils.log("=== LISTITEMBUILDER.BUILD_VIDEO_ITEM CALLED ===", "INFO")
        utils.log("=== RAW MOVIE DETAILS START ===", "INFO")
        utils.log(f"Raw media_info keys: {list(media_info.keys())}", "INFO")
        utils.log(f"Title: {media_info.get('title', 'NOT_SET')}", "INFO")
        utils.log(f"Year: {media_info.get('year', 'NOT_SET')}", "INFO")
        utils.log(f"Plot: {media_info.get('plot', 'NOT_SET')[:200]}...", "INFO")
        utils.log(f"Genre: {media_info.get('genre', 'NOT_SET')}", "INFO")
        utils.log(f"Director: {media_info.get('director', 'NOT_SET')}", "INFO")
        utils.log(f"Rating: {media_info.get('rating', 'NOT_SET')}", "INFO")
        utils.log(f"Votes: {media_info.get('votes', 'NOT_SET')}", "INFO")
        utils.log(f"Duration: {media_info.get('duration', 'NOT_SET')}", "INFO")
        utils.log(f"Kodi ID: {media_info.get('kodi_id', 'NOT_SET')}", "INFO")
        utils.log(f"Media Type: {media_info.get('media_type', media_info.get('mediatype', 'NOT_SET'))}", "INFO")
        utils.log(f"Cast type: {type(media_info.get('cast', 'NOT_SET'))}, length: {len(media_info.get('cast', []))}", "INFO")
        utils.log(f"Art keys: {list(media_info.get('art', {}).keys()) if isinstance(media_info.get('art'), dict) else 'NOT_DICT'}", "INFO")
        utils.log(f"Poster: {media_info.get('poster', 'NOT_SET')}", "INFO")
        utils.log(f"Fanart: {media_info.get('fanart', 'NOT_SET')}", "INFO")
        utils.log(f"Play URL: {media_info.get('play', media_info.get('file', 'NOT_SET'))}", "INFO")
        utils.log("=== RAW MOVIE DETAILS END ===", "INFO")

        # Generate cache key from stable fields
        cache_key = str(media_info.get('title', '')) + str(media_info.get('year', '')) + str(media_info.get('kodi_id', ''))
        if cache_key in ListItemBuilder._item_cache:
            utils.log(f"Using cached ListItem for: {media_info.get('title', 'Unknown')}", "DEBUG")
            return ListItemBuilder._item_cache[cache_key]

        # Create ListItem with proper string title
        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)
        utils.log(f"Created ListItem with title: {title}", "DEBUG")

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
            utils.log(f"Setting poster paths: {poster_url}", "DEBUG")

        # Set fanart
        fanart = media_info.get('fanart') or media_info.get('info', {}).get('fanart')
        if fanart and str(fanart) != 'None':
            art_dict['fanart'] = fanart
            utils.log(f"Setting fanart path: {fanart}", "DEBUG")

        # Use the specialized set_art function with improved normalization and fallbacks
        art_dict = _normalize_art_dict(art_dict, use_fallbacks=True)
        if art_dict:
            utils.log("Setting art for ListItem", "DEBUG")
            set_art(list_item, art_dict)
            utils.log(f"Art types set: {', '.join(art_dict.keys())}", "DEBUG")
        else:
            utils.log("No valid artwork URLs found", "DEBUG")

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
                utils.log(f"Converted year to int: {info_dict['year']}", "DEBUG")
            except (ValueError, TypeError):
                utils.log(f"Failed to convert year: {media_info.get('year')}", "WARNING")
                pass

        if media_info.get('rating'):
            try:
                info_dict['rating'] = float(media_info['rating'])
                utils.log(f"Converted rating to float: {info_dict['rating']}", "DEBUG")
            except (ValueError, TypeError):
                utils.log(f"Failed to convert rating: {media_info.get('rating')}", "WARNING")
                pass

        if media_info.get('votes'):
            try:
                info_dict['votes'] = int(media_info['votes'])
                utils.log(f"Converted votes to int: {info_dict['votes']}", "DEBUG")
            except (ValueError, TypeError):
                utils.log(f"Failed to convert votes: {media_info.get('votes')}", "WARNING")
                pass

        # Handle cast data
        cast = media_info.get('cast', [])
        if cast:
            try:
                # Handle string-encoded cast data
                if isinstance(cast, str):
                    try:
                        cast = json.loads(cast)
                        utils.log(f"Decoded cast JSON string, got {len(cast)} members", "DEBUG")
                    except json.JSONDecodeError:
                        utils.log("Failed to decode cast JSON string", "ERROR")
                        cast = []

                # Ensure cast is a list
                if not isinstance(cast, list):
                    utils.log(f"Cast is not a list, got type: {type(cast)}", "WARNING")
                    cast = []

                info_dict['cast'] = cast
                utils.log(f"Processed cast with {len(cast)} members", "DEBUG")

            except Exception as e:
                utils.log(f"Error processing cast: {str(e)}", "ERROR")
                info_dict['cast'] = []

        # LOG PROCESSED INFO_DICT BEFORE SETTING
        utils.log("=== INFO_DICT TO BE SET START ===", "INFO")
        for key, value in info_dict.items():
            if key == 'cast' and isinstance(value, list):
                utils.log(f"  {key}: [{len(value)} cast members]", "INFO")
            else:
                utils.log(f"  {key}: {value}", "INFO")
        utils.log("=== INFO_DICT TO BE SET END ===", "INFO")

        # Use the specialized set_info_tag function that handles Kodi version compatibility
        set_info_tag(list_item, info_dict, 'video')
        utils.log(f"Set info tag completed for: {title}", "DEBUG")

        # Set resume point if available
        if 'resumetime' in media_info and 'totaltime' in media_info:
            list_item.setProperty('ResumeTime', str(media_info['resumetime']))
            list_item.setProperty('TotalTime', str(media_info['totaltime']))
            utils.log(f"Set resume properties - ResumeTime: {media_info['resumetime']}, TotalTime: {media_info['totaltime']}", "DEBUG")

        # Set content properties
        list_item.setProperty('IsPlayable', 'true')
        utils.log("Set IsPlayable property to true", "DEBUG")

        # Try to get play URL from different possible locations
        play_url = media_info.get('info', {}).get('play') or media_info.get('play') or media_info.get('file')
        if play_url:
            list_item.setPath(play_url)
            utils.log(f"Setting play URL: {play_url}", "DEBUG")
        else:
            utils.log("No valid play URL found", "WARNING")

        # LOG FINAL LISTITEM STATUS
        utils.log(f"=== FINAL LISTITEM STATUS FOR {title} ===", "INFO")
        utils.log(f"ListItem Label: {list_item.getLabel()}", "INFO")
        utils.log(f"ListItem Path: {list_item.getPath()}", "INFO")
        utils.log(f"IsPlayable Property: {list_item.getProperty('IsPlayable')}", "INFO")
        utils.log("=== LISTITEM BUILD COMPLETED ===", "INFO")

        ListItemBuilder._item_cache[cache_key] = list_item
        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem with folder-specific artwork"""
        utils.log(f"=== BUILDING FOLDER ITEM: '{name}' ===", "INFO")
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)

        # Set folder-specific artwork using Kodi's special:// protocol
        folder_art = {
            'icon': 'special://home/addons/plugin.video.librarygenie/resources/media/list_folder_icon.png',
            'thumb': 'special://home/addons/plugin.video.librarygenie/resources/media/list_folder_icon.png',
            'poster': 'special://home/addons/plugin.video.librarygenie/resources/media/list_folder_icon.png',
            'fanart': 'special://home/addons/plugin.video.librarygenie/resources/media/fanart.jpg'
        }
        utils.log(f"Raw folder art dict: {folder_art}", "INFO")

        folder_art = _normalize_art_dict(folder_art)
        if folder_art:
            utils.log(f"Setting folder art with {len(folder_art)} items", "INFO")
            set_art(list_item, folder_art)
            utils.log("Folder artwork set successfully", "INFO")
        else:
            utils.log("No valid folder artwork to set", "WARNING")

        # Log complete ListItem details for debugging
        utils.log(f"=== COMPLETE FOLDER LISTITEM DETAILS FOR '{name}' ===", "INFO")
        utils.log(f"Label: {list_item.getLabel()}", "INFO")
        utils.log(f"Label2: '{list_item.getLabel2()}'", "INFO")
        utils.log(f"Path: {list_item.getPath()}", "INFO")
        utils.log(f"IsFolder: {list_item.isFolder()}", "INFO")

        # Log all properties
        properties_to_check = [
            'IsPlayable', 'ResumeTime', 'TotalTime', 'Art(icon)', 'Art(thumb)',
            'Art(poster)', 'Art(fanart)', 'Art(banner)', 'Art(landscape)'
        ]
        for prop in properties_to_check:
            prop_value = list_item.getProperty(prop)
            if prop_value:
                utils.log(f"Property {prop}: {prop_value}", "INFO")

        utils.log(f"=== END COMPLETE FOLDER LISTITEM DETAILS ===", "INFO")
        utils.log(f"=== FOLDER ITEM '{name}' BUILD COMPLETE ===", "INFO")
        return list_item

    @staticmethod
    def build_list_item(name, is_folder=True, list_data=None):
        """Build a list ListItem with list-specific artwork and enhanced metadata"""
        utils.log(f"=== BUILDING LIST ITEM: '{name}' ===", "INFO")
        utils.log(f"=== LIST_DATA DEBUG INFO ===", "INFO")
        utils.log(f"list_data provided: {list_data is not None}", "INFO")
        if list_data:
            utils.log(f"list_data type: {type(list_data)}", "INFO")
            utils.log(f"list_data keys: {list(list_data.keys()) if isinstance(list_data, dict) else 'NOT_DICT'}", "INFO")
            utils.log(f"list_data contents: {list_data}", "INFO")
        utils.log(f"=== END LIST_DATA DEBUG INFO ===", "INFO")

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
                utils.log(f"Enhanced search history list label: '{display_name}'", "DEBUG")
            else:
                # For regular lists, keep original name but set informative label2
                label2_text = f"Created {date_str} • {item_count} movies"
                utils.log(f"Set label2 for regular list: '{label2_text}'", "DEBUG")

        list_item = xbmcgui.ListItem(label=display_name)
        
        # Set label2 for enhanced display information
        if label2_text:
            list_item.setLabel2(label2_text)
            utils.log(f"Set label2 to: '{label2_text}'", "DEBUG")
        else:
            # Fallback label2 for lists without data
            list_item.setLabel2("Movie List")
            utils.log("Set fallback label2: 'Movie List'", "DEBUG")
        list_item.setIsFolder(is_folder)

        # Set list-specific artwork using Kodi's special:// protocol
        list_art = {
            'icon': 'special://home/addons/plugin.video.librarygenie/resources/media/list_playlist_icon.png',
            'thumb': 'special://home/addons/plugin.video.librarygenie/resources/media/list_playlist_icon.png',
            'poster': 'special://home/addons/plugin.video.librarygenie/resources/media/list_playlist_icon.png',
            'fanart': 'special://home/addons/plugin.video.librarygenie/resources/media/fanart.jpg'
        }
        utils.log(f"Raw list art dict: {list_art}", "INFO")

        list_art = _normalize_art_dict(list_art)
        if list_art:
            utils.log(f"Setting list art with {len(list_art)} items", "INFO")
            set_art(list_item, list_art)
            utils.log("List artwork set successfully", "INFO")
        else:
            utils.log("No valid list artwork to set", "WARNING")

        # Log complete ListItem details for debugging
        utils.log(f"=== COMPLETE LIST LISTITEM DETAILS FOR '{display_name}' ===", "INFO")
        utils.log(f"Original name: {name}", "INFO")
        utils.log(f"Display name: {display_name}", "INFO")
        utils.log(f"Label: {list_item.getLabel()}", "INFO")
        utils.log(f"Label2: '{list_item.getLabel2()}'", "INFO")
        utils.log(f"Path: {list_item.getPath()}", "INFO")
        utils.log(f"IsFolder: {list_item.isFolder()}", "INFO")

        # Log all properties
        properties_to_check = [
            'IsPlayable', 'ResumeTime', 'TotalTime', 'Art(icon)', 'Art(thumb)',
            'Art(poster)', 'Art(fanart)', 'Art(banner)', 'Art(landscape)'
        ]
        for prop in properties_to_check:
            prop_value = list_item.getProperty(prop)
            if prop_value:
                utils.log(f"Property {prop}: {prop_value}", "INFO")

        # Log list-specific metadata if available
        if list_data:
            utils.log(f"List data provided - ID: {list_data.get('id')}, Folder ID: {list_data.get('folder_id')}", "INFO")
            utils.log(f"Created at: {list_data.get('created_at', 'NOT_SET')}", "INFO")
        else:
            utils.log("No list_data provided for enhanced metadata", "INFO")

        utils.log(f"=== END COMPLETE LIST LISTITEM DETAILS ===", "INFO")
        utils.log(f"=== LIST ITEM '{name}' BUILD COMPLETE ===", "INFO")
        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)