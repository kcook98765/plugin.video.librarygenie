
# -*- coding: utf-8 -*-
from __future__ import annotations
import xbmc
import xbmcgui
import time

from lib.utils.kodi_log import log, log_info, log_error, log_warning, get_kodi_logger
from lib.ui.info_hijack_helpers import open_native_info_fast, restore_container_after_close, _log
from lib.ui.navigation_cache import get_cached_info, navigation_action

class InfoHijackManager:
    """
    Redesigned hijack manager that separates native info opening from directory rebuild.
    
    Flow:
    1. When tagged item detected -> save return target and open native info immediately
    2. When native info closes -> restore container to original plugin path
    
    This prevents performance issues by not doing heavy operations during dialog opening.
    """
    def __init__(self, logger=None):
        # Using KodiLogger compatibility adapter for seamless migration
        self._logger = logger or get_kodi_logger('lib.ui.info_hijack_manager')
        self._in_progress = False
        self._native_info_was_open = False
        self._cooldown_until = 0.0
        self._last_hijack_time = 0.0
        
        # XSP Safety Net state tracking
        self._hijack_monitoring_expires = 0.0
        self._last_safety_attempt = 0.0
        self._safety_attempts = 0
        self._last_monitored_path = None
        self._path_stable_since = 0.0
        self._hijack_xsp_created = False
        
        # Anti-spam debugging
        self._last_debug_log = 0.0
        self._debug_log_interval = 10.0  # Log at most every 10 seconds
        
        # Extended monitoring for user "back" navigation to XSP pages
        self._extended_monitoring_active = False

    def tick(self):
        current_time = time.time()
        
        # Skip if we're in cooldown period
        if current_time < self._cooldown_until:
            return
            
        # OPTIMIZATION: Removed DialogBusy check - XSP navigation works even during scanning
        
        # Debug: Periodically scan container for armed items
        if int(current_time * 4) % 10 == 0:  # Every 2.5 seconds
            self._debug_scan_container()

        dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        # CRITICAL FIX: Always check for dialog close detection, regardless of mode
        # Handle dialog close detection - check before updating state
        if hasattr(self, '_last_dialog_state'):
            last_active, last_id = self._last_dialog_state
            
            # Log state changes for debugging (but only significant ones)
            if (dialog_active, current_dialog_id) != self._last_dialog_state:
                # Only log state changes involving our hijacked dialogs or when we have a native dialog open
                if self._native_info_was_open or dialog_active or last_active:
                    log(f"HIJACK DIALOG STATE CHANGE: active={dialog_active}, id={current_dialog_id} (was {self._last_dialog_state})")
            
            # PRIMARY DETECTION: dialog was active, now not active, and we had a native info open
            if last_active and not dialog_active and self._native_info_was_open:
                log("HIJACK STEP 5: DETECTED DIALOG CLOSE via state change - initiating navigation back to plugin")
                try:
                    self._handle_native_info_closed()
                    log("HIJACK STEP 5 COMPLETE: Navigation back to plugin completed")
                except Exception as e:
                    log_error(f"❌ HIJACK STEP 5 FAILED: Navigation error: {e}")
                finally:
                    self._native_info_was_open = False
                
                # Update dialog state and return to prevent further processing
                self._last_dialog_state = (dialog_active, current_dialog_id)
                return
        else:
            # Initialize dialog state tracking
            self._last_dialog_state = (False, 9999)
        
        # SECONDARY DETECTION: fallback for missed state changes (also always check)
        if not dialog_active and self._native_info_was_open:
            log("HIJACK STEP 5: NATIVE INFO DIALOG CLOSED (fallback detection) - initiating navigation back to plugin")
            try:
                self._handle_native_info_closed()
                log("HIJACK STEP 5 COMPLETE: Navigation back to plugin completed (fallback)")
            except Exception as e:
                log_error(f"❌ HIJACK STEP 5 FAILED: Navigation error (fallback): {e}")
            finally:
                self._native_info_was_open = False
            
            # Update dialog state and return to prevent further processing
            self._last_dialog_state = (dialog_active, current_dialog_id)
            return
        
        # Update dialog state for next iteration (only if no close detected)
        self._last_dialog_state = (dialog_active, current_dialog_id)
        
        # XSP AUTO-NAVIGATION: Monitor for user landing on LibraryGenie XSP pages and immediately navigate back
        # This catches user "back" navigation from hijacked dialogs
        if not dialog_active and not self._in_progress:
            self._monitor_and_handle_xsp_appearance(current_time)
            
        # Handle dialog open detection - this is where we trigger hijack
        if dialog_active:
            if not self._native_info_was_open and not self._in_progress:
                # Check if this is a hijackable dialog with armed item
                armed = get_cached_info('ListItem.Property(LG.InfoHijack.Armed)') == '1'
                listitem_label = get_cached_info('ListItem.Label')
                
                # Debug: Always log dialog detection with armed state (optimized: removed container path)
                log(f"🔍 HIJACK DIALOG DETECTED: armed={armed}, label='{listitem_label}'")
                
                if armed:
                    log("HIJACK: NATIVE INFO DIALOG DETECTED ON ARMED ITEM - starting hijack process")
                    
                    # Get hijack data (reuse listitem_label from above)
                    hijack_dbid_prop = get_cached_info('ListItem.Property(LG.InfoHijack.DBID)')
                    hijack_dbtype_prop = get_cached_info('ListItem.Property(LG.InfoHijack.DBType)')
                    native_dbid = get_cached_info('ListItem.DBID')
                    native_dbtype = get_cached_info('ListItem.DBTYPE')
                    
                    dbid = hijack_dbid_prop or native_dbid
                    dbtype = (hijack_dbtype_prop or native_dbtype or '').lower()
                    
                    if dbid and dbtype:
                        log(f"HIJACK: Target - DBID={dbid}, DBType={dbtype}, Label='{listitem_label}'")
                        
                        # Mark as in progress to prevent re-entry
                        self._in_progress = True
                        self._last_hijack_time = current_time
                        
                        try:
                            # 💾 STEP 1: TRUST KODI NAVIGATION HISTORY
                            log("HIJACK STEP 1: Using Kodi's navigation history (no saving needed)")
                            log("HIJACK STEP 1 COMPLETE: Navigation history will handle return")
                            
                            # 🚪 STEP 2: CLOSE CURRENT DIALOG
                            log("HIJACK STEP 2: CLOSING CURRENT DIALOG")
                            initial_dialog_id = xbmcgui.getCurrentWindowDialogId()
                            with navigation_action():
                                xbmc.executebuiltin('Action(Back)')
                            
                            # Monitor for dialog actually closing instead of fixed sleep
                            if self._wait_for_dialog_close("Step 2 dialog close", initial_dialog_id, max_wait=1.0):
                                log("HIJACK STEP 2 COMPLETE: Dialog closed")
                                # Brief delay to allow dialog close animations to complete
                                xbmc.sleep(25)  # 25ms for dialog close animation stability
                            else:
                                log_warning("⚠️ HIJACK STEP 2: Dialog close timeout, proceeding anyway")
                            
                            # Convert dbid to int safely
                            try:
                                dbid_int = int(dbid)
                            except (ValueError, TypeError):
                                log_error(f"HIJACK: Invalid DBID '{dbid}' - cannot convert to integer")
                                return
                            
                            # 🚀 STEP 3: OPEN NATIVE INFO VIA XSP
                            self._logger.debug("HIJACK STEP 3: OPENING NATIVE INFO for %s %s", dbtype, dbid_int)
                            
                            start_time = time.time()
                            ok = open_native_info_fast(dbtype, dbid_int, self._logger)
                            end_time = time.time()
                            
                            if ok:
                                self._logger.debug("HIJACK STEP 3 COMPLETE: Successfully opened native info for %s %s in %.3fs", dbtype, dbid_int, end_time - start_time)
                                self._native_info_was_open = True  # Mark for close detection
                                
                                # Enable XSP auto-navigation monitoring for 120 seconds
                                self._hijack_monitoring_expires = time.time() + 120.0
                                self._hijack_xsp_created = True
                                self._safety_attempts = 0  # Reset attempt counter
                                
                                # Set cooldown
                                operation_time = time.time() - current_time
                                self._cooldown_until = time.time() + max(0.5, operation_time * 2)
                                
                                # 🎉 HIJACK PROCESS COMPLETE
                                self._logger.debug("HIJACK PROCESS COMPLETE: Full hijack successful for %s %s", dbtype, dbid_int)
                            else:
                                self._logger.error("❌ HIJACK STEP 3 FAILED: Failed to open native info for %s %s", dbtype, dbid_int)
                        except Exception as e:
                            self._logger.error("HIJACK: 💥 Exception during hijack: %s", e)
                            import traceback
                            self._logger.error("HIJACK: Traceback: %s", traceback.format_exc())
                        finally:
                            self._in_progress = False
                    else:
                        self._logger.warning("HIJACK: Armed item missing DBID/DBType - DBID=%s, DBType=%s", dbid, dbtype)
                else:
                    # Non-armed dialog, just mark as seen
                    if self._is_native_info_hydrated():
                        self._native_info_was_open = True
                        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
                        listitem_title = get_cached_info('ListItem.Title')
                        self._logger.debug("HIJACK: Non-armed native info detected - Dialog ID: %s, Title: '%s'", current_dialog_id, listitem_title)
            return

        # Only log container info when no dialog is active (reduced frequency)
        if not self._in_progress:
            # Debug: Periodically check for armed items in container (less frequent)
            if int(current_time * 2) % 100 == 0:  # Every 50 seconds instead of 5
                container_path = get_cached_info('Container.FolderPath')
                if 'plugin.video.librarygenie' in container_path:
                    current_item = get_cached_info('Container.CurrentItem')
                    num_items = get_cached_info('Container.NumItems')
                    armed = get_cached_info('ListItem.Property(LG.InfoHijack.Armed)') == '1'
                    if armed:  # Only log when armed items are found
                        self._logger.debug("HIJACK: Armed item detected - %s/%s", current_item, num_items)

    def _is_native_info_hydrated(self) -> bool:
        """Check if native info dialog has native-only labels populated"""
        # Look for indicators that Kodi has populated the native dialog
        duration = get_cached_info('ListItem.Duration')
        codec = get_cached_info('ListItem.VideoCodec')
        # Keep artwork check real-time as it may be visibility-dependent
        has_artwork = xbmc.getCondVisibility('!String.IsEmpty(ListItem.Art(poster))')
        
        return bool(duration or codec or has_artwork)

    def _save_return_target(self, orig_path: str, position: int):
        """Save the return target in window properties"""
        self._logger.debug("HIJACK: Saving return target - path: %s, position: %s", orig_path, position)
        xbmc.executebuiltin('SetProperty(LG.InfoHijack.ReturnPath,%s,Home)' % orig_path)
        xbmc.executebuiltin('SetProperty(LG.InfoHijack.ReturnPosition,%s,Home)' % position)

    

    def _handle_native_info_closed(self):
        """Handle the native info dialog being closed - trust Kodi's automatic navigation"""
        try:
            self._logger.debug("HIJACK STEP 5: Native info dialog closed, checking navigation state")
            
            # Wait for dialog closing animation to complete
            self._wait_for_animations_to_complete("after dialog close")
            
            # Check current state after dialog close
            current_path = get_cached_info("Container.FolderPath")
            current_window = get_cached_info("System.CurrentWindow")
            self._logger.debug("HIJACK: Current state after dialog close - Path: '%s', Window: '%s'", current_path, current_window)
            
            # Check if we're on our own LibraryGenie hijack XSP content that needs navigation
            if self._is_on_librarygenie_hijack_xsp(current_path):
                self._logger.debug("HIJACK: ✋ Detected XSP path: '%s', executing back to return to plugin", current_path)
                
                # Wait for all animations to complete before executing back
                self._wait_for_animations_to_complete("XSP navigation")
                self._logger.debug("HIJACK: Executing back command to exit XSP")
                
                # Single back command when animations are complete
                with navigation_action():
                    xbmc.executebuiltin('Action(Back)')
                
                # Brief wait for navigation
                self._wait_for_navigation_complete("XSP exit")
                
                final_path = get_cached_info("Container.FolderPath")
                if final_path and 'plugin.video.librarygenie' in final_path:
                    self._logger.debug("HIJACK: ✅ Successfully returned to plugin: '%s'", final_path)
            else:
                # Already back in plugin content - Kodi's navigation history worked correctly
                if current_path and 'plugin.video.librarygenie' in current_path:
                    self._logger.info("HIJACK: ✅ Already back in plugin content (Kodi navigation history): '%s'", current_path)
                else:
                    self._logger.warning("HIJACK: Unexpected path after dialog close: '%s'", current_path)
            
            self._cleanup_properties()
                
        except Exception as e:
            self._logger.error("HIJACK: 💥 Error during navigation: %s", e)
            import traceback
            self._logger.error("HIJACK: Traceback: %s", traceback.format_exc())
            self._cleanup_properties()

    def _is_on_librarygenie_hijack_xsp(self, path: str) -> bool:
        """SAFE: Only detect LibraryGenie's own hijack XSP files"""
        if not path:
            return False
        
        # Only target our specific hijack XSP file
        lg_hijack_indicators = [
            'lg_hijack_temp.xsp',
            '/hijack/lg_hijack_temp.xsp',
            'lg_hijack_debug.xsp',
            '/hijack/lg_hijack_debug.xsp'
        ]
        
        for indicator in lg_hijack_indicators:
            if indicator in path:
                return True
        
        return False

    def _execute_single_back_with_verification(self) -> bool:
        """Try single back and carefully verify the result"""
        self._logger.debug("HIJACK: Attempting single back navigation")
        
        # Record where we are before the back command
        initial_path = xbmc.getInfoLabel("Container.FolderPath")
        
        # Wait longer for modal dialog closing animation to complete
        # The log shows the animation can block actions for several seconds
        self._logger.debug("HIJACK: Waiting for modal dialog closing animation to complete")
        xbmc.sleep(500)  # Increased from immediate execution to 500ms
        
        # Execute back command with validation that it was accepted
        self._logger.debug("HIJACK: Executing Action(Back)")
        xbmc.executebuiltin('Action(Back)')
        
        # Brief wait to let the action register before checking
        xbmc.sleep(100)
        
        # Wait for navigation to complete with more patience
        success = self._wait_for_plugin_content("single back", max_wait=3.0)  # Increased timeout
        
        if success:
            final_path = xbmc.getInfoLabel("Container.FolderPath")
            self._logger.info("HIJACK: Single back succeeded - Final path: '%s'", final_path)
            
            # Extra verification: make sure we're not in folder view when we should be in list view
            if 'action=show_folder' in final_path and 'action=show_list' not in final_path:
                self._logger.debug("HIJACK: Single back reached folder level, need to navigate forward to list")
                self._execute_forward_to_list()
            
            return True
        else:
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            self._logger.debug("HIJACK: Single back insufficient - Current path: '%s' (was: '%s')", current_path, initial_path)
            return False

    def _execute_additional_back_if_needed(self):
        """Execute one additional back command only if we're not yet in plugin content"""
        current_path = xbmc.getInfoLabel("Container.FolderPath")
        
        # Only execute additional back if we're still not in plugin content
        if current_path and 'plugin.video.librarygenie' not in current_path:
            self._logger.debug("HIJACK: Executing one additional back command")
            
            # Add small delay before second back command to ensure first completed
            xbmc.sleep(150)
            xbmc.executebuiltin('Action(Back)')
            
            # Brief wait to let the action register
            xbmc.sleep(100)
            
            # Wait for this navigation to complete with increased timeout
            if self._wait_for_plugin_content("additional back", max_wait=3.0):
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.info("HIJACK: Additional back succeeded - Final path: '%s'", final_path)
            else:
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.warning("HIJACK: Additional back timeout - Final path: '%s'", final_path)
        else:
            self._logger.debug("HIJACK: Already in plugin content: '%s' - no additional back needed", current_path)
    
    def _execute_forward_to_list(self):
        """Navigate forward from folder level to list level"""
        self._logger.debug("HIJACK: Navigating forward from folder to list level")
        
        # Get the current path to extract the list we were viewing
        current_path = xbmc.getInfoLabel("Container.FolderPath")
        
        # Look for the list in the current container - it should be the focused item
        current_item_label = xbmc.getInfoLabel('ListItem.Label')
        
        if current_item_label and 'Search:' in current_item_label:
            self._logger.debug("HIJACK: Found search list '%s', navigating to it", current_item_label)
            # Navigate to the focused list item
            xbmc.executebuiltin('Action(Select)')
            
            # Wait for navigation to complete
            if self._wait_for_list_content("forward to list", max_wait=2.0):
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.info("HIJACK: Forward navigation succeeded - Final path: '%s'", final_path)
            else:
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.warning("HIJACK: Forward navigation timeout - Final path: '%s'", final_path)
        else:
            self._logger.warning("HIJACK: Could not identify target list from current item: '%s'", current_item_label)

    def _wait_for_plugin_content(self, context: str, max_wait: float = 2.0) -> bool:
        """Wait specifically for plugin content to be loaded"""
        start_time = time.time()
        check_interval = 0.1  # 100ms checks for faster response
        
        while (time.time() - start_time) < max_wait:
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            
            # Check if we're back in plugin content
            if current_path and 'plugin.video.librarygenie' in current_path:
                self._logger.debug("HIJACK: Plugin content detected %s after %.3fs", context, time.time() - start_time)
                return True
                
            xbmc.sleep(int(check_interval * 1000))
        
        return False
    
    def _wait_for_list_content(self, context: str, max_wait: float = 2.0) -> bool:
        """Wait specifically for list-level plugin content to be loaded"""
        start_time = time.time()
        check_interval = 0.1  # 100ms checks for faster response
        
        while (time.time() - start_time) < max_wait:
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            
            # Check if we're back in list-level plugin content
            if current_path and 'plugin.video.librarygenie' in current_path and 'action=show_list' in current_path:
                self._logger.debug("HIJACK: Plugin list content detected %s after %.3fs", context, time.time() - start_time)
                return True
                
            xbmc.sleep(int(check_interval * 1000))
        
        return False

    def _cleanup_properties(self):
        """Clean up hijack properties"""
        xbmc.executebuiltin('ClearProperty(LG.InfoHijack.ReturnPath,Home)')
        xbmc.executebuiltin('ClearProperty(LG.InfoHijack.ReturnPosition,Home)')
        
        # Also cleanup monitoring state
        self._cleanup_hijack_monitoring_state()

    def _monitor_and_handle_xsp_appearance(self, current_time: float):
        """
        XSP Auto-Navigation: Monitor for user landing on LibraryGenie XSP pages and immediately navigate back
        This directly handles the "user navigated back from hijacked dialog" scenario
        """
        current_path = xbmc.getInfoLabel("Container.FolderPath")
        
        # Check if user is currently on our LibraryGenie hijack XSP page
        if not self._is_on_librarygenie_hijack_xsp(current_path):
            return
        
        # Only monitor within 120-second window after hijack for user "back" navigation
        if current_time > self._hijack_monitoring_expires:
            # Log expiration only once when transitioning out of monitoring
            if self._hijack_xsp_created:
                self._debug_log_with_rate_limit(
                    "XSP AUTO-NAV: 120-second monitoring window expired",
                    current_time, self._logger.info
                )
                self._cleanup_hijack_monitoring_state()
            return
        
        # Rate limiting: at least 2 seconds between attempts to avoid rapid-fire navigation
        if current_time - self._last_safety_attempt < 2.0:
            return
        
        # Log the detection with rate limiting
        self._debug_log_with_rate_limit(
            "🔄 XSP AUTO-NAV: User on LibraryGenie XSP page '%s' - executing back navigation" % current_path,
            current_time, self._logger.info
        )
        
        # Execute immediate back navigation
        self._execute_immediate_back_navigation(current_path, current_time)


    def _execute_immediate_back_navigation(self, current_path: str, current_time: float):
        """Execute immediate back navigation when user appears on XSP page"""
        
        try:
            # Record attempt for rate limiting
            self._last_safety_attempt = current_time
            
            # Execute back navigation immediately
            xbmc.executebuiltin('Action(Back)')
            
            # Brief wait for navigation to register
            xbmc.sleep(200)
            
            # Verify navigation (optional logging)
            final_path = xbmc.getInfoLabel("Container.FolderPath")
            if final_path and 'plugin.video.librarygenie' in final_path:
                self._debug_log_with_rate_limit(
                    "✅ XSP AUTO-NAV: Successfully returned to plugin: '%s'" % final_path,
                    current_time, self._logger.info
                )
            else:
                self._debug_log_with_rate_limit(
                    "🔄 XSP AUTO-NAV: Navigation executed, current path: '%s'" % final_path,
                    current_time, self._logger.info
                )
        
        except Exception as e:
            self._logger.error("❌ XSP AUTO-NAV: Error during navigation: %s", e)

    def _cleanup_hijack_monitoring_state(self):
        """Clean up hijack monitoring state when done"""
        self._hijack_xsp_created = False
        self._safety_attempts = 0
        self._last_monitored_path = None
        self._path_stable_since = 0.0
        self._hijack_monitoring_expires = 0.0

    def _debug_log_with_rate_limit(self, message: str, current_time: float, log_func):
        """Anti-spam debug logging - only log at most every 10 seconds"""
        if current_time - self._last_debug_log >= self._debug_log_interval:
            log_func(message)
            self._last_debug_log = current_time

    def _wait_for_dialog_close(self, context: str, initial_dialog_id: int, max_wait: float = 1.0) -> bool:
        """
        Monitor for dialog actually closing instead of using fixed sleep.
        Much more responsive than waiting arbitrary amounts of time.
        """
        start_time = time.time()
        check_interval = 0.02  # 20ms checks for very responsive detection
        
        while (time.time() - start_time) < max_wait:
            current_dialog_id = xbmcgui.getCurrentWindowDialogId()
            
            # Dialog closed when ID changes from the initial dialog
            if current_dialog_id != initial_dialog_id:
                elapsed = time.time() - start_time
                self._logger.debug("HIJACK: Dialog close detected %s after %.3fs (%s→%s)", context, elapsed, initial_dialog_id, current_dialog_id)
                return True
            
            xbmc.sleep(int(check_interval * 1000))
        
        elapsed = time.time() - start_time
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        self._logger.warning("HIJACK: Dialog close timeout %s after %.1fs (still %s)", context, elapsed, current_dialog_id)
        return False

    def _wait_for_animations_to_complete(self, context: str, max_wait: float = 2.0) -> bool:
        """Wait for Kodi animations to complete before issuing commands"""
        start_time = time.time()
        
        # Always log what we're checking initially
        has_modal = xbmc.getCondVisibility('System.HasModalDialog')
        is_animating = xbmc.getCondVisibility('Window.IsAnimating')
        is_inhibited = xbmc.getCondVisibility('System.IsInhibited')
        
        initial_state = []
        if has_modal: initial_state.append("modal dialog")
        if is_animating: initial_state.append("window animation") 
        if is_inhibited: initial_state.append("system inhibited")
        
        self._logger.debug("HIJACK: Animation check %s - initial state: %s", context, (', '.join(initial_state) if initial_state else 'none detected'))
        
        # If no animations detected initially, wait a bit anyway for dialog close animations
        if not (has_modal or is_animating or is_inhibited):
            if "after dialog close" in context:
                self._logger.debug("HIJACK: No animations detected but waiting 400ms for dialog close animation %s", context)
                xbmc.sleep(400)
                return True
            else:
                self._logger.debug("HIJACK: No animations detected %s, proceeding immediately", context)
                return True
        
        # Animation loop
        animation_detected = True
        consecutive_clear = 0
        
        while (time.time() - start_time) < max_wait:
            # Check multiple animation indicators
            has_modal = xbmc.getCondVisibility('System.HasModalDialog')
            is_animating = xbmc.getCondVisibility('Window.IsAnimating')
            is_inhibited = xbmc.getCondVisibility('System.IsInhibited')
            
            animations_running = has_modal or is_animating or is_inhibited
            
            if not animations_running:
                consecutive_clear += 1
                # Require 3 consecutive clear checks (150ms) for stability
                if consecutive_clear >= 3:
                    elapsed = time.time() - start_time
                    self._logger.info("HIJACK: Animations completed %s after %.3fs", context, elapsed)
                    return True
            else:
                consecutive_clear = 0
                # Log current animation state every 500ms
                if int((time.time() - start_time) * 2) % 10 == 0:  # Every 500ms
                    current_state = []
                    if has_modal: current_state.append("modal dialog")
                    if is_animating: current_state.append("window animation")
                    if is_inhibited: current_state.append("system inhibited")
                    elapsed = time.time() - start_time
                    self._logger.info("HIJACK: Still waiting %s after %.1fs - detected: %s", context, elapsed, ', '.join(current_state))
            
            xbmc.sleep(50)  # Check every 50ms
        
        elapsed = time.time() - start_time
        self._logger.warning("HIJACK: Animation wait timeout %s after %.1fs", context, elapsed)
        return False

    def _wait_for_window_manager_ready(self, context: str, max_wait: float = 0.5) -> bool:
        """
        Quick check for modal dialogs to prevent focus issues.
        Simplified for maximum performance.
        """
        # Single check for modal dialog - the main focus blocker
        if not xbmc.getCondVisibility('System.HasModalDialog'):
            self._logger.debug("HIJACK: Window manager ready %s immediately", context)
            return True
        
        # Wait longer for dialog close animation to complete
        wait_time = 300 if "after dialog close" in context else 100
        xbmc.sleep(wait_time)
        self._logger.debug("HIJACK: Modal detected %s, proceeding after %sms wait", context, wait_time)
        return True

    def _wait_for_gui_ready(self, context: str, max_wait: float = 0.1) -> bool:
        """Simple modal dialog check for focus issues only"""
        if not xbmc.getCondVisibility('System.HasModalDialog'):
            return True
        xbmc.sleep(50)
        return True

    def _wait_for_gui_ready_extended(self, context: str, max_wait: float = 0.1) -> bool:
        """Eliminated - same as basic check"""
        return self._wait_for_gui_ready(context, max_wait)

    def _wait_for_navigation_complete(self, context: str, max_wait: float = 0.2) -> bool:
        """Simplified navigation wait - just ensure command was accepted"""
        xbmc.sleep(100)
        self._logger.debug("HIJACK: Navigation assumed complete %s", context)
        return True

    def _debug_scan_container(self):
        """Debug method to scan container for armed items (minimal logging)"""
        try:
            container_path = xbmc.getInfoLabel('Container.FolderPath')
            if 'plugin.video.librarygenie' not in container_path:
                return  # Only scan our plugin content
                
            # Only log when armed items are detected
            current_armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
            if current_armed == '1':
                current_label = xbmc.getInfoLabel('ListItem.Label')
                self._logger.debug("HIJACK: Armed item detected - '%s'", current_label)
                    
        except Exception as e:
            self._logger.debug("HIJACK DEBUG: Container scan error: %s", e)
