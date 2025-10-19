#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Create Intersection Panel
Custom dialog for creating intersection lists from multiple source lists
"""

import xbmcgui
import xbmc
from typing import Dict, Set, List, Any, Optional
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager

try:
    import xbmcaddon
    ADDON = xbmcaddon.Addon('plugin.video.librarygenie')
except:
    ADDON = None


class CreateIntersectionPanel(xbmcgui.WindowXMLDialog):
    """Custom dialog for creating intersection lists"""
    
    XML_FILENAME = 'DialogLibraryGenieCreateIntersection.xml'
    XML_PATH = 'Default'
    
    def __init__(self, *args, **kwargs):
        self._folder_id = kwargs.pop('folder_id', None)
        self._edit_mode = kwargs.pop('edit_mode', False)
        self._list_id = kwargs.pop('list_id', None)
        self._initial_name = kwargs.pop('initial_name', '')
        self._initial_source_list_ids = kwargs.pop('initial_source_list_ids', [])
        
        super(CreateIntersectionPanel, self).__init__(*args, **kwargs)
        
        self.logger = get_kodi_logger('lib.gui.create_intersection_panel')
        self._result = None
        self._selected_lists: Set[str] = set()
        self._available_lists: List[Dict[str, Any]] = []
        self._list_map: Dict[int, str] = {}
        
        self.query_manager = get_query_manager()
        
    def onInit(self):
        """Initialize the dialog"""
        try:
            self.logger.debug("Initializing Create Intersection Panel for folder_id=%s, edit_mode=%s", 
                            self._folder_id, self._edit_mode)
            
            if not self.query_manager.initialize():
                self.logger.error("Failed to initialize query manager")
                xbmcgui.Dialog().notification("Error", "Database error", xbmcgui.NOTIFICATION_ERROR)
                self.close()
                return
            
            self._load_available_lists()
            self._wire_controls()
            
            if self._edit_mode and self._initial_name:
                self.name_input.setText(self._initial_name)
            
            if self._edit_mode and self._initial_source_list_ids:
                for source_id in self._initial_source_list_ids:
                    self._selected_lists.add(str(source_id))
            
            self._populate_list()
            self._update_counter()
            
            self.setFocusId(100)
            
        except Exception as e:
            self.logger.error("Error initializing Create Intersection Panel: %s", e)
            import traceback
            self.logger.error("Traceback: %s", traceback.format_exc())
    
    def _wire_controls(self):
        """Wire up all controls"""
        try:
            self.name_input = self.getControl(100)
            self.list_container = self.getControl(200)
            self.counter_label = self.getControl(300)
            self.btn_create = self.getControl(400)
            self.btn_select_all = self.getControl(401)
            self.btn_deselect_all = self.getControl(402)
            self.btn_cancel = self.getControl(403)
        except Exception as e:
            self.logger.error("Error wiring controls: %s", e)
    
    def _load_available_lists(self):
        """Load all available lists (excluding intersection lists and Search History)"""
        try:
            all_lists = self.query_manager.get_all_lists_with_folders()
            
            self._available_lists = []
            for lst in all_lists:
                list_id = int(lst['id'])
                folder_name = lst.get('folder_name', '')
                
                if self.query_manager.is_intersection_list(list_id):
                    self.logger.debug("Filtering out intersection list: %s", lst['name'])
                    continue
                
                if folder_name == "Search History":
                    self.logger.debug("Filtering out Search History list: %s", lst['name'])
                    continue
                
                item_count = self.query_manager.get_list_item_count(list_id)
                lst['item_count'] = item_count
                self._available_lists.append(lst)
            
            self.logger.debug("Loaded %s available lists for intersection", len(self._available_lists))
            
        except Exception as e:
            self.logger.error("Error loading available lists: %s", e)
            self._available_lists = []
    
    def _populate_list(self):
        """Populate the list container with available lists"""
        try:
            self.list_container.reset()
            
            for idx, lst in enumerate(self._available_lists):
                list_item = self._create_list_item(lst)
                self.list_container.addItem(list_item)
                
                list_id = str(lst.get('id', ''))
                self._list_map[idx] = list_id
                
            self.logger.debug("Populated list container with %s lists", len(self._available_lists))
            
        except Exception as e:
            self.logger.error("Error populating list: %s", e)
    
    def _create_list_item(self, lst: Dict[str, Any]) -> xbmcgui.ListItem:
        """Create a ListItem for display"""
        try:
            name = lst.get('name', 'Unknown')
            item_count = lst.get('item_count', 0)
            list_id = str(lst.get('id', ''))
            
            list_item = xbmcgui.ListItem(label=name, offscreen=True)
            
            list_item.setProperty('item_count', str(item_count))
            list_item.setProperty('selected', '1' if list_id in self._selected_lists else '0')
            
            return list_item
            
        except Exception as e:
            self.logger.error("Error creating list item: %s", e)
            return xbmcgui.ListItem(label="Error", offscreen=True)
    
    def _update_counter(self):
        """Update the selection counter label"""
        try:
            count = len(self._selected_lists)
            if count == 0:
                label_text = "0 lists selected"
            elif count == 1:
                label_text = "1 list selected"
            else:
                label_text = f"{count} lists selected"
            
            self.counter_label.setLabel(label_text)
            
        except Exception as e:
            self.logger.error("Error updating counter: %s", e)
    
    def _toggle_item_selection(self, position: int):
        """Toggle selection state of a list"""
        try:
            if position < 0 or position >= len(self._available_lists):
                return
            
            list_id = self._list_map.get(position)
            if not list_id:
                return
            
            if list_id in self._selected_lists:
                self._selected_lists.remove(list_id)
                self.logger.debug("Deselected list at position %s (id=%s)", position, list_id)
            else:
                self._selected_lists.add(list_id)
                self.logger.debug("Selected list at position %s (id=%s)", position, list_id)
            
            self._refresh_list_display()
            self._update_counter()
            
        except Exception as e:
            self.logger.error("Error toggling item selection: %s", e)
    
    def _refresh_list_display(self):
        """Rebuild list container items with updated checkbox states"""
        try:
            for idx in range(len(self._available_lists)):
                list_item = self.list_container.getListItem(idx)
                list_id = self._list_map.get(idx)
                
                if list_item and list_id:
                    list_item.setProperty('selected', '1' if list_id in self._selected_lists else '0')
            
        except Exception as e:
            self.logger.error("Error refreshing list display: %s", e)
    
    def _select_all(self):
        """Select all lists"""
        try:
            for idx in range(len(self._available_lists)):
                list_id = self._list_map.get(idx)
                if list_id:
                    self._selected_lists.add(list_id)
            
            self._refresh_list_display()
            self._update_counter()
            self.logger.debug("Selected all %s lists", len(self._available_lists))
            
        except Exception as e:
            self.logger.error("Error selecting all lists: %s", e)
    
    def _deselect_all(self):
        """Deselect all lists"""
        try:
            self._selected_lists.clear()
            self._refresh_list_display()
            self._update_counter()
            self.logger.debug("Deselected all lists")
            
        except Exception as e:
            self.logger.error("Error deselecting all lists: %s", e)
    
    def _create_intersection(self):
        """Create or update the intersection list"""
        try:
            name = self.name_input.getText().strip()
            
            if not name:
                xbmcgui.Dialog().notification(
                    "Error",
                    "Please enter a name for the intersection list",
                    xbmcgui.NOTIFICATION_WARNING
                )
                return
            
            if len(self._selected_lists) < 2:
                xbmcgui.Dialog().notification(
                    "Error",
                    "Please select at least 2 lists to create an intersection",
                    xbmcgui.NOTIFICATION_WARNING
                )
                return
            
            source_list_ids = [int(list_id) for list_id in self._selected_lists]
            
            if self._edit_mode and self._list_id:
                self.logger.debug("Updating intersection list %d with new source_lists=%s", 
                                self._list_id, source_list_ids)
                
                success = self.query_manager.update_intersection_list_sources(
                    list_id=self._list_id,
                    new_source_list_ids=source_list_ids
                )
                
                if success:
                    if name != self._initial_name:
                        self.query_manager.rename_list(self._list_id, name)
                    
                    self.logger.info("Successfully updated intersection list with id=%s", self._list_id)
                    xbmcgui.Dialog().notification(
                        "Success",
                        f"Intersection list '{name}' updated successfully",
                        xbmcgui.NOTIFICATION_INFO
                    )
                    self._result = True
                    self.close()
                else:
                    self.logger.error("Failed to update intersection list")
                    xbmcgui.Dialog().notification(
                        "Error",
                        "Failed to update intersection list",
                        xbmcgui.NOTIFICATION_ERROR
                    )
            else:
                self.logger.debug("Creating intersection list: name=%s, folder_id=%s, source_lists=%s", 
                                name, self._folder_id, source_list_ids)
                
                new_list_id = self.query_manager.create_intersection_list(
                    name=name,
                    folder_id=self._folder_id,
                    source_list_ids=source_list_ids
                )
                
                if new_list_id:
                    self.logger.info("Successfully created intersection list with id=%s", new_list_id)
                    xbmcgui.Dialog().notification(
                        "Success",
                        f"Intersection list '{name}' created successfully",
                        xbmcgui.NOTIFICATION_INFO
                    )
                    self._result = True
                    self.close()
                else:
                    self.logger.error("Failed to create intersection list")
                    xbmcgui.Dialog().notification(
                        "Error",
                        "Failed to create intersection list",
                        xbmcgui.NOTIFICATION_ERROR
                    )
            
        except Exception as e:
            self.logger.error("Error creating intersection: %s", e)
            import traceback
            self.logger.error("Traceback: %s", traceback.format_exc())
            xbmcgui.Dialog().notification(
                "Error",
                "Failed to create intersection list",
                xbmcgui.NOTIFICATION_ERROR
            )
    
    def onClick(self, controlId):
        """Handle click events"""
        try:
            self.logger.debug("onClick: controlId=%s", controlId)
            
            if controlId == 200:
                position = self.list_container.getSelectedPosition()
                self._toggle_item_selection(position)
                
            elif controlId == 400:
                self._create_intersection()
                
            elif controlId == 401:
                self._select_all()
                
            elif controlId == 402:
                self._deselect_all()
                
            elif controlId == 403:
                self.close()
                
        except Exception as e:
            self.logger.error("Error handling click: %s", e)
    
    def onAction(self, action):
        """Handle action events"""
        try:
            action_id = action.getId()
            
            if action_id in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
                self.logger.debug("Close action received")
                self.close()
                
        except Exception as e:
            self.logger.error("Error handling action: %s", e)
    
    def get_result(self) -> Optional[bool]:
        """Get the dialog result"""
        return self._result
    
    def close(self):
        """Close the dialog"""
        super(CreateIntersectionPanel, self).close()


def show_create_intersection_panel(folder_id: Optional[int] = None, 
                                   edit_mode: bool = False,
                                   list_id: Optional[int] = None,
                                   initial_name: str = '',
                                   initial_source_list_ids: Optional[List[int]] = None) -> Optional[bool]:
    """
    Show the create/edit intersection panel dialog
    
    Args:
        folder_id: Target folder ID for the new intersection list (None for root)
        edit_mode: If True, editing existing intersection list
        list_id: List ID when editing
        initial_name: Initial name when editing
        initial_source_list_ids: Initial source list IDs when editing
        
    Returns:
        True if intersection was created/updated, None otherwise
    """
    try:
        logger = get_kodi_logger('lib.gui.create_intersection_panel')
        logger.debug("Opening create intersection panel for folder_id=%s, edit_mode=%s", 
                    folder_id, edit_mode)
        
        dialog = CreateIntersectionPanel(
            CreateIntersectionPanel.XML_FILENAME,
            ADDON.getAddonInfo('path') if ADDON else '',
            CreateIntersectionPanel.XML_PATH,
            folder_id=folder_id,
            edit_mode=edit_mode,
            list_id=list_id,
            initial_name=initial_name,
            initial_source_list_ids=initial_source_list_ids or []
        )
        
        dialog.doModal()
        result = dialog.get_result()
        del dialog
        
        logger.debug("Create intersection panel closed, result: %s", result)
        return result
        
    except Exception as e:
        logger = get_kodi_logger('lib.gui.create_intersection_panel')
        logger.error("Error showing create intersection panel: %s", e)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        return None
