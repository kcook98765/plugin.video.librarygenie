#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Background Service
Handles periodic tasks and library monitoring
"""

import time
from typing import Dict, Any

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

        # Service configuration with safe defaults
        self.interval = max(60, self.config.get_background_interval_seconds())  # Minimum 60s
        self.track_library_changes = self.config.get_bool("track_library_changes", False)  # Default off
        self.token_refresh_enabled = self.config.get_bool("background_token_refresh", True)

        # Error handling and backoff
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.base_backoff_seconds = 60
        self.max_backoff_seconds = 300  # 5 minutes

        self.logger.info(f"Background service starting (interval: {self.interval}s, library_tracking: {self.track_library_changes})")

        # Initialize library scanner (always needed for initial setup)
        self._library_scanner = None
        try:
            from lib.library.scanner import get_library_scanner
            self._library_scanner = get_library_scanner()
            self.logger.debug("Library scanner initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize library scanner: {e}")

        # Token refresh tracking
        self._last_token_check = 0
        self._token_check_interval = 300  # Check tokens every 5 minutes minimum

    def run(self):
        """Main service loop"""
        self.logger.info("Background service started")

        # Perform initial checks
        self._initial_setup()

        # Main loop using proper Monitor.waitForAbort
        while not self.monitor.abortRequested():
            try:
                cycle_start = time.time()

                # Determine current interval (with backoff if needed)
                current_interval = self._get_current_interval()

                # Token refresh check (throttled)
                if self.token_refresh_enabled:
                    self._check_and_refresh_token_throttled()

                # Library change detection (if enabled and cheap)
                if self.track_library_changes and self._library_scanner:
                    self._check_library_changes()

                # Reset failure count on successful cycle
                self.consecutive_failures = 0

                cycle_duration = time.time() - cycle_start
                self.logger.debug(f"Service cycle completed in {cycle_duration:.2f}s")

            except Exception as e:
                self.consecutive_failures += 1
                self.logger.error(f"Background service error (failure #{self.consecutive_failures}): {e}")

                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.logger.warning(f"Too many consecutive failures ({self.consecutive_failures}), applying backoff")

            # Wait for next cycle or abort using proper Monitor method
            if self.monitor.waitForAbort(current_interval):
                break

        self.logger.info("Background service stopped")

    def _get_current_interval(self) -> int:
        """Get current interval with exponential backoff on failures"""
        if self.consecutive_failures == 0:
            return self.interval

        # Apply exponential backoff
        backoff_multiplier = min(2 ** (self.consecutive_failures - 1), 8)  # Cap at 8x
        backoff_interval = min(
            self.base_backoff_seconds * backoff_multiplier,
            self.max_backoff_seconds
        )

        return max(self.interval, backoff_interval)

    def _initial_setup(self):
        """Perform initial setup tasks"""
        try:
            # Always check if library needs initial indexing on service start
            if self._library_scanner and not self._library_scanner.is_library_indexed():
                self.logger.info("Library not indexed, performing initial scan")
                result = self._library_scanner.perform_full_scan()

                if result.get("success"):
                    self.logger.info(f"Initial scan complete: {result.get('items_added', 0)} movies indexed")
                else:
                    self.logger.warning(f"Initial scan failed: {result.get('error', 'Unknown error')}")
            else:
                self.logger.debug("Library already indexed or scanner unavailable")

        except Exception as e:
            self.logger.error(f"Initial setup failed: {e}")

    def _check_and_refresh_token_throttled(self):
        """Check and refresh authentication token if needed (throttled)"""
        try:
            current_time = time.time()

            # Only check tokens every few minutes, not every cycle
            if current_time - self._last_token_check < self._token_check_interval:
                return

            self._last_token_check = current_time

            success = maybe_refresh()
            if success:
                self.logger.debug("Token refresh check completed successfully")
            # Don't log failures as errors - user may not be authorized yet

        except Exception as e:
            self.logger.error(f"Token refresh check failed: {e}")
            raise  # Re-raise to trigger backoff

    def _check_library_changes(self):
        """Check for library changes using delta scan (cheap operation)"""
        try:
            # Skip during playback to avoid interruption
            if xbmc.Player().isPlaying():
                return

            # Use delta scan which should be cheap
            result = self._library_scanner.perform_delta_scan()

            if result.get("success"):
                changes = result.get("items_added", 0) + result.get("items_removed", 0)
                if changes > 0:
                    self.logger.debug(f"Library changes detected: +{result.get('items_added', 0)} -{result.get('items_removed', 0)} movies")
            else:
                self.logger.warning(f"Library scan failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"Library change detection failed: {e}")
            raise  # Re-raise to trigger backoff


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