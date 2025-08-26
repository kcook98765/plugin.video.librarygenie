
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Addon Controller
Entry point for plugin operations and routing
"""

import sys
from typing import Dict, Any, Optional

import xbmcaddon
import xbmcgui
import xbmcplugin

from .utils.logger import get_logger
from .data import get_query_manager
from .ui.menu_builder import MenuBuilder
from .ui.search_handler import SearchHandler
from .ui.listitem_renderer import ListItemRenderer


class AddonController:
    """Main controller for LibraryGenie addon operations"""
    
    def __init__(self, addon_handle: int, addon_url: str, addon_params: Dict[str, Any]):
        self.addon = xbmcaddon.Addon()
        self.handle = addon_handle
        self.url = addon_url
        self.params = addon_params
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.query_manager = get_query_manager()
        self.menu_builder = MenuBuilder()
        self.search_handler = SearchHandler()
        self.listitem_renderer = ListItemRenderer()
    
    def route(self):
        """Route requests to appropriate handlers"""
        try:
            mode = self.params.get('mode', '')
            
            if mode == '':
                self._show_main_menu()
            elif mode == 'lists':
                self._show_lists()
            elif mode == 'view_list':
                self._view_list()
            elif mode == 'search':
                self._handle_search()
            elif mode == 'folders':
                self._show_folders()
            else:
                self.logger.warning(f"Unknown mode: {mode}")
                self._show_main_menu()
                
        except Exception as e:
            self.logger.error(f"Error in route handling: {e}")
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                "An error occurred. Check logs for details.",
                xbmcgui.NOTIFICATION_ERROR
            )
    
    def _show_main_menu(self):
        """Display the main menu"""
        try:
            items = [
                ('Lists', 'plugin://plugin.video.librarygenie/?mode=lists'),
                ('Search', 'plugin://plugin.video.librarygenie/?mode=search'),
                ('Folders', 'plugin://plugin.video.librarygenie/?mode=folders'),
            ]
            
            for title, url in items:
                listitem = xbmcgui.ListItem(title)
                listitem.setInfo('video', {'title': title})
                xbmcplugin.addDirectoryItem(self.handle, url, listitem, True)
            
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self.logger.error(f"Error showing main menu: {e}")
    
    def _show_lists(self):
        """Display all lists"""
        try:
            lists = self.query_manager.get_all_lists()
            
            for list_data in lists:
                title = list_data['name']
                url = f"plugin://plugin.video.librarygenie/?mode=view_list&list_id={list_data['id']}"
                
                listitem = xbmcgui.ListItem(title)
                listitem.setInfo('video', {'title': title})
                xbmcplugin.addDirectoryItem(self.handle, url, listitem, True)
            
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self.logger.error(f"Error showing lists: {e}")
    
    def _view_list(self):
        """Display items in a specific list"""
        try:
            list_id = self.params.get('list_id')
            if not list_id:
                return
            
            items = self.query_manager.get_list_items(int(list_id))
            
            for item in items:
                listitem = self.listitem_renderer.create_listitem(item)
                xbmcplugin.addDirectoryItem(
                    self.handle,
                    item.get('play', ''),
                    listitem,
                    False
                )
            
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self.logger.error(f"Error viewing list: {e}")
    
    def _handle_search(self):
        """Handle search functionality"""
        try:
            query = self.params.get('query')
            
            if not query:
                # Show search input dialog
                keyboard = xbmcgui.Dialog().input(
                    'Search Movies',
                    type=xbmcgui.INPUT_ALPHANUM
                )
                if keyboard:
                    query = keyboard
                else:
                    return
            
            results = self.search_handler.search(query)
            
            for item in results:
                listitem = self.listitem_renderer.create_listitem(item)
                xbmcplugin.addDirectoryItem(
                    self.handle,
                    item.get('play', ''),
                    listitem,
                    False
                )
            
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self.logger.error(f"Error in search: {e}")
    
    def _show_folders(self):
        """Display folder structure"""
        try:
            folders = self.query_manager.get_all_folders()
            
            for folder in folders:
                title = folder['name']
                url = f"plugin://plugin.video.librarygenie/?mode=folder&folder_id={folder['id']}"
                
                listitem = xbmcgui.ListItem(title)
                listitem.setInfo('video', {'title': title})
                xbmcplugin.addDirectoryItem(self.handle, url, listitem, True)
            
            xbmcplugin.endOfDirectory(self.handle)
            
        except Exception as e:
            self.logger.error(f"Error showing folders: {e}")
