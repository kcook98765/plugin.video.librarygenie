
import xbmcgui
from resources.lib.listitem_infotagvideo import set_info, set_art

class ListItemBuilder:
    @staticmethod
    def build_video_item(media_info):
        list_item = xbmcgui.ListItem()
        info_tag = list_item.getVideoInfoTag()
        
        set_info(info_tag, media_info, media_type='movie')
        set_art(list_item, media_info)
        
        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        return xbmcgui.ListItem(label=name)

    @staticmethod 
    def add_context_menu(list_item, menu_items):
        list_item.addContextMenuItems(menu_items)
