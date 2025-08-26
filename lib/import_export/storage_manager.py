#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Storage Manager
Handles file operations for import/export with atomic writes
"""

import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
from ..utils.logger import get_logger

import xbmcvfs
import xbmcaddon


class StorageManager:
    """Manages file storage for import/export operations"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._profile_path = None
    
    def get_profile_path(self) -> str:
        """Get addon profile directory path"""
        if self._profile_path:
            return self._profile_path
        
        try:
            addon = xbmcaddon.Addon()
            profile_path = addon.getAddonInfo('profile')
            
            # Ensure directory exists
            if not xbmcvfs.exists(profile_path):
                xbmcvfs.mkdirs(profile_path)
            
            self._profile_path = profile_path
            return self._profile_path
            
        except Exception as e:
            self.logger.error(f"Error getting profile path: {e}")
            # Emergency fallback
            fallback_path = os.path.join(os.getcwd(), "data")
            os.makedirs(fallback_path, exist_ok=True)
            return fallback_path
    
    def generate_filename(self, export_type: str, file_format: str = "json") -> str:
        """Generate timestamped filename for export"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"plugin.video.library.genie_{export_type}_{timestamp}.{file_format}"
    
    def write_file_atomic(self, file_path: str, content: str) -> bool:
        """Write file atomically using temp file + rename"""
        try:
            # Ensure parent directory exists
            parent_dir = os.path.dirname(file_path)
            os.makedirs(parent_dir, exist_ok=True)
            
            # Write to temporary file first
            temp_path = f"{file_path}.tmp"
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic rename
            shutil.move(temp_path, file_path)
            
            self.logger.info(f"File written atomically: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing file atomically: {e}")
            
            # Clean up temp file if it exists
            temp_path = f"{file_path}.tmp"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            return False
    
    def read_file_safe(self, file_path: str) -> Optional[str]:
        """Read file with error handling"""
        try:
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.logger.debug(f"File read successfully: {file_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def list_export_files(self, pattern: str = "*") -> List[Tuple[str, str, int]]:
        """List export files in profile directory"""
        try:
            profile_path = self.get_profile_path()
            files = []
            
            for file_path in Path(profile_path).glob(pattern):
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append((
                        str(file_path),
                        file_path.name,
                        int(stat.st_size)
                    ))
            
            # Sort by modification time, newest first
            files.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
            return files
            
        except Exception as e:
            self.logger.error(f"Error listing export files: {e}")
            return []
    
    def delete_file_safe(self, file_path: str) -> bool:
        """Delete file with error handling"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"File deleted: {file_path}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except:
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
                self.logger.info(f"Cleaned up {deleted_count} old files")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old files: {e}")
            return 0
    
    def validate_file_path(self, file_path: str) -> bool:
        """Validate file path for security"""
        try:
            # Check if path is within safe boundaries
            resolved_path = os.path.abspath(file_path)
            profile_path = os.path.abspath(self.get_profile_path())
            
            # Must be within profile directory or user-selected directory
            if not resolved_path.startswith(profile_path):
                # Allow user-selected paths outside profile (for custom exports)
                # but prevent system directory access
                dangerous_paths = ['/bin', '/boot', '/dev', '/etc', '/lib', '/proc', '/root', '/sbin', '/sys', '/usr']
                for dangerous in dangerous_paths:
                    if resolved_path.startswith(dangerous):
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating file path: {e}")
            return False


# Global storage manager instance
_storage_manager_instance = None


def get_storage_manager():
    """Get global storage manager instance"""
    global _storage_manager_instance
    if _storage_manager_instance is None:
        _storage_manager_instance = StorageManager()
    return _storage_manager_instance