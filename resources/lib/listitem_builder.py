
import xbmcgui
from resources.lib.listitem_infotagvideo import set_info, set_art
from resources.lib import utils

class ListItemBuilder:
    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        # Ensure media_info is a dict
        if not isinstance(media_info, dict):
            media_info = {}
            
        # Create ListItem with proper string title
        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)
        info_tag = list_item.getVideoInfoTag()
        
        # Ensure proper media type string
        media_type = str(media_info.get('type', 'movie')).lower()
        if media_type not in ['movie', 'tvshow', 'season', 'episode']:
            media_type = 'movie'
        
        # Set artwork if available
        art_dict = {
            'thumb': media_info.get('thumbnail', ''),
            'poster': media_info.get('thumbnail', ''),
            'fanart': media_info.get('fanart', ''),
            'icon': media_info.get('thumbnail', '')
        }
        set_art(list_item, art_dict)

        # Set video info
        set_info(info_tag, media_info, media_type)
        
        # Set content properties
        list_item.setProperty('IsPlayable', 'true')
        if media_info.get('file'):
            list_item.setPath(media_info['file'])
            utils.log(f"Setting path for item: {media_info['file']}", "DEBUG")
            
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
