#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Timestamp Backup Manager
Enhanced backup manager with automated timestamps and flexible storage
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from .export_engine import get_export_engine
from .storage_manager import get_storage_manager
from ..config import get_config
from ..utils.logger import get_logger


class TimestampBackupManager:
    """Enhanced backup manager with timestamp automation and storage flexibility"""

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
            interval = self.config.get("backup_interval", "weekly")

            # Get last backup time
            last_backup = self._get_last_backup_time()
            if not last_backup:
                # No previous backup, should run
                return True

            # Calculate next backup time based on interval
            now = datetime.now()
            if interval == "hourly":
                next_backup = last_backup + timedelta(hours=1)
            elif interval == "daily":
                next_backup = last_backup + timedelta(days=1)
            elif interval == "weekly":
                next_backup = last_backup + timedelta(days=7)
            elif interval == "monthly":
                next_backup = last_backup + timedelta(days=30)
            else:
                # Default to weekly if unknown interval
                next_backup = last_backup + timedelta(days=7)

            return now >= next_backup

        except Exception as e:
            self.logger.error(f"Error checking backup schedule: {e}")
            return False

    def run_automatic_backup(self) -> Dict[str, Any]:
        """Run scheduled automatic backup with timestamp"""
        try:
            self.logger.info("Starting automatic timestamped backup")

            # Generate timestamp with fallback
            timestamp_format = "%Y%m%d-%H%M%S"  # Use hardcoded format since setting may not exist
            timestamp = datetime.now().strftime(timestamp_format)

            # Determine what to backup based on settings
            export_types = ["lists", "list_items"]

            # Only add optional types if they're explicitly enabled or if config is unavailable
            try:
                if self.config.get("backup_include_favorites", True):
                    export_types.append("favorites")

                if self.config.get("backup_include_library", False):
                    export_types.append("library_snapshot")

                if self.config.get("backup_include_folders", False):  # Changed default to False for safety
                    export_types.append("folders")
            except Exception as e:
                self.logger.warning(f"Error reading backup config, using defaults: {e}")
                # Use minimal safe defaults if config fails
                export_types.append("favorites")

            # Generate filename with timestamp
            prefix = "librarygenie"  # Use hardcoded prefix since setting may not exist
            filename = f"{prefix}_backup_{timestamp}.json"

            # Run export
            result = self.export_engine.export_data(
                export_types=export_types,
                file_format="json"
            )

            if result["success"]:
                # Store backup based on storage type
                actual_filename = result.get("filename", filename)
                storage_result = self._store_backup(result["file_path"], actual_filename)

                if storage_result["success"]:
                    # Update last backup time
                    self._update_last_backup_time()

                    # Clean up old backups
                    self._cleanup_old_backups()

                    self.logger.info(f"Automatic backup completed: {result.get('filename', filename)}")

                    return {
                        "success": True,
                        "filename": result.get("filename", filename),
                        "timestamp": timestamp,
                        "file_size": result.get("file_size", 0),
                        "export_types": export_types,
                        "total_items": result.get("total_items", 0),
                        "storage_location": storage_result["location"]
                    }
                else:
                    self.logger.error(f"Backup storage failed: {storage_result.get('error')}")
                    return {"success": False, "error": f"Storage failed: {storage_result.get('error')}"}
            else:
                self.logger.error(f"Automatic backup failed: {result.get('error')}")
                return {"success": False, "error": result.get("error")}

        except Exception as e:
            self.logger.error(f"Error in automatic backup: {e}")
            return {"success": False, "error": str(e)}

    def run_manual_backup(self) -> Dict[str, Any]:
        """Run manual backup with timestamp"""
        try:
            self.logger.info("Starting manual timestamped backup")

            # Force run regardless of schedule
            result = self.run_automatic_backup()
            result["manual"] = True

            return result

        except Exception as e:
            self.logger.error(f"Error in manual backup: {e}")
            return {"success": False, "error": str(e)}

    def test_backup_configuration(self) -> Dict[str, Any]:
        """Test backup configuration without creating actual backup"""
        try:
            storage_type = self.config.get("backup_storage_type", "local")

            if storage_type == "local":
                return self._test_local_storage()
            else:
                return {"success": False, "error": "Only local storage is supported"}

        except Exception as e:
            self.logger.error(f"Error testing backup configuration: {e}")
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backup files from all storage locations"""
        try:
            storage_type = self.config.get("backup_storage_type", "local")

            if storage_type == "local":
                return self._list_local_backups()
            else:
                return []

        except Exception as e:
            self.logger.error(f"Error listing backups: {e}")
            return []

    def restore_backup(self, backup_info: Dict[str, Any]) -> Dict[str, Any]:
        """Restore from a timestamped backup"""
        try:
            storage_type = self.config.get("backup_storage_type", "local")

            if storage_type == "local":
                return self._restore_local_backup(backup_info)
            else:
                return {"success": False, "error": "Unknown storage type"}

        except Exception as e:
            self.logger.error(f"Error restoring backup: {e}")
            return {"success": False, "error": str(e)}

    def _store_backup(self, source_file: str, filename: str) -> Dict[str, Any]:
        """Store backup in configured location"""
        try:
            storage_type = self.config.get("backup_storage_type", "local")

            if storage_type == "local":
                return self._store_local_backup(source_file, filename)
            else:
                return {"success": False, "error": "Unknown storage type"}

        except Exception as e:
            self.logger.error(f"Error storing backup: {e}")
            return {"success": False, "error": str(e)}

    def _store_local_backup(self, source_file: str, filename: str) -> Dict[str, Any]:
        """Store backup in settings-configured location"""
        try:
            # Get backup directory from settings
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            backup_dir = settings.get_backup_storage_location()

            # Handle special:// paths
            if backup_dir.startswith("special://"):
                import xbmcvfs
                backup_dir = xbmcvfs.translatePath(backup_dir)

            # Ensure directory exists
            os.makedirs(backup_dir, exist_ok=True)

            # Destination path
            dest_path = os.path.join(backup_dir, filename)

            # Check if source and destination are the same
            if os.path.abspath(source_file) == os.path.abspath(dest_path):
                # File is already in the correct location
                self.logger.info(f"Backup already in correct location: {dest_path}")
                return {
                    "success": True,
                    "location": dest_path,
                    "storage_type": "local"
                }

            # Copy file to backup location
            import shutil
            shutil.copy2(source_file, dest_path)

            # Clean up temporary file
            try:
                os.remove(source_file)
            except Exception as cleanup_error:
                self.logger.warning(f"Failed to cleanup temp file {source_file}: {cleanup_error}")

            self.logger.info(f"Backup stored in settings location: {dest_path}")

            return {
                "success": True,
                "location": dest_path,
                "storage_type": "local"
            }

        except Exception as e:
            self.logger.error(f"Error storing local backup: {e}")
            return {"success": False, "error": str(e)}

    def _test_local_storage(self) -> Dict[str, Any]:
        """Test local storage configuration"""
        try:
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            storage_location = settings.get_backup_storage_location()

            # Handle special:// paths
            if storage_location.startswith("special://"):
                import xbmcvfs
                test_path = xbmcvfs.translatePath(storage_location)
            else:
                test_path = storage_location

            # Ensure directory exists
            os.makedirs(test_path, exist_ok=True)

            if not os.path.exists(test_path):
                return {"success": False, "error": f"Storage path does not exist: {test_path}"}
            if not os.access(test_path, os.W_OK):
                return {"success": False, "error": f"No write permission: {test_path}"}

            # Test write access
            test_file = os.path.join(test_path, "test_backup.tmp")
            if self.storage_manager.write_file_atomic(test_file, "test"):
                os.remove(test_file)
                return {
                    "success": True,
                    "message": f"Local storage ready: {test_path}",
                    "path": test_path
                }
            else:
                return {"success": False, "error": "Failed to write test file"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _list_local_backups(self) -> List[Dict[str, Any]]:
        """List local backup files from settings-configured location"""
        try:
            # Get backup directory from settings
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            backup_dir = settings.get_backup_storage_location()

            # Handle special:// paths
            if backup_dir.startswith("special://"):
                import xbmcvfs
                backup_dir = xbmcvfs.translatePath(backup_dir)

            if not os.path.exists(backup_dir):
                return []

            # Look for backup files from both old and new naming schemes
            backups = []
            patterns = [
                "librarygenie_backup_*.json",  # New timestamp backup format
                "plugin.video.librarygenie_*_*.json",  # Old backup format
                "plugin.video.library.genie_*_*.json"  # Current export format
            ]

            from pathlib import Path
            for pattern in patterns:
                for file_path in Path(backup_dir).glob(pattern):
                    if file_path.is_file():
                        # Parse filename to extract timestamp
                        filename = file_path.name

                        # Handle different naming formats
                        if filename.startswith("librarygenie_backup_"):
                            # New format: librarygenie_backup_TIMESTAMP.json
                            timestamp_str = filename.replace("librarygenie_backup_", "").replace(".json", "")
                        else:
                            # Old format: plugin.video.librarygenie_TYPE_TIMESTAMP.json
                            parts = filename.replace(".json", "").split("_")
                            if len(parts) >= 2:
                                timestamp_str = parts[-1]
                            else:
                                continue

                        try:
                            # Parse timestamp
                            backup_time = datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")
                            stat = file_path.stat()

                            backups.append({
                                "filename": filename,
                                "file_path": str(file_path),
                                "backup_time": backup_time,
                                "file_size": int(stat.st_size),
                                "age_days": (datetime.now() - backup_time).days,
                                "storage_type": "local"
                            })
                        except ValueError:
                            # Skip files with invalid timestamp format
                            continue

            # Remove duplicates (same timestamp) and sort by backup time, newest first
            seen_timestamps = set()
            unique_backups = []
            for backup in sorted(backups, key=lambda x: x["backup_time"], reverse=True):
                timestamp_key = backup["backup_time"].strftime("%Y%m%d-%H%M%S")
                if timestamp_key not in seen_timestamps:
                    seen_timestamps.add(timestamp_key)
                    unique_backups.append(backup)

            return unique_backups

        except Exception as e:
            self.logger.error(f"Error listing local backups: {e}")
            return []

    def _restore_local_backup(self, backup_info: Dict[str, Any]) -> Dict[str, Any]:
        """Restore from local backup"""
        try:
            file_path = backup_info["file_path"]
            content = self.storage_manager.read_file_safe(file_path)

            if not content:
                return {"success": False, "error": "Failed to read backup file"}

            # Parse and import backup
            from .import_engine import get_import_engine
            import_engine = get_import_engine()

            result = import_engine.import_from_content(content, backup_info["filename"])
            return result

        except Exception as e:
            self.logger.error(f"Error restoring local backup: {e}")
            return {"success": False, "error": str(e)}

    def _get_last_backup_time(self) -> Optional[datetime]:
        """Get timestamp of last backup"""
        try:
            backups = self.list_backups()
            if backups:
                return backups[0]["backup_time"]  # Most recent backup
            return None
        except:
            return None

    def _update_last_backup_time(self):
        """Update last backup timestamp"""
        try:
            now = datetime.now()
            self.logger.debug(f"Backup completed at {now}")
        except Exception as e:
            self.logger.error(f"Error updating backup time: {e}")

    def _cleanup_old_backups(self):
        """Clean up old backup files based on retention policy"""
        try:
            retention_count = self.config.get("backup_retention_count", 5)
            backups = self.list_backups()

            if len(backups) <= retention_count:
                return  # Nothing to clean up

            # Delete oldest backups
            backups_to_delete = backups[retention_count:]
            deleted_count = 0

            for backup in backups_to_delete:
                if self.delete_backup(backup):
                    deleted_count += 1

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old backup files")

        except Exception as e:
            self.logger.error(f"Error cleaning up backups: {e}")

    def delete_backup(self, backup_info: Dict[str, Any]) -> bool:
        """Delete specific backup file"""
        try:
            storage_type = backup_info.get("storage_type", "local")

            if storage_type == "local":
                return self.storage_manager.delete_file_safe(backup_info["file_path"])
            else:
                return False

        except Exception as e:
            self.logger.error(f"Error deleting backup: {e}")
            return False


# Global instance
_timestamp_backup_manager_instance = None


def get_timestamp_backup_manager():
    """Get global timestamp backup manager instance"""
    global _timestamp_backup_manager_instance
    if _timestamp_backup_manager_instance is None:
        _timestamp_backup_manager_instance = TimestampBackupManager()
    return _timestamp_backup_manager_instance