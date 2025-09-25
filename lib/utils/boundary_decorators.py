#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Boundary Decorators for Standardized Error Handling
Decorators for UI boundaries, provider actions, and script entry points
"""

import functools
from typing import Callable, Any, List, Optional
from .error_handler import create_error_handler
from lib.ui.response_types import DialogResponse, DirectoryResponse


def ui_boundary(operation_name: str, user_friendly_action: str, 
                notify: bool = True, cleanup_functions: Optional[List[Callable]] = None):
    """
    Decorator for UI boundary methods (handlers that return DirectoryResponse or DialogResponse)
    
    Args:
        operation_name: Technical name of the operation for logging
        user_friendly_action: User-friendly description for notifications
        notify: Whether to show user notifications on errors
        cleanup_functions: List of cleanup functions to call on errors
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not notify:
                # For operations that shouldn't notify, just execute normally
                return func(*args, **kwargs)
            
            # Create error handler for this boundary
            error_handler = create_error_handler(f"{func.__module__}.{func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                # Handle the exception with cleanup
                dialog_response = error_handler.handle_boundary_exception(
                    operation_name=operation_name,
                    exception=e,
                    user_friendly_action=user_friendly_action,
                    cleanup_functions=cleanup_functions or []
                )
                
                # Return appropriate response type based on function's expected return type
                if hasattr(func, '__annotations__') and func.__annotations__.get('return'):
                    return_type = func.__annotations__['return']
                    if return_type == DirectoryResponse or 'DirectoryResponse' in str(return_type):
                        return DirectoryResponse(items=[], success=False)
                    
                return dialog_response
                
        return wrapper
    return decorator


def provider_action(operation_name: str, user_friendly_action: str, 
                   notify: bool = True, cleanup_functions: Optional[List[Callable]] = None):
    """
    Decorator for provider action methods (tools & options handlers)
    
    Args:
        operation_name: Technical name of the operation for logging
        user_friendly_action: User-friendly description for notifications
        notify: Whether to show user notifications on errors
        cleanup_functions: List of cleanup functions to call on errors
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create error handler for this boundary
            error_handler = create_error_handler(f"{func.__module__}.{func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                
                # Ensure result is a DialogResponse
                if isinstance(result, DialogResponse):
                    return result
                else:
                    # If handler doesn't return DialogResponse, create success response
                    return DialogResponse(success=True)
                    
            except Exception as e:
                # Handle the exception with cleanup and user notification (if enabled)
                if notify:
                    return error_handler.handle_boundary_exception(
                        operation_name=operation_name,
                        exception=e,
                        user_friendly_action=user_friendly_action,
                        cleanup_functions=cleanup_functions or []
                    )
                else:
                    # Log only, no notification
                    error_handler.logger.error(f"Error in {operation_name}: {e}")
                    return DialogResponse(success=False, message=f"Error in {operation_name.replace('_', ' ')}")
                
        return wrapper
    return decorator


def script_action(operation_name: str, user_friendly_action: str,
                 ensure_cleanup: Optional[List[Callable]] = None):
    """
    Decorator for script entry points (utilities.py handlers)
    
    Args:
        operation_name: Technical name of the operation for logging
        user_friendly_action: User-friendly description for notifications
        ensure_cleanup: List of cleanup functions to call on errors
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create error handler for this boundary
            error_handler = create_error_handler(f"{func.__module__}.{func.__name__}")
            
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                # Handle the exception with cleanup
                error_handler.handle_boundary_exception(
                    operation_name=operation_name,
                    exception=e,
                    user_friendly_action=user_friendly_action,
                    cleanup_functions=ensure_cleanup or []
                )
                # Script actions don't return values, just handle the error
                
        return wrapper
    return decorator


def safe_operation(operation_name: str, logger_name: Optional[str] = None,
                  log_only: bool = False):
    """
    Basic decorator for internal operations that should be logged but not notify users
    
    Args:
        operation_name: Technical name of the operation for logging
        logger_name: Logger name override
        log_only: If True, only log errors without any user notification
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create error handler for this operation
            handler_logger_name = logger_name or f"{func.__module__}.{func.__name__}"
            error_handler = create_error_handler(handler_logger_name)
            
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                if log_only:
                    error_handler.logger.error(f"Error in {operation_name}: {e}")
                else:
                    error_handler.logger.warning(f"Error in {operation_name}: {e}")
                
                # Re-raise for caller to handle appropriately
                raise
                
        return wrapper
    return decorator


# Convenience functions for common patterns
def ui_handler(operation_name: str, user_action: str):
    """Shorthand for UI boundary decorator with common settings"""
    return ui_boundary(operation_name, user_action, notify=True)


def tools_handler(operation_name: str, user_action: str):
    """Shorthand for provider action decorator with common settings"""
    return provider_action(operation_name, user_action, notify=True)


def background_operation(operation_name: str):
    """Shorthand for safe operation decorator for background tasks"""
    return safe_operation(operation_name, log_only=True)