#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Builder
Builds ListItems with proper metadata and resume information
"""

import json
from typing import List, Dict, Any, Optional

import xbmc
import xbmcgui
import xbmcplugin

from ..utils.logger import get_logger


def is_kodi_v20_plus() -> bool:
    """
    Check if running Kodi version 20 or higher
    Returns:
        bool: True if Kodi major version >= 20, False otherwise
    """
    try:
        build_version = xbmc.getInfoLabel("System.BuildVersion")
        # "20.2 (20.2.0) Git:..." -> "20"
        major = int(build_version.split('.')[0].split('-')[0])
        return major >= 20
    except Exception:
        # Safe fallback (Matrix behavior)
        return False


class ListItemBuilder:
    """Builds ListItems with proper separation between Kodi library and external items"""

    # -------- lifecycle --------
    def __init__(self, addon_handle: int, addon_id: str):
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_logger(__name__)

    # -------- public API --------
    def build_directory(self, items: List[Dict[str, Any]], content_type: str = "movies") -> bool:
        """
        Build a directory with proper content type and ListItems.

        Args:
            items: list of (possibly mixed) media item dicts
            content_type: "movies", "tvshows", or "episodes"

        Returns:
            bool: success
        """
        try:
            count = len(items)
            self.logger.info(f"DIRECTORY BUILD: {count} items (content_type='{content_type}')")
            xbmcplugin.setContent(self.addon_handle, content_type)

            # Add a few sane sort methods once
            for const in (
                xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
                xbmcplugin.SORT_METHOD_DATE,
                xbmcplugin.SORT_METHOD_VIDEO_YEAR,
            ):
                xbmcplugin.addSortMethod(self.addon_handle, const)

            tuples: List[tuple] = []
            ok = 0
            fail = 0
            for idx, raw in enumerate(items, start=1):
                try:
                    item = self._normalize_item(raw)  # canonical shape
                    built = self._build_single_item(item)
                    if built:
                        tuples.append(built)  # (url, listitem, is_folder)
                        ok += 1
                    else:
                        fail += 1
                        self.logger.warning(f"DIRECTORY BUILD: failed to build #{idx}: '{raw.get('title','Unknown')}'")
                except Exception as ie:
                    fail += 1
                    self.logger.error(f"DIRECTORY BUILD: exception for #{idx}: {ie}")

            self.logger.info(f"DIRECTORY BUILD: {ok} OK, {fail} failed")

            for url, li, is_folder in tuples:
                xbmcplugin.addDirectoryItem(
                    handle=self.addon_handle, url=url, listitem=li, isFolder=is_folder
                )

            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True)
            return True
        except Exception as e:
            self.logger.error(f"DIRECTORY BUILD: fatal error: {e}")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
            return False

    # -------- internals --------
    def _build_single_item(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Decide whether to build a library-backed or external item.
        Returns (url, listitem, is_folder) or None on failure.
        """
        title = item.get('title', 'Unknown')
        media_type = item.get('media_type', 'movie')
        kodi_id = item.get('kodi_id')  # already normalized to int/None
        self.logger.debug(f"ITEM BUILD: '{title}' type={media_type} kodi_id={kodi_id}")

        try:
            # Treat as library-backed ONLY if we truly have a library DB id for movies/episodes
            if media_type in ('movie', 'episode') and isinstance(kodi_id, int):
                return self._create_library_listitem(item)
            else:
                return self._create_external_item(item)
        except Exception as e:
            self.logger.error(f"ITEM BUILD: failed for '{title}': {e}")
            return None

    # ----- normalization -----
    def _normalize_item(self, src: Dict[str, Any]) -> Dict[str, Any]:
        """
        Canonicalize a raw item dict to the lightweight, version-safe shape
        consumed by this builder.
        """
        out: Dict[str, Any] = {}

        # media type
        media_type = (src.get('media_type') or src.get('type') or 'movie').lower()
        if media_type not in ('movie', 'episode', 'tvshow', 'musicvideo'):
            media_type = 'movie'
        out['media_type'] = media_type

        # kodi id (only for movie/episode)
        kodi_id = None
        if media_type == 'movie':
            kodi_id = src.get('kodi_id') or src.get('movieid')
        elif media_type == 'episode':
            kodi_id = src.get('kodi_id') or src.get('episodeid')
        # Do NOT infer from generic 'id' to avoid misclassification
        out['kodi_id'] = int(kodi_id) if isinstance(kodi_id, (int, float)) else (kodi_id if isinstance(kodi_id, int) else None)

        # identity / titles
        out['title'] = src.get('title') or src.get('label') or 'Unknown'
        if src.get('originaltitle') and src.get('originaltitle') != out['title']:
            out['originaltitle'] = src.get('originaltitle')
        if src.get('sorttitle'):
            out['sorttitle'] = src.get('sorttitle')

        # year
        try:
            out['year'] = int(src.get('year')) if src.get('year') is not None else None
        except Exception:
            out['year'] = None

        # genre -> comma string
        genre = src.get('genre')
        if isinstance(genre, list):
            out['genre'] = ", ".join([g for g in genre if g])
        elif isinstance(genre, str):
            out['genre'] = genre
        # else omit

        # plot/outline
        plot = src.get('plot') or src.get('plotoutline') or src.get('description')
        if plot:
            out['plot'] = plot

        # rating/votes/mpaa
        try:
            if src.get('rating') is not None:
                out['rating'] = float(src['rating'])
        except Exception:
            pass
        try:
            if src.get('votes') is not None:
                out['votes'] = int(src['votes'])
        except Exception:
            pass
        if src.get('mpaa'):
            out['mpaa'] = src['mpaa']

        # duration -> minutes (Matrix-safe)
        minutes = None
        if src.get('duration_minutes') is not None:
            # caller already provided minutes
            try:
                minutes = int(src['duration_minutes'])
            except Exception:
                minutes = None
        elif src.get('runtime') is not None:
            # runtime commonly minutes
            try:
                minutes = int(src['runtime'])
            except Exception:
                minutes = None
        elif src.get('duration') is not None:
            # 'duration' may be minutes or seconds; best effort:
            try:
                d = int(src['duration'])
                minutes = d // 60 if d > 300 else d
            except Exception:
                minutes = None
        if minutes and minutes > 0:
            out['duration_minutes'] = minutes

        # studio / country
        if src.get('studio'):
            out['studio'] = src['studio'] if isinstance(src['studio'], str) else (src['studio'][0] if isinstance(src['studio'], list) and src['studio'] else None)
        if src.get('country'):
            out['country'] = src['country'] if isinstance(src['country'], str) else (src['country'][0] if isinstance(src['country'], list) and src['country'] else None)

        # dates
        out['premiered'] = src.get('premiered') or src.get('dateadded')

        # episode extras
        if media_type == 'episode':
            if src.get('tvshowtitle') or src.get('showtitle'):
                out['tvshowtitle'] = src.get('tvshowtitle') or src.get('showtitle')
            for key in ('season', 'episode'):
                if src.get(key) is not None:
                    try:
                        out[key] = int(src[key])
                    except Exception:
                        pass
            if src.get('aired'):
                out['aired'] = src['aired']
            if src.get('playcount') is not None:
                try:
                    out['playcount'] = int(src['playcount'])
                except Exception:
                    pass
            if src.get('lastplayed'):
                out['lastplayed'] = src['lastplayed']
            # Helpful if present for videodb path construction
            if src.get('tvshowid') is not None:
                try:
                    out['tvshowid'] = int(src['tvshowid'])
                except Exception:
                    pass

        # artwork (flatten)
        poster = src.get('poster') or src.get('thumbnail')
        fanart = src.get('fanart')
        if poster:
            out['poster'] = poster
        if fanart:
            out['fanart'] = fanart

        art_blob = src.get('art')
        if art_blob:
            try:
                art_dict = json.loads(art_blob) if isinstance(art_blob, str) else art_blob
                if isinstance(art_dict, dict):
                    for k in ('thumb', 'banner', 'landscape', 'clearlogo'):
                        v = art_dict.get(k)
                        if v:
                            out[k] = v
            except Exception:
                # non-fatal
                pass

        # resume (seconds)
        resume = src.get('resume') or {}
        pos = resume.get('position_seconds') or resume.get('position') or 0
        tot = resume.get('total_seconds') or resume.get('total') or 0
        try:
            pos = int(pos)
        except Exception:
            pos = 0
        try:
            tot = int(tot)
        except Exception:
            tot = 0
        out['resume'] = {'position_seconds': pos, 'total_seconds': tot}

        # preserve source if provided, can be useful for logging/routes
        if src.get('source'):
            out['source'] = src['source']

        return out

    # ----- library & external builders -----
    def _create_library_listitem(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Build library-backed movie/episode row as (url, listitem, is_folder=False)
        with lightweight info and versioned resume.
        """
        try:
            title = item.get('title', 'Unknown')
            media_type = item.get('media_type', 'movie')
            kodi_id = item.get('kodi_id')

            # Label: include year if present
            display = f"{title} ({item['year']})" if item.get('year') else title
            li = xbmcgui.ListItem(label=display)

            # Lightweight info (minutes; no heavy arrays)
            info = self._build_lightweight_info(item)
            li.setInfo('video', info)

            # Art (poster/fanart minimum)
            art = self._build_art_dict(item)
            if art:
                li.setArt(art)

            # Set library identity properties (v19 compatible)
            li.setProperty('dbtype', media_type)
            li.setProperty('dbid', str(kodi_id))
            li.setProperty('mediatype', media_type)

            # URL (videodb preferred)
            url = None
            is_folder = False
            if media_type == 'movie' and isinstance(kodi_id, int):
                url = f"videodb://movies/titles/{kodi_id}"
                li.setPath(url)
                li.setProperty('IsPlayable', 'true')
            elif media_type == 'episode' and isinstance(kodi_id, int):
                tvshowid = item.get('tvshowid')
                season = item.get('season')
                if isinstance(tvshowid, int) and isinstance(season, int):
                    url = f"videodb://tvshows/titles/{tvshowid}/{season}/{kodi_id}"
                    li.setPath(url)
                    li.setProperty('IsPlayable', 'true')
                else:
                    # missing parts for videodb path -> fallback plugin play URL
                    url = self._build_playback_url(item)
                    li.setPath(url)
                    li.setProperty('IsPlayable', 'true')
            else:
                # Shouldn't reach here for library method, but guard anyway
                url = self._build_playback_url(item)
                li.setPath(url)
                li.setProperty('IsPlayable', 'true')

            # Set v20+ InfoTagVideo properties only if available (Step 8)
            if is_kodi_v20_plus():
                try:
                    video_info_tag = li.getVideoInfoTag()
                    video_info_tag.setMediaType(media_type)
                    video_info_tag.setDbId(kodi_id)
                    self.logger.debug(f"LIB ITEM v20+: Set InfoTagVideo for '{title}'")
                except Exception as e:
                    self.logger.warning(f"LIB ITEM v20+: InfoTagVideo failed for '{title}': {e}")

            # Resume (always for library movies/episodes)
            self._set_resume_info_versioned(li, item)

            self.logger.debug(f"LIB ITEM: '{title}' -> {url}")
            return url, li, is_folder
        except Exception as e:
            self.logger.error(f"LIB ITEM: failed for '{item.get('title','Unknown')}': {e}")
            return None

    def _create_external_item(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Build plugin/external row as (url, listitem, is_folder)
        Using lightweight info; no heavy fields (cast/streamdetails) in list view.
        When there's no kodi_id, use plugin:// URL with same lightweight profile as library items.
        """
        try:
            title = item.get('title', 'Unknown')
            media_type = item.get('media_type', 'movie')

            display = f"{title} ({item['year']})" if item.get('year') else title
            li = xbmcgui.ListItem(label=display)

            # Apply exact same lightweight info profile as library items (Step 4)
            info = self._build_lightweight_info(item)
            li.setInfo('video', info)

            # Apply exact same art keys as library items (Step 4)
            art = self._build_art_dict(item)
            if art:
                li.setArt(art)

            # Plugin URL for external/plugin-only items (no kodi_id)
            url = self._build_playback_url(item)
            li.setPath(url)
            
            # Keep folder/playable flags correct - IsPlayable="true" only for playable rows
            is_playable = bool(item.get('play'))
            is_folder = not is_playable
            if is_playable:
                li.setProperty('IsPlayable', 'true')
            # Do NOT set IsPlayable='false' for folders/non-playable

            # Resume for plugin-only: only if you maintain your own resume store
            # (Skip resume for external items - at your discretion)
            # The "always show resume" rule applies to library items only

            # External context menu
            self._set_external_context_menu(li, item)

            self.logger.debug(f"EXT ITEM: '{title}' type={media_type} -> {url} (playable={is_playable}, folder={is_folder})")
            return url, li, is_folder
        except Exception as e:
            self.logger.error(f"EXT ITEM: failed for '{item.get('title','Unknown')}': {e}")
            return None

    # ----- info/art/resume helpers -----
    def _build_lightweight_info(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build lightweight info dictionary for list items (no heavy arrays).
        Duration is in minutes; mediatype set for overlays.
        
        IMPORTANT: This method intentionally avoids heavy fields like:
        - cast/crew arrays
        - deep streamdetails 
        - detailed metadata that would slow down list scrolling
        This keeps list views snappy per Kodi's own approach.
        """
        info: Dict[str, Any] = {}
        # Common
        if item.get('title'):
            info['title'] = item['title']
        if item.get('originaltitle') and item['originaltitle'] != item.get('title'):
            info['originaltitle'] = item['originaltitle']
        if item.get('sorttitle'):
            info['sorttitle'] = item['sorttitle']
        if item.get('year') is not None:
            info['year'] = int(item['year'])
        if item.get('genre'):
            info['genre'] = item['genre']
        if item.get('plot'):
            info['plot'] = item['plot']
        if item.get('rating') is not None:
            info['rating'] = float(item['rating'])
        if item.get('votes') is not None:
            info['votes'] = int(item['votes'])
        if item.get('mpaa'):
            info['mpaa'] = item['mpaa']
        if item.get('duration_minutes') is not None:
            info['duration'] = int(item['duration_minutes'])
        if item.get('studio'):
            info['studio'] = item['studio']
        if item.get('country'):
            info['country'] = item['country']
        if item.get('premiered'):
            info['premiered'] = item['premiered']

        # Episode extras
        if item.get('media_type') == 'episode':
            if item.get('tvshowtitle'):
                info['tvshowtitle'] = item['tvshowtitle']
            if item.get('season') is not None:
                info['season'] = int(item['season'])
            if item.get('episode') is not None:
                info['episode'] = int(item['episode'])
            if item.get('aired'):
                info['aired'] = item['aired']
            if item.get('playcount') is not None:
                info['playcount'] = int(item['playcount'])
            if item.get('lastplayed'):
                info['lastplayed'] = item['lastplayed']

        info['mediatype'] = item.get('media_type', 'movie')
        return info

    def _build_art_dict(self, item: Dict[str, Any]) -> Dict[str, str]:
        """
        Poster/fanart minimum; add others only if valid.
        """
        art: Dict[str, str] = {}
        if item.get('poster'):
            art['poster'] = item['poster']
            # sensible thumb fallback
            art['thumb'] = item['poster']
        elif item.get('thumb'):
            art['thumb'] = item['thumb']
        if item.get('fanart'):
            art['fanart'] = item['fanart']
        for k in ('banner', 'landscape', 'clearlogo'):
            v = item.get(k)
            if v:
                art[k] = v
        return art

    def _set_resume_info_versioned(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """
        Set resume info for list rows (seconds) in a version-safe way.
        Always applied for library movies/episodes when position/total are > 0.
        """
        try:
            res = item.get('resume') or {}
            pos = int(res.get('position_seconds') or 0)
            tot = int(res.get('total_seconds') or 0)
            if pos > 0 and tot > 0:
                if is_kodi_v20_plus():
                    try:
                        tag = list_item.getVideoInfoTag()
                        tag.setResumePoint(pos, tot)
                        self.logger.debug(f"RESUME v20+: {pos}/{tot} sec")
                    except Exception as e:
                        # Fallback to v19 properties
                        list_item.setProperty('ResumeTime', str(pos))
                        list_item.setProperty('TotalTime', str(tot))
                        self.logger.warning(f"RESUME v20+ failed, fallback to props: {e}")
                else:
                    list_item.setProperty('ResumeTime', str(pos))
                    list_item.setProperty('TotalTime', str(tot))
                    self.logger.debug(f"RESUME v19: {pos}/{tot} sec")
        except Exception as e:
            self.logger.error(f"RESUME: failed to set resume info: {e}")

    # ----- misc helpers -----
    def _build_playback_url(self, item: Dict[str, Any]) -> str:
        """
        Return direct play URL if provided; otherwise build a plugin URL
        that routes to info/play handling.
        """
        play = item.get('play')
        if play:
            return play
        item_id = item.get('id') or item.get('imdb_id') or ''
        return f"plugin://{self.addon_id}?action=info&item_id={item_id}"

    def _set_external_context_menu(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Context menu for external items"""
        cm = []
        # Search the library for this title
        cm.append((
            "Search in Library",
            f"RunPlugin(plugin://{self.addon_id}/?action=search_library&title={item.get('title','')})"
        ))
        # Add to list
        cm.append((
            "Add to List",
            f"RunPlugin(plugin://{self.addon_id}/?action=add_to_list&item_id={item.get('id','')})"
        ))
        list_item.addContextMenuItems(cm)
