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
from ..utils.kodi_version import get_kodi_major_version


class ListItemRenderer:
    """Renders ListItems with proper Kodi integration"""

    def __init__(self, addon_handle: int, addon_id: str, context=None):
        """Initialize ListItemRenderer"""
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_logger(__name__)
        self.builder = ListItemBuilder(addon_handle, addon_id, context)

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
            self.logger.info(f"RENDER LISTS: Starting render of {len(lists)} lists (folder_id={folder_id})")

            # Set content type for lists
            self.logger.debug(f"RENDER LISTS: Setting content type 'files' for handle {self.addon_handle}")
            xbmcplugin.setContent(self.addon_handle, "files")

            success_count = 0
            for idx, list_data in enumerate(lists, start=1):
                try:
                    list_name = list_data.get('name', 'Unknown List')
                    list_id = list_data.get('id')

                    self.logger.debug(f"RENDER LISTS: Processing list #{idx}/{len(lists)}: '{list_name}' (id={list_id})")

                    list_item = self._build_list_item(list_data)
                    if list_item:
                        url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"
                        self.logger.debug(f"RENDER LISTS: Built list item for '{list_name}' - URL: '{url}'")

                        xbmcplugin.addDirectoryItem(
                            handle=self.addon_handle,
                            url=url,
                            listitem=list_item,
                            isFolder=True
                        )
                        success_count += 1
                        self.logger.debug(f"RENDER LISTS: Successfully added list #{idx} '{list_name}' to directory")
                    else:
                        self.logger.warning(f"RENDER LISTS: Failed to build list item for '{list_name}'")
                except Exception as e:
                    self.logger.error(f"RENDER LISTS: Error processing list #{idx}: {e}")

            self.logger.info(f"RENDER LISTS: Successfully added {success_count}/{len(lists)} lists to directory")
            self.logger.debug(f"RENDER LISTS: Calling endOfDirectory(handle={self.addon_handle}, cacheToDisc=True)")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return True

        except Exception as e:
            self.logger.error(f"RENDER LISTS: Failed to render lists: {e}")
            self.logger.debug(f"RENDER LISTS: Calling endOfDirectory(handle={self.addon_handle}, succeeded=False)")
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
            self.logger.info(f"RENDERER: Starting render_media_items with {len(items)} items (content_type='{content_type}')")
            if context_menu_callback:
                self.logger.info("RENDERER: Context menu callback provided - will apply to each item")

            # Use the ListItemBuilder to handle the rendering
            builder = ListItemBuilder(self.addon_handle, self.addon_id)
            success = builder.build_directory(items, content_type, context_menu_callback)

            if success:
                self.logger.info(f"RENDERER: Successfully rendered {len(items)} items")
            else:
                self.logger.error("RENDERER: Failed to render items")

            return success

        except Exception as e:
            self.logger.error(f"RENDERER: Error rendering media items: {e}")
            import traceback
            self.logger.error(f"RENDERER: Traceback: {traceback.format_exc()}")
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
            self.logger.error(f"Failed to render folders: {e}")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return False

    def _build_list_item(self, list_data: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Build ListItem for a user list"""
        try:
            name = list_data.get('name', 'Unnamed List')
            list_item = xbmcgui.ListItem(label=name)

            # Set basic info - guard setInfo() for v20+
            kodi_major = get_kodi_major_version()
            if kodi_major >= 20:
                # v20+: Use InfoTagVideo setters
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(name)
                    video_info_tag.setPlot(f"User list: {name}")
                    self.logger.debug(f"LIST ITEM v20+: Set metadata via InfoTagVideo for '{name}'")
                except Exception as e:
                    self.logger.warning(f"LIST ITEM v20+: InfoTagVideo failed for '{name}': {e}")
                    # On v21+, completely avoid setInfo() to prevent deprecation warnings
                    # Only use setInfo() on v19/v20 where InfoTagVideo may not be fully reliable
                    if kodi_major < 21:
                        list_item.setInfo('video', {
                            'title': name,
                            'plot': f"User list: {name}"
                        })
            else:
                # v19: Use setInfo()
                list_item.setInfo('video', {
                    'title': name,
                    'plot': f"User list: {name}"
                })
                self.logger.debug(f"LIST ITEM v19: Set metadata via setInfo for '{name}'")

            # Set folder icon
            list_item.setArt({
                'icon': 'DefaultFolder.png',
                'thumb': 'DefaultFolder.png'
            })

            # Add context menu
            self._set_list_context_menu(list_item, list_data)

            return list_item

        except Exception as e:
            self.logger.error(f"Failed to build list item: {e}")
            return None

    def _build_folder_item(self, folder_data: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Build ListItem for a folder"""
        try:
            name = folder_data.get('name', 'Unnamed Folder')
            list_item = xbmcgui.ListItem(label=name)

            # Set basic info - guard setInfo() for v20+
            kodi_major = get_kodi_major_version()
            if kodi_major >= 20:
                # v20+: Use InfoTagVideo setters
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(name)
                    video_info_tag.setPlot(f"Folder: {name}")
                    self.logger.debug(f"FOLDER ITEM v20+: Set metadata via InfoTagVideo for '{name}'")
                except Exception as e:
                    self.logger.warning(f"FOLDER ITEM v20+: InfoTagVideo failed for '{name}': {e}")
                    # On v21+, completely avoid setInfo() to prevent deprecation warnings
                    # Only use setInfo() on v19/v20 where InfoTagVideo may not be fully reliable
                    if kodi_major < 21:
                        list_item.setInfo('video', {
                            'title': name,
                            'plot': f"Folder: {name}"
                        })
            else:
                # v19: Use setInfo()
                list_item.setInfo('video', {
                    'title': name,
                    'plot': f"Folder: {name}"
                })
                self.logger.debug(f"FOLDER ITEM v19: Set metadata via setInfo for '{name}'")

            # Set folder icon
            list_item.setArt({
                'icon': 'DefaultFolder.png',
                'thumb': 'DefaultFolder.png'
            })

            # Add context menu
            self._set_folder_context_menu(list_item, folder_data)

            return list_item

        except Exception as e:
            self.logger.error(f"Failed to build folder item: {e}")
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
            self.logger.debug(f"SIMPLE LISTITEM: Creating for '{title}'")
            list_item = xbmcgui.ListItem(label=title)

            # Set basic info - guard setInfo() for v20+
            kodi_major = get_kodi_major_version()
            if kodi_major >= 20:
                # v20+: Use InfoTagVideo setters
                try:
                    video_info_tag = list_item.getVideoInfoTag()
                    video_info_tag.setTitle(title)
                    if description:
                        video_info_tag.setPlot(description)
                    self.logger.debug(f"SIMPLE LISTITEM v20+: Set metadata via InfoTagVideo for '{title}'")
                except Exception as e:
                    self.logger.warning(f"SIMPLE LISTITEM v20+: InfoTagVideo failed for '{title}': {e}")
                    # On v21+, completely avoid setInfo() to prevent deprecation warnings
                    # Only use setInfo() on v19/v20 where InfoTagVideo may not be fully reliable
                    if kodi_major < 21:
                        info = {'title': title}
                        if description:
                            info['plot'] = description
                        list_item.setInfo('video', info)
            else:
                # v19: Use setInfo()
                info = {'title': title}
                if description:
                    info['plot'] = description
                    self.logger.debug(f"SIMPLE LISTITEM: Set description for '{title}': {len(description)} chars")

                list_item.setInfo('video', info)
                self.logger.debug(f"SIMPLE LISTITEM v19: Set video info for '{title}': {list(info.keys())}")

            # Set icon/artwork
            art = {}
            if icon:
                art['icon'] = icon
                art['thumb'] = icon
                self.logger.debug(f"SIMPLE LISTITEM: Set custom icon for '{title}': {icon}")
            else:
                art['icon'] = 'DefaultFolder.png'
                art['thumb'] = 'DefaultFolder.png'
                self.logger.debug(f"SIMPLE LISTITEM: Set default icon for '{title}'")

            list_item.setArt(art)

            self.logger.debug(f"SIMPLE LISTITEM: Successfully created for '{title}' with action '{action}'")
            return list_item

        except Exception as e:
            self.logger.error(f"SIMPLE LISTITEM: Failed to create simple listitem for '{title}': {e}")
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
            self.logger.error(f"Failed to create movie listitem: {e}")
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
            self.logger.error(f"Failed to create episode listitem: {e}")
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
            self.logger.info(f"RENDERER DIRECTORY: Starting render of {len(items)} items with content_type='{content_type}'")
            self.logger.debug(f"RENDERER DIRECTORY: Setting content type '{content_type}' for handle {self.addon_handle}")
            xbmcplugin.setContent(self.addon_handle, content_type)

            # Add sort methods once per build (not per item)
            sort_methods = [
                ("SORT_METHOD_TITLE_IGNORE_THE", xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE),
                ("SORT_METHOD_VIDEO_YEAR", xbmcplugin.SORT_METHOD_VIDEO_YEAR),
                ("SORT_METHOD_DATE", xbmcplugin.SORT_METHOD_DATE)
            ]
            self.logger.debug(f"RENDERER DIRECTORY: Adding {len(sort_methods)} sort methods")
            for method_name, method in sort_methods:
                xbmcplugin.addSortMethod(self.addon_handle, method)
                self.logger.debug(f"RENDERER DIRECTORY: Added sort method {method_name}")

            # Build all items, ensuring non-empty URLs
            success_count = 0
            for idx, item in enumerate(items, start=1):
                try:
                    title = item.get('title', 'Unknown')
                    self.logger.debug(f"RENDERER DIRECTORY: Processing item #{idx}/{len(items)}: '{title}'")

                    result = self.builder._build_single_item(item)
                    if result:
                        url, listitem, is_folder = result
                        # Ensure non-empty URL to avoid directory errors
                        if url and url.strip():
                            self.logger.debug(f"RENDERER DIRECTORY: Adding item #{idx} '{title}' - URL: '{url}', isFolder: {is_folder}")
                            xbmcplugin.addDirectoryItem(
                                handle=self.addon_handle,
                                url=url,
                                listitem=listitem,
                                isFolder=is_folder
                            )
                            success_count += 1
                        else:
                            self.logger.warning(f"RENDERER DIRECTORY: Skipping item #{idx} with empty URL: '{title}'")
                    else:
                        self.logger.warning(f"RENDERER DIRECTORY: Failed to build item #{idx}: '{title}'")
                except Exception as e:
                    self.logger.error(f"RENDERER DIRECTORY: Error building item #{idx} '{item.get('title', 'Unknown')}': {e}")

            self.logger.info(f"RENDERER DIRECTORY: Successfully added {success_count}/{len(items)} items to directory")
            self.logger.debug(f"RENDERER DIRECTORY: Calling endOfDirectory(handle={self.addon_handle}, succeeded=True, cacheToDisc=True)")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return True

        except Exception as e:
            self.logger.error(f"RENDERER DIRECTORY: Fatal error in render_directory: {e}")
            self.logger.debug(f"RENDERER DIRECTORY: Calling endOfDirectory(handle={self.addon_handle}, succeeded=False)")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return False


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