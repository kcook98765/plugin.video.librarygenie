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

from ..utils.logger import get_logger
from ..utils.kodi_version import get_kodi_major_version
from .listitem_renderer import get_listitem_renderer
from .localization import L


class MenuBuilder:
    """Builds menus and directory listings for Kodi with Phase 11 enhancements"""

    def __init__(self, string_getter: Optional[Callable[[int], str]] = None):
        self.logger = get_logger(__name__)
        self.renderer = get_listitem_renderer()

    def build_menu(self, items, addon_handle, base_url, breadcrumb_path=None):
        """Build a directory menu from items with optional breadcrumb"""
        self.logger.debug(f"MENU BUILD: Starting build_menu with {len(items)} items")
        self.logger.debug(f"MENU BUILD: addon_handle={addon_handle}, base_url='{base_url}', breadcrumb='{breadcrumb_path}'")

        successful_items = 0
        failed_items = 0

        # Show breadcrumb notification for non-root views
        self._show_breadcrumb_if_needed(breadcrumb_path)

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

        self.logger.debug(f"MENU BUILD: Added {successful_items} menu items successfully, {failed_movies} failed")
        self.logger.debug(f"MENU BUILD: Calling endOfDirectory(handle={addon_handle}, cacheToDisc=True)")
        xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
        self.logger.debug("MENU BUILD: Completed endOfDirectory for menu with caching enabled")

    def _add_directory_item(self, item, addon_handle, base_url):
        """Add a single directory item with context menu support"""
        title = item.get("label", item.get("title", "Unknown"))
        action = item.get("action", "")
        description = item.get("description", "")
        is_folder = item.get("is_folder", True)
        context_menu = item.get("context_menu", [])

        self.logger.debug(f"MENU ITEM: Processing '{title}' - action='{action}', is_folder={is_folder}")

        # Log all item properties for debugging
        item_keys = list(item.keys())
        self.logger.debug(f"MENU ITEM: Available properties for '{title}': {item_keys}")

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

            # Ensure non-folder action items are not marked as playable to prevent info dialog
            if not is_folder and action and list_item is not None:
                list_item.setProperty('IsPlayable', 'false')

        # Check if list_item was created successfully
        if list_item is None:
            self.logger.error(f"MENU ITEM: Failed to create list item for '{title}' - skipping")
            return

        # Add context menu if provided
        context_items_added = 0
        if context_menu and list_item is not None:
            list_item.addContextMenuItems(context_menu)
            context_items_added = len(context_menu)
            self.logger.debug(f"MENU ITEM: Added {context_items_added} base context menu items for '{title}'")

        # Context menus now handled globally via addon.xml and context.py

        if context_items_added > 0:
            self.logger.debug(f"MENU ITEM: Total context menu items for '{title}': {context_items_added}")

        # Add to directory
        xbmcplugin.addDirectoryItem(
            handle=addon_handle, url=url, listitem=list_item, isFolder=is_folder
        )
        self.logger.debug(f"MENU ITEM: Successfully added '{title}' to directory")

    def _add_breadcrumb_item(self, breadcrumb_path: str, addon_handle: int, base_url: str):
        """Add breadcrumb item at top of directory"""
        try:
            kodi_major = get_kodi_major_version()
            self.logger.info(f"BREADCRUMB: Adding breadcrumb '{breadcrumb_path}' on Kodi v{kodi_major}")

            # Add stack trace to identify caller
            import traceback
            stack_info = traceback.extract_stack()
            caller_info = stack_info[-2] if len(stack_info) > 1 else "unknown"
            self.logger.info(f"BREADCRUMB CALLER: {caller_info.filename}:{caller_info.lineno} in {caller_info.name}")

            breadcrumb_item = xbmcgui.ListItem(label=f"[COLOR gray]📍 {breadcrumb_path}[/COLOR]")

            # Version-specific metadata setting
            if kodi_major >= 20:
                try:
                    self.logger.info(f"BREADCRUMB v{kodi_major}: Using InfoTagVideo for breadcrumb")
                    video_info_tag = breadcrumb_item.getVideoInfoTag()
                    video_info_tag.setPlot('Current location')
                    self.logger.info(f"BREADCRUMB v{kodi_major}: Successfully set metadata via InfoTagVideo")
                except Exception as e:
                    self.logger.error(f"BREADCRUMB v{kodi_major}: InfoTagVideo FAILED: {e}")
            else:
                self.logger.info(f"BREADCRUMB v{kodi_major}: Using setInfo() for breadcrumb")
                breadcrumb_item.setInfo('video', {'plot': 'Current location'})
                self.logger.info(f"BREADCRUMB v{kodi_major}: Successfully set metadata via setInfo")

            breadcrumb_item.setArt({'icon': "DefaultFolder.png", 'thumb': "DefaultFolder.png"})

            # Add as non-clickable item (no URL)
            xbmcplugin.addDirectoryItem(
                addon_handle,
                f"{base_url}?action=noop",  # No-op action
                breadcrumb_item,
                False
            )
            self.logger.info(f"BREADCRUMB: Successfully added breadcrumb item")

        except Exception as e:
            self.logger.error(f"BREADCRUMB: Failed to add breadcrumb item: {e}")

    def _show_breadcrumb_if_needed(self, breadcrumb_path: str):
        """Show breadcrumb notification for non-root views"""
        if breadcrumb_path and breadcrumb_path.strip():
            try:
                self.logger.debug(f"BREADCRUMB: Showing notification for '{breadcrumb_path}'")
                xbmcgui.Dialog().notification("Navigation", breadcrumb_path, xbmcgui.NOTIFICATION_INFO, 3000)
                self.logger.debug("BREADCRUMB: Successfully displayed breadcrumb notification")
            except Exception as e:
                self.logger.error(f"BREADCRUMB: Failed to display breadcrumb notification: {e}")

    def _add_breadcrumb_notification(self, breadcrumb_path: str):
        """Show breadcrumb as a notification"""
        try:
            self.logger.debug(f"BREADCRUMB NOTIFICATION: Displaying breadcrumb '{breadcrumb_path}'")
            xbmcgui.Dialog().notification("Navigation", breadcrumb_path, xbmcgui.NOTIFICATION_INFO, 3000)
            self.logger.debug("BREADCRUMB NOTIFICATION: Successfully displayed breadcrumb notification")
        except Exception as e:
            self.logger.error(f"BREADCRUMB NOTIFICATION: Failed to display breadcrumb notification: {e}")


    def build_movie_menu(self, movies: List[Dict[str, Any]], addon_handle, base_url, **options):
        """Build a menu specifically for movie items with enhanced ListItems"""
        self.logger.debug(f"MOVIE MENU: Starting build_movie_menu with {len(movies)} movies")
        self.logger.debug(f"MOVIE MENU: addon_handle={addon_handle}, base_url='{base_url}', options={list(options.keys())}")

        # Set content type for better skin support
        self.logger.debug(f"MOVIE MENU: Setting content type 'movies' for handle {addon_handle}")
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

        self.logger.debug(f"MOVIE MENU: Added {successful_movies} movies successfully, {failed_movies} failed")

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

            # Add to directory
            xbmcplugin.addDirectoryItem(
                handle=addon_handle, url=url, listitem=list_item, isFolder=False
            )
        else:
            # Log error if list_item creation failed
            movie_title = movie_data.get('title', 'Unknown')
            self.logger.error(f"MOVIE MENU: Failed to create list item for movie '{movie_title}' - skipping")

    def create_menu_item(self, label: str, action: str, description: Optional[str] = None, icon: Optional[str] = None, **params) -> Tuple[str, xbmcgui.ListItem]:
        """Create a menu item with URL and ListItem"""
        try:
            kodi_major = get_kodi_major_version()
            self.logger.info(f"MENU BUILDER: Creating menu item '{label}' (action={action}) on Kodi v{kodi_major}")

            # Add stack trace to identify caller
            import traceback
            stack_info = traceback.extract_stack()
            caller_info = stack_info[-2] if len(stack_info) > 1 else "unknown"
            self.logger.info(f"MENU BUILDER CALLER: {caller_info.filename}:{caller_info.lineno} in {caller_info.name}")

            # Build URL
            url_params = [f"action={action}"]
            for key, value in params.items():
                if value is not None:
                    url_params.append(f"{key}={value}")
            url = f"{self.base_url}?{'&'.join(url_params)}"

            # Create ListItem using renderer's method
            self.logger.info(f"MENU BUILDER: Calling renderer.create_simple_listitem for '{label}'")
            list_item = self.renderer.create_simple_listitem(label, description, action, icon)

            # Set metadata based on Kodi version to avoid deprecation warnings
            if kodi_major >= 20:
                # Kodi v20+ (Nexus/Omega): Use InfoTagVideo
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(label)
                    video_info_tag.setPlot(description)
                    if params.get('content_type'):
                        video_info_tag.setGenres([params.get('content_type')])
                except Exception as e:
                    self.logger.error(f"Failed to set metadata via InfoTagVideo: {e}")
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

            self.logger.info(f"MENU BUILDER: Successfully created menu item '{label}' -> {url}")
            return url, list_item

        except Exception as e:
            self.logger.error(f"MENU BUILDER: Failed to create menu item '{label}': {e}")
            # Return fallback
            return f"{self.base_url}?action={action}", xbmcgui.ListItem(label=label)