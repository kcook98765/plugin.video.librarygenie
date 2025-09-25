#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Error Classification System
Custom exception types to drive appropriate error handling responses
"""

from typing import Optional


class LibraryGenieError(Exception):
    """Base exception for all LibraryGenie-specific errors"""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        """
        Initialize LibraryGenie error
        
        Args:
            message: Technical error message for logging
            user_message: User-friendly message for notifications (optional)
        """
        super().__init__(message)
        self.message = message
        self.user_message = user_message or message


class UserError(LibraryGenieError):
    """
    Expected user errors that should show warning notifications
    Examples: validation failures, missing data, invalid input
    """
    pass


class CancelledError(LibraryGenieError):
    """
    User-initiated cancellation - should log debug and show no notification
    Examples: user cancelled dialog, operation interrupted by user choice
    """
    
    def __init__(self, message: str = "Operation cancelled by user"):
        super().__init__(message, user_message=None)


class ValidationError(UserError):
    """Input validation or data validation errors"""
    pass


class NotFoundError(UserError):
    """Resource not found errors"""
    pass


class AlreadyExistsError(UserError):
    """Resource already exists errors"""
    pass


class ConfigurationError(UserError):
    """Configuration or setup errors"""
    pass


class AuthenticationError(UserError):
    """Authentication or authorization errors"""
    pass


class NetworkError(LibraryGenieError):
    """Network-related errors that may be temporary"""
    pass


class DatabaseError(LibraryGenieError):
    """Database operation errors"""
    pass


# Convenience functions for common error patterns
def cancel_operation(message: str = "Operation cancelled by user") -> CancelledError:
    """Create a cancellation error"""
    return CancelledError(message)


def user_error(message: str, user_message: Optional[str] = None) -> UserError:
    """Create a user error with optional friendly message"""
    return UserError(message, user_message)


def validation_error(message: str, user_message: Optional[str] = None) -> ValidationError:
    """Create a validation error"""
    return ValidationError(message, user_message)


def not_found(resource: str, user_message: Optional[str] = None) -> NotFoundError:
    """Create a not found error"""
    message = f"{resource} not found"
    return NotFoundError(message, user_message or f"Could not find {resource.lower()}")


def already_exists(resource: str, user_message: Optional[str] = None) -> AlreadyExistsError:
    """Create an already exists error"""
    message = f"{resource} already exists"
    return AlreadyExistsError(message, user_message or f"{resource} already exists")