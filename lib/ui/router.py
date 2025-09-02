#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any
from .plugin_context import PluginContext
import xbmcgui # Import xbmcgui for dialogs


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
            self.logger = context.logger

        action = context.get_param('action', '')
        params = context.get_params() # Get all params for modular tools
        self.logger.debug(f"Router dispatching action: '{action}'")

        handler = self._handlers.get(action)
        if not handler:
            self.logger.debug(f"No handler found for action '{action}', will show main menu")
            return False

        try:
            # Call handler with context
            self.logger.debug(f"Calling handler for action '{action}'")
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

            elif action == "show_list_tools":
                from .tools_handler import ToolsHandler
                # Instantiate ToolsHandler here if it's not a singleton or managed globally
                if not self.tools_handler:
                    self.tools_handler = ToolsHandler()
                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')
                return self.tools_handler.show_list_tools(context, list_type, list_id)

            elif action == "add_to_list":
                media_item_id = params.get('media_item_id')
                return self._handle_add_to_list(context, media_item_id)

            else:
                # Use the registered handler if not a specific case
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

    def _handle_add_to_list(self, context: PluginContext, media_item_id: str) -> bool:
        """Handle adding media item to a list"""
        try:
            if not media_item_id:
                context.logger.error("No media item ID provided")
                return False

            query_manager = context.query_manager
            if not query_manager:
                context.logger.error("Failed to get query manager")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"):
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    result = lists_handler.create_list(context)
                    if result.success:
                        # Refresh lists and continue
                        all_lists = query_manager.get_all_lists_with_folders()
                    else:
                        return False
                else:
                    return False

            # Build list options for selection
            list_options = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(f"{lst['name']} ({lst['item_count']} items)")
                else:
                    list_options.append(f"{folder_name}/{lst['name']} ({lst['item_count']} items)")

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]")

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options)

            if selected_index < 0:
                return False

            # Handle selection
            if selected_index == len(list_options) - 1:  # Create new list
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                result = lists_handler.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders()
                if all_lists:
                    target_list_id = all_lists[-1]['id']  # Assume last created
                else:
                    return False
            else:
                target_list_id = all_lists[selected_index]['id']

            # Add item to selected list
            result = query_manager.add_item_to_list(target_list_id, media_item_id)

            if result.get("success"):
                list_name = all_lists[selected_index]['name'] if selected_index < len(all_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'",
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list",
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Failed to add to list",
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            context.logger.error(f"Error adding to list: {e}")
            return False