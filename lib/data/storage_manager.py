#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Storage Manager
Handles file system paths and storage locations using proper Kodi addon methods
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
import xbmcvfs
import xbmcaddon

from lib.utils.kodi_log import get_kodi_logger


class StorageManager:
    """Manages file system paths and storage locations using Kodi addon methods"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.data.storage_manager')
        self._addon = xbmcaddon.Addon()
        self._profile_path = None

    def get_profile_path(self) -> str:
        """Get addon profile directory path with improved fallback handling"""
        if self._profile_path:
            return self._profile_path

        try:
            profile_path = self._addon.getAddonInfo('profile')
            # Ensure the path is properly translated from special:// format
            if profile_path.startswith('special://'):
                translated_path = xbmcvfs.translatePath(profile_path)
                if translated_path and translated_path != 'special:':
                    # Ensure directory exists
                    if not xbmcvfs.exists(translated_path):
                        xbmcvfs.mkdirs(translated_path)
                    self._profile_path = translated_path
                    return self._profile_path
            # If it's not a special:// path or translation failed/was invalid, use it directly if valid
            if profile_path and not profile_path.startswith('special:'):
                # Ensure directory exists
                if not xbmcvfs.exists(profile_path):
                    xbmcvfs.mkdirs(profile_path)
                self._profile_path = profile_path
                return self._profile_path
            
            # Fallback if path is empty or 'special:'
            self.logger.warning("Invalid or empty profile path detected, using fallback.")
            fallback_path = os.path.join(os.getcwd(), "data")
            os.makedirs(fallback_path, exist_ok=True)
            self._profile_path = fallback_path
            return self._profile_path

        except Exception as e:
            self.logger.error("Error getting profile path: %s", e)
            # Emergency fallback
            fallback_path = os.path.join(os.getcwd(), "data")
            os.makedirs(fallback_path, exist_ok=True)
            return fallback_path

    def get_database_path(self):
        """Get the database file path using proper Kodi addon profile directory"""
        try:
            profile_dir = self.get_profile_path()
            db_path = os.path.join(profile_dir, 'librarygenie.db')
            self.logger.debug("Using Kodi addon profile database path: %s", db_path)
            return db_path

        except Exception as e:
            self.logger.error("Failed to get database path: %s", e)
            raise RuntimeError(f"Cannot initialize database - profile path unavailable: {e}")

    def get_cache_dir(self):
        """Get cache directory path using proper Kodi addon profile"""
        try:
            profile_dir = self.get_profile_path()
            cache_dir = os.path.join(profile_dir, 'cache')

            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)

            return cache_dir

        except Exception as e:
            self.logger.error("Failed to get cache directory: %s", e)
            raise RuntimeError(f"Cannot initialize cache directory: {e}")

    def get_temp_dir(self):
        """Get temporary directory path using proper Kodi addon profile"""
        try:
            profile_dir = self.get_profile_path()
            temp_dir = os.path.join(profile_dir, 'temp')

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)

            return temp_dir

        except Exception as e:
            self.logger.error("Failed to get temp directory: %s", e)
            raise RuntimeError(f"Cannot initialize temp directory: {e}")

    def generate_filename(self, export_type: str, file_format: str = "json") -> str:
        """Generate timestamped filename for export"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"plugin.video.library.genie_{export_type}_{timestamp}.{file_format}"

    def write_file_atomic(self, file_path: str, content: str) -> bool:
        """Write file atomically with temp file and rename"""
        try:
            # Validate file path
            if not file_path or file_path.startswith('special:'):
                self.logger.error("Invalid file path: %s", file_path)
                return False
            
            # Ensure parent directory exists
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # Write to temporary file first
            temp_path = f"{file_path}.tmp"

            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Atomic rename
            shutil.move(temp_path, file_path)

            self.logger.info("File written atomically: %s", file_path)
            return True

        except Exception as e:
            self.logger.error("Error writing file atomically: %s", e)

            # Clean up temp file if it exists
            temp_path = f"{file_path}.tmp"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            return False

    def read_file_safe(self, file_path: str) -> Optional[str]:
        """Read file with error handling"""
        try:
            if not self.validate_file_path(file_path) or not os.path.exists(file_path):
                self.logger.warning("File not found or invalid path: %s", file_path)
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.logger.debug("File read successfully: %s", file_path)
            return content

        except Exception as e:
            self.logger.error("Error reading file %s: %s", file_path, e)
            return None

    def list_export_files(self, pattern: str = "*") -> List[Tuple[str, str, int]]:
        """List export files in profile directory"""
        try:
            profile_path = self.get_profile_path()
            files = []

            # Use Path.glob for pattern matching
            for file_path in Path(profile_path).glob(pattern):
                if file_path.is_file():
                    # Ensure the file path is valid before accessing stats
                    if self.validate_file_path(str(file_path)):
                        stat = file_path.stat()
                        files.append((
                            str(file_path),
                            file_path.name,
                            int(stat.st_size)
                        ))
                    else:
                        self.logger.warning("Skipping invalid file path during listing: %s", file_path)

            # Sort by modification time, newest first
            files.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
            return files

        except Exception as e:
            self.logger.error("Error listing export files: %s", e)
            return []

    def delete_file_safe(self, file_path: str) -> bool:
        """Delete file with error handling"""
        try:
            if self.validate_file_path(file_path) and os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info("File deleted: %s", file_path)
                return True
            elif not self.validate_file_path(file_path):
                self.logger.warning("Attempted to delete invalid file path: %s", file_path)
                return False
            return False

        except Exception as e:
            self.logger.error("Error deleting file %s: %s", file_path, e)
            return False

    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            if self.validate_file_path(file_path):
                return os.path.getsize(file_path)
            else:
                self.logger.warning("Attempted to get size of invalid file path: %s", file_path)
                return 0
        except OSError:
            return 0

    def cleanup_old_files(self, pattern: str, keep_count: int) -> int:
        """Clean up old files, keeping only the most recent N"""
        try:
            files = self.list_export_files(pattern)

            if len(files) <= keep_count:
                return 0

            files_to_delete = files[keep_count:]
            deleted_count = 0

            for file_path, _, _ in files_to_delete:
                if self.delete_file_safe(file_path):
                    deleted_count += 1

            if deleted_count > 0:
                self.logger.info("Cleaned up %s old files", deleted_count)

            return deleted_count

        except Exception as e:
            self.logger.error("Error cleaning up old files: %s", e)
            return 0

    def validate_file_path(self, file_path: str) -> bool:
        """Validate file path for security"""
        try:
            # Check if path is empty or a special path that cannot be resolved
            if not file_path or file_path.startswith('special:'):
                self.logger.warning("Invalid file path detected (empty or special): %s", file_path)
                return False

            # Resolve the absolute path
            resolved_path = os.path.abspath(file_path)
            profile_path = os.path.abspath(self.get_profile_path())

            # Must be within profile directory or user-selected directory
            if not resolved_path.startswith(profile_path):
                # Allow user-selected paths outside profile (for custom exports)
                # but prevent system directory access
                dangerous_paths = ['/bin', '/boot', '/dev', '/etc', '/lib', '/proc', '/root', '/sbin', '/sys', '/usr', 'C:\\Windows', 'C:\\Program Files']
                for dangerous in dangerous_paths:
                    if resolved_path.startswith(os.path.abspath(dangerous)):
                        self.logger.warning("Access denied to dangerous path: %s", resolved_path)
                        return False

            return True

        except Exception as e:
            self.logger.error("Error validating file path: %s", e)
            return False


# Global storage manager instance
_storage_instance = None


def get_storage_manager():
    """Get global storage manager instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance