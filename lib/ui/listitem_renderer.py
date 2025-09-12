#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Renderer
Renders list items with proper Kodi integration
"""

from typing import List, Dict, Any, Optional
import xbmcgui
import xbmcplugin
from .listitem_builder import ListItemBuilder
from ..utils.logger import get_logger
from .localization import L
from ..utils.kodi_version import get_kodi_major_version, is_kodi_v21_plus


class ListItemRenderer:
    """Renders ListItems with proper Kodi integration"""

    def __init__(self, addon_handle: int, addon_id: str, context=None):
        """Initialize ListItemRenderer"""
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_logger(__name__)
        self.builder = ListItemBuilder(addon_handle, addon_id, context)

    def _translate_path(self, path: str) -> str:
        """Translate path based on Kodi version"""
        kodi_major = get_kodi_major_version()
        if kodi_major >= 20:
            try:
                import xbmcvfs
                return xbmcvfs.translatePath(path)
            except (ImportError, AttributeError):
                # Fallback for older versions
                import xbmc
                return xbmc.translatePath(path)
        else:
            try:
                import xbmc
                return xbmc.translatePath(path)
            except (ImportError, AttributeError):
                # Last resort fallback
                return path

    def _resource_path(self, name: str) -> str:
        """Get absolute path to addon resource"""
        import os
        import xbmcaddon
        addon = xbmcaddon.Addon(self.addon_id)
        base = addon.getAddonInfo('path')
        return self._translate_path(os.path.join(base, 'resources', name))

    def _apply_art(self, list_item: xbmcgui.ListItem, kind: str):
        """Apply version-aware art based on folder type"""        
        try:
            if kind == 'list':
                # For "List" folders (user lists)
                icon_name = 'list_playlist_icon.png'
                thumb_name = 'list_playlist.jpg'
            else:
                # For "Folder" folders (organizational folders)
                icon_name = 'list_folder_icon.png'
                thumb_name = 'list_folder.jpg'
            
            icon = self._resource_path(icon_name)
            thumb = self._resource_path(thumb_name)
            
            # Apply the art
            list_item.setArt({
                'icon': icon,
                'thumb': thumb
            })
            
        except Exception as e:
            # Fallback if setArt() fails
            self.logger.error("Failed to set custom art for %s: %s", kind, e)
            
            try:
                list_item.setArt({
                    'icon': 'DefaultFolder.png',
                    'thumb': 'DefaultFolder.png'
                })
            except Exception as fallback_error:
                self.logger.error("Even fallback art failed: %s", fallback_error)

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

                        xbmcplugin.addDirectoryItem(
                            handle=self.addon_handle,
                            url=url,
                            listitem=list_item,
                            isFolder=True
                        )
                        success_count += 1
                        self.logger.debug("RENDER LISTS: Successfully added list #%s '%s' to directory", idx, list_name)
                    else:
                        self.logger.warning("RENDER LISTS: Failed to build list item for '%s'", list_name)
                except Exception as e:
                    self.logger.error("RENDER LISTS: Error processing list #%s: %s", idx, e)

            self.logger.info("RENDER LISTS: Successfully added %s/%s lists to directory", success_count, len(lists))
            self.logger.debug("RENDER LISTS: Calling endOfDirectory(handle=%s, cacheToDisc=True)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return True

        except Exception as e:
            self.logger.error("RENDER LISTS: Failed to render lists: %s", e)
            self.logger.debug("RENDER LISTS: Calling endOfDirectory(handle=%s, succeeded=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
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

            # Use the ListItemBuilder to handle the rendering
            builder = ListItemBuilder(self.addon_handle, self.addon_id)
            success = builder.build_directory(items, content_type, context_menu_callback)

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

            for folder_data in folders:
                list_item = self._build_folder_item(folder_data)
                if list_item:
                    folder_id = folder_data['id']
                    url = f"plugin://{self.addon_id}/?action=show_folder&folder_id={folder_id}"

                    xbmcplugin.addDirectoryItem(
                        handle=self.addon_handle,
                        url=url,
                        listitem=list_item,
                        isFolder=True
                    )

            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return True

        except Exception as e:
            self.logger.error("Failed to render folders: %s", e)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return False

    def _build_list_item(self, list_data: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Build ListItem for a user list"""
        try:
            name = list_data.get('name', 'Unnamed List')
            list_item = xbmcgui.ListItem(label=name)

            # Set basic info - version-specific approach
            kodi_major = get_kodi_major_version()
            if kodi_major >= 21:
                # v21+: Use InfoTagVideo ONLY - completely avoid setInfo() to prevent deprecation warnings
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(name)
                    video_info_tag.setPlot(f"User list: {name}")
                    self.logger.debug("LIST ITEM v21+: Set metadata via InfoTagVideo for '%s'", name)
                except Exception as e:
                    self.logger.error("LIST ITEM v21+: InfoTagVideo failed for '%s': %s", name, e)
                    # No fallback to setInfo() on v21+ to avoid deprecation warnings
            elif kodi_major == 20:
                # v20: Try InfoTagVideo first, fallback to setInfo() if needed
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(name)
                    video_info_tag.setPlot(f"User list: {name}")
                    self.logger.debug("LIST ITEM v20: Set metadata via InfoTagVideo for '%s'", name)
                except Exception as e:
                    self.logger.warning("LIST ITEM v20: InfoTagVideo failed for '%s': %s, falling back to setInfo()", name, e)
                    list_item.setInfo('video', {
                        'title': name,
                        'plot': f"User list: {name}"
                    })
            else:
                # v19: Use setInfo() only
                list_item.setInfo('video', {
                    'title': name,
                    'plot': f"User list: {name}"
                })
                self.logger.debug("LIST ITEM v19: Set metadata via setInfo for '%s'", name)

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
            list_item = xbmcgui.ListItem(label=name)

            # Set basic info - version-specific approach
            kodi_major = get_kodi_major_version()
            if kodi_major >= 21:
                # v21+: Use InfoTagVideo ONLY - completely avoid setInfo() to prevent deprecation warnings
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(name)
                    video_info_tag.setPlot(f"Folder: {name}")
                    self.logger.debug("FOLDER ITEM v21+: Set metadata via InfoTagVideo for '%s'", name)
                except Exception as e:
                    self.logger.error("FOLDER ITEM v21+: InfoTagVideo failed for '%s': %s", name, e)
                    # No fallback to setInfo() on v21+ to avoid deprecation warnings
            elif kodi_major == 20:
                # v20: Try InfoTagVideo first, fallback to setInfo() if needed
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(name)
                    video_info_tag.setPlot(f"Folder: {name}")
                    self.logger.debug("FOLDER ITEM v20: Set metadata via InfoTagVideo for '%s'", name)
                except Exception as e:
                    self.logger.warning("FOLDER ITEM v20: InfoTagVideo failed for '%s': %s, falling back to setInfo()", name, e)
                    list_item.setInfo('video', {
                        'title': name,
                        'plot': f"Folder: {name}"
                    })
            else:
                # v19: Use setInfo() only
                list_item.setInfo('video', {
                    'title': name,
                    'plot': f"Folder: {name}"
                })
                self.logger.debug("FOLDER ITEM v19: Set metadata via setInfo for '%s'", name)

            # Set folder icon
            self._apply_art(list_item, 'folder')

            # Add context menu
            self._set_folder_context_menu(list_item, folder_data)

            return list_item

        except Exception as e:
            self.logger.error("Failed to build folder item: %s", e)
            return None

    def _set_list_context_menu(self, list_item: xbmcgui.ListItem, list_data: Dict[str, Any]):
        """Set context menu for list items"""
        context_items = []
        list_id = list_data.get('id', '')

        # Rename list
        context_items.append((
            L(31020),  # "Rename"
            f"RunPlugin(plugin://{self.addon_id}/?action=rename_list&list_id={list_id})"
        ))

        # Delete list
        context_items.append((
            L(31021),  # "Delete"
            f"RunPlugin(plugin://{self.addon_id}/?action=delete_list&list_id={list_id})"
        ))

        # Export list
        context_items.append((
            L(31022),  # "Export"
            f"RunPlugin(plugin://{self.addon_id}/?action=export_list&list_id={list_id})"
        ))

        list_item.addContextMenuItems(context_items)

    def _set_folder_context_menu(self, list_item: xbmcgui.ListItem, folder_data: Dict[str, Any]):
        """Set context menu for folder items"""
        context_items = []
        folder_id = folder_data.get('id', '')
        folder_name = folder_data.get('name', '')

        # Don't add rename/delete options for reserved Search History folder
        if folder_name != "Search History":
            # Rename folder
            context_items.append((
                L(31020),  # "Rename"
                f"RunPlugin(plugin://{self.addon_id}/?action=rename_folder&folder_id={folder_id})"
            ))

            # Delete folder
            context_items.append((
                L(31021),  # "Delete"
                f"RunPlugin(plugin://{self.addon_id}/?action=delete_folder&folder_id={folder_id})"
            ))

        list_item.addContextMenuItems(context_items)

    def create_simple_listitem(self, title: str, description: Optional[str] = None, action: Optional[str] = None, icon: Optional[str] = None) -> xbmcgui.ListItem:
        """Create a simple ListItem for menu items (compatibility method for MenuBuilder)"""
        try:
            kodi_major = get_kodi_major_version()
            list_item = xbmcgui.ListItem(label=title)

            # Set basic info - version-specific approach
            if kodi_major >= 21:
                # v21+: Use InfoTagVideo ONLY - completely avoid setInfo() to prevent deprecation warnings
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(title)
                    if description:
                        video_info_tag.setPlot(description)
                except Exception as e:
                    self.logger.error("SIMPLE LISTITEM v21+: InfoTagVideo failed for '%s': %s", title, e)
                    # No fallback to setInfo() on v21+ to avoid deprecation warnings
            elif kodi_major == 20:
                # v20: Try InfoTagVideo first, fallback to setInfo() if needed
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(title)
                    if description:
                        video_info_tag.setPlot(description)
                except Exception as e:
                    self.logger.warning("SIMPLE LISTITEM v20: InfoTagVideo failed for '%s': %s, falling back to setInfo()", title, e)
                    info = {'title': title}
                    if description:
                        info['plot'] = description
                    list_item.setInfo('video', info)
            else:
                # v19: Use setInfo() only
                info = {'title': title}
                if description:
                    info['plot'] = description
                list_item.setInfo('video', info)

            # Set icon/artwork
            art = {}
            if icon:
                art['icon'] = icon
                art['thumb'] = icon
            else:
                art['icon'] = 'DefaultFolder.png'
                art['thumb'] = 'DefaultFolder.png'

            list_item.setArt(art)
            return list_item

        except Exception as e:
            self.logger.error("SIMPLE LISTITEM: Failed to create simple listitem for '%s': %s", title, e)
            # Return basic listitem on error
            return xbmcgui.ListItem(label=title)

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
            self.logger.info("RENDERER DIRECTORY: Starting render of %s items with content_type='%s'", len(items), content_type)
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

            # Build all items, ensuring non-empty URLs
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
                            self.logger.debug("RENDERER DIRECTORY: Adding item #%s '%s' - URL: '%s', isFolder: %s", idx, title, url, is_folder)
                            xbmcplugin.addDirectoryItem(
                                handle=self.addon_handle,
                                url=url,
                                listitem=listitem,
                                isFolder=is_folder
                            )
                            success_count += 1
                        else:
                            self.logger.warning("RENDERER DIRECTORY: Skipping item #%s with empty URL: '%s'", idx, title)
                    else:
                        self.logger.warning("RENDERER DIRECTORY: Failed to build item #%s: '%s'", idx, title)
                except Exception as e:
                    self.logger.error("RENDERER DIRECTORY: Error building item #%s '%s': %s", idx, item.get('title', 'Unknown'), e)

            self.logger.info("RENDERER DIRECTORY: Successfully added %s/%s items to directory", success_count, len(items))
            self.logger.debug("RENDERER DIRECTORY: Calling endOfDirectory(handle=%s, succeeded=True, cacheToDisc=True)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return True

        except Exception as e:
            self.logger.error("RENDERER DIRECTORY: Fatal error in render_directory: %s", e)
            self.logger.debug("RENDERER DIRECTORY: Calling endOfDirectory(handle=%s, succeeded=False)", self.addon_handle)
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return False

    def render_list_items(self, list_id: int, sort_method: str = None) -> None:
        """Render items in a list with optimized performance using media_items data"""
        try:
            # Get list metadata
            list_info = self.query_manager.get_list_by_id(list_id)
            if not list_info:
                self.logger.error("List not found: %s", list_id)
                return

            # Get list items with enhanced media data - no JSON RPC calls needed
            items = self.query_manager.get_list_items_with_media(list_id, sort_method)

            if not items:
                # Show empty list message
                self.plugin_context.add_item(
                    url="plugin://plugin.video.librarygenie/?action=empty",
                    listitem=xbmcgui.ListItem(label="No items in this list"),
                    isFolder=False
                )
                return

            self.logger.debug("Rendering %s list items using media_items data", len(items))

            # Process items efficiently using enhanced media_items data
            for item in items:
                try:
                    # Build listitem using enhanced media data from media_items table
                    # This now uses all the fields we gather in the scanner
                    listitem, url = self.listitem_builder.build_media_listitem(item)

                    # Add context menu for list management
                    context_menu = [
                        (
                            "Remove from List",
                            f"RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={list_id}&media_item_id={item['id']})"
                        )
                    ]
                    listitem.addContextMenuItems(context_menu)

                    # Add to plugin response
                    self.plugin_context.add_item(
                        url=url,
                        listitem=listitem,
                        isFolder=False
                    )

                except Exception as e:
                    self.logger.error("Failed to render list item %s: %s", item.get('id', 'unknown'), e)
                    continue

            # Set content type and finish directory
            self.plugin_context.set_content_type('movies')
            self.plugin_context.end_directory(cacheToDisc=True)

            self.logger.debug("Successfully rendered %s list items", len(items))

        except Exception as e:
            self.logger.error("Failed to render list items: %s", e)
            self.plugin_context.end_directory(succeeded=False)


# Global renderer instance
_listitem_renderer_instance = None


def get_listitem_renderer(addon_handle: Optional[int] = None, addon_id: Optional[str] = None, context=None):
    """Get global listitem renderer instance"""
    global _listitem_renderer_instance
    if _listitem_renderer_instance is None:
        # Use provided parameters or get from current context
        if addon_handle is None or addon_id is None:
            import sys
            addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
            addon_id = "plugin.video.librarygenie"

        _listitem_renderer_instance = ListItemRenderer(addon_handle, addon_id, context)

    return _listitem_renderer_instance