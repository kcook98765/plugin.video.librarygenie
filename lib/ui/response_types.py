#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Response Types
Standardized response objects for UI handlers
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class DirectoryResponse:
    """Response for directory listing handlers"""
    items: List[Dict[str, Any]]
    success: bool = True
    cache_to_disc: bool = True
    update_listing: bool = False
    sort_methods: Optional[List[int]] = None
    content_type: str = "movies"

    def to_kodi_params(self) -> Dict[str, Union[bool, List[int], None]]:
        """Convert to parameters for xbmcplugin.endOfDirectory"""
        params: Dict[str, Union[bool, List[int], None]] = {
            'succeeded': self.success,
            'cacheToDisc': self.cache_to_disc,
            'updateListing': self.update_listing,
            'sortMethods': None
        }
        if self.sort_methods:
            params['sortMethods'] = self.sort_methods
        return params


@dataclass
class DialogResponse:
    """Response type for dialog operations"""

    def __init__(self, success: bool = False, message: str = "", refresh_needed: bool = False,
                 navigate_to_lists: bool = False, navigate_to_folder: Optional[int] = None,
                 navigate_to_main: bool = False, navigate_to_favorites: bool = False,
                 navigate_on_failure: Optional[str] = None):
        self.success = success
        self.message = message
        self.refresh_needed = refresh_needed
        self.navigate_to_lists = navigate_to_lists
        self.navigate_to_folder = navigate_to_folder
        self.navigate_to_main = navigate_to_main
        self.navigate_to_favorites = navigate_to_favorites
        self.navigate_on_failure = navigate_on_failure

    def show_notification(self, addon, default_title: str = "LibraryGenie"):
        """Show notification to user if message is provided"""
        if self.message:
            try:
                import xbmcgui
                xbmcgui.Dialog().notification(
                    default_title,
                    self.message,
                    xbmcgui.NOTIFICATION_INFO if self.success else xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass


@dataclass
class ActionResponse:
    """Response for action handlers (play, add to list, etc.)"""
    success: bool
    action_performed: str
    refresh_needed: bool = False
    notification_message: Optional[str] = None

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
                import xbmc
                xbmc.executebuiltin("Container.Refresh")
            except Exception:
                pass


@dataclass
class ErrorResponse:
    """Response for error conditions"""
    error_message: str
    error_code: Optional[str] = None
    show_to_user: bool = True

    def handle_error(self, context):
        """Handle error with appropriate user feedback"""
        context.logger.error(f"Handler error: {self.error_message}")

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


def create_empty_directory() -> DirectoryResponse:
    """Create an empty directory response"""
    return DirectoryResponse(items=[], success=True)


def create_error_directory(error_msg: str) -> DirectoryResponse:
    """Create an error directory response"""
    return DirectoryResponse(items=[], success=False)