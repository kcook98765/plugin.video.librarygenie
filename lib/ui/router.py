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
                from .handler_factory import get_handler_factory
                from .response_handler import get_response_handler

                factory = get_handler_factory()
                factory.context = context # Set context before using factory
                tools_handler = factory.get_tools_handler()
                response_handler = get_response_handler()

                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')

                result = tools_handler.show_list_tools(context, list_type, list_id)

                # Use response handler to process the result - ensure we don't return anything that would cause fallthrough
                response_handler.handle_dialog_response(result, context)

                # End directory properly to prevent Kodi from trying to load this as a directory
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True  # Always return True to prevent fallthrough to main menu
            elif action == "noop":
                return self._handle_noop(context)
            elif action == 'lists' or action == 'show_lists_menu':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                response = lists_handler.show_lists_menu(context)
                return response
            elif action == 'prompt_and_search':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context # Set context before using factory
                search_handler = factory.get_search_handler()
                result = search_handler.prompt_and_search(context)
                return result
            elif action == 'add_to_list':
                media_item_id = context.get_param('media_item_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')

                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
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
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                return self._handle_remove_from_list(context, lists_handler)
            elif action == 'remove_library_item_from_list':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')
                return lists_handler.remove_library_item_from_list(context, list_id, dbtype, dbid)
            elif action in ['show_list', 'view_list']:
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')
                response = lists_handler.view_list(context, list_id)
                return response
            elif action == 'show_folder':
                folder_id = params.get('folder_id')

                if folder_id:
                    # Use the handler factory
                    from .handler_factory import get_handler_factory
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response = lists_handler.show_folder(context, folder_id)
                    return response
                else:
                    self.logger.error("Missing folder_id parameter")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)

            elif action == 'show_search_history':
                # Handle search history folder access - look up folder ID only when needed
                query_manager = context.query_manager
                if query_manager:
                    search_folder_id = query_manager.get_or_create_search_history_folder()
                    if search_folder_id:
                        # Use the handler factory
                        from .handler_factory import get_handler_factory
                        factory = get_handler_factory()
                        factory.context = context
                        lists_handler = factory.get_lists_handler()
                        response = lists_handler.show_folder(context, search_folder_id)
                        return response
                    else:
                        self.logger.error("Could not access search history folder")
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                        return False
                else:
                    self.logger.error("Query manager not available for search history")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
            elif action == "restore_backup":
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler.handle_restore_backup(params, context)

                # Handle the DialogResponse
                from .response_handler import get_response_handler
                response_handler = get_response_handler()
                return response_handler.handle_dialog_response(result, context)

            elif action == "activate_ai_search":
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler.handle_activate_ai_search(params, context)

                # Handle the DialogResponse
                from .response_handler import get_response_handler
                response_handler = get_response_handler()
                return response_handler.handle_dialog_response(result, context)

            elif action == "authorize_ai_search":
                from .ai_search_handler import AISearchHandler
                ai_handler = AISearchHandler()
                ai_handler.authorize_ai_search(context)
            elif action == "ai_search_replace_sync":
                try:
                    from .ai_search_handler import get_ai_search_handler
                    ai_handler = get_ai_search_handler()
                    ai_handler.trigger_replace_sync(context)
                    return True
                except Exception as e:
                    self.logger.error(f"Error in ai_search_replace_sync handler: {e}")
                    return False

            elif action == "ai_search_regular_sync":
                try:
                    from .ai_search_handler import get_ai_search_handler
                    ai_handler = get_ai_search_handler()
                    ai_handler.trigger_regular_sync(context)
                    return True
                except Exception as e:
                    self.logger.error(f"Error in ai_search_regular_sync handler: {e}")
                    return False
            elif action == 'test_ai_search_connection':
                from .handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                return tools_handler.test_ai_search_connection(context)

            elif action == 'find_similar_movies':
                from .ai_search_handler import AISearchHandler
                ai_search_handler = AISearchHandler()
                return ai_search_handler.find_similar_movies(context)
            else:
                # Check for registered handlers
                handler = self._handlers.get(action)
                if not handler:
                    self.logger.debug(f"No handler found for action '{action}', will show main menu (redirecting to Lists)")
                    # Show Lists as main menu instead of traditional main menu
                    from .handler_factory import get_handler_factory
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response = lists_handler.show_lists_menu(context)
                    return response.success if hasattr(response, 'success') else True

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
            factory.context = context # Set context before using factory
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

    def _handle_authorize_ai_search(self, context: PluginContext) -> bool:
        """Handle AI search authorization action from settings"""
        try:
            self.logger.info("Authorization button clicked from settings")

            # Get settings manager for server URL
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            server_url = settings.get_remote_server_url()

            self.logger.info(f"Retrieved server URL: '{server_url}' (type: {type(server_url)})")

            # Check server URL first
            if not server_url or len(server_url.strip()) == 0:
                self.logger.warning(f"Server URL validation failed - URL: '{server_url}'")
                xbmcgui.Dialog().ok(
                    "Configuration Required",
                    "Please configure the AI Search Server URL before authorizing.\n\nMake sure it's not empty and contains a valid URL."
                )
                return False

            # Pop up keyboard for OTP entry
            dialog = xbmcgui.Dialog()
            otp_code = dialog.input(
                "Enter OTP Code", 
                "Enter the 8-digit OTP code from your server:"
            )

            # Check if user cancelled or entered invalid code
            if not otp_code or len(otp_code.strip()) != 8:
                if otp_code:  # User entered something but it's invalid
                    xbmcgui.Dialog().ok(
                        "Invalid OTP Code",
                        "Please enter a valid 8-digit OTP code."
                    )
                return False

            self.logger.info(f"User entered OTP code: {otp_code}")
            self.logger.info(f"Starting OTP authorization with code: {otp_code}")

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search Authorization", "Exchanging OTP code for API key...")

            try:
                # Exchange OTP for API key
                from ..auth.otp_auth import exchange_otp_for_api_key
                result = exchange_otp_for_api_key(otp_code, server_url)

                progress.close()

                if result['success']:
                    # Success - activate AI Search 
                    settings.set_ai_search_activated(True)
                    self.logger.info(f"✅ AI Search activated with server URL: {server_url}")

                    # Show success dialog
                    xbmcgui.Dialog().ok(
                        "Authorization Complete",
                        f"AI Search activated successfully!\n\nUser: {result.get('user_email', 'Unknown')}"
                    )

                    self.logger.info("OTP authorization completed successfully from settings")
                    return True
                else:
                    # Failed - show error
                    xbmcgui.Dialog().ok(
                        "Authorization Failed",
                        f"Failed to activate AI Search:\n\n{result['error']}"
                    )

                    self.logger.warning(f"OTP authorization failed from settings: {result['error']}")
                    return False

            finally:
                if progress:
                    progress.close()

        except Exception as e:
            self.logger.error(f"Error in authorize_ai_search handler: {e}")
            xbmcgui.Dialog().ok(
                "Authorization Error",
                f"An unexpected error occurred:\n\n{str(e)[:100]}..."
            )
            return False