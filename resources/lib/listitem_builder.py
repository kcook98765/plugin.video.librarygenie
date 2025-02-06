"""Helper class for building ListItems with proper metadata"""
import json
import xbmcgui
import xbmc
from urllib.parse import quote
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag


def format_art(url):
    """
    Temporarily modified to return URL unchanged for testing
    """
    return url


class ListItemBuilder:
    KODI_VERSION = None

    @staticmethod
    def get_kodi_version():
        if ListItemBuilder.KODI_VERSION is None:
            version_info = xbmc.getInfoLabel("System.BuildVersion")
            ListItemBuilder.KODI_VERSION = int(version_info.split('.')[0])
        return ListItemBuilder.KODI_VERSION

    @staticmethod
    def build_video_item(media_info):
        kodi_version = ListItemBuilder.get_kodi_version()
        """Build a complete video ListItem with all available metadata."""
        # Ensure media_info is a dict
        media_info = media_info if isinstance(media_info, dict) else {}

        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)
        utils.log(f"Building video item for: {title}", "DEBUG")

        # --- Artwork Handling ---
        art = {}
        media_art = media_info.get('art', {})

        # Handle all art types
        art_mapping = {
            'poster': ['poster', 'thumb', 'thumbnail'],
            'thumb': ['thumb', 'poster', 'thumbnail'],
            'banner': ['banner'],
            'icon': ['icon', 'poster', 'thumb']
        }

        for art_type, sources in art_mapping.items():
            for source in sources:
                url = (media_art.get(source) or 
                      media_info.get('art', {}).get(source) or 
                      (media_info.get(source) if source == 'thumbnail' else None))
                art[art_type] = format_art(url) if url else ''
                if url:
                    utils.log(f"Set {art_type} URL: {art[art_type]}", "DEBUG")
                break

        # Ensure thumbnail is properly formatted if different from poster
        thumbnail = media_info.get('thumbnail', '')
        if thumbnail:
            thumbnail = format_art(thumbnail)
            if not art.get('thumb'):
                art['thumb'] = thumbnail
            if not art.get('poster'):
                art['poster'] = thumbnail
            utils.log(f"Set thumbnail URL: {thumbnail}", "DEBUG")

        # For fanart, check both nested info and top-level
        # Handle fanart from multiple possible locations
        fanart_url = (media_info.get('info', {}).get('fanart') or 
                     media_info.get('art', {}).get('fanart') or 
                     media_info.get('fanart'))
        if fanart_url:
            fanart_url = format_art(fanart_url)
            art['fanart'] = fanart_url
            utils.log(f"Set fanart URL: {fanart_url}", "DEBUG")

        list_item.setArt(art)

        # --- Info Tag Setup ---
        info = media_info.get('info', {})
        info_dict = {
            'title': title,
            'plot': info.get('plot', ''),
            'tagline': info.get('tagline', ''),
            'cast': json.loads(info.get('cast', '[]')) if isinstance(info.get('cast'), str) else info.get('cast', []),
            'country': info.get('country', ''),
            'director': info.get('director', ''),
            'genre': info.get('genre', ''),
            'mpaa': info.get('mpaa', ''),
            'premiered': info.get('premiered', ''),
            'rating': float(info.get('rating', 0.0)),
            'studio': info.get('studio', ''),
            'trailer': info.get('trailer', ''),
            'votes': info.get('votes', '0'),
            'writer': info.get('writer', ''),
            'year': info.get('year', ''),
            'mediatype': (info.get('media_type') or 'movie').lower()
        }
        set_info_tag(list_item, info_dict, 'video')
        utils.log("Info tag set.", "DEBUG")

        # Set resume properties if available
        if 'resumetime' in info and 'totaltime' in info:
            list_item.setProperty('ResumeTime', str(info['resumetime']))
            list_item.setProperty('TotalTime', str(info['totaltime']))

        list_item.setProperty('IsPlayable', 'true')

        # --- Cast Processing ---
        cast = info.get('cast')
        if cast:
            try:
                if isinstance(cast, str):
                    cast = json.loads(cast)
                if isinstance(cast, list):
                    actors = []
                    for member in cast:
                        thumb = member.get('thumbnail', '')
                        # Ensure thumbnail is properly formatted
                        if thumb and not thumb.startswith('image://'):
                            thumb = format_art(thumb)
                        utils.log(f"Processing cast member thumbnail: {thumb}", "DEBUG")
                        actor = xbmc.Actor(
                            name=str(member.get('name', '')),
                            role=str(member.get('role', '')),
                            order=int(member.get('order', 0)),
                            thumbnail=thumb
                        )
                        actors.append(actor)
                    list_item.setCast(actors)
                    utils.log(f"Set cast with {len(actors)} members", "DEBUG")
            except Exception as e:
                utils.log(f"Error processing cast: {e}", "ERROR")
                list_item.setCast([])

        # --- Play URL Handling ---
        play_url = media_info.get('info', {}).get('play') or media_info.get('play') or media_info.get('file')
        if play_url:
            list_item.setPath(play_url)
            utils.log(f"Set play URL: {play_url}", "DEBUG")
        else:
            utils.log("No valid play URL found", "WARNING")

        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem."""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)
        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem."""
        list_item.addContextMenuItems(menu_items, replaceItems=True)