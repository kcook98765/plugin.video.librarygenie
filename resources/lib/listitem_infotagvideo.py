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

    try:
        # Get the InfoTag for the specified content type
        if content_type == 'video':
            info_tag = list_item.getVideoInfoTag()
        elif content_type == 'music':
            info_tag = list_item.getMusicInfoTag()
        else:
            utils.log(f"Unsupported content type: {content_type}", "WARNING")
            return

        # Set mediatype only for Kodi 20+ (setMediaType was introduced in v20)
        mediatype = info_dict.get('mediatype')
        if mediatype and kodi_version >= 20 and hasattr(info_tag, 'setMediaType'):
            try:
                info_tag.setMediaType(mediatype)
            except Exception as e:
                utils.log(f"Error setting mediatype: {str(e)}", "DEBUG")

        # Set other properties using InfoTag methods
        for key, value in info_dict.items():
            if key == 'mediatype':
                continue  # Already handled above or not supported in v19
            if not value:  # Skip empty values
                continue

            try:
                # Handle special cases
                if key in ['year'] and isinstance(value, (int, str)):
                    # Year handling - setYear() doesn't exist in Kodi v19
                    # Skip year for InfoTag in v19, let setInfo fallback handle it
                    if kodi_version >= 20 and hasattr(info_tag, 'setYear'):
                        try:
                            year_val = int(value) if value else 0
                            if year_val > 0:
                                info_tag.setYear(year_val)
                        except (ValueError, TypeError):
                            pass
                elif key in ['rating'] and isinstance(value, (int, float, str)):
                    # Rating handling - setRating() doesn't exist in Kodi v19
                    if kodi_version >= 20 and hasattr(info_tag, 'setRating'):
                        try:
                            rating_val = float(value) if value else 0.0
                            info_tag.setRating(rating_val)
                        except (ValueError, TypeError):
                            pass
                elif key in ['votes'] and isinstance(value, (int, str)):
                    # Votes handling - setVotes() doesn't exist in Kodi v19
                    if kodi_version >= 20 and hasattr(info_tag, 'setVotes'):
                        try:
                            votes_val = int(value) if value else 0
                            if votes_val > 0:
                                info_tag.setVotes(votes_val)
                        except (ValueError, TypeError):
                            pass
                elif key == 'cast' and isinstance(value, list):
                    # Cast handling - setCast() doesn't exist in Kodi v19
                    if kodi_version >= 20 and hasattr(info_tag, 'setCast'):
                        try:
                            info_tag.setCast(value)
                        except Exception:
                            pass
                elif hasattr(info_tag, f'set{key.capitalize()}'):
                    # Generic setter (e.g., setTitle, setPlot, etc.)
                    try:
                        setter = getattr(info_tag, f'set{key.capitalize()}')
                        setter(str(value))
                        if key == 'plot':
                            utils.log(f"Successfully set plot via InfoTag.setPlot() - length: {len(str(value))}", "INFO")
                    except Exception as e:
                        if key == 'plot':
                            utils.log(f"Failed to set plot via InfoTag.setPlot(): {str(e)}", "ERROR")
                        pass

            except Exception as e:
                # Log but don't fail - continue with other properties
                utils.log(f"Error setting InfoTag property {key}: {str(e)}", "DEBUG")

    except Exception as e:
        # If InfoTag fails completely, fall back to the old setInfo method
        utils.log(f"Error setting InfoTag, falling back to setInfo: {str(e)}", "ERROR")
        try:
            # Clean up info_dict for setInfo compatibility
            clean_info = {}
            for key, value in info_dict.items():
                if value:
                    # Handle cast specially for setInfo
                    if key == 'cast' and isinstance(value, list):
                        # Convert cast list to simple list of actor names for setInfo
                        try:
                            if all(isinstance(actor, dict) for actor in value):
                                clean_info[key] = [actor.get('name', '') for actor in value if actor.get('name')]
                            else:
                                clean_info[key] = [str(actor) for actor in value]
                        except Exception:
                            pass  # Skip cast if conversion fails
                    else:
                        clean_info[key] = value

            utils.log(f"Using setInfo fallback with {len(clean_info)} properties", "INFO")
            if 'plot' in clean_info:
                plot_preview = str(clean_info['plot'])[:100] + "..." if len(str(clean_info['plot'])) > 100 else str(clean_info['plot'])
                utils.log(f"setInfo fallback plot: '{plot_preview}' (length: {len(str(clean_info['plot']))})", "INFO")
            
            list_item.setInfo(content_type, clean_info)
            utils.log("setInfo fallback completed successfully", "INFO")
        except Exception as fallback_error:
            utils.log(f"Fallback setInfo also failed: {str(fallback_error)}", "ERROR")
    
    utils.log(f"=== SET_INFO_TAG COMPLETE for '{title}' ===", "INFO")


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    # utils.log("Setting art for ListItem", "DEBUG")
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)
    # utils.log(f"Art types set: {', '.join(art.keys())}", "DEBUG")