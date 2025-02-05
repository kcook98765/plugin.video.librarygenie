
import json
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
        
        # Ensure proper media type string and set it first
        media_type = str(media_info.get('media_type', 'movie')).lower()
        if media_type not in ['movie', 'tvshow', 'season', 'episode']:
            media_type = 'movie'
        info_tag.setMediaType(media_type)

        # Map all available metadata fields
        info_dict = {
            'plot': media_info.get('plot', ''),
            'tagline': media_info.get('tagline', ''),
            'cast': json.loads(media_info.get('cast', '[]')),
            'country': media_info.get('country', ''),
            'director': media_info.get('director', ''),
            'genre': media_info.get('genre', ''),
            'mpaa': media_info.get('mpaa', ''),
            'premiered': media_info.get('premiered', ''),
            'rating': media_info.get('rating', 0.0),
            'studio': media_info.get('studio', ''),
            'trailer': media_info.get('trailer', ''),
            'votes': media_info.get('votes', ''),
            'writer': media_info.get('writer', ''),
            'year': media_info.get('year', '')
        }
        
        # Set artwork
        art_dict = {
            'thumb': media_info.get('thumbnail', ''),
            'poster': media_info.get('thumbnail', ''),
            'fanart': media_info.get('fanart', ''),
            'icon': media_info.get('thumbnail', '')
        }
        utils.log(f"Setting art for ListItem: {art_dict}", "DEBUG")
        set_art(list_item, art_dict)

        # Set all video info
        utils.log(f"Setting video info for ListItem: {info_dict}", "DEBUG")
        set_info(info_tag, info_dict, media_type)
        
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
