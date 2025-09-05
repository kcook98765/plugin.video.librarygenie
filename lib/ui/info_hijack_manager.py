
# -*- coding: utf-8 -*-
from __future__ import annotations
import xbmc
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

        dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        
        # Handle dialog close detection
        if not dialog_active and self._native_info_was_open:
            self._logger.debug("HIJACK: Native info dialog closed, initiating container restore")
            self._handle_native_info_closed()
            self._native_info_was_open = False
            return
            
        # Handle dialog open detection
        if dialog_active:
            if not self._native_info_was_open and not self._in_progress:
                # Check if this is our native info (has readiness indicators)
                if self._is_native_info_hydrated():
                    self._native_info_was_open = True
                    self._logger.debug("HIJACK: Native info dialog detected and hydrated")
            return

        # Only attempt new hijacks when no dialog is active
        if self._in_progress:
            return

        # Check for tagged items
        armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
        if not armed:
            return

        dbid = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)') or xbmc.getInfoLabel('ListItem.DBID')
        dbtype = (xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)') or xbmc.getInfoLabel('ListItem.DBTYPE') or '').lower()
        
        self._logger.debug(f"HIJACK: 🎯 TRIGGERED for armed item - DBID={dbid}, DBType={dbtype}")
        
        if not dbid or not dbtype:
            self._logger.warning(f"HIJACK: Missing data - DBID={dbid}, DBType={dbtype}")
            return

        self._in_progress = True
        self._last_hijack_time = current_time
        
        try:
            # Save return target before opening native info
            orig_path = xbmc.getInfoLabel('Container.FolderPath') or ''
            current_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
            
            self._save_return_target(orig_path, current_position)
            
            # Open native info WITHOUT directory rebuild
            ok = open_native_info_fast(dbtype, int(dbid), self._logger)
            if ok:
                self._logger.debug(f"HIJACK: ✅ Successfully opened native info for {dbtype} {dbid}")
                # Set cooldown based on how long the operation took
                operation_time = time.time() - current_time
                self._cooldown_until = time.time() + max(0.5, operation_time * 2)
            else:
                self._logger.warning(f"HIJACK: ❌ Failed to open native info for {dbtype} {dbid}")
        except Exception as e:
            self._logger.error(f"HIJACK: 💥 Exception during hijack: {e}")
        finally:
            self._in_progress = False

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
