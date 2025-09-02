
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
from .localization import L
from ..utils.logger import get_logger
from ..import_export.export_engine import get_export_engine


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
                    message=L(30504)  # "Operation failed"
                )

        except Exception as e:
            self.logger.error(f"Error showing list tools: {e}")
            return DialogResponse(
                success=False,
                message=context.addon.getLocalizedString(30504)  # "Operation failed"
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
            scan_option = f"[COLOR white]🔄 {L(36001)}[/COLOR]"  # "Scan Favorites"
            
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
                    
                    scan_option = f"[COLOR white]🔄 {L(36001)} ({time_ago})[/COLOR]"  # "Scan Favorites"
                except Exception as e:
                    context.logger.debug(f"Could not parse last scan time: {e}")

            # Build options for favorites - organized by type
            options = [
                # Refresh operations
                scan_option,
                # Additive operations  
                f"[COLOR lightgreen]💾 {L(36002)}[/COLOR]",  # "Save As New List"
                # Cancel
                f"[COLOR gray]❌ {L(36003)}[/COLOR]"  # "Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36013), options)  # "Favorites Tools & Options"

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

            # Build comprehensive options for user lists - organized by operation type
            options = [
                # Additive operations
                f"[COLOR lightgreen]🔀 {L(36004) % list_info['name']}[/COLOR]",  # "Merge Another List Into '%s'"
                # Modify operations
                f"[COLOR yellow]✏️ {L(36005) % list_info['name']}[/COLOR]",  # "Rename '%s'"
                f"[COLOR yellow]📁 {L(36006) % list_info['name']}[/COLOR]",  # "Move '%s' to Folder"
                # Export operations
                f"[COLOR white]📤 {L(36007) % list_info['name']}[/COLOR]",  # "Export '%s'"
                # Destructive operations
                f"[COLOR red]🗑️ {L(36008) % list_info['name']}[/COLOR]",  # "Delete '%s'"
                # Cancel
                f"[COLOR gray]❌ {L(36003)}[/COLOR]"  # "Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36014), options)  # "List Tools & Options"

            if selected_index < 0 or selected_index == 5:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if selected_index == 0:  # Merge lists
                return self._merge_lists(context, list_id)
            elif selected_index == 1:  # Rename
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.rename_list(context, list_id)
            elif selected_index == 2:  # Move to folder
                return self._move_list_to_folder(context, list_id)
            elif selected_index == 3:  # Export
                return self._export_single_list(context, list_id)
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

            # Build comprehensive options for folders - organized by operation type
            options = []
            
            # Additive operations (always available)
            options.extend([
                f"[COLOR lightgreen]📋 {L(36009) % folder_info['name']}[/COLOR]",  # "Create New List in '%s'"
                f"[COLOR lightgreen]📁 {L(36010) % folder_info['name']}[/COLOR]"  # "Create New Subfolder in '%s'"
            ])
            
            # Modify operations (not for reserved folders)
            if not is_reserved:
                options.extend([
                    f"[COLOR yellow]✏️ {L(36005) % folder_info['name']}[/COLOR]",  # "Rename '%s'"
                    f"[COLOR yellow]📁 {L(36011) % folder_info['name']}[/COLOR]"  # "Move '%s' to Parent Folder"
                ])
            
            # Export operations
            options.append(f"[COLOR white]📤 {L(36012) % folder_info['name']}[/COLOR]")  # "Export All Lists in '%s'"
            
            # Destructive operations (not for reserved folders)
            if not is_reserved:
                options.append(f"[COLOR red]🗑️ {L(36008) % folder_info['name']}[/COLOR]")  # "Delete '%s'"
            
            # Cancel
            options.append(f"[COLOR gray]❌ {L(36003)}[/COLOR]")  # "Cancel"

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36015), options)  # "Folder Tools & Options"

            if selected_index < 0 or selected_index == len(options) - 1:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option - calculate indices based on reserved status
            if is_reserved:
                # Reserved folder: Create List(0), Create Subfolder(1), Export(2), Cancel(3)
                if selected_index == 0:  # Create new list
                    return self._create_list_in_folder(context, folder_id)
                elif selected_index == 1:  # Create subfolder
                    return self._create_subfolder(context, folder_id)
                elif selected_index == 2:  # Export
                    return self._export_folder_lists(context, folder_id)
            else:
                # Regular folder: Create List(0), Create Subfolder(1), Rename(2), Move(3), Export(4), Delete(5), Cancel(6)
                if selected_index == 0:  # Create new list
                    return self._create_list_in_folder(context, folder_id)
                elif selected_index == 1:  # Create subfolder
                    return self._create_subfolder(context, folder_id)
                elif selected_index == 2:  # Rename
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    return lists_handler.rename_folder(context, folder_id)
                elif selected_index == 3:  # Move folder
                    return self._move_folder(context, folder_id)
                elif selected_index == 4:  # Export
                    return self._export_folder_lists(context, folder_id)
                elif selected_index == 5:  # Delete
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    return lists_handler.delete_folder(context, folder_id)

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
            selected_index = dialog.select(L(36029), folder_options)  # "Select destination folder:"

            if selected_index < 0:
                return DialogResponse(success=False)

            # Move list
            target_folder_id = None if selected_index == 0 else all_folders[selected_index - 1]['id']
            result = query_manager.move_list_to_folder(list_id, target_folder_id)

            if result.get("success"):
                folder_name = L(36032) if target_folder_id is None else folder_options[selected_index]  # "root level"
                return DialogResponse(
                    success=True,
                    message=L(36033) % folder_name,  # "Moved list to %s"
                    refresh_needed=True
                )
            else:
                return DialogResponse(success=False, message=L(36035))  # "Failed to move list"

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
            selected_index = dialog.select(L(36028), list_options)  # "Select list to merge:"

            if selected_index < 0:
                return DialogResponse(success=False)

            source_list = source_lists[selected_index]

            # Confirm merge
            if not dialog.yesno(
                L(36021),  # "Confirm Merge"
                L(36022) % source_list['name'],  # "Merge '%s' into target list?"
                L(36023) % source_list['item_count'],  # "This will add %d items."
                L(36024)  # "The source list will remain unchanged."
            ):
                return DialogResponse(success=False)

            # Perform merge
            result = query_manager.merge_lists(source_list['id'], target_list_id)

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message=L(36025) % result.get('items_added', 0),  # "Merged %d new items"
                    refresh_needed=True
                )
            else:
                return DialogResponse(success=False, message=L(36026))  # "Failed to merge lists"

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

    def _export_single_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Export a single list"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get list info for confirmation
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(success=False, message="List not found")

            # Get export engine
            export_engine = get_export_engine()

            # Run export
            result = export_engine.export_data(
                export_types=["lists", "list_items"],
                file_format="json"
            )

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message=f"Exported '{list_info['name']}' to {result['filename']}",
                    refresh_needed=False
                )
            else:
                return DialogResponse(
                    success=False,
                    message=f"Export failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"Error exporting single list: {e}")
            return DialogResponse(success=False, message="Error exporting list")

    def _export_folder_lists(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Export all lists in a folder"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get folder info for confirmation
            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(success=False, message="Folder not found")

            # Get lists in folder count for user info
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            list_count = len(lists_in_folder) if lists_in_folder else 0

            if list_count == 0:
                return DialogResponse(
                    success=False,
                    message=f"No lists found in folder '{folder_info['name']}'"
                )

            # Confirm export
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                "Confirm Export",
                f"Export all {list_count} lists from '{folder_info['name']}'?",
                "This will include all list items and metadata."
            ):
                return DialogResponse(success=False)

            # Get export engine
            export_engine = get_export_engine()

            # Run export
            result = export_engine.export_data(
                export_types=["lists", "list_items"],
                file_format="json"
            )

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message=f"Exported {list_count} lists from '{folder_info['name']}' to {result['filename']}",
                    refresh_needed=False
                )
            else:
                return DialogResponse(
                    success=False,
                    message=f"Export failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"Error exporting folder lists: {e}")
            return DialogResponse(success=False, message="Error exporting folder lists")
