#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Background Service
Handles periodic tasks and library monitoring
"""

import time
from typing import Dict, Any
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcgui # Added for notifications

from lib.config import get_config
from lib.auth.refresh import maybe_refresh
from lib.utils.logger import get_logger
from lib.ui.localization import L


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

        # ✨ Gate: user setting to enable the hijack behavior
        self.info_hijack_enabled = self.config.get_bool("info_hijack_enabled", True)
        self._info_hijack = None
        if self.info_hijack_enabled:
            try:
                from lib.ui.info_hijack_manager import InfoHijackManager
                self._info_hijack = InfoHijackManager(logger=self.logger)
                self.logger.debug("InfoHijackManager initialized (enabled)")
            except Exception as e:
                self.logger.warning(f"Failed to init InfoHijackManager: {e}")
        else:
            self.logger.debug("Info hijack disabled by setting")

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

        # Initialize query manager for search history setup
        self._query_manager = None
        try:
            from lib.data.query_manager import get_query_manager
            self._query_manager = get_query_manager()
            self.logger.debug("Query manager initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize query manager: {e}")



        # Token refresh tracking
        self._last_token_check = 0
        self._token_check_interval = 300  # Check tokens every 5 minutes minimum

        # Scheduled tasks tracking
        self.last_scheduled_check = None


    def run(self):
        """Main service loop"""
        self.logger.info("Background service started")

        # Perform initial checks
        self._initial_setup()

        # Main loop using proper Monitor.waitForAbort
        while not self.monitor.abortRequested():
            # Initialize current_interval with a default value before try block
            current_interval = self.interval

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



                # Check and run any scheduled tasks
                self.check_scheduled_tasks()

                # Reset failure count on successful cycle
                self.consecutive_failures = 0

                cycle_duration = time.time() - cycle_start
                self.logger.debug(f"Service cycle completed in {cycle_duration:.2f}s")

            except Exception as e:
                self.consecutive_failures += 1
                self.logger.error(f"Background service error (failure #{self.consecutive_failures}): {e}")

                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.logger.warning(f"Too many consecutive failures ({self.consecutive_failures}), applying backoff")

            # Wait for next cycle, but poll quickly so Info hijack feels instant
            waited = 0.0
            step = 0.15  # 150 ms
            while waited < current_interval and not self.monitor.abortRequested():
                # ✨ run the hijack tick only when enabled/available
                if self._info_hijack is not None:
                    try:
                        self._info_hijack.tick()
                    except Exception as e:
                        self.logger.debug(f"InfoHijack tick error: {e}")

                # use waitForAbort to be responsive to shutdowns
                remaining = max(0.0, current_interval - waited)
                if self.monitor.waitForAbort(min(step, remaining)):
                    return
                waited += step

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
        """Perform one-time initial setup tasks"""
        try:
            # Check if this is the first run by looking for a setup marker
            if not self._is_addon_initialized():
                self.logger.info("First run detected - performing one-time addon initialization")

                # Mark addon as initialized first to prevent duplicate runs
                self._mark_addon_initialized()

                # Perform initial library scan
                if self._library_scanner:
                    self.logger.info("Performing one-time initial library scan")

                    # Show notification that initial scan is starting
                    try:
                        xbmcgui.Dialog().notification(
                            L(35002),  # "LibraryGenie"
                            "Initial library scan starting...",
                            xbmcgui.NOTIFICATION_INFO,
                            3000
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to show initial scan notification: {e}")

                    # Use background progress dialog for friendlier user experience
                    progress_dialog = None

                    # Progress callback function - background dialog style
                    def progress_callback(page_num, total_pages, items_processed):
                        nonlocal progress_dialog
                        try:
                            percentage = int((page_num / total_pages) * 100) if total_pages > 0 else 0

                            # Create dialog on first call
                            if progress_dialog is None:
                                progress_dialog = xbmcgui.DialogProgressBG()
                                progress_dialog.create(L(35002), "Starting library scan...")

                            # Update progress dialog
                            message = f"Scanning library: {items_processed} movies processed"
                            progress_dialog.update(percentage, message)

                        except Exception as e:
                            self.logger.warning(f"Progress callback error: {e}")

                    # Perform scan with progress callback
                    try:
                        result = self._library_scanner.perform_full_scan(progress_callback=progress_callback)

                        # Close progress dialog
                        if progress_dialog is not None:
                            progress_dialog.close()

                        if result.get("success"):
                            self.logger.info(f"Initial scan complete: {result.get('items_added', 0)} movies indexed")
                            # Show completion notification
                            try:
                                xbmcgui.Dialog().notification(
                                    L(35002),  # "LibraryGenie"
                                    f"Scan complete: {result.get('items_added', 0)} movies indexed",
                                    xbmcgui.NOTIFICATION_INFO,
                                    5000
                                )
                            except Exception as e:
                                self.logger.warning(f"Failed to show completion notification: {e}")
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            if "aborted" in error_msg.lower():
                                self.logger.info(f"Initial scan cancelled by user")
                                # Show cancellation notification
                                try:
                                    xbmcgui.Dialog().notification(
                                        L(35002),  # "LibraryGenie"
                                        "Library scan cancelled",
                                        xbmcgui.NOTIFICATION_WARNING,
                                        3000
                                    )
                                except Exception as e:
                                    self.logger.warning(f"Failed to show cancellation notification: {e}")
                            else:
                                self.logger.warning(f"Initial scan failed: {error_msg}")
                                # Show error notification
                                try:
                                    xbmcgui.Dialog().notification(
                                        L(35002),  # "LibraryGenie"
                                        "Library scan failed",
                                        xbmcgui.NOTIFICATION_ERROR,
                                        5000
                                    )
                                except Exception as e:
                                    self.logger.warning(f"Failed to show error notification: {e}")
                    except Exception as e:
                        # Close progress dialog on exception
                        if progress_dialog is not None:
                            progress_dialog.close()

                        self.logger.error(f"Initial scan failed with exception: {e}")
                        # Show error notification on exception during scan
                        try:
                            xbmcgui.Dialog().notification(
                                L(35002),  # "LibraryGenie"
                                "Library scan failed",
                                xbmcgui.NOTIFICATION_ERROR,
                                5000
                            )
                        except Exception as e:
                            self.logger.warning(f"Failed to show error notification: {e}")
                else:
                    self.logger.warning("Library scanner unavailable during first run")

                # Ensure search history folder exists
                if self._query_manager:
                    try:
                        search_folder_id = self._query_manager.get_or_create_search_history_folder()
                        if search_folder_id:
                            self.logger.info(f"Search history folder ready (ID: {search_folder_id})")
                        else:
                            self.logger.warning("Failed to create search history folder")
                    except Exception as e:
                        self.logger.error(f"Error setting up search history folder: {e}")
                else:
                    self.logger.warning("Query manager unavailable for search history setup")
            else:
                self.logger.debug("Addon already initialized - skipping one-time setup")
                
                # Even on subsequent runs, ensure search history folder exists
                if self._query_manager:
                    try:
                        search_folder_id = self._query_manager.get_or_create_search_history_folder()
                        if search_folder_id:
                            self.logger.debug(f"Search history folder confirmed (ID: {search_folder_id})")
                    except Exception as e:
                        self.logger.warning(f"Error confirming search history folder: {e}")

        except Exception as e:
            self.logger.error(f"Initial setup failed: {e}")

    def _is_addon_initialized(self):
        """Check if addon has been initialized before"""
        try:
            from lib.data.connection_manager import get_connection_manager
            conn_manager = get_connection_manager()

            # Check for initialization marker in kv_cache
            result = conn_manager.execute_single(
                "SELECT value FROM kv_cache WHERE key = 'addon_initialized'"
            )
            return result is not None and result['value'] == 'true'
        except Exception as e:
            self.logger.warning(f"Failed to check initialization status: {e}")
            return False

    def _mark_addon_initialized(self):
        """Mark addon as initialized to prevent duplicate initialization"""
        try:
            from lib.data.connection_manager import get_connection_manager
            conn_manager = get_connection_manager()

            with conn_manager.transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO kv_cache (key, value, updated_at) 
                    VALUES ('addon_initialized', 'true', datetime('now'))
                """)
            self.logger.debug("Marked addon as initialized")
        except Exception as e:
            self.logger.warning(f"Failed to mark addon as initialized: {e}")




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

            # Check if library scanner is available
            if self._library_scanner is None:
                self.logger.warning("Library scanner is not initialized")
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



    def check_scheduled_tasks(self):
        """Check and run any scheduled tasks"""
        try:
            current_time = datetime.now()

            # Only run scheduled tasks if enough time has passed
            if self.last_scheduled_check:
                time_since_last = (current_time - self.last_scheduled_check).total_seconds()
                if time_since_last < 300:  # 5 minutes minimum between scheduled task checks
                    return

            self.last_scheduled_check = current_time

            # Check for library changes if tracking is enabled
            if self.config.get_bool("track_library_changes", False):
                self._check_library_changes()

            # Check for scheduled backups
            self.check_scheduled_backups()

            # TODO: Add other scheduled tasks here (token refresh, etc.)

        except Exception as e:
            self.logger.error(f"Error in scheduled tasks: {e}")

    def check_scheduled_backups(self):
        """Check if scheduled backup should run"""
        try:
            from lib.import_export import get_timestamp_backup_manager

            backup_manager = get_timestamp_backup_manager()

            if backup_manager.should_run_backup():
                self.logger.info("Running scheduled backup")
                result = backup_manager.run_automatic_backup()

                if result["success"]:
                    self.logger.info(f"Scheduled backup completed: {result.get('filename')} at {result.get('storage_location')}")
                else:
                    self.logger.error(f"Scheduled backup failed: {result.get('error')}")

        except Exception as e:
            self.logger.error(f"Error checking scheduled backups: {e}")

# The `run` function was modified to include database initialization.
def run():
    """Main background service entry point"""
    logger = get_logger(__name__)

    try:
        # Force database initialization first
        try:
            from lib.data.migrations import initialize_database
            initialize_database()
            logger.info("Database initialization completed")
        except Exception as db_error:
            logger.error(f"Database initialization failed: {db_error}")
            # Continue anyway - some features might still work

        config = get_config()

        # Check if background service is enabled
        enabled = config.get_bool("background_task_enabled", True)
        if not enabled:
            logger.info("Background service disabled in settings")
            return

        interval = config.get_background_interval_seconds()
        track_library = config.get_bool("track_library_changes", True)

        logger.info(f"Background service starting (interval: {interval}s, library_tracking: {track_library})")

        # Initialize services
        service = BackgroundService() # Removed interval argument as it's handled in __init__
        service.run()

    except Exception as e:
        logger.error(f"Background service failed to start: {e}")
        # Don't raise - let Kodi continue


if __name__ == '__main__':
    run()