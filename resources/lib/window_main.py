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
from resources.lib.window_list_browser import ListBrowserWindow
from resources.lib import utils

utils.log("Initializing MainWindow module", "INFO")
from resources.lib.window_base import BaseWindow

class MainWindow(BaseWindow):
    INDENTATION_MULTIPLIER = 3  # Used for indenting sublevels

    def __init__(self, item_info, title="Item Info"):
        super().__init__(title)
        self.setGeometry(800, 600, 10, 10)
        self.item_info = item_info
        self.list_data = []
        # We'll store our own selection state:
        self.selected_item_id = None   # For folders: the folder id; for lists: the list id.
        self.selected_is_folder = None   # True if the selected item is a folder.
        self.is_playable = self.check_playable()
        # Set root (id 0) to be expanded by default.
        self.folder_expanded_states = {0: True}
        self.moving_list_id = None
        self.moving_list_name = None
        self.moving_folder_id = None
        self.moving_folder_name = None
        self.folder_color_status = {}  # Add folder color status tracking

        self.media_label = pyxbmct.Label("")
        self.list_control = pyxbmct.List()

        self.setup_ui()
        self.populate_list()
        self.set_navigation()
        # (No timer is used in this version.)

    def setup_ui(self):
        self.setGeometry(800, 600, 13, 10)  # Added 1 row for exit button
        # Media info at top right
        title = self.item_info.get('title', 'Unknown')
        year = self.item_info.get('year', '')
        title_year = f"{title} ({year})" if year else title
        
        # Add poster image
        self.poster_image = pyxbmct.Image('')
        poster_path = self.item_info.get('poster', self.item_info.get('art', {}).get('poster', ''))
        if poster_path:
            # Movie posters typically have a 2:3 aspect ratio (e.g., 27x40 inches)
            self.poster_image.setImage(poster_path)
            # Set smaller dimensions while maintaining 2:3 aspect ratio
            self.poster_image.setWidth(120)  # Standard movie poster scaled down
            self.poster_image.setHeight(180)  # Maintains 2:3 ratio (120 * 1.5)
            # Place poster in top-left with minimal padding
            self.placeControl(self.poster_image, 0, 0, rowspan=3, columnspan=1, pad_x=5, pad_y=5)
        
        self.title_label = pyxbmct.Label(title_year, alignment=0)
        self.placeControl(self.title_label, 0, 1, columnspan=9, pad_x=5)

        # Add plot under title
        plot = self.item_info.get('plot', '')
        self.plot_label = pyxbmct.TextBox()
        self.plot_label.setText(plot)
        self.placeControl(self.plot_label, 1, 1, rowspan=2, columnspan=9, pad_x=5)

        # File browser list moved up to row 3
        self.list_control = pyxbmct.List(_imageWidth=25, _imageHeight=25,
                                         _itemTextXOffset=0, _itemHeight=30, _space=2)
        self.placeControl(self.list_control, 3, 0, rowspan=8, columnspan=10, pad_x=5, pad_y=5)
        self.connect(self.list_control, self.on_list_item_click)

        # Create legend label with initial text
        self.legend_label = pyxbmct.Label("[COLOR red]Not in list/folder[/COLOR], [COLOR green]In list/folder[/COLOR]")
        self.placeControl(self.legend_label, 11, 0, columnspan=10, pad_x=5)

        # Status/tips bar with dynamic text
        self.status_label = pyxbmct.Label("")
        self.placeControl(self.status_label, 12, 0, columnspan=6, pad_x=5)
        # The tips will be updated by update_status_text()

        # Collapse All button at bottom
        self.collapse_all_button = pyxbmct.Button("Collapse All")
        self.placeControl(self.collapse_all_button, 12, 6, columnspan=2, pad_x=5, pad_y=5)
        self.connect(self.collapse_all_button, self.collapse_all_folders)

        # Exit button at bottom right
        self.exit_button = pyxbmct.Button("Exit")
        self.placeControl(self.exit_button, 12, 8, columnspan=2, pad_x=5, pad_y=5)
        self.connect(self.exit_button, self.close)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

        # Default folder icon path
        self.folder_icon = "DefaultFolder.png"

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
        # (Not used: Media info is handled in setup_ui)
        pass

    def onAction(self, action):
        # If the action is up or down, update our stored selection state and legend
        if action in (xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN):
            self.update_selection_state()
            self.update_status_text()
        # (Now update our state as before for left/right actions)
        current_item = self.list_control.getSelectedItem()
        if current_item:
            if current_item.getProperty('isRoot') == 'true':
                self.selected_item_id = 0
                self.selected_is_folder = True
            elif current_item.getProperty('isFolder') == 'true':
                try:
                    self.selected_item_id = int(current_item.getProperty('folder_id'))
                except:
                    self.selected_item_id = None
                self.selected_is_folder = True
            else:
                try:
                    self.selected_item_id = int(current_item.getProperty('list_id'))
                except:
                    self.selected_item_id = None
                self.selected_is_folder = False

        if not current_item:
            return super().onAction(action)

        is_folder = current_item.getProperty('isFolder') == 'true'
        is_root = current_item.getProperty('isRoot') == 'true'
        if is_folder or is_root:
            folder_id_prop = current_item.getProperty('folder_id')
            folder_id = 0 if is_root else (int(folder_id_prop) if folder_id_prop else None)
            if folder_id is None:
                return
            current_pos = self.list_control.getSelectedPosition()
            if action == xbmcgui.ACTION_MOVE_RIGHT:
                self.folder_expanded_states[folder_id] = True
                self.populate_list()
                self.list_control.selectItem(current_pos)
                self.update_status_text()
                return
            elif action == xbmcgui.ACTION_MOVE_LEFT:
                self.folder_expanded_states[folder_id] = False
                self.populate_list()
                self.list_control.selectItem(current_pos)
                self.update_status_text()
                return

        try:
            list_id = int(current_item.getProperty('list_id'))
            is_member = current_item.getProperty('is_member') == '1'
            if action == xbmcgui.ACTION_MOVE_LEFT and is_member:
                db_manager = DatabaseManager(Config().db_path)
                item_id = db_manager.get_item_id_by_title_and_list(list_id, self.item_info['title'])
                if item_id:
                    db_manager.delete_data('list_items', f'id={item_id}')
                    xbmcgui.Dialog().notification("LibraryGenie", "Media removed from list",
                                                   xbmcgui.NOTIFICATION_INFO, 2000)
                    current_position = self.list_control.getSelectedPosition()
                    self.populate_list()
                    self.list_control.selectItem(current_position)
                    self.setFocus(self.list_control)
                    self.update_status_text()
            elif action == xbmcgui.ACTION_MOVE_RIGHT and not is_member:
                db_manager = DatabaseManager(Config().db_path)
                fields_keys = [field.split()[0] for field in Config.FIELDS]
                data = {field: self.item_info.get(field) for field in fields_keys}
                data['list_id'] = list_id
                if 'cast' in data and isinstance(data['cast'], list):
                    data['cast'] = json.dumps(data['cast'])
                db_manager.insert_data('list_items', data)
                xbmcgui.Dialog().notification("LibraryGenie", "Media added to list",
                                               xbmcgui.NOTIFICATION_INFO, 2000)
                current_position = self.list_control.getSelectedPosition()
                self.populate_list()
                self.list_control.selectItem(current_position)
                self.setFocus(self.list_control)
                self.update_status_text()
        except (ValueError, TypeError):
            pass

        super().onAction(action)

    def on_list_item_click(self):
        selected_item = self.list_control.getSelectedItem()
        if not selected_item:
            return

        if selected_item.getProperty('isRoot') == 'true':
            self.open_settings()
            return

        action = selected_item.getProperty('action')
        if action:
            self.handle_action(action, selected_item.getProperty('parent_id'))
            return

        if selected_item.getProperty('isFolder') == 'true':
            self.on_options_click()
            return

        # Handle list click - show options for the list
        try:
            list_id = int(selected_item.getProperty('list_id'))
            list_name = self.strip_color_tags(selected_item.getLabel())
            color = 'green' if selected_item.getProperty('is_member') == '1' else 'red'
            self.show_list_options({'id': list_id, 'name': list_name, 'color': color})
        except (ValueError, TypeError):
            pass

        return

    def onFocus(self, controlId):
        super().onFocus(controlId)
        if controlId == self.list_control.getId():
            # When the control receives focus, update our stored state and legend.
            self.update_selection_state()
            self.update_status_text()

    def update_selection_state(self):
        """Update our stored selection state based on the currently focused item."""
        current_item = self.list_control.getSelectedItem()
        if current_item:
            if current_item.getProperty('isRoot') == 'true':
                self.selected_item_id = 0
                self.selected_is_folder = True
            elif current_item.getProperty('isFolder') == 'true':
                try:
                    self.selected_item_id = int(current_item.getProperty('folder_id'))
                except Exception:
                    self.selected_item_id = None
                self.selected_is_folder = True
            else:
                try:
                    self.selected_item_id = int(current_item.getProperty('list_id'))
                except Exception:
                    self.selected_item_id = None
                self.selected_is_folder = False
        else:
            self.selected_item_id = None
            self.selected_is_folder = None

        # Update legend text with count
        legend_text = ""
        if current_item and not current_item.getProperty('isSpecial') == 'true' and current_item.getProperty('isRoot') != 'true':
            is_folder = current_item.getProperty('isFolder') == 'true'
            try:
                if is_folder:
                    folder_id = int(current_item.getProperty('folder_id'))
                    color = self.folder_color_status.get(folder_id, 'red')
                    status = "In folder" if color == 'green' else "Not in folder"
                    legend_text = f"[COLOR {color}]{status}[/COLOR]"
                    
                    # Always show count for folders
                    label = current_item.getLabel()
                    if '(' in label and ')' in label:
                        count = int(label.split('(')[-1].split(')')[0])
                        legend_text += f", ({count}) = total movies in folder"
                else:
                    is_member = current_item.getProperty('is_member') == '1'
                    color = 'green' if is_member else 'red'
                    status = "In list" if is_member else "Not in list"
                    legend_text = f"[COLOR {color}]{status}[/COLOR]"
                    
                    # Show count for lists when playable
                    if self.is_playable:
                        label = current_item.getLabel()
                        if '(' in label and ')' in label:
                            count = int(label.split('(')[-1].split(')')[0])
                            legend_text += f", ({count}) = total movies in list"
            except (IndexError, ValueError, TypeError):
                pass

        if hasattr(self, 'legend_label'):
            self.legend_label.setLabel(legend_text)

    def update_status_text(self):
        """
        Update the navigation legend based on our stored selection state.
        We use self.selected_item_id and self.selected_is_folder.
        """
        current_item = self.list_control.getSelectedItem()
        if not current_item:
            self.status_label.setLabel("No items available")
            return

        # Handle special action items
        action = current_item.getProperty('action')
        if action == 'new_folder':
            self.status_label.setLabel("Click = Make a folder here")
            return
        elif action == 'new_list':
            self.status_label.setLabel("Click = Make a list here")
            return

        if self.selected_item_id == 0:
            self.status_label.setLabel("ROOT: <Collapse/Expand> , Click = Open Settings")
        elif self.selected_is_folder:
            for item in self.list_data:
                if item.get('isFolder') and item.get('id') == self.selected_item_id:
                    if item.get('expanded'):
                        self.status_label.setLabel("FOLDER: <Collapse/Expand> , Click = Options")
                    else:
                        self.status_label.setLabel("FOLDER: <Collapse/Expand> , Click = Options")
                    return
            self.status_label.setLabel("FOLDER: <Collapse/Expand> , Click = Options")
        else:
            self.status_label.setLabel("LIST: <Remove/Add> , Click = Options")

    def populate_list(self, focus_folder_id=None):
        utils.log("Populating list...", "DEBUG")
        db_manager = DatabaseManager(Config().db_path)
        self.list_control.reset()

        all_folders = db_manager.fetch_all_folders()
        all_lists = db_manager.fetch_all_lists_with_item_status(self.item_info.get('kodi_id', 0))

        # For playable media, fetch folder status for color coding and propagate status upward.
        self.folder_color_status = {}
        if self.is_playable:
            folder_status = db_manager.fetch_folders_with_item_status(self.item_info.get('kodi_id', 0))
            for folder in folder_status:
                self.folder_color_status[folder['id']] = 'green' if folder['is_member'] else 'red'
            def propagate_status(folder_id):
                while folder_id is not None:
                    parent_id = next((f['parent_id'] for f in all_folders if f['id'] == folder_id), None)
                    if parent_id is not None:
                        child_folders = [f['id'] for f in all_folders if f['parent_id'] == parent_id]
                        if any(folder_color_status.get(cid, 'red') == 'green' for cid in child_folders):
                            folder_color_status[parent_id] = 'green'
                    folder_id = parent_id
            for folder_id in folder_color_status:
                propagate_status(folder_id)
            utils.log(f"Folder color statuses: {folder_color_status}", "DEBUG")

        self.list_data = []

        # Add the Root item as the sole top-level entry.
        root_expanded = self.folder_expanded_states.get(0, False)
        root_item = xbmcgui.ListItem("Root")
        root_item.setArt({'icon': self.folder_icon, 'thumb': self.folder_icon})
        root_item.setProperty('isFolder', 'true')
        root_item.setProperty('isRoot', 'true')
        root_item.setProperty('folder_id', '0')
        root_item.setProperty('expanded', str(root_expanded))
        root_label = "[B]Root[/B]"
        root_item.setLabel(root_label)
        self.list_control.addItem(root_item)
        self.list_data.append({'name': 'Root', 'isFolder': True, 'isRoot': True, 'id': 0, 'expanded': root_expanded})

        # If Root is expanded, add its children (top-level folders and lists).
        if root_expanded:
            # First add the new items options at root level
            new_list_item = xbmcgui.ListItem("  <New List>")
            new_list_item.setProperty('isFolder', 'false')
            new_list_item.setProperty('isSpecial', 'true')
            new_list_item.setProperty('action', 'new_list')
            new_list_item.setProperty('parent_id', 'None')
            self.list_control.addItem(new_list_item)
            self.list_data.append({'name': '<New List>', 'isFolder': False, 'isSpecial': True, 'id': None, 'indent': 0, 'action': 'new_list'})

            new_folder_item = xbmcgui.ListItem("  <New Folder>")
            new_folder_item.setProperty('isFolder', 'true')
            new_folder_item.setProperty('isSpecial', 'true')
            new_folder_item.setProperty('action', 'new_folder')
            new_folder_item.setProperty('parent_id', 'None')
            self.list_control.addItem(new_folder_item)
            self.list_data.append({'name': '<New Folder>', 'isFolder': True, 'isSpecial': True, 'id': None, 'indent': 0, 'action': 'new_folder'})

            # Add any paste/move actions if active
            if self.moving_list_id:
                paste_list_item = xbmcgui.ListItem(f"  <Paste List Here : {self.moving_list_name}>")
                paste_list_item.setProperty('isFolder', 'false')
                paste_list_item.setProperty('isSpecial', 'true')
                paste_list_item.setProperty('action', f"paste_list_here:{self.moving_list_id}")
                paste_list_item.setProperty('parent_id', 'None')
                self.list_control.addItem(paste_list_item)
                self.list_data.append({'name': f'<Paste List Here : {self.moving_list_name}>', 'isFolder': False, 'isSpecial': True, 'id': None, 'indent': 0, 'action': f"paste_list_here:{self.moving_list_id}"})

            if self.moving_folder_id:
                paste_folder_item = xbmcgui.ListItem(f"  <Paste Folder Here : {self.moving_folder_name}>")
                paste_folder_item.setProperty('isFolder', 'true')
                paste_folder_item.setProperty('isSpecial', 'true')
                paste_folder_item.setProperty('action', f"paste_folder_here:{self.moving_folder_id}")
                paste_folder_item.setProperty('parent_id', 'None')
                self.list_control.addItem(paste_folder_item)
                self.list_data.append({'name': f'<Paste Folder Here : {self.moving_folder_name}>', 'isFolder': True, 'isSpecial': True, 'id': None, 'indent': 0, 'action': f"paste_folder_here:{self.moving_folder_id}"})

            # Then add regular items
            root_lists = [list_item for list_item in all_lists if list_item['folder_id'] is None]
            root_folders = [folder for folder in all_folders if folder.get('parent_id') is None]
            combined_root = root_lists + root_folders
            combined_root.sort(key=lambda x: (0, self.clean_name(x['name']).lower()) if 'parent_id' in x else (1, self.clean_name(x['name']).lower()))
            utils.log(f"Sorted combined root items: {[(self.clean_name(i['name']), i['name']) for i in combined_root]}", "DEBUG")
            for item in combined_root:
                if 'parent_id' in item:
                    utils.log(f"Adding root folder item - ID: {item['id']}, Name: {item['name']}", "DEBUG")
                    self.add_folder_items(item, 0, all_folders, all_lists, folder_color_status)
                else:
                    list_media_count = db_manager.get_list_media_count(item['id'])
                    list_label = f"  {item['name']} ({list_media_count})"
                    color = 'green' if item['is_member'] else 'red'
                    if self.is_playable:
                        list_label = f"[COLOR {color}]{list_label}[/COLOR]"
                    list_item = xbmcgui.ListItem(list_label)
                    list_item.setProperty('isFolder', 'false')
                    list_item.setProperty('list_id', str(item['id']))
                    list_item.setProperty('is_member', str(item['is_member']))
                    self.list_control.addItem(list_item)
                    self.list_data.append({'name': item['name'], 'isFolder': False, 'id': item['id'], 'indent': 0, 'color': color if self.is_playable else None})
            # Note: Special "Add" entries are omitted at root level.

        if self.list_control.size() > 0 and self.list_control.getSelectedItem() is None:
            self.list_control.selectItem(0)
            self.setFocus(self.list_control)
        self.update_status_text()  # update the legend

        self.list_control.setEnabled(True)
        
        # Update legend text with count
        legend_text = "[COLOR red]Not in list/folder[/COLOR], [COLOR green]In list/folder[/COLOR]"
        if self.is_playable:
            selected_item = self.list_control.getSelectedItem()
            if selected_item and not selected_item.getProperty('isSpecial') == 'true':
                try:
                    count = int(selected_item.getLabel().split('(')[-1].split(')')[0])
                    legend_text += f", ({count}) = count of movies in list/folder"
                except (IndexError, ValueError):
                    pass
        self.legend_label.setLabel(legend_text)
        
        self.reselect_previous_item(focus_folder_id)

    def clean_name(self, name):
        name = re.sub(r'\[COLOR.*?\](.*?)\[\/COLOR\]', r'\1', name)
        name = re.sub(r'\[B\](.*?)\[\/B\]', r'\1', name)
        name = name.lstrip('+ -').strip()
        return name

    def add_folder_items(self, folder, indent, all_folders, all_lists, folder_color_status):
        expanded = self.folder_expanded_states.get(folder['id'], False)
        color = folder_color_status.get(folder['id'], 'red') if self.is_playable else None
        utils.log(f"Adding folder - Name: {folder['name']}, Expanded: {expanded}, Indent: {indent}, Color: {color}", "DEBUG")
        db_manager = DatabaseManager(Config().db_path)
        folder_media_count = db_manager.get_folder_media_count(folder['id'])
        indent_str = "  " * indent
        if color:
            folder_label = f"{indent_str}[B][COLOR {color}]{folder['name']} ({folder_media_count})[/COLOR][/B]"
        else:
            folder_label = f"{indent_str}{folder['name']} ({folder_media_count})"
        folder_item = xbmcgui.ListItem(folder_label)
        folder_item.setProperty('indent', indent_str)
        folder_item.setProperty('isFolder', 'true')
        folder_item.setProperty('folder_id', str(folder['id']))
        folder_item.setProperty('expanded', str(expanded))
        self.list_control.addItem(folder_item)
        self.list_data.append({'name': folder['name'], 'isFolder': True, 'id': folder['id'], 'indent': indent, 'expanded': expanded, 'color': color})
        if expanded:
            # First add the new items options
            self.add_new_items(folder, indent + 1)

            # Then add subfolders and lists
            folder_lists = [list_item for list_item in all_lists if list_item['folder_id'] == folder['id']]
            subfolders = [f for f in all_folders if f['parent_id'] == folder['id']]
            combined = folder_lists + subfolders
            combined.sort(key=lambda x: (0, self.clean_name(x['name']).lower()) if 'parent_id' in x else (1, self.clean_name(x['name']).lower()))
            utils.log(f"Sorted combined items for {folder['name']}: {[(self.clean_name(i['name']), i['name']) for i in combined]}", "DEBUG")
            for item in combined:
                if 'parent_id' in item:
                    self.add_folder_items(item, indent + 1, all_folders, all_lists, folder_color_status)
                else:
                    list_media_count = db_manager.get_list_media_count(item['id'])
                    list_label = f"{' ' * ((indent + 1) * self.INDENTATION_MULTIPLIER)} {item['name']} ({list_media_count})"
                    color = 'green' if item['is_member'] else 'red'
                    if self.is_playable:
                        list_label = f"[COLOR {color}]{list_label}[/COLOR]"
                    list_item = xbmcgui.ListItem(list_label)
                    list_item.setProperty('isFolder', 'false')
                    list_item.setProperty('list_id', str(item['id']))
                    list_item.setProperty('is_member', str(item['is_member']))
                    self.list_control.addItem(list_item)
                    self.list_data.append({'name': item['name'], 'isFolder': False, 'id': item['id'], 'indent': indent + 1, 'color': color if self.is_playable else None})

    def add_new_items(self, parent_folder, indent):
        current_depth = 0
        temp_parent_id = parent_folder['id']
        while temp_parent_id is not None:
            current_depth += 1
            folder = DatabaseManager(Config().db_path).fetch_folder_by_id(temp_parent_id)
            temp_parent_id = folder['parent_id'] if folder else None
        if current_depth < Config().max_folder_depth:
            new_folder_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<New Folder>")
            new_folder_item.setProperty('isFolder', 'true')
            new_folder_item.setProperty('isSpecial', 'true')
            new_folder_item.setProperty('action', 'new_folder')
            new_folder_item.setProperty('parent_id', str(parent_folder['id']))
            self.list_control.addItem(new_folder_item)
            self.list_data.append({'name': '<New Folder>', 'isFolder': True, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': 'new_folder'})
        new_list_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<New List>")
        new_list_item.setProperty('isFolder', 'false')
        new_list_item.setProperty('isSpecial', 'true')
        new_list_item.setProperty('action', 'new_list')
        new_list_item.setProperty('parent_id', str(parent_folder['id']))
        self.list_control.addItem(new_list_item)
        self.list_data.append({'name': '<New List>', 'isFolder': False, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': 'new_list'})
        if self.moving_list_id:
            paste_list_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<Paste List Here : {self.moving_list_name}>")
            paste_list_item.setProperty('isFolder', 'false')
            paste_list_item.setProperty('isSpecial', 'true')
            paste_list_item.setProperty('action', f"paste_list_here:{self.moving_list_id}")
            paste_list_item.setProperty('parent_id', str(parent_folder['id']))
            self.list_control.addItem(paste_list_item)
            self.list_data.append({'name': f'<Paste List Here : {self.moving_list_name}>', 'isFolder': False, 'isSpecial': True, 'id': parent_folder['id'], 'indent': indent, 'action': f"paste_list_here:{self.moving_list_id}"})
        if self.moving_folder_id:
            paste_folder_item = xbmcgui.ListItem(f"{' ' * (indent * self.INDENTATION_MULTIPLIER)}<Paste Folder Here : {self.moving_folder_name}>")
            paste_folder_item.setProperty('isFolder', 'true')
            paste_folder_item.setProperty('isSpecial', 'true')
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

    def on_options_click(self):
        selected_item = self.list_control.getSelectedItem()
        if not selected_item:
            return

        selected_item_label = self.strip_color_tags(selected_item.getLabel())
        is_folder = selected_item.getProperty('isFolder') == 'true'
        try:
            selected_item_id = int(selected_item.getProperty('folder_id') if is_folder else selected_item.getProperty('list_id'))
            self.display_item_options(selected_item_label, selected_item_id, is_folder)
        except ValueError:
            pass

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
        is_member = list_data.get('color') == 'green'
        db_manager = DatabaseManager(Config().db_path)
        if is_member:
            item_id = db_manager.get_item_id_by_title_and_list(list_data['id'], self.item_info['title'])
            if item_id:
                db_manager.delete_data('list_items', f'id={item_id}')
                xbmcgui.Dialog().notification("LibraryGenie", "Media removed from list", xbmcgui.NOTIFICATION_INFO, 5000)
        else:
            fields_keys = [field.split()[0] for field in Config.FIELDS]
            data = {field: self.item_info.get(field) for field in fields_keys}
            data['list_id'] = list_data['id']
            if 'cast' in data and isinstance(data['cast'], list):
                data['cast'] = json.dumps(data['cast'])
            db_manager.insert_data('list_items', data)
            xbmcgui.Dialog().notification("LibraryGenie", "Media added to list", xbmcgui.NOTIFICATION_INFO, 5000)
        self.populate_list()
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
        from resources.lib.api_client import ApiClient
        api_client = ApiClient()
        api_client.upload_imdb_list()

    def export_imdb_list(self, list_id):
        from resources.lib.api_client import ApiClient
        api_client = ApiClient()
        api_client.export_imdb_list(list_id)

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
        try:
            # For root level moves, only need to check depth
            if target_folder_id is None:
                subtree_depth = db_manager._get_subtree_depth(folder_id)
                if subtree_depth >= Config().max_folder_depth:
                    raise ValueError(f"Moving folder would exceed maximum depth of {Config().max_folder_depth}")
            else:
                # Check for circular reference
                current_parent = target_folder_id
                while current_parent is not None:
                    if current_parent == folder_id:
                        xbmcgui.Dialog().notification("LibraryGenie", "Cannot move folder: Would create circular reference", xbmcgui.NOTIFICATION_ERROR, 5000)
                        return
                    folder = db_manager.fetch_folder_by_id(current_parent)
                    if folder is None:
                        break
                    current_parent = folder.get('parent_id', None)

            # Get depth of the moving subtree
            subtree_depth = db_manager._get_subtree_depth(folder_id)

            # Get target location depth
            target_depth = 0 if target_folder_id is None else db_manager.get_folder_depth(target_folder_id)

            # Calculate total depth after move
            total_depth = target_depth + subtree_depth + 1

            if total_depth > Config().max_folder_depth:
                raise ValueError(f"Moving folder would exceed maximum depth of {Config().max_folder_depth}")

            db_manager.update_folder_parent(folder_id, target_folder_id)
            xbmcgui.Dialog().notification("LibraryGenie", "Folder moved to new location", xbmcgui.NOTIFICATION_INFO, 5000)
            self.moving_folder_id = None
            self.moving_folder_name = None
            utils.log(f"Pasting folder. FolderID={folder_id}, TargetFolderID={target_folder_id}", "DEBUG")
            self.populate_list()
        except ValueError as e:
            xbmcgui.Dialog().notification("LibraryGenie", str(e), xbmcgui.NOTIFICATION_ERROR, 5000)
            self.moving_folder_id = None
            self.moving_folder_name = None
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
            if self.item_info:
                utils.log(f"Adding media to new list: {self.item_info}", "DEBUG")
                data = {}
                fields_keys = [field.split()[0] for field in Config.FIELDS]
                utils.log(f"Field keys: {fields_keys}", "DEBUG")
                for field in fields_keys:
                    if field in self.item_info and self.item_info[field]:
                        data[field] = self.item_info[field]
                if data:
                    utils.log("Processing data before insert...", "DEBUG")
                    data['list_id'] = list_id
                    utils.log(f"Added list_id: {list_id} to data", "DEBUG")
                    if 'cast' in data and isinstance(data['cast'], list):
                        utils.log("Converting cast to JSON string", "DEBUG")
                        data['cast'] = json.dumps(data['cast'])
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
        xbmcgui.Dialog().notification("LibraryGenie", "List moved to new location", xbmcgui.NOTIFICATION_INFO, 5000)
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
                # Set lateral navigation within list
                self.list_control.controlLeft(self.list_control)
                self.list_control.controlRight(self.list_control)
                
                # Connect list with collapse all button
                self.list_control.controlDown(self.collapse_all_button)
                self.collapse_all_button.controlUp(self.list_control)
                
                # Connect collapse all with exit button
                self.collapse_all_button.controlRight(self.exit_button)
                self.collapse_all_button.controlLeft(self.collapse_all_button)
                self.exit_button.controlLeft(self.collapse_all_button)
                # Exit button navigation - only up and left
                self.exit_button.controlUp(self.list_control)
                self.exit_button.controlRight(self.exit_button)  # Stay on self when right is pressed
                self.exit_button.controlDown(self.exit_button)  # Stay on self when down is pressed
                
                self.list_control.setEnabled(True)
                self.setFocus(self.list_control)
        except Exception as e:
            utils.log(f"Error setting navigation: {str(e)}", "ERROR")
            
    def collapse_all_folders(self):
        """Collapse all folders except root"""
        self.folder_expanded_states = {0: True}  # Keep root expanded, collapse all others
        self.populate_list()

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