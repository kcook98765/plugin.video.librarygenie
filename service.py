#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie Service - Kodi Background Service
Handles periodic tasks, cache management, and AI search synchronization
"""

import xbmc
import xbmcaddon
import xbmcgui
import time
import threading
from typing import Optional

from lib.utils.logger import get_logger
from lib.config.settings import SettingsManager
from lib.remote.ai_search_client import get_ai_search_client
from lib.library.scanner import LibraryScanner
from lib.data.storage_manager import get_storage_manager
from lib.data.migrations import initialize_database
from lib.ui.localization import L
from lib.ui.info_hijack_manager import InfoHijackManager # Import added

logger = get_logger(__name__)
addon = xbmcaddon.Addon()


class LibraryGenieService:
    """Background service for LibraryGenie addon"""

    def __init__(self):
        self.logger = logger
        self.settings = SettingsManager()
        self.ai_client = get_ai_search_client()
        self.storage_manager = get_storage_manager()
        self.monitor = xbmc.Monitor()
        self.sync_thread = None
        self.sync_stop_event = threading.Event()
        self.hijack_manager = InfoHijackManager(self.logger) # Hijack manager initialized
        
        # State tracking to reduce excessive logging
        self._last_ai_sync_state = None
        self._last_ai_sync_check_time = 0
        self._last_service_log_time = 0
        
        # TV episode sync state tracking - initialize to current setting value
        self._last_tv_sync_state = self.settings.get_sync_tv_episodes()
        self._last_tv_sync_check_time = 0
        
        self.logger.info("🚀 LibraryGenie service initialized with InfoHijack manager")

        # Debug: Check initial dialog state
        initial_dialog_id = xbmcgui.getCurrentWindowDialogId()
        initial_dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        self.logger.info("🔍 SERVICE INIT: Initial dialog state - ID: %s, VideoInfo active: %s", initial_dialog_id, initial_dialog_active)

    def _show_notification(self, message: str, icon: int = xbmcgui.NOTIFICATION_INFO, time_ms: int = 5000):
        """Show a Kodi notification"""
        try:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                message,
                icon,
                time_ms
            )
        except Exception as e:
            self.logger.error("Failed to show notification: %s", e)

    def _initialize_database(self):
        """Initialize database schema if needed"""
        try:
            self.logger.info("Checking database initialization...")
            initialize_database()
            self.logger.info("Database initialization completed")
        except Exception as e:
            self.logger.error("Database initialization failed: %s", e)
            self._show_notification(
                f"Database initialization failed: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR
            )

    def _check_and_perform_initial_scan(self):
        """Check if library has been scanned and perform initial scan if needed"""
        try:
            scanner = LibraryScanner()

            if not scanner.is_library_indexed():
                self.logger.info("Library not indexed, performing initial scan...")

                # Perform initial full scan with DialogBG for better UX
                result = scanner.perform_full_scan(use_dialog_bg=True)

                if result.get('success'):
                    items_added = result.get('items_added', 0)
                    self.logger.info("Initial library scan completed: %s movies indexed", items_added)
                    self._show_notification(
                        f"Library scan completed: {items_added} movies indexed",
                        time_ms=8000
                    )
                else:
                    error = result.get('error', 'Unknown error')
                    self.logger.error("Initial library scan failed: %s", error)
                    self._show_notification(
                        f"Library scan failed: {error[:40]}...",
                        xbmcgui.NOTIFICATION_ERROR,
                        time_ms=8000
                    )
            else:
                self.logger.info("Library already indexed, skipping initial scan")

        except Exception as e:
            self.logger.error("Error during initial scan check: %s", e)
            self._show_notification(
                f"Scan check failed: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR
            )

    def start(self):
        """Start the background service"""
        self.logger.info("LibraryGenie background service starting...")

        try:
            # Initialize database if needed
            self._initialize_database()

            # Check if library needs initial scan
            self._check_and_perform_initial_scan()

            # Start AI search sync if enabled  
            self.logger.info("🔍 Checking AI Search activation status at startup...")
            ai_activated = self.settings.get_ai_search_activated()
            self.logger.info("🔍 AI Search activated setting: %s", ai_activated)
            
            if self._should_start_ai_sync():
                self.logger.info("✅ AI Search sync conditions met - starting sync thread")
                self._start_ai_sync_thread()
            else:
                self.logger.info("❌ AI Search sync conditions not met - sync disabled")

            # Initialize TV episode sync state at startup (without triggering sync)
            self.logger.info("📺 Initializing TV episode sync state at startup...")
            self._last_tv_sync_state = self.settings.get_sync_tv_episodes()
            self.logger.info("📺 Initial TV episode sync state: %s", self._last_tv_sync_state)

            # Main service loop
            self.run() # Changed to call run() which contains the hijack manager loop

            # Cleanup
            self._stop_ai_sync_thread()
            self.logger.info("LibraryGenie background service stopped")

        except Exception as e:
            self.logger.error("Service error: %s", e)

    def run(self):
        """Main service loop - optimized for minimal resource usage"""
        self.logger.info("🔥 LibraryGenie service starting main loop...")
        tick_count = 0
        last_dialog_active = False
        last_armed_state = None
        hijack_mode = False
        last_ai_sync_check = 0

        # Reduced logging frequency
        log_interval = 300  # Log every 30 seconds in normal mode, 10 seconds in hijack mode
        ai_sync_check_interval = 30  # Check AI sync activation every 30 seconds

        while not self.monitor.abortRequested():
            try:
                tick_count += 1

                # Check if we need hijack functionality
                dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
                armed_state = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
                
                # Also check if we're in extended monitoring period for XSP auto-navigation
                container_path = xbmc.getInfoLabel('Container.FolderPath')
                in_extended_monitoring = (
                    hasattr(self.hijack_manager, '_hijack_monitoring_expires') and 
                    time.time() < self.hijack_manager._hijack_monitoring_expires
                )

                # Determine if we're in hijack mode (need frequent 100ms ticks)
                needs_hijack = dialog_active or armed_state == '1' or in_extended_monitoring

                # State change detection for mode switching
                if needs_hijack != hijack_mode:
                    hijack_mode = needs_hijack
                    if hijack_mode:
                        if in_extended_monitoring:
                            self.logger.info("🎯 Entering hijack mode - extended monitoring for XSP auto-navigation (120s)")
                        else:
                            self.logger.info("🎯 Entering hijack mode - frequent ticking enabled")
                        log_interval = 600  # 60 seconds in hijack mode (reduced from 10 seconds)
                    else:
                        self.logger.info("😴 Exiting hijack mode - entering idle mode")
                        log_interval = 1800  # 180 seconds (3 minutes) in normal mode (reduced from 30 seconds)

                # Conditional debug logging - only when state changes or at very long intervals
                # Also only log if something interesting is happening (not just idle ticks)
                state_changed = (dialog_active != last_dialog_active or armed_state != last_armed_state)
                interval_reached = (tick_count % log_interval == 0)
                something_interesting = dialog_active or armed_state == '1' or in_extended_monitoring
                
                should_log = (
                    state_changed or  # Always log state changes
                    (interval_reached and something_interesting)  # Only log intervals when something is happening
                )

                if should_log and self.settings.get_debug_logging():
                    dialog_id = xbmcgui.getCurrentWindowDialogId()
                    container_path = xbmc.getInfoLabel('Container.FolderPath')
                    mode_str = "HIJACK" if hijack_mode else "IDLE"
                    
                    if state_changed:
                        self.logger.info("🔍 SERVICE STATE CHANGE [%s]: dialog_active=%s, dialog_id=%s, armed=%s", mode_str, dialog_active, dialog_id, armed_state)
                    else:
                        # Only log periodic ticks when in hijack mode and something is active
                        self.logger.info("🔍 SERVICE [%s] PERIODIC CHECK %s: dialog_active=%s, armed=%s", mode_str, tick_count, dialog_active, armed_state)

                # Store state for next comparison
                last_dialog_active = dialog_active
                last_armed_state = armed_state

                # Check for AI sync activation changes periodically
                if tick_count % ai_sync_check_interval == 0:
                    self._check_ai_sync_activation(tick_count)
                    # Also check TV episode sync activation
                    self._check_tv_episode_sync_activation(tick_count)

                # Run hijack manager tick only when needed
                if hijack_mode:
                    self.hijack_manager.tick()
                    
                    # Check if we can safely exit hijack mode AFTER hijack manager has processed
                    # Stay in hijack mode if user is still on LibraryGenie XSP pages
                    container_path = xbmc.getInfoLabel('Container.FolderPath')
                    on_lg_hijack_xsp = container_path and (
                        'lg_hijack_temp.xsp' in container_path or
                        'lg_hijack_debug.xsp' in container_path
                    )
                    
                    # Only allow hijack mode exit if NOT on our XSP pages
                    if on_lg_hijack_xsp:
                        # Force hijack mode to stay active for next iteration
                        needs_hijack = True
                        if not dialog_active and dialog_active != last_dialog_active:  # Log when dialog closes but still on XSP
                            self.logger.info(f"🔄 HIJACK: Dialog closed but staying in hijack mode - user on LibraryGenie XSP")
                    # Normal hijack mode detection will handle other cases

                # Adaptive sleep timing based on mode
                if hijack_mode:
                    # Fast ticking when hijack is needed (100ms)
                    if self.monitor.waitForAbort(0.1):
                        break
                else:
                    # Slow ticking when idle to save resources (1 second)
                    if self.monitor.waitForAbort(1.0):
                        break

            except Exception as e:
                self.logger.error("💥 SERVICE ERROR: %s", e)
                import traceback
                self.logger.error("SERVICE TRACEBACK: %s", traceback.format_exc())
                # Error recovery with longer wait
                if self.monitor.waitForAbort(2.0):
                    break

        self.logger.info("🛑 LibraryGenie service stopped")

    def _check_ai_sync_activation(self, tick_count=None):
        """Check if AI sync should be started (for dynamic activation detection)"""
        try:
            current_time = time.time()
            # Only log periodic check every 5 minutes instead of 30 seconds
            should_log_periodic = (tick_count is not None and 
                                 (current_time - self._last_ai_sync_check_time) > 300)  # 5 minutes
            
            if should_log_periodic:
                self.logger.info("🔄 Periodic AI sync check (tick %s)", tick_count)
                self._last_ai_sync_check_time = current_time
                
            # Check if AI sync should start and isn't already running
            if self._should_start_ai_sync(force_log=should_log_periodic):
                if not (self.sync_thread and self.sync_thread.is_alive()):
                    self.logger.info("🚀 AI Search activation detected - starting sync thread dynamically")
                    self._start_ai_sync_thread()
            else:
                # Stop sync thread if AI Search was deactivated
                if self.sync_thread and self.sync_thread.is_alive():
                    self.logger.info("🛑 AI Search deactivation detected - stopping sync thread")
                    self._stop_ai_sync_thread()
        except Exception as e:
            self.logger.error("Error checking AI sync activation: %s", e)

    def _should_start_ai_sync(self, force_log=False) -> bool:
        """Check if AI search sync should be started"""
        # Verify that AI search is properly configured with valid auth
        if not self.settings.get_ai_search_activated():
            if force_log:
                self.logger.info("🔍 AI Search not activated in settings")
            return False

        # Test if AI client is properly configured and authorized
        server_url = self.settings.get_remote_server_url()
        api_key = self.settings.get_ai_search_api_key()
        
        # Check what is_authorized() returns (checks database)
        from lib.auth.state import is_authorized, get_api_key
        auth_status = is_authorized()
        db_api_key = get_api_key()
        
        # Create current state summary
        current_state = {
            'server_url_exists': bool(server_url),
            'settings_api_key_exists': bool(api_key),
            'auth_status': auth_status,
            'db_api_key_exists': bool(db_api_key),
            'client_configured': self.ai_client.is_configured()
        }
        
        # Only log detailed info if state changed or forced
        if force_log or current_state != self._last_ai_sync_state:
            self.logger.info("🔍 Server URL: '%s' (exists: %s)", server_url, current_state['server_url_exists'])
            self.logger.info("🔍 API Key (from settings): %s (length: %s)", '[PRESENT]' if api_key else '[MISSING]', len(api_key) if api_key else 0)
            self.logger.info("🔍 is_authorized() result: %s", auth_status)
            self.logger.info("🔍 API Key (from database): %s (length: %s)", '[PRESENT]' if db_api_key else '[MISSING]', len(db_api_key) if db_api_key else 0)
            
            if not current_state['client_configured']:
                self.logger.info("🔍 AI client not configured, skipping sync")
            else:
                self.logger.info("✅ AI Search configuration verified")
            
            self._last_ai_sync_state = current_state
        
        if not current_state['client_configured']:
            return False

        # Configuration looks good - sync worker will test connection when it runs
        return True

    def _start_ai_sync_thread(self):
        """Start the AI search sync background thread"""
        if self.sync_thread and self.sync_thread.is_alive():
            return

        self.logger.info("Starting AI search sync thread")
        self.sync_stop_event.clear()
        self.sync_thread = threading.Thread(target=self._ai_sync_worker, daemon=True)
        self.sync_thread.start()

    def _stop_ai_sync_thread(self):
        """Stop the AI search sync background thread"""
        if self.sync_thread and self.sync_thread.is_alive():
            self.logger.info("Stopping AI search sync thread")
            self.sync_stop_event.set()
            self.sync_thread.join(timeout=10)

    def _ai_sync_worker(self):
        """Background worker for AI search synchronization"""
        self.logger.info("AI search sync worker started")

        try:
            # Periodic sync based on settings
            sync_hours = self.settings.get_ai_search_sync_interval()
            sync_interval = min(sync_hours * 3600, 86400)  # Cap at 24 hours (86400 seconds) to avoid timeout errors

            while not self.sync_stop_event.is_set():
                if self.sync_stop_event.wait(sync_interval):
                    break  # Stop event was set

                # Perform sync if still enabled
                if self._should_start_ai_sync():
                    self._perform_ai_sync()
                else:
                    self.logger.info("AI sync disabled, stopping worker")
                    break

        except Exception as e:
            self.logger.error("AI sync worker error: %s", e)
        finally:
            self.logger.info("AI search sync worker stopped")
            
    def _check_tv_episode_sync_activation(self, tick_count=None):
        """Check if TV episode sync should be triggered (for dynamic activation detection)"""
        try:
            current_time = time.time()
            tv_sync_enabled = self.settings.get_sync_tv_episodes()
            
            # Only log periodic check every 5 minutes instead of 30 seconds
            should_log_periodic = (tick_count is not None and 
                                 (current_time - self._last_tv_sync_check_time) > 300)  # 5 minutes
            
            if should_log_periodic:
                self.logger.info("🔄 Periodic TV episode sync check (tick %s)", tick_count)
                self._last_tv_sync_check_time = current_time
                
            # Check for state change from False to True (newly enabled)
            if tv_sync_enabled and not self._last_tv_sync_state:
                self.logger.info("📺 TV episode sync was just enabled - triggering immediate sync")
                self._trigger_tv_episode_sync()
                
            # Update last known state
            self._last_tv_sync_state = tv_sync_enabled
            
        except Exception as e:
            self.logger.error("Error checking TV episode sync activation: %s", e)
            
    def _trigger_tv_episode_sync(self):
        """Trigger TV episode sync when the setting is enabled"""
        try:
            from lib.config.tv_sync_helper import on_tv_episode_sync_enabled
            
            self.logger.info("📺 Triggering TV episode sync...")
            success = on_tv_episode_sync_enabled()
            
            if success:
                self.logger.info("📺 TV episode sync completed successfully")
                self._show_notification(
                    "TV episode sync completed - episodes are now available for list building",
                    time_ms=8000
                )
            else:
                self.logger.warning("📺 TV episode sync completed with issues")
                self._show_notification(
                    "TV episode sync completed with issues - check logs for details",
                    xbmcgui.NOTIFICATION_WARNING,
                    time_ms=8000
                )
                
        except Exception as e:
            self.logger.error("Error triggering TV episode sync: %s", e)
            self._show_notification(
                f"TV episode sync failed: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR,
                time_ms=8000
            )

    def _perform_ai_sync(self):
        """Perform AI search synchronization"""
        self.logger.info("Starting AI search synchronization")

        # Show start notification
        self._show_notification(L(34103))  # "Sync in progress..."

        try:
            # Test connection first
            connection_test = self.ai_client.test_connection()
            if not connection_test.get('success'):
                error_msg = connection_test.get('error', 'Unknown error')
                self.logger.warning("AI search connection failed: %s", error_msg)
                self._show_notification(f"{L(34105)}: {error_msg}", xbmcgui.NOTIFICATION_ERROR)  # "Sync failed: ..."
                return

            # Get current library version for delta sync (optional - endpoint may not exist)
            server_version = self.ai_client.get_library_version()
            if not server_version:
                self.logger.info("Server library version not available (proceeding with full sync)")

            # Scan library for movies with IMDb IDs
            scanner = LibraryScanner()
            movies_with_imdb = []

            self.logger.info("Scanning local library for movies with IMDb IDs...")

            # Get all movies from Kodi library using existing method
            from lib.data.connection_manager import get_connection_manager
            conn_manager = get_connection_manager()
            
            movies_result = conn_manager.execute_query("SELECT imdbnumber, title, year FROM media_items WHERE imdbnumber IS NOT NULL AND imdbnumber != ''")
            movies = [{"imdbnumber": row["imdbnumber"], "title": row["title"], "year": row["year"]} for row in movies_result]
            for movie in movies:
                imdb_id = movie.get('imdbnumber', '').strip()
                if imdb_id and imdb_id.startswith('tt'):
                    movies_with_imdb.append({
                        'imdb_id': imdb_id,
                        'title': movie.get('title', ''),
                        'year': movie.get('year', 0)
                    })

            self.logger.info("Found %s movies with IMDb IDs", len(movies_with_imdb))

            if not movies_with_imdb:
                self.logger.info("No movies with IMDb IDs found, skipping sync")
                self._show_notification(L(30016), xbmcgui.NOTIFICATION_WARNING)  # "No results found" (reusing existing string)
                return

            # Sync in batches with rate limiting
            batch_size = 500  # Conservative batch size
            total_batches = (len(movies_with_imdb) + batch_size - 1) // batch_size

            for i in range(0, len(movies_with_imdb), batch_size):
                if self.sync_stop_event.is_set():
                    self.logger.info("Sync cancelled by stop event")
                    return

                batch = movies_with_imdb[i:i + batch_size]
                batch_num = (i // batch_size) + 1

                self.logger.info("Syncing batch %s/%s (%s movies)", batch_num, total_batches, len(batch))

                result = self.ai_client.sync_media_batch(batch, batch_size)

                if result and result.get('success'):
                    results = result.get('results', {})
                    self.logger.info(
                        f"Batch {batch_num} sync completed: "
                        f"{results.get('added', 0)} added, "
                        f"{results.get('already_present', 0)} existing, "
                        f"{results.get('invalid', 0)} invalid"
                    )

                    # Show progress notification for significant batches
                    if total_batches > 1:
                        self._show_notification(
                            f"{L(34401)} {batch_num}/{total_batches}",  # "Processing... X/Y"
                            time_ms=3000
                        )
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No response'
                    self.logger.error("Batch %s sync failed: %s", batch_num, error_msg)
                    self._show_notification(
                        f"{L(34105)}: {error_msg}",  # "Sync failed: ..."
                        xbmcgui.NOTIFICATION_ERROR
                    )

                # Rate limiting: 1 second wait between batches
                if batch_num < total_batches and not self.sync_stop_event.is_set():
                    self.logger.debug(f"Waiting 1 second before next batch...")
                    self.sync_stop_event.wait(1)

            self.logger.info("AI search synchronization completed")

            # Show completion notification with summary
            self._show_notification(
                f"{L(34104)} - {len(movies_with_imdb)} movies",  # "Sync completed successfully - X movies"
                time_ms=8000
            )

        except Exception as e:
            self.logger.error("AI sync failed: %s", e)
            self._show_notification(
                f"{L(34105)}: {str(e)}",  # "Sync failed: ..."
                xbmcgui.NOTIFICATION_ERROR,
                time_ms=8000
            )


if __name__ == '__main__':
    # Entry point for Kodi service
    service = LibraryGenieService()
    service.start()