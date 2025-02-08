import re
import json
import pyxbmct
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib.window_list import ListWindow
from resources.lib import utils

# Initialize window logging
utils.log("Initializing MainWindow module", "INFO")

from resources.lib.window_base import BaseWindow

class MainWindow(BaseWindow):
    INDENTATION_MULTIPLIER = 3  # Set the indentation multiplier

    def __init__(self, item_info, title="Item Info"):
        super().__init__(title)
        self.setGeometry(800, 600, 10, 10)
        self.item_info = item_info
        self.list_data = []
        self.selected_item_id = None
        self.selected_is_folder = None  # Track if the selected item is a folder

        self.is_playable = self.check_playable()
        self.folder_expanded_states = {}
        self.moving_list_id = None
        self.moving_list_name = None
        self.moving_folder_id = None
        self.moving_folder_name = None

        self.media_label = pyxbmct.Label("")
        self.list_control = pyxbmct.List()

        self.setup_ui()
        self.populate_list()
        self.set_navigation()

    def setup_ui(self):
        self.placeControl(self.media_label, 0, 0, columnspan=10, pad_x=10, pad_y=10)
        self.placeControl(self.list_control, 1, 0, rowspan=9, columnspan=10, pad_x=10, pad_y=10)
        self.connect(self.list_control, self.on_list_item_click)
        self.display_media_info()

    def check_playable(self):
        is_playable = self.item_info.get('is_playable', False)
        if not is_playable:
            try:
                item_id = int(self.item_info.get('kodi_id', 0))
                if item_id > 0:
                    is_playable = True
            except (ValueError, TypeError):
                is_playable = False
        return is_playable

    def display_media_info(self):
        if self.is_playable:
            title = self.item_info.get('title', 'Unknown')
            art = self.item_info.get('art', {})
            thumbnail = art.get('thumb') or art.get('poster') or art.get('banner') or art.get('fanart')
            if thumbnail:
                image_control = pyxbmct.Image(thumbnail)
                image_control.setHeight(int(image_control.getHeight() * 0.25))
                image_control.setWidth(int(image_control.getWidth() * 0.25))
                self.placeControl(image_control, 0, 0, rowspan=1, columnspan=1, pad_x=10, pad_y=10)
            self.media_label.setLabel(f"Media: {title}")

    def onAction(self, action):
        if action == xbmcgui.ACTION_MOVE_RIGHT:
            self.expand_selected_folder()
        elif action == xbmcgui.ACTION_MOVE_LEFT:
            self.collapse_selected_folder()
        else:
            super().onAction(action)

    def expand_selected_folder(self):
        selected_item = self.list_control.getSelectedItem()
        if selected_item and selected_item.getProperty('isFolder') == 'true':
            folder_id = int(selected_item.getProperty('folder_id'))
            self.selected_item_id = folder_id  # Set the selected item ID
            self.selected_is_folder = True  # Indicate that the selected item is a folder
            utils.log(f"Expanding folder with ID {folder_id}", "DEBUG")
            if not self.folder_expanded_states.get(folder_id, False):
                self.update_folder_expanded_states(folder_id, True)
                self.populate_list(folder_id)  # Pass folder_id to reselect it

    def collapse_selected_folder(self):
        selected_item = self.list_control.getSelectedItem()
        if selected_item and selected_item.getProperty('isFolder') == 'true':
            folder_id = int(selected_item.getProperty('folder_id'))
            self.selected_item_id = folder_id  # Set the selected item ID
            self.selected_is_folder = True  # Indicate that the selected item is a folder
            utils.log(f"Collapsing folder with ID {folder_id}", "DEBUG")
            if self.folder_expanded_states.get(folder_id, False):
                self.update_folder_expanded_states(folder_id, False)
                self.populate_list(folder_id)  # Pass folder_id to reselect it

    def update_folder_expanded_states(self, current_folder_id, expand):
        utils.log(f"Updating folder expanded states for folder ID {current_folder_id}, expand={expand}", "DEBUG")
        for folder_id in self.folder_expanded_states.keys():
            if folder_id != current_folder_id:
                self.folder_expanded_states[folder_id] = False
        self.folder_expanded_states[current_folder_id] = expand
        parent_id = self.get_parent_folder_id(current_folder_id)
        while parent_id:
            self.folder_expanded_states[parent_id] = True
            parent_id = self.get_parent_folder_id(parent_id)

    def populate_list(self, focus_folder_id=None):
        utils.log("Populating list...", "DEBUG")
        db_manager = DatabaseManager(Config().db_path)
        self.list_control.reset()

        all_folders = db_manager.fetch_all_folders()
        all_lists = db_manager.fetch_all_lists_with_item_status(self.item_info.get('kodi_id', 0))

        folder_color_status = {}
        if self.is_playable:
            folder_status = db_manager.fetch_folders_with_item_status(self.item_info.get('kodi_id', 0))

            # Track folder statuses
            for folder in folder_status:
                folder_color_status[folder['id']] = 'green' if folder['is_member'] else 'red'

            # Propagate status upwards through the hierarchy
            def propagate_status(folder_id, color):
                while folder_id is not None:
                    current_color = folder_color_status.get(folder_id, 'red')
                    if color == 'green' and current_color == 'red':
                        folder_color_status[folder_id] = 'green'
                    folder_id = next((f['parent_id'] for f in all_folders if f['id'] == folder_id), None)

            for folder in folder_status:
                if folder['is_member']:
                    propagate_status(folder['parent_id'], 'green')

            utils.log(f"Folder color statuses: {folder_color_status}", "DEBUG")

        self.list_data = []

        root_folders = [folder for folder in all_folders if folder['parent_id'] is None]
        root_lists = [list_item for list_item in all_lists if list_item['folder_id'] is None]
        combined_root = root_folders + root_lists
        combined_root.sort(key=lambda x: self.clean_name(x['name']).lower())
        utils.log(f"Sorted combined root items: {[(self.clean_name(i['name']), i['name']) for i in combined_root]}", "DEBUG")

        any_root_folder_expanded = False
        for item in combined_root:
            if 'parent_id' in item:
                folder_media_count = db_manager.get_folder_media_count(item['id'])
                utils.log(f"Adding root folder item - ID: {item['id']}, Name: {item['name']} ({folder_media_count})", "DEBUG")
                self.add_folder_items(item, 0, all_folders, all_lists, folder_color_status)
                any_root_folder_expanded = any_root_folder_expanded or self.folder_expanded_states.get(item['id'], False)
            else:
                list_media_count = db_manager.get_list_media_count(item['id'])
                list_label = f"  {item['name']} ({list_media_count})"
                color = 'green' if item['is_member'] else 'red'
                if self.is_playable:
                    list_label = f"[COLOR {color}]{list_label}[/COLOR]"
                list_item = xbmcgui.ListItem(list_label)
                list_item.setProperty('isFolder', 'false')
                list_item.setProperty('list_id', str(item['id']))
                list_item.setProperty('is_member', str(item['is_member']))  # Correctly set is_member property
                self.list_control.addItem(list_item)
                self.list_data.append({'name': item['name'], 'isFolder': False, 'id': item['id'], 'indent': 0, 'color': color if self.is_playable else None})

        if not any_root_folder_expanded:
            self.add_new_items({'id': None}, 0)

        self.list_control.setEnabled(True)
        self.reselect_previous_item(focus_folder_id)

    def clean_name(self, name):
        name = re.sub(r'\[COLOR.*?\](.*?)\[\/COLOR\]', r'\1', name)
        name = re.sub(r'\[B\](.*?)\[\/B\]', r'\1', name)
        name = name.lstrip('+ -').strip()
        return name

    def add_folder_items(self, folder, indent, all_folders, all_lists, folder_color_status):
        expanded = self.folder_expanded_states.get(folder['id'], False)
        color = folder_color_status.get(folder['id'], 'red') if self.is_playable else None
        prefix = "<" if expanded else ">"
        utils.log(f"Adding folder - Name: {folder['name']}, Expanded: {expanded}, Indent: {indent}, Color: {color}", "DEBUG")

        db_manager = DatabaseManager(Config().db_path)
        folder_media_count = db_manager.get_folder_media_count(folder['id'])

        folder_label = f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}{prefix}{' ' * (indent * self.INDENTATION_MULTIPLIER)}[B][COLOR {color}]{folder['name']} ({folder_media_count})[/COLOR][/B]" if color else f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}{prefix}{' ' * (indent * self.INDENTATION_MULTIPLIER)}{folder['name']} ({folder_media_count})"

        folder_item = xbmcgui.ListItem(folder_label)
        folder_item.setProperty('isFolder', 'true')
        folder_item.setProperty('folder_id', str(folder['id']))
        folder_item.setProperty('expanded', str(expanded))
        self.list_control.addItem(folder_item)
        self.list_data.append({'name': folder['name'], 'isFolder': True, 'id': folder['id'], 'indent': indent, 'expanded': expanded, 'color': color})

        if expanded:
            subfolders = [f for f in all_folders if f['parent_id'] == folder['id']]
            lists = [l for l in all_lists if l['folder_id'] == folder['id']]
            combined = subfolders + lists
            combined.sort(key=lambda x: self.clean_name(x['name']).lower())
            utils.log(f"Sorted combined items for {folder['name']}: {[(self.clean_name(i['name']), i['name']) for i in combined]}", "DEBUG")

            any_subfolder_expanded = False
            for item in combined:
                if 'parent_id' in item:
                    subfolder_expanded = self.folder_expanded_states.get(item['id'], False)
                    self.add_folder_items(item, indent + 1, all_folders, all_lists, folder_color_status)
                    any_subfolder_expanded = any_subfolder_expanded or subfolder_expanded
                else:
                    list_media_count = db_manager.get_list_media_count(item['id'])
                    list_label = f"{' ' * ((indent + 1) * self.INDENTATION_MULTIPLIER)} {item['name']} ({list_media_count})"
                    color = 'green' if item['is_member'] else 'red'
                    if self.is_playable:
                        list_label = f"[COLOR {color}]{list_label}[/COLOR]"
                    list_item = xbmcgui.ListItem(list_label)
                    list_item.setProperty('isFolder', 'false')
                    list_item.setProperty('list_id', str(item['id']))
                    list_item.setProperty('is_member', str(item['is_member']))  # Correctly set is_member property
                    self.list_control.addItem(list_item)
                    self.list_data.append({'name': item['name'], 'isFolder': False, 'id': item['id'], 'indent': indent + 1, 'color': color if self.is_playable else None})

            if not any_subfolder_expanded:
                self.add_new_items(folder, indent + 1)

    def add_new_items(self, parent_folder, indent):
        new_folder_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<New Folder>")
        new_folder_item.setProperty('isFolder', 'true')
        new_folder_item.setProperty('isSpecial', 'true')  # Add a flag for special items
        new_folder_item.setProperty('action', 'new_folder')
        new_folder_item.setProperty('parent_id', str(parent_folder['id']))
        self.list_control.addItem(new_folder_item)
        self.list_data.append({'name': '<New Folder>', 'isFolder': True, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': 'new_folder'})

        new_list_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<New List>")
        new_list_item.setProperty('isFolder', 'false')
        new_list_item.setProperty('isSpecial', 'true')  # Add a flag for special items
        new_list_item.setProperty('action', 'new_list')
        new_list_item.setProperty('parent_id', str(parent_folder['id']))
        self.list_control.addItem(new_list_item)
        self.list_data.append({'name': '<New List>', 'isFolder': False, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': 'new_list'})

        if self.moving_list_id:
            paste_list_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<Paste List Here : {self.moving_list_name}>")
            paste_list_item.setProperty('isFolder', 'false')
            paste_list_item.setProperty('isSpecial', 'true')  # Add a flag for special items
            paste_list_item.setProperty('action', f"paste_list_here:{self.moving_list_id}")
            paste_list_item.setProperty('parent_id', str(parent_folder['id']))
            self.list_control.addItem(paste_list_item)
            self.list_data.append({'name': f'<Paste List Here : {self.moving_list_name}>', 'isFolder': False, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': f"paste_list_here:{self.moving_list_id}"})

        if self.moving_folder_id:
            paste_folder_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<Paste Folder Here : {self.moving_folder_name}>")
            paste_folder_item.setProperty('isFolder', 'true')
            paste_folder_item.setProperty('isSpecial', 'true')  # Add a flag for special items
            paste_folder_item.setProperty('action', f"paste_folder_here:{self.moving_folder_id}")
            paste_folder_item.setProperty('parent_id', str(parent_folder['id']))
            self.list_control.addItem(paste_folder_item)
            self.list_data.append({'name': f'<Paste Folder Here : {self.moving_folder_name}>', 'isFolder': True, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': f"paste_folder_here:{self.moving_folder_id}"})

    def reselect_previous_item(self, focus_folder_id=None):
        utils.log(f"Reselecting previous item. focus_folder_id={focus_folder_id}, selected_item_id={self.selected_item_id}, selected_is_folder={self.selected_is_folder}", "DEBUG")
        focus_id = self.selected_item_id if self.selected_item_id is not None else focus_folder_id
        focus_is_folder = self.selected_is_folder if self.selected_is_folder is not None else True

        if focus_id is not None:
            db_manager = DatabaseManager(Config().db_path)
            item_exists = False

            if focus_is_folder:
                item_exists = db_manager.fetch_folder_by_id(focus_id) is not None
            else:
                item_exists = db_manager.fetch_list_by_id(focus_id) is not None

            if not item_exists:
                utils.log(f"Item with ID {focus_id} no longer exists", "DEBUG")
                self.list_control.selectItem(0)
                self.setFocus(self.list_control)
                return

            for index in range(self.list_control.size()):
                list_item = self.list_control.getListItem(index)
                is_folder = list_item.getProperty('isFolder') == 'true'
                try:
                    list_item_id = int(list_item.getProperty('folder_id' if is_folder else 'list_id'))
                except (ValueError, TypeError):
                    continue

                utils.log(f"Checking list item. Index={index}, ID={list_item_id}, IsFolder={is_folder}, Label={list_item.getLabel()}", "DEBUG")
                if list_item_id == focus_id and is_folder == focus_is_folder:
                    self.list_control.selectItem(index)
                    self.setFocus(self.list_control)
                    utils.log(f"Item reselected. Index={index}, ID={list_item_id}, Label={list_item.getLabel()}", "DEBUG")
                    break
            else:
                utils.log(f"Could not find item to reselect with ID {focus_id} and IsFolder={focus_is_folder}", "DEBUG")
                self.list_control.selectItem(0)
                self.setFocus(self.list_control)

    def on_list_item_click(self):
        selected_item = self.list_control.getSelectedItem()
        if not selected_item:
            return

        selected_item_label = self.strip_color_tags(selected_item.getLabel())
        is_folder = selected_item.getProperty('isFolder') == 'true'
        action = selected_item.getProperty('action')
        parent_id = selected_item.getProperty('parent_id')

        # Check if the selected item is a special action item
        if action:
            self.handle_action(action, parent_id)
        else:
            try:
                selected_item_id = int(selected_item.getProperty('folder_id') if is_folder else selected_item.getProperty('list_id'))
            except ValueError:
                selected_item_id = None

            self.selected_item_id = selected_item_id
            self.selected_is_folder = is_folder  # Track if the selected item is a folder
            utils.log(f"Item clicked. Label={selected_item_label}, ID={selected_item_id}, IsFolder={is_folder}", "DEBUG")

            if selected_item_id is not None:
                self.display_item_options(selected_item_label, selected_item_id, is_folder)

    def handle_action(self, action, parent_id):
        utils.log(f"Handling action. Action={action}, ParentID={parent_id}", "DEBUG")
        if action == 'new_folder':
            self.create_new_folder(parent_id)
        elif action == 'new_list':
            self.create_new_list(parent_id)
        elif action.startswith('paste_'):
            self.handle_paste_action(action, parent_id)

    def display_item_options(self, label, item_id, is_folder):
        if is_folder:
            self.show_folder_options({'id': item_id, 'name': label})
        else:
            color = 'green' if self.list_control.getSelectedItem().getProperty('is_member') == '1' else 'red'
            self.show_list_options({'id': item_id, 'name': label, 'color': color})

    def show_folder_options(self, folder_data):
        options = ["Rename Folder", "Move Folder", "Delete Folder", "Settings"]
        selected_option = xbmcgui.Dialog().select("Choose an action", options)
        utils.log(f"Folder options selected. FolderID={folder_data['id']}, Option={options[selected_option] if selected_option != -1 else 'None'}", "DEBUG")
        if selected_option == -1:
            return

        if options[selected_option] == "Rename Folder":
            self.rename_folder(folder_data['id'], folder_data['name'])
        elif options[selected_option] == "Move Folder":
            self.move_folder(folder_data['id'], folder_data['name'])
        elif options[selected_option] == "Delete Folder":
            self.delete_folder(folder_data['id'], folder_data['name'])
        elif options[selected_option] == "Settings":
            self.open_settings()

    def show_list_options(self, list_data):
        # Create a new window to display lists hierarchically
        list_browser = ListBrowserWindow(self.item_info)
        list_browser.doModal()
        del list_browser
        # Refresh the main window's list after potential changes
        self.populate_list()

        options.extend([
            "Rename This List",
            "Move This List",
            "Edit This List",
            "Delete This List",
            "Export IMDB List",
            "Upload IMDB List",
            "Settings"
        ])

        selected_option = xbmcgui.Dialog().select("Choose an action", options)
        utils.log(f"List options selected. ListID={list_data['id']}, Option={options[selected_option] if selected_option != -1 else 'None'}", "DEBUG")
        if selected_option == -1:
            return

        if options[selected_option] == "Add Media to List":
            self.add_media_to_list(list_data['id'])
        elif options[selected_option] == "Remove Media from List":
            self.remove_media_from_list(list_data['id'])
        elif options[selected_option] == "Rename This List":
            self.rename_list(list_data['id'], list_data['name'])
        elif options[selected_option] == "Move This List":
            self.move_list(list_data['id'], list_data['name'])
        elif options[selected_option] == "Edit This List":
            self.edit_list(list_data['id'])
        elif options[selected_option] == "Delete This List":
            self.delete_list(list_data['id'], list_data['name'])
        elif options[selected_option] == "Export IMDB List":
            self.export_imdb_list(list_data['id'])
        elif options[selected_option] == "Upload IMDB List":
            self.upload_imdb_list()
        elif options[selected_option] == "Settings":
            self.open_settings()

    def upload_imdb_list(self):
        """Upload IMDB numbers to configured API endpoint"""
        import requests

        upload_url = xbmcaddon.Addon().getSetting('imdb_upload_url')
        api_key = xbmcaddon.Addon().getSetting('imdb_upload_key')

        if not upload_url or not api_key:
            xbmcgui.Dialog().ok("Error", "Please configure IMDB Upload API URL and Key in settings")
            return

        db = DatabaseManager(Config().db_path)
        imdb_numbers = db.get_valid_imdb_numbers()

        if not imdb_numbers:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "No valid IMDB numbers found to upload",
                xbmcgui.NOTIFICATION_INFO,
                5000
            )
            return

        progress = xbmcgui.DialogProgress()
        progress.create("Uploading IMDB List")

        try:
            response = requests.post(
                upload_url,
                json={'imdb_numbers': imdb_numbers},
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=30
            )
            response.raise_for_status()

            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Successfully uploaded {len(imdb_numbers)} IMDB numbers",
                xbmcgui.NOTIFICATION_INFO,
                5000
            )

        except Exception as e:
            utils.log(f"Error uploading IMDB list: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Failed to upload IMDB list: {str(e)}")
        finally:
            progress.close()

    def export_imdb_list(self, list_id):
        """Export list items to IMDB format"""
        from resources.lib.database_sync_manager import DatabaseSyncManager
        from resources.lib.query_manager import QueryManager
        
        query_manager = QueryManager(Config().db_path)
        sync_manager = DatabaseSyncManager(query_manager)

        # Ensure tables exist
        sync_manager.setup_tables()
        
        # Sync library movies
        sync_manager.sync_library_movies()

    def handle_paste_action(self, action, target_id):
        utils.log(f"Handling paste action. Action={action}, TargetID={target_id}", "DEBUG")
        if "paste_list_here" in action:
            list_id = int(action.split(':')[1])
            self.paste_list_here(list_id, target_id)
        elif "paste_folder_here" in action:
            folder_id = int(action.split(':')[1])
            self.paste_folder_here(folder_id, target_id)

    def rename_list(self, list_id, current_name):
        clean_name = re.sub(r'\[.*?\]', '', current_name)
        new_name = xbmcgui.Dialog().input("Enter new name for the list", defaultt=clean_name).strip()
        utils.log(f"Renaming list. ListID={list_id}, CurrentName={current_name}, NewName={new_name}", "DEBUG")
        if not new_name:
            xbmcgui.Dialog().notification("LibraryGenie", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        db_manager = DatabaseManager(Config().db_path)
        existing_list_id = db_manager.get_list_id_by_name(new_name)
        if existing_list_id and existing_list_id != list_id:
            xbmcgui.Dialog().notification("LibraryGenie", f"The list name '{new_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        db_manager.update_data('lists', {'name': new_name}, f'id={list_id}')
        xbmcgui.Dialog().notification("LibraryGenie", f"List renamed to '{new_name}'", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def create_new_folder(self, parent_id):
        try:
            new_folder_name = xbmcgui.Dialog().input("Enter new folder name").strip()
            utils.log(f"Creating new folder. ParentID={parent_id}, NewFolderName={new_folder_name}", "DEBUG")
            if not new_folder_name:
                xbmcgui.Dialog().notification("LibraryGenie", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
                return

            db_manager = DatabaseManager(Config().db_path)
            existing_folder_id = db_manager.get_folder_id_by_name(new_folder_name)
        except Exception:
            utils.log(f"Error creating new folder. ParentID={parent_id}, NewFolderName not set", "ERROR")
            return
        if existing_folder_id:
            xbmcgui.Dialog().notification("LibraryGenie", f"The folder name '{new_folder_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        parent_id = int(parent_id) if parent_id != 'None' else None
        utils.log(f"Creating new folder '{new_folder_name}' under parent ID '{parent_id}'", "DEBUG")
        db_manager.insert_folder(new_folder_name, parent_id)
        xbmcgui.Dialog().notification("LibraryGenie", f"New folder '{new_folder_name}' created", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def rename_folder(self, folder_id, current_name):
        clean_name = re.sub(r'^[\s>]+', '', current_name)
        clean_name = re.sub(r'\[.*?\]', '', clean_name)

        new_name = xbmcgui.Dialog().input("Enter new name for the folder", defaultt=clean_name).strip()
        utils.log(f"Renaming folder. FolderID={folder_id}, CurrentName={current_name}, NewName={new_name}", "DEBUG")
        if not new_name:
            xbmcgui.Dialog().notification("LibraryGenie", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        db_manager = DatabaseManager(Config().db_path)
        existing_folder_id = db_manager.get_folder_id_by_name(new_name)
        if existing_folder_id and existing_folder_id != folder_id:
            xbmcgui.Dialog().notification("LibraryGenie", f"The folder name '{new_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        db_manager.update_folder_name(folder_id, new_name)
        xbmcgui.Dialog().notification("LibraryGenie", f"Folder renamed to '{new_name}'", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def move_folder(self, folder_id, folder_name):
        self.moving_folder_id = folder_id
        self.moving_folder_name = folder_name
        xbmcgui.Dialog().notification("LibraryGenie", f"Select new location for folder: {folder_name}", xbmcgui.NOTIFICATION_INFO, 5000)
        utils.log(f"Moving folder. FolderID={folder_id}, FolderName={folder_name}", "DEBUG")
        self.populate_list()

    def paste_folder_here(self, folder_id, target_folder_id):
        db_manager = DatabaseManager(Config().db_path)

        # Check for circular reference        current_parent = target_folder_id
        while current_parent is not None:
            if current_parent == folder_id:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Cannot move folder: Would create circular reference",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
                return
            folder = db_manager.fetch_folder_by_id(current_parent)
            current_parent = folder['parent_id'] if folder else None

        db_manager.update_folder_parent(folder_id, target_folder_id)
        xbmcgui.Dialog().notification("LibraryGenie", f"Folder moved to new location", xbmcgui.NOTIFICATION_INFO, 5000)
        self.moving_folder_id = None
        self.moving_folder_name = None
        utils.log(f"Pasting folder. FolderID={folder_id}, TargetFolderID={target_folder_id}", "DEBUG")
        self.populate_list()

    def delete_folder(self, folder_id, folder_name):
        confirmed = xbmcgui.Dialog().yesno("Confirm Delete", f"Are you sure you want to delete the folder '{folder_name}'?")
        utils.log(f"Deleting folder. FolderID={folder_id}, FolderName={folder_name}, Confirmed={confirmed}", "DEBUG")
        if not confirmed:
            return
        db_manager = DatabaseManager(Config().db_path)
        db_manager.delete_folder_and_contents(folder_id)
        xbmcgui.Dialog().notification("LibraryGenie", f"Folder '{folder_name}' deleted", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def open_settings(self):
        utils.log("Opening settings", "DEBUG")
        xbmc.executebuiltin("Addon.OpenSettings(plugin.video.librarygenie)")

    def create_new_list(self, parent_id):
        try:
            new_list_name = xbmcgui.Dialog().input("Enter new list name").strip()
            utils.log(f"Creating new list. ParentID={parent_id}, NewListName={new_list_name}", "DEBUG")
            if not new_list_name:
                xbmcgui.Dialog().notification("LibraryGenie", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
                return

            db_manager = DatabaseManager(Config().db_path)
            existing_list_id = db_manager.get_list_id_by_name(new_list_name)
            if existing_list_id:
                xbmcgui.Dialog().notification("LibraryGenie", f"The list name '{new_list_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
                return

        except Exception:
            utils.log(f"Error creating new list. ParentID={parent_id}, NewListName not set", "ERROR")
            return

        parent_id = int(parent_id) if parent_id != 'None' else None
        utils.log(f"Creating new list '{new_list_name}' under parent ID '{parent_id}'", "DEBUG")
        list_id = db_manager.insert_data('lists', {'name': new_list_name, 'folder_id': parent_id})
        utils.log(f"Created new list with ID: {list_id}", "DEBUG")
        if list_id:
            # Add current movie to the new list
            if self.item_info:
                utils.log(f"Adding media to new list: {self.item_info}", "DEBUG")
                data = {}
                fields_keys = [field.split()[0] for field in Config.FIELDS]
                utils.log(f"Field keys: {fields_keys}", "DEBUG")
                
                for field in fields_keys:
                    value = self.item_info.get(field)

                    if field in self.item_info and self.item_info[field]:
                        data[field] = self.item_info[field]
                
                if data:
                    utils.log("Processing data before insert...", "DEBUG")
                    data['list_id'] = list_id
                    utils.log(f"Added list_id: {list_id} to data", "DEBUG")
                    
                    if 'cast' in data and isinstance(data['cast'], list):
                        utils.log("Converting cast to JSON string", "DEBUG")
                        data['cast'] = json.dumps(data['cast'])
                    
                    # Ensure numeric fields are properly typed
                    for field in ['kodi_id', 'year', 'duration', 'votes']:
                        if field in data:
                            try:
                                data[field] = int(data[field]) if data[field] else 0
                                utils.log(f"Converted {field} to int: {data[field]}", "DEBUG")
                            except (ValueError, TypeError) as e:
                                utils.log(f"Error converting {field}: {str(e)}", "ERROR")
                                data[field] = 0
                    
                    if 'rating' in data:
                        try:
                            data['rating'] = float(data['rating']) if data['rating'] else 0.0
                            utils.log(f"Converted rating to float: {data['rating']}", "DEBUG")
                        except (ValueError, TypeError) as e:
                            utils.log(f"Error converting rating: {str(e)}", "ERROR")
                            data['rating'] = 0.0
                    
                    try:
                        result = db_manager.insert_data('list_items', data)
                        utils.log(f"Insert result: {result}", "DEBUG")
                    except Exception as e:
                        utils.log(f"Error during insert: {str(e)}", "ERROR")
                else:
                    utils.log("No media data to insert", "WARNING")
                notification_text = f"Added '{self.item_info.get('title', '')}' to new list '{new_list_name}'"
            else:
                notification_text = f"New list '{new_list_name}' created"

            xbmcgui.Dialog().notification("LibraryGenie", notification_text, xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def move_list(self, list_id, list_name):
        self.moving_list_id = list_id
        self.moving_list_name = list_name
        xbmcgui.Dialog().notification("LibraryGenie", f"Select new location for list: {list_name}", xbmcgui.NOTIFICATION_INFO, 5000)
        utils.log(f"Moving list. ListID={list_id}, ListName={list_name}", "DEBUG")
        self.populate_list()

    def paste_list_here(self, list_id, target_folder_id):
        db_manager = DatabaseManager(Config().db_path)
        db_manager.update_list_folder(list_id, target_folder_id)
        xbmcgui.Dialog().notification("LibraryGenie", f"List moved to new location", xbmcgui.NOTIFICATION_INFO, 5000)
        self.moving_list_id = None
        self.moving_list_name = None
        utils.log(f"Pasting list. ListID={list_id}, TargetFolderID={target_folder_id}", "DEBUG")
        self.populate_list()

    def edit_list(self, list_id):
        utils.log(f"Editing list, opening ListWindow. ListID={list_id}", "DEBUG")
        list_window = ListWindow(list_id)
        list_window.doModal()
        del list_window

    def delete_list(self, list_id, list_name):
        confirmed = xbmcgui.Dialog().yesno("Confirm Delete", f"Are you sure you want to delete the list '{list_name}'?")
        utils.log(f"Deleting list. ListID={list_id}, ListName={list_name}, Confirmed={confirmed}", "DEBUG")
        if not confirmed:
            return
        db_manager = DatabaseManager(Config().db_path)
        db_manager.delete_list(list_id)
        xbmcgui.Dialog().notification("LibraryGenie", f"List '{list_name}' deleted", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def add_media_to_list(self, list_id):
        db_manager = DatabaseManager(Config().db_path)
        fields_keys = [field.split()[0] for field in Config.FIELDS]
        data = {field: self.item_info.get(field) for field in fields_keys}
        data['list_id'] = list_id
        if 'cast' in data and isinstance(data['cast'], list):
            data['cast'] = json.dumps(data['cast'])
        utils.log(f"Adding media to list with data: {data}", "DEBUG")
        db_manager.insert_data('list_items', data)
        xbmcgui.Dialog().notification("LibraryGenie", "Media added to list", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def remove_media_from_list(self, list_id):
        db_manager = DatabaseManager(Config().db_path)
        item_id = db_manager.get_item_id_by_title_and_list(list_id, self.item_info['title'])
        utils.log(f"Removing media from list. ListID={list_id}, ItemID={item_id}", "DEBUG")
        if item_id:
            db_manager.delete_data('list_items', f'id={item_id}')
            xbmcgui.Dialog().notification("LibraryGenie", "Media removed from list", xbmcgui.NOTIFICATION_INFO, 5000)
        else:
            xbmcgui.Dialog().notification("LibraryGenie", "Media not found in list", xbmcgui.NOTIFICATION_WARNING, 5000)
        self.populate_list()

    def strip_color_tags(self, text):
        text = re.sub(r'\[COLOR.*?\](.*?)\[\/COLOR\]', r'\1', text)
        text = re.sub(r'\[B\](.*?)\[\/B\]', r'\1', text)
        text = text.lstrip('* +-').strip()
        return text

    def set_navigation(self):
        try:
            if self.list_control and hasattr(self.list_control, 'getId'):
                self.list_control.controlUp(self.list_control)
                self.list_control.controlDown(self.list_control)
                self.list_control.setEnabled(True)
                self.setFocus(self.list_control)
        except Exception as e:
            utils.log(f"Error setting navigation: {str(e)}", "ERROR")

    def get_parent_folder_id(self, folder_id):
        db_manager = DatabaseManager(Config().db_path)
        folder = db_manager.fetch_folder_by_id(folder_id)
        utils.log(f"Fetching parent folder ID. FolderID={folder_id}, ParentID={folder['parent_id'] if folder else 'None'}", "DEBUG")
        return folder['parent_id'] if folder else None

    def get_breadcrumbs(self, item_id, is_folder):
        db_manager = DatabaseManager(Config().db_path)
        breadcrumbs = []

        while item_id:
            if is_folder:
                folder = db_manager.fetch_folder_by_id(item_id)
                if folder:
                    breadcrumbs.insert(0, folder['name'])
                    item_id = folder['parent_id']
            else:
                list_item = db_manager.fetch_list_by_id(item_id)
                if list_item:
                    folder = db_manager.fetch_folder_by_id(list_item['folder_id'])
                    if folder:
                        breadcrumbs.insert(0, folder['name'])
                        item_id = folder['parent_id']
                    else:
                        item_id = None

        if not breadcrumbs:
            breadcrumbs.append("Home")

        utils.log(f"Breadcrumbs: {breadcrumbs}", "DEBUG")
        return breadcrumbs

    def close(self):
        utils.log("Closing CustomWindow...", "DEBUG")
        pyxbmct.AddonDialogWindow.close(self)
        del self

    def __del__(self):
        utils.log("Deleting CustomWindow instance...", "DEBUG")