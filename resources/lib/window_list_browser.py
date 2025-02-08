
import json
import pyxbmct
import xbmcgui
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib import utils

class ListBrowserWindow(pyxbmct.AddonDialogWindow):
    def __init__(self, item_info, title="Browse Lists"):
        super().__init__(title)
        self.item_info = item_info
        self.setGeometry(800, 600, 12, 8)
        
        # Create UI elements
        self.list_control = pyxbmct.List()
        self.instruction_label = pyxbmct.Label("Click on a list to toggle membership. White = Not in list, Green = In list")
        self.close_button = pyxbmct.Button("Close")
        
        self.setup_ui()
        self.connect_controls()
        self.populate_lists()
        
    def setup_ui(self):
        # Place the instruction label at the top
        self.placeControl(self.instruction_label, 0, 0, 1, 8)
        
        # Place the list control in the middle
        self.placeControl(self.list_control, 1, 0, 10, 8)
        
        # Place the close button at the bottom
        self.placeControl(self.close_button, 11, 3, 1, 2)
        
    def connect_controls(self):
        self.connect(self.list_control, self.on_list_click)
        self.connect(self.close_button, self.close)
        
    def populate_lists(self):
        db_manager = DatabaseManager(Config().db_path)
        all_lists = db_manager.fetch_all_lists_with_item_status(self.item_info.get('kodi_id', 0))
        
        for list_item in all_lists:
            color = 'green' if list_item['is_member'] else 'white'
            label = list_item['name']
            list_label = f"[COLOR {color}]{label}[/COLOR]"
            
            item = xbmcgui.ListItem(list_label)
            item.setProperty('list_id', str(list_item['id']))
            item.setProperty('is_member', str(list_item['is_member']))
            self.list_control.addItem(item)
            
    def on_list_click(self):
        selected_item = self.list_control.getSelectedItem()
        if not selected_item:
            return
            
        list_id = int(selected_item.getProperty('list_id'))
        is_member = selected_item.getProperty('is_member') == '1'
        
        db_manager = DatabaseManager(Config().db_path)
        
        if is_member:
            # Remove from list
            item_id = db_manager.get_item_id_by_title_and_list(list_id, self.item_info['title'])
            if item_id:
                db_manager.delete_data('list_items', f'id={item_id}')
        else:
            # Add to list
            fields_keys = [field.split()[0] for field in Config.FIELDS]
            data = {field: self.item_info.get(field) for field in fields_keys}
            data['list_id'] = list_id
            if 'cast' in data and isinstance(data['cast'], list):
                data['cast'] = json.dumps(data['cast'])
            db_manager.insert_data('list_items', data)
            
        # Refresh the list
        self.list_control.reset()
        self.populate_lists()
