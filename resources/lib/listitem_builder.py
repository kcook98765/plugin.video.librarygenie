
import xbmcgui
from resources.lib.listitem_infotagvideo import set_info, set_art
from resources.lib import utils

class ListItemBuilder:
    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        list_item = xbmcgui.ListItem(label=media_info.get('title', ''))
        info_tag = list_item.getVideoInfoTag()
        
        # Set media info with proper media type
        media_type = media_info.get('type', 'movie')
        set_info(info_tag, media_info, media_type)
        
        # Set artwork if available
        art_dict = {
            'thumb': media_info.get('thumbnail', ''),
            'poster': media_info.get('thumbnail', ''),
            'fanart': media_info.get('fanart', ''),
            'icon': media_info.get('thumbnail', '')
        }
        set_art(list_item, art_dict)
        
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
