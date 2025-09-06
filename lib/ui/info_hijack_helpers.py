# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import json
import time
import html
from typing import Optional

import xbmc
import xbmcgui
import xbmcvfs

from ..utils.logger import get_logger
from ..utils.kodi_version import get_version_specific_control_id
from .localization import L

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
        logger.debug(f"[InfoHijack] {message}")

def prewarm_smb(movie_url: Optional[str]):
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
    t_start = time.perf_counter()
    end = time.time() + (timeout_ms / 1000.0)
    mon = xbmc.Monitor()
    check_count = 0
    
    # Use adaptive polling - start fast, then slow down
    current_step_ms = min(step_ms, 30)  # Start with quick polls
    max_step_ms = max(step_ms, 200)     # Cap at reasonable interval

    while time.time() < end and not mon.abortRequested():
        check_count += 1
        if cond():
            t_end = time.perf_counter()
            _log(f"wait_until: SUCCESS after {check_count} checks ({t_end - t_start:.3f}s, timeout was {timeout_ms}ms)")
            return True
        
        xbmc.sleep(current_step_ms)
        
        # Gradually increase polling interval to reduce CPU overhead on slower devices
        if check_count > 5:  # After initial quick checks
            current_step_ms = min(current_step_ms + 10, max_step_ms)

    t_end = time.perf_counter()
    _log(f"wait_until: TIMEOUT after {check_count} checks ({t_end - t_start:.3f}s, timeout was {timeout_ms}ms)", xbmc.LOGWARNING)
    return False

def _wait_for_info_dialog(timeout=10.0):
    """
    Block until the DialogVideoInfo window is active and usable (not fully loaded).
    Uses earlier detection strategy - accepts dialog as soon as basic structure is present,
    rather than waiting for all metadata/images to finish loading.
    """
    t_start = time.perf_counter()
    end = time.time() + timeout
    check_count = 0
    scan_detected = False
    last_dialog_id = None
    last_busy_state = None
    dialog_first_detected = None

    _log(f"_wait_for_info_dialog: Starting EARLY DETECTION wait for info dialog with {timeout:.1f}s timeout")

    while time.time() < end:
        check_count += 1
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        # Check if Kodi is busy with file operations (subtitle scanning, metadata, etc.)
        is_busy = (
            xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)') or
            xbmc.getCondVisibility('Window.IsActive(DialogProgress.xml)') or
            xbmc.getCondVisibility('Player.HasMedia') or  # Sometimes media loading blocks dialog
            xbmc.getCondVisibility('System.HasModalDialog')
        )
        
        # Log when dialog ID or busy state changes
        if current_dialog_id != last_dialog_id or is_busy != last_busy_state:
            elapsed = time.perf_counter() - t_start
            _log(f"_wait_for_info_dialog: STATE CHANGE at {elapsed:.3f}s - dialog_id: {last_dialog_id}→{current_dialog_id}, busy: {last_busy_state}→{is_busy}")
            last_dialog_id = current_dialog_id
            last_busy_state = is_busy
        
        # Detect if we're in a scanning phase (helps explain delays)
        if is_busy and not scan_detected:
            scan_detected = True
            elapsed = time.perf_counter() - t_start
            _log(f"_wait_for_info_dialog: SCAN DETECTED at {elapsed:.3f}s - Kodi busy state (likely scanning for subtitles/metadata)")

        # More frequent logging during delays
        if check_count % 20 == 0 or (is_busy and check_count % 5 == 0):
            elapsed = time.perf_counter() - t_start
            _log(f"_wait_for_info_dialog: check #{check_count} ({elapsed:.1f}s) - dialog_id={current_dialog_id}, busy={is_busy}")

        # EARLY DETECTION: Dialog structure present
        if current_dialog_id in (12003, 10147):  # DialogVideoInfo / Fallback
            if dialog_first_detected is None:
                dialog_first_detected = time.perf_counter()
                elapsed_to_detection = dialog_first_detected - t_start
                _log(f"_wait_for_info_dialog: EARLY DETECTION - Dialog structure detected at {elapsed_to_detection:.3f}s")
            
            # Check if dialog is "usable" rather than "fully loaded"
            # Look for basic dialog elements being present, not complete metadata
            basic_title = xbmc.getInfoLabel('ListItem.Title')
            basic_label = xbmc.getInfoLabel('ListItem.Label')
            dialog_ready = bool(basic_title or basic_label)
            
            # Additional usability check - dialog controls should be responsive
            control_ready = not xbmc.getCondVisibility('System.HasModalDialog')
            
            elapsed_since_detected = time.perf_counter() - dialog_first_detected
            
            # Early acceptance criteria:
            # 1. Dialog structure is present (dialog_id matches)
            # 2. Basic content is available (title/label populated)
            # 3. Dialog is interactive (no modal blocking)
            # 4. Either not busy OR reasonable wait time has passed since detection
            early_accept = (
                dialog_ready and 
                control_ready and 
                (not is_busy or elapsed_since_detected > 0.2)  # Accept after 200ms even if still busy
            )
            
            if early_accept:
                t_end = time.perf_counter()
                _log(f"_wait_for_info_dialog: EARLY SUCCESS after {check_count} checks ({t_end - t_start:.3f}s) - dialog_id={current_dialog_id}")
                _log(f"_wait_for_info_dialog: Early acceptance criteria met - basic_content={dialog_ready}, interactive={control_ready}, wait_since_detect={elapsed_since_detected:.3f}s")
                if scan_detected:
                    _log(f"_wait_for_info_dialog: Dialog accepted while background scanning may still be active")
                return True
            else:
                # Log why we're not accepting yet
                if check_count % 10 == 0:  # Every 10th check when dialog is detected but not ready
                    _log(f"_wait_for_info_dialog: Dialog detected but not ready - basic_content={dialog_ready}, interactive={control_ready}, busy={is_busy}, wait_time={elapsed_since_detected:.3f}s")
            
        # Use adaptive sleep - very short when dialog detected, normal otherwise
        if dialog_first_detected:
            sleep_time = 20  # Fast polling once dialog structure is detected
        else:
            sleep_time = 30 if is_busy else 50  # Normal polling while waiting for dialog
        xbmc.sleep(sleep_time)

    t_end = time.perf_counter()
    final_dialog_id = xbmcgui.getCurrentWindowDialogId()
    final_busy = xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)')
    _log(f"_wait_for_info_dialog: TIMEOUT after {check_count} checks ({t_end - t_start:.3f}s) - final_dialog_id={final_dialog_id}, still_busy={final_busy}", xbmc.LOGWARNING)
    if dialog_first_detected:
        elapsed_detected = t_end - dialog_first_detected
        _log(f"_wait_for_info_dialog: Dialog was detected {elapsed_detected:.3f}s ago but never became usable", xbmc.LOGWARNING)
    if scan_detected:
        _log(f"_wait_for_info_dialog: Timeout occurred after file scanning was detected - this may indicate slow network storage", xbmc.LOGWARNING)
    return False

def focus_list(control_id: Optional[int] = None, tries: int = 20, step_ms: int = 30) -> bool:
    """Focus the main list control, trying version-specific control IDs"""
    t_focus_start = time.perf_counter()

    if control_id is None:
        control_id = get_version_specific_control_id()

    _log(f"focus_list: Starting with control_id={control_id}, tries={tries}")

    # Build list of control IDs to try in order
    # 55: v20/v21 Estuary default, 500: grid/panel views, 50/52: v19 compatibility
    all_control_ids = [control_id, 55, 500, 50, 52]
    # Remove duplicates while preserving order
    control_ids_to_try = []
    for cid in all_control_ids:
        if cid not in control_ids_to_try:
            control_ids_to_try.append(cid)

    # Calculate how many complete rounds we can do
    max_rounds = max(1, tries // len(control_ids_to_try))

    _log(f"Will try control IDs {control_ids_to_try} for up to {max_rounds} rounds")

    for round_num in range(max_rounds):
        _log(f"Starting round {round_num + 1}/{max_rounds}")

        for cid in control_ids_to_try:
            _log(f"Trying control ID {cid}")
            xbmc.executebuiltin(f"SetFocus({cid})")

            if xbmc.getCondVisibility(f"Control.HasFocus({cid})"):
                t_focus_end = time.perf_counter()
                _log(f"Successfully focused control {cid} on round {round_num + 1} (took {t_focus_end - t_focus_start:.3f}s)")
                return True

            xbmc.sleep(step_ms)

    t_focus_end = time.perf_counter()
    _log(f"Failed to focus any control after {max_rounds} rounds (tried {control_ids_to_try}) - total time: {t_focus_end - t_focus_start:.3f}s", xbmc.LOGWARNING)
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
        _log(f"Movie {dbid} file path: {file_path}")
        return file_path
    elif dbtype == "episode":
        data = jsonrpc("VideoLibrary.GetEpisodeDetails", {"episodeid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("episodedetails") or {}
        file_path = md.get("file")
        _log(f"Episode {dbid} file path: {file_path}")
        return file_path
    elif dbtype == "musicvideo":
        data = jsonrpc("VideoLibrary.GetMusicVideoDetails", {"musicvideoid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("musicvideodetails") or {}
        file_path = md.get("file")
        _log(f"MusicVideo {dbid} file path: {file_path}")
        return file_path
    elif dbtype == "tvshow":
        # tvshow has multiple files; we'll still open its videodb node below.
        return None
    return None

def _create_xsp_for_dbitem(db_type: str, db_id: int) -> Optional[str]:
    """
    Create XSP file that filters to a specific database item by ID.
    This creates a native Kodi list containing just the target item.
    """
    try:
        _log(f"Creating XSP for database item {db_type} {db_id}")
        
        # Get the actual file path from the database item
        file_path = _get_file_for_dbitem(db_type, db_id)
        if not file_path:
            _log(f"No file path found for {db_type} {db_id}", xbmc.LOGWARNING)
            return None
        
        filename = os.path.basename(file_path)
        filename_no_ext = os.path.splitext(filename)[0]
        _log(f"Creating XSP for {db_type} {db_id}: filename='{filename}', no_ext='{filename_no_ext}'")
        
        name = f"LG Hijack {db_type} {db_id}"
        
        if db_type.lower() == 'movie':
            # Create XSP that filters movies by filename
            xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
  <name>{html.escape(name)}</name>
  <match>all</match>
  <rule field="filename" operator="contains">
    <value>{html.escape(filename_no_ext)}</value>
  </rule>
  <order direction="ascending">title</order>
</smartplaylist>"""
        elif db_type.lower() == 'episode':
            # Create XSP that filters episodes by filename
            xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="episodes">
  <name>{html.escape(name)}</name>
  <match>all</match>
  <rule field="filename" operator="contains">
    <value>{html.escape(filename_no_ext)}</value>
  </rule>
  <order direction="ascending">title</order>
</smartplaylist>"""
        else:
            _log(f"Unsupported db_type for XSP creation: {db_type}", xbmc.LOGWARNING)
            return None
        
        # Use profile playlists path
        playlists_dir = "special://profile/playlists/video/"
        xsp_filename = f"lg_hijack_{db_type}_{db_id}.xsp"
        path = playlists_dir + xsp_filename
        
        # Ensure playlists directory exists
        try:
            if not xbmcvfs.exists(playlists_dir):
                _log(f"Creating playlists directory: {playlists_dir}")
                xbmcvfs.mkdirs(playlists_dir)
        except Exception as e:
            _log(f"Failed to create playlists directory: {e}", xbmc.LOGWARNING)
            # Fallback to temp
            path = f"special://temp/{xsp_filename}"
        
        # Log the XSP content for debugging
        _log(f"XSP content for {db_type} {db_id}:\n{xsp}")
        
        if _write_text(path, xsp):
            _log(f"XSP created successfully: {path}")
            return path
        else:
            _log(f"Failed to write XSP file: {path}", xbmc.LOGWARNING)
            return None
            
    except Exception as e:
        _log(f"Exception creating XSP for {db_type} {db_id}: {e}", xbmc.LOGERROR)
        return None

def _create_xsp_for_file(dbtype: str, dbid: int) -> Optional[str]:
    fp = _get_file_for_dbitem(dbtype, dbid)
    if not fp:
        _log(f"No file path found for {dbtype} {dbid}", xbmc.LOGWARNING)
        return None

    filename = os.path.basename(fp)
    # Remove file extension for XSP matching
    filename_no_ext = os.path.splitext(filename)[0]
    _log(f"Creating XSP for {dbtype} {dbid}: filename='{filename}', no_ext='{filename_no_ext}', full_path='{fp}'")

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
            _log(f"Creating playlists directory: {playlists_dir}")
            xbmcvfs.mkdirs(playlists_dir)
    except Exception as e:
        _log(f"Failed to create playlists directory: {e}", xbmc.LOGWARNING)
        # Fallback to temp
        path = f"special://temp/{xsp_filename}"

    # Log the raw XSP content for debugging
    _log(f"XSP RAW CONTENT for {dbtype} {dbid}:\n{xsp}")

    if _write_text(path, xsp):
        _log(f"XSP created successfully: {path} (filename='{filename}')")
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
    _log(f"XSP directory items count: {len(items)}")

    if not items:
        _log("No items found in XSP directory", xbmc.LOGWARNING)
        return 0

    # Simple logic: if first item is ".." parent, use index 1 (the movie)
    # Otherwise use index 0
    if len(items) >= 2 and items[0].get("file", "").endswith(".."):
        _log("XSP has parent item, using index 1 for movie")
        return 1
    else:
        _log("XSP has no parent item, using index 0 for movie")
        return 0

def _wait_videos_on(path: str, timeout_ms=8000) -> bool:
    t_start = time.perf_counter()
    t_norm = (path or "").rstrip('/')
    scan_warning_shown = False
    condition_met_count = 0
    last_condition_details = {}

    _log(f"_wait_videos_on: Starting wait for path '{t_norm}' with {timeout_ms}ms timeout")

    def check_condition():
        nonlocal condition_met_count, last_condition_details
        
        window_active = xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        folder_path = (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/')
        path_match = folder_path == t_norm
        num_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        not_busy = not xbmc.getCondVisibility("Window.IsActive(DialogBusy.xml)")
        
        # Additional check for progress dialogs that might appear during scanning
        not_scanning = not xbmc.getCondVisibility("Window.IsActive(DialogProgress.xml)")

        elapsed = time.perf_counter() - t_start
        
        # Track condition details for debugging
        current_details = {
            'window_active': window_active,
            'path_match': path_match,
            'folder_path': folder_path,
            'num_items': num_items,
            'not_busy': not_busy,
            'not_scanning': not_scanning
        }
        
        # Log when conditions change
        if current_details != last_condition_details:
            _log(f"_wait_videos_on CONDITION CHANGE at {elapsed:.3f}s: {current_details}")
            last_condition_details = current_details.copy()
        
        # Show scan warning after 3 seconds if still busy
        nonlocal scan_warning_shown
        if elapsed > 3.0 and (not not_busy or not not_scanning) and not scan_warning_shown:
            _log(f"_wait_videos_on: Kodi busy for {elapsed:.1f}s - likely scanning for associated files")
            scan_warning_shown = True
        
        # More frequent logging for debugging delays
        if int(elapsed * 2) % 3 == 0 and elapsed - int(elapsed * 2) / 2 < 0.05:  # Every 1.5 seconds
            _log(f"_wait_videos_on check ({elapsed:.1f}s): window={window_active}, path_match={path_match} ('{folder_path}' vs '{t_norm}'), items={num_items}, not_busy={not_busy}, not_scanning={not_scanning}")

        final_condition = window_active and path_match and num_items > 0 and not_busy and not_scanning
        if final_condition:
            condition_met_count += 1
            _log(f"_wait_videos_on: ALL CONDITIONS MET at {elapsed:.3f}s (count: {condition_met_count})")
        else:
            condition_met_count = 0

        return final_condition

    # Extended timeout for network storage scenarios
    _log(f"_wait_videos_on: Starting wait_until with {max(timeout_ms, 10000)}ms timeout")
    wait_start = time.perf_counter()
    result = wait_until(check_condition, timeout_ms=max(timeout_ms, 10000), step_ms=100)
    wait_end = time.perf_counter()
    t_end = time.perf_counter()

    _log(f"_wait_videos_on: wait_until completed in {wait_end - wait_start:.3f}s, result={result}")

    if result:
        _log(f"_wait_videos_on SUCCESS after {t_end - t_start:.3f}s")
        if scan_warning_shown:
            _log(f"_wait_videos_on: XSP loaded successfully after file scanning completed")
    else:
        _log(f"_wait_videos_on TIMEOUT after {t_end - t_start:.3f}s", xbmc.LOGWARNING)
        # Log final state for debugging
        final_window = xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        final_path = (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/')
        final_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        final_busy = xbmc.getCondVisibility("Window.IsActive(DialogBusy.xml)")
        final_progress = xbmc.getCondVisibility("Window.IsActive(DialogProgress.xml)")
        _log(f"_wait_videos_on FINAL STATE: window={final_window}, path='{final_path}', items={final_items}, busy={final_busy}, progress={final_progress}", xbmc.LOGWARNING)

    return result

def open_native_info_fast(db_type: str, db_id: int, logger) -> bool:
    """
    Proper hijack flow: Close current info dialog, navigate to native list, then open info.
    This ensures the video info gets full Kodi metadata population from native library.
    """
    try:
        overall_start_time = time.perf_counter()
        logger.info(f"🎬 HIJACK HELPERS: Starting hijack process for {db_type} {db_id}")
        
        # 🔒 SUBSTEP 1: Close any open dialog first
        substep1_start = time.perf_counter()
        logger.info(f"🔒 SUBSTEP 1: Checking for open dialogs to close")
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        if current_dialog_id in (12003, 10147):  # DialogVideoInfo or similar
            logger.info(f"SUBSTEP 1: Found open dialog ID {current_dialog_id}, closing it")
            xbmc.executebuiltin('Action(Back)')
            # Wait for dialog to close
            xbmc.sleep(200)
            # Verify dialog closed
            after_close_id = xbmcgui.getCurrentWindowDialogId()
            logger.info(f"✅ SUBSTEP 1 COMPLETE: Dialog closed (was {current_dialog_id}, now {after_close_id})")
        else:
            logger.info(f"✅ SUBSTEP 1 COMPLETE: No dialog to close (current dialog ID: {current_dialog_id})")
        substep1_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 1 TIMING: {substep1_end - substep1_start:.3f}s")
        
        # 📝 SUBSTEP 2: Create XSP file for single item to create a native list
        substep2_start = time.perf_counter()
        logger.info(f"📝 SUBSTEP 2: Creating XSP file for {db_type} {db_id}")
        start_xsp_time = time.perf_counter()
        xsp_path = _create_xsp_for_dbitem(db_type, db_id)
        end_xsp_time = time.perf_counter()
        
        if not xsp_path:
            logger.warning(f"❌ SUBSTEP 2 FAILED: Failed to create XSP for {db_type} {db_id}")
            return False
        logger.info(f"✅ SUBSTEP 2 COMPLETE: XSP created at {xsp_path} in {end_xsp_time - start_xsp_time:.3f}s")
        substep2_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 2 TIMING: {substep2_end - substep2_start:.3f}s")
        
        # 🧭 SUBSTEP 3: Navigate to the XSP (creates native Kodi list with single item)
        substep3_start = time.perf_counter()
        logger.info(f"🧭 SUBSTEP 3: Navigating to native list: {xsp_path}")
        current_window_before = xbmcgui.getCurrentWindowId()
        start_nav_time = time.perf_counter()
        logger.info(f"SUBSTEP 3 DEBUG: About to execute ActivateWindow command at {start_nav_time - overall_start_time:.3f}s")
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')
        activate_window_end = time.perf_counter()
        logger.info(f"SUBSTEP 3 DEBUG: ActivateWindow command executed in {activate_window_end - start_nav_time:.3f}s")
        
        # ⏳ SUBSTEP 4: Wait for the Videos window to load with our item
        substep4_start = time.perf_counter()
        logger.info(f"⏳ SUBSTEP 4: Waiting for Videos window to load with XSP content")
        wait_start = time.perf_counter()
        if not _wait_videos_on(xsp_path, timeout_ms=4000):
            wait_end = time.perf_counter()
            end_nav_time = time.perf_counter()
            current_window_after = xbmcgui.getCurrentWindowId()
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            logger.warning(f"❌ SUBSTEP 4 FAILED: Failed to load Videos window with XSP: {xsp_path} after {end_nav_time - start_nav_time:.3f}s")
            logger.warning(f"SUBSTEP 4 DEBUG: Window before={current_window_before}, after={current_window_after}, current_path='{current_path}'")
            logger.warning(f"⏱️ SUBSTEP 4 WAIT TIMING: {wait_end - wait_start:.3f}s")
            return False
        wait_end = time.perf_counter()
        end_nav_time = time.perf_counter()
        current_window_after = xbmcgui.getCurrentWindowId()
        current_path = xbmc.getInfoLabel("Container.FolderPath")
        num_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        logger.info(f"✅ SUBSTEP 4 COMPLETE: Videos window loaded in {end_nav_time - start_nav_time:.3f}s")
        logger.info(f"SUBSTEP 4 STATUS: Window {current_window_before}→{current_window_after}, path='{current_path}', items={num_items}")
        substep4_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 4 TIMING: {substep4_end - substep4_start:.3f}s (wait: {wait_end - wait_start:.3f}s)")
        logger.info(f"⏱️ SUBSTEP 3+4 COMBINED TIMING: {substep4_end - substep3_start:.3f}s")
        
        # 🎯 SUBSTEP 5: Focus the list and find our item
        substep5_start = time.perf_counter()
        logger.info(f"🎯 SUBSTEP 5: Focusing list to locate {db_type} {db_id}")
        start_focus_time = time.perf_counter()
        if not focus_list():
            end_focus_time = time.perf_counter()
            logger.warning(f"❌ SUBSTEP 5 FAILED: Failed to focus list control after {end_focus_time - start_focus_time:.3f}s")
            return False
        end_focus_time = time.perf_counter()
        logger.info(f"✅ SUBSTEP 5 COMPLETE: List focused in {end_focus_time - start_focus_time:.3f}s")
        substep5_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 5 TIMING: {substep5_end - substep5_start:.3f}s")
        
        # 📍 SUBSTEP 6: Check current item and navigate away from parent if needed
        substep6_start = time.perf_counter()
        logger.info(f"📍 SUBSTEP 6: Checking current item and navigating to movie")
        current_item_before = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
        current_item_label = xbmc.getInfoLabel('ListItem.Label')
        
        # Check if we're focused on the parent item ".."
        if current_item_label == ".." or current_item_label.strip() == "..":
            logger.info(f"SUBSTEP 6: Currently on parent item '{current_item_label}', navigating to next item")
            xbmc.executebuiltin('Action(Down)')  # Move to next item
            xbmc.sleep(150)  # Wait for navigation
            current_item_after = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
            new_label = xbmc.getInfoLabel('ListItem.Label')
            logger.info(f"SUBSTEP 6: Moved from parent item {current_item_before} to item {current_item_after}, new label: '{new_label}'")
        else:
            logger.info(f"SUBSTEP 6: Already on target item '{current_item_label}' at position {current_item_before}")
        
        # Verify we're now on the correct item
        final_item_label = xbmc.getInfoLabel('ListItem.Label')
        final_item_dbid = xbmc.getInfoLabel('ListItem.DBID')
        final_item_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
        
        if final_item_label == ".." or final_item_label.strip() == "..":
            logger.warning(f"❌ SUBSTEP 6 FAILED: Still on parent item after navigation attempt")
            return False
        
        logger.info(f"✅ SUBSTEP 6 COMPLETE: On target item - Position: {final_item_position}, Label: '{final_item_label}', DBID: {final_item_dbid}")
        substep6_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 6 TIMING: {substep6_end - substep6_start:.3f}s")
        
        # 🎬 SUBSTEP 7: Open info from the native list (this gets full metadata population)
        substep7_start = time.perf_counter()
        logger.info(f"🎬 SUBSTEP 7: Opening video info from native list")
        pre_info_dialog_id = xbmcgui.getCurrentWindowDialogId()
        start_info_time = time.perf_counter()
        logger.info(f"SUBSTEP 7 DEBUG: About to execute Action(Info) at {start_info_time - overall_start_time:.3f}s")
        xbmc.executebuiltin('Action(Info)')
        action_info_end = time.perf_counter()
        logger.info(f"SUBSTEP 7 DEBUG: Action(Info) command executed in {action_info_end - start_info_time:.3f}s")
        
        # ⌛ SUBSTEP 8: Wait for the native info dialog to appear
        substep8_start = time.perf_counter()
        logger.info(f"⌛ SUBSTEP 8: Waiting for native info dialog to appear (extended timeout for network storage)")
        dialog_wait_start = time.perf_counter()
        success = _wait_for_info_dialog(timeout=10.0)
        dialog_wait_end = time.perf_counter()
        end_info_time = time.perf_counter()
        post_info_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        if success:
            logger.info(f"✅ SUBSTEP 8 COMPLETE: Native info dialog opened in {end_info_time - start_info_time:.3f}s")
            logger.info(f"SUBSTEP 8 STATUS: Dialog ID changed from {pre_info_dialog_id} to {post_info_dialog_id}")
            logger.info(f"🎉 HIJACK HELPERS: ✅ Native info hijack completed successfully for {db_type} {db_id}")
        else:
            logger.warning(f"❌ SUBSTEP 8 FAILED: Failed to open native info after {end_info_time - start_info_time:.3f}s")
            logger.warning(f"SUBSTEP 8 DEBUG: Dialog ID remains {post_info_dialog_id} (was {pre_info_dialog_id})")
            logger.warning(f"💥 HIJACK HELPERS: ❌ Failed to open native info after hijack for {db_type} {db_id}")
        
        substep8_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 8 TIMING: {substep8_end - substep8_start:.3f}s (dialog wait: {dialog_wait_end - dialog_wait_start:.3f}s)")
        
        overall_end_time = time.perf_counter()
        logger.info(f"⏱️ OVERALL HIJACK TIMING: {overall_end_time - overall_start_time:.3f}s")
        logger.info(f"⏱️ TIMING BREAKDOWN: S1={substep1_end - substep1_start:.3f}s, S2={substep2_end - substep2_start:.3f}s, S3+4={substep4_end - substep3_start:.3f}s, S5={substep5_end - substep5_start:.3f}s, S6={substep6_end - substep6_start:.3f}s, S7+8={substep8_end - substep7_start:.3f}s")
            
        return success
    except Exception as e:
        logger.error(f"💥 HIJACK HELPERS: Exception in hijack process for {db_type} {db_id}: {e}")
        import traceback
        logger.error(f"HIJACK HELPERS: Traceback: {traceback.format_exc()}")
        return False

def restore_container_after_close(orig_path: str, position_str: str, logger) -> bool:
    """
    Restore the container to the original plugin path after native info closes.
    This happens AFTER the dialog closes to avoid competing with Kodi.
    """
    if not orig_path:
        _log("No original path to restore to")
        return False

    try:
        position = int(position_str) if position_str else 0
    except (ValueError, TypeError):
        position = 0

    _log(f"Restoring container to: {orig_path} (position: {position})")

    # Reduced delay for faster response, but still safe
    xbmc.sleep(50)

    # Restore the container
    xbmc.executebuiltin(f'Container.Update("{orig_path}",replace)')

    # Extended timeout for slower hardware, but less frequent polling
    t_start = time.perf_counter()
    updated = wait_until(
        lambda: (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/') == orig_path.rstrip('/'),
        timeout_ms=6000,  # Extended timeout for slower devices
        step_ms=150       # Less frequent polling to reduce overhead
    )

    if updated and position > 0:
        # Restore position with minimal delay
        _log(f"Restoring list position to: {position}")
        xbmc.sleep(25)  # Reduced delay
        xbmc.executebuiltin(f'Action(SelectItem,{position})')

    t_end = time.perf_counter()
    _log(f"Container restore completed in {t_end - t_start:.3f}s, success: {updated}")

    return updated

def open_native_info(dbtype: str, dbid: int, logger, orig_path: str) -> bool:
    """
    Legacy function - now uses the fast approach for consistency.
    Close current dialog, open native info fast, then restore container immediately.
    """
    # Save current position
    current_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')

    # Use fast native info opening
    ok = open_native_info_fast(dbtype, dbid, logger)
    if not ok:
        return False

    # Immediately restore container (legacy behavior)
    if orig_path:
        # Brief delay to allow native info to fully open
        xbmc.sleep(200)
        return restore_container_after_close(orig_path, str(current_position), logger)

    return True

def open_movie_info(dbid: int, movie_url: Optional[str] = None, xsp_path: Optional[str] = None) -> bool:
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
            _log(f"🎉 Successfully completed hijack for movie {dbid}")
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