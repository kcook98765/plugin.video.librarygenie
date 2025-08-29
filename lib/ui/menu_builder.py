#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Menu Builder
Builds Kodi directory listings and menus
"""

from urllib.parse import urlencode
from typing import List, Dict, Any, Optional, Callable

import xbmcgui
import xbmcplugin

from ..utils.logger import get_logger
from .listitem_renderer import get_listitem_renderer


class MenuBuilder:
    """Builds menus and directory listings for Kodi with Phase 11 enhancements"""

    def __init__(self, string_getter: Optional[Callable[[int], str]] = None):
        self.logger = get_logger(__name__)
        self.renderer = get_listitem_renderer()

    def build_menu(self, items, addon_handle, base_url):
        """Build a directory menu from items"""
        self.logger.info(f"MENU BUILD: Starting build_menu with {len(items)} items")
        self.logger.debug(f"MENU BUILD: addon_handle={addon_handle}, base_url='{base_url}'")

        successful_items = 0
        failed_items = 0

        for idx, item in enumerate(items):
            try:
                item_title = item.get('title', 'Unknown')
                self.logger.debug(f"MENU BUILD: Processing menu item {idx+1}/{len(items)}: '{item_title}'")
                self.logger.debug(f"MENU BUILD: Item {idx+1} data: {item}")
                
                self._add_directory_item(item, addon_handle, base_url)
                successful_items += 1
                self.logger.debug(f"MENU BUILD: Successfully added menu item {idx+1}: '{item_title}'")
            except Exception as e:
                failed_items += 1
                self.logger.error(f"MENU BUILD: Failed to add menu item {idx+1}: {e}")

        self.logger.info(f"MENU BUILD: Added {successful_items} menu items successfully, {failed_items} failed")
        self.logger.debug(f"MENU BUILD: Calling endOfDirectory(handle={addon_handle})")
        xbmcplugin.endOfDirectory(addon_handle)
        self.logger.debug(f"MENU BUILD: Completed endOfDirectory for menu")

    def _add_directory_item(self, item, addon_handle, base_url):
        """Add a single directory item with context menu support"""
        title = item.get("title", "Unknown")
        action = item.get("action", "")
        description = item.get("description", "")
        is_folder = item.get("is_folder", True)
        context_menu = item.get("context_menu", [])

        self.logger.debug(f"MENU ITEM: Processing '{title}' - action='{action}', is_folder={is_folder}")
        
        # Log all item properties for debugging
        item_keys = list(item.keys())
        self.logger.debug(f"MENU ITEM: Available properties for '{title}': {item_keys}")

        # Build URL with parameters
        params = {"action": action}
        excluded_keys = ["title", "description", "action", "is_folder", "context_menu", "movie_data"]
        
        param_keys = []
        for key, value in item.items():
            if key not in excluded_keys:
                params[key] = value
                param_keys.append(key)

        url = f"{base_url}?{urlencode(params)}" if action else ""
        self.logger.debug(f"MENU ITEM: Built URL for '{title}': '{url}'")
        if param_keys:
            self.logger.debug(f"MENU ITEM: Added URL parameters for '{title}': {param_keys}")

        # Create list item - check if this is a movie item for enhanced rendering
        if item.get("movie_data"):
            # Use Phase 11 renderer for movie items
            self.logger.debug(f"MENU ITEM: Using movie renderer for '{title}' with movie_data")
            list_item = self.renderer.create_movie_listitem(item["movie_data"], base_url, action)
        else:
            # Use simple renderer for menu items
            self.logger.debug(f"MENU ITEM: Using simple renderer for '{title}'")
            list_item = self.renderer.create_simple_listitem(title, description, action, icon=item.get("icon"))

        # Add context menu if provided
        context_items_added = 0
        if context_menu:
            list_item.addContextMenuItems(context_menu)
            context_items_added += len(context_menu)
            self.logger.debug(f"MENU ITEM: Added {len(context_menu)} base context menu items for '{title}'")

        # Add context menu based on item type
        if item.get("context_menu_type") == "library_item" and item.get("library_movie_id"):
            try:
                from .context_menu import get_context_menu_manager
                # Dummy string getter for menu builder
                def get_string(string_id):
                    strings = {
                        31000: "Add to List...",
                        31001: "Quick Add to Default"
                    }
                    return strings.get(string_id, f"String {string_id}")

                context_manager = get_context_menu_manager(get_string)
                list_item = context_manager.add_library_item_context_menu(
                    list_item, item["library_movie_id"]
                )
                self.logger.debug(f"MENU ITEM: Added library item context menu for '{title}' (movie_id: {item['library_movie_id']})")
                context_items_added += 2  # Approximate
            except ImportError:
                self.logger.warning(f"MENU ITEM: Failed to import context_menu for library item '{title}'")
        elif item.get("context_menu_type") == "list_item" and item.get("list_id") and item.get("list_item_id"):
            try:
                from .context_menu import get_context_menu_manager
                # Dummy string getter for menu builder
                def get_string(string_id):
                    strings = {
                        31010: "Remove from List",
                        31011: "Move to Another List..."
                    }
                    return strings.get(string_id, f"String {string_id}")

                context_manager = get_context_menu_manager(get_string)
                list_item = context_manager.add_list_item_context_menu(
                    list_item, item["list_id"], item["list_item_id"]
                )
                self.logger.debug(f"MENU ITEM: Added list item context menu for '{title}' (list_id: {item['list_id']}, item_id: {item['list_item_id']})")
                context_items_added += 2  # Approximate
            except ImportError:
                self.logger.warning(f"MENU ITEM: Failed to import context_menu for list item '{title}'")

        if context_items_added > 0:
            self.logger.debug(f"MENU ITEM: Total context menu items for '{title}': ~{context_items_added}")

        # Add to directory
        xbmcplugin.addDirectoryItem(
            handle=addon_handle, url=url, listitem=list_item, isFolder=is_folder
        )
        self.logger.debug(f"MENU ITEM: Successfully added '{title}' to directory")

    def build_movie_menu(self, movies: List[Dict[str, Any]], addon_handle, base_url, **options):
        """Build a menu specifically for movie items with enhanced ListItems"""
        self.logger.info(f"MOVIE MENU: Starting build_movie_menu with {len(movies)} movies")
        self.logger.debug(f"MOVIE MENU: addon_handle={addon_handle}, base_url='{base_url}', options={list(options.keys())}")

        # Set content type for better skin support
        self.logger.debug(f"MOVIE MENU: Setting content type 'movies' for handle {addon_handle}")
        xbmcplugin.setContent(addon_handle, 'movies')
        self.logger.debug("MOVIE MENU: Successfully set content type to 'movies'")

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
            self.logger.debug(f"MOVIE MENU: Added sort method {method_name}")

        # Build movie items
        successful_movies = 0
        failed_movies = 0
        
        for idx, movie in enumerate(movies):
            try:
                self.logger.debug(f"MOVIE MENU: Processing movie {idx+1}/{len(movies)}: '{movie.get('title', 'Unknown')}'")
                self._add_movie_item(movie, addon_handle, base_url, **options)
                successful_movies += 1
            except Exception as e:
                failed_movies += 1
                self.logger.error(f"MOVIE MENU: Failed to add movie {idx+1}: {e}")

        self.logger.info(f"MOVIE MENU: Added {successful_movies} movies successfully, {failed_movies} failed")

        # Set view mode if specified
        view_mode = options.get('view_mode')
        category = options.get('category', 'Movies')
        if view_mode:
            xbmcplugin.setPluginCategory(addon_handle, category)
            self.logger.debug(f"MOVIE MENU: Set plugin category to '{category}' with view_mode '{view_mode}'")
        else:
            self.logger.debug(f"MOVIE MENU: No view_mode specified, using default category '{category}'")

        xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)
        self.logger.info("MOVIE MENU: Completed movie menu build with caching enabled")

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
        if extra_context:
            current_context = list_item.getProperty('ContextMenuItems') or []
            if isinstance(current_context, str):
                current_context = [current_context]
            current_context.extend(extra_context)
            list_item.addContextMenuItems(current_context)

        # Set as playable item
        list_item.setProperty('IsPlayable', 'true')

        # Add to directory
        xbmcplugin.addDirectoryItem(
            handle=addon_handle, url=url, listitem=list_item, isFolder=False
        )