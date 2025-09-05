#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Tools Handler
Modular tools and options handler for different list types
"""

import xbmcgui
from datetime import datetime
from typing import Dict, Any, Optional
from .plugin_context import PluginContext
from .response_types import DialogResponse
from .localization_helper import L
from ..utils.logger import get_logger
from ..import_export.export_engine import get_export_engine
from ..kodi.favorites_manager import get_phase4_favorites_manager



class ToolsHandler:
    """Modular tools and options handler"""

    def __init__(self, context: Optional[PluginContext] = None):
        self.logger = get_logger(__name__)
        try:
            from .listitem_builder import ListItemBuilder
            if context:
                self.listitem_builder = ListItemBuilder(
                    addon_handle=context.addon_handle,
                    addon_id=context.addon.getAddonInfo('id')
                )
            else:
                self.listitem_builder = None
        except ImportError:
            self.listitem_builder = None

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
            elif list_type == "lists_main":
                return self._show_lists_main_tools(context)
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
            scan_option = f"[COLOR white]{L(36001)}[/COLOR]"  # "Scan Favorites"

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

                    scan_option = f"[COLOR white]{L(36001)} ({time_ago})[/COLOR]"  # "Scan Favorites"
                except Exception as e:
                    context.logger.debug(f"Could not parse last scan time: {e}")

            # Build options for favorites - organized by type
            options = [
                # Refresh operations
                scan_option,
                # Additive operations
                f"[COLOR lightgreen]{L(36002)}[/COLOR]",  # "Save As New List"
                # Cancel
                f"[COLOR gray]{L(36003)}[/COLOR]"  # "Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36013), list(options))  # "Favorites Tools & Options"

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

            # Check if this is a search history list
            is_search_history = list_info.get('folder_name') == 'Search History'

            # Helper function to shorten names for context menus
            def shorten_name_for_menu(name: str, max_length: int = 30) -> str:
                if len(name) <= max_length:
                    return name

                # For search history, extract just the search terms
                if name.startswith("Search: '") and "' (" in name:
                    search_part = name.split("' (")[0].replace("Search: '", "")
                    if len(search_part) <= max_length - 3:
                        return f"'{search_part}'"
                    else:
                        return f"'{search_part[:max_length-6]}...'"

                # For regular names, just truncate
                return f"{name[:max_length-3]}..."

            short_name = shorten_name_for_menu(list_info['name'])

            if is_search_history:
                # Special options for search history lists
                options = [
                    "[COLOR lightgreen]📋 Copy to New List[/COLOR]",
                    f"[COLOR white]{L(36053) % short_name}[/COLOR]",  # "Export %s"
                    f"[COLOR red]{L(36054) % short_name}[/COLOR]",  # "Delete %s"
                    f"[COLOR gray]{L(36003)}[/COLOR]"  # "Cancel"
                ]
            else:
                # Standard list options
                options = [
                    # Additive operations
                    f"[COLOR lightgreen]{L(36004) % short_name}[/COLOR]",  # "Merge Into %s"
                    # Modify operations
                    f"[COLOR yellow]{L(36051) % short_name}[/COLOR]",  # "Rename %s"
                    f"[COLOR yellow]{L(36052) % short_name}[/COLOR]",  # "Move %s to Folder"
                    # Export operations
                    f"[COLOR white]{L(36053) % short_name}[/COLOR]",  # "Export %s"
                    # Destructive operations
                    f"[COLOR red]{L(36054) % short_name}[/COLOR]",  # "Delete %s"
                    # Cancel
                    f"[COLOR gray]{L(36003)}[/COLOR]"  # "Cancel"
                ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36014), list(options))  # "List Tools & Options"

            if selected_index < 0 or selected_index == len(options) - 1:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if is_search_history:
                # Search history list: Copy(0), Export(1), Delete(2), Cancel(3)
                if selected_index == 0:  # Copy to new list
                    return self._copy_search_history_to_list(context, list_id)
                elif selected_index == 1:  # Export
                    return self._export_single_list(context, list_id)
                elif selected_index == 2:  # Delete
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    result = lists_handler.delete_list(context, list_id)

                    # For search history deletion, check if this was the last list in the folder
                    if result.success:
                        search_folder_id = query_manager.get_or_create_search_history_folder()
                        remaining_lists = query_manager.get_lists_in_folder(search_folder_id)

                        if remaining_lists:
                            # Still have search history lists, navigate back to folder
                            result.navigate_to_folder = search_folder_id
                        else:
                            # No more search history lists, navigate back to main menu
                            result.navigate_to_main = True

                    return result
            else:
                # Standard list: Merge(0), Rename(1), Move(2), Export(3), Delete(4), Cancel(5)
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
                    result = lists_handler.delete_list(context, list_id)

                    # For regular list deletion, set flag to navigate back to lists menu
                    if result.success:
                        result.navigate_to_lists = True

                    return result

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

            if is_reserved:
                # Special options for Search History folder
                options.extend([
                    f"[COLOR white]{L(36012) % folder_info['name']}[/COLOR]",  # "Export All Lists in '%s'"
                    "[COLOR yellow]Clear All Search History[/COLOR]"
                ])
            else:
                # Standard folder options
                # Additive operations
                options.extend([
                    f"[COLOR lightgreen]{L(36009) % folder_info['name']}[/COLOR]",  # "Create New List in '%s'"
                    f"[COLOR lightgreen]{L(36010) % folder_info['name']}[/COLOR]"  # "Create New Subfolder in '%s'"
                ])

                # Modify operations
                options.extend([
                    f"[COLOR yellow]{L(36005) % folder_info['name']}[/COLOR]",  # "Rename '%s'"
                    f"[COLOR yellow]{L(36011) % folder_info['name']}[/COLOR]"  # "Move '%s' to Parent Folder"
                ])

                # Export operations
                options.append(f"[COLOR white]{L(36012) % folder_info['name']}[/COLOR]")  # "Export All Lists in '%s'"

                # Destructive operations
                options.append(f"[COLOR red]{L(36008) % folder_info['name']}[/COLOR]")  # "Delete '%s'"

            # Cancel
            options.append(f"[COLOR gray]{L(36003)}[/COLOR]")  # "Cancel"

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36015), list(options))  # "Folder Tools & Options"

            if selected_index < 0 or selected_index == len(options) - 1:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option - calculate indices based on reserved status
            if is_reserved:
                # Search History folder: Export(0), Clear All(1), Cancel(2)
                if selected_index == 0:  # Export
                    return self._export_folder_lists(context, folder_id)
                elif selected_index == 1:  # Clear all search history
                    return self._clear_search_history_folder(context, folder_id)
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
                    result = lists_handler.delete_folder(context, folder_id)

                    # For folder deletion, set flag to navigate back to lists menu
                    if result.success:
                        result.navigate_to_lists = True

                    return result

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
            selected_index = dialog.select(L(36029), list(folder_options))  # "Select destination folder:"

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
            source_lists = [list_item for list_item in all_lists if str(list_item['id']) != str(target_list_id)]

            if not source_lists:
                return DialogResponse(success=False, message="No other lists available to merge")

            # Build list options
            list_options = [f"{list_item['name']} ({list_item['item_count']} items)" for list_item in source_lists]

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36028), list(list_options))  # "Select list to merge:"

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
            selected_index = dialog.select("Select parent folder:", list(folder_options))

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
            new_name = xbmcgui.Dialog().input(
                L(36056),  # "Enter name for new list:"
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                return DialogResponse(success=False)

            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            result = query_manager.create_list(new_name.strip(), folder_id)

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{new_name}' already exists in this folder"
                else:
                    message = "Failed to create list"
                return DialogResponse(success=False, message=message)
            else:
                return DialogResponse(
                    success=True,
                    message=f"Created list: {new_name}",
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

            if result["success"]:
                message = (
                    f"Export completed:\n"
                    f"File: {result.get('filename', 'unknown')}\n"
                    f"Items: {result.get('total_items', 0)}\n"
                    f"Size: {self._format_file_size(result.get('file_size', 0))}"
                )
                return DialogResponse(
                    success=True,
                    message=message,
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
                L(36037),  # "Confirm Export"
                L(36038) % (list_count, folder_info['name']),  # "Export all %d lists from '%s'?"
                L(36039),  # "This will include all list items and metadata."
                nolabel=L(36003),  # "Cancel"
                yeslabel=L(36007)   # "Export"
            ):
                return DialogResponse(success=False)

            # Get export engine
            export_engine = get_export_engine()

            # Run export
            result = export_engine.export_data(
                export_types=["lists", "list_items"],
                file_format="json"
            )

            if result["success"]:
                return DialogResponse(
                    success=True,
                    message=f"Exported {list_count} lists from '{folder_info['name']}' to {result.get('filename', 'export file')}",
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

    def handle_action(self, action: str, params: Dict[str, Any]) -> DialogResponse:
        """Handle tools actions"""
        try:
            if action == "tools":
                return self._show_tools_menu(params)
            elif action == "force_rescan":
                return self._force_rescan()
            elif action == "clear_search_history":
                return self._clear_search_history()
            elif action == "reset_preferences":
                return self._reset_preferences()
            elif action == "library_stats":
                return self._show_library_stats()
            elif action == "favorites_stats":
                return self._show_favorites_stats()
            elif action == "test_backup":
                return self._test_backup_config()
            elif action == "manual_backup":
                return self._run_manual_backup()
            elif action == "backup_manager":
                return self._show_backup_manager()
            else:
                self.logger.warning(f"Unknown tools action: {action}")
                return self._show_tools_menu(params)
        except Exception as e:
            self.logger.error(f"Error in tools handler: {e}")
            return DialogResponse(
                success=False,
                message=f"Error: {e}"
            )

    def _show_favorites_stats(self) -> DialogResponse:
        """Show favorites statistics"""
        try:
            favorites_manager = get_phase4_favorites_manager()

            stats = favorites_manager.get_favorites_stats()

            message = (
                f"Favorites Stats:\n"
                f"Total Favorites: {stats.get('total_favorites', 0)}\n"
                f"Mapped to Library: {stats.get('mapped_favorites', 0)}\n"
                f"Unmapped: {stats.get('unmapped_favorites', 0)}\n"
                f"Missing Targets: {stats.get('missing_favorites', 0)}\n"
                f"Last Scan: {stats.get('last_scan', 'Never')}"
            )

            return DialogResponse(
                success=True,
                message=message
            )

        except Exception as e:
            self.logger.error(f"Error getting favorites stats: {e}")
            return DialogResponse(
                success=False,
                message=f"Error getting favorites stats: {e}"
            )

    def _test_backup_config(self) -> DialogResponse:
        """Test backup configuration"""
        try:
            from ..import_export import get_timestamp_backup_manager
            backup_manager = get_timestamp_backup_manager()

            result = backup_manager.test_backup_configuration()

            if result["success"]:
                message = f"Backup configuration test successful:\n{result['message']}"
            else:
                message = f"Backup configuration test failed:\n{result['error']}"

            return DialogResponse(
                success=result.get("success", False),
                message=message
            )

        except Exception as e:
            self.logger.error(f"Error testing backup config: {e}")
            return DialogResponse(
                success=False,
                message=f"Error testing backup config: {e}"
            )

    def _run_manual_backup(self) -> DialogResponse:
        """Run manual backup"""
        try:
            from ..import_export import get_timestamp_backup_manager
            backup_manager = get_timestamp_backup_manager()

            result = backup_manager.run_manual_backup()

            if result["success"]:
                message = (
                    f"Manual backup completed:\n"
                    f"File: {result['filename']}\n"
                    f"Size: {result['file_size']} bytes\n"
                    f"Items: {result['total_items']}\n"
                    f"Location: {result['storage_location']}"
                )
            else:
                message = f"Manual backup failed: {result['error']}"

            return DialogResponse(
                success=result.get("success", False),
                message=message
            )

        except Exception as e:
            self.logger.error(f"Error running manual backup: {e}")
            return DialogResponse(
                success=False,
                message=f"Error running manual backup: {e}"
            )

    def _show_backup_manager(self) -> DialogResponse:
        """Show backup manager with list of backups"""
        try:
            from ..import_export import get_timestamp_backup_manager
            backup_manager = get_timestamp_backup_manager()

            backups = backup_manager.list_backups()

            # Build backup list for display - return simple dialog with backup info
            if not backups:
                return DialogResponse(
                    success=True,
                    message="No backups found. Create a backup using the manual backup option."
                )

            # Show backup selection dialog
            backup_options = []
            for backup in backups[:10]:  # Show last 10 backups
                age_text = f"{backup['age_days']} days ago" if backup['age_days'] > 0 else "Today"
                size_mb = round(backup['file_size'] / 1024 / 1024, 2)
                backup_options.append(f"{backup['filename']} - {age_text} • {size_mb} MB • {backup['storage_type']}")

            import xbmcgui
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36060), backup_options)  # "Select backup to restore:"

            if selected_index < 0:
                return DialogResponse(success=False, message=L(36062))  # "Restore cancelled"

            selected_backup = backups[selected_index]

            # Confirm restore
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                heading=L(34007),  # "Restore from Backup"
                line1=L(37007) % selected_backup['display_name'],  # "Restore from: %s"
                line2=L(34014),    # "This will replace all current lists and data."
                line3=L(34602),    # "This action cannot be undone."
                nolabel=L(36003),  # "Cancel"
                yeslabel=L(34007)  # "Restore from Backup"
            ):
                return DialogResponse(success=False)

            # Restore backup
            restore_result = backup_manager.restore_backup(selected_backup['filename'])

            if restore_result["success"]:
                total_restored = sum([
                    restore_result.get("lists_restored", 0),
                    restore_result.get("items_restored", 0)
                ])
                message = (
                    f"Backup restored successfully:\n"
                    f"Lists: {restore_result.get('lists_restored', 0)}\n"
                    f"Items: {restore_result.get('items_restored', 0)}\n"
                    f"Total restored: {total_restored}"
                )
                return DialogResponse(success=True, message=message, refresh_needed=True)
            else:
                message = f"Backup restore failed: {restore_result.get('error', 'Unknown error')}"
                return DialogResponse(success=False, message=message)

        except Exception as e:
            self.logger.error(f"Error showing backup manager: {e}")
            return DialogResponse(
                success=False,
                message=f"Error showing backup manager: {e}"
            )

    def restore_backup_from_settings(self) -> DialogResponse:
        """Handle restore backup from settings menu"""
        try:
            from ..import_export import get_timestamp_backup_manager
            backup_manager = get_timestamp_backup_manager()

            import xbmcgui
            dialog = xbmcgui.Dialog()

            # Prompt for replace or append
            options = [L(36071), L(36072)] # "Replace Existing", "Append to Existing"
            selected_option = dialog.select(L(36073), options) # "Restore Backup Options"

            if selected_option == -1:  # User cancelled
                return DialogResponse(success=False, message=L(36062))  # "Restore cancelled"

            replace_mode = options[selected_option].startswith("Replace")

            # Get list of available backups
            available_backups = backup_manager.list_backups()

            if not available_backups:
                return DialogResponse(
                    success=False,
                    message="No backups found."
                )

            # Present backup selection dialog
            backup_options = []
            for backup in available_backups[:20]:  # Show last 20 backups
                age_text = f"{backup['age_days']} days ago" if backup['age_days'] > 0 else "Today"
                size_mb = round(backup['file_size'] / 1024 / 1024, 2)
                backup_options.append(f"{backup['filename']} - {age_text} • {size_mb} MB")

            backup_index = dialog.select(L(36060), backup_options)  # "Select Backup File"

            if backup_index == -1:  # User cancelled
                return DialogResponse(success=False, message=L(36062))  # "Restore cancelled"

            selected_backup = available_backups[backup_index]

            # Perform the restore operation with progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("Restoring Backup", f"Restoring from: {selected_backup['filename']}...")
            progress.update(0)

            try:
                result = backup_manager.restore_backup(selected_backup, replace_mode=replace_mode)

                progress.update(100, "Restore complete!")
                progress.close()

                if result.get("success"):
                    message = (
                        f"Restore completed successfully!\n\n"
                        f"Filename: {selected_backup['filename']}\n"
                        f"Items restored: {result.get('items_added', 0)}\n"
                        f"Items skipped: {result.get('items_skipped', 0)}\n"
                        f"Lists created: {result.get('lists_created', 0)}"
                    )
                    return DialogResponse(success=True, message=message, refresh_needed=True)
                else:
                    error_msg = result.get("error", "Unknown error")
                    return DialogResponse(success=False, message=f"Restore failed:\n{error_msg}")

            except Exception as e:
                progress.update(100, "Restore failed!")
                progress.close()
                self.logger.error(f"Error during restore_backup execution: {e}")
                return DialogResponse(success=False, message=f"An error occurred during restore: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error in restore backup from settings: {e}")
            return DialogResponse(success=False, message=f"An error occurred: {str(e)}")

    def _show_tools_menu(self, params: Dict[str, Any]) -> DialogResponse:
        """Show main tools menu"""
        return DialogResponse(
            success=True,
            message="Tools menu not yet implemented"
        )

    def _force_rescan(self) -> DialogResponse:
        """Force library rescan"""
        return DialogResponse(
            success=True,
            message="Force rescan not yet implemented"
        )

    def _clear_search_history(self) -> DialogResponse:
        """Clear search history"""
        return DialogResponse(
            success=True,
            message="Clear search history not yet implemented"
        )

    def _reset_preferences(self) -> DialogResponse:
        """Reset preferences"""
        return DialogResponse(
            success=True,
            message="Reset preferences not yet implemented"
        )

    def _show_library_stats(self) -> DialogResponse:
        """Show library statistics"""
        return DialogResponse(
            success=True,
            message="Library stats not yet implemented"
        )

    def _show_lists_main_tools(self, context: PluginContext) -> DialogResponse:
        """Show tools specific to the main Lists menu"""
        try:
            # Build comprehensive options for main lists menu - organized by operation type
            options = [
                # Creation operations
                f"[COLOR lightgreen]{L(36019)}[/COLOR]",  # "Create New List"
                f"[COLOR lightgreen]{L(36020)}[/COLOR]",  # "Create New Folder"
                # Import operations
                "[COLOR white]Import Lists[/COLOR]",
                # Export operations
                "[COLOR white]Export All Lists[/COLOR]",
                # Backup operations
                "[COLOR white]Manual Backup[/COLOR]",
                "[COLOR white]Backup Manager[/COLOR]",
                "[COLOR white]Test Backup Config[/COLOR]",
                # Management operations
                "[COLOR yellow]Library Statistics[/COLOR]",
                "[COLOR yellow]Force Library Rescan[/COLOR]",
                "[COLOR yellow]Clear Search History[/COLOR]",
                "[COLOR yellow]Reset Preferences[/COLOR]",
                # Cancel
                f"[COLOR gray]{L(36003)}[/COLOR]"  # "Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(36021), list(options))  # "Lists Tools & Options"

            if selected_index < 0 or selected_index == 11:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if selected_index == 0:  # Create New List
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.create_list(context)
            elif selected_index == 1:  # Create New Folder
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.create_folder(context)
            elif selected_index == 2:  # Import Lists
                return self._import_lists(context)
            elif selected_index == 3:  # Export All Lists
                return self._export_all_lists(context)
            elif selected_index == 4:  # Manual Backup
                return self._run_manual_backup()
            elif selected_index == 5:  # Backup Manager
                return self._show_backup_manager()
            elif selected_index == 6:  # Test Backup Config
                return self._test_backup_config()
            elif selected_index == 7:  # Library Statistics
                return self._show_library_stats()
            elif selected_index == 8:  # Force Library Rescan
                return self._force_rescan()
            elif selected_index == 9:  # Clear Search History
                return self._clear_search_history()
            elif selected_index == 10:  # Reset Preferences
                return self._reset_preferences()

            return DialogResponse(success=False)

        except Exception as e:
            self.logger.error(f"Error showing lists main tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing lists tools"
            )

    def _import_lists(self, context: PluginContext) -> DialogResponse:
        """Import lists from file"""
        try:
            from ..import_export.import_engine import get_import_engine
            import_engine = get_import_engine()

            # Show file browser for selection
            dialog = xbmcgui.Dialog()
            file_path = dialog.browse(
                1,  # Type: ShowAndGetFile
                "Select file to import",
                "files",
                ".json|.ndjson",
                False,  # Use thumbs
                False,  # Treat as folder
                ""  # Default path
            )

            if not file_path:
                return DialogResponse(success=False)

            # Ensure file_path is a string (dialog.browse can return list in some cases)
            if isinstance(file_path, list):
                if not file_path:
                    return DialogResponse(success=False)
                file_path = file_path[0]  # Take the first file if multiple selected

            # Run import
            result = import_engine.import_data(file_path)
            if result.success:
                message = (
                    f"Import completed:\n"
                    f"Lists: {result.lists_created}\n"
                    f"Items: {result.items_added}\n"
                    f"Folders: {getattr(result, 'folders_imported', 0)}"
                )
                return DialogResponse(
                    success=True,
                    message=message,
                    refresh_needed=True
                )
            else:
                error_message = result.errors[0] if result.errors else "Unknown error"
                return DialogResponse(
                    success=False,
                    message=f"Import failed: {error_message}"
                )

        except Exception as e:
            self.logger.error(f"Error importing lists: {e}")
            return DialogResponse(success=False, message="Error importing lists")

    def _export_all_lists(self, context: PluginContext) -> DialogResponse:
        """Export all lists and folders"""
        try:
            # Get export engine
            export_engine = get_export_engine()

            # Get total count for confirmation
            query_manager = context.query_manager
            if query_manager:
                all_lists = query_manager.get_all_lists_with_folders()
                list_count = len(all_lists)

                # Confirm export
                dialog = xbmcgui.Dialog()
                if not dialog.yesno(
                    L(36037),  # "Confirm Export"
                    L(36070) % list_count,  # "Export all %d lists and folders?"
                    L(36039),  # "This will include all list items and metadata."
                    nolabel=L(36003),  # "Cancel"
                    yeslabel=L(36007)   # "Export"
                ):
                    return DialogResponse(success=False)

            # Run export
            result = export_engine.export_data(
                export_types=["lists", "list_items", "folders"],
                file_format="json"
            )

            if result["success"]:
                return DialogResponse(
                    success=True,
                    message=f"Exported all lists to {result.get('filename', 'export file')}",
                    refresh_needed=False
                )
            else:
                return DialogResponse(
                    success=False,
                    message=f"Export failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"Error exporting all lists: {e}")
            return DialogResponse(success=False, message="Error exporting all lists")

    def _clear_search_history_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Clear all search history lists"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get lists in search history folder
            search_lists = query_manager.get_lists_in_folder(folder_id)

            if not search_lists:
                return DialogResponse(
                    success=False,
                    message="No search history to clear"
                )

            # Confirm deletion
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                L(36067),  # "Clear Search History"
                L(36068) % len(search_lists),  # "Delete all %d search history lists?"
                L(30502),  # "This action cannot be undone."
                nolabel=L(36003),  # "Cancel"
                yeslabel=L(36069)   # "Clear"
            ):
                return DialogResponse(success=False)

            # Delete all search history lists
            deleted_count = 0
            for search_list in search_lists:
                result = query_manager.delete_list(search_list['id'])
                if result.get("success"):
                    deleted_count += 1

            if deleted_count > 0:
                return DialogResponse(
                    success=True,
                    message=f"Cleared {deleted_count} search history lists",
                    refresh_needed=True
                )
            else:
                return DialogResponse(
                    success=False,
                    message="Failed to clear search history"
                )

        except Exception as e:
            self.logger.error(f"Error clearing search history folder: {e}")
            return DialogResponse(success=False, message="Error clearing search history")

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size to be human-readable"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        if i == 0:
            return f"{int(size)} {size_names[i]}"
        else:
            return f"{size:.1f} {size_names[i]}"

    def _copy_search_history_to_list(self, context: PluginContext, search_list_id: str) -> DialogResponse:
        """Copy a search history list to a new regular list"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Database error")

            # Get search list info
            search_list_info = query_manager.get_list_by_id(search_list_id)
            if not search_list_info:
                return DialogResponse(success=False, message="Search list not found")

            # Get new list name from user
            suggested_name = search_list_info['name'].replace('Search: ', '').split(' (')[0]
            if suggested_name.startswith("'") and suggested_name.endswith("'"):
                suggested_name = suggested_name[1:-1]

            new_name = xbmcgui.Dialog().input(
                L(36056),  # "Enter name for new list:"
                defaultt=suggested_name,
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                return DialogResponse(success=False)

            # Create new list
            result = query_manager.create_list(new_name.strip())
            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{new_name}' already exists"
                else:
                    message = "Failed to create list"
                return DialogResponse(success=False, message=message)

            new_list_id = result['id']

            # Copy all items from search history list to new list
            search_items = query_manager.get_list_items(search_list_id)
            copied_count = 0

            for item in search_items:
                copy_result = query_manager.add_library_item_to_list(new_list_id, item)
                if copy_result:
                    copied_count += 1

            if copied_count > 0:
                return DialogResponse(
                    success=True,
                    message=f"Copied {copied_count} items to new list '{new_name}'",
                    refresh_needed=True
                )
            else:
                # Clean up empty list if no items were copied
                query_manager.delete_list(new_list_id)
                return DialogResponse(
                    success=False,
                    message="No items could be copied to the new list"
                )

        except Exception as e:
            self.logger.error(f"Error copying search history to list: {e}")
            return DialogResponse(success=False, message="Error copying search history")