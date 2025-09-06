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

def _wait_for_listitem_hydration(timeout_ms=2000, logger=None) -> bool:
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
    check_interval = 0.05  # 50ms checks for responsive detection
    check_count = 0
    
    # Log function for consistent formatting
    def log_msg(message, level="info"):
        if logger:
            if level == "warning":
                logger.warning(f"HYDRATION WAIT: {message}")
            else:
                logger.info(f"HYDRATION WAIT: {message}")
        else:
            _log(f"HYDRATION WAIT: {message}")
    
    log_msg(f"Starting hydration wait with {timeout_ms}ms timeout")
    
    end_time = time.time() + (timeout_ms / 1000.0)
    
    # Track initial state to detect changes
    initial_dbid = xbmc.getInfoLabel('ListItem.DBID')
    initial_genre = xbmc.getInfoLabel('ListItem.Genre')
    initial_duration = xbmc.getInfoLabel('ListItem.Duration')
    
    log_msg(f"Initial state: DBID='{initial_dbid}', Genre='{initial_genre}', Duration='{initial_duration}'")
    
    while time.time() < end_time:
        check_count += 1
        
        # Check key metadata fields that should be populated from the database
        current_dbid = xbmc.getInfoLabel('ListItem.DBID')
        current_genre = xbmc.getInfoLabel('ListItem.Genre')
        current_dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
        current_duration = xbmc.getInfoLabel('ListItem.Duration')
        
        # Also check for basic info that should be present
        current_title = xbmc.getInfoLabel('ListItem.Title')
        current_year = xbmc.getInfoLabel('ListItem.Year')
        
        # Alternative Genre sources to check if primary is empty
        if not current_genre or current_genre.strip() == "":
            # Try VideoPlayer.Genre as alternative
            alt_genre = xbmc.getInfoLabel('VideoPlayer.Genre')
            if alt_genre and alt_genre.strip():
                current_genre = alt_genre
                if check_count <= 3:
                    log_msg(f"Using VideoPlayer.Genre as Genre source: '{alt_genre}'")
            else:
                # Try InfoTag approach for Genre
                try:
                    # This may work on some Kodi versions/skins
                    alt_genre2 = xbmc.getInfoLabel('ListItem.Property(Genre)')
                    if alt_genre2 and alt_genre2.strip():
                        current_genre = alt_genre2
                        if check_count <= 3:
                            log_msg(f"Using ListItem.Property(Genre) as Genre source: '{alt_genre2}'")
                except:
                    pass
        
        # Debug logging for Genre detection issues
        if check_count <= 5 or (check_count % 10 == 0):
            # Log all Genre sources for debugging
            primary_genre = xbmc.getInfoLabel('ListItem.Genre')
            video_genre = xbmc.getInfoLabel('VideoPlayer.Genre') 
            prop_genre = ""
            try:
                prop_genre = xbmc.getInfoLabel('ListItem.Property(Genre)')
            except:
                pass
            log_msg(f"GENRE SOURCES check #{check_count}: ListItem.Genre='{primary_genre}', VideoPlayer.Genre='{video_genre}', Property(Genre)='{prop_genre}', final='{current_genre}'")
        
        elapsed = time.perf_counter() - start_time
        
        # Log every check for the first few, then every 5th check
        if check_count <= 5 or check_count % 5 == 0:
            log_msg(f"Check #{check_count} ({elapsed:.3f}s): DBID='{current_dbid}', Genre='{current_genre}', DBType='{current_dbtype}', Duration='{current_duration}', Title='{current_title}'")
        
        # Enhanced validation - check for complete hydration
        has_dbid = current_dbid and current_dbid != "0" and current_dbid.strip()
        has_genre = current_genre and current_genre.strip() and current_genre != "None"
        has_dbtype = current_dbtype and current_dbtype.strip()
        has_duration = current_duration and current_duration.strip()
        has_title = current_title and current_title.strip()
        
        # Primary requirement: Complete hydration WITH Genre
        # Genre is critical for proper native info dialog population
        complete_hydration = has_dbid and has_genre and has_dbtype and has_duration and has_title
        
        if complete_hydration:
            elapsed_final = time.perf_counter() - start_time
            log_msg(f"SUCCESS: Complete hydration with Genre after {check_count} checks ({elapsed_final:.3f}s)")
            log_msg(f"Final metadata: DBID={current_dbid}, Genre='{current_genre}', DBType='{current_dbtype}', Duration='{current_duration}', Title='{current_title}'")
            
            # Additional Genre debugging - check all possible Genre sources
            alt_genre_info = xbmc.getInfoLabel('VideoPlayer.Genre')
            alt_genre_prop = xbmc.getInfoLabel('ListItem.Property(Genre)')
            log_msg(f"GENRE DEBUG: Primary='{current_genre}', VideoPlayer.Genre='{alt_genre_info}', Property(Genre)='{alt_genre_prop}'")
            
            return True
        
        # Only after significant time (1.2s), consider proceeding without Genre
        # This gives Genre more time to populate since it's database-dependent
        elif elapsed > 1.2:
            basic_hydration = has_dbid and has_dbtype and has_duration and has_title
            if basic_hydration:
                elapsed_final = time.perf_counter() - start_time
                log_msg(f"TIMEOUT FALLBACK: Proceeding without Genre after {check_count} checks ({elapsed_final:.3f}s)")
                log_msg(f"Final metadata: DBID={current_dbid}, Genre='{current_genre or 'MISSING'}', DBType='{current_dbtype}', Duration='{current_duration}', Title='{current_title}'")
                
                # Additional Genre debugging for timeout cases
                alt_genre_info = xbmc.getInfoLabel('VideoPlayer.Genre')
                alt_genre_prop = xbmc.getInfoLabel('ListItem.Property(Genre)')
                log_msg(f"TIMEOUT GENRE DEBUG: Primary='{current_genre}', VideoPlayer.Genre='{alt_genre_info}', Property(Genre)='{alt_genre_prop}'")
                
                return True
        
        # Log what we're still missing
        if check_count <= 3 or check_count % 10 == 0:
            missing = []
            if not has_dbid:
                missing.append("DBID")
            if not has_genre:
                missing.append("Genre")
            if not has_dbtype:
                missing.append("DBType")
            if missing:
                log_msg(f"Still waiting for: {', '.join(missing)} (check #{check_count})")
        
        # Short sleep between checks
        xbmc.sleep(int(check_interval * 1000))
    
    # Timeout reached
    elapsed_final = time.perf_counter() - start_time
    log_msg(f"TIMEOUT after {check_count} checks ({elapsed_final:.3f}s)", "warning")
    log_msg(f"Final state: DBID='{current_dbid}', Genre='{current_genre}', DBType='{current_dbtype}', Duration='{current_duration}', Title='{current_title}'", "warning")
    
    # Detailed analysis of what we have vs what we need
    has_dbid = current_dbid and current_dbid != "0" and current_dbid.strip()
    has_genre = current_genre and current_genre.strip() and current_genre != "None"
    has_dbtype = current_dbtype and current_dbtype.strip()
    has_duration = current_duration and current_duration.strip()
    has_title = current_title and current_title.strip()
    
    # Analyze the timeout situation
    if has_dbid and has_dbtype:
        if not has_genre:
            log_msg(f"WARNING: DBID and DBType present but Genre missing - Genre may populate after dialog opens", "warning")
        if has_duration and has_title:
            log_msg(f"INFO: Core metadata is available, proceeding without Genre - it should populate in the dialog", "warning")
            return True  # Allow proceeding if we have core metadata
        else:
            log_msg(f"CRITICAL: Missing essential metadata - Duration: {bool(has_duration)}, Title: {bool(has_title)}", "warning")
    elif not has_dbid:
        log_msg(f"DBID missing or invalid: '{current_dbid}'", "warning")
    elif not has_dbtype:
        log_msg(f"DBType missing: '{current_dbtype}'", "warning")
    
    # Only block if we're missing critical core metadata (DBID/DBType)
    # Genre can populate after the dialog opens
    return has_dbid and has_dbtype

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
    Create XSP file that filters by the file path of a database item.
    This ensures we get the actual library item with full metadata population.
    """
    try:
        _log(f"Creating XSP for database item {db_type} {db_id}")
        
        # Get the file path for this database item
        file_path = _get_file_for_dbitem(db_type, db_id)
        if not file_path:
            _log(f"No file path found for {db_type} {db_id}", xbmc.LOGWARNING)
            return None
        
        # Extract filename for XSP filtering
        filename = os.path.basename(file_path)
        filename_no_ext = os.path.splitext(filename)[0]
        
        _log(f"Creating XSP for {db_type} {db_id}: filename='{filename}', no_ext='{filename_no_ext}', full_path='{file_path}'")
        
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
        
        # Use profile playlists path with generic filename
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
        _log(f"XSP RAW CONTENT for {db_type} {db_id}:\n{xsp}")
        
        if _write_text(path, xsp):
            _log(f"XSP created successfully: {path} (filename='{filename}')")
            return path
        else:
            _log(f"Failed to write XSP file: {path}", xbmc.LOGWARNING)
            return None
            
    except Exception as e:
        _log(f"Exception creating XSP for {db_type} {db_id}: {e}", xbmc.LOGERROR)
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
    Proper hijack flow: Close current info dialog, navigate directly to videodb, then open info.
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
        
        # 📝 SUBSTEP 2: Create videodb URL for direct navigation
        substep2_start = time.perf_counter()
        logger.info(f"📝 SUBSTEP 2: Creating videodb URL for {db_type} {db_id}")
        start_videodb_time = time.perf_counter()
        
        # Create direct videodb URL for the specific item
        if db_type.lower() == 'movie':
            videodb_url = f"videodb://movies/titles/{db_id}"
        elif db_type.lower() == 'episode':
            videodb_url = f"videodb://tvshows/titles/-1/-1/{db_id}"
        elif db_type.lower() == 'tvshow':
            videodb_url = f"videodb://tvshows/titles/{db_id}"
        else:
            logger.warning(f"❌ SUBSTEP 2 FAILED: Unsupported db_type: {db_type}")
            return False
        
        end_videodb_time = time.perf_counter()
        logger.info(f"✅ SUBSTEP 2 COMPLETE: VideoDB URL created: {videodb_url} in {end_videodb_time - start_videodb_time:.3f}s")
        substep2_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 2 TIMING: {substep2_end - substep2_start:.3f}s")
        
        # 🧭 SUBSTEP 3: Navigate directly to the database item
        substep3_start = time.perf_counter()
        logger.info(f"🧭 SUBSTEP 3: Navigating to database item: {videodb_url}")
        current_window_before = xbmcgui.getCurrentWindowId()
        start_nav_time = time.perf_counter()
        logger.info(f"SUBSTEP 3 DEBUG: About to execute ActivateWindow command at {start_nav_time - overall_start_time:.3f}s")
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{videodb_url}",return)')
        activate_window_end = time.perf_counter()
        logger.info(f"SUBSTEP 3 DEBUG: ActivateWindow command executed in {activate_window_end - start_nav_time:.3f}s")
        
        # ⏳ SUBSTEP 4: Wait for the Videos window to load with videodb content
        substep4_start = time.perf_counter()
        logger.info(f"⏳ SUBSTEP 4: Waiting for Videos window to load with videodb content")
        wait_start = time.perf_counter()
        if not _wait_videos_on(videodb_url, timeout_ms=4000):  # Shorter timeout for direct videodb navigation
            wait_end = time.perf_counter()
            end_nav_time = time.perf_counter()
            current_window_after = xbmcgui.getCurrentWindowId()
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            logger.warning(f"❌ SUBSTEP 4 FAILED: Failed to load Videos window with videodb: {videodb_url} after {end_nav_time - start_nav_time:.3f}s")
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
        
        # 📍 SUBSTEP 6: Verify we're focused on the target database item
        substep6_start = time.perf_counter()
        logger.info(f"📍 SUBSTEP 6: Verifying focus on target database item")
        
        # With direct videodb navigation, we should already be focused on the correct item
        # Just verify the item details
        final_item_label = xbmc.getInfoLabel('ListItem.Label')
        final_item_dbid = xbmc.getInfoLabel('ListItem.DBID')
        final_item_dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
        final_item_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
        
        # Verify this is the correct database item
        expected_dbid = str(db_id)
        if final_item_dbid != expected_dbid:
            logger.warning(f"⚠️ SUBSTEP 6 WARNING: DBID mismatch - expected {expected_dbid}, got {final_item_dbid}")
            # Try to find the correct item if we're not on it
            if final_item_label == ".." or final_item_label.strip() == "..":
                logger.info(f"SUBSTEP 6: Currently on parent item, navigating to target")
                xbmc.executebuiltin('Action(Down)')
                xbmc.sleep(150)
                final_item_label = xbmc.getInfoLabel('ListItem.Label')
                final_item_dbid = xbmc.getInfoLabel('ListItem.DBID')
                final_item_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
        
        logger.info(f"✅ SUBSTEP 6 COMPLETE: On database item - Position: {final_item_position}, Label: '{final_item_label}', DBID: {final_item_dbid}, DBType: {final_item_dbtype}")
        substep6_end = time.perf_counter()
        logger.info(f"⏱️ SUBSTEP 6 TIMING: {substep6_end - substep6_start:.3f}s")
        
        # 💧 SUBSTEP 6.5: HYDRATION WAIT - Wait for Kodi to populate metadata on focused item
        substep6_5_start = time.perf_counter()
        logger.info(f"💧 SUBSTEP 6.5: HYDRATION WAIT - Waiting for Kodi to populate ListItem metadata")
        
        hydration_success = _wait_for_listitem_hydration(timeout_ms=1500, logger=logger)
        
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
            
            # GENRE VERIFICATION: Check what Genre data is available in the opened dialog
            xbmc.sleep(200)  # Brief pause to let dialog fully populate
            dialog_genre = xbmc.getInfoLabel('ListItem.Genre')
            dialog_video_genre = xbmc.getInfoLabel('VideoPlayer.Genre')
            try:
                dialog_prop_genre = xbmc.getInfoLabel('ListItem.Property(Genre)')
            except:
                dialog_prop_genre = ""
            logger.info(f"🔍 POST-DIALOG GENRE CHECK: ListItem.Genre='{dialog_genre}', VideoPlayer.Genre='{dialog_video_genre}', Property(Genre)='{dialog_prop_genre}'")
            
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