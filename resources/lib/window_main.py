""" /resources/lib/window_main.py """
# Import necessary modules and classes
import re
import json
import pyxbmct
import xbmc
import xbmcgui
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib.window_list import ListWindow

class MainWindow(pyxbmct.AddonDialogWindow):
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
                self.placeControl(image_control, 0, 0, rowspan=1, columnspan=1, pad_x=10, pad_y=10)
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
            xbmc.log(f"ListGenius: Expanding folder with ID {folder_id}", xbmc.LOGDEBUG)
            if not self.folder_expanded_states.get(folder_id, False):
                self.update_folder_expanded_states(folder_id, True)
                self.populate_list(folder_id)  # Pass folder_id to reselect it

    def collapse_selected_folder(self):
        selected_item = self.list_control.getSelectedItem()
        if selected_item and selected_item.getProperty('isFolder') == 'true':
            folder_id = int(selected_item.getProperty('folder_id'))
            self.selected_item_id = folder_id  # Set the selected item ID
            self.selected_is_folder = True  # Indicate that the selected item is a folder
            xbmc.log(f"ListGenius: Collapsing folder with ID {folder_id}", xbmc.LOGDEBUG)
            if self.folder_expanded_states.get(folder_id, False):
                self.update_folder_expanded_states(folder_id, False)
                self.populate_list(folder_id)  # Pass folder_id to reselect it

    def update_folder_expanded_states(self, current_folder_id, expand):
        xbmc.log(f"ListGenius: Updating folder expanded states for folder ID {current_folder_id}, expand={expand}", xbmc.LOGDEBUG)
        for folder_id in self.folder_expanded_states.keys():
            if folder_id != current_folder_id:
                self.folder_expanded_states[folder_id] = False
        self.folder_expanded_states[current_folder_id] = expand
        parent_id = self.get_parent_folder_id(current_folder_id)
        while parent_id:
            self.folder_expanded_states[parent_id] = True
            parent_id = self.get_parent_folder_id(parent_id)

    def populate_list(self, focus_folder_id=None):
        xbmc.log("ListGenius: Populating list...", xbmc.LOGDEBUG)
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

            xbmc.log(f"ListGenius: Folder color statuses: {folder_color_status}", xbmc.LOGDEBUG)

        self.list_data = []

        root_folders = [f for f in all_folders if f['parent_id'] is None]
        root_lists = [l for l in all_lists if l['folder_id'] is None]

        combined_root = root_folders + root_lists
        combined_root.sort(key=lambda x: self.clean_name(x['name']).lower())
        xbmc.log(f"ListGenius: Sorted combined root items: {[(self.clean_name(i['name']), i['name']) for i in combined_root]}", xbmc.LOGDEBUG)

        any_root_folder_expanded = False
        for item in combined_root:
            if 'parent_id' in item:
                folder_media_count = db_manager.get_folder_media_count(item['id'])
                xbmc.log(f"ListGenius: Adding root folder item - ID: {item['id']}, Name: {item['name']} ({folder_media_count})", xbmc.LOGDEBUG)
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
        xbmc.log(f"ListGenius: Adding folder - Name: {folder['name']}, Expanded: {expanded}, Indent: {indent}, Color: {color}", xbmc.LOGDEBUG)

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
            xbmc.log(f"ListGenius: Sorted combined items for {folder['name']}: {[(self.clean_name(i['name']), i['name']) for i in combined]}", xbmc.LOGDEBUG)

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
        xbmc.log(f"ListGenius: Reselecting previous item. focus_folder_id={focus_folder_id}, selected_item_id={self.selected_item_id}, selected_is_folder={self.selected_is_folder}", xbmc.LOGDEBUG)
        focus_id = self.selected_item_id if self.selected_item_id is not None else focus_folder_id
        focus_is_folder = self.selected_is_folder if self.selected_is_folder is not None else True

        if focus_id is not None:
            for index in range(self.list_control.size()):
                list_item = self.list_control.getListItem(index)
                is_folder = list_item.getProperty('isFolder') == 'true'
                list_item_id = int(list_item.getProperty('folder_id') if is_folder else list_item.getProperty('list_id'))

                xbmc.log(f"ListGenius: Checking list item. Index={index}, ID={list_item_id}, IsFolder={is_folder}, Label={list_item.getLabel()}", xbmc.LOGDEBUG)
                if list_item_id == focus_id and is_folder == focus_is_folder:
                    self.list_control.selectItem(index)
                    self.setFocus(self.list_control)
                    xbmc.log(f"ListGenius: Item reselected. Index={index}, ID={list_item_id}, Label={list_item.getLabel()}", xbmc.LOGDEBUG)
                    break
            else:
                xbmc.log(f"ListGenius: Could not find item to reselect with ID {focus_id} and IsFolder={focus_is_folder}", xbmc.LOGDEBUG)

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
            xbmc.log(f"ListGenius: Item clicked. Label={selected_item_label}, ID={selected_item_id}, IsFolder={is_folder}", xbmc.LOGDEBUG)

            if selected_item_id is not None:
                self.display_item_options(selected_item_label, selected_item_id, is_folder)

    def handle_action(self, action, parent_id):
        xbmc.log(f"ListGenius: Handling action. Action={action}, ParentID={parent_id}", xbmc.LOGDEBUG)
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
        xbmc.log(f"ListGenius: Folder options selected. FolderID={folder_data['id']}, Option={options[selected_option] if selected_option != -1 else 'None'}", xbmc.LOGDEBUG)
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
        options = []

        if self.is_playable:
            if list_data.get('color') == 'red':
                options.append("Add Media to List")
            elif list_data.get('color') == 'green':
                options.append("Remove Media from List")

        options.extend([
            "Rename This List",
            "Move This List",
            "Edit This List",
            "Delete This List",
            "Settings"
        ])

        selected_option = xbmcgui.Dialog().select("Choose an action", options)
        xbmc.log(f"ListGenius: List options selected. ListID={list_data['id']}, Option={options[selected_option] if selected_option != -1 else 'None'}", xbmc.LOGDEBUG)
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
        elif options[selected_option] == "Settings":
            self.open_settings()

    def handle_paste_action(self, action, target_id):
        xbmc.log(f"ListGenius: Handling paste action. Action={action}, TargetID={target_id}", xbmc.LOGDEBUG)
        if "paste_list_here" in action:
            list_id = int(action.split(':')[1])
            self.paste_list_here(list_id, target_id)
        elif "paste_folder_here" in action:
            folder_id = int(action.split(':')[1])
            self.paste_folder_here(folder_id, target_id)

    def rename_list(self, list_id, current_name):
        clean_name = re.sub(r'\[.*?\]', '', current_name)
        new_name = xbmcgui.Dialog().input("Enter new name for the list", defaultt=clean_name).strip()
        xbmc.log(f"ListGenius: Renaming list. ListID={list_id}, CurrentName={current_name}, NewName={new_name}", xbmc.LOGDEBUG)
        if not new_name:
            xbmcgui.Dialog().notification("ListGenius", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        db_manager = DatabaseManager(Config().db_path)
        existing_list_id = db_manager.get_list_id_by_name(new_name)
        if existing_list_id and existing_list_id != list_id:
            xbmcgui.Dialog().notification("ListGenius", f"The list name '{new_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        db_manager.update_data('lists', {'name': new_name}, f'id={list_id}')
        xbmcgui.Dialog().notification("ListGenius", f"List renamed to '{new_name}'", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def create_new_folder(self, parent_id):
        new_folder_name = xbmcgui.Dialog().input("Enter new folder name").strip()
        xbmc.log(f"ListGenius: Creating new folder. ParentID={parent_id}, NewFolderName={new_folder_name}", xbmc.LOGDEBUG)
        if not new_folder_name:
            xbmcgui.Dialog().notification("ListGenius", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        db_manager = DatabaseManager(Config().db_path)
        existing_folder_id = db_manager.get_folder_id_by_name(new_folder_name)
        if existing_folder_id:
            xbmcgui.Dialog().notification("ListGenius", f"The folder name '{new_folder_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        parent_id = int(parent_id) if parent_id != 'None' else None
        xbmc.log(f"ListGenius: Creating new folder '{new_folder_name}' under parent ID '{parent_id}'", xbmc.LOGDEBUG)
        db_manager.insert_folder(new_folder_name, parent_id)
        xbmcgui.Dialog().notification("ListGenius", f"New folder '{new_folder_name}' created", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def rename_folder(self, folder_id, current_name):
        clean_name = re.sub(r'^[\s>]+', '', current_name)
        clean_name = re.sub(r'\[.*?\]', '', clean_name)

        new_name = xbmcgui.Dialog().input("Enter new name for the folder", defaultt=clean_name).strip()
        xbmc.log(f"ListGenius: Renaming folder. FolderID={folder_id}, CurrentName={current_name}, NewName={new_name}", xbmc.LOGDEBUG)
        if not new_name:
            xbmcgui.Dialog().notification("ListGenius", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        db_manager = DatabaseManager(Config().db_path)
        existing_folder_id = db_manager.get_folder_id_by_name(new_name)
        if existing_folder_id and existing_folder_id != folder_id:
            xbmcgui.Dialog().notification("ListGenius", f"The folder name '{new_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        db_manager.update_folder_name(folder_id, new_name)
        xbmcgui.Dialog().notification("ListGenius", f"Folder renamed to '{new_name}'", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def move_folder(self, folder_id, folder_name):
        self.moving_folder_id = folder_id
        self.moving_folder_name = folder_name
        xbmcgui.Dialog().notification("ListGenius", f"Select new location for folder: {folder_name}", xbmcgui.NOTIFICATION_INFO, 5000)
        xbmc.log(f"ListGenius: Moving folder. FolderID={folder_id}, FolderName={folder_name}", xbmc.LOGDEBUG)
        self.populate_list()

    def paste_folder_here(self, folder_id, target_folder_id):
        db_manager = DatabaseManager(Config().db_path)
        db_manager.update_folder_parent(folder_id, target_folder_id)
        xbmcgui.Dialog().notification("ListGenius", f"Folder moved to new location", xbmcgui.NOTIFICATION_INFO, 5000)
        self.moving_folder_id = None
        self.moving_folder_name = None
        xbmc.log(f"ListGenius: Pasting folder. FolderID={folder_id}, TargetFolderID={target_folder_id}", xbmc.LOGDEBUG)
        self.populate_list()

    def delete_folder(self, folder_id, folder_name):
        confirmed = xbmcgui.Dialog().yesno("Confirm Delete", f"Are you sure you want to delete the folder '{folder_name}'?")
        xbmc.log(f"ListGenius: Deleting folder. FolderID={folder_id}, FolderName={folder_name}, Confirmed={confirmed}", xbmc.LOGDEBUG)
        if not confirmed:
            return
        db_manager = DatabaseManager(Config().db_path)
        db_manager.delete_folder_and_contents(folder_id)
        xbmcgui.Dialog().notification("ListGenius", f"Folder '{folder_name}' deleted", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def open_settings(self):
        xbmc.log("ListGenius: Opening settings", xbmc.LOGDEBUG)
        xbmc.executebuiltin("Addon.OpenSettings(plugin.video.listgenius)")

    def create_new_list(self, parent_id):
        new_list_name = xbmcgui.Dialog().input("Enter new list name").strip()
        xbmc.log(f"ListGenius: Creating new list. ParentID={parent_id}, NewListName={new_list_name}", xbmc.LOGDEBUG)
        if not new_list_name:
            xbmcgui.Dialog().notification("ListGenius", "Invalid name entered", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        db_manager = DatabaseManager(Config().db_path)
        existing_list_id = db_manager.get_list_id_by_name(new_list_name)
        if existing_list_id:
            xbmcgui.Dialog().notification("ListGenius", f"The list name '{new_list_name}' already exists", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        parent_id = int(parent_id) if parent_id != 'None' else None
        xbmc.log(f"ListGenius: Creating new list '{new_list_name}' under parent ID '{parent_id}'", xbmc.LOGDEBUG)
        db_manager.insert_data('lists', {'name': new_list_name, 'folder_id': parent_id})
        xbmcgui.Dialog().notification("ListGenius", f"New list '{new_list_name}' created", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def move_list(self, list_id, list_name):
        self.moving_list_id = list_id
        self.moving_list_name = list_name
        xbmcgui.Dialog().notification("ListGenius", f"Select new location for list: {list_name}", xbmcgui.NOTIFICATION_INFO, 5000)
        xbmc.log(f"ListGenius: Moving list. ListID={list_id}, ListName={list_name}", xbmc.LOGDEBUG)
        self.populate_list()

    def paste_list_here(self, list_id, target_folder_id):
        db_manager = DatabaseManager(Config().db_path)
        db_manager.update_list_folder(list_id, target_folder_id)
        xbmcgui.Dialog().notification("ListGenius", f"List moved to new location", xbmcgui.NOTIFICATION_INFO, 5000)
        self.moving_list_id = None
        self.moving_list_name = None
        xbmc.log(f"ListGenius: Pasting list. ListID={list_id}, TargetFolderID={target_folder_id}", xbmc.LOGDEBUG)
        self.populate_list()

    def edit_list(self, list_id):
        xbmc.log(f"ListGenius: Editing list, opening ListWindow. ListID={list_id}", xbmc.LOGDEBUG)
        list_window = ListWindow(list_id)
        list_window.doModal()
        del list_window

    def delete_list(self, list_id, list_name):
        confirmed = xbmcgui.Dialog().yesno("Confirm Delete", f"Are you sure you want to delete the list '{list_name}'?")
        xbmc.log(f"ListGenius: Deleting list. ListID={list_id}, ListName={list_name}, Confirmed={confirmed}", xbmc.LOGDEBUG)
        if not confirmed:
            return
        db_manager = DatabaseManager(Config().db_path)
        db_manager.delete_data('lists', f'id={list_id}')
        xbmcgui.Dialog().notification("ListGenius", f"List '{list_name}' deleted", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def add_media_to_list(self, list_id):
        db_manager = DatabaseManager(Config().db_path)
        fields_keys = [field.split()[0] for field in Config.FIELDS]
        data = {field: self.item_info.get(field) for field in fields_keys}
        data['list_id'] = list_id
        if 'cast' in data and isinstance(data['cast'], list):
            data['cast'] = json.dumps(data['cast'])
        xbmc.log(f"ListGenius: Adding media to list with data: {data}", xbmc.LOGDEBUG)
        db_manager.insert_data('list_items', data)
        xbmcgui.Dialog().notification("ListGenius", "Media added to list", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()

    def remove_media_from_list(self, list_id):
        db_manager = DatabaseManager(Config().db_path)
        item_id = db_manager.get_item_id_by_title_and_list(list_id, self.item_info['title'])
        xbmc.log(f"ListGenius: Removing media from list. ListID={list_id}, ItemID={item_id}", xbmc.LOGDEBUG)
        if item_id:
            db_manager.delete_data('list_items', f'id={item_id}')
            xbmcgui.Dialog().notification("ListGenius", "Media removed from list", xbmcgui.NOTIFICATION_INFO, 5000)
        else:
            xbmcgui.Dialog().notification("ListGenius", "Media not found in list", xbmcgui.NOTIFICATION_WARNING, 5000)
        self.populate_list()

    def strip_color_tags(self, text):
        text = re.sub(r'\[COLOR.*?\](.*?)\[\/COLOR\]', r'\1', text)
        text = re.sub(r'\[B\](.*?)\[\/B\]', r'\1', text)
        text = text.lstrip('* +-').strip()
        return text

    def set_navigation(self):
        self.list_control.controlUp(self.list_control)
        self.list_control.controlDown(self.list_control)
        self.setFocus(self.list_control)

    def get_parent_folder_id(self, folder_id):
        db_manager = DatabaseManager(Config().db_path)
        folder = db_manager.fetch_folder_by_id(folder_id)
        xbmc.log(f"ListGenius: Fetching parent folder ID. FolderID={folder_id}, ParentID={folder['parent_id'] if folder else 'None'}", xbmc.LOGDEBUG)
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

        xbmc.log(f"ListGenius: Breadcrumbs: {breadcrumbs}", xbmc.LOGDEBUG)
        return breadcrumbs

    def close(self):
        xbmc.log("ListGenius: Closing CustomWindow...", xbmc.LOGDEBUG)
        pyxbmct.AddonDialogWindow.close(self)
        del self

    def __del__(self):
        xbmc.log("ListGenius: Deleting CustomWindow instance...", xbmc.LOGDEBUG)