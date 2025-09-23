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

from lib.utils.kodi_log import log, log_info, log_error, log_warning
from lib.config.settings import SettingsManager
from lib.config.config_manager import get_config
from lib.remote.ai_search_client import get_ai_search_client
from lib.library.scanner import LibraryScanner
from lib.data.storage_manager import get_storage_manager
from lib.data.migrations import initialize_database
from lib.ui.localization import L
from lib.ui.info_hijack_manager import InfoHijackManager # Import added

addon = xbmcaddon.Addon()


class LibraryGenieMonitor(xbmc.Monitor):
    """Custom monitor that handles settings changes"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = get_config()
    
    def onSettingsChanged(self):
        """Called when addon settings are changed"""
        try:
            log_info("Settings changed - reloading configuration cache")
            # Brief delay to ensure settings file is fully written by Kodi
            xbmc.sleep(200)
            self.config_manager.reload()
        except Exception as e:
            log_error(f"Failed to reload settings cache: {e}")


class LibraryGenieService:
    """Background service for LibraryGenie addon"""

    def __init__(self):
        self.settings = SettingsManager()
        self.ai_client = get_ai_search_client()
        self.storage_manager = get_storage_manager()
        self.monitor = LibraryGenieMonitor()
        self.sync_thread = None
        self.sync_stop_event = threading.Event()
        self.hijack_manager = InfoHijackManager() # Hijack manager initialized
        
        # State tracking to reduce excessive logging
        self._last_ai_sync_state = None
        self._last_ai_sync_check_time = 0
        self._last_service_log_time = 0
        
        # Library sync state tracking
        self._last_library_sync_time = 0
        self._library_sync_in_progress = False
        self._service_start_time = time.time()
        
        
        log_info("🚀 LibraryGenie service initialized with InfoHijack manager")

        # Debug: Check initial dialog state
        initial_dialog_id = xbmcgui.getCurrentWindowDialogId()
        initial_dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        log(f"SERVICE INIT: Initial dialog state - ID: {initial_dialog_id}, VideoInfo active: {initial_dialog_active}")

    def _show_notification(self, message: str, icon: str = xbmcgui.NOTIFICATION_INFO, time_ms: int = 5000):
        """Show a Kodi notification"""
        try:
            xbmcgui.Dialog().notification(
                heading="LibraryGenie",
                message=message,
                icon=icon,
                time=time_ms
            )
        except Exception as e:
            log_error(f"Failed to show notification: {e}")

    def _ensure_profile_directory_ready(self, max_wait_seconds=10):
        """Ensure addon profile directory is ready before database initialization"""
        import xbmcvfs
        import xbmcaddon
        
        profile_dir = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        wait_interval = 0.5  # 500ms between attempts
        max_attempts = int(max_wait_seconds / wait_interval)
        
        for attempt in range(max_attempts):
            if xbmcvfs.exists(profile_dir) or xbmcvfs.mkdirs(profile_dir):
                if attempt > 0:  # Only log if we had to wait
                    log_info(f"Profile directory ready after {attempt * wait_interval:.1f}s")
                return True
                
            if self.monitor.abortRequested():
                log_warning("Kodi shutdown requested during profile directory wait")
                return False
                
            xbmc.sleep(int(wait_interval * 1000))  # Convert to milliseconds
        
        log_error(f"Profile directory not ready after {max_wait_seconds}s: {profile_dir}")
        return False

    def _initialize_database(self):
        """Initialize database schema and handle critical setup like Favorites"""
        try:
            log_info("Service: Initializing database with metadata caching...")
            
            # Perform the expensive database initialization
            initialize_database()
            
            # Handle Favorites list creation if needed (moved from plugin startup)
            self._ensure_favorites_list()
            
            # Calculate and cache database optimization parameters for plugin reuse
            self._cache_database_metadata()
            
            log_info("Service: Database ready with cached optimization parameters")
        except Exception as e:
            log_error(f"Service database initialization failed: {e}")
            # Don't set cache on failure - plugin will use fallback
            self._show_notification(
                f"Database initialization failed: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR
            )

    def _ensure_favorites_list(self):
        """Ensure Kodi Favorites list exists if favorites integration is enabled"""
        try:
            # Read directly from Kodi settings to bypass inter-process caching issues
            import xbmcaddon
            fresh_addon = xbmcaddon.Addon()
            
            try:
                favorites_enabled = fresh_addon.getSettingBool('favorites_integration_enabled')
            except Exception:
                favorites_enabled = False
                
            if not favorites_enabled:
                log("Service: Favorites integration disabled - skipping list check")
                return
                
            log("Service: Ensuring Kodi Favorites list exists")
            
            # Use singleton connection manager for database access  
            from lib.data import get_connection_manager
            connection_manager = get_connection_manager()
            with connection_manager.transaction() as conn:
                # Check if Kodi Favorites list exists
                kodi_list = conn.execute("""
                    SELECT id FROM lists WHERE name = 'Kodi Favorites'
                """).fetchone()
                
                if not kodi_list:
                    log_info("Service: Creating 'Kodi Favorites' list")
                    try:
                        from lib.config.favorites_helper import on_favorites_integration_enabled
                        on_favorites_integration_enabled()
                        log_info("Service: Successfully ensured 'Kodi Favorites' list exists")
                    except Exception as e:
                        log_error(f"Service: Failed to create 'Kodi Favorites' list: {e}")
                else:
                    log(f"Service: 'Kodi Favorites' list already exists with ID {kodi_list['id']}")
                    
        except Exception as e:
            log_error(f"Service: Error ensuring Favorites list: {e}")
            # Don't fail initialization for this

    def _cache_database_metadata(self):
        """Calculate database optimization metadata with schema validation"""
        try:
            import os
            import json
            
            db_path = self.storage_manager.get_database_path()
            
            # Get current schema version for validation
            try:
                from lib.data.migrations import TARGET_SCHEMA_VERSION
            except ImportError:
                TARGET_SCHEMA_VERSION = 0  # Fallback if import fails
                
            try:
                from lib.data import get_connection_manager
                connection_manager = get_connection_manager()
                with connection_manager.transaction() as conn:
                    schema_version_result = conn.execute(
                        "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    current_schema_version = schema_version_result['version'] if schema_version_result else 0
            except Exception as e:
                log_error(f"Could not determine schema version: {e}")
                current_schema_version = 0
            
            # Calculate optimization parameters (same logic as ConnectionManager)
            metadata = {
                'db_path': db_path,
                'service_initialized': True,
                'schema_version': current_schema_version,
                'target_schema_version': TARGET_SCHEMA_VERSION
            }
            
            if os.path.exists(db_path):
                db_size_bytes = os.path.getsize(db_path)
                db_size_mb = db_size_bytes / (1024 * 1024)
                
                # Same mmap calculation logic from ConnectionManager
                if db_size_mb < 16:
                    mmap_size = 33554432  # 32MB minimum
                    cache_pages = 500     # 2MB cache
                elif db_size_mb < 64:
                    mmap_size = int(db_size_bytes * 2)
                    cache_pages = min(1500, int(db_size_mb * 75))
                else:
                    mmap_size = min(int(db_size_bytes * 1.5), 134217728)
                    cache_pages = 2000
                    
                metadata.update({
                    'mmap_size': mmap_size,
                    'cache_pages': cache_pages,
                    'db_size_mb': db_size_mb
                })
            else:
                # New database defaults
                metadata.update({
                    'mmap_size': 33554432,  # 32MB
                    'cache_pages': 500      # 2MB cache
                })
            
            # Cache in Window property for plugin access
            window = xbmcgui.Window(10000)
            window.setProperty('librarygenie.db.optimized', json.dumps(metadata))
            
            log_info(f"Service: Cached DB metadata - {metadata.get('db_size_mb', 0):.1f}MB, "
                    f"mmap={metadata['mmap_size']//1048576}MB, "
                    f"cache={metadata['cache_pages']} pages")
            
        except Exception as e:
            log_error(f"Failed to cache database metadata: {e}")

    def _invalidate_and_refresh_db_cache(self):
        """Invalidate database cache and recalculate after initial scan"""
        try:
            log_info("Invalidating database cache after initial scan - recalculating optimization parameters")
            
            # Clear existing cache
            window = xbmcgui.Window(10000)
            window.clearProperty('librarygenie.db.optimized')
            
            # Recalculate with new database size
            self._cache_database_metadata()
            
            log_info("Database cache refreshed with new optimization parameters")
            
        except Exception as e:
            log_error(f"Failed to refresh database cache: {e}")

    def _check_cache_refresh_request(self):
        """Check if database cache refresh has been requested"""
        try:
            window = xbmcgui.Window(10000)
            refresh_needed = window.getProperty('librarygenie.db.refresh_needed')
            
            if refresh_needed == 'true':
                log_info("Database cache refresh requested - recalculating optimization parameters")
                
                # Clear the refresh request flag
                window.clearProperty('librarygenie.db.refresh_needed')
                
                # Refresh the cache
                self._invalidate_and_refresh_db_cache()
                
        except Exception as e:
            log_error(f"Error checking cache refresh request: {e}")

    def _check_and_perform_initial_scan(self):
        """Check if library has been scanned and perform initial scan if needed"""
        try:
            # Check if first-run setup has been completed
            if not self.settings.get_first_run_completed():
                log_info("First run not completed - skipping automatic scan until user configures sync options")
                return
                
            scanner = LibraryScanner()

            if not scanner.is_library_indexed():
                log_info("Library not indexed, performing initial scan...")

                # Use SyncController for proper sync orchestration
                from lib.library.sync_controller import SyncController
                sync_controller = SyncController()
                
                success, message = sync_controller.perform_manual_sync()
                
                if success:
                    log_info(f"Initial library sync completed: {message}")
                    self._show_notification(
                        f"Library sync completed: {message}",
                        time_ms=8000
                    )
                else:
                    log_error(f"Initial library sync failed: {message}")
                    self._show_notification(
                        f"Library sync failed: {message[:40]}...",
                        xbmcgui.NOTIFICATION_ERROR,
                        time_ms=8000
                    )
            else:
                log_info("Library already indexed, skipping initial scan")

        except Exception as e:
            log_error(f"Error during initial scan check: {e}")
            self._show_notification(
                f"Scan check failed: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR
            )

    def start(self):
        """Start the background service"""
        log_info("LibraryGenie background service starting...")

        try:
            # Wait for addon profile directory to be ready (fixes zip installation timing)
            if not self._ensure_profile_directory_ready():
                log_error("Service startup aborted - profile directory not ready")
                return
            
            # Initialize database if needed
            self._initialize_database()

            # Check if library needs initial scan
            self._check_and_perform_initial_scan()

            # Start AI search sync if enabled  
            log("Checking AI Search activation status at startup...")
            # Read directly from Kodi settings to bypass caching
            import xbmcaddon
            fresh_addon = xbmcaddon.Addon()
            try:
                ai_activated = fresh_addon.getSettingBool('ai_search_activated')
            except Exception:
                ai_activated = False
            log(f"AI Search activated setting: {ai_activated}")
            
            if self._should_start_ai_sync():
                log_info("✅ AI Search sync conditions met - starting sync thread")
                self._start_ai_sync_thread()
            else:
                log_info("❌ AI Search sync conditions not met - sync disabled")


            # Main service loop
            self.run() # Changed to call run() which contains the hijack manager loop

            # Cleanup
            self._stop_ai_sync_thread()
            log_info("LibraryGenie background service stopped")

        except Exception as e:
            log_error(f"Service error: {e}")

    def run(self):
        """Main service loop - optimized for minimal resource usage"""
        log_info("🔥 LibraryGenie service starting main loop...")
        tick_count = 0
        last_dialog_active = False
        last_armed_state = None
        last_container_path = None
        hijack_mode = False
        last_ai_sync_check = 0

        # Reduced logging frequency
        log_interval = 300  # Log every 30 seconds in normal mode, 10 seconds in hijack mode
        ai_sync_check_interval = 30  # Check AI sync activation every 30 seconds

        while not self.monitor.abortRequested():
            try:
                tick_count += 1

                # Cache Kodi API queries within tick cycle to reduce redundant calls
                dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
                armed_state = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
                
                # Only query container path when dialog state changes or when forced
                state_changed = (dialog_active != last_dialog_active or armed_state != last_armed_state)
                if state_changed or last_container_path is None:
                    container_path = xbmc.getInfoLabel('Container.FolderPath')
                else:
                    container_path = last_container_path  # Reuse cached value
                
                # Also check if we're in extended monitoring period for XSP auto-navigation
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
                            log("Entering hijack mode - extended monitoring for XSP auto-navigation (120s)")
                        else:
                            log("Entering hijack mode - frequent ticking enabled")
                        log_interval = 600  # 60 seconds in hijack mode (reduced from 10 seconds)
                    else:
                        log("Exiting hijack mode - entering idle mode")
                        log_interval = 1800  # 180 seconds (3 minutes) in normal mode (reduced from 30 seconds)

                # Conditional debug logging - only when state changes or at very long intervals
                # Also only log if something interesting is happening (not just idle ticks)
                interval_reached = (tick_count % log_interval == 0)
                something_interesting = dialog_active or armed_state == '1' or in_extended_monitoring
                
                should_log = (
                    state_changed or  # Always log state changes
                    (interval_reached and something_interesting)  # Only log intervals when something is happening
                )

                if should_log:  # Using direct Kodi logging - no custom debug check needed
                    dialog_id = xbmcgui.getCurrentWindowDialogId()
                    # Reuse cached container_path instead of querying again
                    mode_str = "HIJACK" if hijack_mode else "IDLE"
                    
                    if state_changed:
                        log(f"SERVICE STATE CHANGE [{mode_str}]: dialog_active={dialog_active}, dialog_id={dialog_id}, armed={armed_state}")
                    else:
                        # Only log periodic ticks when in hijack mode and something is active
                        log(f"SERVICE [{mode_str}] PERIODIC CHECK {tick_count}: dialog_active={dialog_active}, armed={armed_state}")

                # Store state for next comparison
                last_dialog_active = dialog_active
                last_armed_state = armed_state
                last_container_path = container_path

                # Check for AI sync activation changes periodically
                if tick_count % ai_sync_check_interval == 0:
                    self._check_ai_sync_activation(tick_count)
                    
                # Check for initial sync requests first (higher priority)
                self._check_initial_sync_request()
                
                # Check for startup sync (once per service run)
                self._check_startup_sync()
                
                # Check for cache refresh requests (every 5 seconds)
                if tick_count % 50 == 0:  # Every 5 seconds
                    self._check_cache_refresh_request()
                
                
                # Check for periodic library sync (every 30 seconds when not in hijack mode)
                # Only check when idle to avoid interference with dialog operations
                if not hijack_mode and tick_count % 30 == 0:  # Every 30 seconds
                    self._check_and_perform_periodic_library_sync()
                

                # Run hijack manager tick only when needed
                if hijack_mode:
                    self.hijack_manager.tick()
                    
                    # Check if we can safely exit hijack mode AFTER hijack manager has processed
                    # Stay in hijack mode if user is still on LibraryGenie XSP pages
                    # Reuse cached container_path instead of querying again
                    on_lg_hijack_xsp = container_path and (
                        'lg_hijack_temp.xsp' in container_path or
                        'lg_hijack_debug.xsp' in container_path
                    )
                    
                    # Only allow hijack mode exit if NOT on our XSP pages
                    if on_lg_hijack_xsp:
                        # Force hijack mode to stay active for next iteration
                        needs_hijack = True
                        if not dialog_active and dialog_active != last_dialog_active:  # Log when dialog closes but still on XSP
                            log("HIJACK: Dialog closed but staying in hijack mode - user on LibraryGenie XSP")
                    # Normal hijack mode detection will handle other cases

                # Adaptive sleep timing based on mode
                if hijack_mode:
                    # Reduced frequency ticking when hijack is needed (150ms instead of 100ms)
                    # Still responsive but 33% less CPU usage
                    if self.monitor.waitForAbort(0.15):
                        break
                else:
                    # Slow ticking when idle to save resources (1 second)
                    if self.monitor.waitForAbort(1.0):
                        break

            except Exception as e:
                log_error(f"💥 SERVICE ERROR: {e}")
                import traceback
                log_error(f"SERVICE TRACEBACK: {traceback.format_exc()}")
                # Error recovery with longer wait
                if self.monitor.waitForAbort(2.0):
                    break

        log_info("🛑 LibraryGenie service stopped")

    def _check_ai_sync_activation(self, tick_count=None):
        """Check if AI sync should be started (for dynamic activation detection)"""
        try:
            current_time = time.time()
            # Only log periodic check every 5 minutes instead of 30 seconds
            should_log_periodic = (tick_count is not None and 
                                 (current_time - self._last_ai_sync_check_time) > 300)  # 5 minutes
            
            if should_log_periodic:
                log(f"🔄 Periodic AI sync check (tick {tick_count})")
                self._last_ai_sync_check_time = current_time
                
            # Check if AI sync should start and isn't already running
            if self._should_start_ai_sync(force_log=should_log_periodic):
                if not (self.sync_thread and self.sync_thread.is_alive()):
                    log_info("🚀 AI Search activation detected - starting sync thread dynamically")
                    self._start_ai_sync_thread()
            else:
                # Stop sync thread if AI Search was deactivated
                if self.sync_thread and self.sync_thread.is_alive():
                    log_info("🛑 AI Search deactivation detected - stopping sync thread")
                    self._stop_ai_sync_thread()
        except Exception as e:
            log_error(f"Error checking AI sync activation: {e}")

    def _is_safe_to_sync_library(self) -> bool:
        """Check if it's safe to perform library sync (not during video playback)"""
        try:
            # Check if video is playing
            is_playing = xbmc.getCondVisibility('Player.HasVideo')
            if is_playing:
                return False
            
            # Additional check for any active playback
            is_playing_any = xbmc.getCondVisibility('Player.Playing')
            if is_playing_any:
                return False
                
            return True
        except Exception as e:
            log_error(f"Error checking playback state: {e}")
            return False  # Err on the side of caution

    def _check_and_perform_periodic_library_sync(self):
        """Check if periodic library sync should be performed"""
        try:
            # Check if library sync is already in progress
            if self._library_sync_in_progress:
                return
                
            # Get sync interval setting
            sync_interval_minutes = self.settings.get_library_sync_interval()
            
            # If disabled (0), skip
            if sync_interval_minutes == 0:
                return
                
            # Check if enough time has passed since last sync
            current_time = time.time()
            time_since_last_sync = (current_time - self._last_library_sync_time) / 60  # Convert to minutes
            
            if time_since_last_sync < sync_interval_minutes:
                return
                
            # Check if it's safe to sync (no video playback)
            if not self._is_safe_to_sync_library():
                log("Library sync skipped - video playback active")
                return
                
            log_info(f"Starting periodic library sync (interval: {sync_interval_minutes} minutes)")
            
            # Update timestamp immediately to prevent rapid-fire syncs
            self._last_library_sync_time = current_time
            
            # Start sync in background thread to avoid blocking service loop
            sync_thread = threading.Thread(
                target=self._perform_background_library_sync,
                daemon=True,
                name="LibrarySync"
            )
            sync_thread.start()
            
        except Exception as e:
            log_error(f"Error during periodic library sync check: {e}")


    def _perform_background_library_sync(self):
        """Perform background library sync using delta scan in background thread"""
        sync_start_time = time.time()
        try:
            self._library_sync_in_progress = True
            log_info("Background library sync thread started")
            
            # Use SyncController for proper locking and error handling
            from lib.library.sync_controller import SyncController
            sync_controller = SyncController()
            
            # Check if library is indexed first
            scanner = LibraryScanner()
            if not scanner.is_library_indexed():
                log_info("Library not indexed, performing initial scan...")
                success, message = sync_controller.perform_manual_sync()
            else:
                # Use delta scan to detect new/changed movies
                log_info("Performing delta library sync to detect new movies...")
                
                # Use scanner directly for delta scan (SyncController is for manual sync)
                result = scanner.perform_delta_scan()
                success = result.get("success", False)
                
                if success:
                    items_added = result.get("items_added", 0)
                    items_removed = result.get("items_removed", 0)
                    if items_added > 0 or items_removed > 0:
                        message = f"Found {items_added} new, {items_removed} removed movies"
                        self._show_notification(f"Library updated: {message}", time_ms=3000)
                        log_info(f"Periodic sync found changes: {message}")
                    else:
                        message = "No new movies found"
                        log("Periodic library sync: No changes detected")
                else:
                    message = result.get("error", "Delta scan failed")
            
            sync_duration = time.time() - sync_start_time
            
            if success:
                log_info(f"Periodic library sync completed in {sync_duration:.1f}s: {message}")
            else:
                log_error(f"Periodic library sync failed after {sync_duration:.1f}s: {message}")
                
        except Exception as e:
            sync_duration = time.time() - sync_start_time
            log_error(f"Error during background library sync after {sync_duration:.1f}s: {e}")
            import traceback
            log_error(f"Sync error traceback: {traceback.format_exc()}")
        finally:
            self._library_sync_in_progress = False
            log_info("Background library sync thread completed")

    def _should_start_ai_sync(self, force_log=False) -> bool:
        """Check if AI search sync should be started"""
        # Read settings directly from Kodi to bypass inter-process caching issues
        import xbmcaddon
        fresh_addon = xbmcaddon.Addon()
        
        # Verify that AI search is properly configured with valid auth
        try:
            ai_search_activated = fresh_addon.getSettingBool('ai_search_activated')
        except Exception:
            ai_search_activated = False
            
        if not ai_search_activated:
            if force_log:
                log("AI Search not activated in settings")
            return False

        # Test if AI client is properly configured and authorized
        try:
            server_url = fresh_addon.getSettingString('remote_server_url')
        except Exception:
            server_url = ""
            
        try:
            api_key = fresh_addon.getSettingString('ai_search_api_key')
        except Exception:
            api_key = ""
        
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
            log(f"Server URL: '{server_url}' (exists: {current_state['server_url_exists']})")
            log(f"API Key (from settings): {'[PRESENT]' if api_key else '[MISSING]'} (length: {len(api_key) if api_key else 0})")
            log(f"is_authorized() result: {auth_status}")
            log(f"API Key (from database): {'[PRESENT]' if db_api_key else '[MISSING]'} (length: {len(db_api_key) if db_api_key else 0})")
            
            if not current_state['client_configured']:
                log("AI client not configured, skipping sync")
            else:
                log_info("✅ AI Search configuration verified")
            
            self._last_ai_sync_state = current_state
        
        if not current_state['client_configured']:
            return False

        # Configuration looks good - sync worker will test connection when it runs
        return True

    def _start_ai_sync_thread(self):
        """Start the AI search sync background thread"""
        if self.sync_thread and self.sync_thread.is_alive():
            return

        log_info("Starting AI search sync thread")
        self.sync_stop_event.clear()
        self.sync_thread = threading.Thread(target=self._ai_sync_worker, daemon=True)
        self.sync_thread.start()

    def _stop_ai_sync_thread(self):
        """Stop the AI search sync background thread"""
        if self.sync_thread and self.sync_thread.is_alive():
            log_info("Stopping AI search sync thread")
            self.sync_stop_event.set()
            self.sync_thread.join(timeout=10)

    def _ai_sync_worker(self):
        """Background worker for AI search synchronization"""
        log_info("AI search sync worker started")

        try:
            # Periodic sync based on settings - read directly from Kodi to bypass caching
            import xbmcaddon
            fresh_addon = xbmcaddon.Addon()
            try:
                sync_hours = fresh_addon.getSettingInt('ai_search_sync_interval')
            except Exception:
                sync_hours = 1  # Default to 1 hour
            sync_interval = min(sync_hours * 3600, 86400)  # Cap at 24 hours (86400 seconds) to avoid timeout errors

            while not self.sync_stop_event.is_set():
                if self.sync_stop_event.wait(sync_interval):
                    break  # Stop event was set

                # Perform sync if still enabled
                if self._should_start_ai_sync():
                    self._perform_ai_sync()
                else:
                    log_info("AI sync disabled, stopping worker")
                    break

        except Exception as e:
            log_error(f"AI sync worker error: {e}")
        finally:
            log_info("AI search sync worker stopped")
            

    def _check_startup_sync(self):
        """Check if startup sync should be performed (once per service run after 30-second settle)"""
        # Wait for 30-second settle period after service startup
        time_since_start = time.time() - self._service_start_time
        if time_since_start < 30:
            return
            
        # Only check once per service startup
        if hasattr(self, '_startup_sync_checked'):
            return
        self._startup_sync_checked = True
        
        try:
            # Import here to avoid circular imports
            from lib.library.sync_controller import SyncController
            
            # Initialize sync controller
            sync_controller = SyncController()
            
            # Skip if first run not completed (initial sync handles this)
            if sync_controller.is_first_run():
                log("Skipping startup sync - first run not completed yet")
                return
            
            # Check if sync is enabled
            sync_movies = sync_controller.settings.get_sync_movies()
            sync_tv_episodes = sync_controller.settings.get_sync_tv_episodes()
            
            if not sync_movies and not sync_tv_episodes:
                log("Skipping startup sync - no sync options enabled")
                return
            
            log_info("🚀 Performing startup library sync (delta scan)")
            
            # Perform delta sync to catch any changes since last Kodi run
            try:
                result = sync_controller.scanner.perform_delta_scan()
                if result.get("success", False):
                    items_added = result.get("items_added", 0)
                    items_removed = result.get("items_removed", 0)
                    
                    if items_added > 0 or items_removed > 0:
                        log_info(f"📚 Startup sync completed: +{items_added} new, -{items_removed} removed")
                        self._show_notification(
                            f"Library updated: {items_added} new items added",
                            time_ms=4000
                        )
                    else:
                        log("Startup sync completed: no changes detected")
                else:
                    error_msg = result.get("error", "Unknown error")
                    log_error(f"Startup sync failed: {error_msg}")
                    
            except Exception as e:
                log_error(f"Error during startup sync: {e}")
                
        except Exception as e:
            log_error(f"Error checking startup sync: {e}")

    def _check_initial_sync_request(self):
        """Check for initial sync requests from fresh install setup"""
        try:
            # Create completely fresh addon instance to bypass all caching between processes
            import xbmcaddon
            fresh_addon = xbmcaddon.Addon()
            
            # Read directly from Kodi settings without any caching layer
            try:
                initial_sync_requested = fresh_addon.getSettingBool('initial_sync_requested')
            except Exception:
                # Setting might not exist yet, treat as False
                initial_sync_requested = False
                
            if not initial_sync_requested:
                return
                
            log_info("⚡ INITIAL SYNC REQUEST DETECTED - Processing sync request")
            
            # Import here to avoid circular imports
            from lib.utils.sync_lock import GlobalSyncLock
            from lib.library.sync_controller import SyncController
            
            # Try to acquire global sync lock
            lock = GlobalSyncLock("service-initial-sync")
            if not lock.acquire():
                # Another process is already syncing
                lock_info = lock.get_lock_info()
                owner = lock_info.get('owner', 'unknown') if lock_info else 'unknown'
                log(f"Initial sync skipped - lock held by: {owner}")
                return
                
            try:
                # Clear the request flag immediately to prevent retriggering
                fresh_addon.setSettingBool('initial_sync_requested', False)
                
                # Get sync preferences directly from Kodi settings to bypass cache issues
                try:
                    sync_movies = fresh_addon.getSettingBool('sync_movies')
                except Exception:
                    sync_movies = True  # Default to True
                    
                try:
                    sync_tv_episodes = fresh_addon.getSettingBool('sync_tv_episodes')
                except Exception:
                    sync_tv_episodes = False  # Default to False
                
                log_info(f"Starting initial sync - Movies: {sync_movies}, TV: {sync_tv_episodes}")
                
                try:
                    # Initialize sync controller
                    sync_controller = SyncController()
                    
                    # Manually perform sync since we already hold the lock
                    # Don't call perform_manual_sync which tries to acquire another lock
                    
                    results = {'movies': 0, 'episodes': 0, 'errors': []}
                    start_time = time.time()
                    
                    # Always use separate dialogs for clean progress experience
                    # Sync movies if enabled
                    if sync_movies:
                        # Movies only
                        try:
                            movies_dialog = xbmcgui.DialogProgressBG()
                            movies_dialog.create("LibraryGenie", "Starting movie sync...")
                            
                            movie_count = sync_controller._sync_movies(progress_dialog=movies_dialog)
                            results['movies'] = movie_count
                            log_info(f"Synced {movie_count} movies")
                            
                            movies_dialog.close()
                        except Exception as e:
                            error_msg = f"Movie sync failed: {str(e)}"
                            results['errors'].append(error_msg)
                            log_error(error_msg)

                    # Sync TV episodes if enabled  
                    if sync_tv_episodes:
                        # TV episodes only
                        try:
                            tv_dialog = xbmcgui.DialogProgressBG()
                            tv_dialog.create("LibraryGenie", "Starting TV episodes sync...")
                            
                            episode_count = sync_controller._sync_tv_episodes(progress_dialog=tv_dialog)
                            results['episodes'] = episode_count
                            log_info(f"Synced {episode_count} TV episodes")
                            
                            tv_dialog.close()
                        except Exception as e:
                            error_msg = f"TV episode sync failed: {str(e)}"
                            results['errors'].append(error_msg)
                            log_error(error_msg)

                    # Calculate duration and format results
                    duration = time.time() - start_time
                    message = sync_controller._format_sync_results(results, duration)
                    success = len(results['errors']) == 0 or (results['movies'] > 0 or results['episodes'] > 0)
                    
                    # Show final notification
                    if success:
                        log_info(f"Initial sync completed: {message}")
                        
                        # INVALIDATE DATABASE CACHE - database size changed dramatically after initial scan
                        total_items = results['movies'] + results['episodes']
                        if total_items > 100:  # Substantial content added, likely fresh install
                            log_info(f"Fresh install sync added {total_items} items - invalidating database cache")
                            self._invalidate_and_refresh_db_cache()
                        
                        self._show_notification(
                            f"Initial sync complete: {message}",
                            xbmcgui.NOTIFICATION_INFO,
                            8000
                        )
                    else:
                        log_warning(f"Initial sync failed: {message}")
                        self._show_notification(
                            f"Initial sync failed: {message[:50]}...",
                            xbmcgui.NOTIFICATION_ERROR,
                            8000
                        )
                        
                finally:
                    # Individual progress dialogs are closed by their respective sync operations
                    pass
                    
            finally:
                lock.release()
                
        except Exception as e:
            log_error(f"Error during initial sync request handling: {e}")
            

    def _perform_ai_sync(self):
        """Perform AI search synchronization"""
        log_info("Starting AI search synchronization")

        # Show start notification
        self._show_notification(L(34103))  # "Sync in progress..."

        try:
            # Test connection first
            connection_test = self.ai_client.test_connection()
            if not connection_test.get('success'):
                error_msg = connection_test.get('error', 'Unknown error')
                log_warning(f"AI search connection failed: {error_msg}")
                self._show_notification(f"{L(34105)}: {error_msg}", xbmcgui.NOTIFICATION_ERROR)  # "Sync failed: ..."
                return

            # Get current library version for delta sync (optional - endpoint may not exist)
            server_version = self.ai_client.get_library_version()
            if not server_version:
                log_info("Server library version not available (proceeding with full sync)")

            # Scan library for movies with IMDb IDs
            scanner = LibraryScanner()
            movies_with_imdb = []

            log_info("Scanning local library for movies with IMDb IDs...")

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

            log_info(f"Found {len(movies_with_imdb)} movies with IMDb IDs")

            if not movies_with_imdb:
                log_info("No movies with IMDb IDs found, skipping sync")
                self._show_notification(L(30016), xbmcgui.NOTIFICATION_WARNING)  # "No results found" (reusing existing string)
                return

            # Sync in batches with rate limiting
            batch_size = 500  # Conservative batch size
            total_batches = (len(movies_with_imdb) + batch_size - 1) // batch_size

            for i in range(0, len(movies_with_imdb), batch_size):
                if self.sync_stop_event.is_set():
                    log_info("Sync cancelled by stop event")
                    return

                batch = movies_with_imdb[i:i + batch_size]
                batch_num = (i // batch_size) + 1

                log_info(f"Syncing batch {batch_num}/{total_batches} ({len(batch)} movies)")

                result = self.ai_client.sync_media_batch(batch, batch_size)

                if result and result.get('success'):
                    results = result.get('results', {})
                    log_info(f"Batch {batch_num} sync completed: {results.get('added', 0)} added, {results.get('already_present', 0)} existing, {results.get('invalid', 0)} invalid")

                    # Show progress notification for significant batches
                    if total_batches > 1:
                        self._show_notification(
                            f"{L(34401)} {batch_num}/{total_batches}",  # "Processing... X/Y"
                            time_ms=3000
                        )
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No response'
                    log_error(f"Batch {batch_num} sync failed: {error_msg}")
                    self._show_notification(
                        f"{L(34105)}: {error_msg}",  # "Sync failed: ..."
                        xbmcgui.NOTIFICATION_ERROR
                    )

                # Rate limiting: 1 second wait between batches
                if batch_num < total_batches and not self.sync_stop_event.is_set():
                    log("Waiting 1 second before next batch...")
                    self.sync_stop_event.wait(1)

            log_info("AI search synchronization completed")

            # Show completion notification with summary
            self._show_notification(
                f"{L(34104)} - {len(movies_with_imdb)} movies",  # "Sync completed successfully - X movies"
                time_ms=8000
            )

        except Exception as e:
            log_error(f"AI sync failed: {e}")
            self._show_notification(
                f"{L(34105)}: {str(e)}",  # "Sync failed: ..."
                xbmcgui.NOTIFICATION_ERROR,
                time_ms=8000
            )


if __name__ == '__main__':
    # Entry point for Kodi service
    service = LibraryGenieService()
    service.start()