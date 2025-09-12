#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Storage Manager
Handles file system paths and storage locations using proper Kodi addon methods
"""

import os
import xbmcvfs
import xbmcaddon

from ..utils.kodi_log import get_kodi_logger


class StorageManager:
    """Manages file system paths and storage locations using Kodi addon methods"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.data.storage_manager')
        self._addon = xbmcaddon.Addon()

    def get_database_path(self):
        """Get the database file path using proper Kodi addon profile directory"""
        try:
            # Use Kodi's addon profile directory - this is the correct method
            profile_dir = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))

            # Ensure directory exists
            if not xbmcvfs.exists(profile_dir):
                success = xbmcvfs.mkdirs(profile_dir)
                if not success:
                    raise RuntimeError(f"Failed to create addon profile directory: {profile_dir}")

            db_path = os.path.join(profile_dir, 'librarygenie.db')
            self.logger.debug("Using Kodi addon profile database path: %s", db_path)
            return db_path

        except Exception as e:
            self.logger.error("Failed to get Kodi addon profile path: %s", e)
            raise RuntimeError(f"Cannot initialize database - Kodi addon profile path unavailable: {e}")

    def get_cache_dir(self):
        """Get cache directory path using proper Kodi addon profile"""
        try:
            profile_dir = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
            cache_dir = os.path.join(profile_dir, 'cache')

            if not xbmcvfs.exists(cache_dir):
                success = xbmcvfs.mkdirs(cache_dir)
                if not success:
                    raise RuntimeError(f"Failed to create cache directory: {cache_dir}")

            return cache_dir

        except Exception as e:
            self.logger.error("Failed to get cache directory: %s", e)
            raise RuntimeError(f"Cannot initialize cache directory: {e}")

    def get_temp_dir(self):
        """Get temporary directory path using proper Kodi addon profile"""
        try:
            profile_dir = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
            temp_dir = os.path.join(profile_dir, 'temp')

            if not xbmcvfs.exists(temp_dir):
                success = xbmcvfs.mkdirs(temp_dir)
                if not success:
                    raise RuntimeError(f"Failed to create temp directory: {temp_dir}")

            return temp_dir

        except Exception as e:
            self.logger.error("Failed to get temp directory: %s", e)
            raise RuntimeError(f"Cannot initialize temp directory: {e}")


# Global storage manager instance
_storage_instance = None


def get_storage_manager():
    """Get global storage manager instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance