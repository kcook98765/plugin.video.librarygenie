# test_info_variants.py — slim harness for Matrix (v19) and Nexus+ (v20+)
# Drop this next to your plugin.py (or under resources/lib and import accordingly).
# It exposes two entry points:
#   add_menu(handle, base_url, dbtype, dbid)
#   handle_click(params, handle=None, base_url=None)
#
# Matrix (v19):
#   - Jumps to videodb://movies/titles/
#   - Waits for the container, finds the row index of movieid via JSON-RPC
#   - Focuses container 55 + index, then Action(Info)
#
# Nexus+ (v20/v21):
#   - Builds a one-item listing where the ListItem has setDbId(movieid, 'movie')
#   - Clicking the item (or its context menu) runs action=nexus_info_click, which sends Action(Info)

from __future__ import annotations
import json
import sys
import time
from urllib.parse import urlencode, parse_qs

import xbmc
import xbmcgui
import xbmcplugin

# ------------------------------
# Helpers
# ------------------------------

LOG_PREFIX = "[InfoHarness]"
LIST_ID = 55                # Estuary main list id in MyVideoNav.xml
VIDEOS_WINDOW = "MyVideoNav.xml"
VDB_TITLES_DIR = "videodb://movies/titles/"


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


def wait_for_videos_container(target_dir: str, timeout_ms: int = 6000) -> bool:
    """Wait until the Videos window is active, the folder path matches, items are present, and busy dialog is closed."""
    mon = xbmc.Monitor()
    target = target_dir.rstrip('/') + '/'
    start = time.time() * 1000  # Convert to milliseconds
    while (time.time() * 1000) - start < timeout_ms and not mon.abortRequested():
        if not xbmc.getCondVisibility(f'Window.IsActive({VIDEOS_WINDOW})'):
            xbmc.sleep(120)
            continue
        cur = (xbmc.getInfoLabel('Container.FolderPath') or '').rstrip('/') + '/'
        num = int(xbmc.getInfoLabel('Container.NumItems') or '0')
        busy = xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)')
        if cur == target and num > 0 and not busy:
            return True
        xbmc.sleep(120)
    return False


def focus_list(control_id: int = LIST_ID, tries: int = 30, sleep_ms: int = 80) -> bool:
    for _ in range(tries):
        xbmc.executebuiltin(f'SetFocus({control_id})')
        if xbmc.getCondVisibility(f'Control.HasFocus({control_id})'):
            return True
        xbmc.sleep(sleep_ms)
    return False


def find_movie_index_in_titles(movieid: int) -> int | None:
    """Return the 0-based index of the movie row inside videodb://movies/titles/ using label-ascending sort."""
    req = {
        "directory": VDB_TITLES_DIR,
        "media": "video",
        "properties": ["title", "year", "thumbnail"],
        "sort": {"method": "label", "order": "ascending"},
    }
    data = jsonrpc("Files.GetDirectory", req)
    files = data.get("result", {}).get("files", [])
    for idx, item in enumerate(files):
        mid = item.get("movieid", item.get("id"))
        if mid == movieid:
            return idx
    return None


def notify(heading: str, message: str, time_ms: int = 3500):
    xbmcgui.Dialog().notification(heading, message, xbmcgui.NOTIFICATION_INFO, time_ms)

# ------------------------------
# Matrix (v19) test
# ------------------------------


def show_info_matrix(movieid: int):
    if kodi_major() != 19:
        _log(f"Matrix path requested on Kodi {kodi_major()}, proceeding anyway but this is designed for v19.")
    _log(f"Matrix test start: movie {movieid} → open {VDB_TITLES_DIR} …")

    xbmc.executebuiltin(f'ActivateWindow(Videos,"{VDB_TITLES_DIR}",return)')
    if not wait_for_videos_container(VDB_TITLES_DIR):
        _log("Timeout waiting for Videos container", xbmc.LOGWARNING)
        notify("Matrix test", "Timed out waiting for movie titles list")
        return

    if not focus_list(LIST_ID):
        _log("Could not focus list control 55", xbmc.LOGWARNING)
        notify("Matrix test", "Couldn’t focus list (55)")
        return

    # Optional nudge to top; FirstItem is not valid on Matrix — use FirstPage
    xbmc.executebuiltin('Action(FirstPage)')

    idx = find_movie_index_in_titles(movieid)
    if idx is None:
        _log(f"movieid {movieid} not present in label-asc list", xbmc.LOGWARNING)
        notify("Matrix test", f"Movie {movieid} not found in list")
        return

    _log(f"Focusing index {idx} then opening Info")
    xbmc.executebuiltin(f'SetFocus({LIST_ID},{idx})')
    xbmc.sleep(150)
    xbmc.executebuiltin('Action(Info)')

# ------------------------------
# Nexus+ (v20/v21) test
# ------------------------------


def build_nexus_item(handle: int, base_url: str, movieid: int):
    if kodi_major() < 20:
        _log(f"Nexus+ item requested on Kodi {kodi_major()} — this path requires v20+.", xbmc.LOGWARNING)
    label = f"Nexus+ test item with setDbId(movieid={movieid})"
    li = xbmcgui.ListItem(label=label)
    try:
        vit = li.getVideoInfoTag()
        vit.setDbId(int(movieid), 'movie')
        # Optionally: vit.setTitle("(Test)")
    except Exception as e:
        _log(f"setDbId failed: {e}", xbmc.LOGWARNING)

    # Clicking the row will route to nexus_info_click which simply issues Action(Info)
    q = urlencode({"action": "nexus_info_click"})
    url = f"{base_url}?{q}"

    # Mark item as non-playable and not a folder; the view will keep focus on it
    li.setProperty('IsPlayable', 'false')
    li.setInfo('video', {})
    li.addContextMenuItems([
        ("Open Info (Nexus+)", f'RunPlugin({url})')
    ])

    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    _log("Nexus+ list built with one item; click it or use context menu to open Info")


def nexus_info_click():
    # When invoked, the focused row should be our setDbId item. Just fire Info.
    if not xbmc.getCondVisibility(f'Window.IsActive({VIDEOS_WINDOW})'):
        _log("Videos window not active; trying to focus list anyway", xbmc.LOGDEBUG)
    focus_list(LIST_ID)
    xbmc.sleep(120)
    xbmc.executebuiltin('Action(Info)')

# ------------------------------
# Public API for your plugin router
# ------------------------------


def add_menu(handle: int, base_url: str, dbtype: str = 'movie', dbid: int = 883):
    _log(f"Building test menu (Kodi {kodi_major()}), {dbtype} {dbid}")

    # Matrix test entry — triggers immediate hop+info
    m_q = urlencode({"action": "test_matrix", "dbtype": dbtype, "dbid": int(dbid)})
    m_url = f"{base_url}?{m_q}"
    m_li = xbmcgui.ListItem(label=f"Matrix v19: Show Info for {dbtype} {dbid} (library hop + focus)")
    xbmcplugin.addDirectoryItem(handle, m_url, m_li, isFolder=False)

    # Nexus+ test entry — builds an item with setDbId when clicked
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

# ------------------------------
# Optional: allow quick standalone testing via RunScript
# ------------------------------

def _parse_argv(argv):
    # argv[0] = plugin://… (base url), argv[1] = handle, argv[2] = ?query
    base_url = argv[0]
    try:
        handle = int(argv[1])
    except Exception:
        handle = -1
    q = parse_qs(argv[2][1:]) if len(argv) > 2 and argv[2].startswith('?') else {}
    params = {k: v[0] for k, v in q.items()}
    return base_url, handle, params

if __name__ == '__main__':
    base_url, handle, params = _parse_argv(sys.argv)
    if not params:
        # Default: build menu with movie 883
        add_menu(handle, base_url, 'movie', 883)
    else:
        # For test_nexus we need handle & base_url
        if params.get('action') == 'test_nexus':
            handle_click(params, handle=handle, base_url=base_url)
        else:
            handle_click(params)
