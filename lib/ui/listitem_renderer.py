#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Renderer
Renders list items with proper Kodi integration
"""

from typing import List, Dict, Any, Optional
import xbmcgui
import xbmcplugin
import xbmcvfs
from lib.utils.kodi_log import get_kodi_logger
from lib.ui.localization import L
from lib.utils.kodi_version import get_kodi_major_version, is_kodi_v21_plus


class ListItemRenderer:
    """Renders ListItems with proper Kodi integration"""

    def __init__(self, addon_handle: int, addon_id: str, context=None):
        """Initialize ListItemRenderer - now with lazy loading for low-power device optimization"""
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_kodi_logger('lib.ui.listitem_renderer')
        self.plugin_context = context
        self.query_manager = context.query_manager if context else None
        
        # Cache addon instance and resources base path for efficient resource access
        import os
        import xbmcaddon
        self._addon = xbmcaddon.Addon(self.addon_id)
        self._resources_base = xbmcvfs.translatePath(
            os.path.join(self._addon.getAddonInfo('path'), 'resources')
        )
        
        # Heavy components now lazy loaded via properties for performance optimization

    @property
    def builder(self):
        """Lazy load ListItemBuilder only when needed"""
        if not hasattr(self, '_builder'):
            self.logger.debug("LAZY LOAD: Loading ListItemBuilder on first use")
            from lib.ui.listitem_builder import ListItemBuilder
            self._builder = ListItemBuilder(self.addon_handle, self.addon_id, self.plugin_context)
        return self._builder
    
    @property
    def listitem_builder(self):
        """Alias for compatibility - also lazy loaded"""
        return self.builder
    
    @property
    def metadata_manager(self):
        """Lazy load ListItemMetadataManager only when needed"""
        if not hasattr(self, '_metadata_manager'):
            self.logger.debug("LAZY LOAD: Loading ListItemMetadataManager on first use")
            from lib.utils.listitem_utils import ListItemMetadataManager
            self._metadata_manager = ListItemMetadataManager(self.addon_id)
        return self._metadata_manager

    @property
    def art_manager(self):
        """Lazy load ListItemArtManager only when needed"""
        if not hasattr(self, '_art_manager'):
            self.logger.debug("LAZY LOAD: Loading ListItemArtManager on first use")
            from lib.utils.listitem_utils import ListItemArtManager
            self._art_manager = ListItemArtManager(self.addon_id)
        return self._art_manager

    @property
    def context_menu_builder(self):
        """Lazy load ContextMenuBuilder only when needed"""
        if not hasattr(self, '_context_menu_builder'):
            self.logger.debug("LAZY LOAD: Loading ContextMenuBuilder on first use")
            from lib.utils.listitem_utils import ContextMenuBuilder
            self._context_menu_builder = ContextMenuBuilder(self.addon_id)
        return self._context_menu_builder

    def _translate_path(self, path: str) -> str:
        """Translate path using Kodi V19+ API"""
        return xbmcvfs.translatePath(path)

    def _resource_path(self, name: str) -> str:
        """Get absolute path to addon resource (cached for efficiency)"""
        import os
        return os.path.join(self._resources_base, name)

    def _apply_art(self, list_item: xbmcgui.ListItem, kind: str):
        """Apply version-aware art based on folder type - CONSOLIDATED"""        
        self.art_manager.apply_type_specific_art(list_item, kind, self._resource_path)

    def render_lists(self, lists: List[Dict[str, Any]], folder_id: Optional[int] = None) -> bool:
        """
        Render lists as directory items

        Args:
            lists: List of list dictionaries
            folder_id: Parent folder ID if any

        Returns:
            bool: Success status
        """
        try:
            self.logger.info("RENDER LISTS: Starting render of %s lists (folder_id=%s)", len(lists), folder_id)

            # Set content type for lists
            self.logger.debug("RENDER LISTS: Setting content type 'files' for handle %s", self.addon_handle)
            xbmcplugin.setContent(self.addon_handle, "files")

            # OPTIMIZED: Prepare items for batch rendering
            batch_items = []
            success_count = 0
            for idx, list_data in enumerate(lists, start=1):
                try:
                    list_name = list_data.get('name', 'Unknown List')
                    list_id = list_data.get('id')

                    self.logger.debug("RENDER LISTS: Processing list #%s/%s: '%s' (id=%s)", idx, len(lists), list_name, list_id)

                    list_item = self._build_list_item(list_data)
                    if list_item:
                        url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"
                        self.logger.debug("RENDER LISTS: Built list item for '%s' - URL: '%s'", list_name, url)

                        batch_items.append((url, list_item, True))
                        success_count += 1
                        self.logger.debug("RENDER LISTS: Successfully prepared list #%s '%s' for batch", idx, list_name)
                    else:
                        self.logger.warning("RENDER LISTS: Failed to build list item for '%s'", list_name)
                except Exception as e:
                    self.logger.error("RENDER LISTS: Error processing list #%s: %s", idx, e)

            # OPTIMIZED: Add all items in a single batch operation
            if batch_items:
                self.logger.debug("RENDER LISTS: Adding %s lists to directory in batch", len(batch_items))
                xbmcplugin.addDirectoryItems(self.addon_handle, batch_items)

            self.logger.info("RENDER LISTS: Successfully added %s/%s lists to directory", success_count, len(lists))
            self.logger.debug("RENDER LISTS: Calling endOfDirectory(handle=%s, cacheToDisc=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
            return True

        except Exception as e:
            self.logger.error("RENDER LISTS: Failed to render lists: %s", e)
            self.logger.debug("RENDER LISTS: Calling endOfDirectory(handle=%s, succeeded=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=True, cacheToDisc=False)
            return False

    def render_media_items(self, items: List[Dict[str, Any]], content_type: str = "movies", context_menu_callback=None) -> bool:
        """
        Render media items using the unified ListItemBuilder

        Args:
            items: List of media item dictionaries
            content_type: Content type for Kodi ("movies", "episodes", etc.)
            context_menu_callback: Optional callback to add custom context menu items

        Returns:
            bool: Success status
        """
        try:
            self.logger.info("RENDERER: Starting render_media_items with %s items (content_type='%s')", len(items), content_type)
            if context_menu_callback:
                self.logger.info("RENDERER: Context menu callback provided - will apply to each item")

            # Use the lazy-loaded ListItemBuilder to handle the rendering
            builder = self.builder
            success = builder.build_directory(items, content_type)

            if success:
                self.logger.info("RENDERER: Successfully rendered %s items", len(items))
            else:
                self.logger.error("RENDERER: Failed to render items")

            return success

        except Exception as e:
            self.logger.error("RENDERER: Error rendering media items: %s", e)
            import traceback
            self.logger.error("RENDERER: Traceback: %s", traceback.format_exc())
            return False


    def render_folders(self, folders: List[Dict[str, Any]], parent_id: Optional[int] = None) -> bool:
        """
        Render folders as directory items

        Args:
            folders: List of folder dictionaries
            parent_id: Parent folder ID if any

        Returns:
            bool: Success status
        """
        try:
            # Set content type for folders
            xbmcplugin.setContent(self.addon_handle, "files")

            # OPTIMIZED: Prepare items for batch rendering
            batch_items = []
            for folder_data in folders:
                list_item = self._build_folder_item(folder_data)
                if list_item:
                    folder_id = folder_data['id']
                    url = f"plugin://{self.addon_id}/?action=show_folder&folder_id={folder_id}"
                    batch_items.append((url, list_item, True))

            # OPTIMIZED: Add all items in a single batch operation
            if batch_items:
                xbmcplugin.addDirectoryItems(self.addon_handle, batch_items)

            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
            return True

        except Exception as e:
            self.logger.error("Failed to render folders: %s", e)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=True, cacheToDisc=False)
            return False

    def _build_list_item(self, list_data: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Build ListItem for a user list"""
        try:
            name = list_data.get('name', 'Unnamed List')
            list_item = xbmcgui.ListItem(label=name, offscreen=True)

            # Set basic info - CONSOLIDATED
            self.metadata_manager.set_basic_metadata(list_item, name, f"User list: {name}", "list")

            # Set list playlist icon
            self._apply_art(list_item, 'list')

            # Add context menu
            self._set_list_context_menu(list_item, list_data)

            return list_item

        except Exception as e:
            self.logger.error("Failed to build list item: %s", e)
            return None

    def _build_folder_item(self, folder_data: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Build ListItem for a folder"""
        try:
            name = folder_data.get('name', 'Unnamed Folder')
            list_item = xbmcgui.ListItem(label=name, offscreen=True)

            # Set basic info - CONSOLIDATED
            self.metadata_manager.set_basic_metadata(list_item, name, f"Folder: {name}", "folder")

            # Set folder icon
            self._apply_art(list_item, 'folder')

            # Add context menu
            self._set_folder_context_menu(list_item, folder_data)

            return list_item

        except Exception as e:
            self.logger.error("Failed to build folder item: %s", e)
            return None

    def _set_list_context_menu(self, list_item: xbmcgui.ListItem, list_data: Dict[str, Any]):
        """Set context menu for list items - CONSOLIDATED"""
        list_id = list_data.get('id', '')
        context_items = self.context_menu_builder.build_context_menu(list_id, 'list')
        list_item.addContextMenuItems(context_items)

    def _set_folder_context_menu(self, list_item: xbmcgui.ListItem, folder_data: Dict[str, Any]):
        """Set context menu for folder items - CONSOLIDATED"""
        folder_id = folder_data.get('id', '')
        folder_name = folder_data.get('name', '')
        # Check if this is a protected folder (currently only "Search History")
        is_protected = folder_name == "Search History"
        context_items = self.context_menu_builder.build_context_menu(folder_id, 'folder', folder_name, is_protected)
        list_item.addContextMenuItems(context_items)

    def create_simple_listitem(self, title: str, description: Optional[str] = None, action: Optional[str] = None, icon: Optional[str] = None) -> xbmcgui.ListItem:
        """Create a simple ListItem for menu items (compatibility method for MenuBuilder) - CONSOLIDATED"""
        from lib.utils.listitem_utils import create_simple_listitem
        return create_simple_listitem(title, description, self.addon_id, False, icon)

    def create_movie_listitem(self, item: Dict[str, Any], base_url: str, action: str) -> Optional[xbmcgui.ListItem]:
        """Create a rich ListItem for a movie with proper metadata and artwork"""
        try:
            # Use the new builder methods that return (url, listitem, is_folder)
            kodi_id = item.get('kodi_id')
            media_type = item.get('media_type', 'movie')

            # Determine if this is a library item
            if media_type in ('movie', 'episode') and isinstance(kodi_id, int):
                result = self.builder._create_library_listitem(item)
            else:
                result = self.builder._create_external_item(item)

            if result:
                url, list_item, is_folder = result
                return list_item
            else:
                return None

        except Exception as e:
            self.logger.error("Failed to create movie listitem: %s", e)
            return None

    def _create_episode_listitem(self, episode_data: Dict[str, Any]) -> xbmcgui.ListItem:
        """Create an episode ListItem"""
        try:
            # Use the new builder method that returns (url, listitem, is_folder)
            result = self.builder._create_library_listitem(episode_data)
            if result:
                url, list_item, is_folder = result
                return list_item
            else:
                # Fallback to simple listitem
                title = episode_data.get('title', episode_data.get('label', 'Unknown'))
                return self.create_simple_listitem(title)
        except Exception as e:
            self.logger.error("Failed to create episode listitem: %s", e)
            # Fallback to simple listitem
            title = episode_data.get('title', episode_data.get('label', 'Unknown'))
            return self.create_simple_listitem(title)

    def render_directory(self, items: List[Dict[str, Any]], content_type: str = "movies") -> bool:
        """
        Render a complete directory with proper container hygiene (Step 7).
        Sets content type and sort methods once per build, ensures non-empty URLs.

        Args:
            items: List of media item dictionaries
            content_type: "movies", "tvshows", or "episodes"

        Returns:
            bool: Success status
        """
        try:
            # Container hygiene - set content type appropriately for skin layouts/overlays
            self.logger.debug("RENDERER DIRECTORY: Starting render of %s items with content_type='%s'", len(items), content_type)
            self.logger.debug("RENDERER DIRECTORY: Setting content type '%s' for handle %s", content_type, self.addon_handle)
            xbmcplugin.setContent(self.addon_handle, content_type)

            # Add sort methods once per build (not per item)
            sort_methods = [
                ("SORT_METHOD_TITLE_IGNORE_THE", xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE),
                ("SORT_METHOD_VIDEO_YEAR", xbmcplugin.SORT_METHOD_VIDEO_YEAR),
                ("SORT_METHOD_DATE", xbmcplugin.SORT_METHOD_DATE)
            ]
            self.logger.debug("RENDERER DIRECTORY: Adding %s sort methods", len(sort_methods))
            for method_name, method in sort_methods:
                xbmcplugin.addSortMethod(self.addon_handle, method)
                self.logger.debug("RENDERER DIRECTORY: Added sort method %s", method_name)

            # OPTIMIZED: Build all items for batch rendering
            batch_items = []
            success_count = 0
            for idx, item in enumerate(items, start=1):
                try:
                    title = item.get('title', 'Unknown')
                    self.logger.debug("RENDERER DIRECTORY: Processing item #%s/%s: '%s'", idx, len(items), title)

                    result = self.builder._build_single_item(item)
                    if result:
                        url, listitem, is_folder = result
                        # Ensure non-empty URL to avoid directory errors
                        if url and url.strip():
                            self.logger.debug("RENDERER DIRECTORY: Preparing item #%s '%s' - URL: '%s', isFolder: %s", idx, title, url, is_folder)
                            batch_items.append((url, listitem, is_folder))
                            success_count += 1
                        else:
                            self.logger.warning("RENDERER DIRECTORY: Skipping item #%s with empty URL: '%s'", idx, title)
                    else:
                        self.logger.warning("RENDERER DIRECTORY: Failed to build item #%s: '%s'", idx, title)
                except Exception as e:
                    self.logger.error("RENDERER DIRECTORY: Error building item #%s '%s': %s", idx, item.get('title', 'Unknown'), e)

            # OPTIMIZED: Add all items in a single batch operation
            if batch_items:
                self.logger.debug("RENDERER DIRECTORY: Adding %s items to directory in batch", len(batch_items))
                xbmcplugin.addDirectoryItems(self.addon_handle, batch_items)

            self.logger.debug("RENDERER DIRECTORY: Successfully added %s/%s items to directory", success_count, len(items))
            self.logger.debug("RENDERER DIRECTORY: Calling endOfDirectory(handle=%s, succeeded=True, cacheToDisc=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
            return True

        except Exception as e:
            self.logger.error("RENDERER DIRECTORY: Fatal error in render_directory: %s", e)
            self.logger.debug("RENDERER DIRECTORY: Calling endOfDirectory(handle=%s, succeeded=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=True, cacheToDisc=False)
            return False

    def render_list_items(self, list_id: int, sort_method: Optional[str] = None) -> None:
        """Render items in a list with optimized performance using media_items data"""
        try:
            # Get list metadata
            if not self.query_manager:
                self.logger.error("Query manager not available")
                return
            list_info = self.query_manager.get_list_by_id(list_id)
            if not list_info:
                self.logger.error("List not found: %s", list_id)
                return

            # Get list items with enhanced media data - no JSON RPC calls needed
            items = self.query_manager.get_list_items_with_media(list_id, sort_method)

            if not items:
                # Show empty list message
                xbmcplugin.addDirectoryItem(
                    handle=self.addon_handle,
                    url="plugin://plugin.video.librarygenie/?action=empty",
                    listitem=xbmcgui.ListItem(label="No items in this list", offscreen=True),
                    isFolder=False
                )
                xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True)
                return

            self.logger.debug("Rendering %s list items using media_items data", len(items))

            # OPTIMIZED: Process items efficiently for batch rendering
            batch_items = []
            for item in items:
                try:
                    # Build listitem using enhanced media data from media_items table
                    # This now uses all the fields we gather in the scanner
                    listitem, url = self.listitem_builder.build_media_listitem(item)

                    # Add context menu for list management
                    from typing import List, Tuple
                    label = "Remove from List"
                    cmd = f"RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={list_id}&media_item_id={item['id']})"
                    context_menu: List[Tuple[str, str]] = [(label, cmd)]
                    listitem.addContextMenuItems(context_menu)

                    batch_items.append((url, listitem, False))

                except Exception as e:
                    self.logger.error("Failed to render list item %s: %s", item.get('id', 'unknown'), e)
                    continue

            # OPTIMIZED: Add all items in a single batch operation
            if batch_items:
                self.logger.debug("Adding %s list items to directory in batch", len(batch_items))
                xbmcplugin.addDirectoryItems(self.addon_handle, batch_items)

            # Set content type and finish directory
            xbmcplugin.setContent(self.addon_handle, 'movies')
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)

            self.logger.debug("Successfully rendered %s list items", len(items))

        except Exception as e:
            self.logger.error("Failed to render list items: %s", e)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)


# Context-aware renderer instance cache for performance optimization
_renderer_cache = {}


def get_listitem_renderer(addon_handle: Optional[int] = None, addon_id: Optional[str] = None, context=None):
    """Get renderer instance with context-aware caching for low-power device optimization"""
    # Use provided parameters or get from current context
    if addon_handle is None or addon_id is None:
        import sys
        addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        addon_id = "plugin.video.librarygenie"
    
    # Generate cache key based on context needs - only cache by handle/id for simplicity
    # Context changes are rare and don't need separate instances
    cache_key = f"{addon_handle}_{addon_id}"
    
    if cache_key not in _renderer_cache:
        _renderer_cache[cache_key] = ListItemRenderer(addon_handle, addon_id, context)
    
    return _renderer_cache[cache_key]


def clear_renderer_cache():
    """Clear renderer cache - useful for testing and memory management"""
    global _renderer_cache
    _renderer_cache.clear()