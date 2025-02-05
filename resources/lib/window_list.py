""" /resources/lib/window_list.py """
import pyxbmct
import xbmc
from resources.lib import utils
import xbmcgui
import json
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib.window_genie import GenieWindow

# Initialize logging
utils.log("List Window module initialized", "INFO")

from resources.lib.window_base import BaseWindow

class ListWindow(BaseWindow):
    def __init__(self, list_id, title="Media List"):
        super().__init__(title)
        self.setGeometry(800, 600, 10, 10)
        self.list_id = list_id
        self.media_list_control = pyxbmct.List()
        self.setup_ui()
        self.populate_list()
        self.setFocus(self.media_list_control)  # Set focus to media list control after populating it

    def setup_ui(self):
        try:
            self.placeControl(self.media_list_control, 1, 0, rowspan=9, columnspan=10, pad_x=10, pad_y=10)
            self.connect(self.media_list_control, self.on_media_item_click)
            if self.media_list_control and hasattr(self.media_list_control, 'getId'):
                self.media_list_control.setEnabled(True)
            self.set_navigation()
        except Exception as e:
            utils.log(f"Error in setup_ui: {str(e)}", "ERROR")

    def set_navigation(self):
        utils.log("Setting up window navigation controls", "DEBUG")
        # Set navigation controls for the media list
        self.media_list_control.controlUp(self.media_list_control)
        self.media_list_control.controlDown(self.media_list_control)
        self.media_list_control.controlLeft(self.media_list_control)
        self.media_list_control.controlRight(self.media_list_control)
        self.setFocus(self.media_list_control)  # Ensure focus is set to the media list

    def populate_list(self):
        utils.log(f"Populating list for list ID {self.list_id}")
        db_manager = DatabaseManager(Config().db_path)
        media_items = db_manager.fetch_list_items(self.list_id)
        self.media_list_control.reset()

        for item in media_items:
            label = f"{item['title']}"
            media_info = {}
            # Map database columns to media info
            try:
                media_info = {
                    'title': str(item[23]) if item[23] else '',  # title
                    'thumbnail': str(item[22]) if item[22] else '',  # thumbnail
                    'fanart': str(item[6]) if item[6] else '',  # fanart
                    'file': str(item[12]) if item[12] else '',  # path
                    'plot': str(item[14]) if item[14] else '',  # plot
                    'tagline': str(item[21]) if item[21] else '',  # tagline
                    'cast': item[1] if item[1] else '[]',  # cast (JSON string)
                    'country': str(item[2]) if item[2] else '',  # country
                    'director': str(item[4]) if item[4] else '',  # director  
                    'genre': str(item[7]) if item[7] else '',  # genre
                    'mpaa': str(item[11]) if item[11] else '',  # mpaa
                    'premiered': str(item[15]) if item[15] else '',  # premiered
                    'rating': float(item[16]) if item[16] else 0.0,  # rating
                    'studio': str(item[20]) if item[20] else '',  # studio
                    'trailer': str(item[24]) if item[24] else '',  # trailer
                    'votes': str(item[26]) if item[26] else '0',  # votes
                    'writer': str(item[27]) if item[27] else '',  # writer
                    'year': str(item[28]) if item[28] else '',  # year
                    'media_type': 'movie'
                }
                utils.log(f"Built media info: {media_info}", "DEBUG")
            except Exception as e:
                utils.log(f"Error building media info: {str(e)}", "ERROR")
                media_info = {'title': str(item[23]) if item[23] else 'Unknown', 'media_type': 'movie'}
            utils.log(f"Building ListItem with media info: {media_info}", "DEBUG")
            list_item = ListItemBuilder.build_video_item(media_info)
            list_item.setProperty('media_item_id', str(item['id']))
            self.media_list_control.addItem(list_item)
            utils.log(f"Added item with metadata - Title: {item['title']}, Info: {item['info']}", "DEBUG")

        self.add_genie_list_option()

    def add_genie_list_option(self):
        db_manager = DatabaseManager(Config().db_path)
        try:
            genie_list = db_manager.get_genie_list(self.list_id)
            if genie_list:
                label = "<Edit GenieList>"
            else:
                label = "<Add GenieList>"
            genie_list_item = xbmcgui.ListItem(label)
            genie_list_item.setProperty('is_genie_list', 'true')
            self.media_list_control.addItem(genie_list_item)
        finally:
            db_manager.close()

    def on_media_item_click(self):
        selected_item = self.media_list_control.getSelectedItem()
        if not selected_item:
            return

        if selected_item.getProperty('is_genie_list') == 'true':
            self.open_genie_window()
        else:
            title = selected_item.getProperty('title')
            media_item_id = int(selected_item.getProperty('media_item_id'))
            self.prompt_for_removal(title, media_item_id)

    def prompt_for_removal(self, title, media_item_id):
        confirm = xbmcgui.Dialog().yesno("Confirm Removal", f"Do you want to remove '{title}' from the list?")
        if confirm:
            self.remove_media_item(media_item_id)

    def remove_media_item(self, media_item_id):
        utils.log(f"Removing media item ID {media_item_id} from list ID {self.list_id}")
        db_manager = DatabaseManager(Config().db_path)
        db_manager.remove_media_item_from_list(self.list_id, media_item_id)
        xbmcgui.Dialog().notification("Media List", "Media item removed from the list", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def open_genie_window(self):
        genie_window = GenieWindow(self.list_id)
        genie_window.doModal()
        del genie_window

    def onAction(self, action):
        if action == xbmcgui.ACTION_NAV_BACK:
            self.close()
        else:
            super().onAction(action)

    def close(self):
        utils.log("Closing ListWindow")
        pyxbmct.AddonDialogWindow.close(self)
        del self

    def __del__(self):
        utils.log("Deleting ListWindow instance")
        if hasattr(self, 'media_list_control'):
            del self.media_list_control

