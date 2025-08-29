
# -*- coding: utf-8 -*-
"""
Test matrix for Kodi DialogVideoInfo resolution (Matrix + Nexus/Omega).

What this tries:
  Matrix (v19):
    - "Library hop" to videodb title path (quoted/unquoted; with/without trailing slash),
      then Action(Info)
    - Container.Update(videodb, replace) then Action(Info)
    - Direct ActivateWindow(VideoInformation, videodb) (control)

  Nexus+ (v20+):
    - Use InfoTagVideo.setDbId(int) + setMediaType('movie') on ListItems
      (with/without setPath and different click behaviors)

No cast is injected. Basic info only. Use context menus or click variants.

USAGE in your router:
    from .test_info_variants import run_test_info_variants, handle_test_info_click

    elif action == 'test_info_variants':
        run_test_info_variants(addon_handle, params)

    elif action == 'test_info_click':
        handle_test_info_click(params, addon_handle)

Launch example:
    ?action=test_info_variants&dbtype=movie&dbid=883
"""

import sys
from urllib.parse import parse_qs

import xbmc
import xbmcgui
import xbmcplugin

ADDON_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1


# ------------------------------
# Helpers
# ------------------------------

def _params_to_dict(argv):
    if len(argv) >= 3 and argv[2]:
        try:
            return {k: v[0] for k, v in parse_qs(argv[2][1:]).items()}
        except Exception:
            return {}
    return {}


def _kodi_major():
    """Return Kodi major version as int, fallback to 19 on parse error."""
    try:
        s = xbmc.getInfoLabel('System.BuildVersion') or ''
        # Formats like "21.0 (20.0.0) Git:..."; take leading int
        for tok in s.split():
            try:
                return int(tok.split('.')[0])
            except Exception:
                continue
    except Exception:
        pass
    return 19


def _vdb_path(dbtype, dbid, tvshowid=None, season=None, trailing_slash=True):
    dbid = int(dbid)
    if dbtype == 'movie':
        p = f'videodb://movies/titles/{dbid}'
    elif dbtype == 'tvshow':
        p = f'videodb://tvshows/titles/{dbid}'
    elif dbtype == 'episode' and tvshowid is not None and season is not None:
        p = f'videodb://tvshows/titles/{int(tvshowid)}/{int(season)}/{dbid}'
    else:
        p = f'videodb://movies/titles/{dbid}'
    return (p + '/') if trailing_slash and not p.endswith('/') else p


def _jsonrpc_cast_check(dbtype, dbid):
    """Log cast presence for sanity."""
    try:
        dbid = int(dbid)
        if dbtype == 'movie':
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "VideoLibrary.GetMovieDetails",
                "params": {"movieid": dbid, "properties": ["cast", "title"]}
            }
        elif dbtype == 'tvshow':
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "VideoLibrary.GetTVShowDetails",
                "params": {"tvshowid": dbid, "properties": ["cast", "title"]}
            }
        else:
            return
        import json as _json
        raw = xbmc.executeJSONRPC(_json.dumps(payload))
        xbmc.log(f"[InfoHarness] JSON-RPC cast check for {dbtype} {dbid}: {raw}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[InfoHarness] JSON-RPC cast check error: {e}", xbmc.LOGERROR)


def _add_variant(
    idx,
    *,
    url,
    vdb,
    set_path=False,
    props=None,
    set_info=True,
    click_mode="noop",
    playable=None,
    is_folder=False,
    use_dbid_tag=False,
    dbtype='movie',
    dbid=None,
):
    """
    click_mode choices:
      - "noop"               : just list the item; use context menu to test
      - "info_direct_uq"     : ActivateWindow(VideoInformation,<vdb>,return)
      - "info_direct_q"      : ActivateWindow(VideoInformation,"<vdb>",return)
      - "libhop_uq"          : ActivateWindow(Videos,<vdb>,return)   ; sleep ; Action(Info)
      - "libhop_q"           : ActivateWindow(Videos,"<vdb>",return) ; sleep ; Action(Info)
      - "container_update"   : Container.Update(<vdb>,replace) ; sleep ; Action(Info)
      - "play"               : PlayMedia(<vdb>)
    """
    label_bits = [f"{idx:02d}"]
    if use_dbid_tag:
        label_bits.append("InfoTag.setDbId")
    if set_path:
        label_bits.append("path")
    if props:
        label_bits.append("props")
    if is_folder:
        label_bits.append("FOLDER")
    if click_mode != "noop":
        label_bits.append(click_mode)
    label = " • ".join(label_bits)

    li = xbmcgui.ListItem(label=label)

    # Minimal info ONLY (no cast injection)
    if set_info:
        li.setInfo('video', {'title': f'Variant {idx:02d}', 'year': 2000 + idx, 'mediatype': 'movie'})

    # v20+: mark the listitem as a library item via InfoTag
    if use_dbid_tag and dbid is not None:
        try:
            tag = li.getVideoInfoTag()
            if hasattr(tag, 'setMediaType'):
                tag.setMediaType('movie' if dbtype == 'movie' else dbtype)
            if hasattr(tag, 'setDbId'):
                tag.setDbId(int(dbid))
        except Exception as e:
            xbmc.log(f"[InfoHarness] setDbId failed on idx {idx}: {e}", xbmc.LOGWARNING)

    # playable hint
    if playable is None:
        playable = (click_mode == "play")
    li.setProperty('IsPlayable', 'true' if playable else 'false')

    # optional properties (strings)
    props = props or {}
    for k, v in props.items():
        if v is not None:
            li.setProperty(str(k), str(v))

    # optional setPath
    if set_path and vdb:
        li.setPath(vdb)

    # context menu to test direct info opening
    cm = []
    cm.append(("[Info] Action(Info) on focused item", "Action(Info)"))
    if vdb:
        cm.append(("[Info] ActivateWindow(VideoInformation) UNQUOTED",
                   f'ActivateWindow(VideoInformation,{vdb},return)'))
        cm.append(("[Info] ActivateWindow(VideoInformation) QUOTED",
                   f'ActivateWindow(VideoInformation,"{vdb}",return)'))
        cm.append(("[Info] Library hop (Videos + Info) UNQUOTED",
                   f'RunPlugin({sys.argv[0]}?action=test_info_click&mode=libhop_uq&vdb={vdb})'))
        cm.append(("[Info] Library hop (Videos + Info) QUOTED",
                   f'RunPlugin({sys.argv[0]}?action=test_info_click&mode=libhop_q&vdb={vdb})'))
    li.addContextMenuItems(cm, replaceItems=False)

    xbmcplugin.addDirectoryItem(ADDON_HANDLE, url=url, listitem=li, isFolder=is_folder)


# ------------------------------
# Entry points
# ------------------------------

def run_test_info_variants(addon_handle, params=None):
    params = params or {}
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', '883') or 883)
    tvshowid = params.get('tvshowid')  # optional
    season = params.get('season')      # optional

    major = _kodi_major()
    vdb_slash = _vdb_path(dbtype, dbid, tvshowid, season, trailing_slash=True)
    vdb_noslash = _vdb_path(dbtype, dbid, tvshowid, season, trailing_slash=False)

    xbmc.log(f"[InfoHarness] Building list (Kodi {major}), {dbtype} {dbid} -> "
             f"{vdb_slash} | {vdb_noslash}", xbmc.LOGINFO)

    xbmcplugin.setContent(addon_handle, 'movies')

    # --- Common baseline items ---
    _add_variant(1,  url=f"{sys.argv[0]}?action=noop", vdb=vdb_slash,  click_mode="noop")
    _add_variant(2,  url=f"{sys.argv[0]}?action=noop", vdb=vdb_noslash, click_mode="noop")
    _add_variant(3,  url=vdb_slash,  vdb=vdb_slash,  click_mode="noop")       # direct vdb url
    _add_variant(4,  url=vdb_noslash, vdb=vdb_noslash, click_mode="noop")     # direct vdb url (no slash)
    _add_variant(5,  url=f"{sys.argv[0]}?action=noop", vdb=vdb_slash, set_path=True, click_mode="noop")
    _add_variant(6,  url=f"{sys.argv[0]}?action=noop", vdb=vdb_noslash, set_path=True, click_mode="noop")

    # --- Click variants that explicitly try to open the info dialog different ways ---
    _add_variant(7,  url=f"{sys.argv[0]}?action=test_info_click&mode=info_direct_uq&vdb={vdb_slash}",
                 vdb=vdb_slash, click_mode="info_direct_uq", playable=False)
    _add_variant(8,  url=f"{sys.argv[0]}?action=test_info_click&mode=info_direct_q&vdb={vdb_slash}",
                 vdb=vdb_slash, click_mode="info_direct_q", playable=False)
    _add_variant(9,  url=f"{sys.argv[0]}?action=test_info_click&mode=container_update&vdb={vdb_slash}",
                 vdb=vdb_slash, click_mode="container_update", playable=False)

    # --- Matrix-oriented: library hop + Action(Info) ---
    _add_variant(10, url=f"{sys.argv[0]}?action=test_info_click&mode=libhop_uq&vdb={vdb_slash}",
                 vdb=vdb_slash, click_mode="libhop_uq", playable=False)
    _add_variant(11, url=f"{sys.argv[0]}?action=test_info_click&mode=libhop_q&vdb={vdb_slash}",
                 vdb=vdb_slash, click_mode="libhop_q", playable=False)
    _add_variant(12, url=f"{sys.argv[0]}?action=test_info_click&mode=libhop_uq&vdb={vdb_noslash}",
                 vdb=vdb_noslash, click_mode="libhop_uq", playable=False)
    _add_variant(13, url=f"{sys.argv[0]}?action=test_info_click&mode=libhop_q&vdb={vdb_noslash}",
                 vdb=vdb_noslash, click_mode="libhop_q", playable=False)

    # --- Control: play target (helps verify the videodb target resolves) ---
    _add_variant(14, url=f"{sys.argv[0]}?action=test_info_click&mode=play&vdb={vdb_slash}",
                 vdb=vdb_slash, click_mode="play", playable=True)

    # --- Nexus+ path: mark items with InfoTag.setDbId ---
    if major >= 20:
        _add_variant(20, url=f"{sys.argv[0]}?action=noop",
                     vdb=vdb_slash, click_mode="noop",
                     use_dbid_tag=True, dbtype=dbtype, dbid=dbid)

        _add_variant(21, url=f"{sys.argv[0]}?action=noop",
                     vdb=vdb_slash, set_path=True, click_mode="noop",
                     use_dbid_tag=True, dbtype=dbtype, dbid=dbid)

        _add_variant(22, url=vdb_slash,
                     vdb=vdb_slash, click_mode="noop",
                     use_dbid_tag=True, dbtype=dbtype, dbid=dbid)

        # Also include a click that shows info directly (even though Action(Info) should work)
        _add_variant(23, url=f"{sys.argv[0]}?action=test_info_click&mode=info_direct_q&vdb={vdb_slash}",
                     vdb=vdb_slash, click_mode="info_direct_q",
                     use_dbid_tag=True, dbtype=dbtype, dbid=dbid, playable=False)

    xbmcplugin.endOfDirectory(addon_handle)


def handle_test_info_click(params, addon_handle):
    """
    Executes the chosen GUI action immediately.
    Also logs JSON-RPC cast presence for the provided videodb path (if dbid can be guessed).
    Accepted params:
        mode = info_direct_uq | info_direct_q | libhop_uq | libhop_q | container_update | play
        vdb  = videodb://... (required)
    """
    mode = params.get('mode', 'noop')
    vdb = params.get('vdb', '')
    major = _kodi_major()

    # Try to infer dbtype/dbid for cast logging
    dbtype, dbid = None, None
    try:
        if vdb.startswith('videodb://movies/titles/'):
            dbtype = 'movie'
            tail = vdb[len('videodb://movies/titles/'):]
            tail = tail.rstrip('/')
            dbid = int(''.join(ch for ch in tail if ch.isdigit()))
        elif vdb.startswith('videodb://tvshows/titles/'):
            dbtype = 'tvshow'
            tail = vdb[len('videodb://tvshows/titles/'):]
            tail = tail.rstrip('/')
            dbid = int(''.join(ch for ch in tail if ch.isdigit()))
    except Exception:
        pass

    if dbtype and dbid:
        _jsonrpc_cast_check(dbtype, dbid)

    xbmc.log(f"[InfoHarness] handle_test_info_click: mode={mode}, vdb={vdb}, kodi={major}", xbmc.LOGINFO)

    try:
        if mode == "info_direct_uq":
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,{vdb},return)')
        elif mode == "info_direct_q":
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,"{vdb}",return)')
        elif mode == "libhop_uq":
            xbmc.executebuiltin(f'ActivateWindow(Videos,{vdb},return)')
            xbmc.sleep(350)
            xbmc.executebuiltin('Action(Info)')
        elif mode == "libhop_q":
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{vdb}",return)')
            xbmc.sleep(350)
            xbmc.executebuiltin('Action(Info)')
        elif mode == "container_update":
            xbmc.executebuiltin(f'Container.Update({vdb},replace)')
            xbmc.sleep(350)
            xbmc.executebuiltin('Action(Info)')
        elif mode == "play":
            xbmc.executebuiltin(f'PlayMedia({vdb})')
        else:
            xbmcgui.Dialog().notification("Info Harness", "noop — use context menu", xbmcgui.NOTIFICATION_INFO, 2500)
    except Exception as e:
        xbmc.log(f"[InfoHarness] Error in handle_test_info_click: {e}", xbmc.LOGERROR)
    finally:
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass
