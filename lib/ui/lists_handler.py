#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Lists Handler
Handles lists display, creation, deletion, and management
"""

import xbmcplugin
import xbmcgui
from typing import List, Dict, Any
from .plugin_context import PluginContext
from .response_types import DirectoryResponse, DialogResponse, ActionResponse
from ..data.query_manager import get_query_manager


class ListsHandler:
    """Handles lists operations"""

    def __init__(self):
        pass

    def show_lists_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main lists menu with folders and lists"""
        try:
            context.logger.info("Displaying lists menu")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get all user lists and folders
            all_lists = query_manager.get_all_lists_with_folders()
            context.logger.info(f"Found {len(all_lists)} total lists")

            # Filter out the special "Kodi Favorites" list from the main Lists menu
            user_lists = [item for item in all_lists if item.get('name') != 'Kodi Favorites']
            context.logger.info(f"Found {len(user_lists)} user lists (excluding Kodi Favorites)")

            if not user_lists:
                # No lists exist, offer to create one
                return self._show_empty_lists_menu(context)

            # Build menu items for lists and folders
            menu_items = []

            # Add "Create New List" option at the top
            menu_items.append({
                'label': "[COLOR yellow]+ Create New List[/COLOR]",
                'url': context.build_url('create_list_execute'),
                'is_folder': True,
                'icon': "DefaultAddSource.png",
                'description': "Create a new list"
            })

            # Add "Create New Folder" option
            menu_items.append({
                'label': "[COLOR cyan]+ Create New Folder[/COLOR]",
                'url': context.build_url('create_folder_execute'),
                'is_folder': True,
                'icon': "DefaultFolder.png",
                'description': "Create a new folder"
            })

            # Get all existing folders to display as navigable items
            all_folders = query_manager.get_all_folders()

            # Add folders as navigable items
            for folder_info in all_folders:
                folder_id = folder_info['id']
                folder_name = folder_info['name']
                list_count = folder_info['list_count']

                # Check if it's the reserved "Search History" folder
                is_reserved_folder = folder_name == 'Search History'
                context_menu = []

                if not is_reserved_folder:
                    context_menu = [
                        (f"Rename Folder '{folder_name}'", f"RunPlugin({context.build_url('rename_folder', folder_id=folder_id)})"),
                        (f"Delete Folder '{folder_name}'", f"RunPlugin({context.build_url('delete_folder', folder_id=folder_id)})")
                    ]

                menu_items.append({
                    'label': f"[COLOR cyan]📁 {folder_name}[/COLOR]",
                    'url': context.build_url('show_folder', folder_id=folder_id),
                    'is_folder': True,
                    'description': f"Folder with {list_count} lists",
                    'context_menu': context_menu
                })

            # Separate standalone lists (not in any folder)
            standalone_lists = [item for item in user_lists if not item.get('folder_name') or item.get('folder_name') == 'Root']

            # Add standalone lists (not in any folder)
            for list_item in standalone_lists:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')
                item_count = list_item.get('item_count', 0)

                context_menu = [
                    (f"Rename List '{name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
                    (f"Delete List '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': f"[COLOR yellow]📋 {name}[/COLOR]",
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': f"{item_count} items - {description}" if description else f"{item_count} items",
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'])

                if 'description' in item:
                    list_item.setInfo('video', {'plot': item['description']})

                if 'icon' in item:
                    list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

                # Add context menu if present
                if 'context_menu' in item:
                    list_item.addContextMenuItems(item['context_menu'])

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    item['url'],
                    list_item,
                    item['is_folder']
                )

            # End directory
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )

            return DirectoryResponse(
                items=menu_items,
                success=True,
                cache_to_disc=True,
                content_type="files"
            )

        except Exception as e:
            context.logger.error(f"Error in show_lists_menu: {e}")
            return DirectoryResponse(
                items=[],
                success=False
            )

    def _show_empty_lists_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show menu when no lists exist"""
        if xbmcgui.Dialog().yesno(
            context.addon.getLocalizedString(35002),
            "No lists found. Create your first list?"
        ):
            return self.create_list(context)

        return DirectoryResponse(items=[], success=True)

    def create_list(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new list"""
        try:
            context.logger.info("Handling create list request")

            # Get list name from user
            list_name = xbmcgui.Dialog().input(
                "Enter list name:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not list_name or not list_name.strip():
                context.logger.info("User cancelled list creation or entered empty name")
                return DialogResponse(success=False)

            # Initialize query manager and create list
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            result = query_manager.create_list(list_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{list_name}' already exists"
                else:
                    message = "Failed to create list"

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info(f"Successfully created list: {list_name}")
                return DialogResponse(
                    success=True,
                    message=f"Created list: {list_name}",
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error(f"Error creating list: {e}")
            return DialogResponse(
                success=False,
                message="Error creating list"
            )

    def delete_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle deleting a list"""
        try:
            context.logger.info(f"Deleting list {list_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get current list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message="List not found"
                )

            # Confirm deletion
            if not xbmcgui.Dialog().yesno(
                context.addon.getLocalizedString(35002),
                f"Delete list '{list_info['name']}'?",
                f"This will remove {list_info['item_count']} items from the list."
            ):
                context.logger.info("User cancelled list deletion")
                return DialogResponse(success=False)

            # Delete the list
            result = query_manager.delete_list(list_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to delete list"
                )
            else:
                context.logger.info(f"Successfully deleted list: {list_info['name']}")
                return DialogResponse(
                    success=True,
                    message=f"Deleted list: {list_info['name']}",
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error(f"Error deleting list: {e}")
            return DialogResponse(
                success=False,
                message="Error deleting list"
            )

    def rename_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle renaming a list"""
        try:
            context.logger.info(f"Renaming list {list_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get current list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message="List not found"
                )

            # Get new name from user
            new_name = xbmcgui.Dialog().input(
                "Enter new list name:",
                defaultt=list_info['name'],
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                context.logger.info("User cancelled list rename or entered empty name")
                return DialogResponse(success=False)

            # Update the list name
            result = query_manager.rename_list(list_id, new_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{new_name}' already exists"
                else:
                    message = "Failed to rename list"

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info(f"Successfully renamed list to: {new_name}")
                return DialogResponse(
                    success=True,
                    message=f"Renamed list to: {new_name}",
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error(f"Error renaming list: {e}")
            return DialogResponse(
                success=False,
                message="Error renaming list"
            )

    def remove_from_list(self, context: PluginContext, list_id: str, item_id: str) -> DialogResponse:
        """Handle removing an item from a list"""
        try:
            context.logger.info(f"Removing item {item_id} from list {list_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get list and item info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message="List not found"
                )

            # Get the media item info for confirmation
            items = query_manager.get_list_items(list_id)
            item_info = None
            for item in items:
                if str(item.get('item_id', item.get('id'))) == str(item_id):
                    item_info = item
                    break

            if not item_info:
                return DialogResponse(
                    success=False,
                    message="Item not found"
                )

            # Confirm removal
            if not xbmcgui.Dialog().yesno(
                context.addon.getLocalizedString(35002),
                f"Remove '{item_info['title']}' from list '{list_info['name']}'?"
            ):
                context.logger.info("User cancelled item removal")
                return DialogResponse(success=False)

            # Remove the item
            result = query_manager.delete_item_from_list(list_id, item_id)

            if result.get("success"):
                context.logger.info(f"Successfully removed item from list")
                return DialogResponse(
                    success=True,
                    message=f"Removed '{item_info['title']}' from list",
                    refresh_needed=True
                )
            else:
                return DialogResponse(
                    success=False,
                    message="Failed to remove item from list"
                )

        except Exception as e:
            context.logger.error(f"Error removing from list: {e}")
            return DialogResponse(
                success=False,
                message="Error removing from list"
            )

    def create_folder(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new folder"""
        try:
            context.logger.info("Handling create folder request")

            # Get folder name from user
            folder_name = xbmcgui.Dialog().input(
                "Enter folder name:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not folder_name or not folder_name.strip():
                context.logger.info("User cancelled folder creation or entered empty name")
                return DialogResponse(success=False)

            # Initialize query manager and create folder
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            result = query_manager.create_folder(folder_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{folder_name}' already exists"
                else:
                    message = "Failed to create folder"

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info(f"Successfully created folder: {folder_name}")
                return DialogResponse(
                    success=True,
                    message=f"Created folder: {folder_name}",
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error(f"Error creating folder: {e}")
            return DialogResponse(
                success=False,
                message="Error creating folder"
            )

    def rename_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle renaming a folder"""
        try:
            context.logger.info(f"Renaming folder {folder_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get current folder info
            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message="Folder not found"
                )

            # Check if it's a reserved folder
            if folder_info['name'] == 'Search History':
                return DialogResponse(
                    success=False,
                    message="Cannot rename reserved folder"
                )

            # Get new name from user
            new_name = xbmcgui.Dialog().input(
                "Enter new folder name:",
                defaultt=folder_info['name'],
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                context.logger.info("User cancelled folder rename or entered empty name")
                return DialogResponse(success=False)

            # Update the folder name
            result = query_manager.rename_folder(folder_id, new_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{new_name}' already exists"
                else:
                    message = "Failed to rename folder"

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info(f"Successfully renamed folder to: {new_name}")
                return DialogResponse(
                    success=True,
                    message=f"Renamed folder to: {new_name}",
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error(f"Error renaming folder: {e}")
            return DialogResponse(
                success=False,
                message="Error renaming folder"
            )

    def delete_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle deleting a folder"""
        try:
            context.logger.info(f"Deleting folder {folder_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get current folder info
            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message="Folder not found"
                )

            # Check if it's a reserved folder
            if folder_info['name'] == 'Search History':
                return DialogResponse(
                    success=False,
                    message="Cannot delete reserved folder"
                )

            # Check if folder has lists
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)

            # Confirm deletion
            if lists_in_folder:
                if not xbmcgui.Dialog().yesno(
                    context.addon.getLocalizedString(35002),
                    f"Delete folder '{folder_info['name']}'?",
                    f"This folder contains {len(lists_in_folder)} lists.",
                    "All lists will be moved to the root level."
                ):
                    context.logger.info("User cancelled folder deletion")
                    return DialogResponse(success=False)
            else:
                if not xbmcgui.Dialog().yesno(
                    context.addon.getLocalizedString(35002),
                    f"Delete empty folder '{folder_info['name']}'?"
                ):
                    context.logger.info("User cancelled folder deletion")
                    return DialogResponse(success=False)

            # Delete the folder
            result = query_manager.delete_folder(folder_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to delete folder"
                )
            else:
                context.logger.info(f"Successfully deleted folder: {folder_info['name']}")
                return DialogResponse(
                    success=True,
                    message=f"Deleted folder: {folder_info['name']}",
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error(f"Error deleting folder: {e}")
            return DialogResponse(
                success=False,
                message="Error deleting folder"
            )

    def view_list(self, context: PluginContext, list_id: str) -> DirectoryResponse:
        """Display contents of a specific list"""
        try:
            context.logger.info(f"Displaying list {list_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                context.logger.error(f"List {list_id} not found")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get list items
            list_items = query_manager.get_list_items(list_id)

            context.logger.info(f"List '{list_info['name']}' has {len(list_items)} items")

            if not list_items:
                # Empty list
                empty_item = xbmcgui.ListItem(label="[COLOR gray]List is empty[/COLOR]")
                empty_item.setInfo('video', {'plot': 'This list contains no items'})
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )
            else:
                # Build list items
                from lib.ui.listitem_builder import ListItemBuilder
                builder = ListItemBuilder(context.addon_handle, context.addon.getAddonInfo('id'))

                for item in list_items:
                    try:
                        # Ensure item has required 'id' field - use item_id if available
                        if 'id' not in item and 'item_id' in item:
                            item['id'] = item['item_id']
                        elif 'id' not in item:
                            # Skip items without proper ID
                            context.logger.warning(f"Skipping list item without ID: {item.get('title', 'Unknown')}")
                            continue

                        # Build context menu for item
                        context_menu = []

                        # Add context menu items
                        if item.get('imdb_id'):
                            context_menu.append((
                                "Remove from List",
                                f"RunPlugin({context.build_url('remove_from_list', list_id=list_id, item_id=item.get('item_id', item.get('id')))})"
                            ))

                        # Create list item for display
                        list_item = builder._create_list_item_from_data(item, context_menu)

                        # Add to directory
                        xbmcplugin.addDirectoryItem(
                            context.addon_handle,
                            list_item['url'],
                            list_item['listitem'],
                            list_item['is_folder']
                        )

                    except Exception as e:
                        context.logger.error(f"Error building list item: {e}")
                        continue

            # Set content type and finish directory
            xbmcplugin.setContent(context.addon_handle, 'movies')
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )

            return DirectoryResponse(
                items=list_items,
                success=True,
                content_type="movies"
            )

        except Exception as e:
            context.logger.error(f"Error viewing list: {e}")
            return DirectoryResponse(
                items=[],
                success=False
            )

    def show_folder(self, context: PluginContext, folder_id: str) -> DirectoryResponse:
        """Display contents of a specific folder"""
        try:
            context.logger.info(f"Displaying folder {folder_id}")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get folder info
            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                context.logger.error(f"Folder {folder_id} not found")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get lists in this folder
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            context.logger.info(f"Folder '{folder_info['name']}' has {len(lists_in_folder)} lists")

            menu_items = []

            # Add "Create New List" option in this folder
            menu_items.append({
                'label': "[COLOR yellow]+ Create New List in this Folder[/COLOR]",
                'url': context.build_url('create_list_in_folder', folder_id=folder_id),
                'is_folder': True,
                'icon': "DefaultAddSource.png",
                'description': f"Create a new list in '{folder_info['name']}'"
            })

            # Add lists in this folder
            for list_item in lists_in_folder:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')
                item_count = list_item.get('item_count', 0)

                context_menu = [
                    (f"Rename List '{name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
                    (f"Delete List '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': f"[COLOR yellow]📋 {name}[/COLOR]",
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': f"{item_count} items - {description}" if description else f"{item_count} items",
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # If folder is empty, show message
            if not lists_in_folder:
                empty_item = xbmcgui.ListItem(label="[COLOR gray]Folder is empty[/COLOR]")
                empty_item.setInfo('video', {'plot': 'This folder contains no lists'})
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'])

                if 'description' in item:
                    list_item.setInfo('video', {'plot': item['description']})

                if 'icon' in item:
                    list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

                # Add context menu if present
                if 'context_menu' in item:
                    list_item.addContextMenuItems(item['context_menu'])

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    item['url'],
                    list_item,
                    item['is_folder']
                )

            # End directory
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )

            return DirectoryResponse(
                items=menu_items,
                success=True,
                cache_to_disc=True,
                content_type="files"
            )

        except Exception as e:
            context.logger.error(f"Error showing folder: {e}")
            return DirectoryResponse(
                items=[],
                success=False
            )