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

def set_info_tag(list_item: ListItem, info_dict: Dict, content_type: str = 'video') -> None:
    """
    Set InfoTag for Kodi 19+ with proper error handling and fallback.
    Uses centralized version detection for optimal performance.
    """
    if not isinstance(info_dict, dict) or not info_dict:
        utils.log("Invalid or empty info_dict provided to set_info_tag", "WARNING")
        return

    title = info_dict.get('title', 'Unknown')
    plot = info_dict.get('plot', '')
    utils.log(f"=== SET_INFO_TAG START for '{title}' ===", "INFO")
    utils.log(f"Info dict has {len(info_dict)} keys: {list(info_dict.keys())}", "DEBUG")

    if plot:
        plot_preview = str(plot)[:100] + "..." if len(str(plot)) > 100 else str(plot)
        utils.log(f"Plot to be set: '{plot_preview}' (length: {len(str(plot))})", "INFO")
    else:
        utils.log("No plot to be set", "WARNING")

    # Use centralized version detection
    utils.log(f"Using cached Kodi version: {utils.get_kodi_version()}", "DEBUG")

    # For Kodi v19, use setInfo directly since InfoTag setters are unreliable
    if utils.is_kodi_v19():
        utils.log("Using setInfo method for Kodi v19", "INFO")
        try:
            # Clean up info_dict for setInfo compatibility
            clean_info = {}
            for key, value in info_dict.items():
                if not value:  # Skip empty values
                    continue

                # Handle special data types for setInfo
                if key == 'cast' and isinstance(value, list):
                    # Convert cast list to simple list of actor names for setInfo
                    try:
                        if all(isinstance(actor, dict) for actor in value):
                            clean_info[key] = [actor.get('name', '') for actor in value if actor.get('name')]
                        else:
                            clean_info[key] = [str(actor) for actor in value]
                    except Exception:
                        pass  # Skip cast if conversion fails
                elif key in ['country', 'director', 'genre', 'studio'] and isinstance(value, list):
                    # Convert lists to comma-separated strings for setInfo
                    clean_info[key] = ' / '.join(str(item) for item in value if item)
                elif key == 'mediatype':
                    # Skip mediatype for v19 setInfo
                    continue
                else:
                    clean_info[key] = value

            utils.log(f"Using setInfo with {len(clean_info)} properties for v19", "INFO")
            if 'plot' in clean_info:
                plot_preview = str(clean_info['plot'])[:100] + "..." if len(str(clean_info['plot'])) > 100 else str(clean_info['plot'])
                utils.log(f"setInfo plot: '{plot_preview}' (length: {len(str(clean_info['plot']))})", "INFO")

            list_item.setInfo(content_type, clean_info)
            utils.log("setInfo completed successfully for v19", "INFO")

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

        utils.log(f"=== SET_INFO_TAG COMPLETE for '{title}' ===", "INFO")
        return

    # For Kodi v20+, try InfoTag methods first with enhanced error handling
    try:
        # Get the InfoTag for the specified content type
        if content_type == 'video':
            info_tag = list_item.getVideoInfoTag()
        elif content_type == 'music':
            info_tag = list_item.getMusicInfoTag()
        else:
            utils.log(f"Unsupported content type: {content_type}", "WARNING")
            return

        utils.log(f"V20+ InfoTag object obtained: {type(info_tag)}", "DEBUG")

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
                utils.log(f"Successfully set mediatype: {mediatype}", "DEBUG")
            except Exception as e:
                utils.log(f"V20+ setMediaType failed: {str(e)}", "WARNING")

        # Process each property with improved V20+ handling
        infotag_success_count = 0

        for key, value in info_dict.items():
            if key == 'mediatype' or not value:
                continue

            try:
                # Special handling for complex data types
                if key == 'cast' and isinstance(value, list):
                    if hasattr(info_tag, 'setCast'):
                        try:
                            # V20+ setCast requires Actor objects, but has compatibility issues
                            # For now, skip setCast and let fallback handle cast via setInfo
                            utils.log(f"V20+ setCast skipped due to API compatibility issues with {len(value)} actors", "DEBUG")
                            # Note: Cast will be handled by fallback setInfo if InfoTag fails completely
                        except Exception as cast_error:
                            utils.log(f"V20+ setCast failed: {str(cast_error)}", "WARNING")

                elif key in ['year', 'runtime', 'duration', 'votes'] and isinstance(value, (int, str)):
                    # Integer properties
                    method_name = infotag_methods.get(key)
                    if method_name and hasattr(info_tag, method_name):
                        try:
                            int_value = int(value) if value else 0
                            if int_value > 0:
                                getattr(info_tag, method_name)(int_value)
                                infotag_success_count += 1
                                utils.log(f"V20+ {method_name} set to {int_value}", "DEBUG")
                        except (ValueError, TypeError) as convert_error:
                            utils.log(f"V20+ {method_name} conversion failed: {str(convert_error)}", "WARNING")

                elif key == 'rating' and isinstance(value, (int, float, str)):
                    # Float rating property
                    if hasattr(info_tag, 'setRating'):
                        try:
                            float_value = float(value)
                            info_tag.setRating(float_value)
                            infotag_success_count += 1
                            utils.log(f"V20+ setRating set to {float_value}", "DEBUG")
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
                                    utils.log(f"V20+ {method_name} set with {len(clean_list)} items", "DEBUG")
                            else:
                                # Convert string to list
                                items = [item.strip() for item in str(value).split('/') if item.strip()]
                                if items:
                                    getattr(info_tag, method_name)(items)
                                    infotag_success_count += 1
                                    utils.log(f"V20+ {method_name} set from string", "DEBUG")
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
                                utils.log(f"V20+ setPlot successful - length: {len(str(value))}", "INFO")
                            else:
                                utils.log(f"V20+ {method_name} set successfully", "DEBUG")
                        except Exception as string_error:
                            utils.log(f"V20+ {method_name} failed: {str(string_error)}", "WARNING")

            except Exception as property_error:
                utils.log(f"V20+ InfoTag processing failed for {key}: {str(property_error)}", "WARNING")

        if infotag_success_count > 0:
            # Handle cast separately using setInfo fallback since InfoTag setCast has compatibility issues
            cast_data = info_dict.get('cast', [])
            if cast_data and isinstance(cast_data, list):
                try:
                    utils.log(f"V20+ InfoTag succeeded but cast needs setInfo fallback for {len(cast_data)} actors", "DEBUG")
                    # Convert cast list to simple list of actor names for setInfo
                    cast_names = []
                    if all(isinstance(actor, dict) for actor in cast_data):
                        cast_names = [actor.get('name', '') for actor in cast_data if actor.get('name')]
                    else:
                        cast_names = [str(actor) for actor in cast_data]
                    
                    if cast_names:
                        # Use setInfo specifically for cast data
                        cast_info = {'cast': cast_names}
                        list_item.setInfo(content_type, cast_info)
                        utils.log(f"V20+ Cast set via setInfo fallback: {len(cast_names)} actors", "DEBUG")
                except Exception as cast_fallback_error:
                    utils.log(f"V20+ Cast setInfo fallback failed: {str(cast_fallback_error)}", "WARNING")

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

            utils.log(f"V20+ InfoTag methods successful: {infotag_success_count} properties set", "INFO")
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

                if key == 'cast' and isinstance(value, list):
                    try:
                        if all(isinstance(actor, dict) for actor in value):
                            clean_info[key] = [actor.get('name', '') for actor in value if actor.get('name')]
                        else:
                            clean_info[key] = [str(actor) for actor in value]
                    except Exception:
                        pass
                elif key in ['country', 'director', 'genre', 'studio'] and isinstance(value, list):
                    clean_info[key] = ' / '.join(str(item) for item in value if item)
                else:
                    clean_info[key] = value

            list_item.setInfo(content_type, clean_info)
            utils.log("setInfo fallback completed successfully for v20+", "INFO")

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

    utils.log(f"=== SET_INFO_TAG COMPLETE for '{title}' ===", "INFO")


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    # utils.log("Setting art for ListItem", "DEBUG")
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)
    # utils.log(f"Art types set: {', '.join(art.keys())}", "DEBUG")