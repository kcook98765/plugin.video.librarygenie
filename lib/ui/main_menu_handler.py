#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Menu Handler
Handles the main menu display and navigation
"""

from typing import Optional
from lib.ui.menu_builder import MenuBuilder
from lib.ui.plugin_context import PluginContext
from lib.utils.kodi_log import get_kodi_logger
from lib.utils.kodi_version import get_kodi_major_version
import xbmcplugin
import xbmcaddon


class MainMenuHandler:
    """Handles main menu display"""

    def __init__(self):
        pass

    def show_main_menu(self, context: PluginContext) -> bool:
        """Show main menu with Lists and Bookmarks options"""
        try:
            kodi_major = get_kodi_major_version()
            context.logger.info("MAIN MENU: Starting main menu display on Kodi v%s", kodi_major)

            # Check if a startup folder is configured
            from lib.config.config_manager import get_config
            config = get_config()
            startup_folder_id = config.get("startup_folder_id", "").strip()
            
            if startup_folder_id:
                context.logger.info("MAIN MENU: Startup folder configured (id: %s), checking if valid", startup_folder_id)
                
                # Verify the folder still exists
                try:
                    folder_info = context.query_manager.get_folder_by_id(startup_folder_id)
                    if folder_info:
                        context.logger.info("MAIN MENU: Redirecting to startup folder: %s", folder_info.get('name'))
                        # Set flag in params so show_folder knows to add "Back to Main Menu" item
                        context.params['is_startup_folder'] = 'true'
                        # Route to show_folder
                        from lib.ui.lists_handler import ListsHandler
                        lists_handler = ListsHandler(context)
                        response = lists_handler.show_folder(context, startup_folder_id)
                        return response.success
                    else:
                        context.logger.warning("MAIN MENU: Startup folder id=%s not found, showing normal menu", startup_folder_id)
                except Exception as e:
                    context.logger.error("MAIN MENU: Error checking startup folder: %s, showing normal menu", e)

            # Build main menu items
            menu_builder = MenuBuilder()
            
            # Add Lists menu item
            menu_builder.add_menu_item(
                label="My Lists",
                action="show_lists_menu",
                icon="DefaultPlaylist.png",
                description="Manage and view your custom media lists and bookmarks"
            )
            
            # Add Search menu item
            menu_builder.add_menu_item(
                label="Search",
                action="prompt_and_search",
                icon="DefaultAddonsSearch.png",
                description="Search your media library"
            )
            
            # Build and display menu
            list_items = menu_builder.build()
            
            # Add items to directory
            for url, listitem, is_folder in list_items:
                xbmcplugin.addDirectoryItem(
                    handle=context.addon_handle,
                    url=url,
                    listitem=listitem,
                    isFolder=is_folder
                )
            
            # Set content type and finish directory
            xbmcplugin.setContent(context.addon_handle, 'files')
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True, cacheToDisc=False)
            return True

        except Exception as e:
            context.logger.error("MAIN MENU: Error showing main menu: %s", e)
            import traceback
            context.logger.error("MAIN MENU: Traceback: %s", traceback.format_exc())
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False