#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any
from .plugin_context import PluginContext
import xbmcgui # Import xbmcgui for dialogs
import xbmc # Import xbmc for executebuiltin
import xbmcplugin # Import xbmcplugin for endOfDirectory
from .response_types import DirectoryResponse, DialogResponse # Import response types
from ..utils.logger import get_logger # Import logger


class Router:
    """Routes actions to appropriate handler functions"""

    def __init__(self):
        self.logger = None  # Will be set from context
        self._handlers: Dict[str, Callable] = {}
        self.favorites_handler = None # Placeholder for favorites handler
        self.tools_handler = None # Placeholder for tools handler

    def register_handler(self, action: str, handler: Callable):
        """Register a handler function for an action"""
        self._handlers[action] = handler

    def register_handlers(self, handlers: Dict[str, Callable]):
        """Register multiple handlers at once"""
        self._handlers.update(handlers)

    def dispatch(self, context: PluginContext) -> bool:
        """
        Dispatch request to appropriate handler based on context
        Returns True if handler was found and called, False otherwise
        """
        if self.logger is None:
            self.logger = get_logger(__name__)

        action = context.get_param('action', '')
        params = context.get_params() # Get all params for modular tools
        self.logger.debug(f"Router dispatching action: '{action}'")

        # Generate breadcrumb context for navigation
        from .breadcrumb_helper import get_breadcrumb_helper
        breadcrumb_helper = get_breadcrumb_helper()
        breadcrumb_path = breadcrumb_helper.get_breadcrumb_for_action(action, params, context.query_manager)

        # Add breadcrumb to context for handlers
        context.breadcrumb_path = breadcrumb_path

        try:
            # Handle special cases first
            if action == "scan_favorites_execute":
                # Assuming favorites_handler is initialized elsewhere or dynamically
                if not self.favorites_handler:
                    from .favorites_handler import FavoritesHandler
                    self.favorites_handler = FavoritesHandler()
                return self.favorites_handler.scan_favorites(context)

            elif action == "show_favorites_tools":
                if not self.favorites_handler:
                    from .favorites_handler import FavoritesHandler
                    self.favorites_handler = FavoritesHandler()
                return self.favorites_handler.show_favorites_tools(context)

            elif action == "save_favorites_as":
                if not self.favorites_handler:
                    from .favorites_handler import FavoritesHandler
                    self.favorites_handler = FavoritesHandler()
                return self.favorites_handler.save_favorites_as(context)

            elif action == "favorites":
                # Handle main favorites menu
                return self._handle_favorites(context)

            elif action == "show_list_tools":
                from .tools_handler import ToolsHandler
                # Instantiate ToolsHandler here if it's not a singleton or managed globally
                if not self.tools_handler:
                    self.tools_handler = ToolsHandler()
                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')
                result = self.tools_handler.show_list_tools(context, list_type, list_id)

                # Handle DialogResponse - show notification if there's a message
                if hasattr(result, 'message') and result.message:
                    notification_type = xbmcgui.NOTIFICATION_INFO if result.success else xbmcgui.NOTIFICATION_ERROR
                    xbmcgui.Dialog().notification("LibraryGenie", result.message, notification_type)

                # Handle navigation flags for successful operations that require navigation
                if hasattr(result, 'success') and result.success:
                    if hasattr(result, 'navigate_to_folder') and result.navigate_to_folder:
                        # Navigate to specific folder (for search history deletion)
                        import xbmc
                        folder_id = result.navigate_to_folder
                        xbmc.executebuiltin(f'Container.Update({context.build_url("show_folder", folder_id=folder_id)},replace)')
                        # End directory properly to prevent fallback navigation
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'navigate_to_lists') and result.navigate_to_lists:
                        # Navigate to main lists menu (for list/folder deletion)
                        import xbmc
                        xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')
                        # End directory properly to prevent fallback navigation
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'navigate_to_main') and result.navigate_to_main:
                        # Navigate to main menu (for search history cleanup)
                        import xbmc
                        xbmc.executebuiltin(f'Container.Update({context.build_url("main_menu")},replace)')
                        # End directory properly to prevent fallback navigation
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'navigate_to_favorites') and result.navigate_to_favorites:
                        # Navigate back to favorites view after successful scan
                        import xbmc
                        xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')
                        # End directory properly
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'refresh_needed') and result.refresh_needed:
                        # Just refresh the current directory
                        import xbmc
                        xbmc.executebuiltin('Container.Refresh')
                        # End directory properly
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                elif hasattr(result, 'success') and not result.success:
                    # For failed/canceled operations, navigate back to the appropriate view
                    import xbmc
                    if list_type == 'folder' and list_id:
                        # Navigate back to the folder view
                        xbmc.executebuiltin(f'Container.Update({context.build_url("show_folder", folder_id=list_id)},replace)')
                    elif list_type == 'user_list' and list_id:
                        # Navigate back to the list view
                        xbmc.executebuiltin(f'Container.Update({context.build_url("show_list", list_id=list_id)},replace)')
                    elif list_type == 'favorites':
                        # Navigate back to favorites view
                        xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')
                    elif list_type == 'lists_main':
                        # Navigate back to main lists menu
                        xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')

                return result.success if hasattr(result, 'success') else True

            elif action == "add_to_list":
                # Handle add to list from context menu
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                success = lists_handler.add_to_list_context(context)
                if success:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        "Added to list successfully", 
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )

            elif action == "quick_add":
                # Handle quick add to default list
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                success = lists_handler.quick_add_context(context)
                if success:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        "Quick added to default list", 
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )

            elif action == 'manual_backup':
                # Handle manual backup
                from .main_menu_handler import MainMenuHandler
                main_handler = MainMenuHandler()
                result = main_handler.handle_manual_backup(context)
                if result.success:
                    if result.message:
                        xbmcgui.Dialog().ok("LibraryGenie", result.message)
                else:
                    if result.message:
                        xbmcgui.Dialog().ok("Error", result.message)
                return

            elif action == 'set_default_list':
                # Handle setting default list for quick-add
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                result = lists_handler.set_default_list(context)
                
                # Show notification based on result
                if result.success and result.message:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        result.message,
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )
                elif not result.success and result.message:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        result.message,
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                return

            else:
                # Check for registered handlers for other actions
                handler = self._handlers.get(action)
                if not handler:
                    self.logger.debug(f"No handler found for action '{action}', will show main menu")
                    return False
                # Use the registered handler
                handler(context)
            return True

        except Exception as e:
            self.logger.error(f"Error in handler for action '{action}': {e}")
            import traceback
            self.logger.error(f"Handler error traceback: {traceback.format_exc()}")

            # Show error to user
            try:
                xbmcgui.Dialog().notification(
                    context.addon.getLocalizedString(35002),
                    f"Error in {action}",
                    xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass

            return False

    

    def _handle_favorites(self, context: PluginContext) -> None:
        """Handle favorites menu action"""
        try:
            from .favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            response = favorites_handler.show_favorites_menu(context)

            if isinstance(response, DirectoryResponse):
                # Directory response is already handled by show_favorites_menu
                return
            else:
                # Fallback if unexpected response type
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)

        except Exception as e:
            self.logger.error(f"Error in favorites handler: {e}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)

    def _handle_scan_favorites(self, context: PluginContext) -> None:
        """Handle scan favorites action"""
        try:
            from .favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            response = favorites_handler.scan_favorites(context)

            if isinstance(response, DialogResponse) and response.success:
                if response.refresh_needed:
                    # Refresh the container to show updated favorites
                    xbmc.executebuiltin('Container.Refresh')

                if response.message:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )
            elif isinstance(response, DialogResponse):
                # Show error message
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message or "Scan failed",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )

        except Exception as e:
            self.logger.error(f"Error in scan favorites handler: {e}")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Error scanning favorites",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

    def _handle_save_favorites_as(self, context: PluginContext) -> None:
        """Handle save favorites as action"""
        try:
            from .favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            response = favorites_handler.save_favorites_as(context)

            if isinstance(response, DialogResponse) and response.success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message or "Favorites saved as new list",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )

                # Optionally refresh to show new list
                if response.refresh_needed:
                    xbmc.executebuiltin('Container.Refresh')

            elif isinstance(response, DialogResponse):
                if response.message:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )

        except Exception as e:
            self.logger.error(f"Error in save favorites as handler: {e}")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Error saving favorites",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

    def _handle_noop(self, context: PluginContext) -> None:
        """Handle no-op action"""
        try:
            # Just end the directory with no items
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
        except Exception as e:
            self.logger.error(f"Error in noop handler: {e}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)

    