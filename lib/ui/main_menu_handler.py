#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Menu Handler
Handles the main menu display and navigation
"""

from typing import Optional
from .menu_builder import MenuBuilder
from .plugin_context import PluginContext
from ..utils.kodi_log import get_kodi_logger
from ..utils.kodi_version import get_kodi_major_version
import xbmcplugin
import xbmcaddon


class MainMenuHandler:
    """Handles main menu display"""

    def __init__(self):
        pass

    def show_main_menu(self, context: PluginContext) -> bool:
        """Show main menu - redirect to Lists as primary interface"""
        try:
            kodi_major = get_kodi_major_version()
            context.logger.info("MAIN MENU: Starting main menu display on Kodi v%s - redirecting to Lists", kodi_major)

            # Redirect main menu directly to Lists interface
            from .handler_factory import get_handler_factory
            factory = get_handler_factory()
            factory.context = context
            lists_handler = factory.get_lists_handler()
            
            # Show Lists menu as the main interface
            response = lists_handler.show_lists_menu(context)
            return response.success if hasattr(response, 'success') else True

        except Exception as e:
            context.logger.error("MAIN MENU: Error showing main menu: %s", e)
            import traceback
            context.logger.error("MAIN MENU: Traceback: %s", traceback.format_exc())
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False