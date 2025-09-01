
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
