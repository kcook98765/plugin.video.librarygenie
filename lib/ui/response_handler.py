#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Response Handler
Standardizes DialogResponse and DirectoryResponse processing and navigation
"""

import xbmc
import xbmcgui
import xbmcplugin
from typing import Any
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DirectoryResponse, DialogResponse
from lib.utils.kodi_log import get_kodi_logger


class ResponseHandler:
    """Handles standardized processing of response types"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.response_handler')

    def handle_dialog_response(self, response: DialogResponse, context: PluginContext) -> None:
        """Handle DialogResponse by showing messages and performing actions"""
        try:
            context.logger.debug("RESPONSE HANDLER: Processing DialogResponse - success=%s, message='%s'", response.success, response.message)
            
            # Show message if present
            if response.message:
                if response.success:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )

            # Handle navigation based on response flags - prioritize specific navigation over refresh
            if response.success:
                # Check for navigate_to_folder attribute directly on the response object
                if getattr(response, 'navigate_to_folder', None):
                    # Navigate to specific folder (highest priority for folder operations)
                    import xbmc
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    folder_id = response.navigate_to_folder
                    folder_url = context.build_cache_busted_url("show_folder", folder_id=folder_id)
                    context.logger.debug("RESPONSE HANDLER: Navigating to folder %s with cache-busted URL: %s", folder_id, folder_url)
                    xbmc.executebuiltin(f'Container.Update("{folder_url}",replace)')
                    return

                elif getattr(response, 'navigate_to_lists', None):
                    # Navigate to lists menu
                    import xbmc
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    lists_url = context.build_cache_busted_url("lists")
                    context.logger.debug("RESPONSE HANDLER: Navigating to lists with cache-busted URL: %s", lists_url)
                    xbmc.executebuiltin(f'Container.Update("{lists_url}",replace)')
                    return

                elif getattr(response, 'navigate_to_main', None):
                    # Navigate to main menu
                    import xbmc
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    main_url = context.build_cache_busted_url("main_menu")
                    context.logger.debug("RESPONSE HANDLER: Navigating to main with cache-busted URL: %s", main_url)
                    xbmc.executebuiltin(f'Container.Update("{main_url}",replace)')
                    return

                elif getattr(response, 'navigate_to_favorites', None):
                    # Navigate to favorites view
                    import xbmc
                    from lib.ui.session_state import get_session_state
                    
                    # Bump refresh token for cache-busting
                    session_state = get_session_state()
                    session_state.bump_refresh_token()
                    
                    favorites_url = context.build_cache_busted_url("kodi_favorites")
                    context.logger.debug("RESPONSE HANDLER: Navigating to favorites with cache-busted URL: %s", favorites_url)
                    xbmc.executebuiltin(f'Container.Update("{favorites_url}",replace)')
                    return

                elif getattr(response, 'refresh_needed', None):
                    # Only refresh if no specific navigation was requested
                    # Use Container.Refresh to force Kodi to rebuild directory from scratch
                    import xbmc
                    from lib.ui.session_state import get_session_state
                    
                    session_state = get_session_state()
                    
                    # Check if we're in tools context and need to return to previous location
                    tools_return_location = session_state.get_tools_return_location()
                    current_path = xbmc.getInfoLabel('Container.FolderPath')
                    
                    context.logger.debug("RESPONSE HANDLER: Refreshing current path: %s", current_path)
                    
                    if tools_return_location and 'show_list_tools' in current_path:
                        # Return to stored location and force refresh
                        context.logger.debug("RESPONSE HANDLER: Returning to tools origin and refreshing")
                        xbmc.executebuiltin(f'Container.Update("{tools_return_location}",replace)')
                        session_state.clear_tools_return_location()
                        # Give Kodi a moment to update, then force refresh
                        xbmc.sleep(100)
                        xbmc.executebuiltin('Container.Refresh')
                    else:
                        # Force complete refresh of current directory to clear Kodi's cache
                        context.logger.debug("RESPONSE HANDLER: Using Container.Refresh to clear Kodi cache")
                        xbmc.executebuiltin('Container.Refresh')
                else:
                    # For successful responses with just a message and no navigation flags,
                    # don't do any navigation - let the tools handler's direct navigation work
                    context.logger.debug("RESPONSE HANDLER: Success response with no navigation flags - letting direct navigation work")

            else:
                # Handle failure navigation
                navigate_on_failure = getattr(response, 'navigate_on_failure', None)
                if navigate_on_failure == 'return_to_tools_location':
                    # Navigate back to the stored tools return location
                    import xbmc
                    from lib.ui.session_state import get_session_state
                    session_state = get_session_state()
                    if session_state and session_state.get_tools_return_location():
                        context.logger.debug("RESPONSE HANDLER: Navigating back to tools return location: %s", session_state.get_tools_return_location())
                        xbmc.executebuiltin(f'Container.Update("{session_state.get_tools_return_location()}",replace)')
                        # Clear the return location after using it
                        session_state.clear_tools_return_location()
                        return
                    else:
                        context.logger.warning("RESPONSE HANDLER: No tools return location found for return navigation")

        except Exception as e:
            context.logger.error("Error handling dialog response: %s", e)
            # Fallback error notification
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "An error occurred",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

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
                xbmcplugin.setContent(context.addon_handle, response.content_type)

            # Get all parameters from the response
            kodi_params = response.to_kodi_params()

            # Handle sort methods separately if provided
            sort_methods = kodi_params.get('sortMethods')
            if sort_methods and isinstance(sort_methods, (list, tuple)):
                for sort_method in sort_methods:
                    xbmcplugin.addSortMethod(context.addon_handle, sort_method)

            # End directory with proper parameters
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=bool(kodi_params.get('succeeded', True)),
                updateListing=bool(kodi_params.get('updateListing', False)),
                cacheToDisc=bool(kodi_params.get('cacheToDisc', True))
            )

            return response.success

        except Exception as e:
            self.logger.error("Error handling directory response: %s", e)
            # Fallback directory ending
            try:
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            except Exception:
                pass
            return False

    def _handle_success_navigation(self, response: DialogResponse, context: PluginContext) -> bool:
        """Handle navigation for successful dialog responses"""
        try:
            # Check for tools return location first - if set, navigate back there after tools operations
            from lib.ui.session_state import get_session_state
            session_state = get_session_state()
            tools_return_location = session_state.get_tools_return_location()
            
            if tools_return_location:
                # Clear the return location and navigate back with cache busting
                session_state.clear_tools_return_location()
                session_state.bump_refresh_token()  # Ensure fresh content for tools return
                cache_busted_url = context.add_cache_buster_to_url(tools_return_location)
                xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True
            # Always bump refresh token for all navigation operations
            session_state.bump_refresh_token()
            
            # Navigate to specific folder
            if hasattr(response, 'navigate_to_folder') and response.navigate_to_folder:
                folder_id = response.navigate_to_folder
                cache_busted_url = context.build_cache_busted_url("show_folder", folder_id=folder_id)
                xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Navigate to main lists menu
            elif hasattr(response, 'navigate_to_lists') and response.navigate_to_lists:
                cache_busted_url = context.build_cache_busted_url("lists")
                xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Navigate to main menu
            elif hasattr(response, 'navigate_to_main') and response.navigate_to_main:
                cache_busted_url = context.build_cache_busted_url("main_menu")
                xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Navigate to favorites view
            elif hasattr(response, 'navigate_to_favorites') and response.navigate_to_favorites:
                cache_busted_url = context.build_cache_busted_url("kodi_favorites")
                xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Just refresh current directory to clear Kodi's cache
            elif hasattr(response, 'refresh_needed') and response.refresh_needed:
                # Use Container.Refresh to force Kodi to rebuild directory from scratch
                context.logger.debug("RESPONSE HANDLER: Using Container.Refresh to clear Kodi cache")
                xbmc.executebuiltin('Container.Refresh')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            return True

        except Exception as e:
            self.logger.error("Error handling success navigation: %s", e)
            return False

    def _handle_failure_navigation(self, response: DialogResponse, context: PluginContext) -> bool:
        """Handle navigation for failed dialog responses"""
        try:
            # For failed operations, we might want to stay in current view
            # or navigate back to a safe location

            # If there are specific failure navigation flags, handle them here
            if hasattr(response, 'navigate_on_failure'):
                navigation_target = getattr(response, 'navigate_on_failure', None)
                if navigation_target == 'lists':
                    cache_busted_url = context.build_cache_busted_url("lists")
                    xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                elif navigation_target == 'main':
                    cache_busted_url = context.build_cache_busted_url("main_menu")
                    xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                elif navigation_target == 'favorites':
                    cache_busted_url = context.build_cache_busted_url("kodi_favorites")
                    xbmc.executebuiltin(f'Container.Update("{cache_busted_url}",replace)')
                elif navigation_target == 'return_to_tools_location':
                    # Navigate back to the stored tools return location
                    from lib.ui.session_state import get_session_state
                    session_state = get_session_state()
                    if session_state and session_state.get_tools_return_location():
                        self.logger.debug("RESPONSE HANDLER: Navigating back to tools return location: %s", session_state.get_tools_return_location())
                        xbmc.executebuiltin(f'Container.Update("{session_state.get_tools_return_location()}",replace)')
                        # Clear the return location after using it
                        session_state.clear_tools_return_location()
                    else:
                        self.logger.warning("RESPONSE HANDLER: No tools return location found for return navigation")

                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Default: stay in current view for failures
            return True

        except Exception as e:
            self.logger.error("Error handling failure navigation: %s", e)
            return False

    def handle_action_response(self, response: Any, context: PluginContext, action: str) -> bool:
        """
        Generic handler that routes to appropriate response handler based on type
        Returns True if response was handled successfully
        """
        try:
            if isinstance(response, DialogResponse):
                return self.handle_dialog_response(response, context)
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
                    xbmcgui.Dialog().ok("Error", response.message)
                return

            # Show success message if provided
            if response.message:
                self.logger.debug("RESPONSE HANDLER: Showing success message: %s", response.message)
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message,
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )

            # Handle navigation based on response flags - don't continue processing after navigation
            if response.navigate_to_main:
                self.logger.debug("RESPONSE HANDLER: Navigating to main menu")
                context.navigate_to_main_menu()
                return
            elif response.navigate_to_lists:
                self.logger.debug("RESPONSE HANDLER: Navigating to lists menu")
                context.navigate_to_lists_menu()
                return
            elif response.navigate_to_folder:
                self.logger.debug("RESPONSE HANDLER: Navigating to folder: %s", response.navigate_to_folder)
                context.navigate_to_folder(response.navigate_to_folder)
                return
            elif response.refresh_needed:
                self.logger.debug("RESPONSE HANDLER: Refreshing current container")
                xbmc.executebuiltin('Container.Refresh')
                return

        except Exception as e:
            self.logger.error("Error handling dialog response: %s", e)
            xbmcgui.Dialog().ok("Error", "An error occurred while processing the request")


# Factory function
_response_handler_instance = None


def get_response_handler() -> ResponseHandler:
    """Get global response handler instance"""
    global _response_handler_instance
    if _response_handler_instance is None:
        _response_handler_instance = ResponseHandler()
    return _response_handler_instance