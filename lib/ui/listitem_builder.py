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
            
            self.logger.info("DIRECTORY BUILD: Starting build with %s items (content_type='%s')", count, content_type)
            xbmcplugin.setContent(self.addon_handle, content_type)

            # Add a few sane sort methods once
            sort_methods = [
                ("SORT_METHOD_TITLE_IGNORE_THE", xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE),
                ("SORT_METHOD_DATE", xbmcplugin.SORT_METHOD_DATE),
                ("SORT_METHOD_VIDEO_YEAR", xbmcplugin.SORT_METHOD_VIDEO_YEAR),
            ]
            for method_name, const in sort_methods:
                xbmcplugin.addSortMethod(self.addon_handle, const)

            tuples: List[tuple] = []
            ok = 0
            fail = 0
            for idx, raw in enumerate(items, start=1):
                try:
                    item = self._normalize_item(raw)  # canonical shape
                    built = self._build_single_item(item)
                    if built:
                        url, listitem, is_folder = built
                        title = item.get('title', 'Unknown')
                        
                        # Critical check for empty URLs in directory build
                        if not url or not url.strip():
                            self.logger.error("PLAYBACK_DEBUG: ❌ CRITICAL - Empty URL being added to directory for '%s' at position %s!", title, idx)

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
            
            # Check for empty URLs in final batch
            for idx, (batch_url, batch_li, batch_is_folder) in enumerate(batch_items, start=1):
                if not batch_url or not batch_url.strip():
                    self.logger.error("PLAYBACK_DEBUG: ❌ CRITICAL - Empty URL in final batch at position %s!", idx)
            
            # FIRST_PLAYABLE_DEBUG: Log comprehensive details of first playable item
            if self._should_debug_first_playable():
                self._debug_first_playable_item(batch_items, tuples)
            
            xbmcplugin.addDirectoryItems(self.addon_handle, batch_items)

            # Use Navigator for pagination with proper semantics: page>1 is a morph (replace)
            current_page = int(self.context.get_param('page', '1'))
            update = current_page > 1  # Replace current listing for page 2+, create new entry for page 1
            
            from lib.ui.nav import finish_directory
            self.logger.debug("DIRECTORY BUILD: Calling Navigator.finish_directory(handle=%s, succeeded=True, update=%s)", 
                             self.addon_handle, update)
            finish_directory(self.addon_handle, succeeded=True, update=update)
            
            # Calculate and log complete build time
            build_end_time = time.time()
            total_build_time = build_end_time - build_start_time
            self.logger.info("DIRECTORY BUILD: ✅ Successfully built directory with %s items (%s failed) - Complete build time: %.3f seconds", ok, fail, total_build_time)
            return True
        except Exception as e:
            self.logger.error("DIRECTORY BUILD: fatal error: %s", e)
            self.logger.debug("DIRECTORY BUILD: Calling Navigator.finish_directory(handle=%s, succeeded=False)", self.addon_handle)
            from lib.ui.nav import finish_directory
            finish_directory(self.addon_handle, succeeded=False)
            
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
        using direct file paths for reliable playback across all Kodi versions.
        """
        try:
            title = item.get('title', 'Unknown')
            media_type = item.get('media_type', 'movie')
            kodi_id = item.get('kodi_id')  # Keep for hijack functionality

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

            # Use direct file path for consistent playback behavior across all Kodi versions
            file_path = item.get('file_path') or item.get('play')
            if not file_path or not file_path.strip():
                self.logger.error("LIB ITEM: No valid file path available for '%s'", title)
                return None
                
            li.setPath(file_path)
            playback_url = file_path
            # Set IsPlayable=true for proper playback and context menu support
            li.setProperty('IsPlayable', 'true')

            is_folder = False
            

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
                    pass
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

            # Final validation before returning tuple
            try:
                final_path_check = li.getPath() if hasattr(li, 'getPath') else 'N/A'
                
                # Critical validation: Check for empty URLs that could cause V22 failures
                if not playback_url or not playback_url.strip():
                    self.logger.error("PLAYBACK_DEBUG: ❌ CRITICAL - Empty playback_url for '%s' (kodi_id=%s)!", title, kodi_id)
                if final_path_check and (not final_path_check.strip() or final_path_check == 'N/A'):
                    self.logger.error("PLAYBACK_DEBUG: ❌ CRITICAL - Empty ListItem path for '%s'!", title)
                    
            except Exception as debug_e:
                self.logger.warning("PLAYBACK_DEBUG: Failed final validation for '%s': %s", title, debug_e)

            # Add context menu options for list items
            self._add_media_context_menu(li, item, media_type, kodi_id, title)
            
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
    
    def _add_media_context_menu(self, li: 'xbmcgui.ListItem', item: Dict[str, Any], media_type: str, kodi_id, title: str):
        """Add context menu items for media items when viewing lists"""
        try:
            # Check if we're in a list context
            list_id = item.get('list_id') or self.context.get_param('list_id')
            if not list_id:
                return
            
            # Get media_item_id if available (preferred for LibraryGenie items)
            media_item_id = item.get('media_item_id') or item.get('id')
            
            context_items = []
            
            # Import localization for labels
            try:
                from lib.ui.localization import L
                remove_label = L(31010) if L(31010) else "Remove from List"
            except ImportError:
                remove_label = "Remove from List"
            
            # Build the appropriate remove action URL based on available data
            if media_item_id and media_item_id != '':
                # Use media_item_id for LibraryGenie items
                remove_url = f"RunPlugin(plugin://{self.addon_id}/?action=remove_from_list&list_id={list_id}&item_id={media_item_id})"
            elif media_type and kodi_id is not None:
                # Use library item identifiers
                remove_url = f"RunPlugin(plugin://{self.addon_id}/?action=remove_library_item_from_list&list_id={list_id}&dbtype={media_type}&dbid={kodi_id}&title={title})"
            else:
                # No valid identifiers available
                return
            
            context_items.append((remove_label, remove_url))
            
            # Add the context menu items to the ListItem
            li.addContextMenuItems(context_items)
            
        except Exception as e:
            self.logger.error("CONTEXT: Failed to add context menu for '%s': %s", title, e)

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
    def _clean_info_labels_for_v22(self, info_labels: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and validate info labels for V22 stricter validation requirements.
        
        Args:
            info_labels: Original info labels dictionary
            
        Returns:
            Dict[str, Any]: Cleaned info labels with V22-compatible values
        """
        cleaned = {}
        
        for key, value in info_labels.items():
            try:
                # Skip None values completely for V22
                if value is None:
                    continue
                    
                # V22 requires proper type validation
                if key in ('year', 'season', 'episode', 'playcount', 'duration', 'votes'):
                    # Numeric fields must be valid integers
                    if isinstance(value, str) and value.strip().isdigit():
                        cleaned[key] = int(value)
                    elif isinstance(value, (int, float)) and value >= 0:
                        cleaned[key] = int(value)
                    # Skip invalid numeric values for V22
                elif key in ('title', 'plot', 'tagline', 'studio', 'genre', 'director', 'writer', 
                           'tvshowtitle', 'premiered', 'aired', 'mpaa', 'imdbnumber', 'tmdb'):
                    # String fields must be properly encoded and non-empty
                    if isinstance(value, str) and value.strip():
                        cleaned[key] = value.strip()
                    elif value:  # Convert non-string values to string
                        cleaned[key] = str(value).strip()
                elif key == 'mediatype':
                    # Media type must be valid
                    if value in ('movie', 'episode', 'tvshow', 'season'):
                        cleaned[key] = value
                else:
                    # Other fields - pass through if valid
                    if value:
                        cleaned[key] = value
                        
            except (TypeError, ValueError) as e:
                self.logger.debug("V22: Skipping invalid field '%s' with value '%s': %s", key, value, e)
                continue
        
        self.logger.debug("V22: Cleaned info labels - original: %d fields, cleaned: %d fields", 
                         len(info_labels), len(cleaned))
        return cleaned


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
                    
                    # V22+ enhanced error handling with stricter validation
                    if kodi_major >= 22:
                        self.logger.warning("V22: InfoTagVideo validation failed, attempting data cleanup: %s", e)
                        try:
                            # Try with cleaned/validated data for V22 compatibility
                            cleaned_info = self._clean_info_labels_for_v22(info_labels)
                            # Create a minimal item dict for set_comprehensive_metadata
                            cleaned_item = {'title': cleaned_info.get('title', 'Unknown')}
                            cleaned_item.update(cleaned_info)
                            self.metadata_manager.set_comprehensive_metadata(listitem, cleaned_item)
                            self.logger.debug("V22: Successfully set metadata with cleaned data")
                        except Exception as e2:
                            self.logger.error("V22: InfoTagVideo failed even with cleaned data - metadata may be incomplete: %s", e2)
                    elif kodi_major == 20:
                        # Only fallback to setInfo for Kodi v20 (where InfoTagVideo might have issues)
                        self.logger.info("Using setInfo() fallback for Kodi v20 compatibility")
                        listitem.setInfo('video', info_labels)
                    else:
                        # Kodi v21+ should not need setInfo() fallback
                        self.logger.error("InfoTagVideo failed on Kodi v%s - this should not happen. Skipping metadata.", kodi_major)
                except Exception as e:
                    # Log unexpected errors but don't use deprecated fallback
                    if kodi_major >= 22:
                        self.logger.error("V22: Unexpected metadata error with enhanced validation: %s", e)
                        # V22+ should not use setInfo() - it's fully deprecated
                        self.logger.warning("V22: Some metadata fields may be missing due to stricter validation")
                    else:
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

    # -------- First Playable Debug Methods --------
    
    def _should_debug_first_playable(self) -> bool:
        """Check if first playable debugging is enabled"""
        try:
            # Use Kodi settings as primary control
            from lib.config.settings import SettingsManager
            settings = SettingsManager()
            return settings.get_debug_first_playable()
        except Exception as e:
            self.logger.debug("FIRST_PLAYABLE_DEBUG: Error checking debug setting: %s", e)
            # Fallback to environment variable if settings fail
            try:
                import os
                env_debug = os.getenv('LG_DEBUG_FIRST_PLAYABLE', '').lower()
                return env_debug in ('true', '1', 'yes')
            except Exception:
                return False
    
    def _debug_first_playable_item(self, batch_items: List[tuple], tuples: List[tuple]):
        """Debug the first playable item in the batch"""
        try:
            first_playable_found = False
            
            for idx, (batch_url, batch_li, batch_is_folder) in enumerate(batch_items, start=1):
                # Check if this is a playable item (not a folder, has IsPlayable=true)
                is_playable = batch_li.getProperty('IsPlayable') == 'true'
                
                if is_playable and not batch_is_folder and not first_playable_found:
                    # This is our first playable item - log everything
                    self.logger.info("FIRST_PLAYABLE_DEBUG: Found first playable item at position #%s", idx)
                    
                    # Get original item data if available
                    original_item = tuples[idx-1][3] if idx <= len(tuples) else None
                    
                    self._log_first_playable_details(batch_li, batch_url, idx, original_item)
                    first_playable_found = True
                    break
            
            if not first_playable_found:
                self.logger.info("FIRST_PLAYABLE_DEBUG: No playable items found in this batch")
                
        except Exception as e:
            self.logger.error("FIRST_PLAYABLE_DEBUG: Error during debugging: %s", e)
    
    def _log_first_playable_details(self, listitem: xbmcgui.ListItem, url: str, position: int, original_item: Optional[Dict[str, Any]] = None):
        """Log comprehensive details of the first playable listitem for debugging"""
        self.logger.info("=" * 80)
        self.logger.info("FIRST_PLAYABLE_DEBUG: DETAILED LOGGING - Position #%s", position)
        self.logger.info("=" * 80)
        
        # Basic info
        self.logger.info("FIRST_PLAYABLE_DEBUG: URL = '%s'", url)
        try:
            actual_path = listitem.getPath() if hasattr(listitem, 'getPath') else 'N/A'
            self.logger.info("FIRST_PLAYABLE_DEBUG: ListItem.getPath() = '%s'", actual_path)
        except Exception as e:
            self.logger.info("FIRST_PLAYABLE_DEBUG: ListItem.getPath() = ERROR: %s", e)
        
        # Properties
        self._log_listitem_properties(listitem)
        
        # Metadata (version-safe)
        self._log_listitem_metadata(listitem)
        
        # Art
        self._log_listitem_art(listitem)
        
        # Original item data
        if original_item:
            self._log_original_item_data(original_item)
        
        self.logger.info("=" * 80)
        self.logger.info("FIRST_PLAYABLE_DEBUG: END OF DETAILED LOGGING")
        self.logger.info("=" * 80)
    
    def _log_listitem_properties(self, listitem: xbmcgui.ListItem):
        """Log all relevant properties of the listitem"""
        try:
            # Core properties to check
            properties_to_check = [
                'IsPlayable', 'media_item_id', 'list_id', 
                'LG.InfoHijack.Armed', 'LG.InfoHijack.DBID', 'LG.InfoHijack.DBType',
                'LG.InfoHijack.Nav.Title', 'LG.InfoHijack.Nav.DBID', 'LG.InfoHijack.Nav.DBType'
            ]
            
            self.logger.info("FIRST_PLAYABLE_DEBUG: --- PROPERTIES ---")
            for prop in properties_to_check:
                try:
                    value = listitem.getProperty(prop)
                    if value:
                        self.logger.info("FIRST_PLAYABLE_DEBUG: Property['%s'] = '%s'", prop, value)
                    else:
                        self.logger.info("FIRST_PLAYABLE_DEBUG: Property['%s'] = <empty/not set>", prop)
                except Exception as e:
                    self.logger.info("FIRST_PLAYABLE_DEBUG: Property['%s'] = ERROR: %s", prop, e)
                    
        except Exception as e:
            self.logger.error("FIRST_PLAYABLE_DEBUG: Error logging properties: %s", e)
    
    def _log_listitem_metadata(self, listitem: xbmcgui.ListItem):
        """Log metadata of the listitem in a version-safe way"""
        try:
            kodi_major = get_kodi_major_version()
            self.logger.info("FIRST_PLAYABLE_DEBUG: --- METADATA (Kodi v%s) ---", kodi_major)
            
            if kodi_major >= 21:
                # Use InfoTagVideo for V21+
                try:
                    video_tag = listitem.getVideoInfoTag()
                    metadata_fields = [
                        ('getTitle', 'Title'),
                        ('getPlot', 'Plot'),
                        ('getYear', 'Year'),
                        ('getRating', 'Rating'),
                        ('getGenres', 'Genres'),
                        ('getDirectors', 'Directors'),
                        ('getWriters', 'Writers'),
                        ('getDuration', 'Duration'),
                        ('getIMDBNumber', 'IMDB Number')
                    ]
                    
                    for method_name, display_name in metadata_fields:
                        try:
                            if hasattr(video_tag, method_name):
                                value = getattr(video_tag, method_name)()
                                self.logger.info("FIRST_PLAYABLE_DEBUG: VideoTag.%s = '%s'", display_name, value)
                            else:
                                self.logger.info("FIRST_PLAYABLE_DEBUG: VideoTag.%s = <method not available>", display_name)
                        except Exception as e:
                            self.logger.info("FIRST_PLAYABLE_DEBUG: VideoTag.%s = ERROR: %s", display_name, e)
                            
                except Exception as e:
                    self.logger.info("FIRST_PLAYABLE_DEBUG: VideoTag = ERROR: %s", e)
                    
            else:
                # For V19/V20, we can't safely extract all metadata due to getInfo() limitations
                # Just log what we know from context
                self.logger.info("FIRST_PLAYABLE_DEBUG: V19/V20 - Limited metadata extraction available")
                try:
                    label = listitem.getLabel()
                    self.logger.info("FIRST_PLAYABLE_DEBUG: Label = '%s'", label)
                except Exception as e:
                    self.logger.info("FIRST_PLAYABLE_DEBUG: Label = ERROR: %s", e)
                    
        except Exception as e:
            self.logger.error("FIRST_PLAYABLE_DEBUG: Error logging metadata: %s", e)
    
    def _log_listitem_art(self, listitem: xbmcgui.ListItem):
        """Log artwork URLs of the listitem"""
        try:
            self.logger.info("FIRST_PLAYABLE_DEBUG: --- ARTWORK ---")
            
            # Art types to check
            art_types = ['poster', 'fanart', 'banner', 'thumb', 'clearart', 'clearlogo', 'landscape', 'icon']
            
            try:
                # Get all art - handle version differences safely
                art_dict = {}
                if hasattr(listitem, 'getArt'):
                    try:
                        art_dict = listitem.getArt("")
                    except (TypeError, AttributeError):
                        # Some Kodi versions have different getArt() signatures
                        art_dict = {}
                if art_dict:
                    for art_type in art_types:
                        art_url = art_dict.get(art_type, '')
                        if art_url:
                            self.logger.info("FIRST_PLAYABLE_DEBUG: Art['%s'] = '%s'", art_type, art_url)
                        else:
                            self.logger.info("FIRST_PLAYABLE_DEBUG: Art['%s'] = <not set>", art_type)
                    
                    # Log any other art types not in our standard list
                    other_art = {k: v for k, v in art_dict.items() if k not in art_types}
                    if other_art:
                        for art_type, art_url in other_art.items():
                            self.logger.info("FIRST_PLAYABLE_DEBUG: Art['%s'] = '%s' (non-standard)", art_type, art_url)
                else:
                    self.logger.info("FIRST_PLAYABLE_DEBUG: Art = <no artwork set>")
                    
            except Exception as e:
                self.logger.info("FIRST_PLAYABLE_DEBUG: Art = ERROR: %s", e)
                
        except Exception as e:
            self.logger.error("FIRST_PLAYABLE_DEBUG: Error logging artwork: %s", e)
    
    def _log_original_item_data(self, original_item: Dict[str, Any]):
        """Log key fields from the original item dictionary"""
        try:
            self.logger.info("FIRST_PLAYABLE_DEBUG: --- ORIGINAL ITEM DATA ---")
            
            # Key fields to log
            key_fields = [
                'title', 'media_type', 'kodi_id', 'file_path', 'year', 'rating', 
                'plot', 'genre', 'director', 'duration', 'tmdb_id', 'imdb_id',
                'play', 'tvshowtitle', 'season', 'episode'
            ]
            
            for field in key_fields:
                if field in original_item:
                    value = original_item[field]
                    # Truncate long values for readability
                    if isinstance(value, str) and len(value) > 200:
                        value = value[:200] + "... (truncated)"
                    self.logger.info("FIRST_PLAYABLE_DEBUG: OriginalItem['%s'] = '%s'", field, value)
                else:
                    self.logger.info("FIRST_PLAYABLE_DEBUG: OriginalItem['%s'] = <not present>", field)
            
            # Log any other fields not in our standard list
            other_fields = {k: v for k, v in original_item.items() if k not in key_fields}
            if other_fields:
                self.logger.info("FIRST_PLAYABLE_DEBUG: --- OTHER ORIGINAL ITEM FIELDS ---")
                for field, value in other_fields.items():
                    if isinstance(value, str) and len(value) > 100:
                        value = str(value)[:100] + "... (truncated)"
                    self.logger.info("FIRST_PLAYABLE_DEBUG: OriginalItem['%s'] = '%s' (other)", field, value)
                    
        except Exception as e:
            self.logger.error("FIRST_PLAYABLE_DEBUG: Error logging original item data: %s", e)