
# -*- coding: utf-8 -*-
from __future__ import annotations
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

    def tick(self):
        # Only act while Info dialog is up
        dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        if not dialog_active:
            if self._in_progress:
                self._logger.debug("HIJACK: Info dialog closed, resetting state")
                # Check if we need to restore navigation context
                self._check_navigation_restoration()
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
        self._logger.info(f"HIJACK: 🚀 Starting hijack process for {dbtype} {dbid}")
        
        try:
            orig_path = xbmc.getInfoLabel('Container.FolderPath') or ''
            self._logger.debug(f"HIJACK: Original container path: {orig_path}")
            
            ok = open_native_info(dbtype, int(dbid), self._logger, orig_path)
            if ok:
                self._logger.info(f"HIJACK: ✅ Successfully opened native info for {dbtype} {dbid}")
            else:
                self._logger.warning(f"HIJACK: ❌ Failed to open native info for {dbtype} {dbid}")
        except Exception as e:
            self._logger.error(f"HIJACK: 💥 Exception during hijack: {e}")
        finally:
            # When native info is up, it won't be tagged; tick() will idle.
            self._in_progress = False

    def _check_navigation_restoration(self):
        """Check if we need to restore original navigation context after info dialog closes"""
        try:
            # Get stored original path
            orig_path = xbmc.getInfoLabel('Window(Home).Property(LG.OriginalPath)')
            if not orig_path:
                return
            
            # Check current container path
            current_path = xbmc.getInfoLabel('Container.FolderPath')
            self._logger.debug(f"HIJACK: Navigation check - current: {current_path}, original: {orig_path}")
            
            # If we're still in an XSP or videodb context, user might want to go back further
            if current_path and ('special://temp' in current_path or 'videodb://' in current_path):
                # Set up a brief monitor to handle potential Back navigation
                self._logger.debug("HIJACK: User may navigate back from XSP/videodb view")
                # Store context for potential restoration
                xbmc.executebuiltin(f'SetProperty(LG.BackupPath,{current_path},Home)')
            
            # Clear the stored original path
            xbmc.executebuiltin('ClearProperty(LG.OriginalPath,Home)')
            
        except Exception as e:
            self._logger.error(f"HIJACK: Error in navigation restoration check: {e}")
