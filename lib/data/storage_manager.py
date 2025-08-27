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
from typing import Optional, Dict, Any, List

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
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Storage Manager
Handles file system paths and storage locations
"""

import os
try:
    import xbmcvfs
    import xbmcaddon
    KODI_AVAILABLE = True
except ImportError:
    KODI_AVAILABLE = False

from ..utils.logger import get_logger


class StorageManager:
    """Manages file system paths and storage locations"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._addon = None
        
        if KODI_AVAILABLE:
            try:
                self._addon = xbmcaddon.Addon()
            except Exception as e:
                self.logger.warning(f"Could not initialize Kodi addon: {e}")

    def get_database_path(self):
        """Get the database file path"""
        if KODI_AVAILABLE and self._addon:
            try:
                # Use Kodi's addon profile directory
                profile_dir = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
                # Ensure directory exists
                if not xbmcvfs.exists(profile_dir):
                    xbmcvfs.mkdirs(profile_dir)
                
                db_path = os.path.join(profile_dir, 'librarygenie.db')
                self.logger.debug(f"Database path: {db_path}")
                return db_path
            except Exception as e:
                self.logger.warning(f"Could not get Kodi profile path: {e}")
        
        # Fallback to current directory
        fallback_path = os.path.join(os.getcwd(), 'librarygenie.db')
        self.logger.debug(f"Using fallback database path: {fallback_path}")
        return fallback_path

    def get_cache_dir(self):
        """Get cache directory path"""
        if KODI_AVAILABLE and self._addon:
            try:
                profile_dir = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
                cache_dir = os.path.join(profile_dir, 'cache')
                if not xbmcvfs.exists(cache_dir):
                    xbmcvfs.mkdirs(cache_dir)
                return cache_dir
            except Exception as e:
                self.logger.warning(f"Could not get Kodi cache path: {e}")
        
        # Fallback
        cache_dir = os.path.join(os.getcwd(), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def get_temp_dir(self):
        """Get temporary directory path"""
        if KODI_AVAILABLE and self._addon:
            try:
                profile_dir = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
                temp_dir = os.path.join(profile_dir, 'temp')
                if not xbmcvfs.exists(temp_dir):
                    xbmcvfs.mkdirs(temp_dir)
                return temp_dir
            except Exception as e:
                self.logger.warning(f"Could not get Kodi temp path: {e}")
        
        # Fallback
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir


# Global storage manager instance
_storage_instance = None


def get_storage_manager():
    """Get global storage manager instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance
