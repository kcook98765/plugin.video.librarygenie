#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Builder
Builds ListItems with proper metadata and resume information
"""

import json
from typing import List, Dict, Any, Optional, Tuple
import xbmcgui
import xbmcplugin
from ..utils.kodi_log import get_kodi_logger
from ..utils.kodi_version import get_kodi_major_version, is_kodi_v20_plus, is_kodi_v21_plus


class ListItemBuilder:
    """Builds ListItems with proper separation between Kodi library and external items"""

    # -------- lifecycle --------
    def __init__(self, addon_handle: int, addon_id: str, context):
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.context = context
        self.logger = get_kodi_logger('lib.ui.listitem_builder')

    # -------- public API --------
    def build_directory(self, items: List[Dict[str, Any]], content_type: Optional[str] = None) -> bool:
        """
        Build a directory with proper content type and ListItems.

        Args:
            items: list of (possibly mixed) media item dicts
            content_type: "movies", "episodes", or "videos" - if None, auto-detect from items

        Returns:
            bool: success
        """
        try:
            count = len(items)
            
            # Auto-detect content type if not provided
            if content_type is None:
                from lib.data.query_manager import get_query_manager
                query_manager = get_query_manager()
                content_type = query_manager.detect_content_type(items)
                self.logger.debug("DIRECTORY BUILD: Auto-detected content type: %s", content_type)
            
            self.logger.info("DIRECTORY BUILD: Starting build with %s items (content_type='%s')", count, content_type)
            self.logger.debug("DIRECTORY BUILD: Setting content type to '%s' for handle %s", content_type, self.addon_handle)
            xbmcplugin.setContent(self.addon_handle, content_type)

            # Add a few sane sort methods once
            sort_methods = [
                ("SORT_METHOD_TITLE_IGNORE_THE", xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE),
                ("SORT_METHOD_DATE", xbmcplugin.SORT_METHOD_DATE),
                ("SORT_METHOD_VIDEO_YEAR", xbmcplugin.SORT_METHOD_VIDEO_YEAR),
            ]
            self.logger.debug("DIRECTORY BUILD: Adding %s sort methods", len(sort_methods))
            for method_name, const in sort_methods:
                xbmcplugin.addSortMethod(self.addon_handle, const)
                self.logger.debug("DIRECTORY BUILD: Added sort method %s", method_name)

            tuples: List[tuple] = []
            ok = 0
            fail = 0
            for idx, raw in enumerate(items, start=1):
                try:
                    item = self._normalize_item(raw)  # canonical shape
                    built = self._build_single_item(item)
                    if built:
                        url, listitem, is_folder = built

                        tuples.append((url, listitem, is_folder, item))  # Include item data for context menu
                        ok += 1
                    else:
                        fail += 1
                        self.logger.warning("DIRECTORY BUILD: failed to build #%s: '%s'", idx, raw.get('title','Unknown'))
                except Exception as ie:
                    fail += 1
                    self.logger.error("DIRECTORY BUILD: exception for #%s: %s", idx, ie)

            self.logger.info("DIRECTORY BUILD: Processed %s items - %s OK, %s failed", count, ok, fail)

            self.logger.debug("DIRECTORY BUILD: Adding %s directory items to Kodi", len(tuples))
            for idx, (url, li, is_folder, item) in enumerate(tuples, start=1):

                # Set properties for global context menu detection
                media_item_id = item.get('media_item_id') or item.get('id')
                if media_item_id:
                    li.setProperty('media_item_id', str(media_item_id))

                # Set list context if available
                list_id = item.get('list_id') or self.context.get_param('list_id')
                if list_id:
                    li.setProperty('list_id', str(list_id))

                # Add to directory immediately after context menu is applied
                xbmcplugin.addDirectoryItem(
                    handle=self.addon_handle, url=url, listitem=li, isFolder=is_folder
                )

            self.logger.debug("DIRECTORY BUILD: Calling endOfDirectory(handle=%s, succeeded=True)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True)
            self.logger.info("DIRECTORY BUILD: ✅ Successfully built directory with %s items (%s failed)", ok, fail)
            return True
        except Exception as e:
            self.logger.error("DIRECTORY BUILD: fatal error: %s", e)
            self.logger.debug("DIRECTORY BUILD: Calling endOfDirectory(handle=%s, succeeded=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
            return False

    # -------- internals --------
    def _build_single_item(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Decide whether to build a library-backed, external, or action item.
        Returns (url, listitem, is_folder) or None on failure.
        """
        title = item.get('title', 'Unknown')
        media_type = item.get('media_type', 'movie')
        kodi_id = item.get('kodi_id')  # already normalized to int/None

        # Check if this is an action item (non-media)
        is_action_item = (
            media_type == 'none' or
            item.get('action') in ('scan_favorites', 'scan_favorites_execute', 'noop', 'create_list', 'create_list_execute', 'create_folder', 'create_folder_execute') or
            title.startswith('[COLOR yellow]Sync') or
            title.startswith('[COLOR yellow]+ Create') or
            title.startswith('[COLOR cyan]+ Create') or
            'Sync Favorites' in title or
            'Create New' in title or
            item.get('is_navigation', False)  # Pagination navigation items
        )


        try:
            if is_action_item:
                return self._create_action_item(item)
            elif media_type in ('movie', 'episode') and self._is_valid_library_id(kodi_id):
                return self._create_library_listitem(item)
            else:
                return self._create_external_item(item)
        except Exception as e:
            self.logger.error("ITEM BUILD: failed for '%s': %s", title, e)
            return None

    def _is_valid_library_id(self, kodi_id) -> bool:
        """Check if kodi_id is valid for library items (int or numeric string)"""
        if kodi_id is None:
            return False
        if isinstance(kodi_id, int):
            return True
        if isinstance(kodi_id, str) and kodi_id.strip().isdigit():
            return True
        return False

    # ----- normalization -----
    def _normalize_item(self, src: Dict[str, Any]) -> Dict[str, Any]:
        """
        Canonicalize a raw item dict to the lightweight, version-safe shape
        consumed by this builder.
        """
        out: Dict[str, Any] = {}

        # media type - be more specific for library items
        media_type = (src.get('media_type') or src.get('type') or 'movie').lower()
        

        # FIXED: Trust database media_type first, then use inference rules
        # Preserve 'none' media type for action items - don't force to 'movie'
        if media_type == 'none':
            out['media_type'] = 'none'
        # Trust database media_type if it's reliable (episode/movie)
        elif media_type in ('episode', 'movie'):
            out['media_type'] = media_type
        # Episode detection: check for episode-specific fields or episodeid
        elif (src.get('episodeid') or src.get('episode') is not None or 
              (src.get('tvshowtitle') and src.get('season') is not None)):
            media_type = 'episode'
            out['media_type'] = media_type
        # Movie detection: movieid or kodi_id without episode indicators
        elif (src.get('movieid') or 
              (src.get('kodi_id') and not any([src.get('tvshowtitle'), src.get('season'), src.get('episode')]))):
            media_type = 'movie'
            out['media_type'] = media_type
        elif media_type not in ('tvshow', 'none'):
            # Default fallback for unknown types (but preserve 'tvshow')
            media_type = 'movie'
            out['media_type'] = media_type
        else:
            out['media_type'] = media_type

        # kodi id (only for movie/episode)
        kodi_id = None
        if media_type == 'movie':
            kodi_id = src.get('kodi_id') or src.get('movieid')
        elif media_type == 'episode':
            kodi_id = src.get('kodi_id') or src.get('episodeid')
        # Do NOT infer from generic 'id' to avoid misclassification
        # Keep original logic but fix the flawed condition
        if kodi_id is not None:
            if isinstance(kodi_id, (int, float)):
                out['kodi_id'] = int(kodi_id)
            elif isinstance(kodi_id, str) and kodi_id.strip().isdigit():
                # Fix: Convert numeric strings to integers 
                out['kodi_id'] = int(kodi_id.strip())
            else:
                out['kodi_id'] = kodi_id  # Keep original value
        else:
            out['kodi_id'] = None

        # identity / titles
        out['title'] = src.get('title') or src.get('label') or 'Unknown'
        if src.get('originaltitle') and src.get('originaltitle') != out['title']:
            out['originaltitle'] = src.get('originaltitle')
        if src.get('sorttitle'):
            out['sorttitle'] = src.get('sorttitle')

        # year
        try:
            year_value = src.get('year')
            out['year'] = int(year_value) if year_value is not None else None
        except (ValueError, TypeError):
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
            rating_value = src.get('rating')
            if rating_value is not None:
                out['rating'] = float(rating_value)
        except (ValueError, TypeError):
            pass
        try:
            votes_value = src.get('votes')
            if votes_value is not None:
                out['votes'] = int(votes_value)
        except (ValueError, TypeError):
            pass
        if src.get('mpaa'):
            out['mpaa'] = src['mpaa']

        # duration -> minutes (Matrix-safe)
        minutes = None
        if src.get('duration_minutes') is not None:
            # caller already provided minutes
            try:
                duration_minutes_value = src.get('duration_minutes')
                minutes = int(duration_minutes_value) if duration_minutes_value is not None else None
            except (ValueError, TypeError):
                minutes = None
        elif src.get('runtime') is not None:
            # runtime commonly minutes
            try:
                runtime_value = src.get('runtime')
                minutes = int(runtime_value) if runtime_value is not None else None
            except (ValueError, TypeError):
                minutes = None
        elif src.get('duration') is not None:
            # 'duration' may be minutes or seconds; best effort:
            try:
                duration_value = src.get('duration')
                d = int(duration_value) if duration_value is not None else 0
                minutes = d // 60 if d > 300 else d
            except (ValueError, TypeError):
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
                        key_value = src.get(key)
                        out[key] = int(key_value) if key_value is not None else None
                    except (ValueError, TypeError):
                        pass
            if src.get('aired'):
                out['aired'] = src['aired']
            if src.get('playcount') is not None:
                try:
                    playcount_value = src.get('playcount')
                    out['playcount'] = int(playcount_value) if playcount_value is not None else None
                except (ValueError, TypeError):
                    pass
            if src.get('lastplayed'):
                out['lastplayed'] = src['lastplayed']
            # Helpful if present for videodb path construction
            if src.get('tvshowid') is not None:
                try:
                    tvshowid_value = src.get('tvshowid')
                    out['tvshowid'] = int(tvshowid_value) if tvshowid_value is not None else None
                except (ValueError, TypeError):
                    pass

        # artwork - only from art JSON field now
        art_blob = src.get('art')
        if art_blob:
            try:
                art_dict = json.loads(art_blob) if isinstance(art_blob, str) else art_blob
                if isinstance(art_dict, dict):
                    # Preserve the full art dictionary for _build_art_dict
                    out['art'] = art_blob  # Keep original JSON string or dict
                    # Also extract individual keys for backward compatibility
                    for k in ('thumb', 'banner', 'landscape', 'clearlogo'):
                        v = art_dict.get(k)
                        if v:
                            out[k] = v
                else:
                    # Even if parsing failed, preserve the original art data
                    out['art'] = art_blob
            except Exception:
                # non-fatal, but still preserve original art data
                out['art'] = art_blob

        # resume (seconds)
        resume = src.get('resume') or {}
        pos_value = resume.get('position_seconds') or resume.get('position') or 0
        tot_value = resume.get('total_seconds') or resume.get('total') or 0
        try:
            pos = int(pos_value) if pos_value is not None else 0
        except (ValueError, TypeError):
            pos = 0
        try:
            tot = int(tot_value) if tot_value is not None else 0
        except (ValueError, TypeError):
            tot = 0
        out['resume'] = {'position_seconds': pos, 'total_seconds': tot}

        # preserve source if provided, can be useful for logging/routes
        if src.get('source'):
            out['source'] = src['source']

        # preserve action for action items
        if src.get('action'):
            out['action'] = src['action']

        # preserve ids for context menu
        out['id'] = src.get('id')
        out['media_item_id'] = src.get('media_item_id')
        out['list_id'] = src.get('list_id')

        return out

    # ----- library & external builders -----
    def _create_library_listitem(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Build library-backed movie/episode row as (url, listitem, is_folder=False)
        with videodb:// path and proper library integration for native Kodi behavior.
        """
        try:
            title = item.get('title', 'Unknown')
            media_type = item.get('media_type', 'movie')
            kodi_id = item.get('kodi_id')

            # Label: format based on media type
            # Check for episode formatting - either explicit media_type='episode' or presence of episode fields
            tvshowtitle = item.get('tvshowtitle', '')
            season = item.get('season')
            episode = item.get('episode')
            is_episode = (media_type == 'episode' or 
                         (tvshowtitle and season is not None and episode is not None))
            
            if is_episode:
                # Format episode label: "Show Name - S01E01 - Episode Title"
                if tvshowtitle and season is not None and episode is not None:
                    display_label = f"{tvshowtitle} - S{int(season):02d}E{int(episode):02d} - {title}"
                elif tvshowtitle:
                    display_label = f"{tvshowtitle} - {title}"
                else:
                    display_label = title
            else:
                # Movies and other media types - include year if present
                display_label = f"{title} ({item['year']})" if item.get('year') else title

            li = xbmcgui.ListItem(label=display_label)

            # Build videodb:// URL for native library integration
            if kodi_id is None:
                self.logger.error("LIB ITEM: Cannot build videodb URL - kodi_id is None for '%s'", title)
                return None
            videodb_url = self._build_videodb_url(media_type, kodi_id, item.get('tvshowid'), item.get('season'))
            li.setPath(videodb_url)

            # Do NOT set IsPlayable for videodb:// items - Kodi handles this natively
            # Setting IsPlayable can interfere with native library handling and skins

            is_folder = False

            # ✨ ALWAYS set InfoHijack properties on library items first (before any metadata operations)
            try:
                li.setProperty("LG.InfoHijack.Armed", "1")
                li.setProperty("LG.InfoHijack.DBID", str(kodi_id) if kodi_id is not None else "0")
                li.setProperty("LG.InfoHijack.DBType", media_type)
                self.logger.debug("🎯 HIJACK ARMED: '%s' - DBID=%s, DBType=%s", title, kodi_id, media_type)
            except Exception as e:
                self.logger.error("LIB ITEM: ❌ Failed to set InfoHijack properties for '%s': %s", title, e)

            # Handle metadata setting based on Kodi version
            kodi_major = get_kodi_major_version()

            if kodi_major >= 20:
                # v20+: Use InfoTagVideo setters and avoid setInfo() for library items
                try:
                    video_info_tag = li.getVideoInfoTag()

                    # setDbId() for library linking - use feature detection instead of version detection
                    dbid_success = False
                    if kodi_id is not None:
                        try:
                            # Try v21+ signature first (2 args)
                            video_info_tag.setDbId(int(kodi_id), media_type)
                            dbid_success = True
                        except TypeError:
                            # Fallback to v19/v20 signature (1 arg)
                            try:
                                video_info_tag.setDbId(int(kodi_id))
                                dbid_success = True
                            except Exception as e:
                                self.logger.warning("LIB ITEM: setDbId() 1-arg fallback failed for '%s': %s", title, e)
                        except Exception as e:
                            self.logger.warning("LIB ITEM: setDbId() 2-arg failed for '%s': %s", title, e)
                    else:
                        self.logger.warning("LIB ITEM: Cannot set setDbId - kodi_id is None for '%s'", title)

                    # Report dbid failure for diagnostics
                    if not dbid_success:
                        self.logger.warning("LIB ITEM: DB linking failed for '%s' - falling back to property method", title)

                    # Set metadata via InfoTagVideo setters (v20+) - but keep it lightweight
                    self._set_infotag_metadata(video_info_tag, item, title)

                except Exception as e:
                    self.logger.error("LIB ITEM: InfoTagVideo setup failed for '%s': %s", title, e)
            else:
                # v19: Use classic setInfo() approach
                info = self._build_lightweight_info(item)
                li.setInfo('video', info)

            # Art from art field
            art = self._build_art_dict(item)
            if art:
                self.logger.debug("V19 ART APPLY: About to apply art dict for '%s'", title)
                self.logger.debug("V19 ART APPLY: Art keys: %s", list(art.keys()))
                for art_key, art_url in art.items():
                    if art_url:
                        self.logger.debug("V19 ART APPLY:   %s = %s", art_key, art_url[:100] + "..." if len(art_url) > 100 else art_url)
                try:
                    li.setArt(art)
                    self.logger.debug("V19 ART APPLY: Successfully called li.setArt() for '%s'", title)
                    
                    # V19 DEBUG: Test if the actual image URLs are reachable
                    kodi_major = get_kodi_major_version()
                    if kodi_major == 19:
                        import xbmcvfs
                        for art_key, art_url in art.items():
                            if art_url.startswith('image://') and 'http' in art_url:
                                # Try to access the image through Kodi's VFS to see if it loads
                                try:
                                    test_file = xbmcvfs.File(art_url, 'r')
                                    if test_file.size() > 0:
                                        self.logger.debug("V19 URL TEST: %s URL is accessible (size: %d bytes)", art_key, test_file.size())
                                    else:
                                        self.logger.warning("V19 URL TEST: %s URL returned 0 bytes: %s", art_key, art_url)
                                    test_file.close()
                                except Exception as url_e:
                                    self.logger.warning("V19 URL TEST: %s URL not accessible: %s - Error: %s", art_key, art_url, url_e)
                    
                except Exception as e:
                    self.logger.error("V19 ART APPLY: setArt() failed for '%s': %s", title, e)
            else:
                self.logger.debug("V19 ART APPLY: No art dictionary for '%s'", title)

            # Always set property fallbacks for maximum compatibility
            # These help when setDbId fails or on older versions
            try:
                li.setProperty('dbtype', media_type)
                li.setProperty('dbid', str(kodi_id) if kodi_id is not None else "0")
                li.setProperty('mediatype', media_type)
            except Exception as e:
                self.logger.warning("LIB ITEM: Property fallback setup failed for '%s': %s", title, e)

            # Resume (always for library movies/episodes)
            self._set_resume_info_versioned(li, item)

            return videodb_url, li, is_folder
        except Exception as e:
            self.logger.error("LIB ITEM: failed for '%s': %s", item.get('title','Unknown'), e)
            return None

    def _create_action_item(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Build action item (like Sync Favorites) as a navigable folder that triggers actions.
        Returns (url, listitem, is_folder) or None on failure.
        """
        try:
            title = item.get('title', 'Unknown')
            description = item.get('description', '')
            action = item.get('action', '')

            # Create folder ListItem that Kodi will treat as a navigable directory
            li = xbmcgui.ListItem(label=title)

            # Ensure it's treated as a folder, not a playable item
            li.setProperty('IsPlayable', 'false')

            # Set folder-appropriate metadata without video assumptions
            kodi_major = get_kodi_major_version()
            if kodi_major >= 20:
                # v20+: Minimal metadata to avoid video treatment
                try:
                    video_info_tag = li.getVideoInfoTag()
                    video_info_tag.setTitle(title)
                    if description:
                        video_info_tag.setPlot(description)
                except Exception as e:
                    self.logger.debug("ACTION ITEM v20+: InfoTagVideo failed for folder '%s': %s", title, e)
                    # On v21+, completely avoid setInfo() to prevent deprecation warnings
                    # Only use setInfo() on v19/v20 where InfoTagVideo may not be fully reliable
                    if kodi_major < 21:
                        info_dict = {'title': title}
                        if description:
                            info_dict['plot'] = description
                        li.setInfo('video', info_dict)
            else:
                # v19: Use setInfo()
                info_dict = {'title': title}
                if description:
                    info_dict['plot'] = description
                li.setInfo('video', info_dict)

            # Use appropriate icons for different action types
            if 'Sync' in title or action == 'scan_favorites_execute':
                icon = 'DefaultAddonService.png'  # Service icon for sync operations
            elif item.get('is_navigation', False):
                # Use direction-specific icons for pagination
                navigation_type = item.get('navigation_type', '')
                if navigation_type == 'previous':
                    icon = 'DefaultArrowLeft.png'
                elif navigation_type == 'next': 
                    icon = 'DefaultArrowRight.png'
                else:
                    icon = item.get('icon', 'DefaultFolder.png')  # Use custom icon if provided
            else:
                icon = 'DefaultFolder.png'  # Standard folder icon for other actions

            li.setArt({'icon': icon, 'thumb': icon})

            # Build plugin URL that will trigger the action when folder is navigated to
            # Prefer pre-built URL (e.g., for pagination navigation) over action-based URL
            if item.get('url'):
                # Use pre-built URL (for pagination navigation)
                url = item.get('url')
            elif action:
                url = f"plugin://{self.addon_id}/?action={action}"
            else:
                # Fallback for actions without specific action
                url = f"plugin://{self.addon_id}/?action=noop"

            # Mark as folder so Kodi treats it as navigable directory
            is_folder = True

            return url, li, is_folder

        except Exception as e:
            self.logger.error("ACTION ITEM: failed for '%s': %s", item.get('title','Unknown'), e)
            return None

    def _create_external_item(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Build plugin/external row as (url, listitem, is_folder)
        Using lightweight info; no heavy fields (cast/streamdetails) in list view.
        When there's no kodi_id, use plugin:// URL with same lightweight profile as library items.
        """
        try:
            title = item.get('title', 'Unknown')

            display_label = f"{title} ({item['year']})" if item.get('year') else title
            li = xbmcgui.ListItem(label=display_label)

            # Apply metadata based on Kodi version - use InfoTagVideo on v20+
            kodi_major = get_kodi_major_version()
            if kodi_major >= 20:
                # v20+: Use InfoTagVideo setters to avoid deprecation warnings
                try:
                    video_info_tag = li.getVideoInfoTag()
                    self._set_infotag_metadata(video_info_tag, item, title)
                except Exception as e:
                    self.logger.warning("EXT ITEM v20+: InfoTagVideo setup failed for '%s': %s", title, e)
                    # On v21+, completely avoid setInfo() to prevent deprecation warnings
                    # Only use setInfo() on v19/v20 where InfoTagVideo may not be fully reliable
                    if kodi_major < 21:
                        info = self._build_lightweight_info(item)
                        li.setInfo('video', info)
            else:
                # v19: Use setInfo()
                info = self._build_lightweight_info(item)
                li.setInfo('video', info)

            # Apply art from art field same as library items
            art = self._build_art_dict(item)
            if art:
                li.setArt(art)

            # Plugin URL for external/plugin-only items (no kodi_id)
            url = self._build_playback_url(item)
            li.setPath(url)

            # Keep folder/playable flags correct - IsPlayable="true" only for playable rows
            is_playable = bool(item.get('play'))
            is_folder = not is_playable

            # Ensure list items that are meant to display list contents are marked as folders.
            # This prevents Kodi from trying to show video info for them.
            action = item.get("action", "")
            if action == "show_list":
                is_folder = True  # Lists should be navigable folders
            elif is_playable:
                is_folder = False # Playable items are not folders
            else:
                # Default to not a folder unless it's explicitly a "show_list" action
                is_folder = False

            # For playable items, set additional properties
            if is_playable:
                li.setProperty('IsPlayable', 'true')
            else:
                li.setProperty('IsPlayable', 'false') # Explicitly mark non-playable items

            # Resume for plugin-only: only if you maintain your own resume store
            # (Skip resume for external items - at your discretion)
            # The "always show resume" rule applies to library items only

            # External context menu
            self._set_external_context_menu(li, item)

            return url, li, is_folder
        except Exception as e:
            self.logger.error("EXT ITEM: failed for '%s': %s", item.get('title','Unknown'), e)
            return None

    # ----- info/art/resume helpers -----
    def _build_lightweight_info(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build lightweight info dictionary for list items with native library metadata.
        Includes fields that Kodi expects for proper library integration but avoids heavy arrays.

        IMPORTANT: This method intentionally avoids heavy fields like:
        - cast/crew arrays (Kodi will populate these automatically via dbid)
        - deep streamdetails
        - complex metadata that would slow down list scrolling
        This keeps list views snappy while providing native library behavior.
        """
        info: Dict[str, Any] = {}

        # Core identification fields
        if item.get('title'):
            info['title'] = item['title']
        if item.get('originaltitle') and item['originaltitle'] != item.get('title'):
            info['originaltitle'] = item['originaltitle']
        if item.get('sorttitle'):
            info['sorttitle'] = item['sorttitle']

        # Year and date fields
        if item.get('year') is not None:
            try:
                year_value = item.get('year')
                info['year'] = int(year_value) if year_value is not None else None
            except (ValueError, TypeError):
                pass
        if item.get('premiered'):
            info['premiered'] = item['premiered']

        # Content description - use full plot text for complete information
        plot_text = item.get('plot', '')
        if plot_text:
            info['plot'] = plot_text
        if item.get('plotoutline'):
            info['plotoutline'] = item['plotoutline']

        # Ratings and content classification
        if item.get('rating') is not None:
            try:
                rating_value = item.get('rating')
                info['rating'] = float(rating_value) if rating_value is not None else None
            except (ValueError, TypeError):
                pass
        if item.get('votes') is not None:
            try:
                votes_value = item.get('votes')
                info['votes'] = int(votes_value) if votes_value is not None else None
            except (ValueError, TypeError):
                pass
        if item.get('mpaa'):
            info['mpaa'] = item['mpaa']

        # Genre handling - data stored in version-appropriate format
        genre_data = item.get('genre', '')
        if genre_data:
            # Data is already in the correct format for this Kodi version
            info['genre'] = genre_data

        # Duration handling - Kodi expects duration in seconds for info dict
        runtime_minutes = item.get('runtime', 0)
        duration_seconds = item.get('duration', 0)
        duration_minutes = item.get('duration_minutes', 0)

        calculated_duration = None
        if runtime_minutes and isinstance(runtime_minutes, (int, float)) and runtime_minutes > 0:
            calculated_duration = int(runtime_minutes * 60)
        elif duration_minutes and isinstance(duration_minutes, (int, float)) and duration_minutes > 0:
            calculated_duration = int(duration_minutes * 60)
        elif duration_seconds and isinstance(duration_seconds, (int, float)) and duration_seconds > 0:
            if duration_seconds < 3600:  # Less than 1 hour, probably minutes
                calculated_duration = int(duration_seconds * 60)
            else:
                calculated_duration = int(duration_seconds)

        if calculated_duration:
            info['duration'] = calculated_duration

        # Production information (lightweight strings only)
        if item.get('director'):
            # Handle both string and list formats
            if isinstance(item['director'], list):
                info['director'] = ", ".join(item['director']) if item['director'] else ""
            else:
                info['director'] = str(item['director'])

        if item.get('studio'):
            # Handle both string and list formats
            if isinstance(item['studio'], list):
                info['studio'] = item['studio'][0] if item['studio'] else ""
            else:
                info['studio'] = str(item['studio'])

        if item.get('country'):
            # Handle both string and list formats
            if isinstance(item['country'], list):
                info['country'] = item['country'][0] if item['country'] else ""
            else:
                info['country'] = str(item['country'])

        # Playback tracking
        if item.get('playcount') is not None:
            try:
                playcount_value = item.get('playcount')
                info['playcount'] = int(playcount_value) if playcount_value is not None else None
            except (ValueError, TypeError):
                pass
        if item.get('lastplayed'):
            info['lastplayed'] = item['lastplayed']

        # Episode-specific fields
        if item.get('media_type') == 'episode':
            if item.get('tvshowtitle'):
                info['tvshowtitle'] = item['tvshowtitle']
            if item.get('season') is not None:
                try:
                    season_value = item.get('season')
                    info['season'] = int(season_value) if season_value is not None else None
                except (ValueError, TypeError):
                    pass
            if item.get('episode') is not None:
                try:
                    episode_value = item.get('episode')
                    info['episode'] = int(episode_value) if episode_value is not None else None
                except (ValueError, TypeError):
                    pass
            if item.get('aired'):
                info['aired'] = item['aired']

        # Media type for proper overlays and library recognition
        info['mediatype'] = item.get('media_type', 'movie')

        return info

    def _build_art_dict(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Build artwork dictionary from item data - uses only art field"""
        art = {}

        # Get art data from the art JSON field only
        item_art = item.get('art')
        if item_art:
            # Handle both dict and JSON string formats
            if isinstance(item_art, str):
                try:
                    item_art = json.loads(item_art)
                except (json.JSONDecodeError, ValueError):
                    item_art = {}

            if isinstance(item_art, dict):
                # Check Kodi version once for efficiency
                kodi_major = get_kodi_major_version()
                is_v19 = (kodi_major == 19)
                
                # Copy all art keys from the art dict
                for art_key in ['poster', 'fanart', 'thumb', 'banner', 'landscape',
                               'clearlogo', 'clearart', 'discart', 'icon']:
                    if art_key in item_art and item_art[art_key]:
                        art_value = item_art[art_key]
                        
                        # V19 fix: Decode URL-encoded image:// URLs
                        if is_v19 and art_value.startswith('image://'):
                            try:
                                import urllib.parse
                                original_url = art_value
                                # Extract the URL from image://URL/ format and decode it
                                if art_value.endswith('/'):
                                    inner_url = art_value[8:-1]  # Remove 'image://' and trailing '/'
                                else:
                                    inner_url = art_value[8:]    # Remove 'image://' (no trailing slash)
                                
                                decoded_url = urllib.parse.unquote(inner_url)
                                
                                # V19 EXPERIMENT: Try providing direct URLs instead of image:// wrapped
                                if decoded_url.startswith('http'):
                                    # Use direct URL for V19
                                    art_value = decoded_url
                                    self.logger.debug("V19 ART EXPERIMENT: Using direct URL for %s", art_key)
                                else:
                                    # Keep image:// wrapper for local/default images
                                    if art_value.endswith('/'):
                                        art_value = f"image://{decoded_url}/"
                                    else:
                                        art_value = f"image://{decoded_url}"
                                
                                self.logger.debug("V19 ART DEBUG: %s for %s", art_key, item.get('title', 'Unknown'))
                                self.logger.debug("V19 ART DEBUG:   BEFORE: %s", original_url)
                                self.logger.debug("V19 ART DEBUG:   AFTER:  %s", art_value)
                                self.logger.debug("V19 ART DEBUG:   INNER_URL: %s", inner_url)
                                self.logger.debug("V19 ART DEBUG:   DECODED: %s", decoded_url)
                                self.logger.debug("V19 ART DEBUG:   DIRECT_URL: %s", "YES" if decoded_url.startswith('http') else "NO")
                            except Exception as e:
                                self.logger.warning("V19 ART FIX: Failed to decode %s URL for %s: %s", art_key, item.get('title', 'Unknown'), e)
                                # Keep original value on decode failure
                        
                        art[art_key] = art_value

        # If we have poster but no thumb/icon, set them for list view compatibility
        if art.get('poster') and not art.get('thumb'):
            art['thumb'] = art['poster']
        if art.get('poster') and not art.get('icon'):
            art['icon'] = art['poster']

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
                    except Exception as e:
                        # Fallback to v19 properties
                        list_item.setProperty('ResumeTime', str(pos))
                        list_item.setProperty('TotalTime', str(tot))
                else:
                    list_item.setProperty('ResumeTime', str(pos))
                    list_item.setProperty('TotalTime', str(tot))
        except Exception as e:
            self.logger.error("RESUME: failed to set resume info: %s", e)

    # ----- misc helpers -----
    def _build_videodb_url(self, media_type: str, kodi_id: int, tvshowid=None, season=None) -> str:
        """
        Build videodb:// URL for native Kodi library integration.

        Args:
            media_type: 'movie' or 'episode'
            kodi_id: Kodi database ID for the item
            tvshowid: TV show ID (for episodes)
            season: Season number (for episodes)

        Returns:
            str: videodb:// URL for native library handling
        """
        if media_type == "movie":
            url = f"videodb://movies/titles/{kodi_id}"
            return url
        elif media_type == "episode":
            if tvshowid is not None and season is not None:
                url = f"videodb://tvshows/titles/{tvshowid}/{season}/{kodi_id}"
                return url
            else:
                # Fallback for episodes without show/season info
                url = f"videodb://episodes/{kodi_id}"
                return url
        else:
            # Fallback to generic format
            url = f"videodb://movies/titles/{kodi_id}"
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

    def _set_infotag_metadata(self, video_info_tag, item: Dict[str, Any], title: str):
        """
        Set metadata via InfoTagVideo setters for v20+ library items.
        Uses pre-computed fields for optimal performance.
        """
        try:
            # Ensure proper media type is set first for correct identification
            media_type = item.get('media_type', 'movie')
            try:
                video_info_tag.setMediaType(media_type)
            except Exception as e:
                self.logger.warning("LIB ITEM v20+: setMediaType() failed for '%s': %s", title, e)

            # Core identification - use formatted title for episodes, original title for others
            title_for_metadata = item.get('title', '')
            if item.get('media_type') == 'episode':
                # For episodes, use the formatted display label if available
                tvshowtitle = item.get('tvshowtitle', '')
                season = item.get('season')
                episode = item.get('episode')
                if tvshowtitle and season is not None and episode is not None:
                    title_for_metadata = f"{tvshowtitle} - S{int(season):02d}E{int(episode):02d} - {title_for_metadata}"
                elif tvshowtitle:
                    title_for_metadata = f"{tvshowtitle} - {title_for_metadata}"
            
            if title_for_metadata:
                video_info_tag.setTitle(title_for_metadata)

            if item.get('year'):
                try:
                    year_value = item.get('year')
                    if year_value is not None:
                        video_info_tag.setYear(int(year_value))
                except (ValueError, TypeError):
                    pass

            # Use full plot text for complete information
            plot_text = item.get('plot', '')
            if plot_text:
                video_info_tag.setPlot(plot_text)

            # Use stored genre data (format depends on Kodi version during scan)
            genre_data = item.get('genre', '')
            if genre_data:
                try:
                    # Try to parse as JSON array first (v20+ format)
                    genres = json.loads(genre_data)
                    if isinstance(genres, list) and genres:
                        video_info_tag.setGenres(genres)
                except (json.JSONDecodeError, TypeError):
                    # Fallback to string format (v19 format or direct string)
                    if isinstance(genre_data, str):
                        genres = [g.strip() for g in genre_data.split(',') if g.strip()]
                        if genres:
                            video_info_tag.setGenres(genres)

            # Rating
            if item.get('rating'):
                try:
                    rating_value = item.get('rating')
                    if rating_value is not None:
                        video_info_tag.setRating(float(rating_value))
                except (ValueError, TypeError):
                    pass

            # Episode-specific fields
            if item.get('media_type') == 'episode':
                if item.get('season') is not None:
                    try:
                        season_value = item.get('season')
                        if season_value is not None:
                            video_info_tag.setSeason(int(season_value))
                    except (ValueError, TypeError):
                        pass

                if item.get('episode') is not None:
                    try:
                        episode_value = item.get('episode')
                        if episode_value is not None:
                            video_info_tag.setEpisode(int(episode_value))
                    except (ValueError, TypeError):
                        pass

                if item.get('tvshowtitle'):
                    video_info_tag.setTvShowTitle(item['tvshowtitle'])

                if item.get('aired'):
                    video_info_tag.setFirstAired(item['aired'])

        except Exception as e:
            self.logger.warning("LIB ITEM v20+: InfoTagVideo metadata setup failed for '%s': %s", title, e)

    def _get_kodi_mediatype(self, media_type: str) -> str:
        """Map internal media type to Kodi's expected values."""
        if media_type == 'movie':
            return 'movie'
        elif media_type == 'tvshow':
            return 'tvshow'
        elif media_type == 'episode':
            return 'episode'
        else:
            return 'movie' # Default to movie if unknown


    def build_media_listitem(self, media_item: Dict[str, Any]) -> "tuple[xbmcgui.ListItem, str]":
        """Build ListItem for media content using enhanced data from media_items table"""
        try:
            # Use media_items data directly instead of JSON RPC calls
            title = media_item.get('title', 'Unknown Title')
            year = media_item.get('year')

            # Format display title based on media type
            media_type = media_item.get('media_type', 'movie')
            # Check for episode formatting - either explicit media_type='episode' or presence of episode fields
            tvshowtitle = media_item.get('tvshowtitle', '')
            season = media_item.get('season')
            episode = media_item.get('episode')
            is_episode = (media_type == 'episode' or 
                         (tvshowtitle and season is not None and episode is not None))
            
            if is_episode:
                # Format episode title: "Show Name - S01E01 - Episode Title"
                if tvshowtitle and season is not None and episode is not None:
                    display_title = f"{tvshowtitle} - S{int(season):02d}E{int(episode):02d} - {title}"
                elif tvshowtitle:
                    display_title = f"{tvshowtitle} - {title}"
                else:
                    display_title = title
            else:
                # Movies and other media types - format with year if available
                if year:
                    display_title = f"{title} ({year})"
                else:
                    display_title = title

            listitem = xbmcgui.ListItem(label=display_title)

            # Set video info using media_items data
            info_labels = {
                'title': title,
                'mediatype': self._get_kodi_mediatype(media_item.get('media_type', 'movie')),
                'plot': media_item.get('plot', ''),
                'year': year or 0,
                'rating': media_item.get('rating', 0.0),
                'votes': str(media_item.get('votes', 0)),
                'duration': media_item.get('duration', 0),
                'mpaa': media_item.get('mpaa', ''),
                'genre': media_item.get('genre', ''),
                'director': media_item.get('director', ''),
                'studio': media_item.get('studio', ''),
                'country': media_item.get('country', ''),
                'writer': media_item.get('writer', '')
            }

            # Add IMDb number if available
            if media_item.get('imdbnumber'):
                info_labels['imdbnumber'] = media_item['imdbnumber']

            # Add TMDb ID if available
            if media_item.get('tmdb_id'):
                info_labels['tmdb'] = media_item['tmdb_id']

            # Add episode-specific fields for TV episodes
            if media_item.get('media_type') == 'episode':
                if media_item.get('tvshowtitle'):
                    info_labels['tvshowtitle'] = media_item['tvshowtitle']
                if media_item.get('season') is not None:
                    info_labels['season'] = media_item['season']
                if media_item.get('episode') is not None:
                    info_labels['episode'] = media_item['episode']
                if media_item.get('aired'):
                    info_labels['aired'] = media_item['aired']

            # Call the version-specific metadata setting function
            from ..utils.kodi_version import get_kodi_major_version
            kodi_major = get_kodi_major_version()

            if kodi_major >= 20:
                # Kodi v20+ (Nexus/Omega): Use InfoTagVideo
                try:
                    video_info_tag = listitem.getVideoInfoTag()

                    # Set basic properties
                    if info_labels.get('title'):
                        video_info_tag.setTitle(info_labels['title'])
                    if info_labels.get('plot'):
                        video_info_tag.setPlot(info_labels['plot'])
                    if info_labels.get('year'):
                        video_info_tag.setYear(int(info_labels['year']))
                    if info_labels.get('rating'):
                        video_info_tag.setRating(float(info_labels['rating']))
                    if info_labels.get('votes'):
                        video_info_tag.setVotes(int(info_labels['votes']))
                    if info_labels.get('mpaa'):
                        video_info_tag.setMpaa(info_labels['mpaa'])
                    if info_labels.get('duration'):
                        video_info_tag.setDuration(int(info_labels['duration'])) # Duration is already in seconds
                    if info_labels.get('premiered'):
                        video_info_tag.setPremiered(info_labels['premiered'])
                    if info_labels.get('studio'):
                        video_info_tag.setStudios([info_labels['studio']])
                    if info_labels.get('genre'):
                        genres = info_labels['genre'].split(',') if isinstance(info_labels['genre'], str) else [info_labels['genre']]
                        video_info_tag.setGenres([g.strip() for g in genres if g.strip()])
                    if info_labels.get('playcount'):
                        video_info_tag.setPlaycount(int(info_labels['playcount']))
                    if info_labels.get('imdbnumber'):
                        video_info_tag.setIMDbNumber(info_labels['imdbnumber'])
                    if info_labels.get('tmdb'):
                        video_info_tag.setUniqueId(str(info_labels['tmdb']), 'tmdb')

                    # Episode-specific fields
                    if info_labels.get('mediatype') == 'episode':
                        if info_labels.get('tvshowtitle'):
                            video_info_tag.setTvShowTitle(info_labels['tvshowtitle'])
                        if info_labels.get('season'):
                            video_info_tag.setSeason(int(info_labels['season']))
                        if info_labels.get('episode'):
                            video_info_tag.setEpisode(int(info_labels['episode']))
                        if info_labels.get('aired'):
                            video_info_tag.setFirstAired(info_labels['aired'])

                except Exception as e:
                    self.logger.error("Failed to set metadata via InfoTagVideo: %s", e)
                    # Fallback to setInfo for compatibility
                    listitem.setInfo('video', info_labels)
            else:
                # Kodi v19 (Matrix): Use setInfo
                listitem.setInfo('video', info_labels)

            # Set artwork using only art field data from media_items
            artwork = {}
            art_data = media_item.get('art')
            if art_data:
                try:
                    if isinstance(art_data, str):
                        artwork = json.loads(art_data)
                    elif isinstance(art_data, dict):
                        artwork = art_data.copy()
                except (json.JSONDecodeError, TypeError):
                    artwork = {}

            if artwork:
                listitem.setArt(artwork)

            # Set playable property
            listitem.setProperty('IsPlayable', 'true')

            # Build play URL using media_items play command or kodi_id
            play_command = media_item.get('play')
            kodi_id = media_item.get('kodi_id')
            media_type = media_item.get('media_type', 'movie')

            if play_command:
                # Use existing play command
                url = play_command
            elif kodi_id and media_type:
                # Build play URL from kodi_id
                if media_type == 'movie':
                    url = f"plugin://plugin.video.librarygenie/?action=play_movie&movie_id={kodi_id}"
                elif media_type == 'episode':
                    url = f"plugin://plugin.video.librarygenie/?action=play_episode&episode_id={kodi_id}"
                else:
                    url = f"plugin://plugin.video.librarygenie/?action=play_item&item_id={kodi_id}&media_type={media_type}"
            else:
                # Fallback - shouldn't happen with proper media_items data
                url = "plugin://plugin.video.librarygenie/?action=error&message=No play method available"

            return listitem, url

        except Exception as e:
            self.logger.error("Failed to build media listitem: %s", e)
            # Return error listitem
            error_item = xbmcgui.ListItem(label="Error loading item")
            error_url = "plugin://plugin.video.librarygenie/?action=error"
            return error_item, error_url