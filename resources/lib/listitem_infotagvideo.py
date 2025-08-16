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

    NOTE: This function does NOT artificially limit cast size - Kodi can handle full cast lists.
    Any performance issues should be handled by the calling code or user preferences, not hardcoded limits.

    Args:
        list_item: The ListItem to set cast on
        cast_list: List of cast dicts with 'name', 'role', 'thumbnail', 'order' keys

    Returns:
        bool: True if cast was set with image support, False if fallback was used
    """
    if not cast_list:
        return False

    # Normalize inputs (avoid None values) - process ALL cast members, no artificial limits
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

    utils.log(f"Setting cast for {len(norm)} actors with image support", "DEBUG")

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
                    except Exception as actor_error:
                        utils.log(f"Failed to create Actor object for {actor['name']}: {str(actor_error)}", "DEBUG")
                        continue

            if actors:
                info.setCast(actors)  # v21+ preferred InfoTagVideo method
                utils.log(f"v21+ InfoTagVideo.setCast() successful: {len(actors)} actors with images", "DEBUG")
                return True
    except Exception as e:
        utils.log(f"v21+ InfoTagVideo.setCast() failed: {str(e)}", "DEBUG")

    # 2) Fallback for v19/v20: ListItem.setCast(list-of-dicts) - now deprecated in v21
    try:
        if hasattr(list_item, 'setCast'):
            # v19/v20 method: accepts dicts with name/role/thumbnail/order
            list_item.setCast(norm)
            utils.log(f"v19/v20 ListItem.setCast() fallback successful: {len(norm)} actors with images (deprecated)", "DEBUG")
            return True
    except Exception as e:
        utils.log(f"v19/v20 ListItem.setCast() fallback failed: {str(e)}", "DEBUG")

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
            utils.log(f"Fallback setInfo cast successful: {len(simple_cast)} actors (no images)", "WARNING")
            return False
    except Exception as e:
        utils.log(f"All cast methods failed: {str(e)}", "ERROR")

    return False

def set_info_tag(list_item, info_dict, content_type='video'):
    """
    Set InfoTag on a ListItem with Kodi version compatibility

    Args:
        list_item: xbmcgui.ListItem instance
        info_dict: Dictionary of metadata
        content_type: Type of content ('video', 'music', etc.)
    """
    from resources.lib import utils

    try:
        if utils.is_kodi_v20_plus():
            # Use Kodi v20+ InfoTag methods
            if content_type == 'video':
                info_tag = list_item.getVideoInfoTag()
                utils.log(f"V20+ InfoTag object obtained: {type(info_tag)}", "DEBUG")

                # Set basic info using InfoTag methods
                if 'title' in info_dict and info_dict['title']:
                    info_tag.setTitle(str(info_dict['title']))
                if 'plot' in info_dict and info_dict['plot']:
                    info_tag.setPlot(str(info_dict['plot']))
                if 'tagline' in info_dict and info_dict['tagline']:
                    info_tag.setTagLine(str(info_dict['tagline']))
                if 'year' in info_dict and info_dict['year']:
                    info_tag.setYear(int(info_dict['year']))
                if 'rating' in info_dict and info_dict['rating']:
                    info_tag.setRating(float(info_dict['rating']))
                if 'votes' in info_dict and info_dict['votes']:
                    info_tag.setVotes(int(info_dict['votes']))
                if 'duration' in info_dict and info_dict['duration']:
                    info_tag.setDuration(int(info_dict['duration']))
                if 'genre' in info_dict and info_dict['genre']:
                    if isinstance(info_dict['genre'], list):
                        info_tag.setGenres(info_dict['genre'])
                    else:
                        # Split string genres by comma or use as single genre
                        genres = [g.strip() for g in str(info_dict['genre']).split(',') if g.strip()]
                        info_tag.setGenres(genres)
                if 'director' in info_dict and info_dict['director']:
                    if isinstance(info_dict['director'], list):
                        info_tag.setDirectors(info_dict['director'])
                    else:
                        # Split string directors by comma
                        directors = [d.strip() for d in str(info_dict['director']).split(',') if d.strip()]
                        info_tag.setDirectors(directors)
                if 'writer' in info_dict and info_dict['writer']:
                    if isinstance(info_dict['writer'], list):
                        info_tag.setWriters(info_dict['writer'])
                    else:
                        # Split string writers by comma
                        writers = [w.strip() for w in str(info_dict['writer']).split(',') if w.strip()]
                        info_tag.setWriters(writers)
                if 'studio' in info_dict and info_dict['studio']:
                    if isinstance(info_dict['studio'], list):
                        info_tag.setStudios(info_dict['studio'])
                    else:
                        # Split string studios by comma
                        studios = [s.strip() for s in str(info_dict['studio']).split(',') if s.strip()]
                        info_tag.setStudios(studios)
                if 'country' in info_dict and info_dict['country']:
                    if isinstance(info_dict['country'], list):
                        info_tag.setCountries(info_dict['country'])
                    else:
                        # Split string countries by comma
                        countries = [c.strip() for c in str(info_dict['country']).split(',') if c.strip()]
                        info_tag.setCountries(countries)
                if 'premiered' in info_dict and info_dict['premiered']:
                    info_tag.setPremiered(str(info_dict['premiered']))
                if 'trailer' in info_dict and info_dict['trailer']:
                    info_tag.setTrailer(str(info_dict['trailer']))
                if 'mpaa' in info_dict and info_dict['mpaa']:
                    info_tag.setMpaa(str(info_dict['mpaa']))
                if 'mediatype' in info_dict and info_dict['mediatype']:
                    info_tag.setMediaType(str(info_dict['mediatype']))

                # Handle cast with proper format for v20+ - NO artificial size limits
                if 'cast' in info_dict and info_dict['cast']:
                    cast_list = info_dict['cast']
                    if isinstance(cast_list, list) and len(cast_list) > 0:
                        # DO NOT artificially limit cast size - let Kodi handle full cast lists
                        # If performance becomes an issue, it should be handled by user preferences
                        # or calling code, not hardcoded limits in the ListItem builder

                        utils.log(f"Setting cast for {len(cast_list)} actors with image support", "DEBUG")

                        # Try v20+ InfoTag.setCast method first
                        try:
                            formatted_cast = []
                            for actor in cast_list:
                                if isinstance(actor, dict):
                                    cast_member = {}
                                    if 'name' in actor:
                                        cast_member['name'] = str(actor['name'])
                                    if 'role' in actor:
                                        cast_member['role'] = str(actor['role'])
                                    if 'thumbnail' in actor:
                                        cast_member['thumbnail'] = str(actor['thumbnail'])
                                    if cast_member:  # Only add if we have at least a name
                                        formatted_cast.append(cast_member)
                                elif isinstance(actor, str):
                                    formatted_cast.append({'name': actor})

                            if formatted_cast:
                                info_tag.setCast(formatted_cast)
                                utils.log(f"v20+ InfoTag.setCast() successful: {len(formatted_cast)} actors with images", "DEBUG")

                        except Exception as cast_error:
                            utils.log(f"v20+ InfoTag.setCast() failed: {str(cast_error)}, falling back to deprecated method", "DEBUG")
                            # Fall back to deprecated ListItem.setCast for compatibility
                            try:
                                list_item.setCast(cast_list)
                                utils.log(f"v19/v20 ListItem.setCast() fallback successful: {len(cast_list)} actors with images (deprecated)", "DEBUG")
                            except Exception as fallback_error:
                                utils.log(f"Both cast methods failed: {str(fallback_error)}", "WARNING")

        else:
            # Kodi v19 - use deprecated setInfo method
            utils.log("Using deprecated setInfo for v19 compatibility", "DEBUG")

            # Handle cast for v19 (deprecated method) - NO artificial size limits
            if 'cast' in info_dict and info_dict['cast']:
                cast_list = info_dict['cast']
                if isinstance(cast_list, list) and len(cast_list) > 0:
                    # DO NOT artificially limit cast size - Kodi v19 can handle full cast lists
                    # Performance concerns should be addressed by user preferences, not hardcoded limits

                    try:
                        list_item.setCast(cast_list)
                        utils.log(f"v19 ListItem.setCast() successful: {len(cast_list)} actors", "DEBUG")
                    except Exception as cast_error:
                        utils.log(f"v19 cast setting failed: {str(cast_error)}", "WARNING")
                        # Remove cast from info_dict if it causes issues
                        info_dict = {k: v for k, v in info_dict.items() if k != 'cast'}

            # Remove cast from info_dict for setInfo call as it's handled separately
            info_for_setinfo = {k: v for k, v in info_dict.items() if k != 'cast'}
            list_item.setInfo(content_type, info_for_setinfo)

    except Exception as e:
        utils.log(f"Error setting info tag: {str(e)}", "ERROR")
        # Fallback to basic info without problematic fields
        try:
            basic_info = {
                'title': info_dict.get('title', ''),
                'plot': info_dict.get('plot', ''),
                'year': info_dict.get('year', 0),
                'mediatype': info_dict.get('mediatype', 'video')
            }
            if utils.is_kodi_v20_plus():
                info_tag = list_item.getVideoInfoTag()
                if 'title' in basic_info:
                    info_tag.setTitle(str(basic_info['title']))
                if 'plot' in basic_info:
                    info_tag.setPlot(str(basic_info['plot']))
                if 'year' in basic_info and basic_info['year']:
                    info_tag.setYear(int(basic_info['year']))
                if 'mediatype' in basic_info:
                    info_tag.setMediaType(str(basic_info['mediatype']))
            else:
                list_item.setInfo(content_type, basic_info)
            utils.log("Fallback to basic info successful", "DEBUG")
        except Exception as fallback_error:
            utils.log(f"Even basic info setting failed: {str(fallback_error)}", "ERROR")


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)