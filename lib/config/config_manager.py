#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Configuration Manager
Reads Kodi settings and manages addon configuration
"""

import xbmcaddon
import threading
from typing import Optional, Dict, Any


class ConfigManager:
    """Manages addon configuration and settings"""

    def __init__(self):
        self._addon = xbmcaddon.Addon()
        
        # Thread-safe cache for settings
        self._cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()

        # Default configuration matching Phase 2-3 requirements
        self._defaults = {
            # General settings
            "confirm_destructive_actions": True,
            "track_library_changes": True,
            "soft_delete_removed_items": True,
            "default_list_id": "",
            "quick_add_enabled": False,
            "show_missing_indicators": True,
            "show_unmapped_favorites": False,
            "sync_tv_episodes": False,  # Sync TV episodes during library scan
            
            # Library sync settings
            "sync_movies": True,
            "first_run_completed": False,
            "sync_frequency_hours": 1,
            "last_sync_time": 0,
            
            # Search settings
            "search_page_size": 200,
            
            # Pagination settings  
            "list_pagination_mode": "auto",  # "auto" or "manual"
            "list_manual_page_size": 50,     # Manual page size when mode is "manual"
            
            # Background service settings
            "enable_background_service": True,
            "background_interval": 5,
            
            # Favorites settings
            "favorites_integration_enabled": False,
            "favorites_scan_interval": 30,
            "enable_batch_processing": True,
            
            # Advanced settings
            "jsonrpc_page_size": 200,  # Items per JSON-RPC page
            "jsonrpc_timeout": 10,
            "database_batch_size": 200,
            "database_busy_timeout": 3000,

            # Remote service settings
            "remote_server_url": "",  # Blank by default for repo safety
            "device_name": "Kodi",
            "auth_polling_interval": 5,  # Align with minimum clamp value
            "enable_auto_token_refresh": True,
            "use_native_kodi_info": True,
            "enable_background_token_refresh": True,
            "remote_enabled": False,
            "remote_timeout": 30,
            "remote_max_retries": 3,
            "remote_fallback_to_local": True,
            "remote_cache_duration": 300,
            
            # AI Search settings
            "ai_search_api_key": "",
            "ai_search_activated": False,
            "ai_search_sync_interval": 1,
            
            # Backup settings
            "enable_automatic_backups": False,
            "backup_interval": "weekly",
            "backup_storage_type": "local",
            "backup_local_path": "",
            "backup_enabled": False,
            "backup_retention_count": 5,
            "backup_retention_policy": "count",
            "backup_include_settings": True,
            "backup_include_non_library": False,
            
            # ShortList integration settings
            "import_from_shortlist": False,
            "clear_before_import": False,
            
            # Initialization state
            "initial_sync_requested": False,
            
            # Authentication tokens
            "access_token": "",
            "refresh_token": "",
            "token_expires_at": "",
        }

    def get(self, key, default=None):
        """Get configuration value with safe fallback and caching"""
        # Check cache first
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
        
        try:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            
            # Always try string first as it's most compatible
            value = self._addon.getSettingString(key)
            
            if value:
                result = value
            else:
                result = self._defaults.get(key, default)
            
            # Cache the result
            with self._cache_lock:
                self._cache[key] = result
            
            return result
        except Exception as e:
            # Return default value if setting read fails
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            logger.error("Exception getting setting '%s': %s", key, e)
            fallback = self._defaults.get(key, default)
            
            # Cache the fallback to prevent repeated exceptions
            with self._cache_lock:
                self._cache[key] = fallback
            
            return fallback

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value with caching"""
        # Check cache first
        cache_key = f"bool:{key}"
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        try:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            
            # Check what type we think this setting should be
            expected_type = self._get_setting_type(key)
            
            # First try getSettingBool
            result = self._addon.getSettingBool(key)
            
            # Cache the result
            with self._cache_lock:
                self._cache[cache_key] = result
            
            return result
        except Exception as e:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            logger.error("getSettingBool('%s') failed with exception: %s: %s", key, type(e).__name__, e)
            
            try:
                # Fallback to string and convert
                str_value = self._addon.getSettingString(key)
                
                if str_value.lower() in ('true', '1', 'yes'):
                    result = True
                elif str_value.lower() in ('false', '0', 'no', ''):
                    result = False
                else:
                    result = self._defaults.get(key, default)
                
                # Cache the result
                with self._cache_lock:
                    self._cache[cache_key] = result
                
                return result
            except Exception as e2:
                # Use defaults dict fallback if available, otherwise use provided default
                from ..utils.kodi_log import get_kodi_logger
                logger = get_kodi_logger('lib.config.config_manager')
                logger.error("String fallback also failed for '%s': %s: %s", key, type(e2).__name__, e2)
                fallback = self._defaults.get(key, default)

                # Cache the fallback
                with self._cache_lock:
                    self._cache[cache_key] = fallback

                return fallback

    def get_int(self, key, default=0):
        """Get integer setting with safe fallback and caching"""
        # Check cache first
        cache_key = f"int:{key}"
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        try:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            
            # First try getSettingInt
            result = self._addon.getSettingInt(key)
            
            # Cache the result
            with self._cache_lock:
                self._cache[cache_key] = result
            
            return result
        except Exception as e:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            logger.warning("getSettingInt('%s') failed: %s", key, e)
            
            try:
                # Fallback to string and convert
                str_value = self._addon.getSettingString(key)
                
                if str_value and str_value.strip():
                    result = int(str_value.strip())
                else:
                    result = self._defaults.get(key, default)
                
                # Cache the result
                with self._cache_lock:
                    self._cache[cache_key] = result
                
                return result
            except (ValueError, TypeError) as e2:
                from ..utils.kodi_log import get_kodi_logger
                logger = get_kodi_logger('lib.config.config_manager')
                logger.error("String conversion failed for '%s': %s", key, e2)
                fallback = self._defaults.get(key, default)

                # Cache the fallback
                with self._cache_lock:
                    self._cache[cache_key] = fallback

                return fallback

    def get_float(self, key, default=0.0):
        """Get float setting with safe fallback and caching"""
        # Check cache first
        cache_key = f"float:{key}"
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        try:
            result = self._addon.getSettingNumber(key)
            
            # Cache the result
            with self._cache_lock:
                self._cache[cache_key] = result
            
            return result
        except Exception:
            fallback = self._defaults.get(key, default)
            
            # Cache the fallback
            with self._cache_lock:
                self._cache[cache_key] = fallback
            
            return fallback

    def set(self, key, value):
        """Set configuration value with write-through caching"""
        try:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            
            setting_type = self._get_setting_type(key)
            
            if setting_type == "bool":
                # Coerce value to boolean to prevent "Invalid setting type" errors
                bool_value = bool(value) if not isinstance(value, str) else value.lower() in ('true', '1', 'yes')
                result = self._addon.setSettingBool(key, bool_value)
                if result:
                    # Update cache with the typed value
                    with self._cache_lock:
                        self._cache[f"bool:{key}"] = bool_value
                        # Also update string cache for get() method
                        self._cache[key] = str(bool_value).lower()
                return result
            elif setting_type == "int":
                # Coerce value to integer to prevent "Invalid setting type" errors
                int_value = int(value)
                result = self._addon.setSettingInt(key, int_value)
                if result:
                    # Update cache with the typed value
                    with self._cache_lock:
                        self._cache[f"int:{key}"] = int_value
                        # Also update string cache for get() method
                        self._cache[key] = str(int_value)
                return result
            elif setting_type == "number":
                # Coerce value to float to prevent "Invalid setting type" errors
                float_value = float(value)
                result = self._addon.setSettingNumber(key, float_value)
                if result:
                    # Update cache with the typed value
                    with self._cache_lock:
                        self._cache[f"float:{key}"] = float_value
                        # Also update string cache for get() method
                        self._cache[key] = str(float_value)
                return result
            else:
                result = self._addon.setSettingString(key, str(value))
                if result:
                    # Update cache with the string value
                    with self._cache_lock:
                        self._cache[key] = str(value)
                return result
        except Exception as e:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            logger.error("Exception setting '%s' = '%s': %s", key, value, e)
            return False

    def invalidate(self, key: Optional[str] = None):
        """Invalidate cache entries
        
        Args:
            key: Specific key to invalidate, or None to clear all cache
        """
        with self._cache_lock:
            if key is None:
                # Clear all cache
                self._cache.clear()
            else:
                # Remove specific key and its typed variants
                keys_to_remove = []
                for cache_key in self._cache:
                    if cache_key == key or cache_key.endswith(f":{key}"):
                        keys_to_remove.append(cache_key)
                
                for cache_key in keys_to_remove:
                    self._cache.pop(cache_key, None)

    def reload(self):
        """Reload all settings by clearing cache completely"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("Reloading all settings cache")
        self.invalidate()

    def _get_setting_type(self, key):
        """Determine setting type based on key name"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        
        # Comprehensive list of all boolean settings
        bool_settings = [
            # General settings
            "confirm_destructive_actions",
            "track_library_changes",
            "soft_delete_removed_items",
            "quick_add_enabled",
            "show_missing_indicators",
            "show_unmapped_favorites",
            # Library sync settings
            "sync_movies",
            "sync_tv_episodes",
            "first_run_completed",
            # Background service settings
            "enable_background_service",
            "enable_batch_processing",
            # Favorites settings
            "favorites_integration_enabled",
            # Remote service settings
            "enable_auto_token_refresh",
            "use_native_kodi_info",
            "enable_background_token_refresh",
            "remote_enabled",
            "remote_fallback_to_local",
            # AI Search settings
            "ai_search_activated",
            # Backup boolean settings
            "enable_automatic_backups",
            "backup_enabled",
            "backup_include_settings",
            "backup_include_non_library",
            "backup_include_folders",
            # ShortList integration settings
            "import_from_shortlist",
            "clear_before_import",
            # Legacy/other boolean settings
            "favorites_batch_processing",
            "shortlist_clear_before_import",
            "background_token_refresh",
            "info_hijack_enabled",
            # Initialization state settings
            "initial_sync_requested",
        ]
        int_settings = [
            # Search settings
            "search_page_size", "search_history_days",
            # Sync settings  
            "last_sync_time", "sync_frequency_hours",
            # Advanced settings
            "jsonrpc_page_size", "jsonrpc_timeout_seconds",
            "db_batch_size", "db_busy_timeout_ms",
            # Remote service settings
            "auth_poll_seconds", "background_interval_minutes",
            # AI Search settings
            "ai_search_sync_interval", 
            # Backup integer settings
            "backup_interval", "backup_retention_count", "backup_storage_type",
            # Pagination settings
            "list_pagination_mode", "list_manual_page_size",
        ]
        float_settings = []

        # Select settings (stored as integer indexes) 
        # Note: These are already handled as integers above
        select_settings = []

        # String settings
        string_settings = [
            # General settings
            "default_list_id", "device_name", "export_location",
            # Remote settings  
            "remote_server_url",
            # Backup settings
            "backup_storage_location", "last_backup_time",
            # AI Search settings
            "ai_search_api_key",
        ]


        if key in bool_settings:
            return "bool"
        elif key in int_settings:
            return "int"
        elif key in float_settings:
            return "number"
        elif key in select_settings:
            return "int"  # Select controls store integer indexes
        elif key in string_settings:
            return "string"
        else:
            logger.warning("Setting '%s' not found in any type list, defaulting to string type", key)
            return "string"


    def get_default_list_id(self):
        """Get default list ID with fallback logic (Phase 2)"""
        stored_id = self.get("default_list_id", "")

        if stored_id:
            # Verify the stored ID still points to a valid list
            try:
                from ..data import QueryManager
                query_manager = QueryManager()

                # Check if list exists
                lists = query_manager.get_user_lists()
                for user_list in lists:
                    if str(user_list.get('id')) == str(stored_id):
                        return stored_id

            except Exception:
                # If verification fails, continue to fallback
                pass

        # Fallback: find alphabetically first list (don't write back silently)
        try:
            from ..data import QueryManager
            query_manager = QueryManager()

            lists = query_manager.get_user_lists()
            if lists:
                # Sort by name and return first
                sorted_lists = sorted(lists, key=lambda x: x.get('name', '').lower())
                return str(sorted_lists[0].get('id'))

        except Exception:
            pass

        # No lists available
        return None

    def set_default_list_id(self, list_id):
        """Set default list ID (Phase 2)"""
        if list_id:
            return self.set("default_list_id", str(list_id))
        else:
            return self.set("default_list_id", "")

    # Phase 3: Advanced settings with clamping

    def get_jsonrpc_page_size(self) -> int:
        """Get JSON-RPC page size"""
        return self.get_int("jsonrpc_page_size", 200)

    def get_jsonrpc_timeout_seconds(self):
        """Get JSON-RPC timeout with safe clamping (5-30 seconds, default 10)"""
        timeout = self.get("jsonrpc_timeout_seconds", 10)
        return max(5, min(30, timeout))

    def get_db_batch_size(self) -> int:
        """Get database batch size for operations"""
        return self.get_int("db_batch_size", 200)

    def get_db_busy_timeout_ms(self) -> int:
        """Get database busy timeout in milliseconds"""
        return self.get_int("db_busy_timeout_ms", 3000)


    def enable_favorites_integration(self) -> bool:
        """Enable favorites integration and trigger immediate scan"""
        try:
            # Set the setting
            success = self.set("favorites_integration_enabled", True)

            if success:
                # Trigger immediate scan
                try:
                    from .favorites_helper import on_favorites_integration_enabled
                    on_favorites_integration_enabled()
                except Exception as e:
                    # Log but don't fail the setting change
                    from ..utils.kodi_log import get_kodi_logger
                    logger = get_kodi_logger('lib.config.config_manager')
                    logger.warning("Failed to trigger immediate favorites scan: %s", e)

            return success

        except Exception:
            return False

    def enable_tv_episode_sync(self) -> bool:
        """Enable TV episode sync and trigger immediate library scan"""
        try:
            # Set the setting
            success = self.set("sync_tv_episodes", True)

            if success:
                # Trigger immediate library scan with TV episodes
                try:
                    from .tv_sync_helper import on_tv_episode_sync_enabled
                    on_tv_episode_sync_enabled()
                except Exception as e:
                    # Log but don't fail the setting change
                    from ..utils.kodi_log import get_kodi_logger
                    logger = get_kodi_logger('lib.config.config_manager')
                    logger.warning("Failed to trigger immediate TV episode sync: %s", e)

            return success

        except Exception:
            return False

    def get_backup_preferences(self) -> Dict[str, Any]:
        """Get backup-related preferences with defaults"""
        return {
            'enabled': self.get_bool('backup_enabled', False),
            'schedule_interval': self.get('backup_interval', 'weekly'),
            'retention_days': self.get_int('backup_retention_count', 5),
            'storage_path': self.get_backup_storage_location(),
            'storage_type': self.get('backup_storage_type', 'local'),
            'include_settings': self.get_bool('backup_include_settings', True),
            'include_non_library': self.get_bool('backup_include_non_library', False)
        }

    def get_export_location(self) -> str:
        """Get export location setting"""
        return str(self.get('export_location', '')).strip()

    def set_export_location(self, path: str) -> None:
        """Set export location setting"""
        self.set('export_location', path)

    def get_backup_storage_location(self) -> str:
        """Get backup storage location with proper fallback"""
        try:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            logger.debug("CONFIG_DEBUG: Getting backup storage location")
            
            storage_type = self.get('backup_storage_type', 'local')
            logger.debug("CONFIG_DEBUG: backup_storage_type = '%s'", storage_type)

            if storage_type == "custom":
                # Use custom path set by user
                custom_path = str(self.get('backup_local_path', ''))
                logger.debug("CONFIG_DEBUG: custom backup path = '%s'", custom_path)
                if custom_path and custom_path.strip():
                    return custom_path.strip()

            # Default to addon data directory
            default_path = "special://userdata/addon_data/plugin.video.librarygenie/backups/"
            logger.debug("CONFIG_DEBUG: Using default backup path: %s", default_path)
            return default_path
        except Exception as e:
            from ..utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.config.config_manager')
            logger.error("CONFIG_DEBUG: Exception in get_backup_storage_location: %s", e)
            # Ultimate fallback
            return "special://userdata/addon_data/plugin.video.librarygenie/backups/"

    def get_backup_enabled(self) -> bool:
        """Get backup enabled setting with detailed debugging"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("CONFIG_DEBUG: Getting backup_enabled setting")
        
        try:
            result = self.get_bool('backup_enabled', False)
            logger.debug("CONFIG_DEBUG: backup_enabled = %s", result)
            return result
        except Exception as e:
            logger.error("CONFIG_DEBUG: Exception getting backup_enabled: %s", e)
            return False

    def get_backup_include_non_library(self) -> bool:
        """Get backup include non-library setting with detailed debugging"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("CONFIG_DEBUG: Getting backup_include_non_library setting")
        
        try:
            result = self.get_bool('backup_include_non_library', False)
            logger.debug("CONFIG_DEBUG: backup_include_non_library = %s", result)
            return result
        except Exception as e:
            logger.error("CONFIG_DEBUG: Exception getting backup_include_non_library: %s", e)
            return False

    def get_backup_include_folders(self) -> bool:
        """Get backup include folders setting with detailed debugging"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("CONFIG_DEBUG: Getting backup_include_folders setting")
        
        try:
            result = self.get_bool('backup_include_folders', True)
            logger.debug("CONFIG_DEBUG: backup_include_folders = %s", result)
            return result
        except Exception as e:
            logger.error("CONFIG_DEBUG: Exception getting backup_include_folders: %s", e)
            return True

    def get_backup_retention_count(self) -> int:
        """Get backup retention count with detailed debugging"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("CONFIG_DEBUG: Getting backup_retention_count setting")
        
        try:
            result = self.get_int('backup_retention_count', 5)
            logger.debug("CONFIG_DEBUG: backup_retention_count = %s", result)
            return result
        except Exception as e:
            logger.error("CONFIG_DEBUG: Exception getting backup_retention_count: %s", e)
            return 5

    def get_backup_storage_type(self) -> str:
        """Get backup storage type with detailed debugging"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("CONFIG_DEBUG: Getting backup_storage_type setting")
        
        try:
            # This is a select setting, so get as int and map to string
            index = self.get_int('backup_storage_type', 0)
            logger.debug("CONFIG_DEBUG: backup_storage_type index = %s", index)
            
            # Map index to storage type
            storage_types = ['local']  # Only local supported for now
            if 0 <= index < len(storage_types):
                result = storage_types[index]
            else:
                result = 'local'
            
            logger.debug("CONFIG_DEBUG: backup_storage_type = '%s'", result)
            return result
        except Exception as e:
            logger.error("CONFIG_DEBUG: Exception getting backup_storage_type: %s", e)
            return 'local'

    def get_backup_interval(self) -> str:
        """Get backup interval with detailed debugging"""
        from ..utils.kodi_log import get_kodi_logger
        logger = get_kodi_logger('lib.config.config_manager')
        logger.debug("CONFIG_DEBUG: Getting backup_interval setting")
        
        try:
            # This is a select setting, so get as int and map to string
            index = self.get_int('backup_interval', 0)
            logger.debug("CONFIG_DEBUG: backup_interval index = %s", index)
            
            # Map index to interval string
            intervals = ['weekly', 'daily', 'monthly']  # Based on settings.xml lvalues
            if 0 <= index < len(intervals):
                result = intervals[index]
            else:
                result = 'weekly'
            
            logger.debug("CONFIG_DEBUG: backup_interval = '%s'", result)
            return result
        except Exception as e:
            logger.error("CONFIG_DEBUG: Exception getting backup_interval: %s", e)
            return 'weekly'


# Global config instance
_CFG: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration instance"""
    global _CFG
    if _CFG is None:
        _CFG = ConfigManager()
    return _CFG


