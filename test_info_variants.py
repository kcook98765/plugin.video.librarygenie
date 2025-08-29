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
LIST_ID = 50                 # Working list control ID for Matrix
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

def focus_list(control_id: int = LIST_ID, tries: int = 5, sleep_ms: int = 100) -> bool:
    _log(f"FOCUS_LIST: Attempting to focus control {control_id}")

    for attempt in range(tries):
        xbmc.executebuiltin(f'SetFocus({control_id})')
        focused = xbmc.getCondVisibility(f'Control.HasFocus({control_id})')

        if focused:
            _log(f"FOCUS_LIST: SUCCESS on attempt {attempt + 1}")
            return True

        xbmc.sleep(sleep_ms)

    _log(f"FOCUS_LIST: FAILED after {tries} attempts")
    return False

def wait_for_videos_container(target_path: str, timeout_ms: int = 6000) -> bool:
    """Wait until Videos window shows target_path as Container.FolderPath and has items."""
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
# Matrix (v19): XSP + Navigation
# ------------------------------
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
        _log(f"No file path from JSON-RPC for movieid={movieid}", xbmc.LOGWARNING)
        return None

    filename = os.path.basename(file_path)
    _log(f"Creating XSP for filename: {filename}")

    xsp = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
    <name>LibraryGenie Test - Movie {movieid}</name>
    <match>all</match>
    <rule field="filename" operator="is">
        <value>{html.escape(filename)}</value>
    </rule>
    <order direction="ascending">title</order>
</smartplaylist>"""

    xsp_path = f"special://temp/libgenie_{movieid}.xsp"

    if _write_text(xsp_path, xsp):
        _log(f"XSP created at {xsp_path}")
        return xsp_path
    return None

def _cleanup_xsp(path_special: str):
    try:
        if path_special and xbmcvfs.exists(path_special):
            xbmcvfs.delete(path_special)
            _log(f"Cleaned up XSP {path_special}")
    except Exception as e:
        _log(f"Cleanup failed: {e}", xbmc.LOGDEBUG)

def show_info_matrix(movieid: int):
    kodi_ver = kodi_major()
    _log(f"=== MATRIX TEST START: movie {movieid} on Kodi v{kodi_ver} ===")

    # Step 1: Verify movie exists
    _log("STEP 1: Verifying movie exists in library...")
    movie_data = jsonrpc("VideoLibrary.GetMovieDetails", {
        "movieid": int(movieid),
        "properties": ["title", "file"]
    })
    movie_details = (movie_data.get("result") or {}).get("moviedetails")
    if not movie_details:
        _log(f"STEP 1: FAILED - Movie {movieid} not found", xbmc.LOGERROR)
        notify("Matrix test", f"Movie {movieid} not found")
        return

    movie_title = movie_details.get("title", "Unknown")
    _log(f"STEP 1: SUCCESS - Found movie: {movie_title}")

    # Step 2: Create XSP
    _log("STEP 2: Creating XSP filter...")
    xsp_path = _create_movie_xsp_by_path(movieid)
    if not xsp_path:
        _log("STEP 2: FAILED - Could not create XSP", xbmc.LOGERROR)
        notify("Matrix test", "Failed to create smart playlist")
        return
    _log("STEP 2: SUCCESS - XSP created")

    # Step 3: Navigate to XSP
    _log("STEP 3: Navigating to XSP...")
    xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')

    # Step 4: Wait for container
    _log("STEP 4: Waiting for container to load...")
    if not wait_for_videos_container(xsp_path, timeout_ms=8000):
        _log("STEP 4: FAILED - Timeout waiting for XSP container", xbmc.LOGERROR)
        notify("Matrix test", "Timed out waiting for playlist")
        _cleanup_xsp(xsp_path)
        return

    container_items = xbmc.getInfoLabel('Container.NumItems')
    _log(f"STEP 4: SUCCESS - Container loaded with {container_items} items")

    # Step 5: Focus list and navigate to movie
    _log("STEP 5: Opening info dialog...")
    xbmc.sleep(750)  # Let UI settle

    # Focus the list control
    if not focus_list(LIST_ID, tries=3, sleep_ms=150):
        _log("STEP 5: FAILED - Could not focus list control", xbmc.LOGERROR)
        notify("Matrix test", "Failed to focus list")
        _cleanup_xsp(xsp_path)
        return

    # Navigate down from ".." to the movie item
    _log("STEP 5: Moving to movie item...")
    xbmc.executebuiltin('Action(Down)')
    xbmc.sleep(400)  # Give time for selection to update

    # Verify we selected the movie
    current_title = xbmc.getInfoLabel('ListItem.Title')
    current_dbid = xbmc.getInfoLabel('ListItem.DBID')
    _log(f"STEP 5: Selected item - Title: '{current_title}', DBID: '{current_dbid}'")

    if not (current_title and current_dbid and current_title != ".."):
        _log("STEP 5: FAILED - Did not select movie item properly", xbmc.LOGERROR)
        notify("Matrix test", "Failed to select movie")
        _cleanup_xsp(xsp_path)
        return

    # Open info dialog
    _log("STEP 5: Opening info dialog with Action(Info)...")
    xbmc.executebuiltin('Action(Info)')
    xbmc.sleep(1000)  # Give time for dialog to open

    # Step 6: Verify success
    _log("STEP 6: Verifying info dialog opened...")
    xbmc.sleep(300)

    dialog_names = ['DialogVideoInfo.xml', 'movieinformation.xml', 'VideoInfo.xml']
    info_open = any(xbmc.getCondVisibility(f'Window.IsActive({dialog})') for dialog in dialog_names)

    if info_open:
        _log("SUCCESS: Info dialog is open")
        notify("Matrix test", f"Info dialog opened for {movie_title}!")
        # Keep XSP for manual cleanup if needed
    else:
        _log("FAILED: Info dialog did not open", xbmc.LOGERROR)
        notify("Matrix test", "Failed to open info dialog")
        _cleanup_xsp(xsp_path)

    _log(f"=== MATRIX TEST END: movie {movieid} ===")

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
        vit.setDbId(int(movieid), 'movie')
    except Exception as e:
        _log(f"setDbId failed: {e}", xbmc.LOGWARNING)

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

    # Matrix test entry
    m_q = urlencode({"action": "test_matrix", "dbtype": dbtype, "dbid": int(dbid)})
    m_url = f"{base_url}?{m_q}"
    m_li = xbmcgui.ListItem(label=f"Matrix v19: Show Info for {dbtype} {dbid}")
    xbmcplugin.addDirectoryItem(handle, m_url, m_li, isFolder=False)

    # Nexus+ test entry
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