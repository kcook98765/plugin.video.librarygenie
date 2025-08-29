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

def focus_list(control_id: int = LIST_ID, tries: int = 30, sleep_ms: int = 80) -> bool:
    for _ in range(tries):
        xbmc.executebuiltin(f'SetFocus({control_id})')
        if xbmc.getCondVisibility(f'Control.HasFocus({control_id})'):
            return True
        xbmc.sleep(sleep_ms)
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
    if kodi_major() != 19:
        _log(f"Matrix path requested on Kodi {kodi_major()} — designed for v19.", xbmc.LOGWARNING)

    _log(f"Matrix test start: movie {movieid} → creating XSP filter …")
    xsp_path = _create_movie_xsp_by_path(movieid)
    if not xsp_path:
        notify("Matrix test", "Failed to create smart playlist")
        return

    _log(f"Opening XSP: {xsp_path}")
    xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')
    if not wait_for_videos_container(xsp_path, timeout_ms=5000):
        _log("Timeout waiting for XSP container", xbmc.LOGWARNING)
        notify("Matrix test", "Timed out waiting for playlist")
        _cleanup_xsp(xsp_path)
        return

    _log(f"Container items: {xbmc.getInfoLabel('Container.NumItems')}")
    
    # Wait for window to be fully ready
    xbmc.sleep(500)
    
    # Check current window and control state
    current_window = xbmc.getInfoLabel('System.CurrentWindow')
    _log(f"Current window: {current_window}")
    
    # Try different approaches to focus and open info
    success = False
    
    # Method 1: Try to focus using the list control
    _log("Method 1: Attempting to focus list control")
    if focus_list(LIST_ID, tries=30, sleep_ms=100):
        _log("List focused - triggering info dialog")
        xbmc.sleep(300)
        xbmc.executebuiltin('Action(Info)')
        success = True
    else:
        # Method 2: Try using the container position directly
        _log("Method 2: Using container position approach")
        xbmc.executebuiltin('SetFocus(50)')  # Try main container first
        xbmc.sleep(200)
        xbmc.executebuiltin('Action(Select)')  # Select first item
        xbmc.sleep(200)
        xbmc.executebuiltin('Action(Info)')
        success = True
    
    if success:
        _log("Info action sent successfully - info dialog should now be open")
        _log("XSP will remain available to keep dialog open - manual cleanup required")
        notify("Matrix test", "Info dialog opened! Close manually when done.")
    else:
        _log("All focus methods failed", xbmc.LOGWARNING)
        notify("Matrix test", "Failed to open info dialog")
        # Only cleanup on failure
        _cleanup_xsp(xsp_path)

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
