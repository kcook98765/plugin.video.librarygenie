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

from ..utils.kodi_log import get_kodi_logger
from ..utils.kodi_version import get_version_specific_control_id
from .localization import L
from .navigation_cache import get_cached_info, get_navigation_snapshot, navigation_action

logger = get_kodi_logger('lib.ui.info_hijack_helpers')

LOG_PREFIX = "[LG.Hijack]"
LIST_ID = 50
VIDEOS_WINDOW = "MyVideoNav.xml"

def _log(message: str, level: int = xbmc.LOGDEBUG, *args) -> None:
    """Internal logging with consistent prefix and deferred formatting"""
    prefixed_message = LOG_PREFIX + " " + message
    if level == xbmc.LOGWARNING:
        logger.warning(prefixed_message, *args)
    elif level == xbmc.LOGERROR:
        logger.error(prefixed_message, *args)
    else:
        logger.debug(prefixed_message, *args)






def jsonrpc(method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    raw = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        return json.loads(raw)
    except Exception:
        _log("JSON parse error for %s: %s", xbmc.LOGWARNING, method, raw)
        return {}

def wait_for_dialog_close(context: str, initial_dialog_id: int, logger, max_wait: float = 1.0) -> bool:
    """Monitor for dialog actually closing instead of using fixed sleep"""
    start_time = time.time()
    check_interval = 0.1  # 100ms checks for responsive detection
    
    while (time.time() - start_time) < max_wait:
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        # Dialog closed when ID changes from the initial dialog
        if current_dialog_id != initial_dialog_id:
            elapsed = time.time() - start_time
            logger.debug("HIJACK: Dialog close detected %s after %.3fs (%d→%d)", context, elapsed, initial_dialog_id, current_dialog_id)
            return True
        
        xbmc.sleep(int(check_interval * 1000))
    
    elapsed = time.time() - start_time
    current_dialog_id = xbmcgui.getCurrentWindowDialogId()
    logger.warning("HIJACK: Dialog close timeout %s after %.1fs (still %d)", context, elapsed, current_dialog_id)
    return False

def wait_until(cond, timeout_ms=2000, step_ms=30) -> bool:
    t_start = time.perf_counter()
    end = time.time() + (timeout_ms / 1000.0)
    mon = xbmc.Monitor()
    check_count = 0
    
    # Use adaptive polling - start fast, then slow down
    current_step_ms = min(step_ms, 100)  # Start with quick polls
    max_step_ms = max(step_ms, 200)     # Cap at reasonable interval

    while time.time() < end and not mon.abortRequested():
        check_count += 1
        if cond():
            t_end = time.perf_counter()
            _log("wait_until: SUCCESS after %d checks (%.3fs, timeout was %dms)", xbmc.LOGDEBUG, check_count, t_end - t_start, timeout_ms)
            return True
        
        xbmc.sleep(current_step_ms)
        
        # Gradually increase polling interval to reduce CPU overhead on slower devices
        if check_count > 5:  # After initial quick checks
            current_step_ms = min(current_step_ms + 10, max_step_ms)

    t_end = time.perf_counter()
    _log("wait_until: TIMEOUT after %d checks (%.3fs, timeout was %dms)", xbmc.LOGWARNING, check_count, t_end - t_start, timeout_ms)
    return False

def _wait_for_info_dialog(timeout=10.0):
    """
    Block until the DialogVideoInfo window is active.
    Focus-essential checks only for maximum performance.
    """
    t_start = time.perf_counter()
    end = time.time() + timeout

    _log("_wait_for_info_dialog: Starting wait for info dialog with %.1fs timeout", xbmc.LOGDEBUG, timeout)

    while time.time() < end:
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        # Only check for target dialog - no other validations
        if current_dialog_id in (12003, 10147):  # DialogVideoInfo / Fallback
            t_end = time.perf_counter()
            _log("_wait_for_info_dialog: SUCCESS (%.3fs) - dialog_id=%d", xbmc.LOGDEBUG, t_end - t_start, current_dialog_id)
            return True
            
        # Simple polling - no complex state tracking
        xbmc.sleep(200)

    t_end = time.perf_counter()
    _log("_wait_for_info_dialog: TIMEOUT (%.3fs)", xbmc.LOGWARNING, t_end - t_start)
    return False

def verify_list_focus() -> bool:
    """Simple check if we're in a list view using Container.Viewmode"""
    try:
        view_mode = get_cached_info("Container.Viewmode").lower().strip()
        
        if not view_mode:
            _log("No viewmode detected - assuming we're in a list view")
            return True
            
        # Define view types
        VERTICAL_VIEWS = {"list", "widelist", "lowlist", "bannerlist", "biglist", 
                         "infolist", "detaillist", "episodes", "songs"}
        HORIZONTAL_VIEWS = {"wall", "poster", "panel", "thumbs", "iconwall", "fanart",
                           "shift", "showcase", "thumbnails", "icons", "grid", "wrap"}
        
        # Check if we're in any recognizable view type
        in_list_view = (view_mode in VERTICAL_VIEWS or view_mode in HORIZONTAL_VIEWS or
                       any(v in view_mode for v in VERTICAL_VIEWS | HORIZONTAL_VIEWS))
        
        _log("verify_list_focus: viewmode='%s', in_list_view=%s", xbmc.LOGDEBUG, view_mode, in_list_view)
        return in_list_view
        
    except Exception as e:
        _log("Error in verify_list_focus: %s - assuming we're in a list view", xbmc.LOGWARNING, e)
        return True

def _capture_navigation_state() -> dict:
    """Capture current navigation state for safe testing"""
    try:
        # Use cached snapshot for efficient batch property access
        snapshot = get_navigation_snapshot()
        return {
            'current_item': snapshot['current_item'],
            'num_items': snapshot['num_items'],
            'current_window': snapshot['current_window'],
            'current_control': snapshot['current_control'],
            'focused_label': snapshot['focused_label']
        }
    except Exception as e:
        _log("Error capturing navigation state: %s", xbmc.LOGWARNING, e)
        return {}

def _is_still_in_container(original_state: dict) -> bool:
    """Check if we're still in the same container after navigation"""
    try:
        current_items = get_cached_info("Container.NumItems")
        current_window = get_cached_info("System.CurrentWindow")
        
        # If window or container size changed dramatically, we probably left
        return (current_items == original_state.get('num_items') and 
                current_window == original_state.get('current_window'))
    except Exception as e:
        _log("Error checking container state: %s", xbmc.LOGWARNING, e)
        return True  # Assume safe if we can't check

def _did_navigation_work(original_state: dict) -> bool:
    """Check if navigation actually moved focus/position"""
    try:
        current_item = get_cached_info("Container.CurrentItem")
        current_control = get_cached_info("System.CurrentControlId")
        current_label = get_cached_info("Container.ListItem().Label")
        
        # Check if any navigation indicators changed
        position_changed = current_item != original_state.get('current_item')
        control_changed = current_control != original_state.get('current_control')
        label_changed = current_label != original_state.get('focused_label')
        
        return position_changed or control_changed or label_changed
    except Exception as e:
        _log("Error checking navigation success: %s", xbmc.LOGWARNING, e)
        return False

def _test_navigation_direction(action: str, opposite_action: str, step_ms: int = 100) -> bool:
    """
    Safely test a navigation direction with container validation and undo capability
    Returns True if the direction works and keeps us in the container
    """
    try:
        # Capture state before testing
        original_state = _capture_navigation_state()
        _log("Testing navigation: %s", xbmc.LOGDEBUG, action)
        
        # Try the navigation action with cache invalidation
        with navigation_action(grace_ms=step_ms):
            xbmc.executebuiltin(action)
            xbmc.sleep(step_ms)
        
        # Check if we're still in the same container
        if not _is_still_in_container(original_state):
            _log("Navigation %s moved outside container - undoing with %s", xbmc.LOGDEBUG, action, opposite_action)
            with navigation_action(grace_ms=step_ms):
                xbmc.executebuiltin(opposite_action)
                xbmc.sleep(step_ms)
            return False
        
        # Check if navigation actually worked (focus/position changed)
        if _did_navigation_work(original_state):
            _log("Navigation %s successful - position/focus changed", xbmc.LOGDEBUG, action)
            return True
        else:
            _log("Navigation %s had no effect - position unchanged", xbmc.LOGDEBUG, action)
            return False
            
    except Exception as e:
        _log("Error testing navigation %s: %s", xbmc.LOGERROR, action, e)
        return False

def focus_list_manual(control_id: Optional[int] = None, tries: int = 3, step_ms: int = 100) -> bool:
    """Smart list navigation using view orientation detection with intelligent fallback"""
    t_focus_start = time.perf_counter()

    try:
        view_mode = get_cached_info("Container.Viewmode").lower().strip()
        _log("focus_list_manual: Detected viewmode = '%s'", xbmc.LOGDEBUG, view_mode)
        
        # Define view types
        VERTICAL_VIEWS = {"list", "widelist", "lowlist", "bannerlist", "biglist", 
                         "infolist", "detaillist", "episodes", "songs"}
        HORIZONTAL_VIEWS = {"wall", "poster", "panel", "thumbs", "iconwall", "fanart",
                           "shift", "showcase", "thumbnails", "icons", "grid", "wrap"}
        
        # Determine navigation direction
        if view_mode in VERTICAL_VIEWS or any(v in view_mode for v in VERTICAL_VIEWS):
            nav_command = "Action(Down)"
            orientation = "vertical"
            _log("focus_list_manual: Using %s for %s view", xbmc.LOGDEBUG, nav_command, orientation)
            
            # Send navigation action for known vertical views
            for attempt in range(tries):
                _log("Attempt %d: Sending %s", xbmc.LOGDEBUG, attempt + 1, nav_command)
                with navigation_action(grace_ms=step_ms):
                    xbmc.executebuiltin(nav_command)
                    xbmc.sleep(step_ms)
                
        elif view_mode in HORIZONTAL_VIEWS or any(v in view_mode for v in HORIZONTAL_VIEWS):
            nav_command = "Action(Right)"
            orientation = "horizontal"
            _log("focus_list_manual: Using %s for %s view", xbmc.LOGDEBUG, nav_command, orientation)
            
            # Send navigation action for known horizontal views
            for attempt in range(tries):
                _log("Attempt %d: Sending %s", xbmc.LOGDEBUG, attempt + 1, nav_command)
                with navigation_action(grace_ms=step_ms):
                    xbmc.executebuiltin(nav_command)
                    xbmc.sleep(step_ms)
                
        else:
            # Unknown view mode - intelligent fallback with safe testing
            _log("Unknown viewmode '%s' - using intelligent fallback testing", xbmc.LOGDEBUG, view_mode)
            
            # Test Right navigation first (horizontal)
            if _test_navigation_direction("Action(Right)", "Action(Left)", step_ms):
                _log("Intelligent fallback: Right navigation works - using horizontal mode")
                nav_command = "Action(Right)"
                
                # Continue with remaining navigation attempts
                for attempt in range(tries - 1):  # -1 because we already tested once
                    _log("Attempt %d: Sending %s", xbmc.LOGDEBUG, attempt + 2, nav_command)
                    with navigation_action(grace_ms=step_ms):
                        xbmc.executebuiltin(nav_command)
                        xbmc.sleep(step_ms)
                    
            # If Right didn't work, test Down navigation (vertical)  
            elif _test_navigation_direction("Action(Down)", "Action(Up)", step_ms):
                _log("Intelligent fallback: Down navigation works - using vertical mode")
                nav_command = "Action(Down)"
                
                # Continue with remaining navigation attempts
                for attempt in range(tries - 1):  # -1 because we already tested once
                    _log("Attempt %d: Sending %s", xbmc.LOGDEBUG, attempt + 2, nav_command)
                    with navigation_action(grace_ms=step_ms):
                        xbmc.executebuiltin(nav_command)
                        xbmc.sleep(step_ms)
                    
            else:
                _log("Intelligent fallback: Neither Right nor Down navigation worked - container may be non-standard", xbmc.LOGWARNING)
                return False
        
        t_focus_end = time.perf_counter()
        _log("focus_list_manual: Completed navigation in %.3fs", xbmc.LOGDEBUG, t_focus_end - t_focus_start)
        return True
        
    except Exception as e:
        t_focus_end = time.perf_counter()
        _log("Error in focus_list_manual: %s - graceful fallback failed (took %.3fs)", xbmc.LOGERROR, e, t_focus_end - t_focus_start)
        return False

def focus_list(control_id: Optional[int] = None, tries: int = 20, step_ms: int = 30) -> bool:
    """Optimized list focusing: check if already focused, then fallback to manual focus"""
    t_focus_start = time.perf_counter()
    
    # First check if list control is already focused (should be automatic after XSP navigation)
    if verify_list_focus():
        t_focus_end = time.perf_counter()
        _log("focus_list: List already focused - substep 5 complete (%.3fs)", xbmc.LOGDEBUG, t_focus_end - t_focus_start)
        return True
    else:
        _log("focus_list: Manual focus needed - using focus_list_manual()")
        return focus_list_manual(control_id, tries, step_ms)

def _write_text(path_special: str, text: str) -> bool:
    try:
        f = xbmcvfs.File(path_special, 'w')
        f.write(text.encode('utf-8'))
        f.close()
        return True
    except Exception as e:
        _log("xbmcvfs write failed: %s", xbmc.LOGWARNING, e)
        return False

def _get_file_for_dbitem(dbtype: str, dbid: int) -> Optional[str]:
    if dbtype == "movie":
        data = jsonrpc("VideoLibrary.GetMovieDetails", {"movieid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("moviedetails") or {}
        file_path = md.get("file")
        _log("Movie %d file path: %s", xbmc.LOGDEBUG, dbid, file_path)
        return file_path
    elif dbtype == "episode":
        data = jsonrpc("VideoLibrary.GetEpisodeDetails", {"episodeid": int(dbid), "properties": ["file"]})
        md = (data.get("result") or {}).get("episodedetails") or {}
        file_path = md.get("file")
        _log("Episode %d file path: %s", xbmc.LOGDEBUG, dbid, file_path)
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
        _log("Creating XSP for database item %s %d", xbmc.LOGDEBUG, db_type, db_id)
        
        # Get the actual file path from the database item
        file_path = _get_file_for_dbitem(db_type, db_id)
        if not file_path:
            _log("No file path found for %s %d", xbmc.LOGWARNING, db_type, db_id)
            return None
        
        filename = os.path.basename(file_path)
        filename_no_ext = os.path.splitext(filename)[0]
        _log("Creating XSP for %s %d: filename='%s', no_ext='%s'", xbmc.LOGDEBUG, db_type, db_id, filename, filename_no_ext)
        
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
            _log("Unsupported db_type for XSP creation: %s", xbmc.LOGWARNING, db_type)
            return None
        
        # Use addon userdata directory for stable XSP file location
        import xbmcaddon
        addon = xbmcaddon.Addon()
        profile_dir = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        hijack_dir = os.path.join(profile_dir, 'hijack')
        xsp_filename = "lg_hijack_temp.xsp"  # Consistent filename that overwrites
        path = os.path.join(hijack_dir, xsp_filename)
        
        # Ensure hijack directory exists
        try:
            if not xbmcvfs.exists(hijack_dir):
                _log("Creating hijack directory: %s", xbmc.LOGDEBUG, hijack_dir)
                xbmcvfs.mkdirs(hijack_dir)
        except Exception as e:
            _log("Failed to create hijack directory: %s", xbmc.LOGWARNING, e)
            # Fallback to profile root
            path = os.path.join(profile_dir, xsp_filename)
        
        # Log the XSP content for debugging
        _log("XSP content for %s %d:\n%s", xbmc.LOGDEBUG, db_type, db_id, xsp)
        
        if _write_text(path, xsp):
            _log("XSP created successfully: %s", xbmc.LOGDEBUG, path)
            return path
        else:
            _log("Failed to write XSP file: %s", xbmc.LOGWARNING, path)
            return None
            
    except Exception as e:
        _log("Exception creating XSP for %s %d: %s", xbmc.LOGERROR, db_type, db_id, e)
        return None

def _create_xsp_for_file(dbtype: str, dbid: int) -> Optional[str]:
    fp = _get_file_for_dbitem(dbtype, dbid)
    if not fp:
        _log("No file path found for %s %d", xbmc.LOGWARNING, dbtype, dbid)
        return None

    filename = os.path.basename(fp)
    # Remove file extension for XSP matching
    filename_no_ext = os.path.splitext(filename)[0]
    _log("Creating XSP for %s %d: filename='%s', no_ext='%s', full_path='%s'", xbmc.LOGDEBUG, dbtype, dbid, filename, filename_no_ext, fp)

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

    # Use addon userdata directory for stable XSP file location (persistent for debugging)
    import xbmcaddon
    addon = xbmcaddon.Addon()
    profile_dir = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    hijack_dir = os.path.join(profile_dir, 'hijack')
    xsp_filename = "lg_hijack_debug.xsp"
    path = os.path.join(hijack_dir, xsp_filename)

    # Ensure hijack temp directory exists
    try:
        if not xbmcvfs.exists(hijack_dir):
            _log("Creating hijack temp directory: %s", xbmc.LOGDEBUG, hijack_dir)
            xbmcvfs.mkdirs(hijack_dir)
    except Exception as e:
        _log("Failed to create hijack temp directory: %s", xbmc.LOGWARNING, e)
        # Fallback to direct temp
        path = f"special://temp/{xsp_filename}"

    # Log the raw XSP content for debugging
    _log("XSP RAW CONTENT for %s %d:\n%s", xbmc.LOGDEBUG, dbtype, dbid, xsp)

    if _write_text(path, xsp):
        _log("XSP created successfully: %s (filename='%s')", xbmc.LOGDEBUG, path, filename)
        return path
    else:
        _log("Failed to write XSP file: %s", xbmc.LOGWARNING, path)
        return None

# XSP cleanup removed - using persistent generic filename for debugging

def _find_index_in_dir_by_file(directory: str, target_file: Optional[str]) -> int:
    """Simplified: assume movie is only match, just skip parent if present"""
    data = jsonrpc("Files.GetDirectory", {
        "directory": directory, "media": "video",
        "properties": ["file", "title", "thumbnail"]
    })
    items = (data.get("result") or {}).get("files") or []
    _log("XSP directory items count: %d", xbmc.LOGDEBUG, len(items))

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

    _log("_wait_videos_on: Starting wait for path '%s' with %dms timeout", xbmc.LOGDEBUG, t_norm, timeout_ms)

    def check_condition():
        nonlocal condition_met_count, last_condition_details
        
        window_active = xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        folder_path = (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/')
        path_match = folder_path == t_norm
        num_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        not_busy = True  # OPTIMIZATION: Removed DialogBusy check for performance
        
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
            _log("_wait_videos_on CONDITION CHANGE at %.3fs: %s", xbmc.LOGDEBUG, elapsed, current_details)
            last_condition_details = current_details.copy()
        
        # Show scan warning after 3 seconds if still busy
        nonlocal scan_warning_shown
        if elapsed > 3.0 and (not not_busy or not not_scanning) and not scan_warning_shown:
            _log("_wait_videos_on: Kodi busy for %.1fs - likely scanning for associated files", xbmc.LOGDEBUG, elapsed)
            scan_warning_shown = True
        
        # More frequent logging for debugging delays
        if int(elapsed * 2) % 3 == 0 and elapsed - int(elapsed * 2) / 2 < 0.05:  # Every 1.5 seconds
            _log("_wait_videos_on check (%.1fs): window=%s, path_match=%s ('%s' vs '%s'), items=%d, not_busy=%s, not_scanning=%s", xbmc.LOGDEBUG, elapsed, window_active, path_match, folder_path, t_norm, num_items, not_busy, not_scanning)

        final_condition = window_active and path_match and num_items > 0 and not_busy and not_scanning
        if final_condition:
            condition_met_count += 1
            _log("_wait_videos_on: ALL CONDITIONS MET at %.3fs (count: %d)", xbmc.LOGDEBUG, elapsed, condition_met_count)
        else:
            condition_met_count = 0

        return final_condition

    # Extended timeout for network storage scenarios
    _log("_wait_videos_on: Starting wait_until with %dms timeout", xbmc.LOGDEBUG, max(timeout_ms, 10000))
    wait_start = time.perf_counter()
    result = wait_until(check_condition, timeout_ms=max(timeout_ms, 10000), step_ms=100)
    wait_end = time.perf_counter()
    t_end = time.perf_counter()

    _log("_wait_videos_on: wait_until completed in %.3fs, result=%s", xbmc.LOGDEBUG, wait_end - wait_start, result)

    if result:
        _log("_wait_videos_on SUCCESS after %.3fs", xbmc.LOGDEBUG, t_end - t_start)
        if scan_warning_shown:
            _log("_wait_videos_on: XSP loaded successfully after file scanning completed")
    else:
        _log("_wait_videos_on TIMEOUT after %.3fs", xbmc.LOGWARNING, t_end - t_start)
        # Log final state for debugging
        final_window = xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        final_path = (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/')
        final_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        final_busy = xbmc.getCondVisibility("Window.IsActive(DialogBusy.xml)")
        final_progress = xbmc.getCondVisibility("Window.IsActive(DialogProgress.xml)")
        _log("_wait_videos_on FINAL STATE: window=%s, path='%s', items=%s, busy=%s, progress=%s", xbmc.LOGWARNING, final_window, final_path, final_items, final_busy, final_progress)

    return result

def cleanup_old_hijack_files():
    """No cleanup needed - we use consistent filename that overwrites"""
    pass

def open_native_info_fast(db_type: str, db_id: int, logger) -> bool:
    """
    Proper hijack flow: Close current info dialog, navigate to native list, then open info.
    This ensures the video info gets full Kodi metadata population from native library.
    """
    try:
        overall_start_time = time.perf_counter()
        logger.debug("%s Starting hijack process for %s %d", LOG_PREFIX, db_type, db_id)
        
        # Clean up any old hijack files before starting
        cleanup_old_hijack_files()
        
        # 🔒 SUBSTEP 1: Close any open dialog first
        substep1_start = time.perf_counter()
        logger.debug("%s SUBSTEP 1: Checking for open dialogs to close", LOG_PREFIX)
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        if current_dialog_id in (12003, 10147):  # DialogVideoInfo or similar
            logger.debug("%s SUBSTEP 1: Found open dialog ID %d, closing it", LOG_PREFIX, current_dialog_id)
            xbmc.executebuiltin('Action(Back)')
            
            # Monitor for dialog actually closing instead of fixed sleep
            if wait_for_dialog_close("SUBSTEP 1 dialog close", current_dialog_id, logger, max_wait=1.0):
                after_close_id = xbmcgui.getCurrentWindowDialogId()
                logger.debug("%s SUBSTEP 1 COMPLETE: Dialog closed (was %d, now %d)", LOG_PREFIX, current_dialog_id, after_close_id)
            else:
                logger.warning("%s ⚠️ SUBSTEP 1: Dialog close timeout, proceeding anyway", LOG_PREFIX)
        else:
            logger.debug("%s SUBSTEP 1 COMPLETE: No dialog to close (current dialog ID: %d)", LOG_PREFIX, current_dialog_id)
        substep1_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 1 TIMING: %.3fs", LOG_PREFIX, substep1_end - substep1_start)
        
        # 📝 SUBSTEP 2: Create XSP file for single item to create a native list
        substep2_start = time.perf_counter()
        logger.debug("%s SUBSTEP 2: Creating XSP file for %s %d", LOG_PREFIX, db_type, db_id)
        start_xsp_time = time.perf_counter()
        xsp_path = _create_xsp_for_dbitem(db_type, db_id)
        end_xsp_time = time.perf_counter()
        
        if not xsp_path:
            logger.warning("%s ❌ SUBSTEP 2 FAILED: Failed to create XSP for %s %d", LOG_PREFIX, db_type, db_id)
            return False
        logger.debug("%s SUBSTEP 2 COMPLETE: XSP created at %s in %.3fs", LOG_PREFIX, xsp_path, end_xsp_time - start_xsp_time)
        substep2_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 2 TIMING: %.3fs", LOG_PREFIX, substep2_end - substep2_start)
        
        # Brief delay to ensure XSP file is fully written and available for Kodi to read
        xbmc.sleep(30)  # 30ms buffer for file system consistency
        
        # 🧭 SUBSTEP 3: Navigate to the XSP (creates native Kodi list with single item)
        substep3_start = time.perf_counter()
        logger.debug("%s SUBSTEP 3: Navigating to native list: %s", LOG_PREFIX, xsp_path)
        current_window_before = xbmcgui.getCurrentWindowId()
        start_nav_time = time.perf_counter()
        logger.debug("%s SUBSTEP 3 DEBUG: About to execute ActivateWindow command at %.3fs", LOG_PREFIX, start_nav_time - overall_start_time)
        xbmc.executebuiltin('ActivateWindow(Videos,"%s",return)' % xsp_path)
        activate_window_end = time.perf_counter()
        logger.debug("%s SUBSTEP 3 DEBUG: ActivateWindow command executed in %.3fs", LOG_PREFIX, activate_window_end - start_nav_time)
        
        # ⏳ SUBSTEP 4: Wait for the Videos window to load with our item
        substep4_start = time.perf_counter()
        logger.debug("%s SUBSTEP 4: Waiting for Videos window to load with XSP content", LOG_PREFIX)
        wait_start = time.perf_counter()
        if not _wait_videos_on(xsp_path, timeout_ms=4000):
            wait_end = time.perf_counter()
            end_nav_time = time.perf_counter()
            current_window_after = xbmcgui.getCurrentWindowId()
            current_path = xbmc.getInfoLabel("Container.FolderPath")
            logger.warning("%s ❌ SUBSTEP 4 FAILED: Failed to load Videos window with XSP: %s after %.3fs", LOG_PREFIX, xsp_path, end_nav_time - start_nav_time)
            logger.warning("%s SUBSTEP 4 DEBUG: Window before=%d, after=%d, current_path='%s'", LOG_PREFIX, current_window_before, current_window_after, current_path)
            logger.warning("%s ⏱️ SUBSTEP 4 WAIT TIMING: %.3fs", LOG_PREFIX, wait_end - wait_start)
            return False
        wait_end = time.perf_counter()
        end_nav_time = time.perf_counter()
        current_window_after = xbmcgui.getCurrentWindowId()
        current_path = xbmc.getInfoLabel("Container.FolderPath")
        num_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
        logger.debug("%s SUBSTEP 4 COMPLETE: Videos window loaded in %.3fs", LOG_PREFIX, end_nav_time - start_nav_time)
        logger.debug("%s SUBSTEP 4 STATUS: Window %d→%d, path='%s', items=%s", LOG_PREFIX, current_window_before, current_window_after, current_path, num_items)
        substep4_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 4 TIMING: %.3fs (wait: %.3fs)", LOG_PREFIX, substep4_end - substep4_start, wait_end - wait_start)
        logger.debug("%s ⏱️ SUBSTEP 3+4 COMBINED TIMING: %.3fs", LOG_PREFIX, substep4_end - substep3_start)
        
        # 🎯 SUBSTEP 5: Focus the list and find our item
        substep5_start = time.perf_counter()
        logger.debug("%s SUBSTEP 5: Focusing list to locate %s %d", LOG_PREFIX, db_type, db_id)
        start_focus_time = time.perf_counter()
        if not focus_list():
            end_focus_time = time.perf_counter()
            logger.warning("%s ❌ SUBSTEP 5 FAILED: Failed to focus list control after %.3fs", LOG_PREFIX, end_focus_time - start_focus_time)
            return False
        end_focus_time = time.perf_counter()
        logger.debug("%s SUBSTEP 5 COMPLETE: List focused in %.3fs", LOG_PREFIX, end_focus_time - start_focus_time)
        substep5_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 5 TIMING: %.3fs", LOG_PREFIX, substep5_end - substep5_start)
        
        # 📍 SUBSTEP 6: Check current item and navigate away from parent if needed
        substep6_start = time.perf_counter()
        logger.debug("%s SUBSTEP 6: Checking current item and navigating to movie", LOG_PREFIX)
        current_item_before = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
        current_item_label = xbmc.getInfoLabel('ListItem.Label')
        
        # Check if we're focused on the parent item ".."
        if current_item_label == ".." or current_item_label.strip() == "..":
            logger.debug("%s SUBSTEP 6: Currently on parent item '%s', navigating to next item", LOG_PREFIX, current_item_label)
            xbmc.executebuiltin('Action(Down)')  # Move to next item
            xbmc.sleep(150)  # Wait for navigation
            current_item_after = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
            new_label = xbmc.getInfoLabel('ListItem.Label')
            logger.debug("%s SUBSTEP 6: Moved from parent item %s to item %s, new label: '%s'", LOG_PREFIX, current_item_before, current_item_after, new_label)
        else:
            logger.debug("%s SUBSTEP 6: Already on target item '%s' at position %s", LOG_PREFIX, current_item_label, current_item_before)
        
        # Verify we're now on the correct item
        final_item_label = xbmc.getInfoLabel('ListItem.Label')
        final_item_dbid = xbmc.getInfoLabel('ListItem.DBID')
        final_item_position = int(xbmc.getInfoLabel('Container.CurrentItem') or '0')
        
        if final_item_label == ".." or final_item_label.strip() == "..":
            logger.warning("%s ❌ SUBSTEP 6 FAILED: Still on parent item after navigation attempt", LOG_PREFIX)
            return False
        
        logger.debug("%s SUBSTEP 6 COMPLETE: On target item - Position: %s, Label: '%s', DBID: %s", LOG_PREFIX, final_item_position, final_item_label, final_item_dbid)
        substep6_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 6 TIMING: %.3fs", LOG_PREFIX, substep6_end - substep6_start)
        
        # Brief pause between SUBSTEP 6 and 7 for UI stability
        xbmc.sleep(50)
        
        # 🎬 SUBSTEP 7: Open info from the native list (this gets full metadata population)
        substep7_start = time.perf_counter()
        logger.debug("%s SUBSTEP 7: Opening video info from native list", LOG_PREFIX)
        pre_info_dialog_id = xbmcgui.getCurrentWindowDialogId()
        start_info_time = time.perf_counter()
        logger.debug("%s SUBSTEP 7 DEBUG: About to execute Action(Info) at %.3fs", LOG_PREFIX, start_info_time - overall_start_time)
        xbmc.executebuiltin('Action(Info)')
        action_info_end = time.perf_counter()
        logger.debug("%s SUBSTEP 7 DEBUG: Action(Info) command executed in %.3fs", LOG_PREFIX, action_info_end - start_info_time)
        
        # Brief pause between SUBSTEP 7 and 8 for UI stability
        xbmc.sleep(50)
        
        # ⌛ SUBSTEP 8: Wait for the native info dialog to appear
        substep8_start = time.perf_counter()
        logger.debug("%s SUBSTEP 8: Waiting for native info dialog to appear (extended timeout for network storage)", LOG_PREFIX)
        dialog_wait_start = time.perf_counter()
        success = _wait_for_info_dialog(timeout=10.0)
        dialog_wait_end = time.perf_counter()
        end_info_time = time.perf_counter()
        post_info_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        if success:
            logger.debug("%s SUBSTEP 8 COMPLETE: Native info dialog opened in %.3fs", LOG_PREFIX, end_info_time - start_info_time)
            logger.debug("%s SUBSTEP 8 STATUS: Dialog ID changed from %d to %d", LOG_PREFIX, pre_info_dialog_id, post_info_dialog_id)
            logger.debug("%s HIJACK HELPERS: Native info hijack completed successfully for %s %d", LOG_PREFIX, db_type, db_id)
        else:
            logger.warning("%s ❌ SUBSTEP 8 FAILED: Failed to open native info after %.3fs", LOG_PREFIX, end_info_time - start_info_time)
            logger.warning("%s SUBSTEP 8 DEBUG: Dialog ID remains %d (was %d)", LOG_PREFIX, post_info_dialog_id, pre_info_dialog_id)
            logger.warning("%s 💥 HIJACK HELPERS: ❌ Failed to open native info after hijack for %s %d", LOG_PREFIX, db_type, db_id)
        
        substep8_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 8 TIMING: %.3fs (dialog wait: %.3fs)", LOG_PREFIX, substep8_end - substep8_start, dialog_wait_end - dialog_wait_start)
        
        overall_end_time = time.perf_counter()
        logger.debug("%s ⏱️ OVERALL HIJACK TIMING: %.3fs", LOG_PREFIX, overall_end_time - overall_start_time)
        logger.debug("%s ⏱️ TIMING BREAKDOWN: S1=%.3fs, S2=%.3fs, S3+4=%.3fs, S5=%.3fs, S6=%.3fs, S7+8=%.3fs", LOG_PREFIX, substep1_end - substep1_start, substep2_end - substep2_start, substep4_end - substep3_start, substep5_end - substep5_start, substep6_end - substep6_start, substep8_end - substep7_start)
            
        return success
    except Exception as e:
        logger.error("%s 💥 HIJACK HELPERS: Exception in hijack process for %s %d: %s", LOG_PREFIX, db_type, db_id, e)
        import traceback
        logger.error("%s HIJACK HELPERS: Traceback: %s", LOG_PREFIX, traceback.format_exc())
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

    _log("Restoring container to: %s (position: %s)" % (orig_path, position))

    # Reduced delay for faster response, but still safe
    xbmc.sleep(50)

    # Restore the container
    xbmc.executebuiltin('Container.Update("%s",replace)' % orig_path)

    # Extended timeout for slower hardware, but less frequent polling
    t_start = time.perf_counter()
    updated = wait_until(
        lambda: (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/') == orig_path.rstrip('/'),
        timeout_ms=6000,  # Extended timeout for slower devices
        step_ms=150       # Less frequent polling to reduce overhead
    )

    if updated and position > 0:
        # Restore position with minimal delay
        _log("Restoring list position to: %s" % position)
        xbmc.sleep(25)  # Reduced delay
        xbmc.executebuiltin('Action(SelectItem,%s)' % position)

    t_end = time.perf_counter()
    _log("Container restore completed in %.3fs, success: %s" % (t_end - t_start, updated))

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
        _log("Opening movie info for dbid=%d, url=%s" % (dbid, movie_url))

        if not xsp_path:
            # Use consistent hijack file in addon userdata directory
            import xbmcaddon
            addon = xbmcaddon.Addon()
            profile_dir = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
            hijack_dir = os.path.join(profile_dir, 'hijack')
            xsp_path = os.path.join(hijack_dir, "lg_hijack_temp.xsp")

        _log("Using XSP path: %s" % xsp_path)

        # -------- precise timings --------
        t_total0 = time.perf_counter()
        t1 = time.perf_counter()
        _log("Opening Videos window with path: %s (t+%.3fs)" % (xsp_path, t1 - t_total0))

        # Open the Videos window on the XSP and focus the list
        xbmc.executebuiltin('ActivateWindow(Videos,"%s",return)' % xsp_path)

        # Wait for control to exist & focus it
        t_focus0 = time.perf_counter()
        focused = focus_list()
        t_focus1 = time.perf_counter()
        if not focused:
            _log("Failed to focus control (focus wait %.3fs)" % (t_focus1 - t_focus0), xbmc.LOGWARNING)
            return False

        # We reached the point where the native dialog should pop; block until it does
        t_dialog0 = time.perf_counter()
        opened = _wait_for_info_dialog()
        t_dialog1 = time.perf_counter()

        if opened:
            _log("✅ Native Info dialog opened (open_window %.3fs, focus %.3fs, dialog_wait %.3fs, total %.3fs)" % (t_focus0 - t1, t_focus1 - t_focus0, t_dialog1 - t_dialog0, t_dialog1 - t_total0))
            _log("🎉 Successfully completed hijack for movie %d" % dbid)
            return True
        else:
            _log("❌ Failed to open native info for movie %d (open_window %.3fs, focus %.3fs, dialog_wait %.3fs, total %.3fs)" % (dbid, t_focus0 - t1, t_focus1 - t_focus0, t_dialog1 - t_dialog0, t_dialog1 - t_total0), xbmc.LOGWARNING)
            return False

    except Exception as e:
        _log("Failed to open movie info: %s" % e, xbmc.LOGERROR)
        return False