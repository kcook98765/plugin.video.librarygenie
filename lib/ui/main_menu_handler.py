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
            menu_builder = MenuBuilder(context)

            # Add breadcrumb if available
            if context.breadcrumb_path:
                context.logger.info(f"MAIN MENU: Adding breadcrumb: '{context.breadcrumb_path}'")
                menu_builder._add_breadcrumb_item(context.breadcrumb_path, context.addon_handle, context.base_url)

            # Build hierarchical menu
            context.logger.info("MAIN MENU: Building hierarchical menu")
            menu_builder.build_hierarchical_menu(lists, folders)

            context.logger.info("MAIN MENU: Successfully completed main menu display")
            return True

        except Exception as e:
            context.logger.error(f"MAIN MENU: Error showing main menu: {e}")
            import traceback
            context.logger.error(f"MAIN MENU: Traceback: {traceback.format_exc()}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False