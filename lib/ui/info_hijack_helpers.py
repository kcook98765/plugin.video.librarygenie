# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, time, html
from typing import Optional

import xbmc
import xbmcgui
import xbmcvfs

from ..utils.logger import get_logger

logger = get_logger(__name__)

LOG_PREFIX = "[LG.Hijack]"
LIST_ID = 50
VIDEOS_WINDOW = "MyVideoNav.xml"

def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    """Internal logging with consistent prefix"""
    if level == xbmc.LOGWARNING:
        logger.warning(f"[InfoHijack] {message}")
    elif level == xbmc.LOGERROR:
        logger.error(f"[InfoHijack] {message}")
    else:
        logger.info(f"[InfoHijack] {message}")

def prewarm_smb(movie_url):
    """
    Cheaply 'touch' the movie's parent SMB folder to wake disks and warm
    directory metadata so Kodi's associated-items scan doesn't stall later.
    """
    try:
        # Expect smb://host/share/path/file.ext
        if not movie_url or "://" not in movie_url:
            return 0.0
        t0 = time.perf_counter()
        # Parent directory (ensure trailing slash for some backends)
        parent = movie_url.rsplit('/', 1)[0] + '/'
        # Minimal filesystem calls that don't copy data
        xbmcvfs.listdir(parent)     # enumerate once to warm directory
        xbmcvfs.exists(movie_url)   # stat the movie file path
        # A tiny sleep helps some NASes finish spinup without busy-waiting
        time.sleep(0.10)
        dt = time.perf_counter() - t0
        _log(f"⏩ Prewarm SMB: parent='{parent}' took {dt:.3f}s")
        return dt
    except Exception as e:
        _log(f"⏩ Prewarm SMB skipped due to error: {e!r}", xbmc.LOGWARNING)
        return 0.0

def _get_list_control_id() -> int:
    """Get the correct list control ID based on Kodi version"""
    try:
        build_version = xbmc.getInfoLabel("System.BuildVersion")
        major = int(build_version.split('.')[0].split('-')[0])

        if major >= 20:
            # Kodi v20/v21 Estuary uses control ID 55 as default main list
            return 55
        else:
            # Kodi v19 uses control ID 50
            return 50
    except Exception:
        return 50  # Fallback to v19 behavior

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

def _wait_for_info_dialog(timeout=6.0):
    """
    Block until the DialogVideoInfo window is active (skin dep. but standard on Kodi 19+).
    """
    end = time.time() + timeout
    while time.time() < end:
        if xbmcgui.getCurrentWindowDialogId() in (12003, 10147):  # DialogVideoInfo / Fallback
            return True
        xbmc.sleep(50)
    return False

def focus_list(control_id: int = None, tries: int = 20, step_ms: int = 30) -> bool:
    """Focus the main list control, trying version-specific control IDs"""
    if control_id is None:
        control_id = _get_list_control_id()

    # Try the specified control ID first
    for _ in range(tries // 2):
        xbmc.executebuiltin(f"SetFocus({control_id})")
        if xbmc.getCondVisibility(f"Control.HasFocus({control_id})"):
            _log(f"Successfully focused control {control_id}", xbmc.LOGINFO)
            return True
        xbmc.sleep(step_ms)

    # If that failed, try alternative control IDs
    # 55: v20/v21 Estuary default, 500: grid/panel views, 50/52: v19 compatibility
    alternative_ids = [55, 500, 50, 52]  # Proper control IDs based on version/skin
    if control_id in alternative_ids:
        alternative_ids.remove(control_id)

    for alt_id in alternative_ids:
        _log(f"Trying alternative control ID {alt_id}", xbmc.LOGINFO)
        for _ in range(5):  # Fewer tries per alternative
            xbmc.executebuiltin(f"SetFocus({alt_id})")
            if xbmc.getCondVisibility(f"Control.HasFocus({alt_id})"):
                _log(f"Successfully focused alternative control {alt_id}", xbmc.LOGINFO)
                return True
            xbmc.sleep(step_ms)

    _log(f"Failed to focus any control (tried {control_id}, {alternative_ids})", xbmc.LOGWARNING)
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
        file_path = md.get("file")
        _log(f"Movie {dbid} file path: {file_path}", xbmc.LOGINFO)
        return file_path
    elif dbtype == "episode":
        data = jsonrpc("VideoLibrary.GetEpisodeDetails", {"episodeid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("episodedetails") or {}
        file_path = md.get("file")
        _log(f"Episode {dbid} file path: {file_path}", xbmc.LOGINFO)
        return file_path
    elif dbtype == "musicvideo":
        data = jsonrpc("VideoLibrary.GetMusicVideoDetails", {"musicvideoid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("musicvideodetails") or {}
        file_path = md.get("file")
        _log(f"MusicVideo {dbid} file path: {file_path}", xbmc.LOGINFO)
        return file_path
    elif dbtype == "tvshow":
        # tvshow has multiple files; we'll still open its videodb node below.
        return None
    return None

def _create_xsp_for_file(dbtype: str, dbid: int) -> Optional[str]:
    fp = _get_file_for_dbitem(dbtype, dbid)
    if not fp:
        _log(f"No file path found for {dbtype} {dbid}", xbmc.LOGWARNING)
        return None

    filename = os.path.basename(fp)
    # Remove file extension for XSP matching
    filename_no_ext = os.path.splitext(filename)[0]
    _log(f"Creating XSP for {dbtype} {dbid}: filename='{filename}', no_ext='{filename_no_ext}', full_path='{fp}'", xbmc.LOGINFO)

    name = f"LG Native Info {dbtype} {dbid}"

    # Use 'contains' operator for more robust filename matching
    # This handles cases where the database stores full paths vs just filenames
    xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
  <name>{html.escape(name)}</name>
  <match>all</match>
  <rule field="filename" operator="contains">
    <value>{html.escape(filename_no_ext)}</value>
  </rule>
  <order direction="ascending">title</order>
</smartplaylist>"""

    # Use profile playlists path with generic filename (persistent for debugging)
    playlists_dir = "special://profile/playlists/video/"
    xsp_filename = "lg_hijack_debug.xsp"
    path = playlists_dir + xsp_filename

    # Ensure playlists directory exists
    try:
        if not xbmcvfs.exists(playlists_dir):
            _log(f"Creating playlists directory: {playlists_dir}", xbmc.LOGINFO)
            xbmcvfs.mkdirs(playlists_dir)
    except Exception as e:
        _log(f"Failed to create playlists directory: {e}", xbmc.LOGWARNING)
        # Fallback to temp
        path = f"special://temp/{xsp_filename}"

    # Log the raw XSP content for debugging
    _log(f"XSP RAW CONTENT for {dbtype} {dbid}:\n{xsp}", xbmc.LOGINFO)

    if _write_text(path, xsp):
        _log(f"XSP created successfully: {path} (filename='{filename}')", xbmc.LOGINFO)
        return path
    else:
        _log(f"Failed to write XSP file: {path}", xbmc.LOGWARNING)
        return None

# XSP cleanup removed - using persistent generic filename for debugging

def _find_index_in_dir_by_file(directory: str, target_file: Optional[str]) -> int:
    """Simplified: assume movie is only match, just skip parent if present"""
    data = jsonrpc("Files.GetDirectory", {
        "directory": directory, "media": "video",
        "properties": ["file", "title", "thumbnail"]
    })
    items = (data.get("result") or {}).get("files") or []
    _log(f"XSP directory items count: {len(items)}", xbmc.LOGINFO)

    if not items:
        _log("No items found in XSP directory", xbmc.LOGWARNING)
        return 0

    # Simple logic: if first item is ".." parent, use index 1 (the movie)
    # Otherwise use index 0
    if len(items) >= 2 and items[0].get("file", "").endswith(".."):
        _log("XSP has parent item, using index 1 for movie", xbmc.LOGINFO)
        return 1
    else:
        _log("XSP has no parent item, using index 0 for movie", xbmc.LOGINFO)
        return 0

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
    focus row, open Info. Uses 'return' parameter to preserve navigation stack.
    """
    logger.info(f"HIJACK HELPER: 🎬 Starting native info process for {dbtype} {dbid}")
    logger.debug(f"HIJACK HELPER: Original path: {orig_path}")
    
    # Log current navigation state for debugging
    current_window = xbmc.getInfoLabel("System.CurrentWindow")
    current_container = xbmc.getInfoLabel("Container.FolderPath")
    logger.debug(f"HIJACK HELPER: Pre-hijack state - Window: {current_window}, Container: {current_container}")

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
        logger.info(f"HIJACK HELPER: Using videodb path for tvshow: {path_to_open}")
    else:
        # Use XSP for items with files (movies, episodes, musicvideos)
        xsp = _create_xsp_for_file(dbtype, dbid)
        if not xsp:
            logger.warning(f"HIJACK HELPER: XSP creation failed for {dbtype} {dbid}")
            return False

        path_to_open = xsp
        target_file = _get_file_for_dbitem(dbtype, dbid)
        logger.info(f"HIJACK HELPER: Using XSP path: {path_to_open}")

    # 2) Show the directory in Videos
    logger.info(f"HIJACK HELPER: Step 2 - Opening Videos window with path: {path_to_open}")
    xbmc.executebuiltin(f'ActivateWindow(Videos,"{path_to_open}",return)')
    logger.debug(f"HIJACK HELPER: Opened Videos window with {'XSP' if path_to_open.endswith('.xsp') else 'videodb'} path")

    if not _wait_videos_on(path_to_open, timeout_ms=8000):
        logger.warning("HIJACK HELPER: ⏰ Timed out opening native container")
        return False
    logger.debug("HIJACK HELPER: Videos window opened successfully")

    # 3) Focus list, jump to the correct row if we can infer it
    logger.debug("HIJACK HELPER: Step 3 - Focusing list and finding item")
    if not focus_list():  # Let focus_list determine the correct control ID
        logger.warning("HIJACK HELPER: Could not focus list control")
        return False

    if path_to_open.startswith("videodb://"):
        # For direct videodb paths: the item should be auto-focused
        logger.debug("HIJACK HELPER: Direct videodb path opened, item should be auto-focused")
        current_label = xbmc.getInfoLabel('ListItem.Label')
        current_dbid = xbmc.getInfoLabel('ListItem.DBID')
        logger.debug(f"HIJACK HELPER: Videodb focus - Label='{current_label}', DBID='{current_dbid}'")
    elif path_to_open.endswith(".xsp"):
        # For XSP: check focused item and navigate only if needed
        logger.debug("HIJACK HELPER: XSP opened, checking focused item")

        current_label = xbmc.getInfoLabel('ListItem.Label')
        current_dbid = xbmc.getInfoLabel('ListItem.DBID')
        logger.debug(f"HIJACK HELPER: Initial focus - Label='{current_label}', DBID='{current_dbid}'")

        # Only navigate if we're on the parent ".." item
        if current_label == ".." or not current_dbid or current_dbid == "0":
            logger.debug("HIJACK HELPER: On parent item, navigating down to content")
            xbmc.executebuiltin("Action(Down)")
            xbmc.sleep(50)  # Minimal delay

            # Verify navigation result
            final_label = xbmc.getInfoLabel('ListItem.Label')
            final_dbid = xbmc.getInfoLabel('ListItem.DBID')
            logger.debug(f"HIJACK HELPER: After navigation - Label='{final_label}', DBID='{final_dbid}'")
        else:
            logger.debug("HIJACK HELPER: Already on content item, no navigation needed")

    # 4) Open native Info
    logger.debug("HIJACK HELPER: Step 4 - Opening native Info dialog")
    xbmc.executebuiltin("Action(Info)")
    ok = wait_until(lambda: xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)"), timeout_ms=1500, step_ms=50)
    if not ok:
        logger.warning("HIJACK HELPER: ❌ Native Info did not open")
        return False
    logger.info("HIJACK HELPER: ✅ Native Info dialog opened")

    # 5) DO NOT replace container - let natural Back behavior work
    # The "return" parameter in ActivateWindow ensures Back will pop the Videos window
    # and return to the original plugin list naturally
    logger.debug("HIJACK HELPER: Hijack complete - letting natural Back navigation work")

    logger.info(f"HIJACK HELPER: 🎉 Successfully completed hijack for {dbtype} {dbid}")
    return True

def open_movie_info(dbid: int, movie_url: str = None, xsp_path: str = None) -> bool:
    """
    Open native Kodi movie info dialog for specified movie

    Args:
        dbid: Kodi database ID for the movie
        movie_url: Optional movie file URL for context
        xsp_path: Optional XSP file path to use

    Returns:
        bool: True if info dialog opened successfully
    """
    try:
        _log(f"Opening movie info for dbid={dbid}, url={movie_url}")

        if not xsp_path:
            xsp_path = f"/tmp/temp_movie_{dbid}.xsp"

        _log(f"Using XSP path: {xsp_path}")

        # -------- precise timings --------
        t_total0 = time.perf_counter()
        t0 = time.perf_counter()
        dt_prewarm = prewarm_smb(movie_url) if movie_url else 0.0
        t1 = time.perf_counter()
        _log(f"Opening Videos window with path: {xsp_path} "
             f"(prewarm {dt_prewarm:.3f}s, t+{t1 - t_total0:.3f}s)")

        # Open the Videos window on the XSP and focus the list
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')

        # Wait for control to exist & focus it
        t_focus0 = time.perf_counter()
        focused = focus_list()
        t_focus1 = time.perf_counter()
        if not focused:
            _log(f"Failed to focus control (focus wait {(t_focus1 - t_focus0):.3f}s)", xbmc.LOGWARNING)
            return False

        # We reached the point where the native dialog should pop; block until it does
        t_dialog0 = time.perf_counter()
        opened = _wait_for_info_dialog()
        t_dialog1 = time.perf_counter()

        if opened:
            _log(f"✅ Native Info dialog opened "
                 f"(open_window {(t_focus0 - t1):.3f}s, focus {(t_focus1 - t_focus0):.3f}s, "
                 f"dialog_wait {(t_dialog1 - t_dialog0):.3f}s, total {(t_dialog1 - t_total0):.3f}s)")
            _log(f"🎉 Successfully completed hijack for movie {dbid} - Back navigation preserved")
            return True
        else:
            _log(f"❌ Failed to open native info for movie {dbid} "
                 f"(open_window {(t_focus0 - t1):.3f}s, focus {(t_focus1 - t_focus0):.3f}s, "
                 f"dialog_wait {(t_dialog1 - t_dialog0):.3f}s, total {(t_dialog1 - t_total0):.3f}s)", 
                 xbmc.LOGWARNING)
            return False

    except Exception as e:
        _log(f"Failed to open movie info: {e}", xbmc.LOGERROR)
        return False