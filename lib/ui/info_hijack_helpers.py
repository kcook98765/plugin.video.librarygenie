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
    Block until the DialogVideoInfo window is active (skin dep. but standard on Kodi 19+).
    Extended timeout and better handling for subtitle/metadata scanning delays.
    """
    t_start = time.perf_counter()
    end = time.time() + timeout
    check_count = 0
    scan_detected = False

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

        # Detect if we're in a scanning phase (helps explain delays)
        if is_busy and not scan_detected:
            scan_detected = True
            _log(f"_wait_for_info_dialog: Detected Kodi busy state (likely scanning for subtitles/metadata)")

        # Log every 30 checks (roughly every 1.5 seconds) or when busy state changes
        if check_count % 30 == 0 or (is_busy and check_count % 10 == 0):
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

    def check_condition():
        window_active = xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        folder_path = (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/')
        path_match = folder_path == t_norm
        num_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        not_busy = not xbmc.getCondVisibility("Window.IsActive(DialogBusy.xml)")

        # Additional check for progress dialogs that might appear during scanning
        not_scanning = not xbmc.getCondVisibility("Window.IsActive(DialogProgress.xml)")

        elapsed = time.perf_counter() - t_start

        # Show scan warning after 3 seconds if still busy
        nonlocal scan_warning_shown
        if elapsed > 3.0 and (not not_busy or not not_scanning) and not scan_warning_shown:
            _log(f"_wait_videos_on: Kodi busy for {elapsed:.1f}s - likely scanning for associated files")
            scan_warning_shown = True

        # Reduced logging frequency for better performance on slower devices
        if int(elapsed) % 3 == 0 and elapsed - int(elapsed) < 0.2:  # Every 3 seconds
            _log(f"_wait_videos_on check ({elapsed:.1f}s): window={window_active}, path_match={path_match}, items={num_items}, not_busy={not_busy}, not_scanning={not_scanning}")

        return window_active and path_match and num_items > 0 and not_busy and not_scanning

    # Extended timeout for network storage scenarios
    result = wait_until(check_condition, timeout_ms=max(timeout_ms, 10000), step_ms=100)
    t_end = time.perf_counter()

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

def open_native_info_fast(dbtype: str, dbid: int, logger) -> bool:
    """
    Open native info by creating temporary XSP and navigating to it.
    This bypasses the slow Container.Update approach.

    Args:
        dbtype: 'movie' or 'episode'
        dbid: Kodi database ID
        logger: Logger instance

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        step_start = time.time()

        # Determine content type for XSP
        if dbtype == 'movie':
            content_type = 'movies'
            filter_field = 'movieid'
        elif dbtype == 'episode':
            content_type = 'episodes'
            filter_field = 'episodeid'
        else:
            logger.error(f"Unsupported dbtype for hijack: {dbtype}")
            return False

        logger.debug(f"HIJACK XSP: Step 3.1 - Content type determination completed in {time.time() - step_start:.3f}s")
        step_start = time.time()

        # Create XSP content
        xsp_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<smartplaylist type="{content_type}">
    <name>lg_hijack_{dbtype}_{dbid}</name>
    <match>one</match>
    <rule field="{filter_field}" operator="is">
        <value>{dbid}</value>
    </rule>
</smartplaylist>'''

        logger.debug(f"HIJACK XSP: Step 3.2 - XSP content generation completed in {time.time() - step_start:.3f}s")
        step_start = time.time()

        # Write to temp file
        temp_file = f"special://temp/lg_hijack_{dbtype}_{dbid}.xsp"

        # Use xbmcvfs to write the file
        file_handle = xbmcvfs.File(temp_file, 'w')
        if not file_handle:
            logger.error(f"Failed to create XSP file: {temp_file}")
            return False

        try:
            bytes_written = file_handle.write(xsp_content.encode('utf-8'))
            if bytes_written == 0:
                logger.error(f"Failed to write content to XSP file: {temp_file}")
                return False
            logger.debug(f"HIJACK XSP: Step 3.3 - XSP file written ({bytes_written} bytes) in {time.time() - step_start:.3f}s")
        finally:
            file_handle.close()

        step_start = time.time()

        # Navigate to the XSP file to load it in library view
        logger.debug(f"HIJACK XSP: Step 3.4 - Starting navigation to {temp_file}")
        xbmc.executebuiltin(f'ActivateWindow(Videos,{temp_file},return)')

        navigation_start = time.time()
        logger.debug(f"HIJACK XSP: Step 3.4 - Navigation command issued in {time.time() - step_start:.3f}s")

        # Wait for navigation and content loading with detailed progress
        max_wait = 10.0  # 10 seconds max
        start_time = time.time()
        last_status_time = start_time

        while (time.time() - start_time) < max_wait:
            current_time = time.time()

            # Log progress every 1 second
            if current_time - last_status_time >= 1.0:
                current_window = xbmc.getInfoLabel("System.CurrentWindow")
                current_path = xbmc.getInfoLabel("Container.FolderPath")
                logger.debug(f"HIJACK XSP: Step 3.5 - Navigation progress at {current_time - navigation_start:.3f}s - Window: '{current_window}', Path: '{current_path[:100]}...'")
                last_status_time = current_time

            # Check if we're in the Videos window with the XSP loaded
            current_window = xbmc.getInfoLabel("System.CurrentWindow")
            current_path = xbmc.getInfoLabel("Container.FolderPath")

            if 'video' in current_window.lower() and temp_file.split('/')[-1] in current_path:
                logger.debug(f"HIJACK XSP: Step 3.5 - Navigation to XSP completed in {current_time - navigation_start:.3f}s")
                content_load_start = time.time()

                # Check if the item is loaded and has the expected DBID
                listitem_dbid = xbmc.getInfoLabel('ListItem.DBID')
                logger.debug(f"HIJACK XSP: Step 3.6 - Checking content load - Expected DBID: {dbid}, Found DBID: '{listitem_dbid}'")

                if listitem_dbid == str(dbid):
                    logger.debug(f"HIJACK XSP: Step 3.6 - Content loaded successfully in {time.time() - content_load_start:.3f}s")
                    info_open_start = time.time()

                    # Found our item, now open info
                    logger.debug(f"HIJACK XSP: Step 3.7 - Opening info dialog")
                    xbmc.executebuiltin('Action(Info)')

                    # Brief wait for info dialog to open
                    xbmc.sleep(200)

                    # Verify info dialog opened
                    if xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)'):
                        logger.debug(f"HIJACK XSP: Step 3.7 - Info dialog opened successfully in {time.time() - info_open_start:.3f}s")
                        logger.debug(f"HIJACK XSP: Successfully opened native info for {dbtype} {dbid} via XSP - Total navigation time: {time.time() - navigation_start:.3f}s")
                        return True
                    else:
                        logger.warning(f"HIJACK XSP: Info dialog did not open for {dbtype} {dbid} after {time.time() - info_open_start:.3f}s")
                        return False

            xbmc.sleep(100)  # Check every 100ms

        # Timeout - log final state
        final_window = xbmc.getInfoLabel("System.CurrentWindow")
        final_path = xbmc.getInfoLabel("Container.FolderPath")
        logger.error(f"HIJACK XSP: Timeout after {time.time() - navigation_start:.3f}s waiting for XSP navigation to complete for {dbtype} {dbid}")
        logger.error(f"HIJACK XSP: Final state - Window: '{final_window}', Path: '{final_path[:200]}...'")
        return False

    except Exception as e:
        logger.error(f"Exception in open_native_info_fast: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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