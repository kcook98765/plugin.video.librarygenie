
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Tools Handler
Modular tools and options handler for different list types
"""

import xbmcgui
from datetime import datetime
from typing import List, Dict, Any, Optional
from .plugin_context import PluginContext
from .response_types import DialogResponse
from ..utils.logger import get_logger


class ToolsHandler:
    """Modular tools and options handler"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def show_list_tools(self, context: PluginContext, list_type: str, list_id: Optional[str] = None) -> DialogResponse:
        """Show tools & options modal for different list types"""
        try:
            self.logger.info(f"Showing tools & options for list_type: {list_type}, list_id: {list_id}")

            if list_type == "favorites":
                return self._show_favorites_tools(context)
            elif list_type == "user_list" and list_id:
                return self._show_user_list_tools(context, list_id)
            elif list_type == "folder" and list_id:
                return self._show_folder_tools(context, list_id)
            else:
                return DialogResponse(
                    success=False,
                    message="Unknown list type"
                )

        except Exception as e:
            self.logger.error(f"Error showing list tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing tools & options"
            )

    def _show_favorites_tools(self, context: PluginContext) -> DialogResponse:
        """Show tools specific to Kodi favorites"""
        try:
            # Get last scan info for display
            favorites_manager = context.favorites_manager
            if not favorites_manager:
                return DialogResponse(
                    success=False,
                    message="Failed to initialize favorites manager"
                )

            last_scan_info = favorites_manager._get_last_scan_info_for_display()
            scan_option = "🔄 Scan Favorites"
            
            if last_scan_info:
                try:
                    last_scan_time = datetime.fromisoformat(last_scan_info['created_at'])
                    current_time = datetime.now()
                    time_diff = current_time - last_scan_time
                    
                    if time_diff.total_seconds() < 60:
                        time_ago = "just now"
                    elif time_diff.total_seconds() < 3600:
                        minutes = int(time_diff.total_seconds() / 60)
                        time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    elif time_diff.total_seconds() < 86400:
                        hours = int(time_diff.total_seconds() / 3600)
                        time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    else:
                        days = int(time_diff.total_seconds() / 86400)
                        time_ago = f"{days} day{'s' if days != 1 else ''} ago"
                    
                    scan_option = f"🔄 Scan Favorites ({time_ago})"
                except Exception as e:
                    context.logger.debug(f"Could not parse last scan time: {e}")

            # Build options for favorites
            options = [
                scan_option,
                "💾 Save As New List",
                "❌ Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Favorites Tools & Options", options)

            if selected_index < 0 or selected_index == 2:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if selected_index == 0:  # Scan Favorites
                from .favorites_handler import FavoritesHandler
                favorites_handler = FavoritesHandler()
                return favorites_handler.scan_favorites(context)
            elif selected_index == 1:  # Save As
                from .favorites_handler import FavoritesHandler
                favorites_handler = FavoritesHandler()
                return favorites_handler.save_favorites_as(context)

            return DialogResponse(success=False)

        except Exception as e:
            self.logger.error(f"Error showing favorites tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing favorites tools"
            )

    def _show_user_list_tools(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Show tools specific to user lists"""
        try:
            # Get list info
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message="List not found"
                )

            # Build comprehensive options for user lists
            options = [
                f"✏️ Rename '{list_info['name']}'",
                f"📁 Move '{list_info['name']}' to Folder",
                f"🔀 Merge Another List Into '{list_info['name']}'",
                f"📤 Export '{list_info['name']}'",
                f"🗑️ Delete '{list_info['name']}'",
                "❌ Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("List Tools & Options", options)

            if selected_index < 0 or selected_index == 5:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if selected_index == 0:  # Rename
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.rename_list(context, list_id)
            elif selected_index == 1:  # Move to folder
                return self._move_list_to_folder(context, list_id)
            elif selected_index == 2:  # Merge lists
                return self._merge_lists(context, list_id)
            elif selected_index == 3:  # Export
                # TODO: Implement export functionality
                return DialogResponse(
                    success=False,
                    message="Export functionality coming soon"
                )
            elif selected_index == 4:  # Delete
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.delete_list(context, list_id)

            return DialogResponse(success=False)

        except Exception as e:
            self.logger.error(f"Error showing user list tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing list tools"
            )

    def _show_folder_tools(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Show tools specific to folders"""
        try:
            # Get folder info
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message="Folder not found"
                )

            # Check if it's a reserved folder
            is_reserved = folder_info['name'] == 'Search History'

            # Build comprehensive options for folders
            options = []
            if not is_reserved:
                options.extend([
                    f"✏️ Rename '{folder_info['name']}'",
                    f"📁 Move '{folder_info['name']}' to Parent Folder",
                    f"🗑️ Delete '{folder_info['name']}'"
                ])
            
            options.extend([
                f"📤 Export All Lists in '{folder_info['name']}'",
                f"📋 Create New List in '{folder_info['name']}'",
                f"📁 Create New Subfolder in '{folder_info['name']}'",
                "❌ Cancel"
            ])

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Folder Tools & Options", options)

            if selected_index < 0 or selected_index == len(options) - 1:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option based on reserved status
            if not is_reserved:
                if selected_index == 0:  # Rename
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    return lists_handler.rename_folder(context, folder_id)
                elif selected_index == 1:  # Move folder
                    return self._move_folder(context, folder_id)
                elif selected_index == 2:  # Delete
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    return lists_handler.delete_folder(context, folder_id)
                elif selected_index == 3:  # Export
                    # TODO: Implement export functionality
                    return DialogResponse(
                        success=False,
                        message="Export functionality coming soon"
                    )
                elif selected_index == 4:  # Create new list
                    return self._create_list_in_folder(context, folder_id)
                elif selected_index == 5:  # Create subfolder
                    return self._create_subfolder(context, folder_id)
            else:
                # Reserved folder options
                if selected_index == 0:  # Export
                    return DialogResponse(
                        success=False,
                        message="Export functionality coming soon"
                    )
                elif selected_index == 1:  # Create new list
                    return self._create_list_in_folder(context, folder_id)
                elif selected_index == 2:  # Create subfolder
                    return self._create_subfolder(context, folder_id)

            return DialogResponse(success=False)

        except Exception as e:
            self.logger.error(f"Error showing folder tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing folder tools"
            )

    def _move_list_to_folder(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Move a list to a different folder"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get available folders
            all_folders = query_manager.get_all_folders()
            folder_options = ["[Root Level]"] + [f['name'] for f in all_folders if f['name'] != 'Search History']

            # Show folder selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Select destination folder:", folder_options)

            if selected_index < 0:
                return DialogResponse(success=False)

            # Move list
            target_folder_id = None if selected_index == 0 else all_folders[selected_index - 1]['id']
            result = query_manager.move_list_to_folder(list_id, target_folder_id)

            if result.get("success"):
                folder_name = "root level" if target_folder_id is None else folder_options[selected_index]
                return DialogResponse(
                    success=True,
                    message=f"Moved list to {folder_name}",
                    refresh_needed=True
                )
            else:
                return DialogResponse(success=False, message="Failed to move list")

        except Exception as e:
            self.logger.error(f"Error moving list to folder: {e}")
            return DialogResponse(success=False, message="Error moving list")

    def _merge_lists(self, context: PluginContext, target_list_id: str) -> DialogResponse:
        """Merge another list into the target list"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get all lists except the target
            all_lists = query_manager.get_all_lists_with_folders()
            source_lists = [l for l in all_lists if str(l['id']) != str(target_list_id)]

            if not source_lists:
                return DialogResponse(success=False, message="No other lists available to merge")

            # Build list options
            list_options = [f"{l['name']} ({l['item_count']} items)" for l in source_lists]

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Select list to merge:", list_options)

            if selected_index < 0:
                return DialogResponse(success=False)

            source_list = source_lists[selected_index]

            # Confirm merge
            if not dialog.yesno(
                "Confirm Merge",
                f"Merge '{source_list['name']}' into target list?",
                f"This will add {source_list['item_count']} items.",
                "The source list will remain unchanged."
            ):
                return DialogResponse(success=False)

            # Perform merge
            result = query_manager.merge_lists(source_list['id'], target_list_id)

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message=f"Merged {result.get('items_added', 0)} new items",
                    refresh_needed=True
                )
            else:
                return DialogResponse(success=False, message="Failed to merge lists")

        except Exception as e:
            self.logger.error(f"Error merging lists: {e}")
            return DialogResponse(success=False, message="Error merging lists")

    def _move_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Move a folder to a different parent folder"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get available parent folders (excluding self and children)
            all_folders = query_manager.get_all_folders()
            folder_options = ["[Root Level]"]
            
            for f in all_folders:
                if str(f['id']) != str(folder_id) and f['name'] != 'Search History':
                    folder_options.append(f['name'])

            # Show folder selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Select parent folder:", folder_options)

            if selected_index < 0:
                return DialogResponse(success=False)

            # Move folder
            target_parent_id = None if selected_index == 0 else all_folders[selected_index - 1]['id']
            result = query_manager.move_folder(folder_id, target_parent_id)

            if result.get("success"):
                parent_name = "root level" if target_parent_id is None else folder_options[selected_index]
                return DialogResponse(
                    success=True,
                    message=f"Moved folder to {parent_name}",
                    refresh_needed=True
                )
            else:
                return DialogResponse(success=False, message="Failed to move folder")

        except Exception as e:
            self.logger.error(f"Error moving folder: {e}")
            return DialogResponse(success=False, message="Error moving folder")

    def _create_list_in_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Create a new list in the specified folder"""
        try:
            # Get list name from user
            list_name = xbmcgui.Dialog().input(
                "Enter list name:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not list_name or not list_name.strip():
                return DialogResponse(success=False)

            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            result = query_manager.create_list(list_name.strip(), folder_id)

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{list_name}' already exists in this folder"
                else:
                    message = "Failed to create list"
                return DialogResponse(success=False, message=message)
            else:
                return DialogResponse(
                    success=True,
                    message=f"Created list: {list_name}",
                    refresh_needed=True
                )

        except Exception as e:
            self.logger.error(f"Error creating list in folder: {e}")
            return DialogResponse(success=False, message="Error creating list")

    def _create_subfolder(self, context: PluginContext, parent_folder_id: str) -> DialogResponse:
        """Create a new subfolder in the specified parent folder"""
        try:
            # Get folder name from user
            folder_name = xbmcgui.Dialog().input(
                "Enter folder name:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not folder_name or not folder_name.strip():
                return DialogResponse(success=False)

            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            result = query_manager.create_folder(folder_name.strip(), parent_folder_id)

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{folder_name}' already exists in this location"
                else:
                    message = "Failed to create folder"
                return DialogResponse(success=False, message=message)
            else:
                return DialogResponse(
                    success=True,
                    message=f"Created subfolder: {folder_name}",
                    refresh_needed=True
                )

        except Exception as e:
            self.logger.error(f"Error creating subfolder: {e}")
            return DialogResponse(success=False, message="Error creating subfolder")
