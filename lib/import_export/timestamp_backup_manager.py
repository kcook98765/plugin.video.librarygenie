#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Timestamp Backup Manager
Handles timestamped backups with database logging
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .export_engine import get_export_engine
from .storage_manager import get_storage_manager
from ..config import get_config
from ..data.connection_manager import get_connection_manager
from ..utils.logger import get_logger


class TimestampBackupManager:
    """Manages timestamped backups with database tracking"""

    def __init__(self):
        self.logger = get_logger(__name__)
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
                self.logger.debug(f"Backup storage path does not exist: {storage_path}")
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
                        self.logger.warning(f"Error getting stats for backup file {filename}: {e}")
                        continue

            # Sort by modification time, newest first
            backups.sort(key=lambda x: x['modified_time'], reverse=True)

            self.logger.debug(f"Found {len(backups)} backup files")
            return backups

        except Exception as e:
            self.logger.error(f"Error listing backups: {e}")
            return []

    def run_automatic_backup(self) -> Dict[str, Any]:
        """Run automatic timestamped backup"""
        try:
            self.logger.info("Starting automatic timestamped backup")

            # Check if backup is worthy
            worthiness = self._validate_backup_worthiness()
            if not worthiness["worthy"]:
                self.logger.info(f"Skipping backup: {worthiness['reason']}")
                return {"success": False, "reason": "not_worthy", "message": worthiness["reason"]}

            # Run export
            export_types = ["lists", "list_items", "folders"]
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

            self.logger.info(f"Backup stored in settings location: {backup_path}")

            # Log to database
            self._log_backup_to_database("automatic", backup_filename, backup_path, result)

            # Cleanup old backups
            self._cleanup_old_backups()

            self.logger.info(f"Automatic backup completed: {backup_filename}")

            return {
                "success": True,
                "filename": backup_filename,
                "file_path": backup_path,
                "items_exported": result.get("items_exported", 0)
            }

        except Exception as e:
            self.logger.error(f"Error in automatic backup: {e}")
            return {"success": False, "error": str(e)}

    def restore_backup(self, file_path: str, replace_mode: bool = False) -> Dict[str, Any]:
        """Restore from backup file"""
        try:
            from .import_engine import get_import_engine
            import_engine = get_import_engine()

            # Restore the backup
            result = import_engine.restore_backup(file_path, replace_mode)

            if result["success"]:
                self.logger.info(f"Backup restored successfully from {file_path}")
            else:
                self.logger.error(f"Backup restore failed from {file_path}: {result.get('errors', [])}")

            return result

        except Exception as e:
            self.logger.error(f"Error restoring backup: {e}")
            return {"success": False, "error": str(e)}

    def _get_backup_file_path(self, filename: str) -> str:
        """Get full path for backup file"""
        storage_path = self.config.get_backup_storage_location()

        # Handle special:// paths
        if storage_path.startswith('special://'):
            import xbmcvfs
            storage_path = xbmcvfs.translatePath(storage_path)

        return os.path.join(storage_path, filename)

    def _log_backup_to_database(self, backup_type: str, filename: str, file_path: str, export_result: Dict[str, Any]):
        """Log backup operation to database"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO backup_history 
                    (backup_type, filename, file_path, storage_type, export_types, 
                     file_size, items_count, success, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    backup_type,
                    filename,
                    file_path,
                    'local',
                    '["lists", "list_items", "folders"]',
                    export_result.get("file_size", 0),
                    export_result.get("items_exported", 0),
                    1,
                    datetime.now().isoformat()
                ])

        except Exception as e:
            self.logger.warning(f"Failed to log backup to database: {e}")

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
                    self.logger.debug(f"Deleted old backup: {backup['filename']}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete backup {backup['filename']}: {e}")

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old backup files")

        except Exception as e:
            self.logger.error(f"Error cleaning up old backups: {e}")

    def _validate_backup_worthiness(self) -> Dict[str, Any]:
        """Check if backup contains meaningful user data"""
        try:
            # Get query manager
            from ..data.query_manager import get_query_manager
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

            self.logger.debug(f"Backup worthiness check: {user_lists} lists, {total_items} items, {user_folders} folders")

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
            self.logger.warning(f"Error validating backup worthiness: {e}")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Timestamp Backup Manager
Enhanced backup manager with automated timestamps and flexible storage
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
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
        self.conn_manager = get_connection_manager()

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

            # Check if there's meaningful data to backup
            validation_result = self._validate_backup_worthiness()
            if not validation_result["worthy"]:
                self.logger.info(f"Skipping backup: {validation_result['reason']}")
                return {
                    "success": False,
                    "skipped": True,
                    "reason": validation_result["reason"],
                    "message": "Backup skipped - no user data to backup"
                }

            # Generate timestamp with fallback
            timestamp_format = "%Y%m%d-%H%M%S"  # Use hardcoded format since setting may not exist
            timestamp = datetime.now().strftime(timestamp_format)

            # Determine what to backup based on settings
            export_types = ["lists", "list_items"]  # Don't backup media_items - those are maintained by the addon

            # Only add optional types if they're explicitly enabled or if config is unavailable
            try:
                if self.config.get("backup_include_non_library", False):
                    export_types.append("non_library_snapshot")

                if self.config.get("backup_include_folders", True):  # Default to True for complete backups
                    export_types.append("folders")
            except Exception as e:
                self.logger.warning(f"Error reading backup config, using defaults: {e}")
                # Use minimal safe defaults if config fails
                pass

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

    def run_manual_backup(self, force: bool = False) -> Dict[str, Any]:
        """Run manual backup with timestamp"""
        try:
            self.logger.info("Starting manual timestamped backup")

            # Check if there's meaningful data to backup (unless forced)
            if not force:
                validation_result = self._validate_backup_worthiness()
                if not validation_result["worthy"]:
                    self.logger.info(f"Manual backup validation failed: {validation_result['reason']}")
                    return {
                        "success": False,
                        "skipped": True,
                        "manual": True,
                        "reason": validation_result["reason"],
                        "message": "Manual backup skipped - no user data to backup. Use 'force' option to backup anyway."
                    }

            # Force run regardless of schedule
            # Temporarily bypass validation for the automatic backup call
            original_method = self._validate_backup_worthiness
            if force:
                self._validate_backup_worthiness = lambda: {"worthy": True, "reason": "forced"}

            try:
                result = self.run_automatic_backup()
                result["manual"] = True
                return result
            finally:
                if force:
                    self._validate_backup_worthiness = original_method

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

    def get_available_backups(self) -> List[Dict[str, Any]]:
        """Get available backups - alias for list_backups for compatibility"""
        return self.list_backups()

    def restore_backup(self, backup_info, replace_mode: bool = True) -> Dict[str, Any]:
        """Restore from a timestamped backup"""
        try:
            # Handle both string filepath and dict backup_info formats
            if isinstance(backup_info, str):
                # Legacy format - backup_info is filepath
                filepath = backup_info
                backup_dict = {"file_path": filepath}
            else:
                # New format - backup_info is dict
                backup_dict = backup_info

            storage_type = self.config.get_backup_storage_type()

            if storage_type == "local":
                return self._restore_local_backup(backup_dict, replace_mode)
            else:
                return {"success": False, "error": "Unknown storage type"}

        except Exception as e:
            self.logger.error(f"Error restoring backup: {e}")
            return {"success": False, "error": str(e)}

    def _store_backup(self, source_file: str, filename: str) -> Dict[str, Any]:
        """Store backup in configured location"""
        try:
            storage_type = self.config.get_backup_storage_type()

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
            # Get backup directory from settings with fallback
            backup_dir = None
            try:
                from ..config.settings import SettingsManager
                settings = SettingsManager()
                if settings:
                    backup_dir = settings.get_backup_storage_location()
            except Exception as settings_error:
                self.logger.warning(f"Error getting backup directory from SettingsManager: {settings_error}")

            # Fallback to config manager if settings manager fails
            if not backup_dir:
                try:
                    backup_dir = self.config.get_backup_storage_location()
                except Exception as config_error:
                    self.logger.warning(f"Error getting backup directory from config: {config_error}")

            # Ultimate fallback to default location
            if not backup_dir:
                backup_dir = "special://userdata/addon_data/plugin.video.library.genie/backups/"
                self.logger.info(f"Using fallback backup directory: {backup_dir}")

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
            # Get storage location with fallback
            storage_location = None
            try:
                from ..config.settings import SettingsManager
                settings = SettingsManager()
                if settings:
                    storage_location = settings.get_backup_storage_location()
            except Exception as settings_error:
                self.logger.warning(f"Error getting storage location from SettingsManager: {settings_error}")

            # Fallback to config manager if settings manager fails
            if not storage_location:
                try:
                    storage_location = self.config.get_backup_storage_location()
                except Exception as config_error:
                    self.logger.warning(f"Error getting storage location from config: {config_error}")

            # Ultimate fallback to default location
            if not storage_location:
                storage_location = "special://userdata/addon_data/plugin.video.library.genie/backups/"
                self.logger.info(f"Using fallback storage location: {storage_location}")

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
            # Get backup directory from settings with fallback
            backup_dir = None
            try:
                from ..config.settings import SettingsManager
                settings = SettingsManager()
                if settings:
                    backup_dir = settings.get_backup_storage_location()
            except Exception as settings_error:
                self.logger.warning(f"Error getting backup directory from SettingsManager: {settings_error}")

            # Fallback to config manager if settings manager fails
            if not backup_dir:
                try:
                    backup_dir = self.config.get_backup_storage_location()
                except Exception as config_error:
                    self.logger.warning(f"Error getting backup directory from config: {config_error}")

            # Ultimate fallback to default location
            if not backup_dir:
                backup_dir = "special://userdata/addon_data/plugin.video.library.genie/backups/"
                self.logger.info(f"Using fallback backup directory: {backup_dir}")

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

    def _restore_local_backup(self, backup_info: Dict[str, Any], replace_mode: bool = True) -> Dict[str, Any]:
        """Restore from local backup"""
        try:
            file_path = backup_info["file_path"]
            content = self.storage_manager.read_file_safe(file_path)

            if not content:
                return {"success": False, "error": "Failed to read backup file"}

            # Parse and import backup
            from .import_engine import get_import_engine
            import_engine = get_import_engine()

            filename = backup_info.get("filename", "backup")

            # Create safety backup before replace mode
            if replace_mode:
                try:
                    safety_result = self.run_manual_backup()
                    if safety_result.get("success"):
                        self.logger.info(f"Created safety backup before restore: {safety_result.get('filename')}")
                    else:
                        self.logger.warning(f"Failed to create safety backup: {safety_result.get('error')}")
                except Exception as e:
                    self.logger.warning(f"Error creating safety backup: {e}")

            result = import_engine.import_from_content(content, filename, replace_mode=replace_mode)
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
        except Exception:
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
            try:
                retention_count = int(retention_count)
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid retention count: {retention_count}, defaulting to 5")
                retention_count = 5

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

    def _validate_backup_worthiness(self) -> Dict[str, Any]:
        """Check if there's meaningful user data worth backing up"""
        try:
            from ..data.query_manager import get_query_manager

            query_manager = get_query_manager()
            if not query_manager.initialize():
                return {"worthy": False, "reason": "Database not accessible"}

            # Count user lists (excluding system folders)
            lists_count = query_manager.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                WHERE f.name != 'Search History' OR f.name IS NULL
            """)

            user_lists = lists_count.get('count', 0) if lists_count else 0

            # Count total list items
            items_count = query_manager.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM list_items
            """)

            total_items = items_count.get('count', 0) if items_count else 0

            # Count user-created folders (excluding Search History)
            folders_count = query_manager.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM folders 
                WHERE name != 'Search History'
            """)

            user_folders = folders_count.get('count', 0) if folders_count else 0

            self.logger.debug(f"Backup worthiness check: {user_lists} lists, {total_items} items, {user_folders} folders")

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
            self.logger.warning(f"Error validating backup worthiness: {e}")
            # If we can't validate, err on the side of allowing backup
            return {"worthy": True, "reason": "Validation failed, allowing backup"}

    def _get_backup_preferences(self) -> Dict[str, Any]:
        """Get backup preferences from config with detailed debugging"""
        try:
            self.logger.debug("BACKUP_DEBUG: Getting backup preferences from config")
            config = get_config()

            # Get each setting individually with debugging
            self.logger.debug("BACKUP_DEBUG: Getting individual backup settings...")
            enabled = config.get_backup_enabled()
            storage_type = config.get_backup_storage_type()
            include_non_library = config.get_backup_include_non_library()
            include_folders = config.get_backup_include_folders()
            retention_count = config.get_backup_retention_count()
            storage_location = config.get_backup_storage_location()

            self.logger.debug(f"BACKUP_DEBUG: Individual settings retrieved:")
            self.logger.debug(f"BACKUP_DEBUG:   enabled = {enabled}")
            self.logger.debug(f"BACKUP_DEBUG:   storage_type = {storage_type}")
            self.logger.debug(f"BACKUP_DEBUG:   include_non_library = {include_non_library}")
            self.logger.debug(f"BACKUP_DEBUG:   include_folders = {include_folders}")
            self.logger.debug(f"BACKUP_DEBUG:   retention_count = {retention_count}")
            self.logger.debug(f"BACKUP_DEBUG:   storage_location = {storage_location}")

            # Now try the original method for comparison
            self.logger.debug("BACKUP_DEBUG: Getting full backup preferences...")
            full_prefs = config.get_backup_preferences()
            self.logger.debug(f"BACKUP_DEBUG: Full preferences: {full_prefs}")

            return full_prefs

        except Exception as e:
            self.logger.error(f"BACKUP_DEBUG: Error getting backup preferences: {type(e).__name__}: {e}")
            return {
                'enabled': False,
                'storage_type': 'local',
                'include_settings': True,
                'include_non_library': False,
                'retention_days': 5
            }


# Global instance
_timestamp_backup_manager_instance = None


def get_timestamp_backup_manager():
    """Get global timestamp backup manager instance"""
    global _timestamp_backup_manager_instance
    if _timestamp_backup_manager_instance is None:
        _timestamp_backup_manager_instance = TimestampBackupManager()
    return _timestamp_backup_manager_instance