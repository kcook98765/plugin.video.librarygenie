
# -*- coding: utf-8 -*-
"""
Test matrix for Kodi DialogVideoInfo resolution.
Builds many variants of the SAME movie ListItem using different combinations of:
- ListItem URL (plugin vs videodb)
- listitem.setPath(videodb://...)
- listitem.setProperty('dbid'/'dbtype'/'mediatype')
- container content

No cast is injected. Minimal basic info only.
Open the info dialog (press "i" or use the context menu entries) and check if cast appears.

Usage (inside your plugin router):
    from .test_info_variants import run_test_info_variants
    ...
    elif action == 'test_info_variants':
        run_test_info_variants(addon_handle, params)

You can pass dbid/dbtype via params, defaults below are safe:
    ?action=test_info_variants&dbtype=movie&dbid=883
"""

import sys
import json
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import parse_qs

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

def _add_variant(idx, addon_handle, *, url, vdb, set_path=False, props=None, set_info=True):
    label = f"{idx:02d} • {url.split('?',1)[0].replace('videodb://','vdb://')}"
    li = xbmcgui.ListItem(label=label)

    # Basic info ONLY (no cast)
    if set_info:
        info = {
            'title': f'Variant {idx:02d}',
            'year': 2000 + idx,  # just to vary visually
            'mediatype': 'movie'
        }
        li.setInfo('video', info)

    # Mark clickable
    li.setProperty('IsPlayable', 'true')

    # Optional properties (must be strings)
    props = props or {}
    for k, v in props.items():
        if v is not None:
            li.setProperty(str(k), str(v))

    # Optional listitem path
    if set_path and vdb:
        li.setPath(vdb)

    # Helpful context menu to open info in different ways
    cm = []
    cm.append(("[Info] Built-in on focused item", "Action(Info)"))
    if vdb:
        cm.append(("[Info] ActivateWindow(VideoInformation) on VDB path",
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

    # For all test cases, keep container strongly typed as movies:
    xbmcplugin.setContent(addon_handle, 'movies')

    # 01) Plugin URL only (no props, no setPath)
    _add_variant(1, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb)

    # 02) Plugin URL with dbid property
    _add_variant(2, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid})

    # 03) Plugin URL with dbtype property
    _add_variant(3, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbtype': dbtype})

    # 04) Plugin URL with both dbid and dbtype properties
    _add_variant(4, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype})

    # 05) Plugin URL with mediatype property
    _add_variant(5, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'mediatype': 'movie'})

    # 06) Plugin URL with all three properties
    _add_variant(6, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'})

    # 07) Plugin URL with setPath to videodb
    _add_variant(7, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True)

    # 08) Plugin URL with setPath + dbid property
    _add_variant(8, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 props={'dbid': dbid})

    # 09) Plugin URL with setPath + all properties
    _add_variant(9, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_path=True,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'})

    # 10) Direct videodb URL (no plugin)
    _add_variant(10, addon_handle,
                 url=vdb,
                 vdb=vdb)

    # 11) Direct videodb URL with properties
    _add_variant(11, addon_handle,
                 url=vdb,
                 vdb=vdb,
                 props={'dbid': dbid, 'dbtype': dbtype})

    # 12) No setInfo call at all
    _add_variant(12, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb,
                 set_info=False,
                 props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'})

    xbmcplugin.endOfDirectory(addon_handle)
