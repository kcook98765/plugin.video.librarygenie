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
        self.renderer = get_listitem_renderer(string_getter)

    def build_menu(self, items, addon_handle, base_url):
        """Build a directory menu from items"""
        self.logger.debug(f"Building menu with {len(items)} items")

        for item in items:
            self._add_directory_item(item, addon_handle, base_url)

        xbmcplugin.endOfDirectory(addon_handle)

    def _add_directory_item(self, item, addon_handle, base_url):
        """Add a single directory item with context menu support"""
        title = item.get("title", "Unknown")
        action = item.get("action", "")
        description = item.get("description", "")
        is_folder = item.get("is_folder", True)
        context_menu = item.get("context_menu", [])

        # Build URL with parameters
        params = {"action": action}
        for key, value in item.items():
            if key not in ["title", "description", "action", "is_folder", "context_menu"]:
                params[key] = value

        url = f"{base_url}?{urlencode(params)}" if action else ""

        # Create list item - check if this is a movie item for enhanced rendering
        if item.get("movie_data"):
            # Use Phase 11 renderer for movie items
            list_item = self.renderer.create_movie_listitem(item["movie_data"], base_url, action)
        else:
            # Use simple renderer for menu items
            list_item = self.renderer.create_simple_listitem(title, description, action, icon=item.get("icon"))
        
        # Add context menu if provided
        if context_menu:
            list_item.addContextMenuItems(context_menu)
        
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
            except ImportError:
                pass
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
            except ImportError:
                pass

        # Add to directory
        xbmcplugin.addDirectoryItem(
            handle=addon_handle, url=url, listitem=list_item, isFolder=is_folder
        )
    
    def build_movie_menu(self, movies: List[Dict[str, Any]], addon_handle, base_url, **options):
        """Build a menu specifically for movie items with enhanced ListItems"""
        self.logger.debug(f"Building movie menu with {len(movies)} movies")
        
        if not KODI_AVAILABLE:
            self.logger.info("Movie menu items (stub mode):")
            for movie in movies:
                self.logger.info(f"  - {movie.get('title', 'Unknown')}")
            return
        
        # Set content type for better skin support
        xbmcplugin.setContent(addon_handle, 'movies')
        
        # Add sort methods for movie lists
        sort_methods = [
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
            xbmcplugin.SORT_METHOD_YEAR,
            xbmcplugin.SORT_METHOD_VIDEO_RATING,
            xbmcplugin.SORT_METHOD_DATE_ADDED,
            xbmcplugin.SORT_METHOD_VIDEO_RUNTIME
        ]
        
        for method in sort_methods:
            xbmcplugin.addSortMethod(addon_handle, method)
        
        # Build movie items
        for movie in movies:
            self._add_movie_item(movie, addon_handle, base_url, **options)
        
        # Set view mode if specified
        view_mode = options.get('view_mode')
        if view_mode:
            xbmcplugin.setPluginCategory(addon_handle, options.get('category', 'Movies'))
        
        xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)
    
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
        if extra_context and KODI_AVAILABLE:
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
