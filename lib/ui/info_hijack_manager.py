
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
        if not xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)'):
            self._in_progress = False
            return

        # Already hijacking this one
        if self._in_progress:
            return

        # Only intercept our tagged rows
        armed = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)') == '1'
        if not armed:
            return

        dbid = xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)') or xbmc.getInfoLabel('ListItem.DBID')
        dbtype = (xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)') or xbmc.getInfoLabel('ListItem.DBTYPE') or '').lower()
        if not dbid or not dbtype:
            return

        self._in_progress = True
        try:
            orig_path = xbmc.getInfoLabel('Container.FolderPath') or ''
            ok = open_native_info(dbtype, int(dbid), self._logger, orig_path)
            if ok:
                self._logger.debug(f"Info hijack: native info opened for {dbtype} {dbid}")
            else:
                self._logger.debug(f"Info hijack: failed for {dbtype} {dbid}")
        except Exception as e:
            self._logger.warning(f"Info hijack error: {e}")
        finally:
            # When native info is up, it won't be tagged; tick() will idle.
            self._in_progress = False
