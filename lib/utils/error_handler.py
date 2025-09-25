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
from .errors import LibraryGenieError, UserError, CancelledError
from lib.ui.dialog_service import get_dialog_service
from lib.ui.response_types import DialogResponse


class ErrorHandler:
    """Centralized error handling that combines logging with user notifications"""
    
    def __init__(self, logger_name: Optional[str] = None, app_name: str = "LibraryGenie", include_traceback: bool = False):
        """
        Initialize error handler
        
        Args:
            logger_name: Name for the logger instance
            app_name: Application name to show in notifications
            include_traceback: Whether to include tracebacks in logs (default False for production)
        """
        self.logger = get_kodi_logger(logger_name) if logger_name else get_kodi_logger()
        self.app_name = app_name
        self.dialog = get_dialog_service(logger_name, app_name)
        self.include_traceback = include_traceback
    
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
        self.dialog.show_error(user_message, time_ms=timeout_ms)
    
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
        
        self.dialog.show_success(user_message, time_ms=timeout_ms)
    
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
        
        self.dialog.show_warning(user_message, time_ms=timeout_ms)
    
    def handle_exception(self,
                        operation_name: str,
                        exception: Exception,
                        user_friendly_action: str,
                        timeout_ms: int = 5000,
                        show_traceback: Optional[bool] = None) -> None:
        """
        Handle an exception with standardized logging and notification
        
        Args:
            operation_name: Name of the operation that failed (for logging)
            exception: The exception that occurred
            user_friendly_action: User-friendly description of what was being done
            timeout_ms: Notification timeout in milliseconds
            show_traceback: Whether to include traceback in log (defaults to instance setting)
        """
        # Classify error type and determine appropriate response
        if isinstance(exception, CancelledError):
            # User cancellation - debug log only, no notification
            self.logger.debug(f"Operation cancelled: {operation_name}")
            return
        elif isinstance(exception, UserError):
            # Expected user error - warning level, show warning notification
            log_message = f"User error in {operation_name}: {exception.message}"
            user_message = exception.user_message or f"Error {user_friendly_action}"
            
            self.log_and_notify_warning(
                log_message=log_message,
                user_message=user_message,
                timeout_ms=timeout_ms
            )
        else:
            # Unexpected error - error level, show error notification
            log_message = f"Error in {operation_name}"
            user_message = f"Error {user_friendly_action}"
            
            # Use instance setting for traceback if not specified
            if show_traceback is None:
                show_traceback = self.include_traceback
            
            self.log_and_notify_error(
                log_message=log_message,
                user_message=user_message,
                exception=exception,
                timeout_ms=timeout_ms,
                show_traceback=show_traceback
            )
    
    def build_error_dialog_response(self, operation_name: str, exception: Exception, 
                                   default_message: str = None) -> DialogResponse:
        """
        Build a DialogResponse for boundary error handling
        
        Args:
            operation_name: Name of the operation that failed
            exception: The exception that occurred
            default_message: Default user message if exception doesn't provide one
            
        Returns:
            DialogResponse indicating failure with appropriate message
        """
        if isinstance(exception, CancelledError):
            # User cancellation - success=False but no error message to avoid notification
            return DialogResponse(success=False)
        elif isinstance(exception, LibraryGenieError) and exception.user_message:
            # Use the exception's user-friendly message
            return DialogResponse(success=False, message=exception.user_message)
        else:
            # Use provided default or generate generic message
            message = default_message or f"Error in {operation_name.replace('_', ' ')}"
            return DialogResponse(success=False, message=message)
    
    def handle_boundary_exception(self, operation_name: str, exception: Exception,
                                 user_friendly_action: str, 
                                 cleanup_functions: list = None,
                                 timeout_ms: int = 5000) -> DialogResponse:
        """
        Handle exception at UI/router/provider boundaries with cleanup
        
        Args:
            operation_name: Name of the operation that failed
            exception: The exception that occurred
            user_friendly_action: User-friendly description of what was being done
            cleanup_functions: List of functions to call for cleanup
            timeout_ms: Notification timeout in milliseconds
            
        Returns:
            DialogResponse indicating the result
        """
        try:
            # Run cleanup functions
            if cleanup_functions:
                for cleanup_func in cleanup_functions:
                    try:
                        cleanup_func()
                    except Exception as cleanup_error:
                        self.logger.warning(f"Cleanup function failed: {cleanup_error}")
            
            # Handle the original exception
            self.handle_exception(operation_name, exception, user_friendly_action, timeout_ms)
            
            # Build appropriate response
            return self.build_error_dialog_response(operation_name, exception, 
                                                   f"Error {user_friendly_action}")
        except Exception as handler_error:
            # Error in error handler itself - log and return basic response
            self.logger.error(f"Error in boundary exception handler: {handler_error}")
            return DialogResponse(success=False, message=f"Error {user_friendly_action}")


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
    
    DEPRECATED: Use ErrorHandler or boundary decorators instead for new code.
    This function is maintained for backward compatibility.
    
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
    
    DEPRECATED: Use ErrorHandler or boundary decorators instead for new code.
    This function is maintained for backward compatibility.
    
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