# test_info_variants.py — focused harness for Matrix (v19) and Nexus+ (v20+)
from __future__ import annotations
import json
import time
import os
import html
from urllib.parse import urlencode, parse_qs

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

# ------------------------------
# Config / constants
# ------------------------------
LOG_PREFIX = "[InfoHarness]"
LIST_ID = 55                 # Estuary main list control in MyVideoNav.xml
VIDEOS_WINDOW = "MyVideoNav.xml"

# ------------------------------
# Logging / utils
# ------------------------------
def _log(msg: str, level=xbmc.LOGINFO):
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

def notify(heading: str, message: str, time_ms: int = 3500):
    xbmcgui.Dialog().notification(heading, message, xbmcgui.NOTIFICATION_INFO, time_ms)

def discover_controls() -> dict:
    """Discover available controls in current window"""
    controls = {}
    
    # Test common list control IDs
    test_ids = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]
    
    for control_id in test_ids:
        exists = xbmc.getCondVisibility(f'Control.IsEnabled({control_id})')
        visible = xbmc.getCondVisibility(f'Control.IsVisible({control_id})')
        focusable = xbmc.getCondVisibility(f'ControlGroup({control_id}).HasFocus(0)') or exists
        
        if exists or visible:
            controls[control_id] = {
                'exists': exists,
                'visible': visible,
                'focusable': focusable
            }
    
    return controls

def focus_list(control_id: int = LIST_ID, tries: int = 10, sleep_ms: int = 50) -> bool:
    _log(f"FOCUS_LIST: Attempting to focus control {control_id} (max {tries} tries, {sleep_ms}ms sleep)")
    
    for attempt in range(tries):
        xbmc.executebuiltin(f'SetFocus({control_id})')
        focused = xbmc.getCondVisibility(f'Control.HasFocus({control_id})')
        current_focus = xbmc.getInfoLabel('System.CurrentControlId')
        
        if focused:
            _log(f"FOCUS_LIST: SUCCESS on attempt {attempt + 1} - control {control_id} now focused")
            return True
        
        if attempt < 3 or attempt == tries - 1:  # Log first few and last attempt
            _log(f"FOCUS_LIST: Attempt {attempt + 1} failed - current focus: {current_focus}")
        
        xbmc.sleep(sleep_ms)
    
    _log(f"FOCUS_LIST: FAILED after {tries} attempts - final focus: {xbmc.getInfoLabel('System.CurrentControlId')}")
    return False

def wait_for_videos_container(target_path: str, timeout_ms: int = 6000) -> bool:
    """Wait until Videos window shows target_path as Container.FolderPath, has items, and no busy dialog."""
    mon = xbmc.Monitor()
    t_norm = (target_path or '').rstrip('/')
    start = int(time.time() * 1000)
    while (int(time.time() * 1000) - start) < timeout_ms and not mon.abortRequested():
        if not xbmc.getCondVisibility(f'Window.IsActive({VIDEOS_WINDOW})'):
            xbmc.sleep(120)
            continue
        cur = (xbmc.getInfoLabel('Container.FolderPath') or '').rstrip('/')
        num = int(xbmc.getInfoLabel('Container.NumItems') or '0')
        busy = xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)')
        if cur == t_norm and num > 0 and not busy:
            return True
        xbmc.sleep(120)
    return False

# ------------------------------
# Matrix (v19): XSP via path + filename (no fallback)
# ------------------------------
def _ensure_dir(special_dir: str):
    """Ensure directory exists using xbmcvfs, handling special:// paths properly"""
    try:
        if not special_dir or special_dir == "special://":
            return
        
        # Clean up the path
        path = special_dir.rstrip('/')
        
        # Don't try to create the root special:// directory
        if path == "special:":
            return
            
        # Check if directory already exists
        if xbmcvfs.exists(path + '/'):
            return
            
        # Create directory
        if not xbmcvfs.mkdir(path):
            _log(f"Failed to create directory: {path}", xbmc.LOGDEBUG)
            
    except Exception as e:
        _log(f"Directory creation error for {special_dir}: {e}", xbmc.LOGDEBUG)

def _write_text(path_special: str, text: str) -> bool:
    try:
        f = xbmcvfs.File(path_special, 'w')
        f.write(text.encode('utf-8'))
        f.close()
        return True
    except Exception as e:
        _log(f"xbmcvfs write failed: {e}", xbmc.LOGWARNING)
        return False

def _get_movie_file(movieid: int) -> str | None:
    data = jsonrpc("VideoLibrary.GetMovieDetails", {
        "movieid": int(movieid),
        "properties": ["file"]
    })
    md = (data.get("result") or {}).get("moviedetails") or {}
    return md.get("file")

def _create_movie_xsp_by_path(movieid: int) -> str | None:
    file_path = _get_movie_file(movieid)
    if not file_path:
        _log("No file path from JSON-RPC for movieid={}".format(movieid), xbmc.LOGWARNING)
        return None

    _log(f"Got file path for movie {movieid}: {file_path}")
    
    # Use filename for more specific matching
    import os
    filename = os.path.basename(file_path)
    _log(f"Using filename for XSP: {filename}")
    
    xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
    <name>LibraryGenie Test - Movie {movieid}</name>
    <match>all</match>
    <rule field="filename" operator="is">
        <value>{html.escape(filename)}</value>
    </rule>
    <order direction="ascending">title</order>
</smartplaylist>"""

    # Use temp directory directly - Kodi's playlists directory might have permissions issues
    xsp_path = f"special://temp/libgenie_{movieid}.xsp"

    if _write_text(xsp_path, xsp):
        _log(f"Wrote XSP to {xsp_path}")
        return xsp_path
    return None

def _cleanup_xsp(path_special: str):
    try:
        if path_special and xbmcvfs.exists(path_special):
            xbmcvfs.delete(path_special)
            _log(f"Removed XSP {path_special}")
    except Exception as e:
        _log(f"Cleanup failed: {e}", xbmc.LOGDEBUG)

def show_info_matrix(movieid: int):
    kodi_ver = kodi_major()
    _log(f"=== MATRIX TEST START: movie {movieid} on Kodi v{kodi_ver} ===")
    
    if kodi_ver != 19:
        _log(f"WARNING: Matrix path requested on Kodi {kodi_ver} — designed for v19.", xbmc.LOGWARNING)

    # Step 0: Verify movie exists in library
    _log("STEP 0: Verifying movie exists in library...")
    movie_data = jsonrpc("VideoLibrary.GetMovieDetails", {
        "movieid": int(movieid),
        "properties": ["title", "file", "imdbnumber"]
    })
    movie_details = (movie_data.get("result") or {}).get("moviedetails")
    if not movie_details:
        _log(f"STEP 0: FAILED - Movie {movieid} not found in library", xbmc.LOGERROR)
        notify("Matrix test", f"Movie {movieid} not found")
        return
    
    movie_title = movie_details.get("title", "Unknown")
    movie_file = movie_details.get("file", "")
    movie_imdb = movie_details.get("imdbnumber", "")
    _log(f"STEP 0: SUCCESS - Found movie: {movie_title} (file: {movie_file}, imdb: {movie_imdb})")
    
    # Step 1: Create XSP
    _log("STEP 1: Creating XSP filter...")
    xsp_path = _create_movie_xsp_by_path(movieid)
    if not xsp_path:
        _log("STEP 1: FAILED - Could not create XSP", xbmc.LOGERROR)
        notify("Matrix test", "Failed to create smart playlist")
        return
    _log(f"STEP 1: SUCCESS - XSP created at {xsp_path}")

    # Step 2: Navigate to XSP
    _log("STEP 2: Navigating to XSP...")
    _log(f"STEP 2: Executing ActivateWindow(Videos,\"{xsp_path}\",return)")
    xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')
    
    # Step 3: Wait for container
    _log("STEP 3: Waiting for container to load...")
    if not wait_for_videos_container(xsp_path, timeout_ms=8000):  # Increased timeout
        _log("STEP 3: FAILED - Timeout waiting for XSP container", xbmc.LOGERROR)
        notify("Matrix test", "Timed out waiting for playlist")
        _cleanup_xsp(xsp_path)
        return
    
    container_items = xbmc.getInfoLabel('Container.NumItems')
    _log(f"STEP 3: SUCCESS - Container loaded with {container_items} items")
    
    # Step 4: Enhanced window state analysis
    _log("STEP 4: Analyzing window state...")
    xbmc.sleep(750)  # Give more time for UI to settle
    
    # Get comprehensive window state
    current_window = xbmc.getInfoLabel('System.CurrentWindow')
    current_control = xbmc.getInfoLabel('System.CurrentControl')
    focused_control = xbmc.getInfoLabel('System.CurrentControlId')
    container_path = xbmc.getInfoLabel('Container.FolderPath')
    container_content = xbmc.getInfoLabel('Container.Content')
    
    _log(f"STEP 4: Window={current_window}, Control={current_control}, FocusedId={focused_control}")
    _log(f"STEP 4: Container.FolderPath={container_path}")
    _log(f"STEP 4: Container.Content={container_content}")
    
    # Get current item info
    if container_items and int(container_items) > 0:
        current_title = xbmc.getInfoLabel('ListItem.Title')
        current_dbid = xbmc.getInfoLabel('ListItem.DBID')
        current_path = xbmc.getInfoLabel('ListItem.Path')
        _log(f"STEP 4: Current item - Title: {current_title}, DBID: {current_dbid}, Path: {current_path}")
    
    # Discover available controls
    _log("STEP 4: Discovering available controls...")
    controls = discover_controls()
    for cid, info in controls.items():
        _log(f"STEP 4: Control {cid}: exists={info['exists']}, visible={info['visible']}, focusable={info['focusable']}")
    
    # Find best list control candidate
    list_candidates = [cid for cid, info in controls.items() if info['visible'] and info['exists']]
    _log(f"STEP 4: List control candidates: {list_candidates}")
    
    # Step 5: Enhanced info dialog attempts
    _log("STEP 5: Attempting to open info dialog...")
    success = False
    method_results = []
    
    # Method 1: Stay in XSP context and navigate to movie item
    _log("METHOD 1: XSP context with proper item navigation...")
    
    # Make sure we're still in the XSP view with the movie selected
    container_path = xbmc.getInfoLabel('Container.FolderPath').rstrip('/')
    xsp_path_norm = xsp_path.rstrip('/')
    
    if container_path == xsp_path_norm:
        _log("METHOD 1: Still in XSP context, focusing and navigating to movie")
        
        # Focus the correct list control (50 based on logs)
        if focus_list(50, tries=3, sleep_ms=150):
            _log("METHOD 1: List control 50 focused, checking initial selection")
            current_title = xbmc.getInfoLabel('ListItem.Title')
            current_dbid = xbmc.getInfoLabel('ListItem.DBID')
            current_path = xbmc.getInfoLabel('ListItem.Path')
            _log(f"METHOD 1: Initial item - Title: '{current_title}', DBID: '{current_dbid}', Path: '{current_path}'")
            
            # Navigate down to find the movie (skip ".." parent entry)
            _log("METHOD 1: Navigating to find movie item...")
            max_nav_attempts = 5
            for nav_attempt in range(max_nav_attempts):
                current_title = xbmc.getInfoLabel('ListItem.Title')
                current_dbid = xbmc.getInfoLabel('ListItem.DBID')
                current_path = xbmc.getInfoLabel('ListItem.Path')
                current_filename = xbmc.getInfoLabel('ListItem.FileNameAndPath')
                
                _log(f"METHOD 1: Nav attempt {nav_attempt + 1} - Title: '{current_title}', DBID: '{current_dbid}', Path: '{current_path}'")
                
                # Check if this is a valid movie item (has title and dbid, not parent)
                if current_title and current_dbid and current_title != ".." and not current_path.endswith("plugin.video.librarygenie/"):
                    _log(f"METHOD 1: Found movie item: {current_title} (DBID: {current_dbid})")
                    break
                
                # Try moving down to next item
                _log("METHOD 1: Moving to next item...")
                xbmc.executebuiltin('Action(Down)')
                xbmc.sleep(300)  # Give more time for navigation
            else:
                _log("METHOD 1: Could not find movie item after navigation attempts")
                
                # Try an alternative approach - move to end and back
                _log("METHOD 1: Trying alternative navigation - move to end first")
                xbmc.executebuiltin('Action(End)')
                xbmc.sleep(300)
                current_title = xbmc.getInfoLabel('ListItem.Title')
                current_dbid = xbmc.getInfoLabel('ListItem.DBID')
                _log(f"METHOD 1: After End - Title: '{current_title}', DBID: '{current_dbid}'")
                
                if not current_title or current_title == "..":
                    # Move up one item
                    xbmc.executebuiltin('Action(Up)')
                    xbmc.sleep(300)
                    current_title = xbmc.getInfoLabel('ListItem.Title')
                    current_dbid = xbmc.getInfoLabel('ListItem.DBID')
                    _log(f"METHOD 1: After Up from End - Title: '{current_title}', DBID: '{current_dbid}'")
            
            # Final check for valid movie item
            current_title = xbmc.getInfoLabel('ListItem.Title')
            current_dbid = xbmc.getInfoLabel('ListItem.DBID')
            current_path = xbmc.getInfoLabel('ListItem.Path')
            
            if current_title and current_dbid and current_title != ".." and not current_path.endswith("plugin.video.librarygenie/"):
                _log(f"METHOD 1: Attempting info for movie: {current_title} (DBID: {current_dbid})")
                
                # Try Action(Info) first since we're now on the movie item
                _log("METHOD 1: Sending Action(Info)")
                xbmc.executebuiltin('Action(Info)')
                xbmc.sleep(1000)  # Give more time for dialog to open
                
                info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)') or \
                           xbmc.getCondVisibility('Window.IsActive(movieinformation.xml)')
                _log(f"METHOD 1: Info dialog open via Action(Info): {info_open}")
                method_results.append(f"Method1: action_info_on_movie, info_open={info_open}")
                
                if not info_open:
                    # Fallback to JSON-RPC with videodb path
                    videodb_path = f"videodb://movies/titles/{movieid}"
                    _log(f"METHOD 1: Fallback - Opening info via JSON-RPC with path: {videodb_path}")
                    
                    json_result = jsonrpc("GUI.ActivateWindow", {
                        "window": "movieinformation",
                        "parameters": [videodb_path]
                    })
                    _log(f"METHOD 1: JSON-RPC result: {json_result}")
                    xbmc.sleep(1000)
                    
                    info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)') or \
                               xbmc.getCondVisibility('Window.IsActive(movieinformation.xml)')
                    _log(f"METHOD 1: Info dialog open via JSON-RPC fallback: {info_open}")
                    method_results.append(f"Method1: jsonrpc_videodb_fallback, info_open={info_open}")
                
                if info_open:
                    success = True
            else:
                _log(f"METHOD 1: Still no valid movie item selected - Title: '{current_title}', DBID: '{current_dbid}', Path: '{current_path}'")
                method_results.append("Method1: no_valid_movie_item, info_open=False")
        else:
            _log("METHOD 1: Could not focus list control 50")
            method_results.append("Method1: focus_failed, info_open=False")
    else:
        _log(f"METHOD 1: Not in XSP context anymore. Current: {container_path}, Expected: {xsp_path_norm}")
        # Try to navigate back to XSP
        _log("METHOD 1: Attempting to return to XSP...")
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')
        xbmc.sleep(500)
        if wait_for_videos_container(xsp_path, timeout_ms=3000):
            _log("METHOD 1: Back in XSP, trying Action(Info)")
            if focus_list(LIST_ID, tries=2):
                xbmc.executebuiltin('Action(Info)')
                xbmc.sleep(600)
                info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
                method_results.append(f"Method1: xsp_return_action_info, info_open={info_open}")
                if info_open:
                    success = True
        
        if not success:
            method_results.append("Method1: xsp_return_failed, info_open=False")
    
    # Method 2: Direct builtin with movieid (Matrix approach)
    if not success:
        _log("METHOD 2: Direct builtin approach...")
        
        # Try ShowVideoInfo builtin with movieid
        builtin_cmd = f'ShowVideoInfo({movieid})'
        _log(f"METHOD 2: Trying {builtin_cmd}")
        xbmc.executebuiltin(builtin_cmd)
        xbmc.sleep(600)
        
        info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        _log(f"METHOD 2: Info dialog open via ShowVideoInfo: {info_open}")
        method_results.append(f"Method2: ShowVideoInfo, info_open={info_open}")
        if info_open:
            success = True
    
    # Method 3: Focus control and Action(Info)
    if not success:
        _log("METHOD 3: Focus and Action(Info)...")
        for candidate in list_candidates[:3]:  # Try top 3 candidates
            _log(f"METHOD 3: Attempting control {candidate}...")
            if focus_list(candidate, tries=5, sleep_ms=100):
                _log(f"METHOD 3: Control {candidate} focused successfully")
                xbmc.sleep(200)
                
                # Verify we have an item selected
                list_item_title = xbmc.getInfoLabel('ListItem.Title')
                list_item_dbid = xbmc.getInfoLabel('ListItem.DBID')
                _log(f"METHOD 3: Selected item - Title: {list_item_title}, DBID: {list_item_dbid}")
                
                # Send Action(Info)
                _log("METHOD 3: Sending Action(Info)")
                xbmc.executebuiltin('Action(Info)')
                xbmc.sleep(600)
                
                # Check result
                info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
                _log(f"METHOD 3: Info dialog open after Action(Info): {info_open}")
                method_results.append(f"Method3: control_{candidate}_action_info, info_open={info_open}")
                if info_open:
                    success = True
                    break
            else:
                _log(f"METHOD 3: Could not focus control {candidate}")
    
    # Method 4: Fallback - Simple Action(Info) from current context
    if not success:
        _log("METHOD 4: Fallback Action(Info) from current context...")
        
        # Make sure we're in a videos window
        current_window = xbmc.getInfoLabel('System.CurrentWindow')
        if "video" not in current_window.lower():
            _log("METHOD 4: Not in videos window, navigating to movies...")
            xbmc.executebuiltin('ActivateWindow(Videos,videodb://movies/titles/,return)')
            xbmc.sleep(800)
        
        # Try simple Action(Info) - this should use whatever is currently focused
        _log("METHOD 4: Sending Action(Info)")
        xbmc.executebuiltin('Action(Info)')
        xbmc.sleep(600)
        
        info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        _log(f"METHOD 4: Info dialog open via fallback Action(Info): {info_open}")
        method_results.append(f"Method4: fallback_action_info, info_open={info_open}")
        if info_open:
            success = True
    
    # Method 5: Context menu approach
    if not success:
        _log("METHOD 5: Context menu approach...")
        if list_candidates:
            focus_list(list_candidates[0], tries=3, sleep_ms=100)
        
        _log("METHOD 5: Opening context menu...")
        xbmc.executebuiltin('Action(ContextMenu)')
        xbmc.sleep(400)
        context_open = xbmc.getCondVisibility('Window.IsActive(DialogContextMenu.xml)')
        _log(f"METHOD 5: Context menu open: {context_open}")
        
        if context_open:
            # Navigate and select info option
            _log("METHOD 5: Navigating to Information option")
            xbmc.executebuiltin('Action(Down)')
            xbmc.sleep(150)
            xbmc.executebuiltin('Action(Select)')
            xbmc.sleep(500)
        
        info_open = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
        _log(f"METHOD 5: Info dialog open via context menu: {info_open}")
        method_results.append(f"Method5: context_menu, info_open={info_open}")
        if info_open:
            success = True
    
    # Final comprehensive state check
    _log("STEP 6: Final state verification...")
    xbmc.sleep(300)  # Let everything settle
    # Check multiple possible dialog names for Matrix
    dialog_names = [
        'DialogVideoInfo.xml',
        'movieinformation.xml', 
        'VideoInfo.xml'
    ]
    final_info_open = False
    for dialog_name in dialog_names:
        if xbmc.getCondVisibility(f'Window.IsActive({dialog_name})'):
            final_info_open = True
            break
    
    final_window = xbmc.getInfoLabel('System.CurrentWindow')
    active_dialogs = []
    
    # Check for various dialog states
    dialog_checks = [
        'DialogVideoInfo.xml',
        'movieinformation.xml',
        'VideoInfo.xml',
        'DialogBusy.xml', 
        'DialogProgress.xml',
        'DialogContextMenu.xml'
    ]
    for dialog in dialog_checks:
        if xbmc.getCondVisibility(f'Window.IsActive({dialog})'):
            active_dialogs.append(dialog)
    
    _log(f"STEP 6: Final info dialog state: {final_info_open}")
    _log(f"STEP 6: Final window: {final_window}")
    _log(f"STEP 6: Active dialogs: {active_dialogs}")
    
    # Summary logging
    _log("=== TEST RESULTS SUMMARY ===")
    for result in method_results:
        _log(f"RESULT: {result}")
    _log(f"FINAL: Info dialog successfully opened: {final_info_open}")
    
    # Results and cleanup
    if final_info_open:
        _log("SUCCESS: Info dialog is open - test completed successfully")
        notify("Matrix test", f"Info dialog opened for {movie_title}!")
        _log("XSP remains available for manual cleanup")
    else:
        if success:
            _log("PARTIAL: A method reported success but final state unclear")
            notify("Matrix test", "Info methods executed - check manually")
        else:
            _log("FAILED: All methods failed to open info dialog", xbmc.LOGERROR)
            notify("Matrix test", "Failed to open info dialog")
        _cleanup_xsp(xsp_path)
    
    _log(f"=== MATRIX TEST END: movie {movieid} ===", xbmc.LOGINFO)

# ------------------------------
# Nexus+ (v20/v21): setDbId + Action(Info)
# ------------------------------
def build_nexus_item(handle: int, base_url: str, movieid: int):
    if kodi_major() < 20:
        _log(f"Nexus+ item requested on Kodi {kodi_major()} — requires v20+.", xbmc.LOGWARNING)

    label = f"Nexus+ setDbId(movieid={movieid})"
    li = xbmcgui.ListItem(label=label)
    try:
        vit = li.getVideoInfoTag()
        vit.setDbId(int(movieid), 'movie')   # <-- key bit for v20+
    except Exception as e:
        _log(f"setDbId failed: {e}", xbmc.LOGWARNING)

    # Click -> send Action(Info). Also expose via context menu.
    q = urlencode({"action": "nexus_info_click"})
    url = f"{base_url}?{q}"

    li.setProperty('IsPlayable', 'false')
    li.setInfo('video', {})
    li.addContextMenuItems([("Open Info (Nexus+)", f'RunPlugin({url})')])

    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    _log("Nexus+ list built; activate Info by clicking or via context menu.")

def nexus_info_click():
    focus_list(LIST_ID)
    xbmc.sleep(120)
    xbmc.executebuiltin('Action(Info)')

# ------------------------------
# Public API for your plugin router
# ------------------------------
def add_menu(handle: int, base_url: str, dbtype: str = 'movie', dbid: int = 883):
    _log(f"Building test menu (Kodi {kodi_major()}), {dbtype} {dbid}")

    # Matrix test entry — immediate XSP hop + Info
    m_q = urlencode({"action": "test_matrix", "dbtype": dbtype, "dbid": int(dbid)})
    m_url = f"{base_url}?{m_q}"
    m_li = xbmcgui.ListItem(label=f"Matrix v19: Show Info for {dbtype} {dbid} (XSP by path)")
    xbmcplugin.addDirectoryItem(handle, m_url, m_li, isFolder=False)

    # Nexus+ test entry — build setDbId item
    n_q = urlencode({"action": "test_nexus", "dbtype": dbtype, "dbid": int(dbid)})
    n_url = f"{base_url}?{n_q}"
    n_li = xbmcgui.ListItem(label=f"Nexus+ v20+: Build item with setDbId for {dbtype} {dbid}")
    xbmcplugin.addDirectoryItem(handle, n_url, n_li, isFolder=False)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

def handle_click(params: dict, handle: int | None = None, base_url: str | None = None):
    action = params.get('action')
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', 0))

    if action == 'test_matrix':
        if dbtype != 'movie':
            notify('Matrix test', 'Only movies supported in this harness')
            return
        show_info_matrix(dbid)

    elif action == 'test_nexus':
        if handle is None or base_url is None:
            _log("test_nexus requires handle and base_url")
            notify('Nexus+ test', 'Internal error: missing handle/base_url')
            return
        if dbtype != 'movie':
            notify('Nexus+ test', 'Only movies supported in this harness')
            return
        build_nexus_item(handle, base_url, dbid)

    elif action == 'nexus_info_click':
        nexus_info_click()

    else:
        _log(f"Unknown action: {action}", xbmc.LOGWARNING)
