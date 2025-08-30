here’s a concrete, copy-pasteable set of changes (no extra knobs) to gate the “native Info hijack” behind a single add-on setting, keep your rich rows, and do the XSP hop only when the user opens Info on one of your library items.

I’m showing each step with the exact snippets to add/modify.

1) Add the single setting

resources/settings.xml (add anywhere appropriate, e.g. your UI category)

```<setting id="info_hijack_enabled"
         type="bool"
         label="Use native Kodi Info for library items"
         default="true" />
```
2) Tag only your library rows

Where you already build library-linked ListItems (i.e., you’ve set InfoTagVideo.setDbId() and media type), add three properties so the service can recognize them when Info opens. Do not add these on non-library/plugin rows.

lib/ui/listitem_builder.py (or wherever you create library rows)

```# ... you already do something like:
li = xbmcgui.ListItem(label=title)
vit = li.getVideoInfoTag()
vit.setMediaType('movie')               # or tvshow/episode/musicvideo
vit.setDbId(int(dbid))                  # you’re already doing this on v20/v21

# ✨ Add these three properties on library items only:
li.setProperty("LG.InfoHijack.Armed", "1")
li.setProperty("LG.InfoHijack.DBID", str(dbid))
li.setProperty("LG.InfoHijack.DBType", dbtype)   # "movie" | "tvshow" | "episode" | "musicvideo"
```

3) New helpers (small, focused)

Create a tiny helpers module the manager can use. This is mostly your harness logic, trimmed and reused.

lib/ui/info_hijack_helpers.py

```# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, time, html
from typing import Optional

import xbmc
import xbmcgui
import xbmcvfs

LOG_PREFIX = "[LG.Hijack]"
LIST_ID = 50
VIDEOS_WINDOW = "MyVideoNav.xml"

def _log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"{LOG_PREFIX} {msg}", level)

def kodi_major() -> int:
    ver = xbmc.getInfoLabel('System.BuildVersion') or ''
    try:
        return int(ver.split('.')[0])
    except Exception:
        return 0

def jsonrpc(method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    raw = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        return json.loads(raw)
    except Exception:
        _log(f"JSON parse error for {method}: {raw}", xbmc.LOGWARNING)
        return {}

def wait_until(cond, timeout_ms=2000, step_ms=30) -> bool:
    end = time.time() + (timeout_ms / 1000.0)
    mon = xbmc.Monitor()
    while time.time() < end and not mon.abortRequested():
        if cond():
            return True
        xbmc.sleep(step_ms)
    return False

def focus_list(control_id: int = LIST_ID, tries: int = 20, step_ms: int = 30) -> bool:
    for _ in range(tries):
        xbmc.executebuiltin(f"SetFocus({control_id})")
        if xbmc.getCondVisibility(f"Control.HasFocus({control_id})"):
            return True
        xbmc.sleep(step_ms)
    return False

def _write_text(path_special: str, text: str) -> bool:
    try:
        f = xbmcvfs.File(path_special, 'w')
        f.write(text.encode('utf-8'))
        f.close()
        return True
    except Exception as e:
        _log(f"xbmcvfs write failed: {e}", xbmc.LOGWARNING)
        return False

def _get_file_for_dbitem(dbtype: str, dbid: int) -> Optional[str]:
    if dbtype == "movie":
        data = jsonrpc("VideoLibrary.GetMovieDetails", {"movieid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("moviedetails") or {}
        return md.get("file")
    elif dbtype == "episode":
        data = jsonrpc("VideoLibrary.GetEpisodeDetails", {"episodeid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("episodedetails") or {}
        return md.get("file")
    elif dbtype == "musicvideo":
        data = jsonrpc("VideoLibrary.GetMusicVideoDetails", {"musicvideoid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("musicvideodetails") or {}
        return md.get("file")
    elif dbtype == "tvshow":
        # tvshow has multiple files; we’ll still open its videodb node below.
        return None
    return None

def _create_xsp_for_file(dbtype: str, dbid: int) -> Optional[str]:
    fp = _get_file_for_dbitem(dbtype, dbid)
    if not fp:
        return None
    filename = os.path.basename(fp)
    name = f"LG Native Info {dbtype} {dbid}"
    xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="video">
  <name>{html.escape(name)}</name>
  <match>all</match>
  <rule field="filename" operator="is">
    <value>{html.escape(filename)}</value>
  </rule>
  <order direction="ascending">title</order>
</smartplaylist>"""
    path = f"special://temp/lg_hijack_{dbtype}_{dbid}.xsp"
    if _write_text(path, xsp):
        return path
    return None

def _cleanup_xsp(path_special: Optional[str]):
    try:
        if path_special and xbmcvfs.exists(path_special):
            xbmcvfs.delete(path_special)
    except Exception as e:
        _log(f"Cleanup failed: {e}", xbmc.LOGDEBUG)

def _find_index_in_dir_by_file(directory: str, target_file: Optional[str]) -> int:
    data = jsonrpc("Files.GetDirectory", {
        "directory": directory, "media": "video",
        "properties": ["file", "title", "thumbnail"]
    })
    items = (data.get("result") or {}).get("files") or []
    if not items:
        return 0
    if target_file:
        for idx, it in enumerate(items):
            if it.get("file") == target_file:
                return idx
    # Common: (“..” at 0) and our item at 1
    return 1 if len(items) == 2 and items[0].get("file","").endswith("..") else 0

def _wait_videos_on(path: str, timeout_ms=6000) -> bool:
    t_norm = (path or "").rstrip('/')
    return wait_until(lambda:
        xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        and (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/') == t_norm
        and int(xbmc.getInfoLabel("Container.NumItems") or "0") > 0
        and not xbmc.getCondVisibility("Window.IsActive(DialogBusy.xml)")
    , timeout_ms=timeout_ms, step_ms=100)

def open_native_info(dbtype: str, dbid: int, logger, orig_path: str) -> bool:
    """
    Close current dialog (already open on plugin item), navigate to a native
    library context (XSP by file for items with a file; videodb node for tvshow),
    focus row, open Info, then immediately restore underlying container to orig_path.
    """
    # 1) Close the plugin’s Info dialog
    xbmc.executebuiltin("Action(Back)")
    wait_until(lambda: not xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)"), 1200, 30)

    path_to_open = None
    focus_index = 0

    if dbtype == "tvshow":
        path_to_open = f"videodb://tvshows/titles/{int(dbid)}"
        target_file = None
    else:
        xsp = _create_xsp_for_file(dbtype, dbid)
        if xsp:
            path_to_open = xsp
            target_file = _get_file_for_dbitem(dbtype, dbid)
        else:
            # Fallback to a generic videodb node if no file (rare)
            if dbtype == "movie":
                path_to_open = f"videodb://movies/titles/{int(dbid)}"
            elif dbtype == "episode":
                # as a fallback, show season/episodes node; still better than nothing
                path_to_open = f"videodb://episodes/"
            else:
                return False
            target_file = None

    # 2) Show the directory in Videos
    if path_to_open.endswith(".xsp"):
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{path_to_open}",return)')
    else:
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{path_to_open}",return)')

    if not _wait_videos_on(path_to_open, timeout_ms=8000):
        logger.warning("Hijack: timed out opening native container")
        if path_to_open.endswith(".xsp"):
            _cleanup_xsp(path_to_open)
        return False

    # 3) Focus list, jump to the correct row if we can infer it
    if not focus_list(LIST_ID):
        logger.debug("Hijack: could not focus list; continuing")
    if path_to_open.endswith(".xsp"):
        focus_index = _find_index_in_dir_by_file(path_to_open, target_file)
        xbmc.executebuiltin(f"SetFocus({LIST_ID},{focus_index})")
        xbmc.sleep(120)

    # 4) Open native Info
    xbmc.executebuiltin("Action(Info)")
    ok = wait_until(lambda: xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)"), timeout_ms=1500, step_ms=50)
    if not ok:
        logger.warning("Hijack: native Info did not open")
        if path_to_open.endswith(".xsp"):
            _cleanup_xsp(path_to_open)
        return False

    # 5) Replace underlying container back to the original path (so Back works)
    if orig_path:
        xbmc.executebuiltin(f'Container.Update("{orig_path}",replace)')

    # 6) Cleanup
    if path_to_open.endswith(".xsp"):
        _cleanup_xsp(path_to_open)
    return True
```

4) New manager (tiny, tick-driven)

lib/ui/info_hijack_manager.py

```# -*- coding: utf-8 -*-
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
```

5) Wire it into your existing service (gated)
a) __init__: read setting and create the manager only if enabled

service.py → BackgroundService.__init__ (add lines marked ✨)

```        self.token_refresh_enabled = self.config.get_bool("background_token_refresh", True)

        # ✨ Gate: user setting to enable the hijack behavior
        self.info_hijack_enabled = self.config.get_bool("info_hijack_enabled", True)
        self._info_hijack = None
        if self.info_hijack_enabled:
            try:
                from lib.ui.info_hijack_manager import InfoHijackManager
                self._info_hijack = InfoHijackManager(logger=self.logger)
                self.logger.debug("InfoHijackManager initialized (enabled)")
            except Exception as e:
                self.logger.warning(f"Failed to init InfoHijackManager: {e}")
        else:
            self.logger.debug("Info hijack disabled by setting")
```

b) run(): replace the single long sleep with a short, tick-driven wait

Replace the final wait block in run():

BEFORE

```# Wait for next cycle or abort using proper Monitor method
if self.monitor.waitForAbort(current_interval):
    break
```

AFTER

```# Wait for next cycle, but poll quickly so Info hijack feels instant
waited = 0.0
step = 0.15  # 150 ms
while waited < current_interval and not self.monitor.abortRequested():
    # ✨ run the hijack tick only when enabled/available
    if self._info_hijack is not None:
        try:
            self._info_hijack.tick()
        except Exception as e:
            self.logger.debug(f"InfoHijack tick error: {e}")

    # use waitForAbort to be responsive to shutdowns
    remaining = max(0.0, current_interval - waited)
    if self.monitor.waitForAbort(min(step, remaining)):
        return
    waited += step
```
Token refresh / delta scan cadence remains the same (per current_interval), but you now also “idle-tick” the hijack manager ~6–7 times per second without threads.

6) That’s it — how it behaves

Setting ON (info_hijack_enabled=true):
When the user opens Info on one of your library rows, the service:

closes that (plugin) dialog,

jumps to a native library context (XSP by filename for items with files; videodb node for tvshows),

opens native Info (with full cast/crew),

immediately swaps the underlying container back to your original list so Back behaves perfectly.
Your list items stay rich; native Info stays native.

Setting OFF: service never installs the manager; nothing new happens.


