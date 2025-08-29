
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
                 vdb=vdb, set_path=False, props={}, set_info=True)

    # 02) Plugin URL + dbid/dbtype props (common plugin pattern)
    _add_variant(2, addon_handle,
                 url=f"{sys.argv[0]}?action=noop&dbtype={dbtype}&dbid={dbid}",
                 vdb=vdb, set_path=False, props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'}, set_info=True)

    # 03) Plugin URL + setPath(vdb) only (key Matrix test)
    _add_variant(3, addon_handle,
                 url=f"{sys.argv[0]}?action=noop",
                 vdb=vdb, set_path=True, props={}, set_info=True)

    # 04) Plugin URL + setPath(vdb) + dbid/dbtype props (often the safest on v19)
    _add_variant(4, addon_handle,
                 url=f"{sys.argv[0]}?action=noop",
                 vdb=vdb, set_path=True, props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'}, set_info=True)

    # 05) URL IS the videodb path (no setPath, no props)
    _add_variant(5, addon_handle,
                 url=vdb, vdb=vdb, set_path=False, props={}, set_info=True)

    # 06) URL IS the videodb path + dbid/dbtype props (belt + suspenders)
    _add_variant(6, addon_handle,
                 url=vdb, vdb=vdb, set_path=False, props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'}, set_info=True)

    # 07) Plugin URL + 'path' property pointing at vdb (no setPath)
    _add_variant(7, addon_handle,
                 url=f"{sys.argv[0]}?action=noop",
                 vdb=vdb, set_path=False, props={'path': vdb, 'dbid': dbid, 'dbtype': dbtype}, set_info=True)

    # 08) Plugin URL + setPath(vdb) but NO setInfo at all (bare minimum)
    _add_variant(8, addon_handle,
                 url=f"{sys.argv[0]}?action=noop",
                 vdb=vdb, set_path=True, props={'dbid': dbid, 'dbtype': dbtype}, set_info=False)

    # 09) Plugin URL + ONLY mediatype in info (no props, no setPath)
    _add_variant(9, addon_handle,
                 url=f"{sys.argv[0]}?action=noop",
                 vdb=vdb, set_path=False, props={}, set_info=True)

    # 10) URL IS videodb + setPath(vdb) as well (overkill) + props
    _add_variant(10, addon_handle,
                 url=vdb, vdb=vdb, set_path=True, props={'dbid': dbid, 'dbtype': dbtype, 'mediatype': 'movie'}, set_info=True)

    xbmcplugin.endOfDirectory(addon_handle, succeeded=True)

# Allow running directly (optional convenience)
if __name__ == '__main__' and ADDON_HANDLE != -1:
    _p = _params_to_dict(sys.argv)
    run_test_info_variants(ADDON_HANDLE, _p)
