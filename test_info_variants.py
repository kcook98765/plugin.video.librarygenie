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

def wait_until(cond, timeout_ms=2000, step_ms=30):
    """Wait for condition with fast polling, no fixed sleeps"""
    end = time.time() + (timeout_ms / 1000.0)
    while time.time() < end and not xbmc.Monitor().abortRequested():
        if cond():
            return True
        xbmc.sleep(step_ms)  # small, responsive yield
    return False

def focus_list(control_id: int = LIST_ID, tries: int = 20, step_ms: int = 30) -> bool:
    """Focus list control with fast polling"""
    for _ in range(tries):
        xbmc.executebuiltin(f'SetFocus({control_id})')
        if xbmc.getCondVisibility(f'Control.HasFocus({control_id})'):
            return True
        xbmc.sleep(step_ms)
    return False

def focus_list_index(control_id: int, index: int, tries: int = 20, step_ms: int = 30) -> bool:
    """Focus specific index in list control (many skins support SetFocus(id,index))"""
    for _ in range(tries):
        xbmc.executebuiltin(f'SetFocus({control_id},{index})')
        # Verify by checking if we have focus
        if xbmc.getCondVisibility(f'Control.HasFocus({control_id})'):
            return True
        xbmc.sleep(step_ms)
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

def find_index_in_xsp(xsp_path: str, movieid: int) -> int:
    """Find the exact row index of movieid in the XSP folder"""
    # Ask Kodi what's in that folder right now and find the row
    data = jsonrpc("Files.GetDirectory", {
        "directory": xsp_path, "media": "video",
        "properties": ["title", "file", "thumbnail", "art", "resume"]
    })
    items = (data.get("result") or {}).get("files") or []
    # Typical XSP list shows ".." first; our movie should be the only real item
    # Match on movieid if present, otherwise match on filename from library
    target_file = _get_movie_file(movieid) or ""
    for idx, it in enumerate(items):
        mid = it.get("movieid") or it.get("id")
        if mid == movieid:
            return idx
        if target_file and it.get("file") == target_file:
            return idx
    # Fallback: if it's one movie plus (".."), that movie is usually index 1
    return 1 if len(items) == 2 and items[0].get("file","").endswith("..") else 0

def swap_under_info(orig_path: str, timeout_ms: int = 2000):
    """Wait for info dialog to open, then replace history immediately"""
    if wait_until(lambda: xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)'), timeout_ms):
        _log(f"SWAP: Container.Update('{orig_path}', replace)")
        xbmc.executebuiltin(f'Container.Update("{orig_path}",replace)')
    else:
        _log("SWAP: Info dialog did not open in time", xbmc.LOGWARNING)

def show_info_matrix(movieid: int):
    _log(f"=== MATRIX TEST START: movie {movieid} on Kodi v{kodi_major()} ===")

    # Where we want Back to return to
    orig_path = xbmc.getInfoLabel('Container.FolderPath') or ''

    # Verify the movie exists
    md = jsonrpc("VideoLibrary.GetMovieDetails", {"movieid": int(movieid), "properties": ["title","file"]})
    details = (md.get("result") or {}).get("moviedetails")
    if not details:
        notify("Matrix test", f"Movie {movieid} not found")
        return
    title = details.get("title") or "Unknown"

    # Build one-movie XSP and open it
    xsp_path = _create_movie_xsp_by_path(movieid)
    if not xsp_path:
        notify("Matrix test", "Failed to create smart playlist")
        return

    xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')

    # Wait until that folder is *actually* showing and populated
    if not wait_until(lambda: xbmc.getCondVisibility(f'Window.IsActive({VIDEOS_WINDOW})')
                               and (xbmc.getInfoLabel('Container.FolderPath') or '').rstrip('/') == xsp_path.rstrip('/')
                               and int(xbmc.getInfoLabel('Container.NumItems') or '0') > 0
                               and not xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)'),
                      timeout_ms=8000):
        notify("Matrix test", "Timed out waiting for playlist")
        _cleanup_xsp(xsp_path)
        return

    # Focus the list & jump straight to the movie row
    if not focus_list(LIST_ID): 
        notify("Matrix test", "Failed to focus list")
        _cleanup_xsp(xsp_path)
        return

    row = find_index_in_xsp(xsp_path, movieid)
    focus_list_index(LIST_ID, row)

    # Sanity check we're on the correct item (no sleep needed)
    ok = wait_until(lambda: xbmc.getInfoLabel('ListItem.DBID') == str(movieid), timeout_ms=600)
    if not ok:
        _log(f"Row focus verification failed; continuing to open Info anyway.", xbmc.LOGWARNING)

    # Open Info and immediately replace the XSP page underneath
    xbmc.executebuiltin('Action(Info)')
    swap_under_info(orig_path)  # returns as soon as the dialog is up

    # Verify dialog is open (fast poll, no fixed sleep)
    if wait_until(lambda: xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)'), timeout_ms=1500):
        notify("Matrix test", f"Info dialog opened for {title}!")
    else:
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