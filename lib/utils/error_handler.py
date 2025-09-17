#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Centralized Error Handling and Notifications
Combines logging with user notifications to eliminate code duplication
"""

import xbmc
import xbmcgui
from typing import Optional, Union
from .kodi_log import get_kodi_logger


class ErrorHandler:
    """Centralized error handling that combines logging with user notifications"""
    
    def __init__(self, logger_name: Optional[str] = None, app_name: str = "LibraryGenie"):
        """
        Initialize error handler
        
        Args:
            logger_name: Name for the logger instance
            app_name: Application name to show in notifications
        """
        self.logger = get_kodi_logger(logger_name) if logger_name else get_kodi_logger()
        self.app_name = app_name
    
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
        try:
            xbmcgui.Dialog().notification(
                self.app_name,
                user_message,
                xbmcgui.NOTIFICATION_ERROR,
                timeout_ms
            )
        except Exception as notify_error:
            # Fallback if notification fails
            self.logger.error(f"Failed to show notification: {notify_error}")
    
    def log_and_notify_success(self,
                              log_message: str,
                              user_message: str,
                              timeout_ms: int = 5000) -> None:
        """
        Log success and show success notification to user
        
        Args:
            log_message: Message for the log
            user_message: User-friendly success message
            timeout_ms: Notification timeout in milliseconds
        """
        self.logger.info(log_message)
        
        try:
            xbmcgui.Dialog().notification(
                self.app_name,
                user_message,
                xbmcgui.NOTIFICATION_INFO,
                timeout_ms
            )
        except Exception as notify_error:
            self.logger.error(f"Failed to show success notification: {notify_error}")
    
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
        
        try:
            xbmcgui.Dialog().notification(
                self.app_name,
                user_message,
                xbmcgui.NOTIFICATION_WARNING,
                timeout_ms
            )
        except Exception as notify_error:
            self.logger.error(f"Failed to show warning notification: {notify_error}")
    
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


# Global convenience functions
def create_error_handler(logger_name: Optional[str] = None, app_name: str = "LibraryGenie") -> ErrorHandler:
    """Create an ErrorHandler instance"""
    return ErrorHandler(logger_name=logger_name, app_name=app_name)


def handle_error_with_notification(logger_name: str,
                                  log_message: str,
                                  user_message: str,
                                  exception: Optional[Exception] = None,
                                  timeout_ms: int = 5000,
                                  app_name: str = "LibraryGenie") -> None:
    """
    Quick function for one-off error handling with notification
    
    Args:
        logger_name: Name for the logger
        log_message: Technical log message
        user_message: User-friendly notification message
        exception: Optional exception
        timeout_ms: Notification timeout
        app_name: App name for notification
    """
    handler = ErrorHandler(logger_name=logger_name, app_name=app_name)
    handler.log_and_notify_error(
        log_message=log_message,
        user_message=user_message,
        exception=exception,
        timeout_ms=timeout_ms
    )


def handle_success_with_notification(logger_name: str,
                                   log_message: str,
                                   user_message: str,
                                   timeout_ms: int = 5000,
                                   app_name: str = "LibraryGenie") -> None:
    """
    Quick function for success handling with notification
    
    Args:
        logger_name: Name for the logger
        log_message: Technical log message
        user_message: User-friendly success message
        timeout_ms: Notification timeout
        app_name: App name for notification
    """
    handler = ErrorHandler(logger_name=logger_name, app_name=app_name)
    handler.log_and_notify_success(
        log_message=log_message,
        user_message=user_message,
        timeout_ms=timeout_ms
    )


# Export all public functions and classes
__all__ = [
    'ErrorHandler',
    'create_error_handler',
    'handle_error_with_notification',
    'handle_success_with_notification'
]