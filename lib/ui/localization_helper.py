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
            'title': L(30122),  # "Confirm Action"
            'message': L(30123),  # "Are you sure?"
            'warning': L(30124)  # "This action cannot be undone"
        }
    elif action_type == "restore":
        return {
            'title': L(30068),  # "Are you sure you want to restore from this backup?"
            'message': L(30069),  # "This will replace all current lists and data."
            'warning': L(30124)  # "This action cannot be undone"
        }
    return {
        'title': L(30122),  # "Confirm Action"
        'message': L(30123),  # "Are you sure?"
        'warning': L(30125)  # "Continue anyway?"
    }

def get_operation_status_strings():
    """Get localized strings for operation status messages"""
    return {
        'success': L(30097),  # "Operation completed"
        'failed': L(30098),   # "Operation failed"
        'retry': L(30099),    # "Please try again"
        'cancelled': L(30126), # "Operation cancelled"
        'confirmed': L(30127)  # "Operation confirmed"
    }

def get_sync_status_strings():
    """Get localized strings for sync operations"""
    return {
        'status': L(30079),      # "Sync Status"
        'last_sync': L(30080),   # "Last sync"
        'sync_now': L(30081),    # "Sync now"
        'in_progress': L(30082), # "Sync in progress..."
        'completed': L(30083),   # "Sync completed successfully"
        'failed': L(30084),      # "Sync failed"
        'auth_required': L(30085) # "Authentication required"
    }

def get_backup_status_strings():
    """Get localized strings for backup operations"""
    return {
        'settings': L(30056),     # "Backup Settings"
        'create_now': L(30061),   # "Create Backup Now"
        'restore': L(30062),      # "Restore from Backup"
        'manage': L(30063),       # "Manage Backups"
        'created': L(30064),      # "Backup created successfully"
        'failed': L(30065),       # "Backup failed"
        'restore_complete': L(30066), # "Restore completed successfully"
        'restore_failed': L(30067),   # "Restore failed"
        'in_progress': L(30073),      # "Backup in progress..."
        'restore_progress': L(30074), # "Restore in progress..."
        'select_backup': L(30075),    # "Select backup to restore"
        'no_backups': L(30076),       # "No backups found"
        'not_found': L(30077),        # "Backup file not found"
        'invalid': L(30078)           # "Invalid backup file"
    }

def get_error_message_strings():
    """Get localized strings for common error messages"""
    return {
        'network': L(30101),      # "Network error"
        'timeout': L(30102),      # "Timeout error"
        'config': L(30103),       # "Configuration error"
        'database': L(30104),     # "Database error"
        'file_access': L(30105),  # "File not accessible"
        'permission': L(30106),   # "Permission denied"
        'invalid_format': L(30107), # "Invalid format"
        'service_unavailable': L(30108) # "Service unavailable"
    }

def get_progress_message_strings():
    """Get localized strings for progress messages"""
    return {
        'initializing': L(30109),     # "Initializing..."
        'processing': L(30113),       # "Processing..."
        'finalizing': L(30114),       # "Finalizing..."
        'please_wait': L(30115),      # "Please wait..."
        'in_progress': L(30116),      # "Operation in progress"
        'scanning_library': L(30117), # "Scanning library..."
        'updating_db': L(30118),      # "Updating database..."
        'validating': L(30119),       # "Validating data..."
        'connecting': L(30120),       # "Connecting to server..."
        'loading': L(30121)           # "Loading..."
    }

def get_auth_status_strings():
    """Get localized strings for authentication operations"""
    return {
        'required': L(30085),         # "Authentication required"
        'device_auth': 30085,      # "Device authorization"
        'pending': 30085,          # "Authorization pending"
        'complete': 30085,         # "Authorization complete"
        'failed': 30085,           # "Authorization failed"
        'token_expired': 30085,    # "Token expired"
        'refreshing': 30085,       # "Refreshing token..."
        'test_success': 30085,     # "Connection test successful"
        'test_failed': 30085       # "Connection test failed"
    }

def get_storage_strings():
    """Get localized strings for storage management"""
    return {
        'management': L(30086),       # "Storage Management"
        'clear_cache': L(30087),      # "Clear cache"
        'cache_cleared': L(30088),    # "Cache cleared successfully"
        'cache_failed': L(30089),     # "Failed to clear cache"
        'validate_paths': L(30090),   # "Validate storage paths"
        'validation': L(30091),       # "Storage path validation"
        'paths_valid': L(30092),      # "All paths are valid"
        'paths_invalid': L(30093),    # "Some paths are invalid"
        'cleanup_temp': L(30094),     # "Cleanup temporary files"
        'temp_cleaned': L(30095),     # "Temporary files cleaned"
        'cleanup_failed': L(30096)    # "Cleanup failed"
    }