#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Lists Handler
Handles lists display, creation, deletion, and management
"""

from typing import Dict, Any
import xbmcplugin
import xbmcgui
from .plugin_context import PluginContext
from .response_types import DirectoryResponse, DialogResponse
from .localization import L
from .breadcrumb_helper import get_breadcrumb_helper
from ..utils.logger import get_logger
from ..data.query_manager import get_query_manager
from .listitem_renderer import get_listitem_renderer
from ..utils.kodi_version import get_kodi_major_version



class ListsHandler:
    """Handles lists operations"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_logger(__name__)
        self.query_manager = context.query_manager
        self.storage_manager = context.storage_manager
        self.breadcrumb_helper = get_breadcrumb_helper()

    def _set_listitem_plot(self, list_item: xbmcgui.ListItem, plot: str):
        """Set plot metadata in version-compatible way to avoid v21 setInfo() deprecation warnings"""
        kodi_major = get_kodi_major_version()
        if kodi_major >= 21:
            # v21+: Use InfoTagVideo ONLY - completely avoid setInfo()
            try:
                video_info_tag = list_item.getVideoInfoTag()
                video_info_tag.setPlot(plot)
            except Exception as e:
                self.logger.error("InfoTagVideo failed for plot: %s", e)
        else:
            # v19/v20: Use setInfo() as fallback
            list_item.setInfo('video', {'plot': plot})

    def _set_custom_art_for_item(self, list_item: xbmcgui.ListItem, item_data: Dict[str, Any]):
        """Apply custom art based on item type"""
        try:
            # Get the renderer instance to use its art methods
            renderer = get_listitem_renderer()
            
            # Determine if this is a list or folder based on the URL action
            url = item_data.get('url', '')
            
            if 'action=show_list' in url:
                # This is a user list - use list/playlist art
                renderer._apply_art(list_item, 'list')
            elif 'action=show_folder' in url:
                # This is a folder - use folder art
                renderer._apply_art(list_item, 'folder')
            else:
                # Default/other items - use original icon if specified
                if 'icon' in item_data:
                    list_item.setArt({'icon': item_data['icon'], 'thumb': item_data['icon']})
                else:
                    list_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
                    
        except Exception as e:
            # Fallback to original behavior
            self.logger.error("Custom art failed: %s", e)
            if 'icon' in item_data:
                list_item.setArt({'icon': item_data['icon'], 'thumb': item_data['icon']})
            else:
                list_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})

    def show_lists_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main lists menu with folders and lists"""
        try:
            context.logger.debug("Displaying lists menu")

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
            context.logger.debug("Found %s total lists", len(all_lists))

            # Include all lists including "Kodi Favorites" in the main Lists menu
            user_lists = all_lists
            context.logger.debug("Found %s user lists (including Kodi Favorites)", len(user_lists))

            if not user_lists:
                # No lists exist - show empty state instead of dialog
                # This prevents confusing dialogs when navigating back from deletions
                menu_items = []

                # Add "Tools & Options" even when empty
                menu_items.append({
                    'label': f"[COLOR yellow]{L(36000)}[/COLOR]",  # "Tools & Options"
                    'url': context.build_url('show_list_tools', list_type='lists_main'),
                    'is_folder': True,
                    'icon': "DefaultAddonProgram.png",
                    'description': L(36018)  # "Access lists tools and options"
                })

                # Add "Create First List" option
                menu_items.append({
                    'label': "[COLOR lightgreen]+ Create Your First List[/COLOR]",
                    'url': context.build_url('create_list_execute'),
                    'is_folder': True,
                    'icon': "DefaultAddSource.png",
                    'description': "Create your first list to get started"
                })

                # Build directory items
                for item in menu_items:
                    list_item = xbmcgui.ListItem(label=item['label'])

                    if 'description' in item:
                        self._set_listitem_plot(list_item, item['description'])

                    if 'icon' in item:
                        list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

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

            # Build menu items for lists and folders
            menu_items = []

            # Add "Tools & Options" at the top - always pass current folder context
            current_folder_id = context.get_param('folder_id')  # Get current folder context
            if current_folder_id:
                tools_url = context.build_url('show_list_tools', list_type='lists_main', folder_id=current_folder_id)
            else:
                tools_url = context.build_url('show_list_tools', list_type='lists_main')

            menu_items.append({
                'label': f"[COLOR yellow]⚙️ Tools & Options[/COLOR]",  # "Tools & Options"
                'url': tools_url,
                'is_folder': True,
                'icon': "DefaultAddonProgram.png",
                'description': "Search, Favorites, Import/Export & Settings"  # Enhanced description
            })

            # Search and other tools are now accessible via Tools & Options menu

            # Check if favorites integration is enabled and ensure "Kodi Favorites" appears FIRST
            favorites_enabled = context.addon.getSettingBool('favorites_integration_enabled')
            kodi_favorites_item = None
            
            # Find existing Kodi Favorites or create if needed
            for item in user_lists:
                if item.get('name') == 'Kodi Favorites':
                    kodi_favorites_item = item
                    break
            
            if favorites_enabled and not kodi_favorites_item:
                # Create "Kodi Favorites" list if it doesn't exist but setting is enabled
                context.logger.info("LISTS HANDLER: Favorites integration enabled but 'Kodi Favorites' list not found, creating it")
                try:
                    from ..config.favorites_helper import on_favorites_integration_enabled
                    on_favorites_integration_enabled()  # This will create the list if it doesn't exist
                    
                    # Refresh the lists to include the newly created "Kodi Favorites"
                    all_lists = query_manager.get_all_lists_with_folders()
                    user_lists = all_lists
                    
                    # Find the newly created Kodi Favorites
                    for item in user_lists:
                        if item.get('name') == 'Kodi Favorites':
                            kodi_favorites_item = item
                            break
                    
                    context.logger.info("LISTS HANDLER: Refreshed lists, now have %s total lists", len(user_lists))
                except Exception as e:
                    context.logger.error("LISTS HANDLER: Error ensuring Kodi Favorites list exists: %s", e)

            # ADD KODI FAVORITES FIRST (before any folders or other lists)
            if favorites_enabled and kodi_favorites_item:
                list_id = kodi_favorites_item.get('id')
                name = kodi_favorites_item.get('name', 'Kodi Favorites')
                description = kodi_favorites_item.get('description', '')
                item_count = kodi_favorites_item.get('item_count', 0)

                context_menu = [
                    (f"Tools & Options for '{name}'", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': f"[COLOR yellow]{name}[/COLOR]",
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': f"{item_count} items - {description}" if description else f"{item_count} items",
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Get all existing folders to display as navigable items
            all_folders = query_manager.get_all_folders()

            # Add folders as navigable items (excluding Search History which is now at root level)
            for folder_info in all_folders:
                folder_id = folder_info['id']
                folder_name = folder_info['name']
                list_count = folder_info['list_count']

                # Skip the reserved "Search History" folder since it's now shown at root level
                if folder_name == 'Search History':
                    continue

                context_menu = [
                    (f"Tools & Options for '{folder_name}'", f"RunPlugin({context.build_url('show_tools', list_type='folder', list_id=folder_id)})")
                ]

                menu_items.append({
                    'label': f"[COLOR cyan]{folder_name}[/COLOR]",
                    'url': context.build_url('show_folder', folder_id=folder_id),
                    'is_folder': True,
                    'description': f"Folder with {list_count} lists",
                    'context_menu': context_menu
                })

            # Separate standalone lists (not in any folder) - EXCLUDE "Kodi Favorites" since it's already added first
            standalone_lists = [item for item in user_lists if (not item.get('folder_name') or item.get('folder_name') == 'Root') and item.get('name') != 'Kodi Favorites']

            # Add standalone lists (not in any folder) - Kodi Favorites already added above
            for list_item in standalone_lists:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')
                item_count = list_item.get('item_count', 0)

                # Special handling for Kodi Favorites - limited context menu
                if name == 'Kodi Favorites':
                    context_menu = [
                        (f"Tools & Options for '{name}'", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})")
                    ]
                else:
                    context_menu = [
                        (f"Rename '{name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
                        (f"Move '{name}' to Folder", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})"),
                        (f"Export '{name}'", f"RunPlugin({context.build_url('export_list', list_id=list_id)})"),
                        (f"Delete '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                    ]

                menu_items.append({
                    'label': f"[COLOR yellow]{name}[/COLOR]",
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': f"{item_count} items - {description}" if description else f"{item_count} items",
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Show breadcrumb notification for Lists menu (now main interface)
            try:
                self.breadcrumb_helper.show_breadcrumb_notification("LibraryGenie")
                context.logger.debug("LISTS HANDLER: Showed breadcrumb notification: 'LibraryGenie' (main interface)")
            except Exception as e:
                context.logger.error("LISTS HANDLER: Failed to show breadcrumb notification: %s", e)

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'])

                if 'description' in item:
                    self._set_listitem_plot(list_item, item['description'])

                # Apply custom art based on item type
                self._set_custom_art_for_item(list_item, item)

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
            context.logger.error("Error in show_lists_menu: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    def _show_empty_lists_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show menu when no lists exist"""
        if xbmcgui.Dialog().yesno(
            L(35002), # "LibraryGenie"
            "No lists found. Create your first list?" # This string should also be localized
        ):
            create_response = self.create_list(context)
            # Convert DialogResponse to DirectoryResponse
            return DirectoryResponse(
                items=[],
                success=create_response.success
            )

        return DirectoryResponse(items=[], success=True)

    def create_list(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new list"""
        try:
            context.logger.info("Handling create list request")

            # Get list name from user
            list_name = xbmcgui.Dialog().input(
                "Enter list name:", # This string should also be localized
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not list_name or not list_name.strip():
                context.logger.info("User cancelled list creation or entered empty name")
                return DialogResponse(success=False, message="")

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
                    message = f"List '{list_name}' already exists" # This string should also be localized
                else:
                    message = "Failed to create list" # This string should also be localized

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info("Successfully created list: %s", list_name)
                return DialogResponse(
                    success=True,
                    message=f"Created list: {list_name}", # This string should also be localized
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error("Error creating list: %s", e)
            return DialogResponse(
                success=False,
                message="Error creating list" # This string should also be localized
            )

    def delete_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle deleting a list"""
        try:
            context.logger.info("Deleting list %s", list_id)

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
                    message="List not found" # This string should also be localized
                )
            list_name = list_info.get('name', 'Unnamed List')

            # Show confirmation dialog with proper formatting
            dialog_lines = [
                f"Are you sure you want to delete '{list_name}'?",
                "",
                "This will permanently remove the list and all its items.",
                "",
                "This action cannot be undone."
            ]

            confirm = xbmcgui.Dialog().yesno(
                "Delete List",
                "\n".join(dialog_lines)
            )

            if not confirm:
                context.logger.info("User cancelled list deletion")
                return DialogResponse(success=False, message="")

            # Delete the list
            result = query_manager.delete_list(list_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to delete list" # This string should also be localized
                )
            else:
                context.logger.info("Successfully deleted list: %s", list_name)
                return DialogResponse(
                    success=True,
                    message=f"Deleted list: {list_name}", # This string should also be localized
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error("Error deleting list: %s", e)
            return DialogResponse(
                success=False,
                message="Error deleting list" # This string should also be localized
            )

    def rename_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle renaming a list"""
        try:
            context.logger.info("Renaming list %s", list_id)

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
                    message="List not found" # This string should also be localized
                )

            # Get new name from user
            new_name = xbmcgui.Dialog().input(
                "Enter new list name:", # This string should also be localized
                defaultt=list_info['name'],
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                context.logger.info("User cancelled list rename or entered empty name")
                return DialogResponse(success=False, message="")

            # Update the list name
            result = query_manager.rename_list(list_id, new_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{new_name}' already exists" # This string should also be localized
                else:
                    message = "Failed to rename list" # This string should also be localized

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info("Successfully renamed list to: %s", new_name)
                return DialogResponse(
                    success=True,
                    message=f"Renamed list to: {new_name}" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error renaming list: %s", e)
            return DialogResponse(
                success=False,
                message="Error renaming list" # This string should also be localized
            )

    def remove_from_list(self, context: PluginContext, list_id: str, item_id: str) -> DialogResponse:
        """Handle removing an item from a list"""
        try:
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
                # Match using the 'id' field returned by the query
                if str(item.get('id')) == str(item_id):
                    item_info = item
                    break

            if not item_info:
                context.logger.warning("Item %s not found in list %s", item_id, list_id)
                return DialogResponse(
                    success=False,
                    message="Item not found"
                )

            # Confirm removal
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                L(30069),  # "Remove from List"
                f"Remove '{item_info['title']}' from list?"
            ):
                return DialogResponse(success=False, message="")

            # Remove the item
            result = query_manager.delete_item_from_list(list_id, item_id)

            if result:
                context.logger.info("Removed '%s' from list '%s'", item_info['title'], list_info['name'])
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
            context.logger.error("Error removing item from list: %s", e)
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
                "Enter folder name:", # This string should also be localized
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not folder_name or not folder_name.strip():
                context.logger.info("User cancelled folder creation or entered empty name")
                return DialogResponse(success=False, message="")

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
                    message = f"Folder '{folder_name}' already exists" # This string should also be localized
                else:
                    message = "Failed to create folder" # This string should also be localized

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info("Successfully created folder: %s", folder_name)
                return DialogResponse(
                    success=True,
                    message=f"Created folder: {folder_name}", # This string should also be localized
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error("Error creating folder: %s", e)
            return DialogResponse(
                success=False,
                message="Error creating folder" # This string should also be localized
            )

    def rename_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle renaming a folder"""
        try:
            context.logger.info("Renaming folder %s", folder_id)

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
                    message="Folder not found" # This string should also be localized
                )

            # Check if it's a reserved folder
            if folder_info['name'] == 'Search History':
                return DialogResponse(
                    success=False,
                    message="Cannot rename reserved folder" # This string should also be localized
                )

            # Get new name from user
            new_name = xbmcgui.Dialog().input(
                "Enter new folder name:", # This string should also be localized
                defaultt=folder_info['name'],
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                context.logger.info("User cancelled folder rename or entered empty name")
                return DialogResponse(success=False, message="")

            # Update the folder name
            result = query_manager.rename_folder(folder_id, new_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{new_name}' already exists" # This string should also be localized
                else:
                    message = "Failed to rename folder" # This string should also be localized

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info("Successfully renamed folder to: %s", new_name)
                return DialogResponse(
                    success=True,
                    message=f"Renamed folder to: {new_name}" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error renaming folder: %s", e)
            return DialogResponse(
                success=False,
                message="Error renaming folder" # This string should also be localized
            )

    def delete_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle deleting a folder"""
        try:
            context.logger.info("Deleting folder %s", folder_id)

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
                    message="Folder not found" # This string should also be localized
                )

            folder_name = folder_info.get('name', 'Unnamed Folder')

            # Check if it's a reserved folder
            if folder_name == 'Search History':
                return DialogResponse(
                    success=False,
                    message="Cannot delete reserved folder" # This string should also be localized
                )

            # Check if folder has lists
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            num_lists = len(lists_in_folder)

            # Show confirmation dialog
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                L(30072),  # "Delete Folder"
                f"Delete folder: {folder_name}?",
                L(37010)   # "This will also delete all lists in this folder."
            ):
                context.logger.info("User cancelled folder deletion")
                return DialogResponse(success=False, message="")

            # Delete the folder
            result = query_manager.delete_folder(folder_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to delete folder" # This string should also be localized
                )
            else:
                context.logger.info("Successfully deleted folder: %s", folder_name)

                # If deletion was successful, navigate back to lists menu
                # since the current folder no longer exists
                import xbmc
                xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')

                return DialogResponse(
                    success=True,
                    message=f"Deleted folder: {folder_name}", # This string should also be localized
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error("Error deleting folder: %s", e)
            return DialogResponse(
                success=False,
                message="Error deleting folder" # This string should also be localized
            )

    def view_list(self, context: PluginContext, list_id: str) -> DirectoryResponse:
        """Display contents of a specific list"""
        try:
            context.logger.debug("Displaying list %s", list_id)

            # Check for custom parent path to fix navigation from search results
            parent_path = context.get_param('parent_path')
            if parent_path:
                context.logger.debug("Setting custom parent path: %s", parent_path)
                # This will be used by Kodi for the ".." navigation
                xbmcplugin.setProperty(context.addon_handle, 'ParentDir', parent_path)

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
                context.logger.error("List %s not found", list_id)
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get list items
            context.logger.debug("Getting list items from query_manager for list_id=%s", list_id)
            list_items = query_manager.get_list_items(list_id)
            context.logger.debug("Query manager returned %s items", len(list_items))

            context.logger.debug("List '%s' has %s items", list_info['name'], len(list_items))

            # Show breadcrumb notification and render list
            # breadcrumb_path = self.breadcrumb_helper.get_breadcrumb_for_action("show_list", {"list_id": list_id}, self.query_manager)
            breadcrumb_path = self.breadcrumb_helper.get_breadcrumb_for_action("show_list", {"list_id": list_id}, query_manager)

            if breadcrumb_path:
                try:
                    self.breadcrumb_helper.show_breadcrumb_notification(breadcrumb_path)
                    self.logger.debug("LISTS HANDLER: Showed breadcrumb notification: '%s'", breadcrumb_path)
                except Exception as e:
                    self.logger.error("LISTS HANDLER: Failed to show breadcrumb notification: %s", e)

            # self.menu_builder.build_movie_menu(
            #     list_items,
            #     context.addon_handle,
            #     context.base_url,
            #     category=f"List: {list_info['name']}"
            # )


            # Add Tools & Options at the top of the list view using version-aware renderer
            renderer = get_listitem_renderer()
            tools_item = renderer.create_simple_listitem(
                title="[COLOR yellow]⚙️ Tools & Options[/COLOR]",  # "Tools & Options"
                description=L(36016),  # "Access list tools and options"
                action='show_list_tools',
                icon="DefaultAddonProgram.png"
            )
            xbmcplugin.addDirectoryItem(
                context.addon_handle,
                context.build_url('show_list_tools', list_type='user_list', list_id=list_id),
                tools_item,
                True
            )

            if not list_items:
                # Empty list - use version-aware renderer
                renderer = get_listitem_renderer()
                empty_item = renderer.create_simple_listitem(
                    title="[COLOR gray]List is empty[/COLOR]",  # This string should also be localized
                    description='This list contains no items',  # This string should also be localized
                    action='noop'
                )
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )
            else:
                # Build list items
                from .listitem_builder import ListItemBuilder
                builder = ListItemBuilder(context.addon_handle, context.addon.getAddonInfo('id'), context)

                for item_idx, item in enumerate(list_items):
                    try:
                        # The query should return 'id' field from the database
                        # If not present, skip the item entirely
                        if 'id' not in item:
                            context.logger.warning("HANDLER: Skipping list item without ID: %s", item.get('title', 'Unknown'))
                            context.logger.warning("HANDLER: Available keys in item: %s", list(item.keys()))
                            continue

                        # Build context menu for item
                        context_menu = []

                        # Add context menu items - use the 'id' field directly from query
                        context_menu.append((
                            "Remove from List", # This string should also be localized
                            f"RunPlugin({context.build_url('remove_from_list', list_id=list_id, item_id=item['id'])})"
                        ))

                        # Create list item for display using existing builder method
                        result = builder._build_single_item(item)

                        if result:
                            url, listitem, is_folder = result

                            # Add context menu if we have one
                            if context_menu and listitem:
                                try:
                                    listitem.addContextMenuItems(context_menu)

                                except Exception as e:
                                    context.logger.warning("HANDLER: Failed to add context menu: %s", e)

                            # Add to directory
                            xbmcplugin.addDirectoryItem(
                                context.addon_handle,
                                url,
                                listitem,
                                is_folder
                            )
                        else:
                            context.logger.error("HANDLER: Failed to build item for '%s'", item.get('title'))
                            continue

                    except Exception as e:
                        context.logger.error("HANDLER: Error building list item %s: %s", item_idx, e)
                        import traceback
                        context.logger.error("HANDLER: Traceback: %s", traceback.format_exc())
                        continue

            # Detect appropriate content type based on list contents
            detected_content_type = query_manager.detect_content_type(list_items)
            context.logger.debug("Detected content type: %s for %s items", detected_content_type, len(list_items))

            # Set content type and finish directory
            xbmcplugin.setContent(context.addon_handle, detected_content_type)
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )

            return DirectoryResponse(
                items=list_items,
                success=True,
                content_type=detected_content_type
            )

        except Exception as e:
            context.logger.error("Error viewing list: %s", e)
            import traceback
            context.logger.error("Traceback: %s", traceback.format_exc())
            return DirectoryResponse(
                items=[],
                success=False
            )

    def show_folder(self, context: PluginContext, folder_id: str) -> DirectoryResponse:
        """Display contents of a specific folder"""
        try:
            context.logger.debug("Displaying folder %s", folder_id)

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
                context.logger.error("Folder %s not found", folder_id)
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get subfolders in this folder
            subfolders = query_manager.get_all_folders(folder_id)
            context.logger.debug("Folder '%s' has %s subfolders", folder_info['name'], len(subfolders))

            # Get lists in this folder
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            context.logger.debug("Folder '%s' (id=%s) has %s lists", folder_info['name'], folder_id, len(lists_in_folder))

            # Debug: Log each list found
            for lst in lists_in_folder:
                context.logger.debug("  Found list in folder: %s (id=%s, folder_id=%s)", lst['name'], lst['id'], lst.get('folder_id'))

            # Additional debugging: Check if there are any lists with this folder_id in the database
            context.logger.debug("DEBUG: Querying for all lists in folder_id=%s", folder_id)
            debug_lists = query_manager.connection_manager.execute_query("""
                SELECT l.id, l.name, l.folder_id, f.name as folder_name
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                WHERE l.folder_id = ?
            """, [int(folder_id)])
            context.logger.debug("DEBUG: Raw query returned %s lists: %s", len(debug_lists), [dict(row) for row in debug_lists])

            # Also check all lists to see where our list ended up
            all_lists_debug = query_manager.connection_manager.execute_query("""
                SELECT l.id, l.name, l.folder_id, f.name as folder_name
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                ORDER BY l.id
            """)
            context.logger.debug("DEBUG: All lists in database: %s", [dict(row) for row in all_lists_debug])

            # Check for folder ID mismatch
            if len(lists_in_folder) == 0:
                # Try to find if any lists exist with a similar folder name
                orphaned_lists = query_manager.connection_manager.execute_query("""
                    SELECT l.id, l.name, l.folder_id, f.name as folder_name
                    FROM lists l
                    LEFT JOIN folders f ON l.folder_id = f.id
                    WHERE f.name = ?
                """, [folder_info['name']])
                if orphaned_lists:
                    context.logger.warning("Found %s lists with folder name '%s' but different ID: %s", len(orphaned_lists), folder_info['name'], [dict(row) for row in orphaned_lists])

                # Also check for lists that might have the wrong folder_id
                all_folder_refs = query_manager.connection_manager.execute_query("""
                    SELECT DISTINCT folder_id FROM lists WHERE folder_id IS NOT NULL
                """)
                context.logger.debug("All folder_id references in lists table: %s", [row['folder_id'] for row in all_folder_refs])

                all_folder_ids = query_manager.connection_manager.execute_query("""
                    SELECT id, name FROM folders ORDER BY id
                """)
                context.logger.debug("All folders in folders table: %s", [dict(row) for row in all_folder_ids])

            menu_items = []

            # Add Tools & Options for this folder - ensure folder_id is passed for context
            menu_items.append({
                'label': f"[COLOR yellow]{L(36000)}[/COLOR]",  # "Tools & Options"
                'url': context.build_url('show_list_tools', list_type='folder', list_id=folder_id, folder_id=folder_id),
                'is_folder': True,
                'icon': "DefaultAddonProgram.png",
                'description': L(36017) % folder_info['name']  # "Access tools and options for '%s'"
            })

            # Add subfolders in this folder
            for subfolder in subfolders:
                subfolder_id = subfolder.get('id')
                subfolder_name = subfolder.get('name', 'Unnamed Folder')
                list_count = subfolder.get('list_count', 0)

                context_menu = [
                    (f"Rename '{subfolder_name}'", f"RunPlugin({context.build_url('rename_folder', folder_id=subfolder_id)})"),
                    (f"Tools & Options for '{subfolder_name}'", f"RunPlugin({context.build_url('show_list_tools', list_type='folder', list_id=subfolder_id, folder_id=subfolder_id)})"),
                    (f"Delete '{subfolder_name}'", f"RunPlugin({context.build_url('delete_folder', folder_id=subfolder_id)})")
                ]

                menu_items.append({
                    'label': f"[COLOR cyan]📁 {subfolder_name}[/COLOR]",
                    'url': context.build_url('show_folder', folder_id=subfolder_id),
                    'is_folder': True,
                    'description': f"Subfolder with {list_count} lists",
                    'context_menu': context_menu,
                    'icon': "DefaultFolder.png"
                })

            # Add lists in this folder
            for list_item in lists_in_folder:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')
                item_count = list_item.get('item_count', 0)

                context_menu = [
                    (f"Rename '{name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
                    (f"Move '{name}' to Folder", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})"),
                    (f"Export '{name}'", f"RunPlugin({context.build_url('export_list', list_id=list_id)})"),
                    (f"Delete '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': f"[COLOR yellow]{name}[/COLOR]",
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': f"{item_count} items - {description}" if description else f"{item_count} items",
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # If folder is empty, show message using version-aware renderer
            if not lists_in_folder:
                renderer = get_listitem_renderer()
                empty_item = renderer.create_simple_listitem(
                    title="[COLOR gray]Folder is empty[/COLOR]",  # This string should also be localized
                    description='This folder contains no lists',  # This string should also be localized
                    action='noop'
                )
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )

            # Show breadcrumb notification for folder view with proper hierarchy
            breadcrumb_path = self.breadcrumb_helper.get_breadcrumb_for_action('show_folder', {'folder_id': folder_id}, query_manager)
            if breadcrumb_path:
                try:
                    self.breadcrumb_helper.show_breadcrumb_notification(breadcrumb_path)
                    context.logger.debug("LISTS HANDLER: Showed breadcrumb notification: '%s'", breadcrumb_path)
                except Exception as e:
                    context.logger.error("LISTS HANDLER: Failed to show breadcrumb notification: %s", e)

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'])

                if 'description' in item:
                    self._set_listitem_plot(list_item, item['description'])

                # Apply custom art based on item type
                self._set_custom_art_for_item(list_item, item)

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
            context.logger.error("Error showing folder: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    def set_default_list(self, context: PluginContext) -> DialogResponse:
        """Handle setting the default list for quick-add functionality"""
        try:
            context.logger.info("Handling set default list request")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager for set_default_list")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()

            if not all_lists:
                # Offer to create a new list if none exist
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list to set as default?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        # Refresh the list of lists
                        all_lists = query_manager.get_all_lists_with_folders()
                    else:
                        context.logger.warning("Failed to create a new list for default.")
                        return DialogResponse(
                            success=False,
                            message="Failed to create new list" # Localize this string
                        )
                else:
                    context.logger.info("User chose not to create a new list.")
                    return DialogResponse(success=False, message="")

            if not all_lists:  # Still no lists
                return DialogResponse(
                    success=False,
                    message="No lists available to set as default" # Localize this string
                )

            # Build list options for selection
            list_options = []
            list_ids = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    display_name = lst['name']
                else:
                    display_name = f"{folder_name}/{lst['name']}"
                list_options.append(f"{display_name} ({lst['item_count']} items)")
                list_ids.append(lst['id'])

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]") # Localize this string

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Set Default Quick-Add List:", list_options) # Localize this string

            if selected_index < 0:
                context.logger.info("User cancelled setting default list.")
                return DialogResponse(success=False, message="")

            target_list_id = None
            if selected_index == len(list_options) - 1:  # User chose to create a new list
                result = self.create_list(context)
                if not result.success:
                    context.logger.warning("Failed to create new list for default.")
                    return DialogResponse(
                        success=False,
                        message="Failed to create new list" # Localize this string
                    )
                # Get the newly created list ID
                all_lists = query_manager.get_all_lists_with_folders()  # Refresh lists
                if all_lists:
                    target_list_id = all_lists[-1]['id']  # Assume last created
                else:
                    context.logger.error("Could not retrieve newly created list ID.")
                    return DialogResponse(
                        success=False,
                        message="Could not retrieve newly created list" # Localize this string
                    )
            else:
                target_list_id = list_ids[selected_index]

            if target_list_id is None:
                context.logger.error("Target list ID is None.")
                return DialogResponse(
                    success=False,
                    message="Invalid list selection" # Localize this string
                )

            # Set the default list ID in settings
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            settings.set_default_list_id(target_list_id)

            # Get list name for confirmation message
            selected_list_name = list_options[selected_index].split(' (')[0] if selected_index < len(list_options) - 1 else "newly created list"

            context.logger.info("Set default quick-add list to: %s", selected_list_name)
            return DialogResponse(
                success=True,
                message=f"Default quick-add list set to: '{selected_list_name}'" # Localize this string
            )

        except Exception as e:
            context.logger.error("Error in set_default_list: %s", e)
            return DialogResponse(
                success=False,
                message="Failed to set default list" # Localize this string
            )

    def add_to_list_menu(self, context: PluginContext, media_item_id: str) -> bool:
        """Handle adding media item to a list"""
        try:
            if not media_item_id:
                context.logger.error("No media item ID provided")
                return False

            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return False

            # Get all available lists, excluding special lists
            all_lists = query_manager.get_all_lists_with_folders()
            available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
            if not available_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        # Refresh lists and continue
                        all_lists = query_manager.get_all_lists_with_folders()
                        available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                    else:
                        return False
                else:
                    return False

            # Build list options for selection
            list_options = []
            for lst in available_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(f"{lst['name']} ({lst['item_count']} items)")
                else:
                    list_options.append(f"{folder_name}/{lst['name']} ({lst['item_count']} items)")

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]") # Localize this string

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options) # Localize this string

            if selected_index < 0:
                return False

            # Handle selection
            if selected_index == len(list_options) - 1:  # Create new list
                result = self.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                if available_lists:
                    target_list_id = available_lists[-1]['id']  # Assume last created
                else:
                    return False
            else:
                target_list_id = available_lists[selected_index]['id']

            # Add item to selected list
            result = query_manager.add_item_to_list(target_list_id, media_item_id)

            if result is not None and result.get("success"):
                list_name = available_lists[selected_index]['name'] if selected_index < len(available_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error") if result else "Query manager returned None"
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list", # Localize this string
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Failed to add to list: {error_msg}", # Localize this string
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            context.logger.error("Error adding to list: %s", e)
            return False

    def add_library_item_to_list_context(self, context: PluginContext) -> bool:
        """Handle adding library item to a list from context menu"""
        try:
            # Get library item parameters
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')

            if not dbtype or not dbid:
                context.logger.error("Missing dbtype or dbid for library item")
                return False

            context.logger.info("Adding library item to list: dbtype=%s, dbid=%s", dbtype, dbid)

            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager for library item add")
                return False

            # Get all available lists, excluding special lists
            all_lists = query_manager.get_all_lists_with_folders()
            available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
            if not available_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                        available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                    else:
                        return False
                else:
                    return False

            if not available_lists: # Still no lists after offering to create
                xbmcgui.Dialog().notification("LibraryGenie", "No lists available to add to.", xbmcgui.NOTIFICATION_WARNING) # Localize strings
                return False

            # Build list options for selection
            list_options = []
            for lst in available_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(f"{lst['name']} ({lst['item_count']} items)")
                else:
                    list_options.append(f"{folder_name}/{lst['name']} ({lst['item_count']} items)")

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]") # Localize this string

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options) # Localize this string

            if selected_index < 0:
                return False # User cancelled

            # Handle selection
            target_list_id = None
            if selected_index == len(list_options) - 1:  # Create new list
                result = self.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                if available_lists:
                    target_list_id = available_lists[-1]['id']  # Assume last created
                else:
                    return False
            else:
                target_list_id = available_lists[selected_index]['id']

            if target_list_id is None:
                return False

            # Check if item already exists in media_items table
            library_item = None
            existing_item = None

            if dbtype == 'movie':
                existing_item = query_manager.connection_manager.execute_single("""
                    SELECT * FROM media_items WHERE kodi_id = ? AND media_type = 'movie'
                """, [int(dbid)])

                if existing_item:
                    library_item = dict(existing_item)
                    library_item['source'] = 'lib'
                else:
                    # Item not in database yet - create minimal entry
                    library_item = {
                        'kodi_id': int(dbid),
                        'media_type': 'movie',
                        'title': f'Movie {dbid}',  # Placeholder, will be enriched later
                        'year': 0,
                        'source': 'lib'
                    }

            elif dbtype == 'episode':
                existing_item = query_manager.connection_manager.execute_single("""
                    SELECT * FROM media_items WHERE kodi_id = ? AND media_type = 'episode'
                """, [int(dbid)])

                if existing_item:
                    library_item = dict(existing_item)
                    library_item['source'] = 'lib'
                else:
                    # Item not in database yet - create minimal entry
                    library_item = {
                        'kodi_id': int(dbid),
                        'media_type': 'episode',
                        'title': f'Episode {dbid}',  # Placeholder, will be enriched later
                        'source': 'lib'
                    }

            if not library_item:
                context.logger.error("Unsupported dbtype: %s", dbtype)
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Unsupported item type: {dbtype}", # Localize this string
                    xbmcgui.NOTIFICATION_ERROR
                )
                return False

            # Add library item to selected list
            result = query_manager.add_library_item_to_list(target_list_id, library_item)

            if result is not None:
                list_name = available_lists[selected_index]['name'] if selected_index < len(available_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added '{library_item['title']}' to '{list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Failed to add item to list", # Localize this string
                    xbmcgui.NOTIFICATION_ERROR
                )
                return False

        except Exception as e:
            context.logger.error("Error adding library item to list from context: %s", e)
            import traceback
            context.logger.error("Traceback: %s", traceback.format_exc())
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Error: {str(e)}", # Localize this string
                xbmcgui.NOTIFICATION_ERROR
            )
            return False

    def add_to_list_context(self, context: PluginContext) -> bool:
        """Handle adding media item to a list from context menu"""
        try:
            media_item_id = context.get_param('media_item_id')
            if not media_item_id:
                context.logger.error("No media item ID provided for context menu add")
                return False

            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager for context menu add")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                    else:
                        return False
                else:
                    return False

            if not all_lists: # Still no lists after offering to create
                xbmcgui.Dialog().notification("LibraryGenie", "No lists available to add to.", xbmcgui.NOTIFICATION_WARNING) # Localize strings
                return False

            # Build list options for selection
            list_options = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(f"{lst['name']} ({lst['item_count']} items)")
                else:
                    list_options.append(f"{folder_name}/{lst['name']} ({lst['item_count']} items)")

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]") # Localize this string

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options) # Localize this string

            if selected_index < 0:
                return False # User cancelled

            # Handle selection
            target_list_id = None
            if selected_index == len(list_options) - 1:  # Create new list
                result = self.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                if all_lists:
                    target_list_id = all_lists[-1]['id']  # Assume last created
                else:
                    return False # Should not happen if create_list succeeded
            else:
                target_list_id = all_lists[selected_index]['id']

            if target_list_id is None:
                return False

            # Add item to selected list
            result = query_manager.add_item_to_list(target_list_id, media_item_id)

            if result is not None and result.get("success"):
                list_name = all_lists[selected_index]['name'] if selected_index < len(all_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error") if result else "Query manager returned None"
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list", # Localize this string
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Failed to add to list: {error_msg}", # Localize this string
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            context.logger.error("Error adding to list from context: %s", e)
            return False

    def quick_add_context(self, context: PluginContext) -> bool:
        """Handle quick add to default list from context menu"""
        try:
            # Get parameters
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')

            # Get settings
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            default_list_id = settings.get_default_list_id()

            if not default_list_id:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "No default list configured", # Localize this string
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return False

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                return False

            # Create external item data
            external_item = {
                'title': context.get_param('title', 'Unknown'),
                'dbtype': dbtype,
                'dbid': dbid,
                'source': 'context_menu'
            }

            # Add to default list
            result = query_manager.add_library_item_to_list(default_list_id, external_item)
            return result is not None

        except Exception as e:
            context.logger.error("Error quick adding to list from context: %s", e)
            return False

    def add_external_item_to_list(self, context: PluginContext) -> bool:
        """Handle adding external/plugin item to a list"""
        try:
            # Extract external item data from URL parameters
            external_data = {}
            for key, value in context.get_params().items():
                if key not in ('action', 'external_item'):
                    external_data[key] = value

            if not external_data.get('title'):
                context.logger.error("No title found for external item")
                return False

            # Convert to format expected by add_to_list system
            media_item = {
                'id': f"external_{hash(external_data.get('file_path', external_data['title']))}",
                'title': external_data['title'],
                'media_type': external_data.get('media_type', 'movie'),
                'source': 'external'
            }

            # Copy over all the gathered metadata
            for key in ['originaltitle', 'year', 'plot', 'rating', 'votes', 'genre',
                       'director', 'studio', 'country', 'mpaa', 'runtime', 'premiered',
                       'playcount', 'lastplayed', 'poster', 'fanart', 'thumb',
                       'banner', 'clearlogo', 'imdbnumber', 'file_path']:
                if key in external_data:
                    media_item[key] = external_data[key]

            # Episode-specific fields
            if external_data.get('media_type') == 'episode':
                for key in ['tvshowtitle', 'season', 'episode', 'aired']:
                    if key in external_data:
                        media_item[key] = external_data[key]

            # Music video-specific fields
            elif external_data.get('media_type') == 'musicvideo':
                for key in ['artist', 'album']:
                    if key in external_data:
                        media_item[key] = external_data[key]

            context.logger.info("Processing external item: %s (type: %s)", media_item['title'], media_item['media_type'])

            # Use existing add_to_list flow with the external media item
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        # Refresh lists and continue
                        all_lists = query_manager.get_all_lists_with_folders()
                    else:
                        return False
                else:
                    return False

            # Build list selection options
            list_options = []
            list_ids = []

            for item in all_lists:
                if item.get('type') == 'list':
                    list_name = item['name']
                    list_options.append(list_name)
                    list_ids.append(item['id'])

            if not list_options:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "No lists available", # Localize this string
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return False

            # Show list selection dialog
            selected_index = xbmcgui.Dialog().select(
                f"Add '{media_item['title']}' to list:", # Localize this string
                list_options
            )

            if selected_index < 0:
                return False  # User cancelled

            selected_list_id = list_ids[selected_index]
            selected_list_name = list_options[selected_index]

            # Add the external item to the selected list
            result = query_manager.add_item_to_list(selected_list_id, media_item)
            success = result is not None and result.get("success", False)

            if success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added '{media_item['title']}' to '{selected_list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                # Refresh container to show changes
                import xbmc
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Failed to add item to list", # Localize this string
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False

        except Exception as e:
            context.logger.error("Error in add_external_item_to_list: %s", e)
            return False

    def remove_library_item_from_list(self, context: PluginContext, list_id: str, dbtype: str, dbid: str) -> bool:
        """Handle removing a library item from a list using dbtype and dbid"""
        try:
            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return False

            # Get list items to find the matching item
            list_items = query_manager.get_list_items(list_id)
            matching_item = None

            for item in list_items:
                if (item.get('kodi_id') == int(dbid) and
                    item.get('media_type') == dbtype):
                    matching_item = item
                    break

            if not matching_item or 'id' not in matching_item:
                context.logger.warning("Could not find library item %s:%s in list %s", dbtype, dbid, list_id)
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Item not found in list",
                    xbmcgui.NOTIFICATION_WARNING
                )
                return False

            # Use the regular remove method with the found item ID
            response = self.remove_from_list(context, list_id, str(matching_item['id']))

            # Handle the DialogResponse
            from .response_types import DialogResponse
            from .response_handler import get_response_handler

            if isinstance(response, DialogResponse):
                response_handler = get_response_handler()
                response_handler.handle_dialog_response(response, context)
                return response.success

            return False

        except Exception as e:
            context.logger.error("Error removing library item from list: %s", e)
            return False