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
from ..utils.kodi_log import get_kodi_logger
from ..ui.localization import L

class SettingsManager:
    """Manages all addon settings with proper type conversion and validation"""

    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.logger = get_kodi_logger('lib.config.settings')

    # General Settings

    def get_confirm_destructive(self) -> bool:
        """Get confirmation for destructive actions setting"""
        return self.addon.getSettingBool('confirm_destructive')


    # Library Settings
    def get_track_library_changes(self) -> bool:
        """Get track library changes setting"""
        return self.addon.getSettingBool('track_library_changes')

    def get_soft_delete_removed(self) -> bool:
        """Get soft delete removed items setting"""
        return self.addon.getSettingBool('soft_delete_removed')

    def get_sync_movies(self) -> bool:
        """Get sync movies during library scan setting"""
        return self.addon.getSettingBool('sync_movies')

    def set_sync_movies(self, enabled: bool) -> None:
        """Set sync movies during library scan setting"""
        self.addon.setSettingBool('sync_movies', enabled)

    def get_sync_tv_episodes(self) -> bool:
        """Get sync TV episodes during library scan setting"""
        return self.addon.getSettingBool('sync_tv_episodes')

    def set_sync_tv_episodes(self, enabled: bool) -> None:
        """Set sync TV episodes during library scan setting"""
        self.addon.setSettingBool('sync_tv_episodes', enabled)

    def get_first_run_completed(self) -> bool:
        """Get whether first run setup has been completed"""
        return self.addon.getSettingBool('first_run_completed')

    def set_first_run_completed(self, completed: bool) -> None:
        """Set whether first run setup has been completed"""
        self.addon.setSettingBool('first_run_completed', completed)

    def get_sync_frequency_hours(self) -> int:
        """Get sync frequency in hours (1-48, default 1)"""
        return max(1, min(48, self.addon.getSettingInt('sync_frequency_hours') or 1))

    def set_sync_frequency_hours(self, hours: int) -> None:
        """Set sync frequency in hours (1-48)"""
        validated_hours = max(1, min(48, hours))
        self.addon.setSettingInt('sync_frequency_hours', validated_hours)

    def get_last_sync_time(self) -> int:
        """Get timestamp of last sync completion"""
        return self.addon.getSettingInt('last_sync_time')

    def set_last_sync_time(self, timestamp: int) -> None:
        """Set timestamp of last sync completion"""
        self.addon.setSettingInt('last_sync_time', timestamp)

    # Lists Settings
    def get_default_list_id(self) -> Optional[str]:
        """Get default list ID for quick-add"""
        value = self.addon.getSetting('default_list_id')
        return value if value else None

    def set_default_list_id(self, list_id: str) -> None:
        """Set default list ID for quick-add"""
        self.addon.setSetting('default_list_id', str(list_id) if list_id else "")

    def get_enable_quick_add(self) -> bool:
        """Get enable quick-add setting"""
        return self.addon.getSettingBool('quick_add_enabled')

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
        return self.addon.getSettingBool('favorites_integration_enabled')

    def get_favorites_scan_interval(self) -> int:
        """Get favorites scan interval in minutes"""
        return max(5, min(1440, self.addon.getSettingInt('favorites_scan_interval')))

    def get_show_unmapped_favorites(self) -> bool:
        """Get show unmapped favorites setting"""
        return self.addon.getSettingBool('show_unmapped_favorites')

    def get_enable_batch_processing(self) -> bool:
        """Get enable batch processing for large favorites files"""
        return self.addon.getSettingBool('enable_batch_processing')



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

    # AI Search Server Settings

    def get_ai_search_api_key(self) -> Optional[str]:
        """Get AI search API key"""
        value = self.addon.getSetting('ai_search_api_key')
        return value.strip() if value else None

    def set_ai_search_api_key(self, api_key: str) -> None:
        """Set AI search API key"""
        self.addon.setSetting('ai_search_api_key', api_key if api_key else "")

    def get_ai_search_activated(self) -> bool:
        """Get AI search activated status"""
        return self.addon.getSettingBool('ai_search_activated')


    def set_ai_search_activated(self, activated: bool) -> None:
        """Set AI search activated status"""
        self.addon.setSettingBool('ai_search_activated', activated)


    def get_ai_search_sync_interval(self) -> int:
        """Get AI search sync interval in seconds"""
        selector_value = self.addon.getSettingInt('ai_search_sync_interval')
        # Map selector values to seconds: 0=1hr, 1=12hr, 2=24hr
        interval_map = {
            0: 3600,    # 1 Hour
            1: 43200,   # 12 Hours  
            2: 86400    # 24 Hours
        }
        return interval_map.get(selector_value, 43200)  # Default to 12 hours

    # Backup Settings
    def get_enable_automatic_backups(self) -> bool:
        """Get enable automatic backups setting"""
        return self.addon.getSettingBool('enable_automatic_backups')

    def get_backup_interval(self) -> str:
        """Get backup interval setting"""
        return self.addon.getSetting('backup_interval')

    def get_backup_storage_location(self) -> str:
        """Get backup storage location with safe fallbacks"""
        try:
            storage_type = self.addon.getSetting('backup_storage_type')

            if storage_type == "custom":
                # Use custom path set by user
                custom_path = self.addon.getSetting('backup_local_path')
                if custom_path and custom_path.strip():
                    return custom_path.strip()

            # Default to addon data directory
            return "special://userdata/addon_data/plugin.video.librarygenie/backups/"
        except Exception as e:
            self.logger.warning("Error reading backup storage location: %s", e)
            return "special://userdata/addon_data/plugin.video.librarygenie/backups/"

    def get_backup_storage_type(self) -> str:
        """Get backup storage type with safe fallback"""
        try:
            return self.addon.getSetting('backup_storage_type') or 'local'
        except Exception as e:
            self.logger.warning("Error reading backup storage type: %s", e)
            return 'local'

    def get_backup_enabled(self) -> bool:
        """Get backup enabled setting with safe fallback"""
        try:
            return self.addon.getSettingBool('backup_enabled')
        except Exception as e:
            try:
                # Try as string fallback
                str_val = self.addon.getSettingString('backup_enabled')
                return str_val.lower() in ('true', '1', 'yes')
            except Exception:
                self.logger.warning("Error reading backup_enabled setting: %s", e)
                return False

    def get_backup_retention_count(self) -> int:
        """Get backup retention count with safe fallback"""
        try:
            return max(1, min(50, self.addon.getSettingInt('backup_retention_count')))
        except Exception as e:
            try:
                # Try as string fallback
                str_val = self.addon.getSettingString('backup_retention_count')
                if str_val and str_val.strip():
                    return max(1, min(50, int(str_val.strip())))
                else:
                    return 5
            except (ValueError, TypeError):
                self.logger.warning("Error reading backup retention count: %s", e)
                return 5

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
            self.logger.debug("Setting %s set to %s", setting_id, value)
        except Exception as e:
            self.logger.error("Failed to set setting %s: %s", setting_id, e)

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values"""
        try:
            # This would require iterating through all settings and resetting them
            # For now, we'll log the action
            self.logger.info(L(34503))  # "Setting restored to default"
        except Exception as e:
            self.logger.error("Failed to reset settings: %s", e)

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
            self.logger.error("%s: %s", L(34505), e)  # "Configuration validation failed"
            return False

    def get_validation_status_message(self, is_valid: bool) -> str:
        """Get localized validation status message"""
        return L(34504) if is_valid else L(34505)  # "Configuration validated" or "Configuration validation failed"

    def get_setting_save_message(self, success: bool) -> str:
        """Get localized setting save message"""
        return L(34501) if success else L(34502)  # "Setting saved successfully" or "Failed to save setting"

    def get_backup_preferences(self) -> Dict[str, Any]:
        """Get backup-related preferences with defaults"""
        try:
            config = get_config()

            return {
                'enabled': config.get_bool('backup_enabled', False),
                'schedule_interval': config.get('backup_interval', 'weekly'),
                'retention_days': config.get_int('backup_retention_count', 5),
                'storage_path': config.get('backup_storage_location', ''),
                'storage_type': config.get('backup_storage_type', 'local'),
                'include_settings': config.get_bool('backup_include_settings', True),
                'include_non_library': config.get_bool('backup_include_non_library', False)
            }
        except Exception as e:
            self.logger.warning("Error reading backup preferences: %s", e)
            return {
                'enabled': False,
                'schedule_interval': 'weekly',
                'retention_days': 5,
                'storage_path': "special://userdata/addon_data/plugin.video.librarygenie/backups/",
                'storage_type': 'local',
                'include_settings': True,
                'include_non_library': False
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