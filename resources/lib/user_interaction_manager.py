""" /resources/lib/user_interaction_manager.py """
import json
import xbmc
import xbmcgui
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config

class UserInteractionManager:

    def __init__(self, addon_handle):
        self.addon_handle = addon_handle
        self.db_manager = DatabaseManager(Config().db_path)

    def context_menu_action(self, action):
        if action == "flag_item":
            item_id = self.get_focused_item_id()
            self.flag_list_item(item_id)

    def text_input(self, prompt):
        dialog = xbmcgui.Dialog()
        return dialog.input(prompt)

    def display_text(self, data):
        dialog = xbmcgui.Dialog()
        dialog.textviewer(xbmc.getLocalizedString(30008), data)

    def save_list_item(self, list_id, item):
        # Extract FIELDS keys without data types
        fields_keys = [field.split()[0] for field in Config.FIELDS]

        # Prepare data dictionary using fields
        data = {field: item.get(field) for field in fields_keys}
        data['list_id'] = list_id

        # Convert the cast list to a JSON string if it exists
        if 'cast' in data and isinstance(data['cast'], list):
            data['cast'] = json.dumps(data['cast'])

        xbmc.log(f"ListGenius: Saving item to database: {data}", xbmc.LOGDEBUG)
        self.db_manager.insert_data('list_items', data)

    def flag_list_item(self, item_id):
        self.db_manager.update_data('list_items', {'flagged': 1}, f'id={item_id}')

    def get_focused_item_id(self):
        return int(xbmc.getInfoLabel('ListItem.DBID'))