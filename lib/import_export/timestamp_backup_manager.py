#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Timestamp Backup Manager
Handles timestamped backups with database tracking
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from lib.import_export.export_engine import get_export_engine
from lib.import_export.storage_manager import get_storage_manager
from lib.config import get_config
from lib.data.connection_manager import get_connection_manager
from lib.utils.kodi_log import get_kodi_logger


class TimestampBackupManager:
    """Manages timestamped backups with database tracking"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.timestamp_backup_manager')
        self.export_engine = get_export_engine()
        self.storage_manager = get_storage_manager()
        self.config = get_config()
        self.conn_manager = get_connection_manager()

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backup files"""
        try:
            backups = []

            # Get backup storage location
            storage_path = self.config.get_backup_storage_location()

            # Handle special:// paths
            if storage_path.startswith('special://'):
                import xbmcvfs
                storage_path = xbmcvfs.translatePath(storage_path)

            if not os.path.exists(storage_path):
                self.logger.debug("Backup storage path does not exist: %s", storage_path)
                return []

            # List backup files
            for filename in os.listdir(storage_path):
                if filename.startswith('plugin.video.library.genie_') and filename.endswith('.json'):
                    file_path = os.path.join(storage_path, filename)
                    try:
                        file_stat = os.stat(file_path)
                        file_size = file_stat.st_size
                        modified_time = datetime.fromtimestamp(file_stat.st_mtime)
                        age_days = (datetime.now() - modified_time).days

                        backups.append({
                            'filename': filename,
                            'file_path': file_path,
                            'file_size': file_size,
                            'modified_time': modified_time.isoformat(),
                            'age_days': age_days
                        })
                    except (OSError, ValueError) as e:
                        self.logger.warning("Error getting stats for backup file %s: %s", filename, e)
                continue

            # Sort by modification time, newest first
            backups.sort(key=lambda x: x['modified_time'], reverse=True)

            self.logger.debug("Found %s backup files", len(backups))
            return backups

        except Exception as e:
            self.logger.error("Error listing backups: %s", e)
            return []

    def run_automatic_backup(self) -> Dict[str, Any]:
        """Run automatic timestamped backup"""
        try:
            self.logger.info("Starting automatic timestamped backup")

            # Check if backup is worthy
            worthiness = self._validate_backup_worthiness()
            if not worthiness["worthy"]:
                self.logger.info("Skipping backup: %s", worthiness['reason'])
                return {"success": False, "reason": "not_worthy", "message": worthiness["reason"]}

            # Determine what to backup based on settings
            export_types = ["lists", "list_items"]
            
            # Check if external items should be included
            if self.config.get_bool("backup_include_non_library", False):
                export_types.append("non_library_snapshot")
            
            # Check if folders should be included  
            if self.config.get_bool("backup_include_folders", True):
                export_types.append("folders")
                
            result = self.export_engine.export_data(export_types, file_format="json")

            if not result["success"]:
                return {"success": False, "error": result.get("error", "Export failed")}

            # Move to backup location
            temp_file = result["file_path"]
            backup_filename = os.path.basename(temp_file)
            backup_path = self._get_backup_file_path(backup_filename)

            # Ensure backup directory exists
            backup_dir = os.path.dirname(backup_path)
            os.makedirs(backup_dir, exist_ok=True)

            # Move file to backup location
            import shutil
            shutil.move(temp_file, backup_path)

            self.logger.info("Backup stored in settings location: %s", backup_path)

            # Database logging removed to reduce storage overhead on user devices

            # Cleanup old backups
            self._cleanup_old_backups()

            self.logger.info("Automatic backup completed: %s", backup_filename)

            return {
                "success": True,
                "filename": backup_filename,
                "file_path": backup_path,
                "items_exported": result.get("items_exported", 0)
            }

        except Exception as e:
            self.logger.error("Error in automatic backup: %s", e)
            return {"success": False, "error": str(e)}

    def restore_backup(self, file_path: str, replace_mode: bool = False) -> Dict[str, Any]:
        """Restore from backup file"""
        try:
            from lib.import_export.import_engine import get_import_engine
            import_engine = get_import_engine()

            # Read backup file content
            content = self.storage_manager.read_file_safe(file_path)
            if content is None:
                return {"success": False, "error": "Could not read backup file"}

            # Extract filename from path for import
            filename = os.path.basename(file_path)

            # Restore the backup using import_from_content
            result = import_engine.import_from_content(content, filename, replace_mode)

            if result["success"]:
                self.logger.info("Backup restored successfully from %s", file_path)
            else:
                self.logger.error("Backup restore failed from %s: %s", file_path, result.get('errors', []))

            return result

        except Exception as e:
            self.logger.error("Error restoring backup: %s", e)
            return {"success": False, "error": str(e)}

    def _get_backup_file_path(self, filename: str) -> str:
        """Get full path for backup file"""
        storage_path = self.config.get_backup_storage_location()

        # Handle special:// paths
        if storage_path.startswith('special://'):
            import xbmcvfs
            storage_path = xbmcvfs.translatePath(storage_path)

        return os.path.join(storage_path, filename)

    def _cleanup_old_backups(self):
        """Clean up old backup files based on retention policy"""
        try:
            retention_count = self.config.get_int("backup_retention_count", 5)

            backups = self.list_backups()
            if len(backups) <= retention_count:
                return

            backups_to_delete = backups[retention_count:]
            deleted_count = 0

            for backup in backups_to_delete:
                try:
                    os.remove(backup["file_path"])
                    deleted_count += 1
                    self.logger.debug("Deleted old backup: %s", backup['filename'])
                except OSError as e:
                    self.logger.warning("Failed to delete backup %s: %s", backup['filename'], e)

            if deleted_count > 0:
                self.logger.info("Cleaned up %s old backup files", deleted_count)

        except Exception as e:
            self.logger.error("Error cleaning up old backups: %s", e)

    def _validate_backup_worthiness(self) -> Dict[str, Any]:
        """Check if backup contains meaningful user data"""
        try:
            # Get query manager
            from lib.data.query_manager import get_query_manager
            query_manager = get_query_manager()

            # Count user lists (excluding Search History and Kodi Favorites)
            lists_count = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM lists 
                WHERE name NOT IN ('Search History', 'Kodi Favorites')
            """)

            user_lists = lists_count.get('count', 0) if lists_count else 0

            # Count total list items
            items_count = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM list_items
            """)

            total_items = items_count.get('count', 0) if items_count else 0

            # Count user-created folders (excluding Search History)
            folders_count = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM folders 
                WHERE name != 'Search History'
            """)

            user_folders = folders_count.get('count', 0) if folders_count else 0

            self.logger.debug("Backup worthiness check: %s lists, %s items, %s folders", user_lists, total_items, user_folders)

            # Backup is worthy if there are user lists, items, or folders
            if user_lists > 0 or total_items > 0 or user_folders > 0:
                return {
                    "worthy": True, 
                    "reason": f"Found {user_lists} lists, {total_items} items, {user_folders} folders"
                }
            else:
                return {
                    "worthy": False, 
                    "reason": "No user lists, items, or folders found (only system data)"
                }

        except Exception as e:
            self.logger.warning("Error validating backup worthiness: %s", e)
            # If we can't validate, err on the side of allowing backup
            return {"worthy": True, "reason": "Validation failed, allowing backup"}


# Global timestamp backup manager instance
_timestamp_backup_manager_instance = None


def get_timestamp_backup_manager():
    """Get global timestamp backup manager instance"""
    global _timestamp_backup_manager_instance
    if _timestamp_backup_manager_instance is None:
        _timestamp_backup_manager_instance = TimestampBackupManager()
    return _timestamp_backup_manager_instance