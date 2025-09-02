#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Localization Helper
Provides helper functions for common localization patterns
"""

from .localization import L

def get_confirmation_dialog_strings(action_type: str = "delete"):
    """Get localized strings for confirmation dialogs"""
    if action_type == "delete":
        return {
            'title': L(34600),  # "Confirm Action"
            'message': L(34601),  # "Are you sure?"
            'warning': L(34602)  # "This action cannot be undone"
        }
    elif action_type == "restore":
        return {
            'title': L(34013),  # "Are you sure you want to restore from this backup?"
            'message': L(34014),  # "This will replace all current lists and data."
            'warning': L(34602)  # "This action cannot be undone"
        }
    return {
        'title': L(34600),  # "Confirm Action"
        'message': L(34601),  # "Are you sure?"
        'warning': L(34603)  # "Continue anyway?"
    }

def get_operation_status_strings():
    """Get localized strings for operation status messages"""
    return {
        'success': L(34300),  # "Operation completed"
        'failed': L(34301),   # "Operation failed"
        'retry': L(34302),    # "Please try again"
        'cancelled': L(34604), # "Operation cancelled"
        'confirmed': L(34605)  # "Operation confirmed"
    }

def get_sync_status_strings():
    """Get localized strings for sync operations"""
    return {
        'status': L(34100),      # "Sync Status"
        'last_sync': L(34101),   # "Last sync"
        'sync_now': L(34102),    # "Sync now"
        'in_progress': L(34103), # "Sync in progress..."
        'completed': L(34104),   # "Sync completed successfully"
        'failed': L(34105),      # "Sync failed"
        'auth_required': L(34106) # "Authentication required"
    }

def get_backup_status_strings():
    """Get localized strings for backup operations"""
    return {
        'settings': L(34001),     # "Backup Settings"
        'create_now': L(34006),   # "Create Backup Now"
        'restore': L(34007),      # "Restore from Backup"
        'manage': L(34008),       # "Manage Backups"
        'created': L(34009),      # "Backup created successfully"
        'failed': L(34010),       # "Backup failed"
        'restore_complete': L(34011), # "Restore completed successfully"
        'restore_failed': L(34012),   # "Restore failed"
        'in_progress': L(34015),      # "Backup in progress..."
        'restore_progress': L(34016), # "Restore in progress..."
        'select_backup': L(34017),    # "Select backup to restore"
        'no_backups': L(34018),       # "No backups found"
        'not_found': L(34019),        # "Backup file not found"
        'invalid': L(34020)           # "Invalid backup file"
    }

def get_error_message_strings():
    """Get localized strings for common error messages"""
    return {
        'network': L(34303),      # "Network error"
        'timeout': L(34304),      # "Timeout error"
        'config': L(34305),       # "Configuration error"
        'database': L(34306),     # "Database error"
        'file_access': L(34307),  # "File not accessible"
        'permission': L(34308),   # "Permission denied"
        'invalid_format': L(34309), # "Invalid format"
        'service_unavailable': L(34310) # "Service unavailable"
    }

def get_progress_message_strings():
    """Get localized strings for progress messages"""
    return {
        'initializing': L(34400),     # "Initializing..."
        'processing': L(34401),       # "Processing..."
        'finalizing': L(34402),       # "Finalizing..."
        'please_wait': L(34403),      # "Please wait..."
        'in_progress': L(34404),      # "Operation in progress"
        'scanning_library': L(34405), # "Scanning library..."
        'updating_db': L(34406),      # "Updating database..."
        'validating': L(34407),       # "Validating data..."
        'connecting': L(34408),       # "Connecting to server..."
        'loading': L(34409)           # "Loading..."
    }

def get_auth_status_strings():
    """Get localized strings for authentication operations"""
    return {
        'required': L(34106),         # "Authentication required"
        'device_auth': L(34107),      # "Device authorization"
        'pending': L(34108),          # "Authorization pending"
        'complete': L(34109),         # "Authorization complete"
        'failed': L(34110),           # "Authorization failed"
        'token_expired': L(34111),    # "Token expired"
        'refreshing': L(34112),       # "Refreshing token..."
        'test_success': L(34113),     # "Connection test successful"
        'test_failed': L(34114)       # "Connection test failed"
    }

def get_storage_strings():
    """Get localized strings for storage management"""
    return {
        'management': L(34200),       # "Storage Management"
        'clear_cache': L(34201),      # "Clear cache"
        'cache_cleared': L(34202),    # "Cache cleared successfully"
        'cache_failed': L(34203),     # "Failed to clear cache"
        'validate_paths': L(34204),   # "Validate storage paths"
        'validation': L(34205),       # "Storage path validation"
        'paths_valid': L(34206),      # "All paths are valid"
        'paths_invalid': L(34207),    # "Some paths are invalid"
        'cleanup_temp': L(34208),     # "Cleanup temporary files"
        'temp_cleaned': L(34209),     # "Temporary files cleaned"
        'cleanup_failed': L(34210)    # "Cleanup failed"
    }