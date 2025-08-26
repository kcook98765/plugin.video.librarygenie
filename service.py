#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie Background Service
Handles background tasks like library scanning and sync operations
"""

# All imports should be at module level but avoid network calls at import time
import time
import threading
from typing import Optional

import xbmc
import xbmcaddon

from lib.config import get_config
from lib.auth.refresh import maybe_refresh
from lib.utils.logger import get_logger


class BackgroundService:
    """Background service for token refresh and library monitoring"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.addon = xbmcaddon.Addon()
        self.monitor = xbmc.Monitor()

        # Service configuration
        self.interval = self.config.get_background_interval_seconds()
        self.track_library_changes = self.config.get_bool("track_library_changes", True)

        self.logger.info(f"Background service starting (interval: {self.interval}s)")

        # Initialize library scanner if needed
        self._library_scanner = None
        if self.track_library_changes:
            try:
                from lib.library.scanner import get_library_scanner
                self._library_scanner = get_library_scanner()
                self.logger.debug("Library scanner initialized for background monitoring")
            except Exception as e:
                self.logger.warning(f"Failed to initialize library scanner: {e}")

    def run(self):
        """Main service loop"""
        self.logger.info("Background service started")

        # Perform initial checks
        self._initial_setup()

        # Main loop
        while not self.monitor.abortRequested():
            try:
                # Token refresh check
                self._check_and_refresh_token()

                # Library change detection (if enabled)
                if self.track_library_changes and self._library_scanner:
                    self._check_library_changes()

            except Exception as e:
                self.logger.error(f"Background service error: {e}")

            # Wait for next cycle or abort
            if self.monitor.waitForAbort(self.interval):
                break

        self.logger.info("Background service stopped")

    def _initial_setup(self):
        """Perform initial setup tasks"""
        try:
            # Check if library needs initial indexing
            if self._library_scanner and not self._library_scanner.is_library_indexed():
                self.logger.info("Library not indexed, performing initial scan")
                result = self._library_scanner.perform_full_scan()

                if result.get("success"):
                    self.logger.info(f"Initial scan complete: {result.get('items_added', 0)} movies indexed")
                else:
                    self.logger.warning(f"Initial scan failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"Initial setup failed: {e}")

    def _check_and_refresh_token(self):
        """Check and refresh authentication token if needed"""
        try:
            success = maybe_refresh()
            if not success:
                # Token refresh failed or not authorized
                # This is normal if user hasn't authorized yet
                pass

        except Exception as e:
            self.logger.error(f"Token refresh check failed: {e}")

    def _check_library_changes(self):
        """Check for library changes using delta scan"""
        try:
            # Skip during playback to avoid interruption
            if xbmc.Player().isPlaying():
                return

            result = self._library_scanner.perform_delta_scan()

            if result.get("success"):
                changes = result.get("items_added", 0) + result.get("items_removed", 0)
                if changes > 0:
                    self.logger.debug(f"Library changes detected: +{result.get('items_added', 0)} -{result.get('items_removed', 0)} movies")
            else:
                self.logger.warning(f"Library scan failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"Library change detection failed: {e}")


def run():
    """Service entry point"""
    try:
        service = BackgroundService()
        service.run()
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Background service crashed: {e}")


if __name__ == '__main__':
    run()