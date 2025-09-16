#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Response Types
Standardized response objects for UI handlers
"""

from typing import List, Dict, Any, Optional, Union
from lib.ui.localization import L


class DirectoryResponse:
    """Response for directory listing handlers"""
    
    def __init__(self, items: List[Dict[str, Any]], success: bool = True, 
                 cache_to_disc: bool = False, update_listing: bool = False,
                 sort_methods: Optional[List[int]] = None, content_type: str = "movies",
                 allow_caching: bool = False):
        self.items = items
        self.success = success
        self.cache_to_disc = cache_to_disc  # Default to no caching for dynamic content
        self.update_listing = update_listing
        self.sort_methods = sort_methods
        self.content_type = content_type
        self.allow_caching = allow_caching  # Explicit flag to enable caching for truly static content

    def to_kodi_params(self) -> Dict[str, Union[bool, List[int], None]]:
        """Convert to parameters for xbmcplugin.endOfDirectory"""
        # Use smart caching logic: allow_caching overrides cache_to_disc
        cache_enabled = self.allow_caching if hasattr(self, 'allow_caching') else self.cache_to_disc
        
        params: Dict[str, Union[bool, List[int], None]] = {
            'succeeded': self.success,
            'cacheToDisc': cache_enabled,
            'updateListing': self.update_listing,
            'sortMethods': None
        }
        if self.sort_methods:
            params['sortMethods'] = self.sort_methods
        return params


class DialogResponse:
    """Response type for dialog operations"""
    
    def __init__(self, success: bool = False, message: str = "", 
                 refresh_needed: bool = False, navigate_to_lists: bool = False,
                 navigate_to_folder: Optional[int] = None, navigate_to_main: bool = False,
                 navigate_to_favorites: bool = False, navigate_on_failure: Optional[str] = None,
                 is_settings_operation: bool = False):
        self.success = success
        self.message = message
        self.refresh_needed = refresh_needed
        self.navigate_to_lists = navigate_to_lists
        self.navigate_to_folder = navigate_to_folder
        self.navigate_to_main = navigate_to_main
        self.navigate_to_favorites = navigate_to_favorites
        self.navigate_on_failure = navigate_on_failure
        self.is_settings_operation = is_settings_operation
        
        # Debug logging (moved from __post_init__)
        try:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.response_types')
            logger.debug("DEBUG: DialogResponse created - success=%s, message='%s'", self.success, self.message)
        except Exception:
            pass  # Don't let logging errors break the response

    def show_notification(self, addon, default_title: Optional[str] = None):
        """Show notification to user if message is provided"""
        if self.message:
            try:
                import xbmcgui
                title = default_title or L(32300)  # "LibraryGenie"
                xbmcgui.Dialog().notification(
                    title,
                    self.message,
                    xbmcgui.NOTIFICATION_INFO if self.success else xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass


class ActionResponse:
    """Response for action handlers (play, add to list, etc.)"""
    
    def __init__(self, success: bool, action_performed: str, 
                 refresh_needed: bool = False, notification_message: Optional[str] = None):
        self.success = success
        self.action_performed = action_performed
        self.refresh_needed = refresh_needed
        self.notification_message = notification_message

    def handle_result(self, context):
        """Handle the action result with appropriate user feedback"""
        if self.notification_message:
            try:
                import xbmcgui
                xbmcgui.Dialog().notification(
                    context.addon.getLocalizedString(32000),  # Addon name
                    self.notification_message,
                    xbmcgui.NOTIFICATION_INFO if self.success else xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass

        if self.refresh_needed and self.success:
            try:
                # Use Container.Refresh to force Kodi to rebuild directory from scratch
                # This clears Kodi's internal cache and ensures new lists/folders appear immediately
                import xbmc
                xbmc.executebuiltin('Container.Refresh')
            except Exception:
                pass


class ErrorResponse:
    """Response for error conditions"""
    
    def __init__(self, error_message: str, error_code: Optional[str] = None, 
                 show_to_user: bool = True):
        self.error_message = error_message
        self.error_code = error_code
        self.show_to_user = show_to_user

    def handle_error(self, context):
        """Handle error with appropriate user feedback"""
        context.logger.error("Handler error: %s", self.error_message)

        if self.show_to_user:
            try:
                import xbmcgui
                xbmcgui.Dialog().notification(
                    context.addon.getLocalizedString(35002),  # Error title
                    self.error_message,
                    xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass


class ListResponse:
    """Response data for list-based UI actions"""

    def __init__(self, menu_items=None, error=False, error_message=None, navigate_to_main=False, refresh_needed=False, breadcrumb_path=None):
        self.menu_items = menu_items or []
        self.error = error
        self.error_message = error_message
        self.navigate_to_main = navigate_to_main
        self.refresh_needed = refresh_needed
        self.breadcrumb_path = breadcrumb_path


def create_empty_directory() -> DirectoryResponse:
    """Create an empty directory response"""
    return DirectoryResponse(items=[], success=True)


def create_error_directory(error_msg: str) -> DirectoryResponse:
    """Create an error directory response"""
    return DirectoryResponse(items=[], success=False)