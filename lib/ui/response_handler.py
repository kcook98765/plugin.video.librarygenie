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
from .plugin_context import PluginContext
from .response_types import DirectoryResponse, DialogResponse
from ..utils.logger import get_logger


class ResponseHandler:
    """Handles standardized processing of response types"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def handle_dialog_response(self, response: DialogResponse, context: PluginContext) -> None:
        """Handle DialogResponse by showing messages and performing actions"""
        try:
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
                if hasattr(response, 'navigate_to_main') and response.navigate_to_main:
                    # Navigate to main menu
                    import xbmc
                    xbmc.executebuiltin(f'Container.Update({context.build_url("main")},replace)')

                elif hasattr(response, 'navigate_to_lists') and response.navigate_to_lists:
                    # Navigate to lists menu
                    import xbmc
                    xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')

                elif hasattr(response, 'navigate_to_folder') and response.navigate_to_folder:
                    # Navigate to specific folder
                    import xbmc
                    folder_id = response.navigate_to_folder
                    xbmc.executebuiltin(f'Container.Update({context.build_url("show_folder", folder_id=folder_id)},replace)')

                elif response.refresh_needed:
                    # Only refresh if no specific navigation was requested
                    # For tools operations, we should navigate back to the current view instead of refreshing
                    # to prevent tools dialog from reopening
                    import xbmc
                    current_path = xbmc.getInfoLabel('Container.FolderPath')
                    if 'show_list_tools' in current_path:
                        # If we're in tools context, navigate to parent instead of refreshing
                        xbmc.executebuiltin('Action(ParentDir)')
                    else:
                        xbmc.executebuiltin('Container.Refresh')

        except Exception as e:
            context.logger.error(f"Error handling dialog response: {e}")
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
            self.logger.error(f"Error handling directory response: {e}")
            # Fallback directory ending
            try:
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            except Exception:
                pass
            return False

    def _handle_success_navigation(self, response: DialogResponse, context: PluginContext) -> bool:
        """Handle navigation for successful dialog responses"""
        try:
            # Navigate to specific folder
            if hasattr(response, 'navigate_to_folder') and response.navigate_to_folder:
                folder_id = response.navigate_to_folder
                xbmc.executebuiltin(f'Container.Update({context.build_url("show_folder", folder_id=folder_id)},replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Navigate to main lists menu
            elif hasattr(response, 'navigate_to_lists') and response.navigate_to_lists:
                xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Navigate to main menu
            elif hasattr(response, 'navigate_to_main') and response.navigate_to_main:
                xbmc.executebuiltin(f'Container.Update({context.build_url("main_menu")},replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Navigate to favorites view
            elif hasattr(response, 'navigate_to_favorites') and response.navigate_to_favorites:
                xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Just refresh current directory
            elif hasattr(response, 'refresh_needed') and response.refresh_needed:
                xbmc.executebuiltin('Container.Refresh')
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            return True

        except Exception as e:
            self.logger.error(f"Error handling success navigation: {e}")
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
                    xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')
                elif navigation_target == 'main':
                    xbmc.executebuiltin(f'Container.Update({context.build_url("main_menu")},replace)')
                elif navigation_target == 'favorites':
                    xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')

                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True

            # Default: stay in current view for failures
            return True

        except Exception as e:
            self.logger.error(f"Error handling failure navigation: {e}")
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
                self.logger.warning(f"Unknown response type for action '{action}': {type(response)}")
                return False

        except Exception as e:
            self.logger.error(f"Error handling action response for '{action}': {e}")
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
            self.logger.debug(f"RESPONSE HANDLER: Processing response - success={response.success}")

            if not response.success:
                if response.message:
                    self.logger.debug(f"RESPONSE HANDLER: Showing error message: {response.message}")
                    xbmcgui.Dialog().ok("Error", response.message)
                return

            # Show success message if provided
            if response.message:
                self.logger.debug(f"RESPONSE HANDLER: Showing success message: {response.message}")
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
                self.logger.debug(f"RESPONSE HANDLER: Navigating to folder: {response.navigate_to_folder}")
                context.navigate_to_folder(response.navigate_to_folder)
                return
            elif response.refresh_needed:
                self.logger.debug("RESPONSE HANDLER: Refreshing current container")
                xbmc.executebuiltin('Container.Refresh')
                return

        except Exception as e:
            self.logger.error(f"Error handling dialog response: {e}")
            xbmcgui.Dialog().ok("Error", "An error occurred while processing the request")


# Factory function
_response_handler_instance = None


def get_response_handler() -> ResponseHandler:
    """Get global response handler instance"""
    global _response_handler_instance
    if _response_handler_instance is None:
        _response_handler_instance = ResponseHandler()
    return _response_handler_instance