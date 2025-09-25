#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any
from lib.ui.plugin_context import PluginContext
import xbmcgui
import xbmcplugin
import time
from lib.utils.kodi_log import get_kodi_logger


class Router:
    """Routes actions to appropriate handler functions"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.router')
        self._handlers: Dict[str, Callable] = {}

    def _get_current_route_info(self):
        """Get current route information for navigation decisions"""
        try:
            import xbmc
            current_path = xbmc.getInfoLabel('Container.FolderPath')

            # Extract action and parameters from current path
            if 'action=' in current_path:
                # Parse current route parameters
                import urllib.parse
                parsed = urllib.parse.urlparse(current_path)
                params = urllib.parse.parse_qs(parsed.query)
                # Flatten parameter values
                current_params = {k: v[0] if v else '' for k, v in params.items()}
                current_route = current_params.get('action', '')
            else:
                current_route = None
                current_params = {}

            self.logger.debug("ROUTER: Current route info - route: %s, params: %s", current_route, current_params)
            return current_route, current_params
        except Exception as e:
            self.logger.warning("ROUTER: Error getting current route info: %s", e)
            return None, {}

    def register_handler(self, action: str, handler: Callable):
        """Register a handler function for an action"""
        self._handlers[action] = handler

    def register_handlers(self, handlers: Dict[str, Callable]):
        """Register multiple handlers at once"""
        self._handlers.update(handlers)

    def _navigate_smart(self, next_route: str, reason: str = "navigation", next_params: Dict[str, Any] = None):
        """Navigate using navigation policy to determine push vs replace"""
        try:
            from lib.ui.nav_policy import decide_mode
            from lib.ui.nav import get_navigator

            current_route, current_params = self._get_current_route_info()
            next_params = next_params or {}

            # Decide navigation mode
            mode = decide_mode(current_route, next_route, reason, current_params, next_params)

            navigator = get_navigator()
            if mode == 'push':
                navigator.push(next_route)
            else:  # replace
                navigator.replace(next_route)

            self.logger.debug("ROUTER: Smart navigation - mode: %s, route: %s", mode, next_route)

        except Exception as e:
            self.logger.error("ROUTER: Error in smart navigation: %s", e)
            # Fallback to push
            from lib.ui.nav import push
            push(next_route)

    def dispatch(self, context: PluginContext) -> bool:
        """
        Dispatch request to appropriate handler based on context
        Returns True if handler was found and called, False otherwise
        """
        action = context.get_param('action', '')
        params = context.get_params() # Get all params for modular tools
        self.logger.debug("Router dispatching action: '%s'", action)

        # Generate breadcrumb context for navigation (skip for Tools & Options for performance)
        if action != "show_list_tools":
            from lib.ui.breadcrumb_helper import get_breadcrumb_helper
            breadcrumb_helper = get_breadcrumb_helper()
            breadcrumb_path = breadcrumb_helper.get_breadcrumb_for_action(action, params, context.query_manager)
            # Add breadcrumb to context for handlers
            context.breadcrumb_path = breadcrumb_path
        else:
            # Tools & Options don't need breadcrumbs - skip for performance
            context.breadcrumb_path = None

        try:
            # Handle special router-managed actions
            if action == "show_list_tools":
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                from lib.ui.session_state import get_session_state

                # Store current location for returning after tools operations
                import xbmc
                current_path = xbmc.getInfoLabel('Container.FolderPath')
                session_state = get_session_state()
                session_state.set_tools_return_location(current_path)

                factory = get_handler_factory()
                factory.context = context # Set context before using factory
                tools_handler = factory.get_tools_handler()
                response_handler = get_response_handler()

                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')

                result = tools_handler.show_list_tools(context, list_type, list_id)

                # Use response handler to process the result - ensure we don't return anything that would cause fallthrough
                response_handler.handle_dialog_response(result, context)

                # Check if this is a settings operation - if so, skip endOfDirectory to prevent empty list flash
                if hasattr(result, 'is_settings_operation') and result.is_settings_operation:
                    # For settings operations, don't call endOfDirectory to prevent empty directory display
                    return True
                else:
                    # End directory properly to prevent Kodi from trying to load this as a directory
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                    return True  # Always return True to prevent fallthrough to main menu
            elif action == "noop":
                return self._handle_noop(context)
            elif action == 'lists' or action == 'show_lists_menu':
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                response_handler = get_response_handler()
                response = lists_handler.show_lists_menu(context)
                return response_handler.handle_directory_response(response, context)
            elif action == 'prompt_and_search':
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.nav import finish_directory
                factory = get_handler_factory()
                factory.context = context # Set context before using factory
                search_handler = factory.get_search_handler()
                result = search_handler.prompt_and_search(context)
                # Search results use PUSH semantics (new page, not refinement)
                finish_directory(context.addon_handle, succeeded=result, update=False)
                return result
            elif action == 'add_to_list':
                media_item_id = context.get_param('media_item_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')

                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()

                # Check if this is a context action (called from outside the plugin)
                import xbmc
                container_path = xbmc.getInfoLabel('Container.FolderPath')
                is_context_action = not container_path or 'plugin.video.librarygenie' not in container_path

                if media_item_id:
                    # Handle adding existing media item to list
                    success = lists_handler.add_to_list_context(context)
                elif dbtype and dbid:
                    # Handle adding library item to list
                    success = lists_handler.add_library_item_to_list_context(context)
                else:
                    # Handle adding external item to list
                    success = lists_handler.add_external_item_to_list(context)

                # For context actions, end cleanly without navigation
                if is_context_action:
                    # End directory to prevent Kodi from trying to display plugin interface
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return True  # Prevent fallthrough to main menu
                else:
                    return success
            # Added new handler for remove_from_list
            elif action == 'remove_from_list':
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                return self._handle_remove_from_list(context, lists_handler)
            elif action == 'remove_library_item_from_list':
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')
                return lists_handler.remove_library_item_from_list(context, list_id, dbtype, dbid)
            elif action in ['show_list', 'view_list']:
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')

                # Special handling for Kodi Favorites - trigger scan-if-needed before showing
                if self._is_kodi_favorites_list(context, list_id):
                    self._handle_kodi_favorites_scan_if_needed(context)

                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                response = lists_handler.view_list(context, list_id)

                # Router delegates to response handler - it will process the navigation intent
                return response_handler.handle_directory_response(response, context)

            elif action == 'show_folder':
                folder_id = params.get('folder_id')

                if folder_id:
                    # Use the handler factory
                    from lib.ui.handler_factory import get_handler_factory
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    from lib.ui.response_handler import get_response_handler
                    response_handler = get_response_handler()
                    response = lists_handler.show_folder(context, str(folder_id))
                    return response_handler.handle_directory_response(response, context)
                else:
                    self.logger.error("Missing folder_id parameter")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'delete_folder':
                folder_id = params.get('folder_id')
                if folder_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.delete_folder(context, str(folder_id))
                    # Auto-refresh after successful folder deletion
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing folder_id parameter for delete_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'rename_folder':
                folder_id = params.get('folder_id')
                if folder_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.rename_folder(context, str(folder_id))
                    # Auto-refresh after successful folder rename
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing folder_id parameter for rename_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'move_folder':
                folder_id = params.get('folder_id')
                if folder_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.move_folder(context, str(folder_id))
                    # Auto-refresh after successful folder move
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing folder_id parameter for move_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'show_search_history':
                # Handle search history folder access - look up folder ID only when needed
                query_manager = context.query_manager
                if query_manager:
                    search_folder_id = query_manager.get_or_create_search_history_folder()
                    if search_folder_id:
                        # Use the handler factory
                        from lib.ui.handler_factory import get_handler_factory
                        factory = get_handler_factory()
                        factory.context = context
                        lists_handler = factory.get_lists_handler()
                        from lib.ui.response_handler import get_response_handler
                        response_handler = get_response_handler()
                        response = lists_handler.show_folder(context, str(search_folder_id))
                        return response_handler.handle_directory_response(response, context)
                    else:
                        self.logger.error("Could not access search history folder")
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                        return False
                else:
                    self.logger.error("Query manager not available for search history")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == "restore_backup":
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler.handle_restore_backup(params, context)

                # Handle the DialogResponse
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                success = response_handler.handle_dialog_response(result, context)
                return bool(success) if success is not None else True

            elif action == "activate_ai_search":
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler.handle_activate_ai_search(params, context)

                # Handle the DialogResponse
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                success = response_handler.handle_dialog_response(result, context)
                return bool(success) if success is not None else True

            elif action == "authorize_ai_search":
                from lib.ai_search_handler import AISearchHandler
                ai_handler = AISearchHandler()
                result = ai_handler.authorize_ai_search(context)
                return result if isinstance(result, bool) else True
            elif action == "ai_search_replace_sync":
                try:
                    from lib.ui.ai_search_handler import get_ai_search_handler
                    ai_handler = get_ai_search_handler()
                    ai_handler.trigger_replace_sync(context)
                    return True
                except Exception as e:
                    self.logger.error("Error in ai_search_replace_sync handler: %s", e)
                    return False

            elif action == "ai_search_regular_sync":
                try:
                    from lib.ui.ai_search_handler import get_ai_search_handler
                    ai_handler = get_ai_search_handler()
                    ai_handler.trigger_regular_sync(context)
                    return True
                except Exception as e:
                    self.logger.error("Error in ai_search_regular_sync handler: %s", e)
                    return False
            elif action == 'test_ai_search_connection':
                try:
                    from lib.auth.otp_auth import test_api_connection
                    from lib.config.settings import SettingsManager
                    settings = SettingsManager()
                    server_url = settings.get_remote_server_url()
                    if not server_url:
                        self.logger.error("No server URL configured for AI search connection test")
                        return False
                    result = test_api_connection(server_url)
                    return result.get('success', False)
                except Exception as e:
                    self.logger.error("Error testing AI search connection: %s", e)
                    return False

            elif action == 'find_similar_movies':
                from lib.ui.ai_search_handler import AISearchHandler
                ai_search_handler = AISearchHandler()
                return ai_search_handler.find_similar_movies(context)
            elif action.startswith('quick_add'):
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.nav import execute_intent, refresh
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()

                is_context = context.is_from_outside_plugin()

                if action == 'quick_add' and context.get_param('media_item_id'):
                    result = lists_handler.quick_add_to_default_list(context)
                elif action == 'quick_add_context':
                    result = lists_handler.quick_add_library_item_to_default_list(context)
                elif action == 'quick_add_external':
                    result = lists_handler.quick_add_external_item_to_default_list(context)
                else:
                    result = False

                # Context menu actions vs plugin actions
                if is_context:
                    # Pure context actions - no endOfDirectory, use NavigationIntent
                    if result and hasattr(result, 'intent') and result.intent:
                        execute_intent(result.intent)
                    elif result:
                        refresh()  # Fallback to refresh if no intent
                    return True
                else:
                    # For plugin actions, end directory normally
                    from lib.ui.nav import finish_directory
                    finish_directory(context.addon_handle, succeeded=bool(result))
                    return bool(result)
            elif action.startswith('add_to_list') or action.startswith('add_library_item_to_list'):
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                from lib.ui.nav import execute_intent, refresh
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()
                response_handler = get_response_handler()

                is_context = context.is_from_outside_plugin()
                result = None

                # Dispatch based on specific action
                if action == 'add_to_list':
                    media_item_id = context.get_param('media_item_id')
                    if media_item_id:
                        result = lists_handler.add_to_list_menu(context)
                    else:
                        # Handle library item parameters
                        result = lists_handler.add_library_item_to_list_context(context)
                elif action == 'add_library_item_to_list':
                    result = lists_handler.add_library_item_to_list_context(context)
                elif action == 'add_external_item':
                    result = lists_handler.add_external_item_to_list(context)

                # Handle context actions differently
                if is_context:
                    # Pure context actions - no endOfDirectory, use NavigationIntent
                    if result and hasattr(result, 'intent') and result.intent:
                        execute_intent(result.intent)
                    elif result:
                        refresh()  # Fallback to refresh if no intent
                    return bool(result)
                else:
                    # For plugin directory actions, handle the response properly
                    if hasattr(result, 'success'):
                        # It's a DialogResponse - handle with response handler
                        response_handler.handle_dialog_response(result, context)
                        return result.success
                    else:
                        # It's a boolean or similar result
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=bool(result))
                        return bool(result)
            else:
                # Check for registered handlers
                handler = self._handlers.get(action)
                if not handler:
                    self.logger.debug("No handler found for action '%s', will show main menu (redirecting to Lists)", action)

                    # ROUTER TIMING: Handler factory import
                    import_start_time = time.time()
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    import_end_time = time.time()
                    self.logger.info(f"ROUTER: Handler factory import took {import_end_time - import_start_time:.3f} seconds")

                    # ROUTER TIMING: Factory instance creation
                    factory_creation_start_time = time.time()
                    factory = get_handler_factory()
                    factory.context = context
                    response_handler = get_response_handler()
                    factory_creation_end_time = time.time()
                    self.logger.info(f"ROUTER: Handler factory creation and context setup took {factory_creation_end_time - factory_creation_start_time:.3f} seconds")

                    # ROUTER TIMING: Lists handler retrieval
                    lists_handler_start_time = time.time()
                    lists_handler = factory.get_lists_handler()
                    lists_handler_end_time = time.time()
                    self.logger.info(f"ROUTER: Lists handler retrieval took {lists_handler_end_time - lists_handler_start_time:.3f} seconds")

                    # ROUTER TIMING: Main menu handler execution
                    main_menu_start_time = time.time()
                    response = lists_handler.show_lists_menu(context)
                    success = response_handler.handle_directory_response(response, context)
                    main_menu_end_time = time.time()
                    self.logger.info(f"ROUTER: Main menu handler execution took {main_menu_end_time - main_menu_start_time:.3f} seconds")

                    return success
                # Use the registered handler
                handler(context)
                return True

        except Exception as e:
            self.logger.error("Error in handler for action '%s': %s", action, e)
            import traceback
            self.logger.error("Handler error traceback: %s", traceback.format_exc())

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
            from lib.ui.handler_factory import get_handler_factory
            from lib.ui.response_handler import get_response_handler

            factory = get_handler_factory()
            factory.context = context # Set context before using factory
            tools_handler = factory.get_tools_handler()
            response_handler = get_response_handler()

            list_type = params.get('list_type', 'unknown')
            list_id = params.get('list_id')

            result = tools_handler.show_list_tools(context, list_type, list_id)

            # Use response handler to process the result
            success = response_handler.handle_dialog_response(result, context)
            return bool(success) if success is not None else True

        except Exception as e:
            self.logger.error("Error in list tools handler: %s", e)
            return False

    def _handle_noop(self, context: PluginContext) -> bool:
        """Handle no-op action"""
        try:
            # Just end the directory with no items
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
            return True
        except Exception as e:
            self.logger.error("Error in noop handler: %s", e)
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
            from lib.config.settings import SettingsManager
            settings = SettingsManager()
            server_url = settings.get_remote_server_url()

            self.logger.info("Retrieved server URL: '%s' (type: %s)", server_url, type(server_url))

            # Check server URL first
            if not server_url or len(server_url.strip()) == 0:
                self.logger.warning("Server URL validation failed - URL: '%s'", server_url)
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

            self.logger.info("User entered OTP code: %s", otp_code)
            self.logger.info("Starting OTP authorization with code: %s", otp_code)

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search Authorization", "Exchanging OTP code for API key...")

            try:
                # Exchange OTP for API key
                from lib.auth.otp_auth import exchange_otp_for_api_key
                result = exchange_otp_for_api_key(otp_code, server_url)

                progress.close()

                if result['success']:
                    # Success - activate AI Search
                    settings.set_ai_search_activated(True)
                    self.logger.info("✅ AI Search activated with server URL: %s", server_url)

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

                    self.logger.warning("OTP authorization failed from settings: %s", result['error'])
                    return False

            finally:
                if progress:
                    progress.close()

        except Exception as e:
            self.logger.error("Error in authorize_ai_search handler: %s", e)
            xbmcgui.Dialog().ok(
                "Authorization Error",
                f"An unexpected error occurred:\n\n{str(e)[:100]}..."
            )
            return False

    def _is_kodi_favorites_list(self, context, list_id):
        """Check if the list being viewed is the Kodi Favorites list"""
        try:
            if not list_id:
                return False

            query_manager = context.query_manager
            if not query_manager:
                return False

            list_info = query_manager.get_list_by_id(list_id)
            if list_info and list_info.get('name') == 'Kodi Favorites':
                self.logger.debug("ROUTER: Detected Kodi Favorites list (id: %s)", list_id)
                return True

            return False
        except Exception as e:
            self.logger.error("ROUTER: Error checking if list is Kodi Favorites: %s", e)
            return False

    def _handle_kodi_favorites_scan_if_needed(self, context):
        """Trigger scan-if-needed for Kodi Favorites before showing the list"""
        try:
            self.logger.info("ROUTER: Triggering scan-if-needed for Kodi Favorites")

            # Initialize favorites manager
            favorites_manager = context.favorites_manager
            if not favorites_manager:
                self.logger.warning("ROUTER: Favorites manager not available")
                return

            # Check if scan is needed and perform if so
            result = favorites_manager.scan_favorites(force_refresh=False)
            if result.get('success'):
                scan_type = result.get('scan_type', 'unknown')
                items_found = result.get('items_found', 0)
                items_mapped = result.get('items_mapped', 0)
                self.logger.info("ROUTER: Kodi Favorites scan completed - type: %s, found: %s, mapped: %s", scan_type, items_found, items_mapped)
            else:
                self.logger.warning("ROUTER: Kodi Favorites scan failed: %s", result.get('message', 'Unknown error'))

        except Exception as e:
            self.logger.error("ROUTER: Error during Kodi Favorites scan: %s", e)