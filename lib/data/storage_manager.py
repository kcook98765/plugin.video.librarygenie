#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Storage Location Manager
Manages database file location using Kodi's profile directory
"""

import os
from pathlib import Path
import xbmcvfs
import xbmcaddon

from ..utils.logger import get_logger


class StorageManager:
    """Manages database storage location using Kodi's profile directory"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._db_path = None
        
    def get_database_path(self):
        """Get the appropriate database file path for current environment"""
        if self._db_path is None:
            self._db_path = self._determine_db_path()
        
        return self._db_path
    
    def _determine_db_path(self):
        """Determine database path using Kodi's profile directory"""
        addon = xbmcaddon.Addon()
        profile_path = addon.getAddonInfo('profile')
        
        # Convert to filesystem path and ensure directory exists
        profile_dir = Path(xbmcvfs.translatePath(profile_path))
        profile_dir.mkdir(parents=True, exist_ok=True)
        db_path = profile_dir / "lists.db"
        self.logger.debug(f"Using Kodi profile database: {db_path}")
        return str(db_path)
    
    def get_data_directory(self):
        """Get the directory containing the database file"""
        db_path = Path(self.get_database_path())
        return str(db_path.parent)


# Global storage manager instance
_storage_instance = None


def get_storage_manager():
    """Get global storage manager instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance