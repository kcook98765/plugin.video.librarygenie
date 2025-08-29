# -*- coding: utf-8 -*-
"""
Test matrix for Kodi DialogVideoInfo resolution.

This builds multiple variants of the SAME movie ListItem using different
combinations of:
- URL (plugin vs videodb)
- listitem.setPath(videodb://…)
- listitem.setProperty('dbid'/'dbtype'/'mediatype')
- Container content typing
- Click behavior (open Info via ActivateWindow on videodb path, quoted vs unquoted)

No cast is injected. Minimal basic info only.

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
        # tvshow info page, not a season/episode
        return f'videodb://tvshows/titles/{dbid}/'
    elif dbtype == 'episode' and tvshowid is not None and season is not None:
        return f'videodb://tvshows/titles/{int(tvshowid)}/{int(season)}/{dbid}/'
    # fallback
    return f'videodb://movies/titles/{dbid}/'


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
    playable=None
):
    """
    click_mode:
      - "noop"            : clicking calls plugin but does nothing (use context menu to test)
      - "info_unquoted"   : plugin opens info via ActivateWindow(VideoInformation,<vdb>,return)
      - "info_quoted"     : plugin opens info via ActivateWindow(VideoInformation,"<vdb>",return)
      - "play"            : plugin calls PlayMedia(<vdb>) to verify the target
    """
    label_bits = [f"{idx:02d}", click_mode]
    if set_path:
        label_bits.append("+path")
    if props:
        label_bits.append("+props")
    label = " ".join(label_bits)

    li = xbmcgui.ListItem(label=label)

    # Basic info ONLY (no cast)
    if set_info:
        info = {
            'title': f'Variant {idx:02d}',
            'year': 2000 + idx,
            'mediatype': 'movie'
        }
        li.setInfo('video', info)

    # Decide "playable" hint:
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

    # Context menu to test both ways of opening Info
    cm = []
    cm.append(("[Info] Action(Info) on focused item", "Action(Info)"))
    if vdb:
        # Unquoted (Matrix-friendly)
        cm.append(("[Info] ActivateWindow(VideoInformation) on VDB (UNQUOTED)",
                   f'ActivateWindow(VideoInformation,{vdb},return)'))
        # Quoted (works on later builds; helps compare)
        cm.append(("[Info] ActivateWindow(VideoInformation) on VDB (QUOTED)",
                   f'ActivateWindow(VideoInformation,"{vdb}",return)'))
    li.addContextMenuItems(cm, replaceItems=False)

    xbmcplugin.addDirectoryItem(addon_handle, url=url, listitem=li, isFolder=False)


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

    # ── A) Your original "plugin URL" style (compare with Action(Info) vs context) ──
    _add_variant(1, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 click_mode="noop")

    _add_variant(2, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid},
                 click_mode="noop")

    _add_variant(3, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbtype': dbtype},
                 click_mode="noop")

    _add_variant(4, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype},
                 click_mode="noop")

    _add_variant(5, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'mediatype': 'movie'},
                 click_mode="noop")

    _add_variant(6, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'},
                 click_mode="noop")

    _add_variant(7, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 click_mode="noop")

    _add_variant(8, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 props={'dbid': dbid},
                 click_mode="noop")

    _add_variant(9, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'},
                 click_mode="noop")

    # ── B) Direct videodb URL (compare how click behaves vs context menu) ──
    _add_variant(10, addon_handle,
                 url=vdb,
                 vdb=vdb,
                 click_mode="noop")

    _add_variant(11, addon_handle,
                 url=vdb,
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype},
                 click_mode="noop")

    # 12) No setInfo at all (still typed by container)
    _add_variant(12, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_info=False,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'},
                 click_mode="noop")

    # ── C) NEW: Items whose *click* opens info via ActivateWindow on VDB ──
    # 13) Click -> info (UNQUOTED)
    _add_variant(13, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=info_unquoted&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 click_mode="info_unquoted",
                 playable=False)

    # 14) Click -> info (QUOTED)
    _add_variant(14, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=info_quoted&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 click_mode="info_quoted",
                 playable=False)

    # 15) Click -> play VDB (sanity check that the vdb target is correct)
    _add_variant(15, addon_handle,
                 url=f"{sys.argv[0]}?action=test_info_click&mode=play&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 click_mode="play",
                 playable=True)

    xbmcplugin.endOfDirectory(addon_handle)


def handle_test_info_click(params, addon_handle):
    """
    Router for the clickable test variants (13–15).
    Performs the GUI action immediately (no directory rendering).
    """
    mode = params.get('mode', 'noop')
    dbtype = params.get('dbtype', 'movie')
    dbid = int(params.get('dbid', '0') or 0)
    tvshowid = params.get('tvshowid')
    season = params.get('season')

    vdb = _vdb_path(dbtype, dbid, tvshowid, season)
    xbmc.log(f"[TestInfoVariants] handle_test_info_click mode={mode} vdb={vdb}", xbmc.LOGINFO)

    try:
        if mode == "info_unquoted":
            # Matrix-friendly: do NOT quote the VDB path
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,{vdb},return)')
        elif mode == "info_quoted":
            # Compare behavior with quoted path
            xbmc.executebuiltin(f'ActivateWindow(VideoInformation,"{vdb}",return)')
        elif mode == "play":
            xbmc.executebuiltin(f'PlayMedia({vdb})')
        else:
            xbmcgui.Dialog().notification("Test Info Variants", "noop: use context menu to test Info", xbmcgui.NOTIFICATION_INFO, 2500)
    except Exception as e:
        xbmc.log(f"[TestInfoVariants] Error in handle_test_info_click: {e}", xbmc.LOGERROR)
    finally:
        # Don't try to render a directory for this action
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass
