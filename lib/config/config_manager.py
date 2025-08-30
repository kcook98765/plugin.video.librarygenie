#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Configuration Manager
Reads Kodi settings and manages addon configuration
"""

import xbmcaddon
try:
    from typing import Optional, List
except ImportError:
    # Python < 3.5 fallback
    Optional = object
    List = object


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
            "search_remember_scope": True,
            "search_include_file_path": False,
            "search_page_size": 50,
            "search_history_days": 30,
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
            # Always try string first as it's most compatible
            value = self._addon.getSettingString(key)
            if value:
                return value
            else:
                return self._defaults.get(key, default)
        except Exception:
            # Return default value if setting read fails
            return self._defaults.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        try:
            value = self._addon.getSettingBool(key)
            return value
        except Exception:
            # Use defaults dict fallback if available, otherwise use provided default
            return self._defaults.get(key, default)

    def get_int(self, key, default=0):
        """Get integer setting with safe fallback"""
        try:
            return self._addon.getSettingInt(key)
        except Exception:
            return self._defaults.get(key, default)

    def get_float(self, key, default=0.0):
        """Get float setting with safe fallback"""
        try:
            return self._addon.getSettingNumber(key)
        except Exception:
            return self._defaults.get(key, default)

    def set(self, key, value):
        """Set configuration value"""
        try:
            setting_type = self._get_setting_type(key)
            if setting_type == "bool":
                return self._addon.setSettingBool(key, value)
            elif setting_type == "int":
                return self._addon.setSettingInt(key, value)
            elif setting_type == "number":
                return self._addon.setSettingNumber(key, value)
            else:
                return self._addon.setSettingString(key, str(value))
        except Exception:
            return False

    def _get_setting_type(self, key):
        """Determine setting type based on key name"""
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
            "search_remember_scope",
            "search_include_file_path",
        ]
        int_settings = [
            "background_interval_seconds", "favorites_scan_interval_minutes",
            "search_page_size", "search_history_days",
            # Phase 3: Advanced settings
            "jsonrpc_page_size", "jsonrpc_timeout_seconds",
            "db_batch_size", "db_busy_timeout_ms",
            # Remote service settings
            "auth_poll_seconds",
        ]
        float_settings = []

        if key in bool_settings:
            return "bool"
        elif key in int_settings:
            return "int"
        elif key in float_settings:
            return "number"
        # Select settings (stored as integer indexes)
        select_settings = [
            "select_action"
        ]

        # String settings
        string_settings = [
            "default_list_id", "remote_base_url", "device_name"
        ]

        if key in select_settings:
            return "int"  # Select controls store integer indexes
        elif key in string_settings:
            return "string"
        else:
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