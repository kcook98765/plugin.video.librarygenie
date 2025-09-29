#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Response Types
Standardized response objects for UI handlers
"""

from typing import List, Dict, Any, Optional, Union, Literal
from lib.ui.localization import L


class NavigationIntent:
    """Describes navigation intent without performing it"""

    def __init__(self, mode: Literal['push', 'replace', 'refresh', None] = None, url: Optional[str] = None):
        self.mode = mode
        self.url = url

        # Validation
        if mode in ['push', 'replace'] and not url:
            raise ValueError(f"Navigation mode '{mode}' requires a URL")
        if mode == 'refresh' and url:
            raise ValueError("Refresh mode should not have a URL")

    def __repr__(self):
        if self.mode == 'refresh':
            return f"NavigationIntent(mode='refresh')"
        elif self.mode in ['push', 'replace']:
            return f"NavigationIntent(mode='{self.mode}', url='{self.url}')"
        else:
            return "NavigationIntent(mode=None)"


class DirectoryResponse:
    """Response for directory listing handlers"""

    def __init__(self, items: List[Dict[str, Any]], success: bool = True, content_type: str = "movies", 
                 update_listing: bool = False, sort_methods: Optional[List[int]] = None, 
                 intent: Optional['NavigationIntent'] = None):
        self.items = items
        self.success = success
        self.content_type = content_type
        self.update_listing = update_listing
        self.sort_methods = sort_methods or []
        self.intent = intent

    def to_kodi_params(self) -> Dict[str, Any]:
        """Convert to parameters for xbmcplugin.endOfDirectory"""
        return {
            'succeeded': self.success,
            'updateListing': self.update_listing,
            'cacheToDisc': False,  # Always disable caching for dynamic content
            'sortMethods': self.sort_methods
        }


class DialogResponse:
    """Response type for dialog operations"""

    def __init__(self, success: bool = False, message: str = "", 
                 refresh_needed: bool = False, navigate_to_lists: bool = False,
                 navigate_to_folder: Optional[Union[int, str]] = None, navigate_to_main: bool = False,
                 navigate_to_favorites: bool = False, navigate_on_failure: Optional[str] = None,
                 is_settings_operation: bool = False, intent: Optional[NavigationIntent] = None):
        self.success = success
        self.message = message
        self.refresh_needed = refresh_needed
        self.navigate_to_lists = navigate_to_lists
        self.navigate_to_folder = navigate_to_folder
        self.navigate_to_main = navigate_to_main
        self.navigate_to_favorites = navigate_to_favorites
        self.navigate_on_failure = navigate_on_failure
        self.is_settings_operation = is_settings_operation
        self.intent = intent

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