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

def set_info_tag(listitem, infolabels, tag_type='video'):
    """
    Universal setter for InfoTag - REQUIRES KODI 19+ (Matrix and above)
    This addon does not support Kodi 18 (Leia) or earlier versions
    """

    kodi_version = get_kodi_version()
    # utils.log(f"Detected Kodi version: {kodi_version}, setting info for: {infolabels.get('title', 'Unknown')}", "DEBUG")

    # Minimum version check - only support Kodi 19+
    if kodi_version < 19:
        utils.log(f"UNSUPPORTED KODI VERSION: {kodi_version}. This addon requires Kodi 19 (Matrix) or higher.", "ERROR")
        # Still attempt to set basic info for graceful degradation
        listitem.setInfo(tag_type, infolabels)
        return

    # For non-video types, fall back to setInfo (but still require Kodi 19+)
    if tag_type != 'video':
        # utils.log("Using setInfo for non-video content type", "DEBUG")
        listitem.setInfo(tag_type, infolabels)
        return

    try:
        # Get video info tag - available in Kodi 18+
        info_tag = listitem.getVideoInfoTag()

        # Set mediatype first - this is crucial for proper display
        mediatype = str(infolabels.get('mediatype', 'movie')).lower()
        if mediatype not in ['movie', 'tvshow', 'season', 'episode', 'musicvideo']:
            mediatype = 'movie'
        info_tag.setMediaType(mediatype)
        # utils.log(f"Set mediatype to: {mediatype}", "DEBUG")

        # Set basic string properties
        if infolabels.get('title'):
            info_tag.setTitle(str(infolabels['title']))
        if infolabels.get('plot'):
            info_tag.setPlot(str(infolabels['plot']))
        if infolabels.get('tagline'):
            info_tag.setTagLine(str(infolabels['tagline']))
        if infolabels.get('mpaa'):
            info_tag.setMpaa(str(infolabels['mpaa']))
        if infolabels.get('premiered'):
            info_tag.setPremiered(str(infolabels['premiered']))

        # Set list-based properties (convert single strings to lists)
        if infolabels.get('genre'):
            genres = [str(infolabels['genre'])] if isinstance(infolabels['genre'], str) else infolabels['genre']
            info_tag.setGenres(genres)
        if infolabels.get('country'):
            countries = [str(infolabels['country'])] if isinstance(infolabels['country'], str) else infolabels['country']
            info_tag.setCountries(countries)
        if infolabels.get('director'):
            directors = [str(infolabels['director'])] if isinstance(infolabels['director'], str) else infolabels['director']
            info_tag.setDirectors(directors)
        if infolabels.get('studio'):
            studios = [str(infolabels['studio'])] if isinstance(infolabels['studio'], str) else infolabels['studio']
            info_tag.setStudios(studios)
        if infolabels.get('writer'):
            writers = [str(infolabels['writer'])] if isinstance(infolabels['writer'], str) else infolabels['writer']
            info_tag.setWriters(writers)

        # Set numeric properties with error handling
        if infolabels.get('year'):
            try:
                year = int(infolabels['year'])
                if 1800 <= year <= 2100:  # Sanity check
                    info_tag.setYear(year)
            except (ValueError, TypeError):
                utils.log(f"Invalid year value: {infolabels.get('year')}", "WARNING")

        if infolabels.get('rating'):
            try:
                rating = float(infolabels['rating'])
                if 0 <= rating <= 10:  # Sanity check
                    info_tag.setRating(rating)
            except (ValueError, TypeError):
                utils.log(f"Invalid rating value: {infolabels.get('rating')}", "WARNING")

        if infolabels.get('votes'):
            try:
                votes = int(infolabels['votes'])
                if votes >= 0:  # Sanity check
                    info_tag.setVotes(votes)
            except (ValueError, TypeError):
                utils.log(f"Invalid votes value: {infolabels.get('votes')}", "WARNING")

        if infolabels.get('duration'):
            try:
                duration = int(infolabels['duration'])
                if duration > 0:
                    info_tag.setDuration(duration)
            except (ValueError, TypeError):
                utils.log(f"Invalid duration value: {infolabels.get('duration')}", "WARNING")

        # Handle cast - Kodi 19+ only (no legacy support for older versions)
        if infolabels.get('cast'):
            cast = infolabels['cast']
            if isinstance(cast, str):
                try:
                    cast = json.loads(cast)
                except json.JSONDecodeError:
                    utils.log("Failed to parse cast JSON", "WARNING")
                    cast = []

            if cast and isinstance(cast, list):
                if kodi_version >= 20:
                    # For Kodi 20+, try to use Actor class if available
                    try:
                        from xbmc import Actor
                        actors = []
                        for item in cast:
                            if isinstance(item, dict):
                                actor = Actor(
                                    name=str(item.get('name', '')),
                                    role=str(item.get('role', '')),
                                    order=int(item.get('order', 0)),
                                    thumbnail=str(item.get('thumbnail', ''))
                                )
                                actors.append(actor)
                        if actors:
                            info_tag.setCast(actors)
                            # utils.log(f"Set cast with {len(actors)} actors using Actor class", "DEBUG")
                    except (ImportError, Exception) as e:
                        utils.log(f"Failed to use Actor class, falling back to dictionary format: {str(e)}", "WARNING")
                        # Fall back to dictionary format for Kodi 19+
                        legacy_cast = []
                        for item in cast:
                            if isinstance(item, dict):
                                legacy_cast.append({
                                    'name': str(item.get('name', '')),
                                    'role': str(item.get('role', '')),
                                    'order': int(item.get('order', 0)),
                                    'thumbnail': str(item.get('thumbnail', ''))
                                })
                        if legacy_cast:
                            info_tag.setCast(legacy_cast)
                            # utils.log(f"Set cast with {len(legacy_cast)} actors using dictionary format", "DEBUG")
                else:
                    # For Kodi 19, use dictionary format (minimum supported version)
                    legacy_cast = []
                    for item in cast:
                        if isinstance(item, dict):
                            legacy_cast.append({
                                'name': str(item.get('name', '')),
                                'role': str(item.get('role', '')),
                                'order': int(item.get('order', 0)),
                                'thumbnail': str(item.get('thumbnail', ''))
                            })
                    if legacy_cast:
                        info_tag.setCast(legacy_cast)
                        # utils.log(f"Set cast with {len(legacy_cast)} actors using dictionary format for Kodi 19", "DEBUG")

        # utils.log(f"Successfully set InfoTag for: {infolabels.get('title', 'Unknown')}", "DEBUG")

    except Exception as e:
        utils.log(f"Error setting InfoTag, falling back to setInfo: {str(e)}", "ERROR")
        # Fallback to setInfo (still requires Kodi 19+ for this addon)
        listitem.setInfo(tag_type, infolabels)


def set_art(listitem: ListItem, art: Dict[str, str]) -> None:
    """
    Set artwork for a ListItem.
    """
    if not art:
        return

    try:
        listitem.setArt(art)
    except Exception as e:
        utils.log(f"Error setting artwork batch: {str(e)}", "ERROR")
        # Fallback: set individual art types
        for art_type, art_url in art.items():
            try:
                listitem.setArt({art_type: art_url})
            except Exception as inner_e:
                utils.log(f"Failed to set {art_type} artwork: {str(inner_e)}", "ERROR")