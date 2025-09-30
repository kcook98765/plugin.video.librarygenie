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
            'title': L(30380),  # "Confirm Action"
            'message': L(30381),  # "Are you sure?"
            'warning': L(30382)  # "This action cannot be undone"
        }
    elif action_type == "restore":
        return {
            'title': L(30316),  # "Are you sure you want to restore from this backup?"
            'message': L(30317),  # "This will replace all current lists and data."
            'warning': L(30382)  # "This action cannot be undone"
        }
    return {
        'title': L(30380),  # "Confirm Action"
        'message': L(30381),  # "Are you sure?"
        'warning': L(30383)  # "Continue anyway?"
    }

def get_operation_status_strings():
    """Get localized strings for operation status messages"""
    return {
        'success': L(30353),  # "Operation completed"
        'failed': L(30354),   # "Operation failed"
        'retry': L(30355),    # "Please try again"
        'cancelled': L(30384), # "Operation cancelled"
        'confirmed': L(30385)  # "Operation confirmed"
    }

def get_sync_status_strings():
    """Get localized strings for sync operations"""
    return {
        'status': L(30327),      # "Sync Status"
        'last_sync': L(30328),   # "Last sync"
        'sync_now': L(30329),    # "Sync now"
        'in_progress': L(30333), # "Sync in progress..."
        'completed': L(30334),   # "Sync completed successfully"
        'failed': L(30335),      # "Sync failed"
        'auth_required': L(30336) # "Authentication required"
    }

def get_backup_status_strings():
    """Get localized strings for backup operations"""
    return {
        'settings': L(30301),     # "Backup Settings"
        'create_now': L(30306),   # "Create Backup Now"
        'restore': L(30307),      # "Restore from Backup"
        'manage': L(30308),       # "Manage Backups"
        'created': L(30309),      # "Backup created successfully"
        'failed': L(30313),       # "Backup failed"
        'restore_complete': L(30314), # "Restore completed successfully"
        'restore_failed': L(30315),   # "Restore failed"
        'in_progress': L(30318),      # "Backup in progress..."
        'restore_progress': L(30319), # "Restore in progress..."
        'select_backup': L(30323),    # "Select backup to restore"
        'no_backups': L(30324),       # "No backups found"
        'not_found': L(30325),        # "Backup file not found"
        'invalid': L(30326)           # "Invalid backup file"
    }

def get_error_message_strings():
    """Get localized strings for common error messages"""
    return {
        'network': L(30356),      # "Network error"
        'timeout': L(30357),      # "Timeout error"
        'config': L(30358),       # "Configuration error"
        'database': L(30359),     # "Database error"
        'file_access': L(30360),  # "File not accessible"
        'permission': L(30361),   # "Permission denied"
        'invalid_format': L(30362), # "Invalid format"
        'service_unavailable': L(30363) # "Service unavailable"
    }

def get_progress_message_strings():
    """Get localized strings for progress messages"""
    return {
        'initializing': L(30364),     # "Initializing..."
        'processing': L(30365),       # "Processing..."
        'finalizing': L(30366),       # "Finalizing..."
        'please_wait': L(30367),      # "Please wait..."
        'in_progress': L(30368),      # "Operation in progress"
        'scanning_library': L(30369), # "Scanning library..."
        'updating_db': L(30370),      # "Updating database..."
        'validating': L(30371),       # "Validating data..."
        'connecting': L(30372),       # "Connecting to server..."
        'loading': L(30373)           # "Loading..."
    }

def get_auth_status_strings():
    """Get localized strings for authentication operations"""
    return {
        'required': L(30336),         # "Authentication required"
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
        'management': L(30337),       # "Storage Management"
        'clear_cache': L(30338),      # "Clear cache"
        'cache_cleared': L(30339),    # "Cache cleared successfully"
        'cache_failed': L(30342),     # "Failed to clear cache"
        'validate_paths': L(30343),   # "Validate storage paths"
        'validation': L(30344),       # "Storage path validation"
        'paths_valid': L(30345),      # "All paths are valid"
        'paths_invalid': L(30346),    # "Some paths are invalid"
        'cleanup_temp': L(30347),     # "Cleanup temporary files"
        'temp_cleaned': L(30348),     # "Temporary files cleaned"
        'cleanup_failed': L(30349)    # "Cleanup failed"
    }