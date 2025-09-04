#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Backup Manager
Handles automatic scheduled backups with retention policies
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .export_engine import get_export_engine
from .storage_manager import get_storage_manager
from ..config import get_config
from ..utils.logger import get_logger
from ..config.settings import SettingsManager


class BackupManager:
    """Manages automatic backups with scheduling and retention"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.export_engine = get_export_engine()
        self.storage_manager = get_storage_manager()
        self.config = get_config()

    def should_run_backup(self) -> bool:
        """Check if backup should run based on schedule"""
        try:
            # Check if backups are enabled
            if not self.config.get("backup_enabled", False):
                return False

            # Get backup interval
            interval = self.config.get("backup_interval", "weekly")  # daily, weekly

            # Get last backup time
            last_backup = self._get_last_backup_time()
            if not last_backup:
                # No previous backup, should run
                return True

            # Calculate next backup time
            now = datetime.now()
            if interval == "daily":
                next_backup = last_backup + timedelta(days=1)
            else:  # weekly
                next_backup = last_backup + timedelta(days=7)

            return now >= next_backup

        except Exception as e:
            self.logger.error(f"Error checking backup schedule: {e}")
            return False

    def run_automatic_backup(self) -> Dict[str, Any]:
        """Run scheduled automatic backup - DEPRECATED: Use TimestampBackupManager instead"""
        try:
            self.logger.info("DEPRECATED: BackupManager.run_automatic_backup - redirecting to TimestampBackupManager")

            # Redirect to the new timestamp backup manager
            from . import get_timestamp_backup_manager
            timestamp_backup_manager = get_timestamp_backup_manager()

            return timestamp_backup_manager.run_automatic_backup()

        except Exception as e:
            self.logger.error(f"Error in automatic backup: {e}")
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backup files - DEPRECATED: Use TimestampBackupManager instead"""
        try:
            self.logger.info("DEPRECATED: BackupManager.list_backups - redirecting to TimestampBackupManager")

            # Redirect to the new timestamp backup manager
            from . import get_timestamp_backup_manager
            timestamp_backup_manager = get_timestamp_backup_manager()

            return timestamp_backup_manager.list_backups()

        except Exception as e:
            self.logger.error(f"Error listing backups: {e}")
            return []

    def delete_backup(self, filename: str) -> bool:
        """Delete specific backup file"""
        try:
            profile_path = self.storage_manager.get_profile_path()
            file_path = os.path.join(profile_path, filename)

            if self.storage_manager.delete_file_safe(file_path):
                self.logger.info(f"Deleted backup: {filename}")
                return True
            else:
                return False

        except Exception as e:
            self.logger.error(f"Error deleting backup: {e}")
            return False

    def get_backup_settings(self) -> Dict[str, Any]:
        """Get current backup settings"""
        try:
            settings = SettingsManager()

            backup_preferences = {
                'enabled': settings.get_backup_enabled(),
                'schedule_interval': self.config.get('backup_interval', 'weekly'),
                'retention_days': settings.get_backup_retention_count(),
                'storage_path': settings.get_backup_storage_location(),
                'storage_type': settings.get_backup_storage_type(),
                'include_settings': self.config.get_bool('backup_include_settings', True)
            }
            return backup_preferences
        except Exception as e:
            self.logger.error(f"Error getting backup settings: {e}")
            # Return safe defaults
            return {
                'enabled': False,
                'schedule_interval': 'weekly',
                'retention_days': 5,
                'storage_path': "special://userdata/addon_data/plugin.video.librarygenie/backups/",
                'storage_type': 'local',
                'include_settings': True
            }


    def _get_last_backup_time(self) -> Optional[datetime]:
        """Get timestamp of last backup"""
        try:
            last_backup_str = self.config.get("last_backup_time", "")
            if last_backup_str:
                return datetime.fromisoformat(last_backup_str)
            return None
        except:
            return None

    def _update_last_backup_time(self):
        """Update last backup timestamp"""
        try:
            now = datetime.now()
            # Note: This would update config if we had a way to persist it
            # For now, we'll rely on file timestamps
            self.logger.debug(f"Backup completed at {now}")
        except Exception as e:
            self.logger.error(f"Error updating backup time: {e}")

    def _cleanup_old_backups(self):
        """Clean up old backup files based on retention policy"""
        try:
            retention_count = int(self.config.get("backup_retention_count", 5))

            # Get all backup files
            backups = self.list_backups()

            if len(backups) <= retention_count:
                return  # Nothing to clean up

            # Delete oldest backups
            backups_to_delete = backups[retention_count:]
            deleted_count = 0

            for backup in backups_to_delete:
                if self.delete_backup(backup["filename"]):
                    deleted_count += 1

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old backup files")

        except Exception as e:
            self.logger.error(f"Error cleaning up backups: {e}")

    def estimate_backup_size(self, export_types: List[str]) -> Dict[str, Any]:
        """Estimate size of backup with given export types"""
        try:
            preview = self.export_engine.get_export_preview(export_types)
            return {
                "export_types": export_types,
                "estimated_items": sum(preview["totals"].values()),
                "estimated_size_kb": preview["estimated_size_kb"],
                "breakdown": preview["totals"]
            }
        except Exception as e:
            self.logger.error(f"Error estimating backup size: {e}")
            return {"export_types": export_types, "estimated_items": 0, "estimated_size_kb": 0}

    def get_backup_preferences(self) -> Dict[str, Any]:
        """Get backup-related preferences with defaults"""
        try:
            self.logger.debug("BACKUP_DEBUG: Starting get_backup_preferences")

            # Get each setting individually with error handling
            enabled = None
            try:
                enabled = self.config.get_bool('backup_enabled', False)
                self.logger.debug(f"BACKUP_DEBUG: backup_enabled = {enabled}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting backup_enabled: {e}")
                enabled = False

            schedule_interval = None
            try:
                schedule_interval = self.config.get('backup_interval', 'weekly')
                self.logger.debug(f"BACKUP_DEBUG: backup_interval = {schedule_interval}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting backup_interval: {e}")
                schedule_interval = 'weekly'

            retention_days = None
            try:
                retention_days = self.config.get_int('backup_retention_count', 5)
                self.logger.debug(f"BACKUP_DEBUG: backup_retention_count = {retention_days}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting backup_retention_count: {e}")
                retention_days = 5

            storage_path = None
            try:
                storage_path = self.config.get_backup_storage_location()
                self.logger.debug(f"BACKUP_DEBUG: storage_path = {storage_path}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting storage_path: {e}")
                storage_path = "special://userdata/addon_data/plugin.video.librarygenie/backups/"

            storage_type = None
            try:
                storage_type = self.config.get('backup_storage_type', 'local')
                self.logger.debug(f"BACKUP_DEBUG: backup_storage_type = {storage_type}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting backup_storage_type: {e}")
                storage_type = 'local'

            include_settings = None
            try:
                include_settings = self.config.get_bool('backup_include_settings', True)
                self.logger.debug(f"BACKUP_DEBUG: backup_include_settings = {include_settings}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting backup_include_settings: {e}")
                include_settings = True

            include_non_library = None
            try:
                include_non_library = self.config.get_bool('backup_include_non_library', False)
                self.logger.debug(f"BACKUP_DEBUG: backup_include_non_library = {include_non_library}")
            except Exception as e:
                self.logger.error(f"BACKUP_DEBUG: Error getting backup_include_non_library: {e}")
                include_non_library = False

            result = {
                'enabled': enabled,
                'schedule_interval': schedule_interval,
                'retention_days': retention_days,
                'storage_path': storage_path,
                'storage_type': storage_type,
                'include_settings': include_settings,
                'include_non_library': include_non_library
            }

            self.logger.debug(f"BACKUP_DEBUG: Final backup preferences: {result}")
            return result

        except Exception as e:
            self.logger.error(f"BACKUP_DEBUG: Exception in get_backup_preferences: {e}")
            return {
                'enabled': False,
                'schedule_interval': 'weekly',
                'retention_days': 5,
                'storage_path': "special://userdata/addon_data/plugin.video.librarygenie/backups/",
                'storage_type': 'local',
                'include_settings': True,
                'include_non_library': False
            }


# Global backup manager instance
_backup_manager_instance = None


def get_backup_manager():
    """Get global backup manager instance"""
    global _backup_manager_instance
    if _backup_manager_instance is None:
        _backup_manager_instance = BackupManager()
    return _backup_manager_instance