#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Centralized Dialog Service
Provides a unified interface for all dialog interactions, combining type safety,
error handling, and logging while eliminating duplication across the codebase.
"""

import xbmcgui
from typing import Optional, Union, Sequence
from lib.utils.kodi_log import get_kodi_logger


class DialogService:
    """
    Centralized dialog service that provides a unified interface for all dialog interactions.
    Combines the type safety of DialogAdapter with centralized error handling and logging.
    """
    
    def __init__(self, logger_name: Optional[str] = None, app_name: str = "LibraryGenie"):
        """
        Initialize dialog service
        
        Args:
            logger_name: Name for the logger instance
            app_name: Application name to show in notifications
        """
        self.logger = get_kodi_logger(logger_name) if logger_name else get_kodi_logger('lib.ui.dialog_service')
        self.app_name = app_name
        self.dialog = xbmcgui.Dialog()
    
    # Selection and Input Dialogs
    
    def select(self, title: str, options: Sequence[Union[str, xbmcgui.ListItem]], 
               preselect: int = -1, use_details: bool = False) -> int:
        """
        Show selection dialog with type-safe parameters
        
        Args:
            title: Dialog title
            options: List of options to select from
            preselect: Pre-selected index (-1 for none)
            use_details: Whether to use detailed list items
            
        Returns:
            int: Selected index (-1 if cancelled)
        """
        try:
            self.logger.debug("Showing selection dialog: %s with %d options", title, len(options))
            # Convert to list to satisfy xbmcgui requirements
            options_list = list(options)
            result = self.dialog.select(
                heading=title,
                list=options_list,
                preselect=preselect,
                useDetails=use_details
            )
            self.logger.debug("Selection dialog result: %d", result)
            return result
        except Exception as e:
            self.logger.error("Dialog select error: %s", e)
            return -1
    
    def yesno(self, title: str, message: str, 
             yes_label: Optional[str] = None, no_label: Optional[str] = None) -> bool:
        """
        Show yes/no confirmation dialog
        
        Args:
            title: Dialog title
            message: Dialog message
            yes_label: Custom yes button label
            no_label: Custom no button label
            
        Returns:
            bool: True if confirmed, False if cancelled
        """
        try:
            self.logger.debug("Showing yesno dialog: %s", title)
            result = self.dialog.yesno(
                heading=title,
                message=message,
                yeslabel=yes_label if yes_label else "",
                nolabel=no_label if no_label else ""
            )
            self.logger.debug("YesNo dialog result: %s", result)
            return result
        except Exception as e:
            self.logger.error("Dialog yesno error: %s", e)
            return False
    
    def input(self, title: str, default: str = "", 
             input_type: int = xbmcgui.INPUT_ALPHANUM,
             hidden: bool = False) -> Optional[str]:
        """
        Show input dialog
        
        Args:
            title: Dialog title
            default: Default input value
            input_type: Type of input (xbmcgui.INPUT_*)
            hidden: Whether to hide input (for passwords)
            
        Returns:
            str: User input, None if cancelled
        """
        try:
            self.logger.debug("Showing input dialog: %s", title)
            result = self.dialog.input(
                heading=title,
                defaultt=default,
                type=input_type,
                option=xbmcgui.ALPHANUM_HIDE_INPUT if hidden else 0
            )
            self.logger.debug("Input dialog completed: %s", "text entered" if result else "cancelled")
            return result if result else None
        except Exception as e:
            self.logger.error("Dialog input error: %s", e)
            return None
    
    def ok(self, title: str, message: str) -> None:
        """
        Show OK dialog for information display
        
        Args:
            title: Dialog title
            message: Dialog message
        """
        try:
            self.logger.debug("Showing OK dialog: %s", title)
            self.dialog.ok(title, message)
        except Exception as e:
            self.logger.error("Dialog OK error: %s", e)
    
    # Notification Methods
    
    def notification(self, message: str, 
                    icon: str = "info",
                    time_ms: int = 5000,
                    title: Optional[str] = None) -> None:
        """
        Show notification to user
        
        Args:
            message: Notification message
            icon: Icon type ("info", "warning", "error")
            time_ms: Display time in milliseconds
            title: Custom title (defaults to app_name)
        """
        try:
            # Map string icons to xbmcgui constants
            icon_map = {
                "info": xbmcgui.NOTIFICATION_INFO,
                "warning": xbmcgui.NOTIFICATION_WARNING, 
                "error": xbmcgui.NOTIFICATION_ERROR
            }
            icon_value = icon_map.get(icon, xbmcgui.NOTIFICATION_INFO)
            display_title = title if title else self.app_name
            
            self.logger.debug("Showing notification: %s - %s", display_title, message)
            self.dialog.notification(
                heading=display_title,
                message=message,
                icon=icon_value,
                time=time_ms
            )
        except Exception as e:
            self.logger.error("Dialog notification error: %s", e)
    
    def show_success(self, message: str, title: Optional[str] = None, time_ms: int = 3000) -> None:
        """Show success notification"""
        self.notification(message, icon="info", title=title, time_ms=time_ms)
    
    def show_error(self, message: str, title: Optional[str] = None, time_ms: int = 5000) -> None:
        """Show error notification"""
        self.notification(message, icon="error", title=title, time_ms=time_ms)
    
    def show_warning(self, message: str, title: Optional[str] = None, time_ms: int = 5000) -> None:
        """Show warning notification"""
        self.notification(message, icon="warning", title=title, time_ms=time_ms)
    
    # Combined Error Handling Methods (integrating ErrorHandler functionality)
    
    def log_and_notify_error(self, 
                           log_message: str, 
                           user_message: str,
                           exception: Optional[Exception] = None,
                           timeout_ms: int = 5000,
                           show_traceback: bool = False) -> None:
        """
        Log error and show notification to user
        
        Args:
            log_message: Message for the log (technical details)
            user_message: User-friendly message for notification
            exception: Optional exception object to log
            timeout_ms: Notification timeout in milliseconds
            show_traceback: Whether to include traceback in log
        """
        # Log the error with full details
        full_log_message = log_message
        if exception:
            full_log_message += f": {exception}"
            
        if show_traceback and exception:
            import traceback
            full_log_message += f"\nTraceback: {traceback.format_exc()}"
            
        self.logger.error(full_log_message)
        
        # Show user-friendly notification
        self.show_error(user_message, time_ms=timeout_ms)
    
    def log_and_notify_success(self,
                              log_message: str,
                              user_message: str,
                              timeout_ms: int = 3000) -> None:
        """
        Log success and show success notification to user
        
        Args:
            log_message: Message for the log
            user_message: User-friendly success message
            timeout_ms: Notification timeout in milliseconds
        """
        self.logger.info(log_message)
        self.show_success(user_message, time_ms=timeout_ms)
    
    def log_and_notify_warning(self,
                              log_message: str,
                              user_message: str,
                              timeout_ms: int = 5000) -> None:
        """
        Log warning and show warning notification to user
        
        Args:
            log_message: Message for the log
            user_message: User-friendly warning message
            timeout_ms: Notification timeout in milliseconds
        """
        self.logger.warning(log_message)
        self.show_warning(user_message, time_ms=timeout_ms)
    
    def handle_exception(self,
                        operation_name: str,
                        exception: Exception,
                        user_friendly_action: str,
                        timeout_ms: int = 5000,
                        show_traceback: bool = True) -> None:
        """
        Handle an exception with standardized logging and notification
        
        Args:
            operation_name: Name of the operation that failed (for logging)
            exception: The exception that occurred
            user_friendly_action: User-friendly description of what was being done
            timeout_ms: Notification timeout in milliseconds
            show_traceback: Whether to include traceback in log
        """
        log_message = f"Error in {operation_name}"
        user_message = f"Error {user_friendly_action}"
        
        self.log_and_notify_error(
            log_message=log_message,
            user_message=user_message,
            exception=exception,
            timeout_ms=timeout_ms,
            show_traceback=show_traceback
        )


# Global instance management
_dialog_service_instance = None


def get_dialog_service(logger_name: Optional[str] = None, app_name: str = "LibraryGenie") -> DialogService:
    """
    Get global dialog service instance with optional customization
    
    Args:
        logger_name: Custom logger name for this context
        app_name: Custom app name for notifications
        
    Returns:
        DialogService: Configured dialog service instance
    """
    global _dialog_service_instance
    
    # Create new instance if customization is requested or none exists
    if logger_name is not None or _dialog_service_instance is None:
        return DialogService(logger_name=logger_name, app_name=app_name)
    
    return _dialog_service_instance


def create_dialog_service(logger_name: Optional[str] = None, app_name: str = "LibraryGenie") -> DialogService:
    """Create a new DialogService instance"""
    return DialogService(logger_name=logger_name, app_name=app_name)


# Convenience functions for quick usage
def show_notification(message: str, icon: str = "info", time_ms: int = 5000, title: Optional[str] = None) -> None:
    """Quick notification function"""
    service = get_dialog_service()
    service.notification(message, icon=icon, time_ms=time_ms, title=title)


def show_error_notification(message: str, time_ms: int = 5000) -> None:
    """Quick error notification function"""
    service = get_dialog_service()
    service.show_error(message, time_ms=time_ms)


def show_success_notification(message: str, time_ms: int = 3000) -> None:
    """Quick success notification function"""
    service = get_dialog_service()
    service.show_success(message, time_ms=time_ms)


def confirm_action(title: str, message: str, 
                  yes_label: Optional[str] = None, no_label: Optional[str] = None) -> bool:
    """Quick confirmation dialog function"""
    service = get_dialog_service()
    return service.yesno(title, message, yes_label=yes_label, no_label=no_label)


# Export all public functions and classes
__all__ = [
    'DialogService',
    'get_dialog_service',
    'create_dialog_service',
    'show_notification',
    'show_error_notification', 
    'show_success_notification',
    'confirm_action'
]