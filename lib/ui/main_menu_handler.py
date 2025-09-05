#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Menu Handler
Handles the main menu display and navigation
"""

from typing import Optional
from .menu_builder import MenuBuilder
from .plugin_context import PluginContext
from ..utils.logger import get_logger
from ..utils.kodi_version import get_kodi_major_version
import xbmcplugin


class MainMenuHandler:
    """Handles main menu display"""

    def __init__(self):
        pass

    def show_main_menu(self, context: PluginContext) -> bool:
        """Show main menu with lists and folders"""
        try:
            kodi_major = get_kodi_major_version()
            context.logger.info(f"MAIN MENU: Starting main menu display on Kodi v{kodi_major}")

            query_manager = context.query_manager
            if not query_manager:
                context.logger.error("Query manager not available")
                return False

            # Get all lists and folders
            context.logger.info("Displaying lists menu")
            lists = query_manager.get_user_lists()
            folders = query_manager.get_all_folders()

            context.logger.info(f"Found {len(lists)} total lists")
            context.logger.info(f"Found {len([l for l in lists if l['name'] != 'Kodi Favorites'])} user lists (excluding Kodi Favorites)")

            # Build menu using MenuBuilder
            context.logger.info("MAIN MENU: Creating MenuBuilder instance")
            menu_builder = MenuBuilder()

            # Build menu items for lists and folders
            menu_items = []
            
            # Add folders first
            for folder in folders:
                menu_items.append({
                    'label': f"📁 {folder['name']}",
                    'action': 'show_folder',
                    'folder_id': folder['id'],
                    'is_folder': True,
                    'icon': 'DefaultFolder.png',
                    'description': f"Folder: {folder['name']}"
                })
            
            # Add lists
            for list_item in lists:
                menu_items.append({
                    'label': f"📋 {list_item['name']}",
                    'action': 'show_list',
                    'list_id': list_item['id'],
                    'is_folder': True,
                    'icon': 'DefaultPlaylist.png',
                    'description': f"List: {list_item['name']}"
                })
            
            # Add tools and options
            menu_items.append({
                'label': f"[COLOR yellow]🔧 Tools & Options[/COLOR]",
                'action': 'show_list_tools',
                'list_type': 'lists_main',
                'is_folder': True,
                'icon': 'DefaultAddonProgram.png',
                'description': 'Access lists tools and options'
            })

            # Use MenuBuilder to create the menu
            context.logger.info("MAIN MENU: Building menu with MenuBuilder")
            menu_builder.build_menu(
                menu_items, 
                context.addon_handle, 
                context.base_url, 
                breadcrumb_path=context.breadcrumb_path
            )

            context.logger.info("MAIN MENU: Successfully completed main menu display")
            return True

        except Exception as e:
            context.logger.error(f"MAIN MENU: Error showing main menu: {e}")
            import traceback
            context.logger.error(f"MAIN MENU: Traceback: {traceback.format_exc()}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False