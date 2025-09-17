#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Menu Builder
Builds Kodi directory listings and menus
"""

from urllib.parse import urlencode
from typing import List, Tuple, Dict, Any, Optional, Callable

import xbmcgui
import xbmcplugin

from lib.utils.kodi_log import get_kodi_logger
from lib.utils.kodi_version import get_kodi_major_version
from lib.ui.listitem_renderer import get_listitem_renderer
from lib.ui.localization import L


class MenuBuilder:
    """Builds menus and directory listings for Kodi with Phase 11 enhancements"""

    def __init__(self, string_getter: Optional[Callable[[int], str]] = None):
        self.logger = get_kodi_logger('lib.ui.menu_builder')
        self.renderer = get_listitem_renderer()

    def build_menu(self, items, addon_handle, base_url, breadcrumb_path=None):
        """Build a directory menu from items with optional breadcrumb"""
        self.logger.debug("MENU BUILD: Starting build_menu with %s items", len(items))
        self.logger.debug("MENU BUILD: addon_handle=%s, base_url='%s', breadcrumb='%s'", addon_handle, base_url, breadcrumb_path)

        successful_items = 0
        failed_items = 0

        # Breadcrumb notifications deprecated - replaced by Tools & Options integration

        # Add Tools & Options with breadcrumb context for non-root views
        # But only if no Tools & Options item already exists in the menu items
        if breadcrumb_path and breadcrumb_path.strip():
            # Check if any item already contains "Tools & Options" to avoid duplicates
            has_tools_item = any(
                'Tools & Options' in item.get('label', '') or 
                'Tools & Options' in item.get('title', '')
                for item in items
            )
            
            if not has_tools_item:
                try:
                    from lib.ui.breadcrumb_helper import get_breadcrumb_helper
                    breadcrumb_helper = get_breadcrumb_helper()
                    
                    breadcrumb_text = breadcrumb_helper.get_breadcrumb_for_tools_label_raw(breadcrumb_path)
                    description_text = breadcrumb_helper.get_breadcrumb_for_tools_description_raw(breadcrumb_path)
                    
                    tools_item = xbmcgui.ListItem(label=f"[COLOR yellow]Tools & Options[/COLOR] {breadcrumb_text}")
                    tools_item.setInfo('video', {'plot': description_text})
                    tools_item.setProperty('IsPlayable', 'false')
                    tools_item.setArt({'icon': "DefaultAddonProgram.png", 'thumb': "DefaultAddonProgram.png"})
                    
                    # Build context-appropriate tools URL based on breadcrumb path
                    if " > " in breadcrumb_path:
                        # Parse breadcrumb to determine context
                        parts = breadcrumb_path.split(" > ")
                        if len(parts) == 2 and parts[0] == "Lists":
                            # Format: "Lists > Folder Name" = folder context (but handlers should add their own)
                            tools_url = f"{base_url}?action=show_list_tools&list_type=lists_main"
                        elif len(parts) >= 3 and parts[0] == "Lists":
                            # Format: "Lists > Folder > List Name" = list context 
                            tools_url = f"{base_url}?action=show_list_tools&list_type=lists_main"  
                        else:
                            # Other contexts (e.g., "Search History")
                            tools_url = f"{base_url}?action=show_list_tools&list_type=lists_main"
                    else:
                        # Single-level breadcrumb
                        if breadcrumb_path == "Kodi Favorites":
                            tools_url = f"{base_url}?action=show_list_tools&list_type=favorites"
                        else:
                            tools_url = f"{base_url}?action=show_list_tools&list_type=lists_main"
                    
                    xbmcplugin.addDirectoryItem(
                        addon_handle,
                        tools_url,
                        tools_item,
                        True
                    )
                    self.logger.debug("MENU BUILD: Added Tools & Options with breadcrumb: %s", breadcrumb_text)
                except Exception as e:
                    self.logger.error("MENU BUILD: Failed to add Tools & Options: %s", e)
            else:
                self.logger.debug("MENU BUILD: Skipping Tools & Options - already present in menu items")

        for idx, item in enumerate(items):
            try:
                item_title = item.get('title', 'Unknown')
                self.logger.debug("MENU BUILD: Processing menu item %s/%s: '%s'", idx+1, len(items), item_title)
                self.logger.debug("MENU BUILD: Item %s data: %s", idx+1, item)

                self._add_directory_item(item, addon_handle, base_url)
                successful_items += 1
                self.logger.debug("MENU BUILD: Successfully added menu item %s: '%s'", idx+1, item_title)
            except Exception as e:
                failed_items += 1
                self.logger.error("MENU BUILD: Failed to add menu item %s: %s", idx+1, e)

        self.logger.debug("MENU BUILD: Added %s menu items successfully, %s failed", successful_items, failed_items)
        self.logger.debug("MENU BUILD: Calling endOfDirectory(handle=%s, cacheToDisc=False)", addon_handle)
        xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
        self.logger.debug("MENU BUILD: Completed endOfDirectory for menu with caching disabled")

    def _add_directory_item(self, item, addon_handle, base_url):
        """Add a single directory item with context menu support"""
        title = item.get("label", item.get("title", "Unknown"))
        action = item.get("action", "")
        description = item.get("description", "")
        is_folder = item.get("is_folder", True)
        context_menu = item.get("context_menu", [])

        self.logger.debug("MENU ITEM: Processing '%s' - action='%s', is_folder=%s", title, action, is_folder)

        # Log all item properties for debugging
        item_keys = list(item.keys())
        self.logger.debug("MENU ITEM: Available properties for '%s': %s", title, item_keys)

        # Build URL with parameters
        param_keys = []
        if item.get("url"):
            # Use provided URL directly
            url = item["url"]
        elif action:
            # Build URL from action and other parameters
            params = {"action": action}
            excluded_keys = ["label", "title", "description", "action", "is_folder", "context_menu", "movie_data", "url"]

            for key, value in item.items():
                if key not in excluded_keys:
                    params[key] = value
                    param_keys.append(key)

            url = f"{base_url}?{urlencode(params)}"
        else:
            url = ""
        self.logger.debug("MENU ITEM: Built URL for '%s': '%s'", title, url)
        if param_keys:
            self.logger.debug("MENU ITEM: Added URL parameters for '%s': %s", title, param_keys)

        # Create list item - check if this is a movie item for enhanced rendering
        if item.get("movie_data"):
            # Use Phase 11 renderer for movie items
            self.logger.debug("MENU ITEM: Using movie renderer for '%s' with movie_data", title)
            list_item = self.renderer.create_movie_listitem(item["movie_data"], base_url, action)
        else:
            # Use simple renderer for menu items
            self.logger.debug("MENU ITEM: Using simple renderer for '%s'", title)
            list_item = self.renderer.create_simple_listitem(title, description, action, icon=item.get("icon"))

            # Ensure non-folder action items are not marked as playable to prevent info dialog
            if not is_folder and action and list_item is not None:
                list_item.setProperty('IsPlayable', 'false')

        # Check if list_item was created successfully
        if list_item is None:
            self.logger.error("MENU ITEM: Failed to create list item for '%s' - skipping", title)
            return

        # Add context menu if provided
        context_items_added = 0
        if context_menu and list_item is not None:
            list_item.addContextMenuItems(context_menu)
            context_items_added = len(context_menu)
            self.logger.debug("MENU ITEM: Added %s base context menu items for '%s'", context_items_added, title)

        # Context menus now handled globally via addon.xml and context.py

        if context_items_added > 0:
            self.logger.debug("MENU ITEM: Total context menu items for '%s': %s", title, context_items_added)

        # Add to directory
        xbmcplugin.addDirectoryItem(
            handle=addon_handle, url=url, listitem=list_item, isFolder=is_folder
        )
        self.logger.debug("MENU ITEM: Successfully added '%s' to directory", title)

    def _show_breadcrumb_if_needed(self, breadcrumb_path: str):
        """[DEPRECATED] Breadcrumb context now integrated into Tools & Options labels"""
        # Keeping method for backward compatibility but making it no-op
        pass


    def build_movie_menu(self, movies: List[Dict[str, Any]], addon_handle, base_url, **options):
        """Build a menu specifically for movie items with enhanced ListItems"""
        self.logger.debug("MOVIE MENU: Starting build_movie_menu with %s movies", len(movies))
        self.logger.debug("MOVIE MENU: addon_handle=%s, base_url='%s', options=%s", addon_handle, base_url, list(options.keys()))

        # Set content type for better skin support
        self.logger.debug("MOVIE MENU: Setting content type 'movies' for handle %s", addon_handle)
        xbmcplugin.setContent(addon_handle, 'movies')
        self.logger.debug("MOVIE MENU: Successfully set content type to 'movies'")

        # Show breadcrumb notification for non-root views
        breadcrumb_path = options.get('breadcrumb_path')
        self._show_breadcrumb_if_needed(breadcrumb_path)

        # Add sort methods for movie lists
        sort_methods = [
            ('SORT_METHOD_LABEL_IGNORE_THE', xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE),
            ('SORT_METHOD_YEAR', xbmcplugin.SORT_METHOD_YEAR),
            ('SORT_METHOD_VIDEO_RATING', xbmcplugin.SORT_METHOD_VIDEO_RATING),
            ('SORT_METHOD_DATE_ADDED', xbmcplugin.SORT_METHOD_DATE_ADDED),
            ('SORT_METHOD_VIDEO_RUNTIME', xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
        ]

        for method_name, method in sort_methods:
            xbmcplugin.addSortMethod(addon_handle, method)
            self.logger.debug("MOVIE MENU: Added sort method %s", method_name)

        # Build movie items
        successful_movies = 0
        failed_movies = 0

        for idx, movie in enumerate(movies):
            try:
                self.logger.debug("MOVIE MENU: Processing movie %s/%s: '%s'", idx+1, len(movies), movie.get('title', 'Unknown'))
                self._add_movie_item(movie, addon_handle, base_url, **options)
                successful_movies += 1
            except Exception as e:
                failed_movies += 1
                self.logger.error("MOVIE MENU: Failed to add movie %s: %s", idx+1, e)

        self.logger.debug("MOVIE MENU: Added %s movies successfully, %s failed", successful_movies, failed_movies)

        # Set view mode if specified
        view_mode = options.get('view_mode')
        category = options.get('category', 'Movies')
        if view_mode:
            xbmcplugin.setPluginCategory(addon_handle, category)
            self.logger.debug("MOVIE MENU: Set plugin category to '%s' with view_mode '%s'", category, view_mode)
        else:
            self.logger.debug("MOVIE MENU: No view_mode specified, using default category '%s'", category)

        xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
        self.logger.info("MOVIE MENU: Completed movie menu build with caching disabled")

    def _add_movie_item(self, movie_data: Dict[str, Any], addon_handle, base_url, **options):
        """Add a movie item with Phase 11 enhanced ListItem"""

        # Create enhanced ListItem using the renderer
        list_item = self.renderer.create_movie_listitem(movie_data, base_url, action="play_movie")

        # Build playback URL
        kodi_id = movie_data.get('kodi_id')
        if kodi_id:
            params = {
                "action": options.get('default_action', 'play_movie'),
                "kodi_id": kodi_id
            }
            url = f"{base_url}?{urlencode(params)}"
        else:
            url = ""

        # Add additional context menu items if specified
        extra_context = options.get('extra_context_menu', [])
        if extra_context and list_item is not None:
            # Get existing context menu items (should be tuples)
            current_context = list_item.getProperty('ContextMenuItems') or []
            if isinstance(current_context, str):
                # Convert single string to tuple format
                current_context = [(current_context, f'RunPlugin({current_context})')]
            elif current_context and isinstance(current_context[0], str):
                # Convert list of strings to list of tuples
                current_context = [(item, f'RunPlugin({item})') for item in current_context]

            # Ensure extra_context is in tuple format
            if extra_context:
                if isinstance(extra_context[0], str):
                    # Convert strings to tuples
                    extra_context = [(item, f'RunPlugin({item})') for item in extra_context]
                current_context.extend(extra_context)

            list_item.addContextMenuItems(current_context)

        # Set as playable item and add to directory only if list_item is valid
        if list_item is not None:
            list_item.setProperty('IsPlayable', 'true')

            # Set plot from description if available, using version-specific methods
            if 'description' in movie_data:
                kodi_major = get_kodi_major_version()
                if kodi_major >= 20:
                    try:
                        video_info_tag = list_item.getVideoInfoTag()
                        video_info_tag.setPlot(movie_data['description'])
                    except Exception as e:
                        self.logger.error("Failed to set plot via InfoTagVideo for movie '%s': %s", movie_data.get('title'), e)
                        list_item.setInfo('video', {'plot': movie_data['description']})
                else:
                    list_item.setInfo('video', {'plot': movie_data['description']})

            # Add to directory
            xbmcplugin.addDirectoryItem(
                handle=addon_handle, url=url, listitem=list_item, isFolder=False
            )
        else:
            # Log error if list_item creation failed
            movie_title = movie_data.get('title', 'Unknown')
            self.logger.error("MOVIE MENU: Failed to create list item for movie '%s' - skipping", movie_title)

    def create_menu_item(self, label: str, action: str, description: Optional[str] = None, icon: Optional[str] = None, **params) -> Tuple[str, xbmcgui.ListItem]:
        """Create a menu item with URL and ListItem"""
        try:
            kodi_major = get_kodi_major_version()
            self.logger.info("MENU BUILDER: Creating menu item '%s' (action=%s) on Kodi v%s", label, action, kodi_major)

            # Add stack trace to identify caller
            import traceback
            stack_info = traceback.extract_stack()
            caller_info = stack_info[-2] if len(stack_info) > 1 else "unknown"
            self.logger.info("MENU BUILDER CALLER: %s:%s in %s", caller_info.filename, caller_info.lineno, caller_info.name)

            # Build URL
            url_params = [f"action={action}"]
            for key, value in params.items():
                if value is not None:
                    url_params.append(f"{key}={value}")
            url = f"{self.base_url}?{'&'.join(url_params)}"

            # Create ListItem using renderer's method
            self.logger.info("MENU BUILDER: Calling renderer.create_simple_listitem for '%s'", label)
            list_item = self.renderer.create_simple_listitem(label, description, action, icon)

            # Set metadata based on Kodi version to avoid deprecation warnings
            if list_item is not None:
                if kodi_major >= 20:
                    # Kodi v20+ (Nexus/Omega): Use InfoTagVideo
                    try:
                        video_info_tag = list_item.getVideoInfoTag()
                        video_info_tag.setTitle(label)
                        video_info_tag.setPlot(description)
                        if params.get('content_type'):
                            video_info_tag.setGenres([params.get('content_type')])
                    except Exception as e:
                        self.logger.error("Failed to set metadata via InfoTagVideo for menu item '%s': %s", label, e)
                        # Fallback to setInfo for compatibility
                        list_item.setInfo('video', {
                            'title': label,
                            'plot': description,
                            'genre': params.get('content_type', '')
                        })
                else:
                    # Kodi v19 (Matrix): Use setInfo
                    list_item.setInfo('video', {
                        'title': label,
                        'plot': description,
                        'genre': params.get('content_type', '')
                    })

            self.logger.info("MENU BUILDER: Successfully created menu item '%s' -> %s", label, url)
            return url, list_item

        except Exception as e:
            self.logger.error("MENU BUILDER: Failed to create menu item '%s': %s", label, e)
            # Return fallback
            return f"{self.base_url}?action={action}", xbmcgui.ListItem(label=label)