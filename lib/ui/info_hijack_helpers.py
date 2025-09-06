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

def _wait_for_listitem_hydration(timeout_ms=3000, logger=None) -> bool:
    """
    Wait for Kodi to fully hydrate the focused ListItem with metadata from the database.
    
    This prevents opening the info dialog before Kodi has populated fields like Genre,
    which would result in blank metadata in the native dialog.
    
    Args:
        timeout_ms: Maximum time to wait in milliseconds
        logger: Logger instance for detailed logging
        
    Returns:
        bool: True if hydration detected, False if timeout
    """
    start_time = time.perf_counter()
    check_interval = 0.1  # 100ms checks - less aggressive but more thorough
    check_count = 0
    
    # Log function for consistent formatting
    def log_msg(message, level="debug"):
        if logger:
            if level == "warning":
                logger.warning(f"GENRE HYDRATION: {message}")
            else:
                logger.info(f"GENRE HYDRATION: {message}")
        else:
            _log(f"GENRE HYDRATION: {message}")
    
    log_msg(f"Starting Genre-focused hydration wait with {timeout_ms}ms timeout")
    
    end_time = time.time() + (timeout_ms / 1000.0)
    
    # Track initial state
    initial_dbid = xbmc.getInfoLabel('ListItem.DBID')
    initial_genre = xbmc.getInfoLabel('ListItem.Genre')
    initial_title = xbmc.getInfoLabel('ListItem.Title')
    
    log_msg(f"Initial state: DBID='{initial_dbid}', Title='{initial_title}', Genre='{initial_genre}'")
    
    # Define comprehensive list of Genre sources to check
    genre_sources = [
        ('ListItem.Genre', 'Standard Genre'),
        ('ListItem.Property(Genre)', 'Property Genre'),
        ('ListItem.Property(genre)', 'Property genre (lowercase)'),
        ('ListItem.Property(genrelist)', 'Property genrelist'),
        ('ListItem.Property(genres)', 'Property genres'),
        ('Container.ListItem.Genre', 'Container ListItem Genre'),
        ('Container(50).ListItem.Genre', 'Container 50 Genre'),
        ('Container(55).ListItem.Genre', 'Container 55 Genre'),
        ('VideoPlayer.Genre', 'VideoPlayer Genre'),
    ]
    
    while time.time() < end_time:
        check_count += 1
        
        # Get core metadata
        current_dbid = xbmc.getInfoLabel('ListItem.DBID')
        current_dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
        current_title = xbmc.getInfoLabel('ListItem.Title')
        current_duration = xbmc.getInfoLabel('ListItem.Duration')
        
        # Comprehensive Genre check
        found_genre = None
        genre_source_used = None
        
        for source_path, source_name in genre_sources:
            try:
                genre_value = xbmc.getInfoLabel(source_path)
                if genre_value and genre_value.strip() and genre_value.strip().lower() not in ('', 'none', 'unknown'):
                    found_genre = genre_value.strip()
                    genre_source_used = source_name
                    break
            except:
                continue
        
        elapsed = time.perf_counter() - start_time
        
        # More frequent logging for Genre debugging
        if check_count <= 10 or check_count % 5 == 0:
            if found_genre:
                log_msg(f"Check #{check_count} ({elapsed:.3f}s): ✅ GENRE FOUND via {genre_source_used}: '{found_genre}'")
            else:
                log_msg(f"Check #{check_count} ({elapsed:.3f}s): ❌ No Genre found - DBID='{current_dbid}', Title='{current_title}', Duration='{current_duration}'")
        
        # Validation checks
        has_dbid = current_dbid and current_dbid != "0" and current_dbid.strip()
        has_genre = bool(found_genre)
        has_dbtype = current_dbtype and current_dbtype.strip()
        has_title = current_title and current_title.strip()
        has_duration = current_duration and current_duration.strip()
        
        # PRIMARY SUCCESS: We have Genre + core metadata
        if has_dbid and has_genre and has_dbtype:
            elapsed_final = time.perf_counter() - start_time
            log_msg(f"🎉 SUCCESS: Complete hydration WITH Genre after {check_count} checks ({elapsed_final:.3f}s)")
            log_msg(f"Final metadata: DBID={current_dbid}, Genre='{found_genre}' (via {genre_source_used}), DBType='{current_dbtype}', Title='{current_title}'")
            return True
        
        # If we've waited 2+ seconds and have core metadata but no Genre, investigate further
        if elapsed > 2.0 and has_dbid and has_dbtype and not has_genre:
            log_msg(f"⚠️ GENRE INVESTIGATION: After {elapsed:.1f}s, no Genre found despite DBID={current_dbid}, DBType={current_dbtype}")
            
            # Try a JSON-RPC query to see if Genre exists in database
            try:
                if current_dbtype.lower() == 'movie':
                    result = jsonrpc("VideoLibrary.GetMovieDetails", {
                        "movieid": int(current_dbid), 
                        "properties": ["genre", "title"]
                    })
                    db_movie = result.get("result", {}).get("moviedetails", {})
                    db_genre = db_movie.get("genre", [])
                    db_title = db_movie.get("title", "")
                    
                    if db_genre:
                        if isinstance(db_genre, list):
                            db_genre_str = ", ".join(db_genre)
                        else:
                            db_genre_str = str(db_genre)
                        log_msg(f"💾 DATABASE CHECK: Movie {current_dbid} '{db_title}' HAS Genre in DB: '{db_genre_str}'")
                    else:
                        log_msg(f"💾 DATABASE CHECK: Movie {current_dbid} '{db_title}' has NO Genre in database")
            except Exception as e:
                log_msg(f"💾 DATABASE CHECK failed: {e}")
        
        # Extended wait for Genre - only give up after full timeout
        if elapsed < (timeout_ms / 1000.0) - 0.1:  # Continue until near timeout
            xbmc.sleep(int(check_interval * 1000))
            continue
        
        # TIMEOUT: Final decision
        if has_dbid and has_dbtype and has_title:
            elapsed_final = time.perf_counter() - start_time
            log_msg(f"⏰ TIMEOUT: Proceeding without Genre after {elapsed_final:.3f}s - Core metadata present", "warning")
            log_msg(f"Final state: DBID={current_dbid}, DBType={current_dbtype}, Title='{current_title}', Duration='{current_duration}', Genre=MISSING", "warning")
            return True
        else:
            break
    
    # Complete failure
    elapsed_final = time.perf_counter() - start_time
    log_msg(f"❌ CRITICAL TIMEOUT after {check_count} checks ({elapsed_final:.3f}s)", "warning")
    log_msg(f"Missing core metadata - DBID: {bool(has_dbid)}, DBType: {bool(has_dbtype)}, Title: {bool(has_title)}", "warning")
    
    return False

def _wait_for_info_dialog(timeout=10.0):
    """
    Block until the DialogVideoInfo window is active (skin dep. but standard on Kodi 19+).
    Extended timeout and better handling for subtitle/metadata scanning delays.
    """
    t_start = time.perf_counter()
    end = time.time() + timeout
    check_count = 0
    scan_detected = False
    last_dialog_id = None
    last_busy_state = None

    _log(f"_wait_for_info_dialog: Starting wait for info dialog with {timeout:.1f}s timeout")

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

        if current_dialog_id in (12003, 10147):  # DialogVideoInfo / Fallback
            t_end = time.perf_counter()
            _log(f"_wait_for_info_dialog: SUCCESS after {check_count} checks ({t_end - t_start:.3f}s) - dialog_id={current_dialog_id}")
            if scan_detected:
                _log(f"_wait_for_info_dialog: Dialog opened after file scanning completed")
            return True
            
        # Use adaptive sleep - shorter during scanning, longer when stable
        sleep_time = 30 if is_busy else 50
        xbmc.sleep(sleep_time)

    t_end = time.perf_counter()
    final_dialog_id = xbmcgui.getCurrentWindowDialogId()
    final_busy = xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)')
    _log(f"_wait_for_info_dialog: TIMEOUT after {check_count} checks ({t_end - t_start:.3f}s) - final_dialog_id={final_dialog_id}, still_busy={final_busy}", xbmc.LOGWARNING)
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
    Uses database ID filtering for complete metadata population including Genre.
    """
    try:
        _log(f"Creating XSP for database item {db_type} {db_id}")
        
        name = f"LG Hijack {db_type} {db_id}"
        
        if db_type.lower() == 'movie':
            # Create XSP that filters movies by database ID - this ensures full metadata
            xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
  <name>{html.escape(name)}</name>
  <match>all</match>
  <rule field="playcount" operator="greaterthan">
    <value>-1</value>
  </rule>
  <rule field="inprogress" operator="false">
    <value></value>
  </rule>
  <order direction="ascending">title</order>
  <limit>1000</limit>
</smartplaylist>"""
            # Note: We can't directly filter by movieid in XSP, so we use a broad filter
            # and rely on navigation to the correct item after the list loads
            
        elif db_type.lower() == 'episode':
            # Create XSP that filters episodes by database approach
            xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="episodes">
  <name>{html.escape(name)}</name>
  <match>all</match>
  <rule field="playcount" operator="greaterthan">
    <value>-1</value>
  </rule>
  <order direction="ascending">title</order>
  <limit>1000</limit>
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
    Alternative approach: Use direct JSON-RPC GUI.ActivateWindow call to open info dialog.
    This bypasses XSP navigation entirely and opens info directly from database.
    """
    try:
        overall_start_time = time.perf_counter()
        logger.info(f"🎬 HIJACK HELPERS: Starting direct info dialog approach for {db_type} {db_id}")
        
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
        
        # 🎯 SUBSTEP 2: Direct JSON-RPC approach to open info dialog with database item
        substep2_start = time.perf_counter()
        logger.info(f"🎯 SUBSTEP 2: Opening info dialog directly via JSON-RPC for {db_type} {db_id}")
        
        try:
            if db_type.lower() == 'movie':
                # Use JSON-RPC to open movie info directly
                result = jsonrpc("GUI.ActivateWindow", {
                    "window": "movieinformation",
                    "parameters": [f"videodb://movies/titles/{db_id}"]
                })
                logger.info(f"SUBSTEP 2: JSON-RPC result: {result}")
            elif db_type.lower() == 'episode':
                # Use JSON-RPC to open episode info directly  
                result = jsonrpc("GUI.ActivateWindow", {
                    "window": "episodeinformation", 
                    "parameters": [f"videodb://tvshows/episodes/{db_id}"]
                })
                logger.info(f"SUBSTEP 2: JSON-RPC result: {result}")
            else:
                logger.warning(f"❌ SUBSTEP 2 FAILED: Unsupported db_type: {db_type}")
                return False
                
        except Exception as json_rpc_error:
            logger.warning(f"SUBSTEP 2: JSON-RPC approach failed: {json_rpc_error}, falling back to XSP method")
            # Fallback to XSP approach if JSON-RPC fails
            return _fallback_xsp_approach(db_type, db_id, logger, overall_start_time)
        
        substep2_end = time.perf_counter() 
        logger.info(f"⏱️ SUBSTEP 2 TIMING: {substep2_end - substep2_start:.3f}s")
        
        # ⌛ SUBSTEP 3: Wait for the info dialog to appear
        substep3_start = time.perf_counter()
        logger.info(f"⌛ SUBSTEP 3: Waiting for direct info dialog to appear")
        success = _wait_for_info_dialog(timeout=8.0)
        substep3_end = time.perf_counter()
        
        if success:
            post_info_dialog_id = xbmcgui.getCurrentWindowDialogId()
            logger.info(f"✅ SUBSTEP 3 COMPLETE: Direct info dialog opened - Dialog ID: {post_info_dialog_id}")
            logger.info(f"🎉 HIJACK HELPERS: ✅ Direct info approach completed successfully for {db_type} {db_id}")
        else:
            logger.warning(f"❌ SUBSTEP 3 FAILED: Failed to open direct info dialog")
            logger.warning(f"💥 HIJACK HELPERS: ❌ Failed direct info approach for {db_type} {db_id}")
        
        logger.info(f"⏱️ SUBSTEP 3 TIMING: {substep3_end - substep3_start:.3f}s")
        overall_end_time = time.perf_counter()
        logger.info(f"⏱️ OVERALL DIRECT TIMING: {overall_end_time - overall_start_time:.3f}s")
            
        return success
    except Exception as e:
        logger.error(f"💥 HIJACK HELPERS: Exception in direct info approach for {db_type} {db_id}: {e}")
        import traceback
        logger.error(f"HIJACK HELPERS: Traceback: {traceback.format_exc()}")
        return False

def _fallback_xsp_approach(db_type: str, db_id: int, logger, overall_start_time: float) -> bool:
    """
    Fallback to XSP approach if direct JSON-RPC fails
    """
    logger.info(f"🔄 FALLBACK: Switching to XSP approach for {db_type} {db_id}")
    
    # Continue with original XSP logic...
        
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
        
        # 💧 SUBSTEP 6.5: HYDRATION WAIT - Wait for Kodi to populate metadata on focused item
        substep6_5_start = time.perf_counter()
        logger.info(f"💧 SUBSTEP 6.5: HYDRATION WAIT - Waiting for Kodi to populate ListItem metadata")
        
        hydration_success = _wait_for_listitem_hydration(timeout_ms=800, logger=logger)
        
        substep6_5_end = time.perf_counter()
        if hydration_success:
            logger.info(f"✅ SUBSTEP 6.5 COMPLETE: ListItem metadata hydrated in {substep6_5_end - substep6_5_start:.3f}s")
        else:
            logger.warning(f"⚠️ SUBSTEP 6.5 TIMEOUT: ListItem metadata not fully hydrated after {substep6_5_end - substep6_5_start:.3f}s - proceeding anyway")
        logger.info(f"⏱️ SUBSTEP 6.5 TIMING: {substep6_5_end - substep6_5_start:.3f}s")
        
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
        logger.info(f"⏱️ TIMING BREAKDOWN: S1={substep1_end - substep1_start:.3f}s, S2={substep2_end - substep2_start:.3f}s, S3+4={substep4_end - substep3_start:.3f}s, S5={substep5_end - substep5_start:.3f}s, S6={substep6_end - substep6_start:.3f}s, S6.5={substep6_5_end - substep6_5_start:.3f}s, S7+8={substep8_end - substep7_start:.3f}s")
            
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