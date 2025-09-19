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

from lib.utils.kodi_log import get_kodi_logger
from lib.utils.kodi_version import get_version_specific_control_id
from lib.ui.localization import L
from lib.ui.navigation_cache import get_cached_info, get_navigation_snapshot, navigation_action
from lib.ui.dialogs.video_info import is_video_info_active

logger = get_kodi_logger('lib.ui.info_hijack_helpers')

LOG_PREFIX = "[LG.Hijack]"
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

class ExpectedTarget:
    """Structure to hold expected target item information for focus verification"""
    def __init__(self, db_type: Optional[str] = None, db_id: Optional[int] = None, filename: Optional[str] = None, 
                 filename_no_ext: Optional[str] = None, expected_index: Optional[int] = None, 
                 expected_label: Optional[str] = None, expected_year: Optional[str] = None):
        self.db_type = db_type
        self.db_id = db_id  
        self.filename = filename
        self.filename_no_ext = filename_no_ext
        self.expected_index = expected_index
        self.expected_label = expected_label
        self.expected_year = expected_year

def verify_list_focus(expected: Optional[ExpectedTarget] = None) -> bool:
    """Check if focus is on the intended item with comprehensive identity verification"""
    try:
        # Get detailed focus information for debugging
        view_mode = get_cached_info("Container.Viewmode").lower().strip()
        current_item_label = get_cached_info("Container.ListItem().Label")
        current_item_index = int(get_cached_info("Container.CurrentItem") or "0")
        num_items = get_cached_info("Container.NumItems") 
        current_window = get_cached_info("System.CurrentWindow")
        current_control = get_cached_info("System.CurrentControlId")
        container_path = get_cached_info("Container.FolderPath")
        
        # Get additional identity information if available
        current_dbid = get_cached_info("Container.ListItem().DBID")
        current_dbtype = get_cached_info("Container.ListItem().DBType")  
        current_filepath = get_cached_info("Container.ListItem().FilenameAndPath")
        current_year = get_cached_info("Container.ListItem().Year")
        
        # Comprehensive debug output
        _log("verify_list_focus DEBUG - Focus state analysis:", xbmc.LOGDEBUG)
        _log("  Current window: %s", xbmc.LOGDEBUG, current_window)
        _log("  Current control: %s", xbmc.LOGDEBUG, current_control) 
        _log("  Container path: %s", xbmc.LOGDEBUG, container_path)
        _log("  View mode: '%s'", xbmc.LOGDEBUG, view_mode)
        _log("  Focused item label: '%s'", xbmc.LOGDEBUG, current_item_label)
        _log("  Current item index: %s", xbmc.LOGDEBUG, current_item_index)
        _log("  Total items in container: %s", xbmc.LOGDEBUG, num_items)
        _log("  Current DBID: %s", xbmc.LOGDEBUG, current_dbid)
        _log("  Current DBType: %s", xbmc.LOGDEBUG, current_dbtype)
        _log("  Current filepath: %s", xbmc.LOGDEBUG, current_filepath)
        _log("  Current year: %s", xbmc.LOGDEBUG, current_year)
        
        if expected:
            _log("  Expected target - DBID: %s, DBType: %s, filename: %s, index: %s, label: %s, year: %s", 
                 xbmc.LOGDEBUG, expected.db_id, expected.db_type, expected.filename_no_ext, 
                 expected.expected_index, expected.expected_label, expected.expected_year)
        
        # Step 1: Log current control for debugging (no longer enforce specific control ID)
        _log("verify_list_focus: Current control ID: %s", xbmc.LOGDEBUG, current_control)
        
        # Step 2: Basic sanity - not on parent directory  
        if current_item_label == ".." or current_item_label.strip() == "..":
            _log("verify_list_focus: FAILED - Focus is on parent directory '..' - need navigation", xbmc.LOGDEBUG)
            return False
            
        # Step 3: Must have some focused item
        if not current_item_label or current_item_label.strip() == "":
            _log("verify_list_focus: FAILED - No focused item detected", xbmc.LOGDEBUG)
            return False
            
        # Step 4: If we have expected target, perform identity verification (priority order)
        if expected:
            # Priority 1: Match DBID and DBType (most reliable)
            if expected.db_id and expected.db_type and current_dbid and current_dbtype:
                if str(current_dbid) == str(expected.db_id) and current_dbtype.lower() == expected.db_type.lower():
                    _log("verify_list_focus: SUCCESS - Perfect match on DBID %s and DBType %s", 
                         xbmc.LOGDEBUG, current_dbid, current_dbtype)
                    return True
                else:
                    _log("verify_list_focus: FAILED - DBID/DBType mismatch (current: %s/%s, expected: %s/%s)", 
                         xbmc.LOGDEBUG, current_dbid, current_dbtype, expected.db_id, expected.db_type)
                    return False
                    
            # Priority 2: Match filename/path
            if expected.filename_no_ext and current_filepath:
                if expected.filename_no_ext in current_filepath:
                    _log("verify_list_focus: SUCCESS - Filename match ('%s' in '%s')", 
                         xbmc.LOGDEBUG, expected.filename_no_ext, current_filepath)
                    return True
                else:
                    _log("verify_list_focus: FAILED - Filename mismatch ('%s' not in '%s')", 
                         xbmc.LOGDEBUG, expected.filename_no_ext, current_filepath)
                    return False
                    
            # Priority 3: Match expected index position
            if expected.expected_index is not None:
                if current_item_index == expected.expected_index:
                    _log("verify_list_focus: SUCCESS - Index match (position %s)", xbmc.LOGDEBUG, current_item_index)
                    return True
                else:
                    _log("verify_list_focus: FAILED - Index mismatch (current: %s, expected: %s)", 
                         xbmc.LOGDEBUG, current_item_index, expected.expected_index)
                    return False
                    
            # Priority 4: Label + year heuristic (last resort)
            if expected.expected_label:
                label_match = expected.expected_label.lower() in current_item_label.lower()
                year_match = (not expected.expected_year or 
                            (current_year and expected.expected_year in current_year))
                
                if label_match and year_match:
                    _log("verify_list_focus: SUCCESS - Label+year heuristic match", xbmc.LOGDEBUG)
                    return True
                else:
                    _log("verify_list_focus: FAILED - Label+year mismatch (label_match: %s, year_match: %s)", 
                         xbmc.LOGDEBUG, label_match, year_match)
                    return False
                    
            # If expected was provided but no matches found
            _log("verify_list_focus: FAILED - Expected target provided but no identity matches found", xbmc.LOGDEBUG)
            return False
        
        # Step 5: If no expected target, just verify we're in a valid list view with content
        if not view_mode:
            _log("verify_list_focus: WARNING - No viewmode detected, but have content item '%s' - assuming valid", 
                 xbmc.LOGDEBUG, current_item_label)
            return True
            
        # Define view types  
        VERTICAL_VIEWS = {"list", "widelist", "lowlist", "bannerlist", "biglist", 
                         "infolist", "detaillist", "episodes", "songs"}
        HORIZONTAL_VIEWS = {"wall", "poster", "panel", "thumbs", "iconwall", "fanart",
                           "shift", "showcase", "thumbnails", "icons", "grid", "wrap"}
        
        in_list_view = (view_mode in VERTICAL_VIEWS or view_mode in HORIZONTAL_VIEWS or
                       any(v in view_mode for v in VERTICAL_VIEWS | HORIZONTAL_VIEWS))
        
        if not in_list_view:
            _log("verify_list_focus: FAILED - Unknown viewmode '%s'", xbmc.LOGDEBUG, view_mode)
            return False
            
        _log("verify_list_focus: SUCCESS - Valid content focus in %s view (no specific target expected)", 
             xbmc.LOGDEBUG, view_mode)
        return True
        
    except Exception as e:
        _log("Error in verify_list_focus: %s - defaulting to FALSE", xbmc.LOGWARNING, e)
        return False

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
        # Pre-check: If already focused on target item (not parent ".."), no navigation needed
        current_item_label = get_cached_info("Container.ListItem().Label")
        _log("focus_list_manual: Current focused item label = '%s'", xbmc.LOGDEBUG, current_item_label)
        
        if current_item_label != ".." and current_item_label.strip() != "..":
            t_focus_end = time.perf_counter()
            _log("focus_list_manual: Already focused on target item '%s' - no navigation needed (%.3fs)", xbmc.LOGDEBUG, current_item_label, t_focus_end - t_focus_start)
            return True
        
        _log("focus_list_manual: Currently on parent item '%s' - navigation required", xbmc.LOGDEBUG, current_item_label)
        
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

def focus_list_xsp_optimized(expected_index: int = 0, tries: int = 3, step_ms: int = 100) -> bool:
    """Optimized focus for XSP context - no expensive verify_list_focus calls needed
    
    XSP structure is predictable:
    - Index 0: Target item (if no parent) 
    - Index 1: Target item (if parent ".." exists at index 0)
    """
    t_focus_start = time.perf_counter()
    
    _log("focus_list_xsp_optimized: Starting optimized XSP focus (expected_index=%d)", xbmc.LOGDEBUG, expected_index)
    
    # Check current item label - if it's parent "..", navigate to target
    current_label = get_cached_info("Container.ListItem().Label")
    if current_label == ".." or current_label.strip() == "..":
        _log("focus_list_xsp_optimized: Currently on parent '..', navigating to target at index %d", xbmc.LOGDEBUG, expected_index)
        
        # Simple navigation - just move to the target index
        for attempt in range(tries):
            _log("focus_list_xsp_optimized: Navigation attempt %d", xbmc.LOGDEBUG, attempt + 1)
            
            with navigation_action(grace_ms=step_ms):
                xbmc.executebuiltin("Action(Down)")  # Move from parent to content
                xbmc.sleep(step_ms)
            
            # Check if we moved off parent
            new_label = get_cached_info("Container.ListItem().Label")
            if new_label != ".." and new_label.strip() != "..":
                t_focus_end = time.perf_counter()
                _log("focus_list_xsp_optimized: SUCCESS - Moved to target item '%s' (%.3fs)", xbmc.LOGDEBUG, new_label, t_focus_end - t_focus_start)
                return True
            
            _log("focus_list_xsp_optimized: Still on parent after attempt %d", xbmc.LOGDEBUG, attempt + 1)
        
        t_focus_end = time.perf_counter()
        _log("focus_list_xsp_optimized: FAILED - Could not move off parent (%.3fs)", xbmc.LOGWARNING, t_focus_end - t_focus_start)
        return False
    else:
        # Already on content item - assume it's correct since XSP guarantees target item
        t_focus_end = time.perf_counter()
        _log("focus_list_xsp_optimized: Already on content item '%s' - assuming correct (%.3fs)", xbmc.LOGDEBUG, current_label, t_focus_end - t_focus_start)
        return True

def focus_list(expected: Optional[ExpectedTarget] = None, control_id: Optional[int] = None, tries: int = 3, step_ms: int = 100) -> bool:
    """Simplified, skin-agnostic focus logic that works with any container"""
    t_focus_start = time.perf_counter()
    
    _log("focus_list: Starting skin-agnostic focus verification", xbmc.LOGDEBUG)
    
    # Step 1: Check if already focused on intended item
    if verify_list_focus(expected):
        t_focus_end = time.perf_counter()
        _log("focus_list: Already focused on intended item - step 5 complete (%.3fs)", xbmc.LOGDEBUG, t_focus_end - t_focus_start)
        return True
    
    # Step 2: Check if we're on parent ".." and need navigation
    current_label = get_cached_info("Container.ListItem().Label")
    if current_label == ".." or current_label.strip() == "..":
        _log("focus_list: Currently on parent '..', attempting navigation to content", xbmc.LOGDEBUG)
        
        if navigate_from_parent_to_content(expected, tries, step_ms):
            t_focus_end = time.perf_counter()
            _log("focus_list: Successfully navigated to intended item (%.3fs)", xbmc.LOGDEBUG, t_focus_end - t_focus_start)
            return True
        else:
            t_focus_end = time.perf_counter()
            _log("focus_list: FAILED - Could not navigate to intended item (%.3fs)", xbmc.LOGWARNING, t_focus_end - t_focus_start)
            return False
    
    # Step 3: We're on some content item, but not the intended one
    t_focus_end = time.perf_counter()
    _log("focus_list: FAILED - Focused on wrong content item '%s' (%.3fs)", xbmc.LOGWARNING, current_label, t_focus_end - t_focus_start)
    return False

def navigate_from_parent_to_content(expected: Optional[ExpectedTarget] = None, tries: int = 3, step_ms: int = 100) -> bool:
    """Simple viewtype-based navigation from parent '..' to content item"""
    try:
        _log("navigate_from_parent_to_content: Starting navigation from parent to content", xbmc.LOGDEBUG)
        
        # Determine navigation direction based on viewtype
        view_mode = get_cached_info("Container.Viewmode").lower().strip()
        _log("navigate_from_parent_to_content: Detected viewmode = '%s'", xbmc.LOGDEBUG, view_mode)
        
        VERTICAL_VIEWS = {"list", "widelist", "lowlist", "bannerlist", "biglist", 
                         "infolist", "detaillist", "episodes", "songs"}
        HORIZONTAL_VIEWS = {"wall", "poster", "panel", "thumbs", "iconwall", "fanart",
                           "shift", "showcase", "thumbnails", "icons", "grid", "wrap"}
        
        # Determine primary navigation direction
        if view_mode in VERTICAL_VIEWS or any(v in view_mode for v in VERTICAL_VIEWS):
            nav_command = "Action(Down)"
            _log("navigate_from_parent_to_content: Using vertical navigation (Down)", xbmc.LOGDEBUG)
        elif view_mode in HORIZONTAL_VIEWS or any(v in view_mode for v in HORIZONTAL_VIEWS):
            nav_command = "Action(Right)"
            _log("navigate_from_parent_to_content: Using horizontal navigation (Right)", xbmc.LOGDEBUG)
        else:
            # Unknown viewtype - try Down first (most common), then Right
            _log("navigate_from_parent_to_content: Unknown viewmode - trying Down first", xbmc.LOGDEBUG)
            nav_command = "Action(Down)"
        
        # Attempt navigation with verification
        for attempt in range(tries):
            _log("navigate_from_parent_to_content: Attempt %d - sending %s", xbmc.LOGDEBUG, attempt + 1, nav_command)
            
            with navigation_action(grace_ms=step_ms):
                xbmc.executebuiltin(nav_command)
                xbmc.sleep(step_ms)
            
            # Check if we're no longer on parent
            current_label = get_cached_info("Container.ListItem().Label")
            if current_label != ".." and current_label.strip() != "..":
                _log("navigate_from_parent_to_content: Moved off parent to item '%s'", xbmc.LOGDEBUG, current_label)
                
                # Check if this is the intended item
                if verify_list_focus(expected):
                    _log("navigate_from_parent_to_content: SUCCESS - Found intended item '%s'", xbmc.LOGDEBUG, current_label)
                    return True
                else:
                    _log("navigate_from_parent_to_content: Reached content but wrong item '%s'", xbmc.LOGDEBUG, current_label)
                    # Continue trying - might reach the right item with more navigation
            else:
                _log("navigate_from_parent_to_content: Still on parent after attempt %d", xbmc.LOGDEBUG, attempt + 1)
        
        # If Down didn't work and we tried it for unknown viewtype, try Right
        if nav_command == "Action(Down)" and not view_mode in VERTICAL_VIEWS:
            _log("navigate_from_parent_to_content: Down didn't work for unknown viewtype - trying Right", xbmc.LOGDEBUG)
            nav_command = "Action(Right)"
            
            for attempt in range(tries):
                _log("navigate_from_parent_to_content: Right attempt %d", xbmc.LOGDEBUG, attempt + 1)
                
                with navigation_action(grace_ms=step_ms):
                    xbmc.executebuiltin(nav_command)
                    xbmc.sleep(step_ms)
                
                current_label = get_cached_info("Container.ListItem().Label")
                if current_label != ".." and current_label.strip() != "..":
                    _log("navigate_from_parent_to_content: Moved off parent with Right to item '%s'", xbmc.LOGDEBUG, current_label)
                    
                    if verify_list_focus(expected):
                        _log("navigate_from_parent_to_content: SUCCESS - Found intended item with Right navigation", xbmc.LOGDEBUG)
                        return True
        
        _log("navigate_from_parent_to_content: FAILED - Could not navigate to intended item", xbmc.LOGWARNING)
        return False
        
    except Exception as e:
        _log("Error in navigate_from_parent_to_content: %s", xbmc.LOGERROR, e)
        return False

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
        # OPTIMIZATION: Removed expensive Container.NumItems call - XSP always has exactly 1 item
        not_busy = True  # OPTIMIZATION: Removed DialogBusy check for performance
        
        # Additional check for progress dialogs that might appear during scanning
        not_scanning = not xbmc.getCondVisibility("Window.IsActive(DialogProgress.xml)")

        elapsed = time.perf_counter() - t_start
        
        # Track condition details for debugging (optimized: removed num_items)
        current_details = {
            'window_active': window_active,
            'path_match': path_match,
            'folder_path': folder_path,
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
        
        # More frequent logging for debugging delays (optimized: removed num_items)
        if int(elapsed * 2) % 3 == 0 and elapsed - int(elapsed * 2) / 2 < 0.05:  # Every 1.5 seconds
            _log("_wait_videos_on check (%.1fs): window=%s, path_match=%s ('%s' vs '%s'), not_busy=%s, not_scanning=%s", xbmc.LOGDEBUG, elapsed, window_active, path_match, folder_path, t_norm, not_busy, not_scanning)

        # OPTIMIZATION: Removed num_items > 0 check - XSP always contains exactly the target item
        # But require conditions to be stable for 2-3 polls to prevent race conditions
        basic_condition = window_active and path_match and not_busy and not_scanning
        if basic_condition:
            condition_met_count += 1
            _log("_wait_videos_on: CONDITIONS MET at %.3fs (count: %d)", xbmc.LOGDEBUG, elapsed, condition_met_count)
            # Require 2 consecutive successful checks for stability (~200ms)
            if condition_met_count >= 2:
                _log("_wait_videos_on: ALL CONDITIONS STABLE at %.3fs (count: %d)", xbmc.LOGDEBUG, elapsed, condition_met_count)
                return True
        else:
            condition_met_count = 0

        return False

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
        # Log final state for debugging (optimized: removed expensive Container.NumItems call)
        final_window = xbmc.getCondVisibility(f"Window.IsActive({VIDEOS_WINDOW})")
        final_path = (xbmc.getInfoLabel("Container.FolderPath") or "").rstrip('/')
        final_busy = xbmc.getCondVisibility("Window.IsActive(DialogBusy.xml)")
        final_progress = xbmc.getCondVisibility("Window.IsActive(DialogProgress.xml)")
        _log("_wait_videos_on FINAL STATE: window=%s, path='%s', busy=%s, progress=%s", xbmc.LOGWARNING, final_window, final_path, final_busy, final_progress)

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
        
        # ✅ PRECONDITION CHECK: Ensure no video info dialog is active
        # Dialog closing should have been handled by the manager before calling this function
        if is_video_info_active():
            current_dialog_id = xbmcgui.getCurrentWindowDialogId()
            logger.error("%s ❌ PRECONDITION FAILED: Video info dialog still active (ID: %d)", LOG_PREFIX, current_dialog_id)
            logger.error("%s Manager should have closed dialog before calling open_native_info_fast", LOG_PREFIX)
            return False
        
        logger.debug("%s ✅ PRECONDITION OK: No video info dialog detected, proceeding with XSP navigation", LOG_PREFIX)
        
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
        # OPTIMIZATION: Removed expensive Container.NumItems call - XSP structure is predictable
        logger.debug("%s SUBSTEP 4 COMPLETE: Videos window loaded in %.3fs", LOG_PREFIX, end_nav_time - start_nav_time)
        logger.debug("%s SUBSTEP 4 STATUS: Window %d→%d, path='%s'", LOG_PREFIX, current_window_before, current_window_after, current_path)
        substep4_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 4 TIMING: %.3fs (wait: %.3fs)", LOG_PREFIX, substep4_end - substep4_start, wait_end - wait_start)
        logger.debug("%s ⏱️ SUBSTEP 3+4 COMBINED TIMING: %.3fs", LOG_PREFIX, substep4_end - substep3_start)
        
        # 🎯 SUBSTEP 5: Focus the list and find our item
        substep5_start = time.perf_counter()
        logger.debug("%s SUBSTEP 5: Focusing list to locate %s %d", LOG_PREFIX, db_type, db_id)
        
        # Create expected target for focus verification
        # OPTIMIZATION: Simplified XSP index logic - check if on parent instead of counting items
        current_label = xbmc.getInfoLabel('ListItem.Label')
        expected_index = 1 if current_label == ".." else 0  # If on parent, target is at index 1
        
        expected = ExpectedTarget(
            db_type=db_type,
            db_id=db_id,
            expected_index=expected_index
        )
        
        start_focus_time = time.perf_counter()
        # OPTIMIZATION: Use simplified XSP focus instead of expensive verify_list_focus calls
        if not focus_list_xsp_optimized(expected_index=expected.expected_index):
            end_focus_time = time.perf_counter()
            logger.warning("%s ❌ SUBSTEP 5 FAILED: Failed to focus list control after %.3fs", LOG_PREFIX, end_focus_time - start_focus_time)
            return False
        end_focus_time = time.perf_counter()
        logger.debug("%s SUBSTEP 5 COMPLETE: List focused in %.3fs", LOG_PREFIX, end_focus_time - start_focus_time)
        substep5_end = time.perf_counter()
        logger.debug("%s ⏱️ SUBSTEP 5 TIMING: %.3fs", LOG_PREFIX, substep5_end - substep5_start)
        
        # 📍 SUBSTEP 6: Verify we're focused on target item (parent navigation now handled in focus_list_manual)
        substep6_start = time.perf_counter()
        logger.debug("%s SUBSTEP 6: Verifying focus on target item", LOG_PREFIX)
        
        # Get current item details for verification
        final_item_label = xbmc.getInfoLabel('ListItem.Label')
        final_item_dbid = xbmc.getInfoLabel('ListItem.DBID')
        # OPTIMIZATION: Removed expensive Container.CurrentItem call - only used for debug logging
        
        # Verify we're not on parent item (should be handled by optimized focus_list_manual)
        if final_item_label == ".." or final_item_label.strip() == "..":
            logger.warning("%s ❌ SUBSTEP 6 FAILED: Still on parent item - focus_list_manual should have handled this", LOG_PREFIX)
            return False
        
        logger.debug("%s SUBSTEP 6 COMPLETE: On target item - Label: '%s', DBID: %s", LOG_PREFIX, final_item_label, final_item_dbid)
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