
# -*- coding: utf-8 -*-
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
        # tvshow has multiple files; we'll still open its videodb node below.
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
    # Common: (".." at 0) and our item at 1
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
    logger.info(f"HIJACK HELPER: 🎬 Starting native info process for {dbtype} {dbid}")
    logger.debug(f"HIJACK HELPER: Original path: {orig_path}")
    
    # 1) Close the plugin's Info dialog
    logger.debug("HIJACK HELPER: Step 1 - Closing plugin Info dialog")
    xbmc.executebuiltin("Action(Back)")
    closed = wait_until(lambda: not xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)"), 1200, 30)
    if not closed:
        logger.warning("HIJACK HELPER: Failed to close plugin Info dialog")
        return False
    logger.debug("HIJACK HELPER: Plugin Info dialog closed")

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
    logger.info(f"HIJACK HELPER: Step 2 - Opening Videos window with path: {path_to_open}")
    if path_to_open.endswith(".xsp"):
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{path_to_open}",return)')
        logger.debug("HIJACK HELPER: Used XSP path")
    else:
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{path_to_open}",return)')
        logger.debug("HIJACK HELPER: Used videodb path")

    if not _wait_videos_on(path_to_open, timeout_ms=8000):
        logger.warning("HIJACK HELPER: ⏰ Timed out opening native container")
        if path_to_open.endswith(".xsp"):
            _cleanup_xsp(path_to_open)
        return False
    logger.debug("HIJACK HELPER: Videos window opened successfully")

    # 3) Focus list, jump to the correct row if we can infer it
    if not focus_list(LIST_ID):
        logger.debug("Hijack: could not focus list; continuing")
    if path_to_open.endswith(".xsp"):
        focus_index = _find_index_in_dir_by_file(path_to_open, target_file)
        xbmc.executebuiltin(f"SetFocus({LIST_ID},{focus_index})")
        xbmc.sleep(120)

    # 4) Open native Info
    logger.debug("HIJACK HELPER: Step 4 - Opening native Info dialog")
    xbmc.executebuiltin("Action(Info)")
    ok = wait_until(lambda: xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)"), timeout_ms=1500, step_ms=50)
    if not ok:
        logger.warning("HIJACK HELPER: ❌ Native Info did not open")
        if path_to_open.endswith(".xsp"):
            _cleanup_xsp(path_to_open)
        return False
    logger.info("HIJACK HELPER: ✅ Native Info dialog opened")

    # 5) Replace underlying container back to the original path (so Back works)
    if orig_path:
        logger.debug(f"HIJACK HELPER: Step 5 - Restoring original container: {orig_path}")
        xbmc.executebuiltin(f'Container.Update("{orig_path}",replace)')
    else:
        logger.debug("HIJACK HELPER: No original path to restore")

    # 6) Cleanup
    if path_to_open.endswith(".xsp"):
        logger.debug("HIJACK HELPER: Step 6 - Cleaning up XSP file")
        _cleanup_xsp(path_to_open)
    
    logger.info(f"HIJACK HELPER: 🎉 Successfully completed hijack for {dbtype} {dbid}")
    return True
