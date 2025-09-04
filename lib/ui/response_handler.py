
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

    def handle_dialog_response(self, response: DialogResponse, context: PluginContext) -> bool:
        """
        Handle DialogResponse with notifications and navigation
        Returns True if response was handled successfully
        """
        try:
            if not isinstance(response, DialogResponse):
                self.logger.warning("Expected DialogResponse but got different type")
                return False

            # Show notification if there's a message
            if hasattr(response, 'message') and response.message:
                notification_type = xbmcgui.NOTIFICATION_INFO if response.success else xbmcgui.NOTIFICATION_ERROR
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    response.message, 
                    notification_type,
                    5000
                )

            # Handle navigation flags for successful operations
            if response.success:
                return self._handle_success_navigation(response, context)
            else:
                return self._handle_failure_navigation(response, context)

        except Exception as e:
            self.logger.error(f"Error handling dialog response: {e}")
            return False

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

            # Handle caching
            cache_to_disc = getattr(response, 'cache_to_disc', True)

            # End directory
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=response.success,
                updateListing=getattr(response, 'update_listing', False),
                cacheToDisc=cache_to_disc
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


# Factory function
_response_handler_instance = None


def get_response_handler() -> ResponseHandler:
    """Get global response handler instance"""
    global _response_handler_instance
    if _response_handler_instance is None:
        _response_handler_instance = ResponseHandler()
    return _response_handler_instance
