
"""Helper class for building ListItems with proper metadata"""
import json
import xbmcgui
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag

class ListItemBuilder:
    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}
        
        utils.log(f"Building video item with media info: {media_info}", "DEBUG")
            
        # Create ListItem with proper string title
        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)
        utils.log(f"Created ListItem with title: {title}", "DEBUG")
        
        # Set artwork
        art_dict = {}
        if 'thumbnail' in media_info.get('info', {}):
            art_dict['thumb'] = media_info['info']['thumbnail']
            art_dict['poster'] = media_info['info']['thumbnail']
            art_dict['icon'] = media_info['info']['thumbnail']
        if 'fanart' in media_info.get('info', {}):
            art_dict['fanart'] = media_info['info']['fanart']
        list_item.setArt(art_dict)

        # Prepare info dictionary from nested info structure
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
        
        utils.log(f"Prepared info dictionary: {info_dict}", "DEBUG")

        # Set video info using the compatibility helper
        set_info_tag(list_item, info_dict, 'video')
        utils.log("Set info tag completed", "DEBUG")
        
        # Set content properties
        list_item.setProperty('IsPlayable', 'true')
        if media_info.get('file'):
            list_item.setPath(media_info['file'])
            
        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem"""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)
        return list_item

    @staticmethod 
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)
