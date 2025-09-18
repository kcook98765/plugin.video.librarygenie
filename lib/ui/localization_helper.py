#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Localization Helper
Provides helper functions for common localization patterns
"""

from lib.ui.localization import L

def get_confirmation_dialog_strings(action_type: str = "delete"):
    """Get localized strings for confirmation dialogs"""
    if action_type == "delete":
        return {
            'title': L(94600),  # "Confirm Action"
            'message': L(94601),  # "Are you sure?"
            'warning': L(94602)  # "This action cannot be undone"
        }
    elif action_type == "restore":
        return {
            'title': L(94013),  # "Are you sure you want to restore from this backup?"
            'message': L(94014),  # "This will replace all current lists and data."
            'warning': L(94602)  # "This action cannot be undone"
        }
    return {
        'title': L(94600),  # "Confirm Action"
        'message': L(94601),  # "Are you sure?"
        'warning': L(94603)  # "Continue anyway?"
    }

def get_operation_status_strings():
    """Get localized strings for operation status messages"""
    return {
        'success': L(94300),  # "Operation completed"
        'failed': L(94301),   # "Operation failed"
        'retry': L(94302),    # "Please try again"
        'cancelled': L(94604), # "Operation cancelled"
        'confirmed': L(94605)  # "Operation confirmed"
    }

def get_sync_status_strings():
    """Get localized strings for sync operations"""
    return {
        'status': L(94100),      # "Sync Status"
        'last_sync': L(94101),   # "Last sync"
        'sync_now': L(94102),    # "Sync now"
        'in_progress': L(94103), # "Sync in progress..."
        'completed': L(94104),   # "Sync completed successfully"
        'failed': L(94105),      # "Sync failed"
        'auth_required': L(94106) # "Authentication required"
    }

def get_backup_status_strings():
    """Get localized strings for backup operations"""
    return {
        'settings': L(94001),     # "Backup Settings"
        'create_now': L(94006),   # "Create Backup Now"
        'restore': L(94007),      # "Restore from Backup"
        'manage': L(94008),       # "Manage Backups"
        'created': L(94009),      # "Backup created successfully"
        'failed': L(94010),       # "Backup failed"
        'restore_complete': L(94011), # "Restore completed successfully"
        'restore_failed': L(94012),   # "Restore failed"
        'in_progress': L(94015),      # "Backup in progress..."
        'restore_progress': L(94016), # "Restore in progress..."
        'select_backup': L(94017),    # "Select backup to restore"
        'no_backups': L(94018),       # "No backups found"
        'not_found': L(94019),        # "Backup file not found"
        'invalid': L(94020)           # "Invalid backup file"
    }

def get_error_message_strings():
    """Get localized strings for common error messages"""
    return {
        'network': L(94303),      # "Network error"
        'timeout': L(94304),      # "Timeout error"
        'config': L(94305),       # "Configuration error"
        'database': L(94306),     # "Database error"
        'file_access': L(94307),  # "File not accessible"
        'permission': L(94308),   # "Permission denied"
        'invalid_format': L(94309), # "Invalid format"
        'service_unavailable': L(94310) # "Service unavailable"
    }

def get_progress_message_strings():
    """Get localized strings for progress messages"""
    return {
        'initializing': L(94400),     # "Initializing..."
        'processing': L(94401),       # "Processing..."
        'finalizing': L(94402),       # "Finalizing..."
        'please_wait': L(94403),      # "Please wait..."
        'in_progress': L(94404),      # "Operation in progress"
        'scanning_library': L(94405), # "Scanning library..."
        'updating_db': L(94406),      # "Updating database..."
        'validating': L(94407),       # "Validating data..."
        'connecting': L(94408),       # "Connecting to server..."
        'loading': L(94409)           # "Loading..."
    }

def get_auth_status_strings():
    """Get localized strings for authentication operations"""
    return {
        'required': L(94106),         # "Authentication required"
        'device_auth': L(94107),      # "Device authorization"
        'pending': L(94108),          # "Authorization pending"
        'complete': L(94109),         # "Authorization complete"
        'failed': L(94110),           # "Authorization failed"
        'token_expired': L(94111),    # "Token expired"
        'refreshing': L(94112),       # "Refreshing token..."
        'test_success': L(94113),     # "Connection test successful"
        'test_failed': L(94114)       # "Connection test failed"
    }

def get_storage_strings():
    """Get localized strings for storage management"""
    return {
        'management': L(94200),       # "Storage Management"
        'clear_cache': L(94201),      # "Clear cache"
        'cache_cleared': L(94202),    # "Cache cleared successfully"
        'cache_failed': L(94203),     # "Failed to clear cache"
        'validate_paths': L(94204),   # "Validate storage paths"
        'validation': L(94205),       # "Storage path validation"
        'paths_valid': L(94206),      # "All paths are valid"
        'paths_invalid': L(94207),    # "Some paths are invalid"
        'cleanup_temp': L(94208),     # "Cleanup temporary files"
        'temp_cleaned': L(94209),     # "Temporary files cleaned"
        'cleanup_failed': L(94210)    # "Cleanup failed"
    }