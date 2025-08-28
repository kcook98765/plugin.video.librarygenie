#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Renderer
Renders list items with proper Kodi integration
"""

from typing import List, Dict, Any, Optional
import xbmc
import xbmcgui
import xbmcplugin
from .listitem_builder import ListItemBuilder
from ..utils.logger import get_logger


class ListItemRenderer:
    """Renders lists and media items as Kodi ListItems"""

    def __init__(self, addon_handle: int, addon_id: str):
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_logger(__name__)
        self.builder = ListItemBuilder(addon_handle, addon_id)

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
            # Set content type for lists
            xbmcplugin.setContent(self.addon_handle, "files")

            for list_data in lists:
                list_item = self._build_list_item(list_data)
                if list_item:
                    list_id = list_data['id']
                    url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"

                    xbmcplugin.addDirectoryItem(
                        handle=self.addon_handle,
                        url=url,
                        listitem=list_item,
                        isFolder=True
                    )

            xbmcplugin.endOfDirectory(self.addon_handle)
            return True

        except Exception as e:
            self.logger.error(f"Failed to render lists: {e}")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
            return False

    def render_media_items(self, items: List[Dict[str, Any]], content_type: str = "movies") -> bool:
        """
        Render media items using the dual-mode builder

        Args:
            items: List of media item dictionaries
            content_type: "movies", "tvshows", or "episodes"

        Returns:
            bool: Success status
        """
        return self.builder.build_directory(items, content_type)

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

            xbmcplugin.endOfDirectory(self.addon_handle)
            return True

        except Exception as e:
            self.logger.error(f"Failed to render folders: {e}")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
            return False

    def _build_list_item(self, list_data: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Build ListItem for a user list"""
        try:
            name = list_data.get('name', 'Unnamed List')
            list_item = xbmcgui.ListItem(label=name)

            # Set basic info
            list_item.setInfo('video', {
                'title': name,
                'plot': f"User list: {name}"
            })

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

            # Set basic info
            list_item.setInfo('video', {
                'title': name,
                'plot': f"Folder: {name}"
            })

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
            "Rename",
            f"RunPlugin(plugin://{self.addon_id}/?action=rename_list&list_id={list_id})"
        ))

        # Delete list
        context_items.append((
            "Delete",
            f"RunPlugin(plugin://{self.addon_id}/?action=delete_list&list_id={list_id})"
        ))

        # Export list
        context_items.append((
            "Export",
            f"RunPlugin(plugin://{self.addon_id}/?action=export_list&list_id={list_id})"
        ))

        list_item.addContextMenuItems(context_items)

    def _set_folder_context_menu(self, list_item: xbmcgui.ListItem, folder_data: Dict[str, Any]):
        """Set context menu for folder items"""
        context_items = []
        folder_id = folder_data.get('id', '')

        # Rename folder
        context_items.append((
            "Rename",
            f"RunPlugin(plugin://{self.addon_id}/?action=rename_folder&folder_id={folder_id})"
        ))

        # Delete folder
        context_items.append((
            "Delete",
            f"RunPlugin(plugin://{self.addon_id}/?action=delete_folder&folder_id={folder_id})"
        ))

        list_item.addContextMenuItems(context_items)

    def create_simple_listitem(self, title: str, description: str = None, action: str = None, icon: str = None) -> xbmcgui.ListItem:
        """Create a simple ListItem for menu items (compatibility method for MenuBuilder)"""
        try:
            self.logger.debug(f"SIMPLE LISTITEM: Creating for '{title}'")
            list_item = xbmcgui.ListItem(label=title)

            # Set basic info
            info = {'title': title}
            if description:
                info['plot'] = description
                self.logger.debug(f"SIMPLE LISTITEM: Set description for '{title}': {len(description)} chars")

            list_item.setInfo('video', info)
            self.logger.debug(f"SIMPLE LISTITEM: Set video info for '{title}': {list(info.keys())}")

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

    def create_movie_listitem(self, movie_data: Dict[str, Any], base_url: str, action: str) -> xbmcgui.ListItem:
        """Create a movie ListItem (compatibility method for MenuBuilder)"""
        try:
            # Delegate to the builder for movie items
            return self.builder._create_library_listitem(movie_data)
        except Exception as e:
            self.logger.error(f"Failed to create movie listitem: {e}")
            # Fallback to simple listitem
            title = movie_data.get('title', movie_data.get('label', 'Unknown'))
            return self.create_simple_listitem(title)


# Global renderer instance
_listitem_renderer_instance = None


def get_listitem_renderer(addon_handle: int = None, addon_id: str = None):
    """Get global listitem renderer instance"""
    global _listitem_renderer_instance
    if _listitem_renderer_instance is None:
        if addon_handle is None or addon_id is None:
            # Try to get from current context
            try:
                import sys
                import xbmcaddon
                addon = xbmcaddon.Addon()
                addon_id = addon.getAddonInfo('id')
                addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else 0
            except:
                addon_handle = 0
                addon_id = 'plugin.video.librarygenie'
        _listitem_renderer_instance = ListItemRenderer(addon_handle, addon_id)
    return _listitem_renderer_instance