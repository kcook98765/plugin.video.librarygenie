# -*- coding: utf-8 -*-
"""
Test matrix for Kodi DialogVideoInfo resolution (Matrix-friendly).

Builds many variants of the SAME movie ListItem using different combinations of:
- URL (plugin vs videodb)
- listitem.setPath(videodb://…)
- listitem.setProperty('dbid'/'dbtype'/'mediatype')
- Container content typing
- Click behavior (open Info via:
    * ActivateWindow(VideoInformation,...)
    * "Library jump" to Videos window then Action(Info)
    * Container.Update(vdb,replace) then Action(Info)
- Folder vs Playable hinting

No cast is injected. Minimal basic info only.
Open the info dialog (press "i" or use the click variants) and check if cast appears.

USAGE (inside your plugin router):
    from .test_info_variants import run_test_info_variants, handle_test_info_click

    elif action == 'test_info_variants':
        run_test_info_variants(addon_handle, params)

    elif action == 'test_info_click':
        handle_test_info_click(params, addon_handle)

You can pass dbid/dbtype via params (defaults below are safe):
    ?action=test_info_variants&dbtype=movie&dbid=883
"""

import sys
from urllib.parse import parse_qs

import xbmc
import xbmcgui
import xbmcplugin

ADDON_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1


def _params_to_dict(argv):
    if len(argv) >= 3 and argv[2]:
        try:
            return {k: v[0] for k, v in parse_qs(argv[2][1:]).items()}
        except Exception:
            return {}
    return {}


def _vdb_path(dbtype, dbid, tvshowid=None, season=None):
    dbid = int(dbid)
    if dbtype == 'movie':
        return f'videodb://movies/titles/{dbid}/'
    elif dbtype == 'tvshow':
        return f'videodb://tvshows/titles/{dbid}/'
    elif dbtype == 'episode' and tvshowid is not None and season is not None:
        return f'videodb://tvshows/titles/{int(tvshowid)}/{int(season)}/{dbid}/'
    return f'videodb://movies/titles/{dbid}/'


def _jsonrpc_cast_count(dbtype, dbid):
    """Log cast count from Kodi DB for sanity."""
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
        xbmc.log(f"[TestInfoVariants] JSON-RPC cast check: {raw}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[TestInfoVariants] JSON-RPC cast check error: {e}", xbmc.LOGERROR)


def _add_variant(
    idx,
    addon_handle,
    *,
    url,
    vdb,
    set_path=False,
    props=None,
    set_info=True,
    click_mode="noop",
    playable=None,
    is_folder=False,
):
    """
    click_mode:
      - "noop"               : clicking calls plugin but does nothing (use context menu to test)
      - "info_unquoted"      : ActivateWindow(VideoInformation,<vdb>,return)
      - "info_quoted"        : ActivateWindow(VideoInformation,"<vdb>",return)
      - "libjump_info_uq"    : ActivateWindow(Videos,<vdb>,return) + sleep + Action(Info)
      - "libjump_info_q"     : ActivateWindow(Videos,"<vdb>",return) + sleep + Action(Info)
      - "container_update"   : Container.Update(<vdb>,replace) + sleep + Action(Info)
      - "play"               : PlayMedia(<vdb>) (sanity check target)
    """
    badges = []
    if click_mode != "noop":
        badges.append(click_mode)
    if set_path:
        badges.append("path")
    if props:
        badges.append("props")
    if is_folder:
        badges.append("FOLDER")
    title = f"{idx:02d} • {'+'.join(badges) if badges else 'base'}"

    li = xbmcgui.ListItem(label=title)

    # Basic info ONLY (no cast)
    if set_info:
        info = {'title': f'Variant {idx:02d}', 'year': 2000 + idx, 'mediatype': 'movie'}
        li.setInfo('video', info)

    # Decide "playable" hint (Matrix: keep non-playable for info tests)
    if playable is None:
        playable = (click_mode == "play")
    li.setProperty('IsPlayable', 'true' if playable else 'false')

    # Optional properties (must be strings)
    props = props or {}
    for k, v in props.items():
        if v is not None:
            li.setProperty(str(k), str(v))

    # Optional listitem path
    if set_path and vdb:
        li.setPath(vdb)

    # Context menu helpers
    cm = []
    cm.append(("[Info] Action(Info) on focused item", "Action(Info)"))
    if vdb:
        cm.append(("[Info] ActivateWindow(VideoInformation) on VDB (UNQUOTED)",
                   f'ActivateWindow(VideoInformation,{vdb},return)'))
        cm.append(("[Info] ActivateWindow(VideoInformation) on VDB (QUOTED)",
                   f'ActivateWindow(VideoInformation,"{vdb}",return)'))
    li.addContextMenuItems(cm, replaceItems=False)

    xbmcplugin.addDirectoryItem(addon_handle, url=url, listitem=li, isFolder=is_folder)


def run_test_info_variants(addon_handle, params=None):
    params = params or {}
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', '883'))
    tvshowid = params.get('tvshowid')  # optional
    season = params.get('season')      # optional

    vdb = _vdb_path(dbtype, dbid, tvshowid, season)

    xbmc.log(f"[TestInfoVariants] Building variants for dbtype={dbtype}, dbid={dbid}, vdb={vdb}", xbmc.LOGINFO)

    # Strongly type the container as movies:
    xbmcplugin.setContent(addon_handle, 'movies')

    # ── A) Original plugin-URL style (use context menu entries to open Info) ──
    _add_variant(1, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb)

    _add_variant(2, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid})

    _add_variant(3, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbtype': dbtype})

    _add_variant(4, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype})

    _add_variant(5, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'mediatype': 'movie'})

    _add_variant(6, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'})

    _add_variant(7, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True)

    _add_variant(8, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 props={'dbid': dbid})

    _add_variant(9, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'})

    # ── B) Direct videodb URL (compare click vs context) ──
    _add_variant(10, addon_handle, url=vdb, vdb=vdb)
    _add_variant(11, addon_handle, url=vdb, vdb=vdb, props={'dbid': dbid, 'dbtype': dbtype})

    # 12) No setInfo at all (still typed by container)
    _add_variant(12, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_info=False,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'})

    # ── C) Click-to-open Info via different mechanisms ──
    _add_variant(13, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=info_unquoted&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, click_mode="info_unquoted", playable=False)

    _add_variant(14, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=info_quoted&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, click_mode="info_quoted", playable=False)

    _add_variant(15, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=play&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, click_mode="play", playable=True)

    # ── D) NEW: Library jump + Action(Info) (Matrix-friendly) ──
    _add_variant(16, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=libjump_info_uq&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, click_mode="libjump_info_uq", playable=False)

    _add_variant(17, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=libjump_info_q&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, click_mode="libjump_info_q", playable=False)

    # ── E) NEW: Container.Update(vdb, replace) + Action(Info) ──
    _add_variant(18, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=container_update&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, click_mode="container_update", playable=False)

    # ── F) NEW: Direct videodb items added as FOLDERs (no IsPlayable) ──
    _add_variant(19, addon_handle,
                 url=vdb, vdb=vdb, is_folder=True)

    _add_variant(20, addon_handle,
                 url=vdb, vdb=vdb, is_folder=True, set_path=True)

    xbmcplugin.endOfDirectory(addon_handle)


def handle_test_info_click(params, addon_handle):
    """
    Router for the clickable test variants (13–20).
    Performs GUI actions immediately (no directory rendering).
    Also logs JSON-RPC cast presence for the target ID first.
    """
    mode = params.get('mode', 'noop')
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', '0') or 0)
    tvshowid = params.get('tvshowid')
    season = params.get('season')

    vdb = _vdb_path(dbtype, dbid, tvshowid, season)
    xbmc.log(f"[TestInfoVariants] handle_test_info_click mode={mode} vdb={vdb}", xbmc.LOGINFO)

    # Log cast presence from DB for this id (helps confirm DB is populated)
    _jsonrpc_cast_count(dbtype, dbid)

    try:
        if mode == "info_unquoted":
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,{vdb},return)')
        elif mode == "info_quoted":
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,"{vdb}",return)')
        elif mode == "libjump_info_uq":
            xbmc.executebuiltin(f'ActivateWindow(Videos,{vdb},return)')
            xbmc.sleep(250)
            xbmc.executebuiltin('Action(Info)')
        elif mode == "libjump_info_q":
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{vdb}",return)')
            xbmc.sleep(250)
            xbmc.executebuiltin('Action(Info)')
        elif mode == "container_update":
            xbmc.executebuiltin(f'Container.Update({vdb},replace)')
            xbmc.sleep(250)
            xbmc.executebuiltin('Action(Info)')
        elif mode == "play":
            xbmc.executebuiltin(f'PlayMedia({vdb})')
        else:
            xbmcgui.Dialog().notification("Test Info Variants", "noop: use context menu to test Info", xbmcgui.NOTIFICATION_INFO, 2500)
    except Exception as e:
        xbmc.log(f"[TestInfoVariants] Error in handle_test_info_click: {e}", xbmc.LOGERROR)
    finally:
        # Do not render a directory for this call
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass
