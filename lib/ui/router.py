#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any
from .plugin_context import PluginContext


class Router:
    """Routes actions to appropriate handler functions"""

    def __init__(self):
        self.logger = None  # Will be set from context
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
                return self.favorites_handler.scan_favorites(context)

            elif action == "show_favorites_tools":
                return self.favorites_handler.show_favorites_tools(context)

            elif action == "save_favorites_as":
                return self.favorites_handler.save_favorites_as(context)

            elif action == "show_list_tools":
                from .tools_handler import ToolsHandler
                tools_handler = ToolsHandler()
                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')
                return tools_handler.show_list_tools(context, list_type, list_id)
            else:
                handler(context)
            return True

        except Exception as e:
            self.logger.error(f"Error in handler for action '{action}': {e}")
            import traceback
            self.logger.error(f"Handler error traceback: {traceback.format_exc()}")

            # Show error to user
            try:
                import xbmcgui
                xbmcgui.Dialog().notification(
                    context.addon.getLocalizedString(35002),
                    f"Error in {action}",
                    xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass

            return False