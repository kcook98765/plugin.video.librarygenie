from typing import Dict
from urllib.parse import quote
import json

import xbmc
from xbmcgui import ListItem
from resources.lib import utils

__all__ = ['set_info_tag', 'set_art']

# confirming via testing the following can be removed
# Initialize logging
#utils.log("ListItem InfoTagVideo module initialized", "INFO")
# class ListItemInfoTagVideo:
#    _instance = None
#    _initialized = False

#    def __new__(cls):
#        if cls._instance is None:
#            cls._instance = super(ListItemInfoTagVideo, cls).__new__(cls)
#        return cls._instance

#    def __init__(self):
#        if not ListItemInfoTagVideo._initialized:
#            utils.log("ListItem InfoTagVideo module initialized", "INFO")
#            ListItemInfoTagVideo._initialized = True

"""InfoTag compatibility helper for Kodi 19+ only - No support for Kodi 18 and below"""


def _set_full_cast(list_item: ListItem, cast_list: list) -> bool:
    """
    Version-agnostic cast setter optimized for Kodi v21+ with proper InfoTagVideo.setCast() priority.

    Args:
        list_item: The ListItem to set cast on
        cast_list: List of cast dicts with 'name', 'role', 'thumbnail', 'order' keys

    Returns:
        bool: True if cast was set with image support, False if fallback was used
    """
    if not cast_list:
        return False

    # Normalize inputs (avoid None values)
    norm = []
    for actor in cast_list:
        if isinstance(actor, dict):
            norm.append({
                'name': (actor.get('name') or '').strip(),
                'role': (actor.get('role') or '').strip(),
                'thumbnail': (actor.get('thumbnail') or '').strip(),
                'order': int(actor.get('order') or 0),
            })

    if not norm:
        return False

    # 1) Priority path for v21+: InfoTagVideo.setCast() with Actor objects
    try:
        import xbmcgui
        info = list_item.getVideoInfoTag()

        # Enhanced v21+ detection - check Kodi version directly
        if utils.get_kodi_version() >= 21 and hasattr(info, 'setCast') and hasattr(xbmcgui, 'Actor'):
            actors = []
            for actor in norm:
                if actor['name']:  # Only add actors with names
                    try:
                        actor_obj = xbmcgui.Actor(
                            name=str(actor['name']),
                            role=str(actor['role']),
                            order=int(actor['order']),
                            thumbnail=str(actor['thumbnail']) if actor['thumbnail'] else ""
                        )
                        actors.append(actor_obj)
                    except Exception:
                        continue

            if actors:
                info.setCast(actors)  # v21+ preferred InfoTagVideo method
                return True
    except Exception:
        pass

    # 2) Fallback for v19/v20: ListItem.setCast(list-of-dicts) - now deprecated in v21
    try:
        if hasattr(list_item, 'setCast'):
            # v19/v20 method: accepts dicts with name/role/thumbnail/order
            list_item.setCast(norm)
            return True
    except Exception:
        pass

    # 3) Last resort: names/roles only via setInfo (no images)
    try:
        simple_cast = []
        for actor in norm:
            if actor['name']:
                if actor['role']:
                    simple_cast.append((actor['name'], actor['role']))
                else:
                    simple_cast.append(actor['name'])

        if simple_cast:
            # Convert cast list to string format for setInfo compatibility
            cast_str = ' / '.join([f"{actor[0]} ({actor[1]})" if isinstance(actor, tuple) and len(actor) > 1 else str(actor) for actor in simple_cast])
            list_item.setInfo('video', {'cast': cast_str})
            return False
    except Exception:
        pass

    return False

def set_info_tag(list_item: ListItem, info_dict: Dict, content_type: str = 'video') -> None:
    """
    Set InfoTag for Kodi 19+ with proper error handling and fallback.
    Uses centralized version detection for optimal performance.
    """
    if not isinstance(info_dict, dict) or not info_dict:
        utils.log("Invalid or empty info_dict provided to set_info_tag", "WARNING")
        return

    # For Kodi v19, use setInfo directly since InfoTag setters are unreliable
    if utils.is_kodi_v19():
        try:
            # Clean up info_dict for setInfo compatibility
            clean_info = {}
            for key, value in info_dict.items():
                if not value:  # Skip empty values
                    continue

                # Handle cast with v19 ListItem.setCast() which supports thumbnails
                if key == 'cast' and isinstance(value, list):
                    _set_full_cast(list_item, value)
                    continue  # Don't add cast to clean_info since it's handled separately
                elif key in ['country', 'director', 'genre', 'studio'] and isinstance(value, list):
                    # Convert lists to comma-separated strings for setInfo
                    clean_info[key] = ' / '.join(str(item) for item in value if item)
                elif key == 'mediatype':
                    # Skip mediatype for v19 setInfo
                    continue
                elif key == 'uniqueid':
                    # Handle uniqueid for v19 - setInfo expects it as a dict but may not handle it properly
                    # Skip for setInfo and handle separately
                    continue
                else:
                    clean_info[key] = value
            
            # Handle uniqueid separately for v19 compatibility
            uniqueid_data = info_dict.get('uniqueid')
            if uniqueid_data and isinstance(uniqueid_data, dict):
                imdb_id = uniqueid_data.get('imdb')
                if imdb_id and str(imdb_id).startswith('tt'):
                    # Ensure imdbnumber is set for v19 compatibility
                    clean_info['imdbnumber'] = str(imdb_id)
                    utils.log(f"Set imdbnumber for v19 compatibility: {imdb_id}", "DEBUG")

            # Skip DBID for v19 non-playable items to prevent Information dialog conflicts
            # Only add DBID for actual playable library movies, not for options/folder items
            kodi_id = info_dict.get('kodi_id') or info_dict.get('movieid') or info_dict.get('id')
            file_path = info_dict.get('file', '')
            is_playable = file_path and not file_path.startswith('plugin://') and info_dict.get('mediatype') == 'movie'

            if kodi_id and is_playable:
                try:
                    clean_info['dbid'] = int(kodi_id)
                    utils.log(f"Added DBID to setInfo for playable library movie: {kodi_id}", "DEBUG")
                except (ValueError, TypeError):
                    pass
            elif kodi_id:
                utils.log(f"Skipped DBID for non-playable item to prevent v19 Information dialog: {kodi_id} (file: {file_path})", "DEBUG")

            list_item.setInfo(content_type, clean_info)

            # Handle resume data for v19 using properties (setInfo doesn't support resume)
            resume_data = info_dict.get('resume', {})
            if isinstance(resume_data, dict) and any(resume_data.values()):
                try:
                    position = float(resume_data.get('position', 0))
                    total = float(resume_data.get('total', 0))

                    if position > 0:
                        list_item.setProperty('resumetime', str(position))
                        if total > 0:
                            list_item.setProperty('totaltime', str(total))
                        utils.log(f"v19 resume properties set: {position}s of {total}s", "DEBUG")
                except (ValueError, TypeError) as resume_error:
                    utils.log(f"v19 resume data conversion failed: {str(resume_error)}", "WARNING")
        except Exception as setinfo_error:
            utils.log(f"setInfo failed for v19: {str(setinfo_error)}", "ERROR")

        return

    # For Kodi v20+, try InfoTag methods first with enhanced error handling
    try:
        # Get the InfoTag for the specified content type
        info_tag = list_item.getVideoInfoTag()

        # V20+ InfoTag method mapping with validation
        infotag_methods = {
            'title': 'setTitle',
            'plot': 'setPlot',
            'year': 'setYear',
            'rating': 'setRating',
            'votes': 'setVotes',
            'runtime': 'setDuration',
            'duration': 'setDuration',
            'tagline': 'setTagline',
            'originaltitle': 'setOriginalTitle',
            'director': 'setDirectors',
            'writer': 'setWriters',
            'genre': 'setGenres',
            'studio': 'setStudios',
            'country': 'setCountries',
            'mpaa': 'setMpaa',
            'premiered': 'setPremiered',
            'dateadded': 'setDateAdded',
            'imdbnumber': 'setIMDBNumber',
            'trailer': 'setTrailer'
        }

        # Set mediatype first for V20+
        mediatype = info_dict.get('mediatype', 'movie')
        if hasattr(info_tag, 'setMediaType'):
            try:
                info_tag.setMediaType(mediatype)
                # Set mediatype
            except Exception as e:
                utils.log(f"V20+ setMediaType failed: {str(e)}", "WARNING")

        # Process each property with improved V20+ handling
        infotag_success_count = 0

        for key, value in info_dict.items():
            if key == 'mediatype' or not value:
                continue

            try:
                # Special handling for cast with version-agnostic approach
                if key == 'cast' and isinstance(value, list):
                    cast_success = _set_full_cast(list_item, value)
                    if cast_success:
                        infotag_success_count += 1
                        # Cast set successfully
                    else:
                        utils.log("V20+ cast set without images (fallback used)", "DEBUG")

                elif key in ['year', 'runtime', 'duration', 'votes'] and isinstance(value, (int, str)):
                    # Integer properties
                    method_name = infotag_methods.get(key)
                    if method_name and hasattr(info_tag, method_name):
                        try:
                            int_value = int(value) if value else 0
                            if int_value > 0:
                                getattr(info_tag, method_name)(int_value)
                                infotag_success_count += 1
                                # numeric_fields[key][1](int_value)
                        except (ValueError, TypeError) as convert_error:
                            utils.log(f"V20+ {method_name} conversion failed: {str(convert_error)}", "WARNING")

                elif key == 'rating' and isinstance(value, (int, float, str)):
                    # Float rating property
                    if hasattr(info_tag, 'setRating'):
                        try:
                            float_value = float(value)
                            info_tag.setRating(float_value)
                            infotag_success_count += 1
                            # numeric_fields[key][1](float_value)
                        except (ValueError, TypeError) as rating_error:
                            utils.log(f"V20+ setRating failed: {str(rating_error)}", "WARNING")

                elif key in ['director', 'writer', 'genre', 'studio', 'country']:
                    # List properties that need special handling
                    method_name = infotag_methods.get(key)
                    if method_name and hasattr(info_tag, method_name):
                        try:
                            if isinstance(value, list):
                                # V20+ expects list format for these methods
                                clean_list = [str(item) for item in value if item]
                                if clean_list:
                                    getattr(info_tag, method_name)(clean_list)
                                    infotag_success_count += 1
                                    # string_list_fields[key][1](clean_list)
                            else:
                                # Convert string to list
                                items = [item.strip() for item in str(value).split('/') if item.strip()]
                                if items:
                                    getattr(info_tag, method_name)(items)
                                    infotag_success_count += 1
                                    # string_list_fields[key][1](items)
                        except Exception as list_error:
                            utils.log(f"V20+ {method_name} failed: {str(list_error)}", "WARNING")

                else:
                    # String properties
                    method_name = infotag_methods.get(key)
                    if method_name and hasattr(info_tag, method_name):
                        try:
                            getattr(info_tag, method_name)(str(value))
                            infotag_success_count += 1
                            if key == 'plot':
                                # Plot set successfully
                                pass
                            else:
                                # string_list_fields[key][1](str(value))
                                pass
                        except Exception as string_error:
                            utils.log(f"V20+ {method_name} failed: {str(string_error)}", "WARNING")

            except Exception as property_error:
                utils.log(f"V20+ InfoTag processing failed for {key}: {str(property_error)}", "WARNING")

        if infotag_success_count > 0:
            # Handle resume data with version-appropriate methods
            resume_data = info_dict.get('resume', {})
            if isinstance(resume_data, dict) and any(resume_data.values()):
                try:
                    position = float(resume_data.get('position', 0))
                    total = float(resume_data.get('total', 0))

                    if position > 0:
                        try:
                            if hasattr(info_tag, 'setResumePoint'):
                                info_tag.setResumePoint(position, total)
                                utils.log(f"V20+ setResumePoint successful: {position}s of {total}s", "DEBUG")
                            else:
                                # Fallback to property method
                                list_item.setProperty('resumetime', str(position))
                                if total > 0:
                                    list_item.setProperty('totaltime', str(total))
                                utils.log(f"V20+ resume fallback to properties: {position}s of {total}s", "DEBUG")
                        except Exception as resume_error:
                            # Final fallback to property method
                            list_item.setProperty('resumetime', str(position))
                            if total > 0:
                                list_item.setProperty('totaltime', str(total))
                            utils.log(f"V20+ resume error fallback: {str(resume_error)}", "WARNING")
                except (ValueError, TypeError) as resume_convert_error:
                    utils.log(f"V20+ resume data conversion failed: {str(resume_convert_error)}", "WARNING")

            # InfoTag methods completed
        else:
            utils.log("V20+ No InfoTag methods succeeded, falling back to setInfo", "WARNING")
            raise Exception(f"All V20+ InfoTag methods failed")

    except Exception as e:
        # Enhanced fallback to setInfo for v20+ if InfoTag fails
        utils.log(f"V20+ InfoTag failed, falling back to setInfo: {str(e)}", "WARNING")
        try:
            # Clean up info_dict for setInfo compatibility
            clean_info = {}
            for key, value in info_dict.items():
                if not value:
                    continue

                # Cast is handled separately by _set_full_cast function
                if key == 'cast' and isinstance(value, list):
                    cast_success = _set_full_cast(list_item, value)
                    utils.log(f"Fallback cast handling: {'success' if cast_success else 'no images'}", "DEBUG")
                    continue  # Skip adding to clean_info
                elif key in ['country', 'director', 'genre', 'studio'] and isinstance(value, list):
                    clean_info[key] = ' / '.join(str(item) for item in value if item)
                else:
                    clean_info[key] = value

            list_item.setInfo(content_type, clean_info)

            # Handle resume data for v20+ setInfo fallback using properties
            resume_data = info_dict.get('resume', {})
            if isinstance(resume_data, dict) and any(resume_data.values()):
                try:
                    position = float(resume_data.get('position', 0))
                    total = float(resume_data.get('total', 0))

                    if position > 0:
                        list_item.setProperty('resumetime', str(position))
                        if total > 0:
                            list_item.setProperty('totaltime', str(total))
                        utils.log(f"v20+ fallback resume properties set: {position}s of {total}s", "DEBUG")
                except (ValueError, TypeError) as resume_error:
                    utils.log(f"v20+ fallback resume data conversion failed: {str(resume_error)}", "WARNING")
        except Exception as fallback_error:
            utils.log(f"Fallback setInfo also failed: {str(fallback_error)}", "ERROR")


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)