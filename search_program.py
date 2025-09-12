
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Program Entry Point
Provides program addon functionality for Search and tools access
"""

import sys
import xbmcgui
import xbmcaddon

from lib.ui.plugin_context import PluginContext
from lib.ui.handler_factory import get_handler_factory
from lib.utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('search_program')

def show_program_menu():
    """Show program menu with Search and tools options"""
    try:
        addon = xbmcaddon.Addon()
        
        # Create menu options
        menu_items = [
            "Search Library",
            "Search History", 
            "Kodi Favorites",
            "Import/Export Tools",
            "Settings"
        ]
        
        # Show selection dialog
        dialog = xbmcgui.Dialog()
        selected = dialog.select("LibraryGenie Tools", menu_items)
        
        if selected < 0:
            return  # User cancelled
            
        # Handle selection
        if selected == 0:  # Search Library
            # Create context for search
            sys.argv = [f"plugin://{addon.getAddonInfo('id')}/", "-1", "?action=search"]
            context = PluginContext()
            factory = get_handler_factory()
            factory.context = context
            search_handler = factory.get_search_handler()
            search_handler.prompt_and_search(context)
            
        elif selected == 1:  # Search History
            # Navigate to search history
            import xbmc
            xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://{addon.getAddonInfo("id")}/?action=show_search_history",return)')
            
        elif selected == 2:  # Kodi Favorites
            # Navigate to favorites
            import xbmc
            xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://{addon.getAddonInfo("id")}/?action=kodi_favorites",return)')
            
        elif selected == 3:  # Import/Export Tools
            # Navigate to tools
            import xbmc
            xbmc.executebuiltin(f'ActivateWindow(10025,"plugin://{addon.getAddonInfo("id")}/?action=show_list_tools&list_type=global",return)')
            
        elif selected == 4:  # Settings
            addon.openSettings()
            
    except Exception as e:
        logger.error("Error in program menu: %s", e)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Error accessing tools",
            xbmcgui.NOTIFICATION_ERROR
        )

if __name__ == '__main__':
    show_program_menu()
