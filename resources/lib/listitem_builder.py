
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
        art_dict = {
            'thumb': media_info.get('thumbnail', ''),
            'poster': media_info.get('thumbnail', ''),
            'fanart': media_info.get('fanart', ''),
            'icon': media_info.get('thumbnail', '')
        }
        list_item.setArt(art_dict)

        # Prepare info dictionary
        info_dict = {
            'title': title,
            'plot': media_info.get('plot', ''),
            'tagline': media_info.get('tagline', ''),
            'cast': json.loads(media_info.get('cast', '[]')),
            'country': media_info.get('country', ''),
            'director': media_info.get('director', ''),
            'genre': media_info.get('genre', ''),
            'mpaa': media_info.get('mpaa', ''),
            'premiered': media_info.get('premiered', ''),
            'rating': float(media_info.get('rating', 0.0)),
            'studio': media_info.get('studio', ''),
            'trailer': media_info.get('trailer', ''),
            'votes': media_info.get('votes', '0'),
            'writer': media_info.get('writer', ''),
            'year': media_info.get('year', ''),
            'mediatype': media_info.get('media_type', 'movie').lower()
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
