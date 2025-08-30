
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
            self._in_progress = False
            return

        # Already hijacking this one
        if self._in_progress:
            return

        # Debug current state
        self._logger.debug("HIJACK: Info dialog detected, checking for tagged items...")

        # Check for hijack armed status - try multiple property sources
        armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
        self._logger.debug(f"HIJACK: Armed status = '{xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')}'")
        
        # Also check if this is a library item that should be hijacked (fallback detection)
        dbid_prop = xbmc.getInfoLabel('ListItem.Property(DBID)') or xbmc.getInfoLabel('ListItem.DBID')
        dbtype_prop = (xbmc.getInfoLabel('ListItem.Property(DBTYPE)') or xbmc.getInfoLabel('ListItem.DBTYPE') or '').lower()
        
        # Get current container path to check if this is from our plugin
        container_path = xbmc.getInfoLabel('Container.FolderPath') or ''
        is_from_plugin = 'plugin.video.librarygenie' in container_path
        
        # Trigger hijack if explicitly armed OR if it's a library item from our plugin
        should_hijack = armed or (is_from_plugin and dbid_prop and dbtype_prop in ['movie', 'episode'])
        
        if not should_hijack:
            self._logger.debug(f"HIJACK: Not hijacking - armed={armed}, from_plugin={is_from_plugin}, dbid={dbid_prop}, dbtype={dbtype_prop}")
            return

        # Get database info from multiple sources
        dbid = (xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)') or 
                xbmc.getInfoLabel('ListItem.Property(DBID)') or 
                xbmc.getInfoLabel('ListItem.DBID'))
        dbtype = (xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)') or 
                  xbmc.getInfoLabel('ListItem.Property(DBTYPE)') or 
                  xbmc.getInfoLabel('ListItem.DBTYPE') or '').lower()
        
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
