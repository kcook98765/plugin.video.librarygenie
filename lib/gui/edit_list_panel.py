#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Edit List Panel
Custom dialog for bulk editing list items with selection support
"""

import xbmcgui
import xbmc
from typing import Dict, Set, List, Any, Optional
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager
from lib.ui.localization import L

try:
    import xbmcaddon
    ADDON = xbmcaddon.Addon('plugin.video.librarygenie')
except:
    ADDON = None


class EditListPanel(xbmcgui.WindowXMLDialog):
    """Custom dialog for editing list items with multi-select support"""
    
    XML_FILENAME = 'DialogLibraryGenieEditList.xml'
    XML_PATH = 'Default'
    
    def __init__(self, *args, **kwargs):
        self._list_id = kwargs.pop('list_id', None)
        self._list_name = kwargs.pop('list_name', 'Unknown List')
        
        super(EditListPanel, self).__init__(*args, **kwargs)
        
        self.logger = get_kodi_logger('lib.gui.edit_list_panel')
        self._result = None
        self._selected_items: Set[str] = set()
        self._items: List[Dict[str, Any]] = []
        self._item_map: Dict[int, str] = {}
        self._changes_made = False
        
        self.query_manager = get_query_manager()
        
    def onInit(self):
        """Initialize the dialog"""
        try:
            self.logger.debug("Initializing Edit List Panel for list_id=%s", self._list_id)
            
            self._wire_controls()
            self._load_list_items()
            self._populate_list()
            self._update_header()
            self._update_selection_counter()
            
            self.setFocusId(500)
            
        except Exception as e:
            self.logger.error("Error initializing Edit List Panel: %s", e)
            import traceback
            self.logger.error("Traceback: %s", traceback.format_exc())
    
    def _wire_controls(self):
        """Wire up all controls"""
        try:
            self.list_container = self.getControl(500)
            self.header_label = self.getControl(100)
            self.selection_counter = self.getControl(101)
            self.btn_select_all = self.getControl(610)
            self.btn_delete = self.getControl(620)
            self.btn_move = self.getControl(630)
            self.btn_close = self.getControl(640)
        except Exception as e:
            self.logger.error("Error wiring controls: %s", e)
    
    def _load_list_items(self):
        """Load items from the list"""
        try:
            if not self.query_manager.initialize():
                self.logger.error("Failed to initialize query manager")
                return
            
            self._items = self.query_manager.get_list_items(self._list_id)
            self.logger.debug("Loaded %s items from list %s", len(self._items), self._list_id)
            
        except Exception as e:
            self.logger.error("Error loading list items: %s", e)
            self._items = []
    
    def _populate_list(self):
        """Populate the list container with items"""
        try:
            self.list_container.reset()
            
            for idx, item in enumerate(self._items):
                list_item = self._create_list_item(item)
                self.list_container.addItem(list_item)
                
                item_id = str(item.get('id', ''))
                self._item_map[idx] = item_id
                
            self.logger.debug("Populated list with %s items", len(self._items))
            
        except Exception as e:
            self.logger.error("Error populating list: %s", e)
    
    def _create_list_item(self, item: Dict[str, Any]) -> xbmcgui.ListItem:
        """Create a ListItem for display"""
        try:
            title = item.get('title', 'Unknown')
            year = item.get('year', '')
            plot = item.get('plot', '')
            
            if len(plot) > 150:
                plot = plot[:147] + '...'
            
            list_item = xbmcgui.ListItem(label=title, offscreen=True)
            
            list_item.setProperty('year', str(year) if year else '')
            list_item.setProperty('plot', plot)
            list_item.setProperty('selected', 'false')
            
            info_labels = {
                'title': title,
                'year': year if year else 0,
                'plot': plot,
            }
            list_item.setInfo('video', info_labels)
            
            poster = item.get('poster_url') or item.get('poster')
            if poster:
                list_item.setArt({'poster': poster, 'thumb': poster})
            
            return list_item
            
        except Exception as e:
            self.logger.error("Error creating list item: %s", e)
            return xbmcgui.ListItem(label="Error", offscreen=True)
    
    def _update_header(self):
        """Update the header with list name"""
        try:
            header_text = f"Edit List: {self._list_name}"
            self.header_label.setLabel(header_text)
        except Exception as e:
            self.logger.error("Error updating header: %s", e)
    
    def _update_selection_counter(self):
        """Update the selection counter label"""
        try:
            count = len(self._selected_items)
            if count == 0:
                label_text = "No items selected"
                self.clearProperty('HasSelection')
            elif count == 1:
                label_text = "1 item selected"
                self.setProperty('HasSelection', '1')
            else:
                label_text = f"{count} items selected"
                self.setProperty('HasSelection', '1')
            
            self.selection_counter.setLabel(label_text)
            
        except Exception as e:
            self.logger.error("Error updating selection counter: %s", e)
    
    def _toggle_item_selection(self, position: int):
        """Toggle selection state of an item"""
        try:
            if position < 0 or position >= len(self._items):
                return
            
            item_id = self._item_map.get(position)
            if not item_id:
                return
            
            list_item = self.list_container.getListItem(position)
            
            if item_id in self._selected_items:
                self._selected_items.remove(item_id)
                list_item.setProperty('selected', 'false')
                self.logger.debug("Deselected item at position %s (id=%s)", position, item_id)
            else:
                self._selected_items.add(item_id)
                list_item.setProperty('selected', 'true')
                self.logger.debug("Selected item at position %s (id=%s)", position, item_id)
            
            self._update_selection_counter()
            
        except Exception as e:
            self.logger.error("Error toggling item selection: %s", e)
    
    def _select_all(self):
        """Select all items"""
        try:
            if len(self._selected_items) == len(self._items):
                self._deselect_all()
            else:
                for idx in range(len(self._items)):
                    item_id = self._item_map.get(idx)
                    if item_id:
                        self._selected_items.add(item_id)
                        list_item = self.list_container.getListItem(idx)
                        list_item.setProperty('selected', 'true')
                
                self._update_selection_counter()
                self.logger.debug("Selected all %s items", len(self._items))
                
        except Exception as e:
            self.logger.error("Error selecting all items: %s", e)
    
    def _deselect_all(self):
        """Deselect all items"""
        try:
            for idx in range(len(self._items)):
                list_item = self.list_container.getListItem(idx)
                list_item.setProperty('selected', 'false')
            
            self._selected_items.clear()
            self._update_selection_counter()
            self.logger.debug("Deselected all items")
            
        except Exception as e:
            self.logger.error("Error deselecting all items: %s", e)
    
    def _delete_selected(self):
        """Delete selected items from the list"""
        try:
            if not self._selected_items:
                return
            
            count = len(self._selected_items)
            
            confirm = xbmcgui.Dialog().yesno(
                "Delete Items",
                f"Are you sure you want to remove {count} item(s) from this list?\n\n"
                "This will not delete the items from your library."
            )
            
            if not confirm:
                return
            
            if not self.query_manager.initialize():
                xbmcgui.Dialog().notification("Error", "Database error", xbmcgui.NOTIFICATION_ERROR)
                return
            
            success_count = 0
            for item_id in self._selected_items:
                result = self.query_manager.remove_item_from_list(self._list_id, item_id)
                if result.get('success'):
                    success_count += 1
            
            self.logger.info("Deleted %s/%s items from list", success_count, count)
            
            self._changes_made = True
            self._selected_items.clear()
            
            self._load_list_items()
            self._populate_list()
            self._update_selection_counter()
            
            xbmcgui.Dialog().notification(
                "Success",
                f"Removed {success_count} item(s) from list",
                xbmcgui.NOTIFICATION_INFO
            )
            
        except Exception as e:
            self.logger.error("Error deleting selected items: %s", e)
            xbmcgui.Dialog().notification("Error", "Failed to delete items", xbmcgui.NOTIFICATION_ERROR)
    
    def _move_selected(self):
        """Move selected items to another list"""
        try:
            if not self._selected_items:
                return
            
            if not self.query_manager.initialize():
                xbmcgui.Dialog().notification("Error", "Database error", xbmcgui.NOTIFICATION_ERROR)
                return
            
            all_lists = self.query_manager.get_all_lists_with_folders()
            target_lists = [lst for lst in all_lists if str(lst['id']) != str(self._list_id)]
            
            if not target_lists:
                xbmcgui.Dialog().notification("Error", "No other lists available", xbmcgui.NOTIFICATION_WARNING)
                return
            
            list_options = [lst['name'] for lst in target_lists]
            selected_index = xbmcgui.Dialog().select("Select destination list:", list_options)
            
            if selected_index < 0:
                return
            
            target_list = target_lists[selected_index]
            target_list_id = target_list['id']
            target_list_name = target_list['name']
            
            count = len(self._selected_items)
            
            confirm = xbmcgui.Dialog().yesno(
                "Move Items",
                f"Move {count} item(s) to '{target_list_name}'?\n\n"
                "Items will be removed from this list."
            )
            
            if not confirm:
                return
            
            success_count = 0
            for item_id in self._selected_items:
                add_result = self.query_manager.add_item_to_list(target_list_id, item_id)
                if add_result.get('success'):
                    remove_result = self.query_manager.remove_item_from_list(self._list_id, item_id)
                    if remove_result.get('success'):
                        success_count += 1
            
            self.logger.info("Moved %s/%s items to list '%s'", success_count, count, target_list_name)
            
            self._changes_made = True
            self._selected_items.clear()
            
            self._load_list_items()
            self._populate_list()
            self._update_selection_counter()
            
            xbmcgui.Dialog().notification(
                "Success",
                f"Moved {success_count} item(s) to '{target_list_name}'",
                xbmcgui.NOTIFICATION_INFO
            )
            
        except Exception as e:
            self.logger.error("Error moving selected items: %s", e)
            xbmcgui.Dialog().notification("Error", "Failed to move items", xbmcgui.NOTIFICATION_ERROR)
    
    def onClick(self, controlId):
        """Handle click events"""
        try:
            self.logger.debug("onClick: controlId=%s", controlId)
            
            if controlId == 500:
                position = self.list_container.getSelectedPosition()
                self._toggle_item_selection(position)
                
            elif controlId == 610:
                self._select_all()
                
            elif controlId == 620:
                self._delete_selected()
                
            elif controlId == 630:
                self._move_selected()
                
            elif controlId == 640:
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
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the dialog result"""
        return {
            'changes_made': self._changes_made
        }
    
    def close(self):
        """Close the dialog"""
        super(EditListPanel, self).close()


def show_edit_list_panel(list_id: str, list_name: str = "Unknown List") -> Optional[Dict[str, Any]]:
    """
    Show the edit list panel dialog
    
    Args:
        list_id: ID of the list to edit
        list_name: Name of the list
        
    Returns:
        Dialog result or None
    """
    try:
        logger = get_kodi_logger('lib.gui.edit_list_panel')
        logger.debug("Opening edit list panel for list_id=%s, list_name=%s", list_id, list_name)
        
        dialog = EditListPanel(
            EditListPanel.XML_FILENAME,
            ADDON.getAddonInfo('path') if ADDON else '',
            EditListPanel.XML_PATH,
            list_id=list_id,
            list_name=list_name
        )
        
        dialog.doModal()
        result = dialog.get_result()
        del dialog
        
        logger.debug("Edit list panel closed, result: %s", result)
        return result
        
    except Exception as e:
        logger = get_kodi_logger('lib.gui.edit_list_panel')
        logger.error("Error showing edit list panel: %s", e)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        return None
