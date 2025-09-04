#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Configuration Manager
Reads Kodi settings and manages addon configuration
"""

import xbmcaddon
from typing import Optional, Dict, Any


class ConfigManager:
    """Manages addon configuration and settings"""

    def __init__(self):
        self._addon = xbmcaddon.Addon()

        # Default configuration matching Phase 2-3 requirements
        self._defaults = {
            "debug_logging": False,
            "background_task_enabled": True,
            "background_interval_seconds": 120,  # 120 seconds (safer default)
            # Phase 3: Advanced settings with safe defaults
            "jsonrpc_page_size": 200,  # Items per JSON-RPC page
            "jsonrpc_timeout_seconds": 10,  # JSON-RPC request timeout
            "db_batch_size": 200,  # Database write batch size
            "db_busy_timeout_ms": 3000,  # Database busy timeout
            "confirm_destructive_actions": True,
            "show_item_counts": True,
            "track_library_changes": True,
            "soft_delete_removed_items": True,
            "default_list_id": "",
            "quick_add_enabled": False,
            "show_missing_indicators": True,
            "favorites_integration_enabled": False,
            "favorites_scan_interval_minutes": 30,
            "show_unmapped_favorites": False,

            # Remote service settings
            "remote_base_url": "",  # Blank by default for repo safety
            "device_name": "Kodi",
            "auth_poll_seconds": 3,
            # UI behavior settings
            "select_action": "0",  # Default to play action
        }

    def get(self, key, default=None):
        """Get configuration value with safe fallback"""
        try:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"CONFIG_DEBUG: Getting setting '{key}' (default: {default})")
            
            # Always try string first as it's most compatible
            value = self._addon.getSettingString(key)
            logger.debug(f"CONFIG_DEBUG: getSettingString('{key}') returned: '{value}' (type: {type(value)})")
            
            if value:
                logger.debug(f"CONFIG_DEBUG: Using string value for '{key}': '{value}'")
                return value
            else:
                fallback = self._defaults.get(key, default)
                logger.debug(f"CONFIG_DEBUG: Using fallback for '{key}': '{fallback}' (from defaults: {key in self._defaults})")
                return fallback
        except Exception as e:
            # Return default value if setting read fails
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"CONFIG_DEBUG: Exception getting setting '{key}': {e}")
            fallback = self._defaults.get(key, default)
            logger.debug(f"CONFIG_DEBUG: Exception fallback for '{key}': '{fallback}'")
            return fallback

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        try:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"CONFIG_DEBUG: Getting bool setting '{key}' (default: {default})")
            
            # First try getSettingBool
            result = self._addon.getSettingBool(key)
            logger.debug(f"CONFIG_DEBUG: getSettingBool('{key}') returned: {result}")
            return result
        except Exception as e:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"CONFIG_DEBUG: getSettingBool('{key}') failed: {e}")
            
            try:
                # Fallback to string and convert
                str_value = self._addon.getSettingString(key)
                logger.debug(f"CONFIG_DEBUG: String fallback for '{key}': '{str_value}'")
                
                if str_value.lower() in ('true', '1', 'yes'):
                    logger.debug(f"CONFIG_DEBUG: Converting '{str_value}' to True for '{key}'")
                    return True
                elif str_value.lower() in ('false', '0', 'no', ''):
                    logger.debug(f"CONFIG_DEBUG: Converting '{str_value}' to False for '{key}'")
                    return False
                else:
                    fallback = self._defaults.get(key, default)
                    logger.debug(f"CONFIG_DEBUG: Using defaults fallback for '{key}': {fallback}")
                    return fallback
            except Exception as e2:
                # Use defaults dict fallback if available, otherwise use provided default
                from ..utils.logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"CONFIG_DEBUG: String fallback also failed for '{key}': {e2}")
                fallback = self._defaults.get(key, default)
                logger.debug(f"CONFIG_DEBUG: Final fallback for '{key}': {fallback}")
                return fallback

    def get_int(self, key, default=0):
        """Get integer setting with safe fallback"""
        try:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"CONFIG_DEBUG: Getting int setting '{key}' (default: {default})")
            
            # First try getSettingInt
            result = self._addon.getSettingInt(key)
            logger.debug(f"CONFIG_DEBUG: getSettingInt('{key}') returned: {result}")
            return result
        except Exception as e:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"CONFIG_DEBUG: getSettingInt('{key}') failed: {e}")
            
            try:
                # Fallback to string and convert
                str_value = self._addon.getSettingString(key)
                logger.debug(f"CONFIG_DEBUG: String fallback for int '{key}': '{str_value}'")
                
                if str_value and str_value.strip():
                    result = int(str_value.strip())
                    logger.debug(f"CONFIG_DEBUG: Converted '{str_value}' to {result} for '{key}'")
                    return result
                else:
                    fallback = self._defaults.get(key, default)
                    logger.debug(f"CONFIG_DEBUG: Empty string, using fallback for '{key}': {fallback}")
                    return fallback
            except (ValueError, TypeError) as e2:
                from ..utils.logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"CONFIG_DEBUG: String conversion failed for '{key}': {e2}")
                fallback = self._defaults.get(key, default)
                logger.debug(f"CONFIG_DEBUG: Final fallback for '{key}': {fallback}")
                return fallback

    def get_float(self, key, default=0.0):
        """Get float setting with safe fallback"""
        try:
            return self._addon.getSettingNumber(key)
        except Exception:
            return self._defaults.get(key, default)

    def set(self, key, value):
        """Set configuration value"""
        try:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            
            setting_type = self._get_setting_type(key)
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' = '{value}' (type: {setting_type})")
            
            if setting_type == "bool":
                result = self._addon.setSettingBool(key, value)
                logger.debug(f"CONFIG_DEBUG: setSettingBool('{key}', {value}) returned: {result}")
                return result
            elif setting_type == "int":
                result = self._addon.setSettingInt(key, value)
                logger.debug(f"CONFIG_DEBUG: setSettingInt('{key}', {value}) returned: {result}")
                return result
            elif setting_type == "number":
                result = self._addon.setSettingNumber(key, value)
                logger.debug(f"CONFIG_DEBUG: setSettingNumber('{key}', {value}) returned: {result}")
                return result
            else:
                result = self._addon.setSettingString(key, str(value))
                logger.debug(f"CONFIG_DEBUG: setSettingString('{key}', '{str(value)}') returned: {result}")
                return result
        except Exception as e:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"CONFIG_DEBUG: Exception setting '{key}' = '{value}': {e}")
            return False

    def _get_setting_type(self, key):
        """Determine setting type based on key name"""
        from ..utils.logger import get_logger
        logger = get_logger(__name__)
        
        bool_settings = [
            "debug_logging",
            "background_task_enabled",
            "confirm_destructive_actions",
            "show_item_counts",
            "track_library_changes",
            "soft_delete_removed_items",
            "quick_add_enabled",
            "show_missing_indicators",
            "favorites_integration_enabled",
            "show_unmapped_favorites",
            "backup_enabled",
            "backup_include_settings",
            "backup_include_non_library",
            "backup_include_folders",
        ]
        int_settings = [
            "background_interval_seconds", "favorites_scan_interval_minutes",
            "search_page_size", "search_history_days",
            # Phase 3: Advanced settings
            "jsonrpc_page_size", "jsonrpc_timeout_seconds",
            "db_batch_size", "db_busy_timeout_ms",
            # Remote service settings
            "auth_poll_seconds",
            "backup_retention_count",
        ]
        float_settings = []

        if key in bool_settings:
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' identified as bool type")
            return "bool"
        elif key in int_settings:
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' identified as int type")
            return "int"
        elif key in float_settings:
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' identified as number type")
            return "number"
            
        # Select settings (stored as integer indexes)
        select_settings = [
            "select_action",
            "backup_storage_type",
            "backup_interval"
        ]

        # String settings
        string_settings = [
            "default_list_id", "remote_base_url", "device_name"
        ]

        if key in select_settings:
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' identified as int type (select)")
            return "int"  # Select controls store integer indexes
        elif key in string_settings:
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' identified as string type")
            return "string"
        else:
            logger.debug(f"CONFIG_DEBUG: Setting '{key}' defaulting to string type")
            return "string"

    def get_background_interval_seconds(self) -> int:
        """Get background service interval in seconds"""
        return self.get_int("background_interval_seconds", 1800)

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

    def get_select_action(self) -> str:
        """Get the select action preference: 'play' or 'info'"""
        try:
            # For select type settings, try getSettingInt first (most reliable for select controls)
            try:
                index = self._addon.getSettingInt("select_action")
                return "info" if index == 1 else "play"
            except Exception:
                # Fallback to string method
                raw_value = self._addon.getSettingString("select_action")
                if raw_value and raw_value.strip():
                    try:
                        # Convert string index to preference
                        index = int(raw_value.strip())
                        return "info" if index == 1 else "play"
                    except (ValueError, TypeError):
                        # If not a number, check string value directly
                        if raw_value.strip().lower() in ["info", "1"]:
                            return "info"

            # Safe default if setting not found or invalid
            return "play"

        except Exception:
            # Ultimate fallback
            return "play"

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
                    from ..utils.logger import get_logger
                    logger = get_logger(__name__)
                    logger.warning(f"Failed to trigger immediate favorites scan: {e}")

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

    def get_backup_storage_location(self) -> str:
        """Get backup storage location with proper fallback"""
        try:
            storage_type = self.get('backup_storage_type', 'local')

            if storage_type == "custom":
                # Use custom path set by user
                custom_path = self.get('backup_local_path', '')
                if custom_path and custom_path.strip():
                    return custom_path.strip()

            # Default to addon data directory
            return "special://userdata/addon_data/plugin.video.librarygenie/backups/"
        except Exception:
            # Ultimate fallback
            return "special://userdata/addon_data/plugin.video.librarygenie/backups/"


# Global config instance
_CFG: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration instance"""
    global _CFG
    if _CFG is None:
        _CFG = ConfigManager()
    return _CFG


def get_select_pref() -> str:
    """Get the select action preference: 'play' or 'info' - convenience function"""
    config = get_config()
    return config.get_select_action()