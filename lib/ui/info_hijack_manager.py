
# -*- coding: utf-8 -*-
from __future__ import annotations
import time
import xbmc

from .info_hijack_helpers import open_native_info, _log

class InfoHijackManager:
    """
    Called frequently (tick). When DialogVideoInfo opens on one of OUR tagged
    items, quickly re-opens Kodi's native info for the same DB item and swaps
    the underlying container back to the original path.
    """
    def __init__(self, logger):
        self._logger = logger
        self._in_progress = False
        self._last_hijack_time = 0
        self._hijack_count = 0

    def tick(self):
        # Only act while Info dialog is up
        dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        if not dialog_active:
            if self._in_progress:
                self._logger.debug("HIJACK: Info dialog closed, resetting state")
            self._in_progress = False
            return

        # Already hijacking this one
        if self._in_progress:
            return

        # Debug current state
        self._logger.debug("HIJACK: Info dialog detected, checking for tagged items...")

        # Only intercept our tagged rows
        armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
        self._logger.debug(f"HIJACK: Armed status = '{xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')}'")
        
        if not armed:
            self._logger.debug("HIJACK: Item not armed, ignoring")
            return

        dbid = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)') or xbmc.getInfoLabel('ListItem.DBID')
        dbtype = (xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)') or xbmc.getInfoLabel('ListItem.DBTYPE') or '').lower()
        
        self._logger.info(f"HIJACK: 🎯 TRIGGERED for armed item - DBID={dbid}, DBType={dbtype}")
        
        if not dbid or not dbtype:
            self._logger.warning(f"HIJACK: Missing data - DBID={dbid}, DBType={dbtype}")
            return

        self._in_progress = True
        self._hijack_count += 1
        current_time = time.time()
        time_since_last = current_time - self._last_hijack_time if self._last_hijack_time > 0 else 0
        
        self._logger.info(f"HIJACK: 🚀 Starting hijack #{self._hijack_count} for {dbtype} {dbid} (last: {time_since_last:.1f}s ago)")
        
        try:
            orig_path = xbmc.getInfoLabel('Container.FolderPath') or ''
            self._logger.debug(f"HIJACK: Original container path: {orig_path}")
            
            # Add brief delay for subsequent hijacks to let Kodi settle
            if self._hijack_count > 1 and time_since_last < 2.0:
                settle_time = 100  # 100ms settle time for rapid successive hijacks
                self._logger.debug(f"HIJACK: Adding {settle_time}ms settle time for rapid successive hijack")
                xbmc.sleep(settle_time)
            
            hijack_start = time.time()
            ok = open_native_info(dbtype, int(dbid), self._logger, orig_path)
            hijack_duration = time.time() - hijack_start
            
            if ok:
                self._logger.info(f"HIJACK: ✅ Successfully opened native info for {dbtype} {dbid} in {hijack_duration:.2f}s")
            else:
                self._logger.warning(f"HIJACK: ❌ Failed to open native info for {dbtype} {dbid} after {hijack_duration:.2f}s")
                
        except Exception as e:
            self._logger.error(f"HIJACK: 💥 Exception during hijack: {e}")
        finally:
            self._last_hijack_time = current_time
            # When native info is up, it won't be tagged; tick() will idle.
            self._in_progress = False
