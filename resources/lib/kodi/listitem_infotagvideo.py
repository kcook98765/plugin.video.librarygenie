from typing import Dict
from urllib.parse import quote
from xbmcgui import ListItem
from resources.lib.utils import utils

__all__ = ['set_info_tag', 'set_art']

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

    # 3) Last resort for v19 ONLY: setInfo fallback (NEVER for v20+)
    if utils.get_kodi_version() == 19:
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
                # Skip None, empty, or invalid values
                if value is None or (isinstance(value, (str, list, dict)) and not value):
                    continue

                # Handle cast with v19 ListItem.setCast() which supports thumbnails
                if key == 'cast' and isinstance(value, list):
                    try:
                        _set_full_cast(list_item, value)
                    except Exception as cast_error:
                        utils.log(f"v19 cast setting failed: {str(cast_error)}", "WARNING")
                    continue  # Don't add cast to clean_info since it's handled separately
                elif key in ['country', 'director', 'genre', 'studio', 'writer'] and isinstance(value, list):
                    # Convert lists to comma-separated strings for setInfo - ensure all items are strings
                    string_items = []
                    for item in value:
                        if item is not None and str(item).strip():
                            string_items.append(str(item).strip())
                    if string_items:
                        clean_info[key] = ' / '.join(string_items)
                elif key == 'mediatype':
                    # Skip mediatype for v19 setInfo
                    continue
                elif key == 'uniqueid':
                    # Handle uniqueid for v19 - setInfo expects it as a dict but may not handle it properly
                    # Skip for setInfo and handle separately
                    continue
                elif key == 'ratings':
                    # Skip ratings dict for v19 setInfo - it can't handle complex rating structures
                    continue
                elif key == 'streamdetails':
                    # Skip streamdetails for v19 setInfo
                    continue
                elif key == 'resume':
                    # Skip resume for v19 setInfo - handle separately with properties
                    continue
                else:
                    # Ensure all other values are properly converted to strings/numbers for v19
                    if isinstance(value, (int, float)):
                        clean_info[key] = value
                    elif isinstance(value, str) and value.strip():
                        clean_info[key] = value.strip()
                    elif value is not None:
                        # Convert other types to string, but skip empty results
                        str_value = str(value).strip()
                        if str_value and str_value != 'None':
                            clean_info[key] = str_value

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

    # For Kodi v20+, use InfoTag methods exclusively to avoid deprecation warnings
    # v20+ implementation using InfoTagVideo methods - NO setInfo fallbacks
    if not utils.is_kodi_v19():
        # Abort guard - prevent any setInfo calls on v20+
        utils.log("InfoTagVideo: Using v20+ InfoTag methods (no setInfo fallbacks)", "DEBUG")

    info_tag = list_item.getVideoInfoTag()
    if not info_tag:
        utils.log("InfoTagVideo: No InfoTagVideo available for v20+", "ERROR")
        # Emergency fallback: just set the label and continue - NO setInfo
        if info_dict.get('title'):
            list_item.setLabel(str(info_dict['title']))
        return

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
        except Exception as e:
            utils.log(f"V20+ setMediaType failed: {str(e)}", "DEBUG")

    # Process each property with improved V20+ handling - continue on individual failures
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

            elif key in ['year', 'runtime', 'duration', 'votes'] and isinstance(value, (int, str)):
                # Integer properties
                method_name = infotag_methods.get(key)
                if method_name and hasattr(info_tag, method_name):
                    try:
                        int_value = int(value) if value else 0
                        if int_value > 0:
                            getattr(info_tag, method_name)(int_value)
                            infotag_success_count += 1
                    except (ValueError, TypeError):
                        # Skip invalid values silently for v20+
                        pass

            elif key == 'rating' and isinstance(value, (int, float, str)):
                # Float rating property
                if hasattr(info_tag, 'setRating'):
                    try:
                        float_value = float(value)
                        info_tag.setRating(float_value)
                        infotag_success_count += 1
                    except (ValueError, TypeError):
                        # Skip invalid values silently for v20+
                        pass

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
                        else:
                            # Convert string to list
                            items = [item.strip() for item in str(value).split('/') if item.strip()]
                            if items:
                                getattr(info_tag, method_name)(items)
                                infotag_success_count += 1
                    except Exception:
                        # Continue processing other fields even if one fails
                        pass

            else:
                # String properties
                method_name = infotag_methods.get(key)
                if method_name and hasattr(info_tag, method_name):
                    try:
                        getattr(info_tag, method_name)(str(value))
                        infotag_success_count += 1
                    except Exception:
                        # Continue processing other fields even if one fails
                        pass

        except Exception:
            # Continue processing other properties even if one fails
            continue

    # Handle uniqueid with v20+ InfoTag methods
    uniqueid_data = info_dict.get('uniqueid', {})
    if isinstance(uniqueid_data, dict) and uniqueid_data:
        try:
            if hasattr(info_tag, 'setUniqueIDs'):
                # v20+ method for setting multiple unique IDs
                info_tag.setUniqueIDs(uniqueid_data)
                infotag_success_count += 1
            elif hasattr(info_tag, 'setUniqueID'):
                # Fallback: set individual unique IDs
                for source, uid in uniqueid_data.items():
                    if uid:
                        try:
                            info_tag.setUniqueID(str(uid), str(source))
                            infotag_success_count += 1
                            break  # Only set first one if setUniqueIDs not available
                        except Exception:
                            continue
        except Exception:
            pass

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
                    else:
                        # Fallback to property method for older v20
                        list_item.setProperty('resumetime', str(position))
                        if total > 0:
                            list_item.setProperty('totaltime', str(total))
                except Exception:
                    # Final fallback to property method
                    list_item.setProperty('resumetime', str(position))
                    if total > 0:
                        list_item.setProperty('totaltime', str(total))
        except (ValueError, TypeError):
            pass

    # For v20+, completely avoid any setInfo fallback to prevent deprecation warnings
    utils.log(f"V20+ InfoTag processing completed with {infotag_success_count} successful fields - no setInfo fallback", "DEBUG")

    # If InfoTag completely failed, only set essential label - no setInfo on v20+
    if infotag_success_count < 1:
        title = info_dict.get('title')
        if title:
            list_item.setLabel(str(title))
            utils.log("V20+ InfoTag failed completely - set label only, no deprecated setInfo", "DEBUG")

    else:
        utils.log(f"V20+ InfoTag processing completed successfully with {infotag_success_count} fields set.", "DEBUG")

    # NOTE: The original code had an explicit return False here for v20+ if InfoTagVideo was not available.
    # However, the primary goal is to avoid deprecated setInfo calls.
    # If InfoTagVideo is unavailable, the subsequent operations within this block will handle it gracefully.
    # The logic above already includes fallbacks for label setting.


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)