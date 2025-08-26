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
        """Run scheduled automatic backup"""
        try:
            self.logger.info("Starting automatic backup")

            # Determine what to backup based on settings
            export_types = ["lists", "list_items"]

            # Add favorites if available
            if self.config.get("backup_include_favorites", True):
                export_types.append("favorites")

            # Add library snapshot if requested
            if self.config.get("backup_include_library", False):
                export_types.append("library_snapshot")

            # Run export
            result = self.export_engine.export_data(
                export_types=export_types,
                file_format="json"
            )

            if result["success"]:
                # Update last backup time
                self._update_last_backup_time()

                # Clean up old backups
                self._cleanup_old_backups()

                self.logger.info(f"Automatic backup completed: {result['filename']}")

                return {
                    "success": True,
                    "filename": result["filename"],
                    "file_size": result["file_size"],
                    "export_types": export_types,
                    "total_items": result["total_items"]
                }
            else:
                self.logger.error(f"Automatic backup failed: {result.get('error')}")
                return {"success": False, "error": result.get("error")}

        except Exception as e:
            self.logger.error(f"Error in automatic backup: {e}")
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backup files"""
        try:
            # Look for backup files in profile directory
            files = self.storage_manager.list_export_files("plugin.video.librarygenie_*_*.json")

            backups = []
            for file_path, filename, file_size in files:
                # Parse filename to extract metadata
                parts = filename.replace(".json", "").split("_")

                if len(parts) >= 4:
                    export_type = "_".join(parts[3:-1])  # Everything between addon name and timestamp
                    timestamp_str = parts[-1]

                    try:
                        # Parse timestamp
                        backup_time = datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")

                        backups.append({
                            "filename": filename,
                            "file_path": file_path,
                            "export_type": export_type,
                            "backup_time": backup_time,
                            "file_size": file_size,
                            "age_days": (datetime.now() - backup_time).days
                        })
                    except ValueError:
                        # Skip files with invalid timestamp format
                        continue

            # Sort by backup time, newest first
            backups.sort(key=lambda x: x["backup_time"], reverse=True)

            return backups

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
        return {
            "enabled": self.config.get("backup_enabled", False),
            "interval": self.config.get("backup_interval", "weekly"),
            "retention_count": self.config.get("backup_retention_count", 5),
            "include_favorites": self.config.get("backup_include_favorites", True),
            "include_library": self.config.get("backup_include_library", False),
            "last_backup": self._get_last_backup_time()
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
            retention_count = self.config.get("backup_retention_count", 5)

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


# Global backup manager instance
_backup_manager_instance = None


def get_backup_manager():
    """Get global backup manager instance"""
    global _backup_manager_instance
    if _backup_manager_instance is None:
        _backup_manager_instance = BackupManager()
    return _backup_manager_instance