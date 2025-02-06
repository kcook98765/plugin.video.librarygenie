"""
Classes and functions that process data from JSON-RPC API and assign them to ListItem instances
"""

from typing import Dict, Any, List, Tuple, Type, Iterable, Union
from urllib.parse import quote
import json

import xbmc
from xbmc import InfoTagVideo, Actor
from xbmcgui import ListItem
from resources.lib import utils

__all__ = ['set_info_tag', 'set_art']

# Initialize logging
utils.log("ListItem InfoTagVideo module initialized", "INFO")

StreamDetailsType = Union[xbmc.VideoStreamDetail, xbmc.AudioStreamDetail, xbmc.SubtitleStreamDetail]

def get_kodi_version() -> int:
    """
    Get the major version number of the current Kodi installation.
    """
    version_info = xbmc.getInfoLabel("System.BuildVersion")
    return int(version_info.split('.')[0])


"""InfoTag compatibility helper for Kodi 19+"""

def set_info_tag(listitem, infolabels, tag_type='video'):
    """Universal setter for InfoTag that works across Kodi versions"""
    utils.log(f"Setting info tag for type {tag_type}", "DEBUG")

    kodi_version = get_kodi_version()
    utils.log(f"Detected Kodi version: {kodi_version}", "DEBUG")

    if tag_type != 'video' or kodi_version < 19:
        listitem.setInfo(tag_type, infolabels)
        return

    # Get video tag for Kodi 19+
    info_tag = listitem.getVideoInfoTag()

    # Set mediatype first
    mediatype = str(infolabels.get('mediatype', 'movie')).lower()
    if mediatype not in ['movie', 'tvshow', 'season', 'episode']:
        mediatype = 'movie'
    info_tag.setMediaType(mediatype)

    # Map values to their setter methods
    if infolabels.get('title'): 
        info_tag.setTitle(str(infolabels['title']))
    if infolabels.get('plot'):
        info_tag.setPlot(str(infolabels['plot']))
    if infolabels.get('tagline'):
        info_tag.setTagLine(str(infolabels['tagline']))
    if infolabels.get('genre'):
        info_tag.setGenres([str(infolabels['genre'])])
    if infolabels.get('country'):
        info_tag.setCountries([str(infolabels['country'])])
    if infolabels.get('director'):
        info_tag.setDirectors([str(infolabels['director'])])
    if infolabels.get('mpaa'):
        info_tag.setMpaa(str(infolabels['mpaa']))
    if infolabels.get('premiered'):
        info_tag.setPremiered(str(infolabels['premiered']))
    if infolabels.get('year'):
        try:
            info_tag.setYear(int(infolabels['year']))
        except (ValueError, TypeError):
            pass
    if infolabels.get('rating'):
        try:
            info_tag.setRating(float(infolabels['rating']))
        except (ValueError, TypeError):
            pass
    if infolabels.get('votes'):
        try:
            info_tag.setVotes(int(infolabels['votes']))
        except (ValueError, TypeError):
            pass
    if infolabels.get('studio'):
        info_tag.setStudios([str(infolabels['studio'])])
    if infolabels.get('writer'):
        info_tag.setWriters([str(infolabels['writer'])])
    if infolabels.get('cast'):
        cast = infolabels['cast']
        if isinstance(cast, str):
            try:
                cast = json.loads(cast)
            except:
                cast = []
        actors = []
        idx = 0
        for member in cast:
            idx +=1
            thumb = member.get('thumbnail', '')
            # Ensure thumbnail is properly formatted
            if thumb and not thumb.startswith('image://'):
                thumb = format_art(thumb)
            if idx < 3:  # Only log first 3 cast members
                utils.log(f"Processing cast member thumbnail: {thumb}", "DEBUG")
            actor = xbmc.Actor(
                name=str(member.get('name', '')),
                role=str(member.get('role', '')),
                order=int(member.get('order', 0)),
                thumbnail=str(thumb)
            )
            actors.append(actor)
        info_tag.setCast(actors)


def set_art(list_item: ListItem, raw_art: Dict[str, str]) -> None:
    utils.log("Setting art for ListItem", "DEBUG")
    art = {art_type: raw_url for art_type, raw_url in raw_art.items()}
    list_item.setArt(art)
    utils.log(f"Art types set: {', '.join(art.keys())}", "DEBUG")