
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
        
        # Handle dialog close detection
        if not dialog_active and self._native_info_was_open:
            self._logger.info("🔄 HIJACK STEP 5: NATIVE INFO DIALOG CLOSED - initiating container restore")
            self._handle_native_info_closed()
            self._native_info_was_open = False
            self._logger.info("✅ HIJACK STEP 5 COMPLETE: Container restoration initiated")
            return
            
        # Handle dialog open detection - this is where we trigger hijack
        if dialog_active:
            if not self._native_info_was_open and not self._in_progress:
                # Check if this is a hijackable dialog with armed item
                armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
                
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
                            # 💾 STEP 1: SAVE RETURN TARGET
                            self._logger.info(f"💾 HIJACK STEP 1: SAVING RETURN TARGET")
                            orig_path = xbmc.getInfoLabel('Container.FolderPath') or ''
                            current_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
                            
                            self._save_return_target(orig_path, current_position)
                            self._logger.info(f"✅ HIJACK STEP 1 COMPLETE: Return target saved")
                            
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

        # Only log container info when no dialog is active
        if not self._in_progress:
            # Debug: Periodically check for armed items in container
            if int(current_time * 2) % 10 == 0:  # Every 5 seconds
                container_path = xbmc.getInfoLabel('Container.FolderPath')
                if 'plugin.video.librarygenie' in container_path:
                    current_item = xbmc.getInfoLabel('Container.CurrentItem')
                    num_items = xbmc.getInfoLabel('Container.NumItems')
                    list_item_label = xbmc.getInfoLabel('ListItem.Label')
                    armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
                    self._logger.debug(f"HIJACK DEBUG: Container scan - item: {current_item}/{num_items}, label: '{list_item_label}', armed: {armed}")

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
        """Handle the native info dialog being closed - restore container"""
        try:
            # Retrieve saved return target
            return_path = xbmc.getInfoLabel('Window(Home).Property(LG.InfoHijack.ReturnPath)')
            return_position_str = xbmc.getInfoLabel('Window(Home).Property(LG.InfoHijack.ReturnPosition)')
            
            if return_path:
                self._logger.debug(f"HIJACK: Restoring container to: {return_path}")
                restore_container_after_close(return_path, return_position_str, self._logger)
                
                # Clear the saved properties
                xbmc.executebuiltin('ClearProperty(LG.InfoHijack.ReturnPath,Home)')
                xbmc.executebuiltin('ClearProperty(LG.InfoHijack.ReturnPosition,Home)')
            else:
                self._logger.debug("HIJACK: No return path saved, skipping container restore")
                
        except Exception as e:
            self._logger.error(f"HIJACK: Error during container restore: {e}")

    def _debug_scan_container(self):
        """Debug method to scan container for armed items"""
        try:
            container_path = xbmc.getInfoLabel('Container.FolderPath')
            if 'plugin.video.librarygenie' not in container_path:
                return  # Only scan our plugin content
                
            num_items = int(xbmc.getInfoLabel('Container.NumItems') or '0')
            current_item = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
            
            if num_items > 0:
                self._logger.info(f"HIJACK DEBUG: Container scan - {container_path}, item {current_item}/{num_items}")
                
                # Check current item properties
                current_armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
                current_label = xbmc.getInfoLabel('ListItem.Label')
                if current_armed == '1':
                    self._logger.info(f"HIJACK DEBUG: Current item '{current_label}' IS ARMED!")
                else:
                    self._logger.info(f"HIJACK DEBUG: Current item '{current_label}' is not armed (value: '{current_armed}')")
                    
        except Exception as e:
            self._logger.debug(f"HIJACK DEBUG: Container scan error: {e}")
