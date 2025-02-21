import xbmc
import xbmcgui
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib import utils

class UserInteractionManager:
    _instance = None
    _initialized = False

    def __new__(cls, addon_handle):
        if cls._instance is None:
            cls._instance = super(UserInteractionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, addon_handle):
        if not self.__class__._initialized:
            utils.log("User Interaction Manager initialized", "INFO")
            self.addon_handle = addon_handle
            self.db_manager = DatabaseManager(Config().db_path)
            self.__class__._initialized = True

    def context_menu_action(self, action):
        """Handle context menu actions"""
        utils.log(f"Context menu action: {action}", "DEBUG")
        if action == "flag_item":
            item_id = self.get_focused_item_id()
            self.flag_list_item(item_id)

    def text_input(self, prompt):
        dialog = xbmcgui.Dialog()
        return dialog.input(prompt)

    def display_text(self, data):
        dialog = xbmcgui.Dialog()
        dialog.textviewer(xbmc.getLocalizedString(30008), data)

    def save_list_item(self, list_id, item_data):
        """Save an item to a list"""
        utils.log(f"Saving item to list {list_id}", "INFO")
        if not item_data:
            utils.log("No item data provided", "WARNING")
            return False

        try:
            self.db_manager.insert_data('list_items', {
                'list_id': list_id,
                **item_data
            })
            utils.log("Item saved successfully", "INFO")
            return True
        except Exception as e:
            utils.log(f"Error saving item: {str(e)}", "ERROR")
            return False

    def flag_list_item(self, item_id):
        self.db_manager.update_data('list_items', {'flagged': 1}, f'id={item_id}')

    def get_focused_item_id(self):
        return int(xbmc.getInfoLabel('ListItem.DBID'))
