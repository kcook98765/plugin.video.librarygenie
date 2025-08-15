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

def get_kodi_version() -> int:
    """
    Get the major version number of the current Kodi installation.
    Minimum supported version: Kodi 19 (Matrix)
    """
    version_info = xbmc.getInfoLabel("System.BuildVersion")
    return int(version_info.split('.')[0])

"""InfoTag compatibility helper for Kodi 19+ only - No support for Kodi 18 and below"""

def set_info_tag(list_item: ListItem, info_dict: Dict, content_type: str = 'video') -> None:
    """
    Set InfoTag for Kodi 19+ with proper error handling and fallback.
    Minimum supported version: Kodi 19 (Matrix)
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

    kodi_version = get_kodi_version()
    utils.log(f"Using Kodi version: {kodi_version}", "DEBUG")

    # For Kodi v19, use setInfo directly since InfoTag setters are unreliable
    if kodi_version < 20:
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
        except Exception as setinfo_error:
            utils.log(f"setInfo failed for v19: {str(setinfo_error)}", "ERROR")
        
        utils.log(f"=== SET_INFO_TAG COMPLETE for '{title}' ===", "INFO")
        return

    # For Kodi v20+, try InfoTag methods first
    try:
        # Get the InfoTag for the specified content type
        if content_type == 'video':
            info_tag = list_item.getVideoInfoTag()
        elif content_type == 'music':
            info_tag = list_item.getMusicInfoTag()
        else:
            utils.log(f"Unsupported content type: {content_type}", "WARNING")
            return

        # Set mediatype for Kodi 20+
        mediatype = info_dict.get('mediatype')
        if mediatype and hasattr(info_tag, 'setMediaType'):
            try:
                info_tag.setMediaType(mediatype)
                utils.log(f"Successfully set mediatype: {mediatype}", "DEBUG")
            except Exception as e:
                utils.log(f"Error setting mediatype: {str(e)}", "DEBUG")

        # Set other properties using InfoTag methods
        infotag_success = False
        for key, value in info_dict.items():
            if key == 'mediatype' or not value:  # Skip mediatype (handled above) and empty values
                continue

            try:
                # Handle special cases for v20+
                if key == 'year' and isinstance(value, (int, str)):
                    if hasattr(info_tag, 'setYear'):
                        year_val = int(value) if value else 0
                        if year_val > 0:
                            info_tag.setYear(year_val)
                            infotag_success = True
                elif key == 'rating' and isinstance(value, (int, float, str)):
                    if hasattr(info_tag, 'setRating'):
                        info_tag.setRating(float(value))
                        infotag_success = True
                elif key == 'votes' and isinstance(value, (int, str)):
                    if hasattr(info_tag, 'setVotes'):
                        votes_val = int(value) if value else 0
                        if votes_val > 0:
                            info_tag.setVotes(votes_val)
                            infotag_success = True
                elif key == 'cast' and isinstance(value, list):
                    if hasattr(info_tag, 'setCast'):
                        info_tag.setCast(value)
                        infotag_success = True
                elif hasattr(info_tag, f'set{key.capitalize()}'):
                    # Generic setter (e.g., setTitle, setPlot, etc.)
                    setter = getattr(info_tag, f'set{key.capitalize()}')
                    setter(str(value))
                    infotag_success = True
                    if key == 'plot':
                        utils.log(f"Successfully set plot via InfoTag - length: {len(str(value))}", "INFO")

            except Exception as e:
                utils.log(f"InfoTag setter failed for {key}: {str(e)}", "WARNING")

        if infotag_success:
            utils.log("InfoTag methods successful for v20+", "INFO")
        else:
            utils.log("No InfoTag methods succeeded, falling back to setInfo", "WARNING")
            raise Exception("InfoTag methods failed")

    except Exception as e:
        # Fall back to setInfo for v20+ if InfoTag fails
        utils.log(f"InfoTag failed for v20+, falling back to setInfo: {str(e)}", "WARNING")
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
        except Exception as fallback_error:
            utils.log(f"Fallback setInfo also failed: {str(fallback_error)}", "ERROR")
    
    utils.log(f"=== SET_INFO_TAG COMPLETE for '{title}' ===", "INFO")


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    # utils.log("Setting art for ListItem", "DEBUG")
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)
    # utils.log(f"Art types set: {', '.join(art.keys())}", "DEBUG")