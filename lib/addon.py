#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Addon Controller
Entry point for plugin operations and routing
"""

from __future__ import annotations

import sys
import xbmcgui
import xbmcaddon
import xbmcplugin
from typing import Dict, Any
from lib.utils.kodi_log import get_kodi_logger
from lib.config import get_config


class AddonController:
    """Main controller for LibraryGenie addon operations"""

    def __init__(self, addon_handle: int, addon_url: str, addon_params: Dict[str, Any]):
        self.addon = xbmcaddon.Addon()
        self.handle = addon_handle
        self.base_url = addon_url
        self.params = addon_params
        self.logger = get_kodi_logger('lib.addon')
        self.cfg = get_config()

    def route(self):
        """Route requests to appropriate handlers"""
        try:
            mode = self.params.get('mode', 'home')

            self.logger.debug("Routing mode: %s", mode)

            if mode == 'search':
                self._handle_search()
            elif mode == 'authorize':
                self._handle_authorize()
            elif mode == 'logout':
                self._handle_logout()
            else:
                # Default to home/main menu
                self._show_main_menu()

        except Exception as e:
            self.logger.error("Error in route handling: %s", e)
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                "An error occurred. Check logs for details.",
                xbmcgui.NOTIFICATION_ERROR
            )

    def _set_listitem_title(self, list_item: xbmcgui.ListItem, title: str):
        """Set title metadata in version-compatible way to avoid v21 setInfo() deprecation warnings"""
        from lib.utils.kodi_version import get_kodi_major_version
        kodi_major = get_kodi_major_version()
        if kodi_major >= 21:
            # v21+: Use InfoTagVideo ONLY - completely avoid setInfo()
            try:
                video_info_tag = list_item.getVideoInfoTag()
                video_info_tag.setTitle(title)
            except Exception as e:
                self.logger.error("InfoTagVideo failed for title: %s", e)
        else:
            # v19/v20: Use setInfo() as fallback
            list_item.setInfo('video', {'title': title})

    def _show_main_menu(self):
        """Display the main menu"""
        try:
            self.logger.info("Showing main menu")

            items = []

            # Always show search
            items.append(("Search", f"{self.base_url}?mode=search", True))

            # Show authorization status dependent items
            if self._is_authorized():
                items.append(("Sign out", f"{self.base_url}?mode=logout", False))
            else:
                items.append(("Authorize device", f"{self.base_url}?mode=authorize", False))

            # Add items to directory
            for label, url, is_folder in items:
                listitem = xbmcgui.ListItem(label, offscreen=True)
                # Use version-aware metadata setting to avoid v21 deprecation warnings
                self._set_listitem_title(listitem, label)
                xbmcplugin.addDirectoryItem(self.handle, url, listitem, is_folder)

            xbmcplugin.endOfDirectory(self.handle)

        except Exception as e:
            self.logger.error("Error showing main menu: %s", e)

    def _handle_search(self):
        """Handle search functionality"""
        try:
            self.logger.info("Handling search - starting search flow")
            self.logger.debug("Search params: %s", self.params)

            # Import search UI handler (lazy import to avoid circular dependencies)
            from lib.ui.search_handler import SearchHandler
            self.logger.debug("SearchHandler imported successfully")

            search_handler = SearchHandler(self.handle)
            self.logger.debug("SearchHandler instance created")

            # Show search dialog and handle results
            self.logger.info("Calling search_handler.prompt_and_show()")
            search_handler.prompt_and_show()
            self.logger.info("Search handler completed")

        except Exception as e:
            import traceback
            self.logger.error("Error in search handling: %s", e)
            self.logger.error("SearchHandler error traceback: %s", traceback.format_exc())

            # Show error to user
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                f"Search error: {str(e)}",
                xbmcgui.NOTIFICATION_ERROR
            )
            self._show_main_menu()

    def _handle_authorize(self):
        """Handle device authorization"""
        try:
            self.logger.info("Handling authorization")

            # Import and run authorization flow (lazy import)
            from lib.auth.device_code import run_authorize_flow
            run_authorize_flow()

            # Return to main menu after authorization attempt
            self._show_main_menu()

        except ImportError:
            self.logger.warning("Authorization module not available")
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                "Authorization not implemented yet",
                xbmcgui.NOTIFICATION_INFO
            )
            self._show_main_menu()
        except Exception as e:
            self.logger.error("Error in authorization: %s", e)
            self._show_main_menu()

    def _handle_logout(self):
        """Handle logout/sign out"""
        try:
            self.logger.info("Handling logout")

            # Import and clear auth tokens (lazy import)
            from lib.auth.state import clear_tokens

            success = clear_tokens()

            if success:
                xbmcgui.Dialog().notification(
                    self.addon.getAddonInfo('name'),
                    "Signed out successfully",
                    xbmcgui.NOTIFICATION_INFO
                )
            else:
                xbmcgui.Dialog().notification(
                    self.addon.getAddonInfo('name'),
                    "Error during sign out",
                    xbmcgui.NOTIFICATION_WARNING
                )

            # Return to main menu
            self._show_main_menu()

        except ImportError:
            self.logger.warning("Auth state module not available")
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                "Logout not implemented yet",
                xbmcgui.NOTIFICATION_INFO
            )
            self._show_main_menu()
        except Exception as e:
            self.logger.error("Error in logout: %s", e)
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo('name'),
                "Error during sign out",
                xbmcgui.NOTIFICATION_ERROR
            )
            self._show_main_menu()

    def _is_authorized(self) -> bool:
        """Check if user is authorized"""
        try:
            # Lazy import to avoid circular dependencies
            from lib.auth.state import is_authorized
            return is_authorized()
        except ImportError:
            # Auth module not available, assume not authorized
            return False
        except Exception as e:
            self.logger.error("Error checking authorization status: %s", e)
            return False


def main():
    """Main addon entry point"""
    try:
        logger = get_kodi_logger('lib.addon.main')

        # Diagnose logging configuration
        _diagnose_logging(logger)

        logger.info("LibraryGenie addon starting...")

        # Parse addon parameters
        if len(sys.argv) >= 3:
            addon_handle = int(sys.argv[1])
            addon_url = sys.argv[0]
            params_string = sys.argv[2][1:]  # Remove leading '?'
            
            # Parse parameters
            params = {}
            if params_string:
                for param in params_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = value
                    else:
                        params[param] = ''
        else:
            addon_handle = 0
            addon_url = ""
            params = {}

        logger.debug("Addon parameters: handle=%s, url=%s, params=%s", addon_handle, addon_url, params)

        # Initialize controller and route
        controller = AddonController(addon_handle, addon_url, params)
        controller.route()

    except Exception as e:
        logger = get_kodi_logger('lib.addon.main')
        logger.error("Fatal error in addon main: %s", e, exc_info=True)
        # Show user-friendly error
        xbmcgui.Dialog().notification("LibraryGenie", "Addon startup failed", xbmcgui.NOTIFICATION_ERROR)


def _diagnose_logging(logger):
    """Diagnose logging configuration to help with troubleshooting"""
    try:
        config = get_config()
        # Using direct Kodi logging - no custom debug settings needed

        logger.info("LOGGING DIAGNOSIS: Using direct Kodi logging throughout")
        logger.info("LOGGING DIAGNOSIS: KodiLogger now routes directly to xbmc.log")
        logger.info("LOGGING DIAGNOSIS: Using direct Kodi logging for maximum efficiency")

        # Test both levels
        logger.debug("LOGGING DIAGNOSIS: This is a DEBUG message")
        logger.info("LOGGING DIAGNOSIS: This is an INFO message")

    except Exception as e:
        logger.error("LOGGING DIAGNOSIS: Failed to diagnose logging: %s", e)