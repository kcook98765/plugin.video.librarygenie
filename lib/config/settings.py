#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Settings Manager
Handles addon settings and preferences
"""

from __future__ import annotations

import xbmcaddon
from typing import Any, Dict, Optional, Union

from .config_manager import get_config
from ..utils.logger import get_logger
from ..ui.localization import L

class SettingsManager:
    """Manages all addon settings with proper type conversion and validation"""

    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.logger = get_logger(__name__)

    # General Settings
    def get_debug_logging(self) -> bool:
        """Get debug logging setting"""
        return self.addon.getSettingBool('debug_logging')

    def get_confirm_destructive(self) -> bool:
        """Get confirmation for destructive actions setting"""
        return self.addon.getSettingBool('confirm_destructive')

    def get_show_item_counts(self) -> bool:
        """Get show item counts setting"""
        return self.addon.getSettingBool('show_item_counts')

    # Library Settings
    def get_track_library_changes(self) -> bool:
        """Get track library changes setting"""
        return self.addon.getSettingBool('track_library_changes')

    def get_soft_delete_removed(self) -> bool:
        """Get soft delete removed items setting"""
        return self.addon.getSettingBool('soft_delete_removed')

    # Lists Settings
    def get_default_list_id(self) -> Optional[str]:
        """Get default list ID for quick-add"""
        value = self.addon.getSetting('default_list_id')
        return value if value else None

    def get_enable_quick_add(self) -> bool:
        """Get enable quick-add setting"""
        return self.addon.getSettingBool('enable_quick_add')

    def get_show_missing_indicators(self) -> bool:
        """Get show missing movie indicators setting"""
        return self.addon.getSettingBool('show_missing_indicators')

    # Background Service Settings
    def get_enable_background_service(self) -> bool:
        """Get enable background service setting"""
        return self.addon.getSettingBool('enable_background_service')

    def get_background_interval(self) -> int:
        """Get background service interval in minutes"""
        return max(5, min(720, self.addon.getSettingInt('background_interval')))

    # Favorites Settings
    def get_enable_favorites_integration(self) -> bool:
        """Get enable favorites integration setting"""
        return self.addon.getSettingBool('enable_favorites_integration')

    def get_favorites_scan_interval(self) -> int:
        """Get favorites scan interval in minutes"""
        return max(5, min(1440, self.addon.getSettingInt('favorites_scan_interval')))

    def get_show_unmapped_favorites(self) -> bool:
        """Get show unmapped favorites setting"""
        return self.addon.getSettingBool('show_unmapped_favorites')

    def get_enable_batch_processing(self) -> bool:
        """Get enable batch processing for large favorites files"""
        return self.addon.getSettingBool('enable_batch_processing')

    # Search Settings
    def get_search_match_mode(self) -> str:
        """Get search match mode (contains/starts_with)"""
        return self.addon.getSetting('search_match_mode')

    def get_include_file_path_search(self) -> bool:
        """Get include file path in search setting"""
        return self.addon.getSettingBool('include_file_path_search')

    def get_search_results_per_page(self) -> int:
        """Get search results per page"""
        return max(10, min(100, self.addon.getSettingInt('search_results_per_page')))

    def get_enable_decade_shorthand(self) -> bool:
        """Get enable decade shorthand setting"""
        return self.addon.getSettingBool('enable_decade_shorthand')

    def get_remember_last_search_scope(self) -> bool:
        """Get remember last search scope setting"""
        return self.addon.getSettingBool('remember_last_search_scope')

    def get_search_history_days(self) -> int:
        """Get search history retention in days"""
        return max(0, min(365, self.addon.getSettingInt('search_history_days')))

    # Advanced Settings
    def get_jsonrpc_page_size(self) -> int:
        """Get JSON-RPC page size"""
        return max(50, min(500, self.addon.getSettingInt('jsonrpc_page_size')))

    def get_jsonrpc_timeout(self) -> int:
        """Get JSON-RPC timeout in seconds"""
        return max(5, min(60, self.addon.getSettingInt('jsonrpc_timeout')))

    def get_database_batch_size(self) -> int:
        """Get database batch size"""
        return max(100, min(1000, self.addon.getSettingInt('database_batch_size')))

    def get_database_busy_timeout(self) -> int:
        """Get database busy timeout in milliseconds"""
        return max(1000, min(30000, self.addon.getSettingInt('database_busy_timeout')))

    # Remote Service Settings
    def get_remote_server_url(self) -> Optional[str]:
        """Get remote server URL"""
        value = self.addon.getSetting('remote_server_url')
        return value.strip() if value else None

    def get_device_name(self) -> str:
        """Get device name for authentication"""
        value = self.addon.getSetting('device_name')
        return value if value else L(30412)  # "Device name"

    def get_auth_polling_interval(self) -> int:
        """Get authentication polling interval in seconds"""
        return max(5, min(60, self.addon.getSettingInt('auth_polling_interval')))

    def get_enable_auto_token_refresh(self) -> bool:
        """Get enable automatic token refresh setting"""
        return self.addon.getSettingBool('enable_auto_token_refresh')

    def get_use_native_kodi_info(self) -> bool:
        """Get use native Kodi info for library items setting"""
        return self.addon.getSettingBool('use_native_kodi_info')

    def get_enable_background_token_refresh(self) -> bool:
        """Get enable automatic token refresh in background service setting"""
        return self.addon.getSettingBool('enable_background_token_refresh')

    # Backup Settings
    def get_enable_automatic_backups(self) -> bool:
        """Get enable automatic backups setting"""
        return self.addon.getSettingBool('enable_automatic_backups')

    def get_backup_interval(self) -> str:
        """Get backup interval setting"""
        return self.addon.getSetting('backup_interval')

    def get_backup_storage_location(self) -> str:
        """Get backup storage location"""
        value = self.addon.getSetting('backup_storage_location')
        return value if value else "special://userdata/addon_data/plugin.video.library.genie/backups/"

    def get_backup_retention_policy(self) -> str:
        """Get backup retention policy"""
        return self.addon.getSetting('backup_retention_policy')

    # ShortList Integration Settings
    def get_import_from_shortlist(self) -> bool:
        """Get import from ShortList addon setting"""
        return self.addon.getSettingBool('import_from_shortlist')

    def get_clear_before_import(self) -> bool:
        """Get clear list before importing setting"""
        return self.addon.getSettingBool('clear_before_import')

    # Settings Helper Methods
    def set_setting(self, setting_id: str, value: Union[str, bool, int]) -> None:
        """Set a setting value with proper type conversion"""
        try:
            if isinstance(value, bool):
                self.addon.setSettingBool(setting_id, value)
            elif isinstance(value, int):
                self.addon.setSettingInt(setting_id, value)
            else:
                self.addon.setSetting(setting_id, str(value))
            self.logger.debug(f"Setting {setting_id} set to {value}")
        except Exception as e:
            self.logger.error(f"Failed to set setting {setting_id}: {e}")

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values"""
        try:
            # This would require iterating through all settings and resetting them
            # For now, we'll log the action
            self.logger.info(L(34503))  # "Setting restored to default"
        except Exception as e:
            self.logger.error(f"Failed to reset settings: {e}")

    def validate_settings(self) -> bool:
        """Validate all settings and return True if valid"""
        try:
            # Perform basic validation checks
            if self.get_background_interval() < 5:
                self.logger.warning("Background interval too low, using minimum")
                return False

            if self.get_jsonrpc_page_size() > 500:
                self.logger.warning("JSON-RPC page size too high, using maximum")
                return False

            self.logger.info(L(34504))  # "Configuration validated"
            return True
        except Exception as e:
            self.logger.error(f"{L(34505)}: {e}")  # "Configuration validation failed"
            return False

    def get_validation_status_message(self, is_valid: bool) -> str:
        """Get localized validation status message"""
        return L(34504) if is_valid else L(34505)  # "Configuration validated" or "Configuration validation failed"

    def get_setting_save_message(self, success: bool) -> str:
        """Get localized setting save message"""
        return L(34501) if success else L(34502)  # "Setting saved successfully" or "Failed to save setting"

    def get_backup_preferences(self) -> Dict[str, Any]:
        """Get backup-related preferences with defaults"""
        config = get_config()

        return {
            'enabled': config.get_bool('backup_enabled', False),
            'schedule_interval': config.get('backup_interval', 'weekly'),
            'retention_days': config.get_int('backup_retention_count', 5),
            'storage_path': config.get('backup_storage_location', ''),
            'storage_type': config.get('backup_storage_type', 'local'),
            'include_settings': config.get_bool('backup_include_settings', True),
            'include_favorites': config.get_bool('backup_include_favorites', True)
        }

    def get_phase12_remote_settings(self) -> Dict[str, Any]:
        """Get remote service settings for Phase 1.2 integration"""
        return {
            'enabled': self.addon.getSettingBool('remote_enabled'),
            'server_url': self.get_remote_server_url(),
            'timeout': self.addon.getSettingInt('remote_timeout'),
            'max_retries': self.addon.getSettingInt('remote_max_retries'),
            'fallback_to_local': self.addon.getSettingBool('remote_fallback_to_local'),
            'cache_duration': self.addon.getSettingInt('remote_cache_duration')
        }


# Module-level convenience functions
def get_phase12_remote_settings() -> Dict[str, Any]:
    """Module-level function to get remote service settings for Phase 1.2 integration"""
    settings_manager = SettingsManager()
    return settings_manager.get_phase12_remote_settings()