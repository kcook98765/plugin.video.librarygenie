
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Localization Helper
Provides common localization patterns and utilities
"""

from .localization import L

class LocalizationHelper:
    """Helper class for common localization patterns"""
    
    @staticmethod
    def get_error_message(error_type: str, details: str = None) -> str:
        """Get localized error message with optional details"""
        error_map = {
            'network': L(34303),      # "Network error"
            'timeout': L(34304),      # "Timeout error"
            'config': L(34305),       # "Configuration error"
            'database': L(34306),     # "Database error"
            'file': L(34307),         # "File not accessible"
            'permission': L(34308),   # "Permission denied"
            'format': L(34309),       # "Invalid format"
            'service': L(34310),      # "Service unavailable"
        }
        
        base_msg = error_map.get(error_type, L(34301))  # "Operation failed"
        
        if details:
            return f"{base_msg}: {details}"
        return base_msg
    
    @staticmethod
    def get_progress_message(progress_type: str) -> str:
        """Get localized progress message"""
        progress_map = {
            'init': L(34400),         # "Initializing..."
            'process': L(34401),      # "Processing..."
            'finalize': L(34402),     # "Finalizing..."
            'wait': L(34403),         # "Please wait..."
            'scan': L(34405),         # "Scanning library..."
            'update': L(34406),       # "Updating database..."
            'validate': L(34407),     # "Validating data..."
            'connect': L(34408),      # "Connecting to server..."
            'load': L(34409),         # "Loading..."
        }
        
        return progress_map.get(progress_type, L(34404))  # "Operation in progress"
    
    @staticmethod
    def get_confirmation_dialog(action_type: str) -> tuple:
        """Get localized confirmation dialog title and message"""
        if action_type == 'delete':
            return L(34600), L(34602)  # "Confirm Action", "This action cannot be undone"
        elif action_type == 'restore':
            return L(34013), L(34014)  # Backup restore confirmation
        else:
            return L(34600), L(34601)  # "Confirm Action", "Are you sure?"
    
    @staticmethod
    def format_success_message(operation: str, item_name: str = None) -> str:
        """Format a success message for common operations"""
        if operation == 'backup':
            return L(34009)  # "Backup created successfully"
        elif operation == 'restore':
            return L(34011)  # "Restore completed successfully"
        elif operation == 'sync':
            return L(34104)  # "Sync completed successfully"
        elif operation == 'add_to_list' and item_name:
            return L(31102)  # "Added to list successfully"
        else:
            return L(34300)  # "Operation completed"
