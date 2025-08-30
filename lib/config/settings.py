#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 10 Import/Export Settings
Settings for backup management and import/export functionality
"""

from typing import Dict, Any, Optional, List, Tuple
from ..utils.logger import get_logger


def get_import_export_settings() -> Dict[str, Any]:
    """Get all import/export related settings with defaults"""
    return {
        # Export Settings
        "export_default_types": ["lists", "list_items"],  # Default export selection
        "export_include_library": False,  # Include library snapshot by default
        "export_include_favorites": True,  # Include favorites mirror by default
        "export_confirm_overwrite": True,  # Confirm before overwriting files

        # Import Settings
        "import_show_preview": True,  # Show preview dialog before importing
        "import_confirm_large": True,  # Confirm imports over size threshold
        "import_max_size_mb": 50,  # Maximum import file size
        "import_skip_duplicates": True,  # Skip duplicate items during import

        # Backup Settings
        "backup_enabled": False,  # Automatic backups disabled by default
        "backup_interval": "weekly",  # daily, weekly
        "backup_retention_count": 5,  # Keep last N backups
        "backup_include_favorites": True,  # Include favorites in backups
        "backup_include_library": False,  # Include library snapshot in backups
        "backup_run_on_startup": False,  # Check for backup on addon startup

        # File Management Settings
        "storage_cleanup_enabled": True,  # Enable automatic cleanup
        "storage_temp_retention_hours": 24,  # Keep temp files for 24 hours
        "storage_validate_paths": True,  # Validate file paths for security

        # Performance Settings
        "export_chunk_size": 1000,  # Items per chunk for large exports
        "import_batch_size": 500,  # Items per transaction for imports
        "backup_ui_updates": True,  # Show progress during backup operations

        # Background Service Settings
        "background_interval_minutes": 5,  # Background service interval (minimum 1 minute)
        "track_library_changes": False,  # Monitor library for changes
        "background_token_refresh": True,  # Enable background token refresh
    }


def get_phase11_ui_settings() -> Dict[str, Any]:
    """Get Phase 11 UI and display settings with defaults"""
    return {
        # UI Density Settings
        "ui_density": "compact",  # compact, detailed, art_heavy
        "artwork_preference": "poster",  # poster, fanart
        "show_secondary_label": True,  # Show year in secondary label
        "show_plot_in_detailed": True,  # Show plot in detailed mode
        "fallback_icon": "DefaultVideo.png",  # Default icon for missing artwork

        # List Display Settings
        "items_per_page": 50,  # Items per page in lists
        "sort_method_default": "title_asc",  # Default sort method
        "show_item_counts": True,  # Show item counts in list names

        # Playback Settings
        "auto_resume": True,  # Automatically resume movies with resume points
        "show_resume_dialog": True,  # Show resume confirmation dialog
        "queue_notification": True,  # Show notification when adding to queue

        # Performance Settings
        "preload_artwork": True,  # Preload artwork for better performance
        "thumbnail_quality": "medium",  # low, medium, high
        "cache_listitem_data": True,  # Cache ListItem data for performance
    }


def get_phase12_remote_settings() -> Dict[str, Any]:
    """Get Phase 12 remote integration settings with defaults"""
    return {
        # Master Controls
        "remote_enabled": False,  # Master toggle - off by default
        "remote_base_url": "",  # Base URL for remote API
        "remote_api_key": "",  # API key/token for authentication

        # Connection Settings
        "remote_timeout_seconds": 10,  # Request timeout
        "remote_retry_count": 2,  # Number of retries on failure
        "remote_rate_limit_ms": 100,  # Milliseconds between requests

        # Feature Toggles
        "remote_search_enabled": True,  # Use remote for search results
        "remote_lists_enabled": True,  # Enable remote lists browsing
        "remote_show_nonlocal": False,  # Show items not in local library
        "remote_cache_enabled": True,  # Cache remote results locally

        # Cache Settings
        "remote_cache_ttl_hours": 6,  # Cache TTL in hours
        "remote_cache_max_entries": 1000,  # Maximum cache entries
        "remote_page_size": 50,  # Results per page for remote calls

        # Privacy & Behavior
        "remote_send_minimal_data": True,  # Send only necessary data
        "remote_fallback_on_error": True,  # Fall back to local on errors
        "remote_log_requests": False,  # Log remote requests (debug only)
    }


def get_setting_descriptions() -> Dict[str, str]:
    """Get user-friendly descriptions for settings"""
    return {
        # Export Descriptions
        "export_default_types": "Default data types to include when exporting",
        "export_include_library": "Include complete library snapshot in exports",
        "export_include_favorites": "Include Kodi favorites mirror in exports",
        "export_confirm_overwrite": "Ask before overwriting existing export files",

        # Import Descriptions
        "import_show_preview": "Show preview of changes before importing data",
        "import_confirm_large": "Ask for confirmation when importing large files",
        "import_max_size_mb": "Maximum allowed import file size in megabytes",
        "import_skip_duplicates": "Skip items that are already in lists during import",

        # Backup Descriptions
        "backup_enabled": "Enable automatic scheduled backups",
        "backup_interval": "How often to create automatic backups",
        "backup_retention_count": "Number of backup files to keep",
        "backup_include_favorites": "Include favorites data in automatic backups",
        "backup_include_library": "Include library snapshot in automatic backups",
        "backup_run_on_startup": "Check for scheduled backup when addon starts",

        # File Management Descriptions
        "storage_cleanup_enabled": "Automatically clean up old temporary files",
        "storage_temp_retention_hours": "Hours to keep temporary files before cleanup",
        "storage_validate_paths": "Validate file paths to prevent security issues",

        # Performance Descriptions
        "export_chunk_size": "Number of items to process at once during export",
        "import_batch_size": "Number of items to import in each database transaction",
        "backup_ui_updates": "Show progress information during backup operations",

        # Background Service Descriptions
        "background_interval_minutes": "How often the background service runs (minimum 1 minute)",
        "track_library_changes": "Monitor Kodi library for changes in the background",
        "background_token_refresh": "Automatically refresh authentication tokens",
    }


def validate_setting_value(setting_key: str, value: Any) -> Tuple[bool, str]:
    """Validate a setting value, return (is_valid, error_message)"""
    try:
        if setting_key == "backup_interval":
            if value not in ["daily", "weekly"]:
                return False, "Backup interval must be 'daily' or 'weekly'"

        elif setting_key == "backup_retention_count":
            if not isinstance(value, int) or value < 1 or value > 50:
                return False, "Retention count must be between 1 and 50"

        elif setting_key == "import_max_size_mb":
            if not isinstance(value, int) or value < 1 or value > 500:
                return False, "Max import size must be between 1 and 500 MB"

        elif setting_key == "storage_temp_retention_hours":
            if not isinstance(value, int) or value < 1 or value > 168:  # Max 1 week
                return False, "Temp retention must be between 1 and 168 hours"

        elif setting_key == "export_chunk_size":
            if not isinstance(value, int) or value < 100 or value > 10000:
                return False, "Export chunk size must be between 100 and 10,000"

        elif setting_key == "import_batch_size":
            if not isinstance(value, int) or value < 50 or value > 5000:
                return False, "Import batch size must be between 50 and 5,000"

        elif setting_key == "export_default_types":
            if not isinstance(value, list):
                return False, "Export types must be a list"
            valid_types = {"lists", "list_items", "favorites", "library_snapshot"}
            if not all(t in valid_types for t in value):
                return False, f"Invalid export types. Valid: {valid_types}"

        elif setting_key == "background_interval_minutes":
            if not isinstance(value, int) or value < 1 or value > 1440:  # Max 24 hours
                return False, "Background interval must be between 1 and 1440 minutes"

        return True, ""

    except Exception as e:
        return False, f"Validation error: {e}"


class ImportExportSettings:
    """Helper class for managing import/export settings"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = get_logger(__name__)
        self.defaults = get_import_export_settings()

    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value with fallback to default"""
        return self.config.get(key, self.defaults.get(key, default))

    def set(self, key: str, value: Any) -> bool:
        """Set setting value with validation"""
        is_valid, error_msg = validate_setting_value(key, value)
        if not is_valid:
            self.logger.error(f"Invalid setting value for {key}: {error_msg}")
            return False

        self.config.set(key, value)
        return True

    def get_export_defaults(self) -> List[str]:
        """Get default export types"""
        return self.get("export_default_types", ["lists", "list_items"])

    def get_backup_config(self) -> Dict[str, Any]:
        """Get backup configuration"""
        return {
            "enabled": self.get("backup_enabled", False),
            "interval": self.get("backup_interval", "weekly"),
            "retention_count": self.get("backup_retention_count", 5),
            "include_favorites": self.get("backup_include_favorites", True),
            "include_library": self.get("backup_include_library", False),
            "run_on_startup": self.get("backup_run_on_startup", False)
        }

    def get_import_config(self) -> Dict[str, Any]:
        """Get import configuration"""
        return {
            "show_preview": self.get("import_show_preview", True),
            "confirm_large": self.get("import_confirm_large", True),
            "max_size_mb": self.get("import_max_size_mb", 50),
            "skip_duplicates": self.get("import_skip_duplicates", True),
            "batch_size": self.get("import_batch_size", 500)
        }

    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage management configuration"""
        return {
            "cleanup_enabled": self.get("storage_cleanup_enabled", True),
            "temp_retention_hours": self.get("storage_temp_retention_hours", 24),
            "validate_paths": self.get("storage_validate_paths", True)
        }

    def reset_to_defaults(self, keys: Optional[List[str]] = None):
        """Reset specified keys to default values"""
        if keys is None:
            keys = list(self.defaults.keys())

        for key in keys:
            if key in self.defaults:
                self.config.set(key, self.defaults[key])
                self.logger.info(f"Reset {key} to default value")


def get_import_export_settings_instance(config_manager):
    """Get ImportExportSettings instance with config manager"""
    return ImportExportSettings(config_manager)