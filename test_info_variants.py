# -*- coding: utf-8 -*-
"""
Matrix-friendly tests for opening the native Video Info with cast populated
WITHOUT injecting cast from the addon.

Core idea: "Library hop"
  1) Open Videos window at the *library item* path (videodb item, no trailing slash)
  2) Small delay to let the container focus the item
  3) Action(Info)

USAGE (router):
    from .test_info_variants import run_test_info_variants, handle_test_info_click

    elif action == 'test_info_variants':
        run_test_info_variants(addon_handle, params)

    elif action == 'test_info_click':
        handle_test_info_click(params, addon_handle)

Launch with:
    ?action=test_info_variants&dbtype=movie&dbid=883
"""

import sys
from urllib.parse import parse_qs
import xbmc
import xbmcgui
import xbmcplugin

ADDON_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1


# ---------------------------
# Helpers
# ---------------------------
def _params_to_dict(argv):
    if len(argv) >= 3 and argv[2]:
        try:
            return {k: v[0] for k, v in parse_qs(argv[2][1:]).items()}
        except Exception:
            return {}
    return {}


def _vdb_item_path(dbtype, dbid, tvshowid=None, season=None):
    """
    Return the *ITEM* path (NO trailing slash).
    """
    dbid = int(dbid)
    if dbtype == 'movie':
        return f'videodb://movies/titles/{dbid}'
    elif dbtype == 'tvshow':
        # tvshow info page (show-level item)
        return f'videodb://tvshows/titles/{dbid}'
    elif dbtype == 'episode' and tvshowid is not None and season is not None:
        return f'videodb://tvshows/titles/{int(tvshowid)}/{int(season)}/{dbid}'
    # fallback to movie
    return f'videodb://movies/titles/{dbid}'


def _jsonrpc_cast_count(dbtype, dbid):
    """
    Log the raw JSON-RPC response for cast to confirm Kodi DB has it.
    """
    try:
        if dbtype == 'movie':
            payload = (
                '{"jsonrpc":"2.0","id":1,"method":"VideoLibrary.GetMovieDetails",'
                f'"params":{{"movieid":{int(dbid)},"properties":["cast"]}}}}'
            )
        elif dbtype == 'tvshow':
            payload = (
                '{"jsonrpc":"2.0","id":1,"method":"VideoLibrary.GetTVShowDetails",'
                f'"params":{{"tvshowid":{int(dbid)},"properties":["cast"]}}}}'
            )
        else:
            return
        raw = xbmc.executeJSONRPC(payload)
        xbmc.log(f"[LibHopTest] JSON-RPC cast check: {raw}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[LibHopTest] JSON-RPC cast check error: {e}", xbmc.LOGERROR)


def _library_hop_and_info(vdb_item, delay_ms=350, quoted=False):
    """
    Open Videos window at the given *item* path and then open Info.
    Works on Matrix when direct VideoInformation doesn't.
    """
    try:
        # Ensure item path has no trailing slash
        vdb_item = vdb_item.rstrip('/')

        if quoted:
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{vdb_item}",return)')
        else:
            xbmc.executebuiltin(f'ActivateWindow(Videos,{vdb_item},return)')

        # Small wait so the container can focus the item
        xbmc.sleep(int(delay_ms))

        # Open info on the focused library item
        xbmc.executebuiltin('Action(Info)')
    except Exception as e:
        xbmc.log(f"[LibHopTest] library_hop_and_info error: {e}", xbmc.LOGERROR)


def _add_row(idx, url, label_suffix, *, vdb_item, is_playable=False):
    """
    Minimal row builder; no cast set. Title includes test number & mode.
    """
    li = xbmcgui.ListItem(label=f"{idx:02d} • {label_suffix}")
    li.setInfo('video', {'title': f'Variant {idx:02d}', 'year': 2000 + idx, 'mediatype': 'movie'})
    li.setProperty('IsPlayable', 'true' if is_playable else 'false')

    # Handy context menu entries to compare behaviors
    cm = [
        ("[Info] Action(Info) on focused item", "Action(Info)"),
        ("[Info] ActivateWindow(VideoInformation) (unquoted)",
         f'ActivateWindow(VideoInformation,{vdb_item},return)'),
        ("[Info] ActivateWindow(VideoInformation) (quoted)",
         f'ActivateWindow(VideoInformation,"{vdb_item}",return)'),
    ]
    li.addContextMenuItems(cm, replaceItems=False)

    xbmcplugin.addDirectoryItem(ADDON_HANDLE, url=url, listitem=li, isFolder=False)


# ---------------------------
# Directory builder
# ---------------------------
def run_test_info_variants(addon_handle, params=None):
    params = params or {}
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', '883') or 0)
    tvshowid = params.get('tvshowid')
    season = params.get('season')

    vdb_item = _vdb_item_path(dbtype, dbid, tvshowid, season)
    xbmc.log(f"[LibHopTest] Build list for {dbtype} {dbid} -> {vdb_item}", xbmc.LOGINFO)

    xbmcplugin.setContent(addon_handle, 'movies')

    # 01) Baseline: does nothing on click (use context menu entries)
    _add_row(
        1,
        url=f"{sys.argv[0]}?action=test_info_click&mode=noop&dbtype={dbtype}&dbid={dbid}",
        label_suffix="baseline (use context menu)",
        vdb_item=vdb_item
    )

    # 02) Library hop (UNQUOTED)
    _add_row(
        2,
        url=f"{sys.argv[0]}?action=test_info_click&mode=libhop_uq&dbtype={dbtype}&dbid={dbid}",
        label_suffix="LIB HOP → Info (unquoted)",
        vdb_item=vdb_item
    )

    # 03) Library hop (QUOTED)
    _add_row(
        3,
        url=f"{sys.argv[0]}?action=test_info_click&mode=libhop_q&dbtype={dbtype}&dbid={dbid}",
        label_suffix="LIB HOP → Info (quoted)",
        vdb_item=vdb_item
    )

    # 04) Direct VideoInformation (UNQUOTED) — likely fails on Matrix, included for comparison
    _add_row(
        4,
        url=f"{sys.argv[0]}?action=test_info_click&mode=info_uq&dbtype={dbtype}&dbid={dbid}",
        label_suffix="Direct VideoInformation (unquoted)",
        vdb_item=vdb_item
    )

    # 05) Direct VideoInformation (QUOTED) — compare to #4
    _add_row(
        5,
        url=f"{sys.argv[0]}?action=test_info_click&mode=info_q&dbtype={dbtype}&dbid={dbid}",
        label_suffix="Direct VideoInformation (quoted)",
        vdb_item=vdb_item
    )

    # 06) Sanity: PlayMedia on the item path (helps verify target)
    _add_row(
        6,
        url=f"{sys.argv[0]}?action=test_info_click&mode=play&dbtype={dbtype}&dbid={dbid}",
        label_suffix="PlayMedia(vdb item)",
        vdb_item=vdb_item,
        is_playable=True
    )

    xbmcplugin.endOfDirectory(addon_handle)


# ---------------------------
# Click router
# ---------------------------
def handle_test_info_click(params, addon_handle):
    mode = params.get('mode', 'noop')
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', '0') or 0)
    tvshowid = params.get('tvshowid')
    season = params.get('season')

    vdb_item = _vdb_item_path(dbtype, dbid, tvshowid, season)
    xbmc.log(f"[LibHopTest] click mode={mode} vdb_item={vdb_item}", xbmc.LOGINFO)

    # Confirm Kodi DB has cast for the id we’re targeting
    _jsonrpc_cast_count(dbtype, dbid)

    try:
        if mode == 'libhop_uq':
            _library_hop_and_info(vdb_item, delay_ms=350, quoted=False)

        elif mode == 'libhop_q':
            _library_hop_and_info(vdb_item, delay_ms=350, quoted=True)

        elif mode == 'info_uq':
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,{vdb_item},return)')

        elif mode == 'info_q':
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,"{vdb_item}",return)')

        elif mode == 'play':
            xbmc.executebuiltin(f'PlayMedia({vdb_item})')

        else:
            xbmcgui.Dialog().notification("LibHop Test", "Use context menu or pick a LIB HOP row.", xbmcgui.NOTIFICATION_INFO, 2500)

    except Exception as e:
        xbmc.log(f"[LibHopTest] Error in handle_test_info_click: {e}", xbmc.LOGERROR)
    finally:
        # Don't render a directory for click actions
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass
