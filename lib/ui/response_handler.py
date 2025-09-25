
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Response Handler
Standardizes DialogResponse and DirectoryResponse processing and navigation
"""

import xbmcgui
from typing import Any
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DirectoryResponse, DialogResponse
from lib.ui.nav import get_navigator
from lib.ui.dialog_service import get_dialog_service
from lib.utils.kodi_log import get_kodi_logger


class ResponseHandler:
    """Handles standardized processing of response types"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.response_handler')
        self.navigator = get_navigator()
        self.dialog = get_dialog_service('lib.ui.response_handler')

    def handle_dialog_response(self, response: DialogResponse, context: PluginContext) -> None:
        """Handle DialogResponse by showing messages and performing actions"""
        try:
            context.logger.debug("RESPONSE HANDLER: Processing DialogResponse - success=%s, message='%s'", response.success, response.message)
            
            # Show message if present
            if response.message:
                if response.success:
                    self.dialog.show_success(response.message, time_ms=3000)
                else:
                    self.dialog.show_error(response.message, time_ms=5000)

            # Handle navigation based on NavigationIntent (primary) or legacy flags (fallback)
            if response.success:
                # Check for legacy navigation flags for backward compatibility
                if getattr(response, 'navigate_to_folder', None):
                    # Navigate to specific folder (highest priority for folder operations)
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    folder_id = response.navigate_to_folder
                    folder_url = context.build_cache_busted_url("show_folder", folder_id=folder_id)
                    context.logger.debug("RESPONSE HANDLER: Navigating to folder %s with cache-busted URL: %s", folder_id, folder_url)
                    self.navigator.replace(folder_url)
                    return

                elif getattr(response, 'navigate_to_lists', None):
                    # Navigate to lists menu
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    lists_url = context.build_cache_busted_url("lists")
                    context.logger.debug("RESPONSE HANDLER: Navigating to lists with cache-busted URL: %s", lists_url)
                    self.navigator.replace(lists_url)
                    return

                elif getattr(response, 'navigate_to_main', None):
                    # Navigate to main menu
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    main_url = context.build_cache_busted_url("main_menu")
                    context.logger.debug("RESPONSE HANDLER: Navigating to main with cache-busted URL: %s", main_url)
                    self.navigator.replace(main_url)
                    return

                elif getattr(response, 'navigate_to_favorites', None):
                    # Navigate to favorites view
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    favorites_url = context.build_cache_busted_url("kodi_favorites")
                    context.logger.debug("RESPONSE HANDLER: Navigating to favorites with cache-busted URL: %s", favorites_url)
                    self.navigator.replace(favorites_url)
                    return

                elif getattr(response, 'refresh_needed', None):
                    # Only refresh if no specific navigation was requested
                    from lib.ui.session_state import get_session_state
                    
                    session_state = get_session_state()
                    
                    # Check if we're in tools context and need to return to previous location
                    tools_return_location = session_state.get_tools_return_location()
                    import xbmc
                    current_path = xbmc.getInfoLabel('Container.FolderPath')
                    
                    context.logger.debug("RESPONSE HANDLER: Refreshing current path: %s", current_path)
                    
                    if tools_return_location and 'show_list_tools' in current_path:
                        # Return to stored location and force refresh
                        context.logger.debug("RESPONSE HANDLER: Returning to tools origin and refreshing")
                        self.navigator.replace(tools_return_location)
                        session_state.clear_tools_return_location()
                        # Give Kodi a moment to update, then force refresh
                        import xbmc
                        xbmc.sleep(100)
                        self.navigator.refresh()
                    else:
                        # Force complete refresh of current directory to clear Kodi's cache
                        context.logger.debug("RESPONSE HANDLER: Using Container.Refresh to clear Kodi cache")
                        self.navigator.refresh()
                else:
                    # For successful responses with just a message and no navigation flags,
                    # don't do any navigation - let the tools handler's direct navigation work
                    context.logger.debug("RESPONSE HANDLER: Success response with no navigation flags - letting direct navigation work")

            else:
                # Handle failure navigation
                navigate_on_failure = getattr(response, 'navigate_on_failure', None)
                if navigate_on_failure == 'return_to_tools_location':
                    # Navigate back to the stored tools return location
                    from lib.ui.session_state import get_session_state
                    session_state = get_session_state()
                    tools_return_url = session_state.get_tools_return_location() if session_state else None
                    if tools_return_url:
                        context.logger.debug("RESPONSE HANDLER: Navigating back to tools return location: %s", tools_return_url)
                        self.navigator.replace(tools_return_url)
                        # Clear the return location after using it
                        session_state.clear_tools_return_location()
                        return
                    else:
                        context.logger.warning("RESPONSE HANDLER: No tools return location found for return navigation")

            # Execute NavigationIntent if present
            if response.intent:
                context.logger.debug("RESPONSE HANDLER: Executing NavigationIntent: %s", response.intent)
                self.navigator.execute_intent(response.intent)

        except Exception as e:
            context.logger.error("Error handling dialog response: %s", e)
            # Fallback error notification
            self.dialog.show_error("An error occurred", time_ms=3000)

    def handle_directory_response(self, response: DirectoryResponse, context: PluginContext) -> bool:
        """
        Handle DirectoryResponse with proper directory completion
        Returns True if response was handled successfully
        """
        try:
            if not isinstance(response, DirectoryResponse):
                self.logger.warning("Expected DirectoryResponse but got different type")
                return False

            # Set content type if specified
            if hasattr(response, 'content_type') and response.content_type:
                import xbmcplugin
                xbmcplugin.setContent(context.addon_handle, response.content_type)

            # Get all parameters from the response
            kodi_params = response.to_kodi_params()

            # Handle sort methods separately if provided
            sort_methods = kodi_params.get('sortMethods')
            if sort_methods and isinstance(sort_methods, (list, tuple)):
                import xbmcplugin
                for sort_method in sort_methods:
                    xbmcplugin.addSortMethod(context.addon_handle, sort_method)

            # End directory using Navigator instead of direct xbmcplugin call
            # Navigator always uses cacheToDisc=False for dynamic content
            self.navigator.finish_directory(
                context.addon_handle,
                succeeded=bool(kodi_params.get('succeeded', True)),
                update=bool(kodi_params.get('updateListing', False))
            )

            # Execute NavigationIntent if present
            if response.intent:
                context.logger.debug("RESPONSE HANDLER: Executing NavigationIntent: %s", response.intent)
                self.navigator.execute_intent(response.intent)

            return response.success

        except Exception as e:
            self.logger.error("Error handling directory response: %s", e)
            # Fallback directory ending using Navigator
            try:
                self.navigator.finish_directory(context.addon_handle, succeeded=False)
            except Exception:
                pass
            return False

    def handle_action_response(self, response: Any, context: PluginContext, action: str) -> bool:
        """
        Generic handler that routes to appropriate response handler based on type
        Returns True if response was handled successfully
        """
        try:
            if isinstance(response, DialogResponse):
                self.handle_dialog_response(response, context)
                return True
            elif isinstance(response, DirectoryResponse):
                return self.handle_directory_response(response, context)
            else:
                self.logger.warning("Unknown response type for action '%s': %s", action, type(response))
                return False

        except Exception as e:
            self.logger.error("Error handling action response for '%s': %s", action, e)
            return False

    def create_success_dialog_response(self, message: str, **kwargs) -> DialogResponse:
        """Helper to create successful dialog response"""
        return DialogResponse(
            success=True,
            message=message,
            **kwargs
        )

    def create_error_dialog_response(self, message: str, **kwargs) -> DialogResponse:
        """Helper to create error dialog response"""
        return DialogResponse(
            success=False,
            message=message,
            **kwargs
        )

    def create_success_directory_response(self, items: list, content_type: str = "movies", **kwargs) -> DirectoryResponse:
        """Helper to create successful directory response"""
        return DirectoryResponse(
            items=items,
            success=True,
            content_type=content_type,
            **kwargs
        )

    def create_error_directory_response(self, **kwargs) -> DirectoryResponse:
        """Helper to create error directory response"""
        return DirectoryResponse(
            items=[],
            success=False,
            **kwargs
        )


    def handle_response(self, response: DialogResponse, context: PluginContext) -> None:
        """Handle dialog response and perform appropriate navigation"""
        try:
            self.logger.debug("RESPONSE HANDLER: Processing response - success=%s", response.success)

            if not response.success:
                if response.message:
                    self.logger.debug("RESPONSE HANDLER: Showing error message: %s", response.message)
                    self.dialog.ok("Error", response.message)
                return

            # Show success message if provided
            if response.message:
                self.logger.debug("RESPONSE HANDLER: Showing success message: %s", response.message)
                self.dialog.show_success(response.message, time_ms=3000)

            # Handle navigation based on response flags - don't continue processing after navigation
            if response.navigate_to_main:
                self.logger.debug("RESPONSE HANDLER: Navigating to main menu")
                from lib.ui.session_state import get_session_state
                session_state = get_session_state()
                session_state.bump_refresh_token()
                main_url = context.build_cache_busted_url("main_menu")
                self.navigator.replace(main_url)
                return
            elif response.navigate_to_lists:
                self.logger.debug("RESPONSE HANDLER: Navigating to lists menu")
                from lib.ui.session_state import get_session_state
                session_state = get_session_state()
                session_state.bump_refresh_token()
                lists_url = context.build_cache_busted_url("lists")
                self.navigator.replace(lists_url)
                return
            elif response.navigate_to_folder:
                self.logger.debug("RESPONSE HANDLER: Navigating to folder: %s", response.navigate_to_folder)
                from lib.ui.session_state import get_session_state
                session_state = get_session_state()
                session_state.bump_refresh_token()
                folder_url = context.build_cache_busted_url("show_folder", folder_id=response.navigate_to_folder)
                self.navigator.replace(folder_url)
                return
            elif response.refresh_needed:
                self.logger.debug("RESPONSE HANDLER: Refreshing current container")
                self.navigator.refresh()
                return

            # Execute NavigationIntent if present
            if response.intent:
                self.logger.debug("RESPONSE HANDLER: Executing NavigationIntent: %s", response.intent)
                self.navigator.execute_intent(response.intent)

        except Exception as e:
            self.logger.error("Error handling dialog response: %s", e)
            self.dialog.ok("Error", "An error occurred while processing the request")


# Factory function
_response_handler_instance = None


def get_response_handler() -> ResponseHandler:
    """Get global response handler instance"""
    global _response_handler_instance
    if _response_handler_instance is None:
        _response_handler_instance = ResponseHandler()
    return _response_handler_instance
