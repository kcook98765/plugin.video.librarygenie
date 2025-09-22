#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Builder
Builds ListItems with proper metadata and resume information
"""

import json
import re
import time
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
import xbmcgui
import xbmcplugin
from lib.utils.kodi_log import get_kodi_logger
from lib.utils.kodi_version import get_kodi_major_version, is_kodi_v20_plus, is_kodi_v21_plus, is_kodi_v22_plus


class ListItemBuilder:
    """Builds ListItems with proper separation between Kodi library and external items"""

    # -------- lifecycle --------
    def __init__(self, addon_handle: int, addon_id: str, context):
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.context = context
        self.logger = get_kodi_logger('lib.ui.listitem_builder')
        
        # Cache addon instance and resources base path for efficient resource access
        import os
        import xbmcaddon
        import xbmcvfs
        self._addon = xbmcaddon.Addon(self.addon_id)
        self._resources_base = xbmcvfs.translatePath(
            os.path.join(self._addon.getAddonInfo('path'), 'resources')
        )
        
        # Initialize consolidated utilities - CONSOLIDATED
        from lib.utils.listitem_utils import ListItemMetadataManager, ListItemPropertyManager, ListItemArtManager, ContextMenuBuilder
        self.metadata_manager = ListItemMetadataManager(addon_id)
        self.property_manager = ListItemPropertyManager()
        self.art_manager = ListItemArtManager(addon_id)
        self.context_menu_builder = ContextMenuBuilder(addon_id)

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
        # Start timing the complete directory build process
        build_start_time = time.time()
        
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

            # OPTIMIZED: Prepare items for batch rendering
            batch_items = []
            for idx, (url, li, is_folder, item) in enumerate(tuples, start=1):
                # Set properties for global context menu detection
                media_item_id = item.get('media_item_id') or item.get('id')
                if media_item_id:
                    li.setProperty('media_item_id', str(media_item_id))

                # Set list context if available
                list_id = item.get('list_id') or self.context.get_param('list_id')
                if list_id:
                    li.setProperty('list_id', str(list_id))

                batch_items.append((url, li, is_folder))

            # OPTIMIZED: Add all items in a single batch operation
            self.logger.debug("DIRECTORY BUILD: Adding %s directory items to Kodi in batch", len(batch_items))
            xbmcplugin.addDirectoryItems(self.addon_handle, batch_items)

            # Use updateListing for pagination to control navigation history
            current_page = int(self.context.get_param('page', '1'))
            update_listing = current_page > 1  # Replace current listing for page 2+, create new entry for page 1
            
            self.logger.debug("DIRECTORY BUILD: Calling endOfDirectory(handle=%s, succeeded=True, updateListing=%s)", 
                             self.addon_handle, update_listing)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=update_listing)
            
            # Calculate and log complete build time
            build_end_time = time.time()
            total_build_time = build_end_time - build_start_time
            self.logger.info("DIRECTORY BUILD: ✅ Successfully built directory with %s items (%s failed) - Complete build time: %.3f seconds", ok, fail, total_build_time)
            return True
        except Exception as e:
            self.logger.error("DIRECTORY BUILD: fatal error: %s", e)
            self.logger.debug("DIRECTORY BUILD: Calling endOfDirectory(handle=%s, succeeded=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
            
            # Calculate and log complete build time even on failure
            build_end_time = time.time()
            total_build_time = build_end_time - build_start_time
            self.logger.error("DIRECTORY BUILD: ❌ Failed to build directory - Complete build time: %.3f seconds", total_build_time)
            return False

    # -------- internals --------
    def _get_resource_path(self, name: str) -> str:
        """Get absolute path to addon resource (cached for efficiency)"""
        import os
        return os.path.join(self._resources_base, name)

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
            title.startswith('Sync') or
            title.startswith('+ Create') or
            title.startswith('+ Create') or
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
        OPTIMIZED: Trust canonical data from QueryManager, only process non-canonical items.
        This eliminates double normalization for optimal performance.
        """
        # Check if this is already canonical data from QueryManager
        if self._is_canonical_item(src):
            # Canonical items are already properly formatted - pass through directly
            return src

        # Only do minimal processing for non-canonical items (action items, etc.)
        out: Dict[str, Any] = {}
        
        # Basic fields for non-canonical items
        out['media_type'] = src.get('media_type', src.get('type', 'none'))
        out['title'] = src.get('title', src.get('label', 'Unknown'))
        
        # Preserve action and other special fields
        for key in ('action', 'id', 'media_item_id', 'list_id', 'url', 'is_navigation', 'navigation_type', 'icon'):
            if src.get(key):
                out[key] = src[key]
                
        return out

    def _is_canonical_item(self, item: Dict[str, Any]) -> bool:
        """Check if item is already canonical (processed by QueryManager)"""
        # Canonical items have specific fields from QueryManager normalization
        canonical_indicators = [
            'duration_minutes',  # QueryManager converts runtime to this
            'created_at',        # QueryManager preserves timestamps
            'file_path',         # QueryManager preserves file paths
            'order_score'        # QueryManager includes list ordering
        ]
        return any(item.get(field) is not None for field in canonical_indicators)

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

            li = xbmcgui.ListItem(label=display_label, offscreen=True)

            # Prioritize videodb:// URLs for library items to eliminate background processing delays,
            # fallback to direct file paths only when videodb isn't available
            if kodi_id is not None and self._is_valid_library_id(kodi_id):
                # Use videodb:// URL for native library integration (eliminates 4+ second delays)
                videodb_url = self._build_videodb_url(media_type, kodi_id, item.get('tvshowid'), item.get('season'))
                li.setPath(videodb_url)
                playback_url = videodb_url
                # For videodb:// URLs, Kodi handles IsPlayable automatically
            else:
                # Fallback to direct file path when videodb isn't available
                file_path = item.get('file_path') or item.get('play')
                if file_path and file_path.strip():
                    li.setPath(file_path)
                    self.logger.debug("LIB ITEM: Using fallback file path for '%s': %s", title, file_path)
                    playback_url = file_path
                    # For direct file paths, we need to explicitly set IsPlayable=true for context menu support
                    li.setProperty('IsPlayable', 'true')
                    self.logger.debug("LIB ITEM: Set IsPlayable=true for direct file path: '%s'", title)
                else:
                    self.logger.error("LIB ITEM: No valid path available - kodi_id=%s, file_path=%s for '%s'", kodi_id, file_path, title)
                    return None

            is_folder = False
            
            # DEBUG: Check what path is actually set on the ListItem

            # Set InfoHijack properties only if user has enabled native Kodi info hijacking
            try:
                from lib.config.settings import SettingsManager
                settings_manager = SettingsManager()
                if settings_manager.get_use_native_kodi_info():
                    li.setProperty("LG.InfoHijack.Armed", "1")
                    li.setProperty("LG.InfoHijack.DBID", str(kodi_id) if kodi_id is not None else "0")
                    li.setProperty("LG.InfoHijack.DBType", media_type)
                    
                    # OPTIMIZATION: Pre-populate navigation cache to eliminate cache misses during hijack detection
                    self._preload_hijack_cache_properties(title, kodi_id, media_type)
                else:
                    # Setting is disabled - do not arm hijack
                    self.logger.debug("📱 HIJACK DISABLED: '%s' - use_native_kodi_info setting is off", title)
            except Exception as e:
                self.logger.error("LIB ITEM: ❌ Failed to set InfoHijack properties for '%s': %s", title, e)

            # Enhanced episode title formatting for maximum skin compatibility
            self._set_enhanced_episode_formatting(li, item, display_label, is_episode)

            # Handle metadata setting based on Kodi version - CONSOLIDATED
            # For library items, use comprehensive metadata to ensure V19 gets all fields like the old method
            metadata_title = display_label if is_episode else title
            self.metadata_manager.set_comprehensive_metadata(li, item, title_override=metadata_title)
            
            # Handle DB linking for library items with V22 enhanced validation
            kodi_major = get_kodi_major_version()
            if kodi_major >= 20 and kodi_id is not None:
                try:
                    video_info_tag = li.getVideoInfoTag()
                    
                    # V22+ requires stricter validation and may need additional parameters
                    if kodi_major >= 22:
                        # V22 (Piers) - Enhanced validation with stricter type checking
                        try:
                            # Ensure all parameters are properly validated for V22
                            validated_kodi_id = int(kodi_id)
                            validated_media_type = str(media_type) if media_type else 'movie'
                            video_info_tag.setDbId(validated_kodi_id, validated_media_type)
                            self.logger.debug("LIB ITEM V22: DB linking successful for '%s' (id=%s, type=%s)", title, validated_kodi_id, validated_media_type)
                        except (TypeError, ValueError) as e:
                            self.logger.warning("LIB ITEM V22: setDbId validation failed for '%s': %s, falling back to V21 method", title, e)
                            # Fallback to V21 method
                            video_info_tag.setDbId(int(kodi_id), media_type)
                    else:
                        # V21+ standard signature (2 args), fallback to v19/v20 (1 arg)
                        try:
                            video_info_tag.setDbId(int(kodi_id), media_type)
                        except TypeError:
                            video_info_tag.setDbId(int(kodi_id))
                except Exception as e:
                    self.logger.warning("LIB ITEM: DB linking failed for '%s': %s", title, e)

            # Art from art field
            art = self._build_art_dict(item)
            if art:
                li.setArt(art)

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


            return playback_url, li, is_folder
        except Exception as e:
            self.logger.error("LIB ITEM: failed for '%s': %s", item.get('title','Unknown'), e)
            return None

    def _preload_hijack_cache_properties(self, title: str, kodi_id, media_type: str):
        """
        Pre-populate navigation cache with hijack properties to eliminate cache misses
        during hijack detection.
        """
        try:
            from lib.ui.navigation_cache import get_navigation_cache
            import time
            
            cache = get_navigation_cache()
            now = time.monotonic()
            
            # Pre-populate cache with hijack properties that will be accessed during hijack detection
            hijack_properties = {
                'ListItem.Property(LG.InfoHijack.Armed)': '1',
                'ListItem.Property(LG.InfoHijack.DBID)': str(kodi_id) if kodi_id is not None else '0',
                'ListItem.Property(LG.InfoHijack.DBType)': media_type,
                'ListItem.Label': title,
                'ListItem.DBID': str(kodi_id) if kodi_id is not None else '',
                'ListItem.DBTYPE': media_type
            }
            
            # Populate cache directly to avoid API calls during hijack
            with cache._lock:
                for label, value in hijack_properties.items():
                    cache._cache[label] = {
                        'value': value,
                        'timestamp': now,
                        'generation': cache._generation
                    }
            
            
        except Exception as e:
            self.logger.debug("CACHE PRELOAD: Failed to pre-populate cache for '%s': %s", title, e)

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
            li = xbmcgui.ListItem(label=title, offscreen=True)

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
            icon = None  # Initialize icon variable
            
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
                # For create list/folder actions, try to use custom art
                if 'Create' in title and ('List' in title or 'Folder' in title):
                    # Use the art manager to apply type-specific art
                    try:
                        if 'List' in title:
                            self.art_manager.apply_type_specific_art(li, 'list', self._get_resource_path)
                        elif 'Folder' in title:
                            self.art_manager.apply_type_specific_art(li, 'folder', self._get_resource_path)
                        else:
                            li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
                    except:
                        li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
                else:
                    icon = 'DefaultFolder.png'  # Standard folder icon for other actions
            
            # Set art with icon if one was specified
            if icon:
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
            li = xbmcgui.ListItem(label=display_label, offscreen=True)

            # Apply metadata based on Kodi version - CONSOLIDATED
            plot_text = item.get('plot', '')
            self.metadata_manager.set_basic_metadata(li, title, plot_text, "video")

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

    def _build_art_dict(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Build artwork dictionary from item data - CONSOLIDATED"""
        return self.art_manager.build_art_dict(item)

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

    def _set_enhanced_episode_formatting(self, li: xbmcgui.ListItem, item: Dict[str, Any], display_label: str, is_episode: bool):
        """
        Enhanced episode title formatting for maximum skin compatibility across Kodi versions.
        Sets multiple label/title fields and properties that different skins might check.
        """
        try:
            if not is_episode:
                return
                
            tvshowtitle = item.get('tvshowtitle', '')
            season = item.get('season')
            episode = item.get('episode')
            title = item.get('title', '')
            kodi_major = get_kodi_major_version()
            
            # Set ListItem label explicitly - some skins check this directly
            li.setLabel(display_label)
            self.logger.debug("EPISODE FORMAT: Set ListItem.Label to '%s'", display_label)
            
            # Set custom properties for skins that might use them
            li.setProperty('formatted_episode_title', display_label)
            li.setProperty('episode_format_type', 'extended')
            
            # Set individual formatted components for skins that construct their own labels
            if tvshowtitle and season is not None and episode is not None:
                li.setProperty('episode_formatted_number', f"S{int(season):02d}E{int(episode):02d}")
                li.setProperty('episode_full_context', f"{tvshowtitle} - S{int(season):02d}E{int(episode):02d}")
            
            # Version-specific additional properties for enhanced compatibility
            if kodi_major >= 21:
                # v21+ specific properties
                li.setProperty('kodi21_episode_label', display_label)
                self.logger.debug("EPISODE FORMAT v21+: Set enhanced properties for '%s'", title)
            elif kodi_major >= 20:
                # v20 specific properties  
                li.setProperty('kodi20_episode_label', display_label)
                self.logger.debug("EPISODE FORMAT v20: Set enhanced properties for '%s'", title)
            else:
                # v19 fallback properties
                li.setProperty('kodi19_episode_label', display_label)
                self.logger.debug("EPISODE FORMAT v19: Set fallback properties for '%s'", title)
                
        except Exception as e:
            self.logger.warning("EPISODE FORMAT: Failed to set enhanced formatting for '%s': %s", item.get('title', 'Unknown'), e)


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

            listitem = xbmcgui.ListItem(label=display_title, offscreen=True)

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
            from lib.utils.kodi_version import get_kodi_major_version
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
                    # setUniqueId introduced in Kodi v20+, but double-check it exists
                    if info_labels.get('tmdb') and get_kodi_major_version() >= 20 and hasattr(video_info_tag, 'setUniqueId'):
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

                except (AttributeError, TypeError) as e:
                    # Only catch specific exceptions that indicate API compatibility issues
                    self.logger.warning("InfoTagVideo method failed with %s: %s", type(e).__name__, e)
                    
                    # Only fallback to setInfo for Kodi v20 (where InfoTagVideo might have issues)
                    # For Kodi v21+, InfoTagVideo should work fine, so log error without fallback
                    if kodi_major == 20:
                        self.logger.info("Using setInfo() fallback for Kodi v20 compatibility")
                        listitem.setInfo('video', info_labels)
                    else:
                        # Kodi v21+ should not need setInfo() fallback
                        self.logger.error("InfoTagVideo failed on Kodi v%s - this should not happen. Skipping metadata.", kodi_major)
                except Exception as e:
                    # Log unexpected errors but don't use deprecated fallback
                    self.logger.error("Unexpected error setting metadata on Kodi v%s: %s", kodi_major, e)
                    if kodi_major < 21:
                        # Only use deprecated fallback for pre-v21
                        self.logger.info("Using setInfo() fallback for Kodi v%s", kodi_major)
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
            error_item = xbmcgui.ListItem(label="Error loading item", offscreen=True)
            error_url = "plugin://plugin.video.librarygenie/?action=error"
            return error_item, error_url