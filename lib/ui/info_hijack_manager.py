
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
        self._last_dialog_state = False
        self._tick_count = 0

    def tick(self):
        self._tick_count += 1
        
        # Log every 1000 ticks to prove the service is running
        if self._tick_count % 1000 == 0:
            self._logger.debug(f"HIJACK: Service tick #{self._tick_count} - hijack manager is running")
        
        # Check if Info dialog is currently open
        dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        
        # Log dialog state changes
        if dialog_active != self._last_dialog_state:
            if dialog_active:
                self._logger.info("HIJACK: 🎬 Info dialog OPENED - checking for hijack targets")
            else:
                self._logger.debug("HIJACK: Info dialog CLOSED")
                if self._in_progress:
                    self._logger.debug("HIJACK: Resetting hijack state")
                self._in_progress = False
            self._last_dialog_state = dialog_active
        
        # Only process when dialog is active
        if not dialog_active:
            return

        # Already hijacking this one
        if self._in_progress:
            return

        # Get all the possible hijack properties
        armed_prop = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
        dbid_hijack = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)')
        dbtype_hijack = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)')
        
        # Also check standard library properties as fallback
        dbid_standard = xbmc.getInfoLabel('ListItem.Property(DBID)') or xbmc.getInfoLabel('ListItem.DBID')
        dbtype_standard = (xbmc.getInfoLabel('ListItem.Property(DBTYPE)') or xbmc.getInfoLabel('ListItem.DBTYPE') or '').lower()
        
        # Get container path to check if this is from our plugin
        container_path = xbmc.getInfoLabel('Container.FolderPath') or ''
        is_from_plugin = 'plugin.video.librarygenie' in container_path
        
        # Current ListItem title for debugging
        current_title = xbmc.getInfoLabel('ListItem.Title') or xbmc.getInfoLabel('ListItem.Label')
        
        # Log detailed state for debugging
        self._logger.debug(f"HIJACK: Dialog active, checking item '{current_title}':")
        self._logger.debug(f"  Armed={armed_prop}, DBID_hijack={dbid_hijack}, DBType_hijack={dbtype_hijack}")
        self._logger.debug(f"  DBID_std={dbid_standard}, DBType_std={dbtype_standard}")
        self._logger.debug(f"  Container={container_path}, FromPlugin={is_from_plugin}")
        
        # Determine if we should hijack
        explicitly_armed = armed_prop == '1'
        has_hijack_data = dbid_hijack and dbtype_hijack
        has_library_data = dbid_standard and dbtype_standard in ['movie', 'episode']
        
        should_hijack = explicitly_armed and has_hijack_data
        
        # Also hijack library items from our plugin as fallback
        if not should_hijack and is_from_plugin and has_library_data:
            should_hijack = True
            dbid_hijack = dbid_standard
            dbtype_hijack = dbtype_standard
            self._logger.info(f"HIJACK: Using fallback detection for library item from plugin")
        
        if not should_hijack:
            self._logger.debug(f"HIJACK: Not hijacking - armed={explicitly_armed}, hijack_data={has_hijack_data}, lib_data={has_library_data}, from_plugin={is_from_plugin}")
            return

        # We have a hijack target!
        self._logger.info(f"HIJACK: 🎯 HIJACK TRIGGERED for '{current_title}' - DBID={dbid_hijack}, DBType={dbtype_hijack}")
        
        if not dbid_hijack or not dbtype_hijack:
            self._logger.warning(f"HIJACK: Missing required data - DBID={dbid_hijack}, DBType={dbtype_hijack}")
            return

        self._in_progress = True
        self._logger.info(f"HIJACK: 🚀 Starting hijack process for {dbtype_hijack} {dbid_hijack}")
        
        try:
            orig_path = container_path
            self._logger.debug(f"HIJACK: Original container path: {orig_path}")
            
            ok = open_native_info(dbtype_hijack, int(dbid_hijack), self._logger, orig_path)
            if ok:
                self._logger.info(f"HIJACK: ✅ Successfully opened native info for {dbtype_hijack} {dbid_hijack}")
            else:
                self._logger.warning(f"HIJACK: ❌ Failed to open native info for {dbtype_hijack} {dbid_hijack}")
        except Exception as e:
            self._logger.error(f"HIJACK: 💥 Exception during hijack: {e}")
            import traceback
            self._logger.error(f"HIJACK: Hijack traceback: {traceback.format_exc()}")
        finally:
            # When native info is up, it won't be tagged; tick() will idle.
            self._in_progress = False
