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
# The original code had an incorrect import for get_select_pref.
# It was defined in this file but intended to be imported from config_manager.
# The fix involves changing the import path to the correct location.
from ..config.config_manager import get_select_pref
from .matrix_info_helper import open_movie_info_v19


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
            self.logger.info(f"DIRECTORY BUILD: Starting build with {count} items (content_type='{content_type}')")
            self.logger.debug(f"DIRECTORY BUILD: Setting content type to '{content_type}' for handle {self.addon_handle}")
            xbmcplugin.setContent(self.addon_handle, content_type)

            # Add a few sane sort methods once
            sort_methods = [
                ("SORT_METHOD_TITLE_IGNORE_THE", xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE),
                ("SORT_METHOD_DATE", xbmcplugin.SORT_METHOD_DATE),
                ("SORT_METHOD_VIDEO_YEAR", xbmcplugin.SORT_METHOD_VIDEO_YEAR),
            ]
            self.logger.debug(f"DIRECTORY BUILD: Adding {len(sort_methods)} sort methods")
            for method_name, const in sort_methods:
                xbmcplugin.addSortMethod(self.addon_handle, const)
                self.logger.debug(f"DIRECTORY BUILD: Added sort method {method_name}")

            tuples: List[tuple] = []
            ok = 0
            fail = 0
            for idx, raw in enumerate(items, start=1):
                try:
                    self.logger.debug(f"DIRECTORY BUILD: Processing item #{idx}/{count}: '{raw.get('title','Unknown')}'")
                    self.logger.debug(f"DIRECTORY BUILD: Raw item #{idx} data: {raw}")

                    item = self._normalize_item(raw)  # canonical shape
                    self.logger.debug(f"DIRECTORY BUILD: Normalized item #{idx}: {item}")

                    built = self._build_single_item(item)
                    if built:
                        url, listitem, is_folder = built
                        self.logger.debug(f"DIRECTORY BUILD: Built item #{idx} - URL: '{url}', isFolder: {is_folder}")
                        tuples.append(built)  # (url, listitem, is_folder)
                        ok += 1
                    else:
                        fail += 1
                        self.logger.warning(f"DIRECTORY BUILD: failed to build #{idx}: '{raw.get('title','Unknown')}'")
                except Exception as ie:
                    fail += 1
                    self.logger.error(f"DIRECTORY BUILD: exception for #{idx}: {ie}")

            self.logger.info(f"DIRECTORY BUILD: Processed {count} items - {ok} OK, {fail} failed")

            self.logger.debug(f"DIRECTORY BUILD: Adding {len(tuples)} directory items to Kodi")
            for idx, (url, li, is_folder) in enumerate(tuples, start=1):
                self.logger.debug(f"DIRECTORY BUILD: Adding item #{idx} - URL: '{url}', isFolder: {is_folder}")
                xbmcplugin.addDirectoryItem(
                    handle=self.addon_handle, url=url, listitem=li, isFolder=is_folder
                )

            self.logger.debug(f"DIRECTORY BUILD: Calling endOfDirectory(handle={self.addon_handle}, succeeded=True)")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True)
            self.logger.info(f"DIRECTORY BUILD: Successfully completed directory with {ok} items")
            return True
        except Exception as e:
            self.logger.error(f"DIRECTORY BUILD: fatal error: {e}")
            self.logger.debug(f"DIRECTORY BUILD: Calling endOfDirectory(handle={self.addon_handle}, succeeded=False)")
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

            self.logger.debug(f"LIB ITEM: Creating library ListItem for '{title}' (type={media_type}, kodi_id={kodi_id})")

            # Label: include year if present
            display = f"{title} ({item['year']})" if item.get('year') else title
            self.logger.debug(f"LIB ITEM: Display label set to: '{display}'")
            li = xbmcgui.ListItem(label=display)

            # Set lightweight info for all versions (plot, rating, etc. are needed)
            info = self._build_lightweight_info(item)
            self.logger.debug(f"LIB ITEM: Video info dict for '{title}': {info}")
            li.setInfo('video', info)

            # Art (poster/fanart minimum)
            art = self._build_art_dict(item)
            if art:
                self.logger.debug(f"LIB ITEM: Art dict for '{title}': {art}")
                li.setArt(art)
            else:
                self.logger.debug(f"LIB ITEM: No art available for '{title}'")

            # Set library identity properties (v19 compatible)
            properties = {
                'dbtype': media_type,
                'dbid': str(kodi_id),
                'mediatype': media_type
            }
            self.logger.debug(f"LIB ITEM: Setting properties for '{title}': {properties}")
            for prop_name, prop_value in properties.items():
                li.setProperty(prop_name, prop_value)

            # Build a plugin URL so we can decide Play vs Info on click
            url = self._library_click_url(media_type, kodi_id, item.get('tvshowid'), item.get('season'))
            li.setPath(url)
            self.logger.info(f"LIB ITEM: Generated click URL for '{title}': {url}")

            # Get user preference safely (but don't let it break ListItem creation)
            # The original code had an incorrect import for get_select_pref.
            # It was defined in this file but intended to be imported from config_manager.
            # The fix involves changing the import path to the correct location.
            pref = get_select_pref()
            self.logger.debug(f"LIB ITEM: User preference for '{title}': {pref}")

            # CRITICAL: Always mark as playable so the ListItem can be clicked/activated
            # Without this, Kodi won't send click events to our plugin
            li.setProperty('IsPlayable', 'true')
            self.logger.info(f"LIB ITEM: Set IsPlayable=true for '{title}' - enables click handling")

            is_folder = False

            # Set InfoTagVideo properties only for v20+ (skip entirely on v19)
            if is_kodi_v20_plus():
                try:
                    video_info_tag = li.getVideoInfoTag()

                    # setMediaType() is v20+ only
                    try:
                        video_info_tag.setMediaType(media_type)
                        self.logger.debug(f"LIB ITEM: Set mediatype='{media_type}' for '{title}' (v20+)")
                    except Exception as e:
                        self.logger.warning(f"LIB ITEM: setMediaType() failed for '{title}': {e}")

                    # setDbId() for library linking on v20+
                    video_info_tag.setDbId(int(kodi_id), media_type)
                    self.logger.debug(f"LIB ITEM: Set dbid={kodi_id} for '{title}' - library linking enabled (v20+)")

                except Exception as e:
                    self.logger.warning(f"LIB ITEM: InfoTagVideo setup failed for '{title}': {e}")
            else:
                self.logger.debug(f"LIB ITEM: Skipping InfoTagVideo setters for '{title}' on v19")

            # Resume (always for library movies/episodes)
            self._set_resume_info_versioned(li, item)

            self.logger.info(f"LIB ITEM: Successfully created library ListItem '{title}' -> URL: {url}, isFolder: {is_folder}")
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

            self.logger.debug(f"EXT ITEM: Creating external ListItem for '{title}' (type={media_type})")

            display = f"{title} ({item['year']})" if item.get('year') else title
            self.logger.debug(f"EXT ITEM: Display label set to: '{display}'")
            li = xbmcgui.ListItem(label=display)

            # Apply exact same lightweight info profile as library items (Step 4)
            info = self._build_lightweight_info(item)
            self.logger.debug(f"EXT ITEM: Video info dict for '{title}': {info}")
            li.setInfo('video', info)

            # Apply exact same art keys as library items (Step 4)
            art = self._build_art_dict(item)
            if art:
                self.logger.debug(f"EXT ITEM: Art dict for '{title}': {art}")
                li.setArt(art)
            else:
                self.logger.debug(f"EXT ITEM: No art available for '{title}'")

            # Plugin URL for external/plugin-only items (no kodi_id)
            url = self._build_playback_url(item)
            self.logger.debug(f"EXT ITEM: Built playback URL for '{title}': {url}")
            li.setPath(url)

            # Keep folder/playable flags correct - IsPlayable="true" only for playable rows
            is_playable = bool(item.get('play'))
            is_folder = not is_playable
            self.logger.debug(f"EXT ITEM: Playable flags for '{title}': is_playable={is_playable}, is_folder={is_folder}, play_value={item.get('play')}")

            if is_playable:
                li.setProperty('IsPlayable', 'true')
                self.logger.debug(f"EXT ITEM: Set IsPlayable=true for '{title}'")
            # Do NOT set IsPlayable='false' for folders/non-playable

            # Resume for plugin-only: only if you maintain your own resume store
            # (Skip resume for external items - at your discretion)
            # The "always show resume" rule applies to library items only

            # External context menu
            self._set_external_context_menu(li, item)
            self.logger.debug(f"EXT ITEM: Added external context menu for '{title}'")

            self.logger.info(f"EXT ITEM: Successfully created external ListItem '{title}' -> URL: {url}, type={media_type}, playable={is_playable}, folder={is_folder}")
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
        title = item.get('title', 'Unknown')

        self.logger.debug(f"INFO BUILD: Building lightweight info for '{title}'")

        # Common
        if item.get('title'):
            info['title'] = item['title']
            self.logger.debug(f"INFO BUILD: Set title='{info['title']}'")
        if item.get('originaltitle') and item['originaltitle'] != item.get('title'):
            info['originaltitle'] = item['originaltitle']
            self.logger.debug(f"INFO BUILD: Set originaltitle='{info['originaltitle']}'")
        if item.get('sorttitle'):
            info['sorttitle'] = item['sorttitle']
            self.logger.debug(f"INFO BUILD: Set sorttitle='{info['sorttitle']}'")
        if item.get('year') is not None:
            info['year'] = int(item['year'])
            self.logger.debug(f"INFO BUILD: Set year={info['year']}")
        if item.get('genre'):
            info['genre'] = item['genre']
            self.logger.debug(f"INFO BUILD: Set genre='{info['genre']}'")
        if item.get('plot'):
            info['plot'] = item['plot']
            plot_preview = info['plot'][:100] + "..." if len(info['plot']) > 100 else info['plot']
            self.logger.debug(f"INFO BUILD: Set plot (length={len(info['plot'])}): '{plot_preview}'")
        if item.get('rating') is not None:
            info['rating'] = float(item['rating'])
            self.logger.debug(f"INFO BUILD: Set rating={info['rating']}")
        if item.get('votes') is not None:
            info['votes'] = int(item['votes'])
            self.logger.debug(f"INFO BUILD: Set votes={info['votes']}")
        if item.get('mpaa'):
            info['mpaa'] = item['mpaa']
            self.logger.debug(f"INFO BUILD: Set mpaa='{info['mpaa']}'")

        # Duration handling - prioritize runtime (minutes), fallback to duration
        runtime_minutes = item.get('runtime', 0)
        duration_seconds = item.get('duration', 0)

        if runtime_minutes and isinstance(runtime_minutes, (int, float)) and runtime_minutes > 0:
            # Runtime is in minutes, convert to seconds
            info['duration'] = int(runtime_minutes * 60)
        elif duration_seconds and isinstance(duration_seconds, (int, float)) and duration_seconds > 0:
            # Duration might be in seconds already, but check if it's suspiciously small (likely minutes)
            if duration_seconds < 3600:  # Less than 1 hour, probably minutes
                info['duration'] = int(duration_seconds * 60)
            else:
                info['duration'] = int(duration_seconds)

        # Keep duration_minutes for backward compatibility
        if runtime_minutes:
            info['duration_minutes'] = int(runtime_minutes)

        if item.get('studio'):
            info['studio'] = item['studio']
            self.logger.debug(f"INFO BUILD: Set studio='{info['studio']}'")
        if item.get('country'):
            info['country'] = item['country']
            self.logger.debug(f"INFO BUILD: Set country='{info['country']}'")
        if item.get('premiered'):
            info['premiered'] = item['premiered']
            self.logger.debug(f"INFO BUILD: Set premiered='{info['premiered']}'")

        # Episode extras
        if item.get('media_type') == 'episode':
            self.logger.debug(f"INFO BUILD: Processing episode-specific fields for '{title}'")
            if item.get('tvshowtitle'):
                info['tvshowtitle'] = item['tvshowtitle']
                self.logger.debug(f"INFO BUILD: Set tvshowtitle='{info['tvshowtitle']}'")
            if item.get('season') is not None:
                info['season'] = int(item['season'])
                self.logger.debug(f"INFO BUILD: Set season={info['season']}")
            if item.get('episode') is not None:
                info['episode'] = int(item['episode'])
                self.logger.debug(f"INFO BUILD: Set episode={info['episode']}")
            if item.get('aired'):
                info['aired'] = item['aired']
                self.logger.debug(f"INFO BUILD: Set aired='{info['aired']}'")
            if item.get('playcount') is not None:
                info['playcount'] = int(item['playcount'])
                self.logger.debug(f"INFO BUILD: Set playcount={info['playcount']}")
            if item.get('lastplayed'):
                info['lastplayed'] = item['lastplayed']
                self.logger.debug(f"INFO BUILD: Set lastplayed='{info['lastplayed']}'")

        info['mediatype'] = item.get('media_type', 'movie')
        self.logger.debug(f"INFO BUILD: Set mediatype='{info['mediatype']}'")

        self.logger.debug(f"INFO BUILD: Completed info dict for '{title}' with {len(info)} fields: {list(info.keys())}")
        return info

    def _build_art_dict(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Build artwork dictionary from item data"""
        art = {}
        title = item.get('title', 'Unknown')

        self.logger.debug(f"ART BUILD: Building art dict for '{title}'")
        self.logger.debug(f"ART BUILD: Available art sources - item.art: {type(item.get('art'))}, item.poster: {bool(item.get('poster'))}, item.fanart: {bool(item.get('fanart'))}")

        # First check if we have a JSON-RPC art dict
        item_art = item.get('art')
        if item_art:
            self.logger.debug(f"ART BUILD: Found art data of type {type(item_art)} for '{title}'")
            # Handle both dict and JSON string formats
            if isinstance(item_art, str):
                try:
                    import json
                    item_art = json.loads(item_art)
                    self.logger.debug(f"ART BUILD: Parsed JSON art string for '{title}': {list(item_art.keys()) if isinstance(item_art, dict) else 'not a dict'}")
                except (json.JSONDecodeError, ValueError):
                    self.logger.warning(f"ART BUILD: Failed to parse art JSON for '{title}': {item_art[:100]}")
                    item_art = {}

            if isinstance(item_art, dict):
                # Copy all art keys from JSON-RPC art dict
                for art_key in ['poster', 'fanart', 'thumb', 'banner', 'landscape',
                               'clearlogo', 'clearart', 'discart', 'icon']:
                    if art_key in item_art and item_art[art_key]:
                        art[art_key] = item_art[art_key]
                        self.logger.debug(f"ART BUILD: Added {art_key} for '{title}': {item_art[art_key][:50]}...")

        # Also check top-level fields (enrichment may have flattened them)
        for art_key in ['poster', 'fanart', 'thumb', 'banner', 'landscape', 'clearlogo']:
            if item.get(art_key) and not art.get(art_key):
                art[art_key] = item[art_key]
                self.logger.debug(f"ART BUILD: Added top-level {art_key} for '{title}': {item[art_key][:50]}...")

        # If we have poster but no thumb/icon, set them for list view compatibility
        if art.get('poster') and not art.get('thumb'):
            art['thumb'] = art['poster']
            self.logger.debug(f"ART BUILD: Set thumb=poster for '{title}'")
        if art.get('poster') and not art.get('icon'):
            art['icon'] = art['poster']
            self.logger.debug(f"ART BUILD: Set icon=poster for '{title}'")

        self.logger.debug(f"ART BUILD: Final art dict for '{title}': {list(art.keys())}")
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
    def _library_click_url(self, media_type: str, kodi_id: int, tvshowid=None, season=None) -> str:
        """
        Build plugin URL for library item selection handling with proper query parameters.

        Args:
            media_type: 'movie' or 'episode'
            kodi_id: Kodi database ID for the item
            tvshowid: TV show ID (for episodes)
            season: Season number (for episodes)

        Returns:
            str: Plugin URL with on_select action and database parameters
        """
        import urllib.parse

        # Build clean query parameters
        params = {
            "action": "on_select",
            "dbtype": media_type,
            "dbid": str(kodi_id)
        }

        # Add episode-specific parameters if provided
        if tvshowid is not None:
            params["tvshowid"] = str(tvshowid)
        if season is not None:
            params["season"] = str(season)

        # Use urllib.parse.urlencode for proper encoding
        query = urllib.parse.urlencode(params)
        url = f"plugin://{self.addon_id}/?{query}"

        self.logger.debug(f"CLICK URL: Built URL for {media_type} {kodi_id}: {url}")
        return url

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

    def open_library_info_dialog(self, media_type: str, kodi_id: int, return_path: Optional[str] = None) -> bool:
        """
        Open info dialog for a library item with version-aware handling
        
        Args:
            media_type: 'movie' or 'episode'
            kodi_id: Kodi database ID for the item
            return_path: Optional path to return to when info is closed
            
        Returns:
            bool: True if info dialog was successfully opened
        """
        try:
            kodi_major = self._get_kodi_major_version()
            self.logger.info(f"Opening info dialog for {media_type} {kodi_id} on Kodi v{kodi_major}")
            
            if media_type == 'movie':
                if kodi_major <= 19:
                    # Use Matrix XSP navigation method
                    return open_movie_info_v19(kodi_id, return_path)
                else:
                    # Use Nexus+ direct method
                    return self._open_info_nexus_plus(media_type, kodi_id)
            elif media_type == 'episode':
                # For episodes, use direct videodb approach on all versions
                return self._open_info_videodb(media_type, kodi_id)
            else:
                self.logger.error(f"Unsupported media type for info dialog: {media_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to open info dialog for {media_type} {kodi_id}: {e}")
            return False
    
    def _get_kodi_major_version(self) -> int:
        """Get Kodi major version number"""
        try:
            build_version = xbmc.getInfoLabel("System.BuildVersion")
            major = int(build_version.split('.')[0].split('-')[0])
            return major
        except Exception:
            return 19  # Safe fallback to Matrix behavior
    
    def _open_info_nexus_plus(self, media_type: str, kodi_id: int) -> bool:
        """Open info dialog using Nexus+ Action(Info) method"""
        try:
            # This assumes the item is already focused/selected in a list
            xbmc.executebuiltin('Action(Info)')
            self.logger.info(f"Opened info dialog for {media_type} {kodi_id} using Action(Info)")
            return True
        except Exception as e:
            self.logger.error(f"Failed to open info using Action(Info): {e}")
            return False
    
    def _open_info_videodb(self, media_type: str, kodi_id: int) -> bool:
        """Open info dialog using videodb:// path method"""
        try:
            if media_type == "movie":
                videodb_path = f'videodb://movies/titles/{kodi_id}'
            elif media_type == "episode":
                videodb_path = f'videodb://episodes/{kodi_id}'
            else:
                self.logger.error(f"Unsupported media type for videodb method: {media_type}")
                return False
            
            xbmc.executebuiltin(f'ActivateWindow(DialogVideoInfo,"{videodb_path}",return)')
            self.logger.info(f"Opened info dialog for {media_type} {kodi_id} using videodb path")
            return True
        except Exception as e:
            self.logger.error(f"Failed to open info using videodb path: {e}")
            return False