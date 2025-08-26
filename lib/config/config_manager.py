#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Configuration Manager
Reads Kodi settings and manages addon configuration
"""

import xbmcaddon


class ConfigManager:
    """Manages addon configuration and settings"""

    def __init__(self):
        self._addon = xbmcaddon.Addon()

        # Default configuration matching Phase 2-3 requirements
        self._defaults = {
            "debug_logging": False,
            "background_task_enabled": True,
            "background_interval_minutes": 30,  # 30 minutes (Phase 2 safe default)
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
        }

    def get(self, key, default=None):
        """Get configuration value"""
        try:
            setting_type = self._get_setting_type(key)
            if setting_type == "bool":
                return self._addon.getSettingBool(key)
            elif setting_type == "int":
                return self._addon.getSettingInt(key)
            elif setting_type == "number":
                return self._addon.getSettingNumber(key)
            else:
                return self._addon.getSettingString(key)
        except Exception as e:
            # Return default value if setting read fails
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
        except Exception as e:
            self.logger.warning(f"Failed to set setting {key}: {e}")
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
            "background_interval_minutes", "favorites_scan_interval_minutes", 
            "search_page_size", "search_history_days",
            # Phase 3: Advanced settings
            "jsonrpc_page_size", "jsonrpc_timeout_seconds", 
            "db_batch_size", "db_busy_timeout_ms"
        ]

        if key in bool_settings:
            return "bool"
        elif key in int_settings:
            return "int"
        else:
            return "string"

    def get_background_interval_seconds(self):
        """Get background interval in seconds with safe clamping (Phase 2)"""
        minutes = self.get("background_interval_minutes", 30)
        # Phase 2: Clamp to safe minimum (5 minutes) and maximum (720 minutes/12 hours)
        minutes = max(5, min(720, minutes))
        return minutes * 60
    
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
    
    def get_jsonrpc_page_size(self):
        """Get JSON-RPC page size with safe clamping (50-500, default 200)"""
        size = self.get("jsonrpc_page_size", 200)
        return max(50, min(500, size))
    
    def get_jsonrpc_timeout_seconds(self):
        """Get JSON-RPC timeout with safe clamping (5-30 seconds, default 10)"""
        timeout = self.get("jsonrpc_timeout_seconds", 10)
        return max(5, min(30, timeout))
    
    def get_db_batch_size(self):
        """Get database batch size with safe clamping (50-500, default 200)"""
        size = self.get("db_batch_size", 200)
        return max(50, min(500, size))
    
    def get_db_busy_timeout_ms(self):
        """Get database busy timeout with safe clamping (1000-10000ms, default 3000)"""
        timeout = self.get("db_busy_timeout_ms", 3000)
        return max(1000, min(10000, timeout))


# Global config instance
_config_instance = None


def get_config():
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
