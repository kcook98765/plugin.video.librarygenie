#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any
from .plugin_context import PluginContext
import xbmcgui
import xbmcplugin
from ..utils.logger import get_logger


class Router:
    """Routes actions to appropriate handler functions"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._handlers: Dict[str, Callable] = {}

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
            # Handle special router-managed actions
            if action == "show_list_tools":
                return self._handle_list_tools(context, params)
            elif action == "noop":
                return self._handle_noop(context)
            elif action == 'lists' or action == 'show_lists_menu':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                handler = factory.get_lists_handler()
                return handler.show_lists_menu(context)
            elif action == 'prompt_and_search':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                search_handler = factory.get_search_handler()
                search_handler.prompt_and_search(context)
                return True
            elif action == 'add_to_list':
                media_item_id = context.get_param('media_item_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')

                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                lists_handler = factory.get_lists_handler()

                if media_item_id:
                    # Handle adding existing media item to list
                    success = lists_handler.add_to_list_context(context)
                    return success
                elif dbtype and dbid:
                    # Handle adding library item to list
                    success = lists_handler.add_library_item_to_list_context(context)
                    return success
                else:
                    # Handle adding external item to list
                    success = lists_handler.add_external_item_to_list(context)
                    return success
            # Added new handler for remove_from_list
            elif action == 'remove_from_list':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                lists_handler = factory.get_lists_handler()
                return self._handle_remove_from_list(context, lists_handler)
            elif action == 'remove_library_item_from_list':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')
                return lists_handler.remove_library_item_from_list(context, list_id, dbtype, dbid)
            else:
                # Check for registered handlers
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

    def _handle_list_tools(self, context: PluginContext, params: Dict[str, Any]) -> bool:
        """Handle list tools action with response processing"""
        try:
            from .handler_factory import get_handler_factory
            from .response_handler import get_response_handler

            factory = get_handler_factory()
            tools_handler = factory.get_tools_handler()
            response_handler = get_response_handler()

            list_type = params.get('list_type', 'unknown')
            list_id = params.get('list_id')

            result = tools_handler.show_list_tools(context, list_type, list_id)

            # Use response handler to process the result
            return response_handler.handle_dialog_response(result, context)

        except Exception as e:
            self.logger.error(f"Error in list tools handler: {e}")
            return False

    def _handle_noop(self, context: PluginContext) -> bool:
        """Handle no-op action"""
        try:
            # Just end the directory with no items
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
            return True
        except Exception as e:
            self.logger.error(f"Error in noop handler: {e}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

    def _handle_remove_from_list(self, context: PluginContext, lists_handler) -> bool:
        """Handles the remove_from_list action, including fallback logic."""
        list_id = context.get_param('list_id')
        item_id = context.get_param('item_id')

        if item_id:
            # If item_id is directly provided, use it
            return lists_handler.remove_from_list(context, list_id, item_id)
        else:
            # Fallback: try to find the item_id using library identifiers
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')
            if dbtype and dbid:
                return lists_handler.remove_library_item_from_list(context, list_id, dbtype, dbid)
            else:
                self.logger.error("Cannot remove from list: missing item_id, dbtype, or dbid.")
                try:
                    xbmcgui.Dialog().notification(
                        context.addon.getLocalizedString(35002),
                        "Could not remove item from list.",
                        xbmcgui.NOTIFICATION_ERROR
                    )
                except Exception:
                    pass
                return False