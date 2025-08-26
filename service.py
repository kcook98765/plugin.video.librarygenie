#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Background Service
Handles background tasks and periodic operations
"""

import threading
import time
import xbmc
import xbmcaddon

from lib.config import get_config
from lib.utils.logger import get_logger


class BackgroundService:
    """Background service for Movie List Manager"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.monitor = xbmc.Monitor()
        self.running = False

    def start(self):
        """Start the background service"""
        self.logger.info("Movie List Manager background service starting...")
        self.running = True

        # Check if background task is enabled
        task_enabled = self.config.get("background_task_enabled", True)

        if not task_enabled:
            self.logger.info("Background task is disabled, service will remain idle")
            # Sleep quietly and respond to shutdown requests only
            while self.running and not self.monitor.abortRequested():
                if self.monitor.waitForAbort(30):  # Check every 30 seconds
                    break
            self.logger.info("Movie List Manager background service stopped (was idle)")
            return

        # Get safe interval from config (with clamping)
        interval = self.config.get_background_interval_seconds()
        self.logger.info(f"Background task enabled with {interval}s interval")

        while self.running and not self.monitor.abortRequested():
            try:
                # Perform background tasks
                self._background_tick()

                # Wait for next iteration or abort
                if self.monitor.waitForAbort(interval):
                    break

            except Exception as e:
                self.logger.error(f"Error in background service: {e}")
                # Wait before retrying on error (1 minute)
                if self.monitor.waitForAbort(60):
                    break

        self.logger.info("Movie List Manager background service stopped")

    def stop(self):
        """Stop the background service"""
        self.running = False

    def _background_tick(self):
        """Perform one iteration of background tasks"""
        self.logger.debug("Background service tick")

        # Initialize database if not done yet
        if not hasattr(self, '_db_initialized'):
            try:
                from lib.data import QueryManager
                query_manager = QueryManager()
                query_manager.initialize()
                self._db_initialized = True
                self.logger.info("Database initialized by background service")
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {e}")
                return

        # Initialize library scanner if not done yet
        if not hasattr(self, '_library_scanner'):
            try:
                from lib.library import LibraryScanner
                self._library_scanner = LibraryScanner()
                self.logger.debug("Library scanner initialized by background service")
            except Exception as e:
                self.logger.error(f"Failed to initialize library scanner: {e}")
                return

        # Check if this is first run and library needs indexing
        if not hasattr(self, '_initial_scan_done'):
            try:
                if not self._library_scanner.is_library_indexed():
                    self.logger.info("Library not indexed, performing initial full scan")
                    result = self._library_scanner.perform_full_scan()
                    
                    if result.get("success"):
                        self.logger.info(f"Initial scan complete: {result.get('items_added', 0)} movies indexed")
                    else:
                        self.logger.warning(f"Initial scan failed: {result.get('error', 'Unknown error')}")
                else:
                    self.logger.debug("Library already indexed, skipping initial scan")
                
                self._initial_scan_done = True
            except Exception as e:
                self.logger.error(f"Failed during initial scan check: {e}")
                return

        # Perform delta scan for library changes
        try:
            # Check if we should skip during playback to avoid interruption
            if xbmc.Player().isPlaying():
                self.logger.debug("Skipping library scan during playback")
                return
                
            result = self._library_scanner.perform_delta_scan()
            
            if result.get("success"):
                changes = result.get("items_added", 0) + result.get("items_removed", 0)
                if changes > 0:
                    self.logger.debug(f"Delta scan: +{result.get('items_added', 0)} -{result.get('items_removed', 0)} movies")
            else:
                self.logger.warning(f"Delta scan failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Failed during delta scan: {e}")

        # Scan favorites if enabled
        if self.config.get("favorites_integration_enabled", False):
            try:
                from lib.kodi.favorites_manager import get_favorites_manager
                
                favorites_manager = get_favorites_manager()
                result = favorites_manager.scan_favorites()
                
                if result.get("success") and result.get("scan_type") == "full":
                    self.logger.info(f"Favorites scan: {result.get('items_mapped', 0)} mapped")
            except Exception as e:
                self.logger.error(f"Error in background favorites scan: {e}")
        
        # Future tasks:
        # - Sync with external services (if enabled)
        # - Clean up old removed items
        # - Update metadata cache


def main():
    """Main service entry point"""
    logger = get_logger(__name__)

    try:
        service = BackgroundService()
        service.start()
    except Exception as e:
        logger.error(f"Failed to start background service: {e}")


if __name__ == "__main__":
    main()
