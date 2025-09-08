
# -*- coding: utf-8 -*-
from __future__ import annotations
import xbmc
import xbmcgui
import time

from .info_hijack_helpers import open_native_info_fast, restore_container_after_close, _log

class InfoHijackManager:
    """
    Redesigned hijack manager that separates native info opening from directory rebuild.
    
    Flow:
    1. When tagged item detected -> save return target and open native info immediately
    2. When native info closes -> restore container to original plugin path
    
    This prevents performance issues by not doing heavy operations during dialog opening.
    """
    def __init__(self, logger):
        self._logger = logger
        self._in_progress = False
        self._native_info_was_open = False
        self._cooldown_until = 0.0
        self._last_hijack_time = 0.0

    def tick(self):
        current_time = time.time()
        
        # Skip if we're in cooldown period
        if current_time < self._cooldown_until:
            return
            
        # Check if addon is busy with major operations
        if xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)'):
            self._logger.debug("HIJACK: Addon busy, skipping hijack logic")
            return
        
        # Debug: Periodically scan container for armed items
        if int(current_time * 4) % 10 == 0:  # Every 2.5 seconds
            self._debug_scan_container()

        dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        # Handle dialog close detection - check before updating state
        if hasattr(self, '_last_dialog_state'):
            last_active, last_id = self._last_dialog_state
            
            # Log state changes for debugging
            if (dialog_active, current_dialog_id) != self._last_dialog_state:
                self._logger.info(f"🔍 HIJACK DIALOG STATE CHANGE: active={dialog_active}, id={current_dialog_id} (was {self._last_dialog_state})")
            
            # Primary detection: dialog was active, now not active
            if last_active and not dialog_active and self._native_info_was_open:
                self._logger.info("🔄 HIJACK STEP 5: DETECTED DIALOG CLOSE via state change - initiating navigation back to plugin")
                try:
                    self._handle_native_info_closed()
                    self._logger.info("✅ HIJACK STEP 5 COMPLETE: Navigation back to plugin completed")
                except Exception as e:
                    self._logger.error(f"❌ HIJACK STEP 5 FAILED: Navigation error: {e}")
                finally:
                    self._native_info_was_open = False
                    self._last_dialog_state = (dialog_active, current_dialog_id)
                return
        else:
            # Initialize dialog state tracking
            self._last_dialog_state = (False, 9999)
        
        # Secondary detection: fallback for missed state changes
        if not dialog_active and self._native_info_was_open:
            self._logger.info("🔄 HIJACK STEP 5: NATIVE INFO DIALOG CLOSED (fallback detection) - initiating navigation back to plugin")
            try:
                self._handle_native_info_closed()
                self._logger.info("✅ HIJACK STEP 5 COMPLETE: Navigation back to plugin completed (fallback)")
            except Exception as e:
                self._logger.error(f"❌ HIJACK STEP 5 FAILED: Navigation error (fallback): {e}")
            finally:
                self._native_info_was_open = False
                self._last_dialog_state = (dialog_active, current_dialog_id)
            return
        
        # Update dialog state for next iteration (only if no close detected)
        self._last_dialog_state = (dialog_active, current_dialog_id)
            
        # Handle dialog open detection - this is where we trigger hijack
        if dialog_active:
            if not self._native_info_was_open and not self._in_progress:
                # Check if this is a hijackable dialog with armed item
                armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
                listitem_label = xbmc.getInfoLabel('ListItem.Label')
                container_path = xbmc.getInfoLabel('Container.FolderPath')
                
                # Debug: Always log dialog detection with armed state
                self._logger.debug(f"🔍 HIJACK DIALOG DETECTED: armed={armed}, label='{listitem_label}', container='{container_path[:50]}...' if container_path else 'None'")
                
                if armed:
                    self._logger.info(f"🎯 HIJACK: NATIVE INFO DIALOG DETECTED ON ARMED ITEM - starting hijack process")
                    
                    # Get hijack data
                    listitem_label = xbmc.getInfoLabel('ListItem.Label')
                    hijack_dbid_prop = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)')
                    hijack_dbtype_prop = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)')
                    native_dbid = xbmc.getInfoLabel('ListItem.DBID')
                    native_dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
                    
                    dbid = hijack_dbid_prop or native_dbid
                    dbtype = (hijack_dbtype_prop or native_dbtype or '').lower()
                    
                    if dbid and dbtype:
                        self._logger.info(f"HIJACK: Target - DBID={dbid}, DBType={dbtype}, Label='{listitem_label}'")
                        
                        # Mark as in progress to prevent re-entry
                        self._in_progress = True
                        self._last_hijack_time = current_time
                        
                        try:
                            # 💾 STEP 1: TRUST KODI NAVIGATION HISTORY
                            self._logger.info(f"💾 HIJACK STEP 1: Using Kodi's navigation history (no saving needed)")
                            self._logger.info(f"✅ HIJACK STEP 1 COMPLETE: Navigation history will handle return")
                            
                            # 🚪 STEP 2: CLOSE CURRENT DIALOG
                            self._logger.info(f"🚪 HIJACK STEP 2: CLOSING CURRENT DIALOG")
                            xbmc.executebuiltin('Action(Back)')
                            xbmc.sleep(200)  # Wait for dialog to close
                            self._logger.info(f"✅ HIJACK STEP 2 COMPLETE: Dialog closed")
                            
                            # Convert dbid to int safely
                            try:
                                dbid_int = int(dbid)
                            except (ValueError, TypeError):
                                self._logger.error(f"HIJACK: Invalid DBID '{dbid}' - cannot convert to integer")
                                return
                            
                            # 🚀 STEP 3: OPEN NATIVE INFO VIA XSP
                            self._logger.info(f"🚀 HIJACK STEP 3: OPENING NATIVE INFO for {dbtype} {dbid_int}")
                            
                            start_time = time.time()
                            ok = open_native_info_fast(dbtype, dbid_int, self._logger)
                            end_time = time.time()
                            
                            if ok:
                                self._logger.info(f"✅ HIJACK STEP 3 COMPLETE: Successfully opened native info for {dbtype} {dbid_int} in {end_time - start_time:.3f}s")
                                self._native_info_was_open = True  # Mark for close detection
                                
                                # Set cooldown
                                operation_time = time.time() - current_time
                                self._cooldown_until = time.time() + max(0.5, operation_time * 2)
                                
                                # 🎉 HIJACK PROCESS COMPLETE
                                self._logger.info(f"🎉 HIJACK PROCESS COMPLETE: Full hijack successful for {dbtype} {dbid_int}")
                            else:
                                self._logger.error(f"❌ HIJACK STEP 3 FAILED: Failed to open native info for {dbtype} {dbid_int}")
                        except Exception as e:
                            self._logger.error(f"HIJACK: 💥 Exception during hijack: {e}")
                            import traceback
                            self._logger.error(f"HIJACK: Traceback: {traceback.format_exc()}")
                        finally:
                            self._in_progress = False
                    else:
                        self._logger.warning(f"HIJACK: Armed item missing DBID/DBType - DBID={dbid}, DBType={dbtype}")
                else:
                    # Non-armed dialog, just mark as seen
                    if self._is_native_info_hydrated():
                        self._native_info_was_open = True
                        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
                        listitem_title = xbmc.getInfoLabel('ListItem.Title')
                        self._logger.debug(f"HIJACK: Non-armed native info detected - Dialog ID: {current_dialog_id}, Title: '{listitem_title}'")
            return

        # Only log container info when no dialog is active (reduced frequency)
        if not self._in_progress:
            # Debug: Periodically check for armed items in container (less frequent)
            if int(current_time * 2) % 100 == 0:  # Every 50 seconds instead of 5
                container_path = xbmc.getInfoLabel('Container.FolderPath')
                if 'plugin.video.librarygenie' in container_path:
                    current_item = xbmc.getInfoLabel('Container.CurrentItem')
                    num_items = xbmc.getInfoLabel('Container.NumItems')
                    armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
                    if armed:  # Only log when armed items are found
                        self._logger.debug(f"HIJACK: Armed item detected - {current_item}/{num_items}")

    def _is_native_info_hydrated(self) -> bool:
        """Check if native info dialog has native-only labels populated"""
        # Look for indicators that Kodi has populated the native dialog
        duration = xbmc.getInfoLabel('ListItem.Duration')
        codec = xbmc.getInfoLabel('ListItem.VideoCodec')
        has_artwork = xbmc.getCondVisibility('!String.IsEmpty(ListItem.Art(poster))')
        
        return bool(duration or codec or has_artwork)

    def _save_return_target(self, orig_path: str, position: int):
        """Save the return target in window properties"""
        self._logger.debug(f"HIJACK: Saving return target - path: {orig_path}, position: {position}")
        xbmc.executebuiltin(f'SetProperty(LG.InfoHijack.ReturnPath,{orig_path},Home)')
        xbmc.executebuiltin(f'SetProperty(LG.InfoHijack.ReturnPosition,{position},Home)')

    

    def _handle_native_info_closed(self):
        """Handle the native info dialog being closed - detect XSP and execute proper navigation"""
        try:
            self._logger.info("🔄 HIJACK STEP 5: Native info dialog closed, starting navigation back to plugin")
            
            # Wait for dialog close animation to complete
            if not self._wait_for_gui_ready_extended("after dialog close", max_wait=3.0):
                self._logger.warning("HIJACK: GUI not ready after 3s, proceeding anyway")
            
            # Log current state for verification
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            current_window = xbmc.getInfoLabel("System.CurrentWindow")
            self._logger.info(f"HIJACK: Current state - Path: '{current_path}', Window: '{current_window}'")
            
            # Execute first back command
            self._logger.info("HIJACK: Executing first back command")
            xbmc.executebuiltin('Action(Back)')
            
            # Wait for first navigation to complete
            if not self._wait_for_navigation_complete("first back", max_wait=3.0):
                self._logger.warning("HIJACK: First back navigation timeout")
            
            # Check if we're now on an XSP path (temporary hijack list)
            intermediate_path = xbmc.getInfoLabel("Container.FolderPath")
            intermediate_window = xbmc.getInfoLabel("System.CurrentWindow")
            
            self._logger.info(f"HIJACK: After first back - Path: '{intermediate_path}', Window: '{intermediate_window}'")
            
            # Detect if we're on XSP/temporary list that needs second back
            if self._is_currently_on_xsp(intermediate_path, intermediate_window):
                self._logger.info(f"HIJACK: ✋ Detected XSP path: '{intermediate_path}', executing second back")
                
                # Brief pause before second back
                xbmc.sleep(150)
                
                # Execute second back command to return to original plugin content
                self._logger.info("HIJACK: Executing second back command")
                xbmc.executebuiltin('Action(Back)')
                
                # Wait for second navigation to complete
                if not self._wait_for_navigation_complete("second back", max_wait=3.0):
                    self._logger.warning("HIJACK: Second back navigation timeout")
                
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                if final_path and 'plugin.video.librarygenie' in final_path:
                    self._logger.info(f"HIJACK: ✅ Double-back successful, returned to plugin: '{final_path}'")
                else:
                    self._logger.warning(f"HIJACK: Double-back failed, unexpected path: '{final_path}'")
            else:
                # Single back was sufficient - we're already back in plugin content
                if intermediate_path and 'plugin.video.librarygenie' in intermediate_path:
                    self._logger.info(f"HIJACK: ✅ Single back successful, returned to plugin: '{intermediate_path}'")
                else:
                    self._logger.warning(f"HIJACK: Single back insufficient, unexpected path: '{intermediate_path}'")
            
            self._cleanup_properties()
                
        except Exception as e:
            self._logger.error(f"HIJACK: 💥 Error during navigation: {e}")
            import traceback
            self._logger.error(f"HIJACK: Traceback: {traceback.format_exc()}")
            self._cleanup_properties()

    def _is_currently_on_xsp(self, path: str, window: str) -> bool:
        """Determine if we're currently on an XSP path"""
        if not path:
            return False
            
        # Direct XSP indicators
        xsp_indicators = ['.xsp', 'smartplaylist', 'lg_hijack', 'playlists/video']
        if any(indicator in path.lower() for indicator in xsp_indicators):
            return True
            
        # Window context check - Videos window but not plugin content
        if window and 'video' in window.lower():
            if 'plugin.video.librarygenie' not in path:
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
            self._logger.info(f"HIJACK: Single back succeeded - Final path: '{final_path}'")
            
            # Extra verification: make sure we're not in folder view when we should be in list view
            if 'action=show_folder' in final_path and 'action=show_list' not in final_path:
                self._logger.debug(f"HIJACK: Single back reached folder level, need to navigate forward to list")
                self._execute_forward_to_list()
            
            return True
        else:
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            self._logger.debug(f"HIJACK: Single back insufficient - Current path: '{current_path}' (was: '{initial_path}')")
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
                self._logger.info(f"HIJACK: Additional back succeeded - Final path: '{final_path}'")
            else:
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.warning(f"HIJACK: Additional back timeout - Final path: '{final_path}'")
        else:
            self._logger.debug(f"HIJACK: Already in plugin content: '{current_path}' - no additional back needed")
    
    def _execute_forward_to_list(self):
        """Navigate forward from folder level to list level"""
        self._logger.debug("HIJACK: Navigating forward from folder to list level")
        
        # Get the current path to extract the list we were viewing
        current_path = xbmc.getInfoLabel("Container.FolderPath")
        
        # Look for the list in the current container - it should be the focused item
        current_item_label = xbmc.getInfoLabel('ListItem.Label')
        
        if current_item_label and 'Search:' in current_item_label:
            self._logger.debug(f"HIJACK: Found search list '{current_item_label}', navigating to it")
            # Navigate to the focused list item
            xbmc.executebuiltin('Action(Select)')
            
            # Wait for navigation to complete
            if self._wait_for_list_content("forward to list", max_wait=2.0):
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.info(f"HIJACK: Forward navigation succeeded - Final path: '{final_path}'")
            else:
                final_path = xbmc.getInfoLabel("Container.FolderPath")
                self._logger.warning(f"HIJACK: Forward navigation timeout - Final path: '{final_path}'")
        else:
            self._logger.warning(f"HIJACK: Could not identify target list from current item: '{current_item_label}'")

    def _wait_for_plugin_content(self, context: str, max_wait: float = 2.0) -> bool:
        """Wait specifically for plugin content to be loaded"""
        start_time = time.time()
        check_interval = 0.1  # 100ms checks for faster response
        
        while (time.time() - start_time) < max_wait:
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            
            # Check if we're back in plugin content
            if current_path and 'plugin.video.librarygenie' in current_path:
                self._logger.debug(f"HIJACK: Plugin content detected {context} after {time.time() - start_time:.3f}s")
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
                self._logger.debug(f"HIJACK: Plugin list content detected {context} after {time.time() - start_time:.3f}s")
                return True
                
            xbmc.sleep(int(check_interval * 1000))
        
        return False

    def _cleanup_properties(self):
        """Clean up hijack properties"""
        xbmc.executebuiltin('ClearProperty(LG.InfoHijack.ReturnPath,Home)')
        xbmc.executebuiltin('ClearProperty(LG.InfoHijack.ReturnPosition,Home)')

    def _wait_for_gui_ready(self, context: str, max_wait: float = 2.0) -> bool:
        """Wait for Kodi GUI to be ready to accept actions"""
        start_time = time.time()
        check_interval = 0.05  # 50ms checks
        consecutive_ready_checks = 0
        
        while (time.time() - start_time) < max_wait:
            # Multiple checks for GUI readiness
            is_ready = (
                not xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)') and
                not xbmc.getCondVisibility('Window.IsActive(DialogProgress.xml)') and
                not xbmc.getCondVisibility('System.HasModalDialog')
            )
            
            if is_ready:
                consecutive_ready_checks += 1
                # Require multiple consecutive ready checks for stability
                if consecutive_ready_checks >= 3:
                    self._logger.debug(f"HIJACK: GUI ready {context} after {time.time() - start_time:.3f}s")
                    return True
            else:
                consecutive_ready_checks = 0
            
            xbmc.sleep(int(check_interval * 1000))
        
        self._logger.warning(f"HIJACK: GUI readiness timeout {context} after {max_wait:.1f}s")
        return False

    def _wait_for_gui_ready_extended(self, context: str, max_wait: float = 5.0) -> bool:
        """Wait for Kodi GUI to be ready with extended timeout for dialog animations"""
        start_time = time.time()
        check_interval = 0.1  # 100ms checks for longer waits
        consecutive_ready_checks = 0
        animation_detected = False
        
        while (time.time() - start_time) < max_wait:
            # Check for dialog animation in progress (this is the key issue from the log)
            has_modal = xbmc.getCondVisibility('System.HasModalDialog')
            is_busy = xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)')
            is_progress = xbmc.getCondVisibility('Window.IsActive(DialogProgress.xml)')
            
            # Additional check for window manager busy state
            window_manager_busy = xbmc.getCondVisibility('Window.IsMedia') and has_modal
            
            is_ready = not (has_modal or is_busy or is_progress or window_manager_busy)
            
            # Log when we detect animation state
            if (has_modal or window_manager_busy) and not animation_detected:
                animation_detected = True
                elapsed = time.time() - start_time
                self._logger.debug(f"HIJACK: Dialog animation detected at {elapsed:.3f}s - waiting for completion")
            
            if is_ready:
                consecutive_ready_checks += 1
                # Require more consecutive checks for longer waits
                required_checks = 5 if animation_detected else 3
                if consecutive_ready_checks >= required_checks:
                    elapsed = time.time() - start_time
                    self._logger.debug(f"HIJACK: GUI ready {context} after {elapsed:.3f}s (animation_detected={animation_detected})")
                    return True
            else:
                consecutive_ready_checks = 0
            
            xbmc.sleep(int(check_interval * 1000))
        
        elapsed = time.time() - start_time
        self._logger.warning(f"HIJACK: GUI readiness timeout {context} after {elapsed:.1f}s (animation_detected={animation_detected})")
        return False

    def _wait_for_navigation_complete(self, context: str, max_wait: float = 2.0) -> bool:
        """Wait for navigation to complete by monitoring path changes"""
        start_time = time.time()
        check_interval = 0.05  # 50ms checks
        initial_path = xbmc.getInfoLabel("Container.FolderPath")
        path_change_detected = False
        stable_count = 0
        last_path = initial_path
        
        # For XSP navigation, we need more patience
        if "first back" in context and max_wait < 3.0:
            max_wait = 3.0  # Give XSP navigation more time
        
        while (time.time() - start_time) < max_wait:
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            
            # First detect that path has changed from initial
            if current_path != initial_path and current_path:
                path_change_detected = True
            
            # Check for path stability once we've detected a change
            if path_change_detected:
                if current_path == last_path:
                    stable_count += 1
                    # Require longer stability for first back (XSP navigation)
                    required_stability = 6 if "first back" in context else 3
                    if stable_count >= required_stability:
                        self._logger.debug(f"HIJACK: Navigation complete {context} after {time.time() - start_time:.3f}s - Path: '{current_path}'")
                        return True
                else:
                    stable_count = 0  # Reset if path is still changing
                    last_path = current_path
            
            xbmc.sleep(int(check_interval * 1000))
        
        final_path = xbmc.getInfoLabel("Container.FolderPath")
        # Only warn if no path change was detected at all
        if not path_change_detected:
            self._logger.warning(f"HIJACK: Navigation timeout {context} after {max_wait:.1f}s - No path change detected. Final path: '{final_path}'")
        else:
            self._logger.debug(f"HIJACK: Navigation {context} took {time.time() - start_time:.3f}s (may still be completing) - Final path: '{final_path}'")
        
        return path_change_detected

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
                self._logger.debug(f"HIJACK: Armed item detected - '{current_label}'")
                    
        except Exception as e:
            self._logger.debug(f"HIJACK DEBUG: Container scan error: {e}")
