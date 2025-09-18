#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Tools Handler
Modular tools and options handler for different list types
"""

import xbmcgui
from datetime import datetime
from typing import Dict, Any, Optional, Literal
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DialogResponse
from lib.ui.localization import L
from lib.utils.kodi_log import get_kodi_logger


class ToolsHandler:
    """Modular tools and options handler"""

    def __init__(self, context: Optional[PluginContext] = None):
        self.logger = get_kodi_logger('lib.ui.tools_handler')
        self.context = context
        try:
            from lib.ui.listitem_builder import ListItemBuilder
            if context:
                self.listitem_builder = ListItemBuilder(
                    addon_handle=context.addon_handle,
                    addon_id=context.addon.getAddonInfo('id')
                )
            else:
                self.listitem_builder = None
        except ImportError:
            self.listitem_builder = None
            
        # Tools menu system is lazy loaded on first use for better startup performance
        self._tools_service = None

    @property
    def tools_service(self):
        """Lazy load tools menu system only when tools are actually used"""
        if self._tools_service is None:
            self.logger.debug("LAZY LOAD: Loading ToolsMenuService on first use")
            from lib.ui.tools_menu import ToolsMenuService
            self._tools_service = ToolsMenuService()
            self._register_providers()
        return self._tools_service

    def _register_providers(self) -> None:
        """Register tools providers for different contexts"""
        try:
            from lib.ui.tools_menu.providers import (
                FavoritesToolsProvider, 
                UserListToolsProvider,
                FolderToolsProvider,
                ListsMainToolsProvider
            )
            
            # Register providers with the tools service
            # Note: we access _tools_service directly since this method is called from the property
            service = self._tools_service
            service.register_provider("favorites", FavoritesToolsProvider())
            service.register_provider("user_list", UserListToolsProvider())
            service.register_provider("folder", FolderToolsProvider())
            service.register_provider("lists_main", ListsMainToolsProvider())
            self.logger.debug("All tools providers registered successfully")
        except Exception as e:
            self.logger.error("Error registering tools providers: %s", e)

    def show_list_tools(self, context: PluginContext, list_type: Literal['favorites','user_list','folder','lists_main'], list_id: Optional[str] = None) -> DialogResponse:
        """Show tools & options modal for different list types using centralized system"""
        try:
            self.logger.debug("Showing tools & options for list_type: %s, list_id: %s", list_type, list_id)

            # Create tools context
            from lib.ui.tools_menu import ToolsContext
            tools_context = ToolsContext(
                list_type=list_type,
                list_id=list_id,
                folder_id=list_id if list_type == "folder" else None
            )
            
            # Build menu actions using centralized system
            actions = self.tools_service.build_menu(tools_context, context)
            if not actions:
                return DialogResponse(
                    success=False,
                    message=L(90504)  # "Operation failed"
                )
            
            # Determine appropriate title based on context
            title = self._get_tools_title(list_type)
            
            # Show centralized tools menu
            return self.tools_service.show_menu(title, actions, context)

        except Exception as e:
            self.logger.error("Error showing list tools: %s", e)
            return DialogResponse(
                success=False,
                message=L(90504)  # "Operation failed"
            )
    
    def _get_tools_title(self, list_type: str) -> str:
        """Get appropriate title for tools menu based on context"""
        titles = {
            "favorites": L(96013),  # "Favorites Tools & Options"
            "user_list": L(96014),  # "List Tools & Options"
            "folder": L(96015),     # "Folder Tools & Options"
            "lists_main": "Tools & Options"  # TODO: Add to localization
        }
        return titles.get(list_type, "Tools & Options")





    def _move_list_to_folder(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Move a list to a different folder"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            # Get available folders
            all_folders = query_manager.get_all_folders()
            folder_options = ["[Root Level]"] + [f['name'] for f in all_folders if f['name'] != 'Search History']

            # Show folder selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(96029), list(folder_options))  # "Select destination folder:"

            if selected_index < 0:
                return DialogResponse(success=False)

            # Move list
            target_folder_id = None if selected_index == 0 else all_folders[selected_index - 1]['id']

            self.logger.debug("Moving list %s to folder %s (selected_index: %s)", list_id, target_folder_id, selected_index)

            result = query_manager.move_list_to_folder(list_id, target_folder_id)

            if result.get("success"):
                folder_name = L(96032) if target_folder_id is None else folder_options[selected_index]  # "root level"
                response = DialogResponse(
                    success=True,
                    message=L(96033) % folder_name,  # "Moved list to %s"
                )

                # Navigate to appropriate location after move
                if target_folder_id is None:
                    response.navigate_to_lists = True
                else:
                    response.navigate_to_folder = target_folder_id
                    # Ensure no other navigation flags are set that could override folder navigation
                    response.navigate_to_lists = False
                    response.navigate_to_main = False
                    response.refresh_needed = False

                self.logger.debug("Set navigation to folder %s", target_folder_id)
                return response
            else:
                error_msg = result.get("error", "unknown")
                self.logger.error("Failed to move list: %s", error_msg)
                return DialogResponse(success=False, message=f"Failed to move list: {error_msg}")

        except Exception as e:
            self.logger.error("Error moving list to folder: %s", e)
            return DialogResponse(success=False, message="Error moving list")

    def _merge_lists(self, context: PluginContext, target_list_id: str) -> DialogResponse:
        """Merge another list into the target list"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            # Get all lists except the target
            all_lists = query_manager.get_all_lists_with_folders()
            source_lists = [list_item for list_item in all_lists if str(list_item['id']) != str(target_list_id)]

            if not source_lists:
                return DialogResponse(success=False, message="No other lists available to merge")

            # Build list options
            list_options = [list_item['name'] for list_item in source_lists]

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(L(96028), list(list_options))  # "Select list to merge:"

            if selected_index < 0:
                return DialogResponse(success=False)

            source_list = source_lists[selected_index]

            # Confirm merge
            message = f"{L(96022) % source_list['name']}\n{L(96024)}"  # "Merge '%s' into target list?\nThe source list will remain unchanged."
            if not dialog.yesno(
                L(96021),  # "Confirm Merge"
                message
            ):
                return DialogResponse(success=False)

            # Perform merge
            result = query_manager.merge_lists(source_list['id'], target_list_id)

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message=L(96025) % result.get('items_added', 0),  # "Merged %d new items"
                    navigate_to_lists=True
                )
            else:
                return DialogResponse(success=False, message=L(96026))  # "Failed to merge lists"

        except Exception as e:
            self.logger.error("Error merging lists: %s", e)
            return DialogResponse(success=False, message="Error merging lists")

    def _move_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Move a folder to a different parent folder"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            # Get available destination folders (excluding self and children)
            all_folders = query_manager.get_all_folders()
            folder_options = ["[Root Level]"]
            folder_mapping = [None]  # None represents root level

            for f in all_folders:
                if str(f['id']) != str(folder_id) and f['name'] != 'Search History':
                    folder_options.append(f['name'])
                    folder_mapping.append(f['id'])

            # Show folder selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Select destination folder:", list(folder_options))

            if selected_index < 0:
                return DialogResponse(success=False)

            # Move folder using the correct mapping
            target_folder_id = folder_mapping[selected_index]
            result = query_manager.move_folder(folder_id, target_folder_id)

            if result.get("success"):
                destination_name = "root level" if target_folder_id is None else folder_options[selected_index]

                # Navigate to the destination location instead of refreshing current view
                if target_folder_id is None:
                    # Moved to root level - navigate to main lists menu
                    return DialogResponse(
                        success=True,
                        message=f"Moved folder to {destination_name}",
                        navigate_to_lists=True
                    )
                else:
                    # Moved to another folder - navigate to that destination folder
                    return DialogResponse(
                        success=True,
                        message=f"Moved folder to {destination_name}",
                        navigate_to_folder=target_folder_id
                    )
            else:
                return DialogResponse(success=False, message="Failed to move folder")

        except Exception as e:
            self.logger.error("Error moving folder: %s", e)
            return DialogResponse(success=False, message="Error moving folder")

    def _create_list_in_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Create a new list in the specified folder"""
        try:
            self.logger.debug("TOOLS DEBUG: _create_list_in_folder called with folder_id: %s", folder_id)

            # Get list name from user
            new_name = xbmcgui.Dialog().input(
                L(96056),  # "Enter name for new list:"
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                self.logger.debug("TOOLS DEBUG: User cancelled list creation or entered empty name")
                return DialogResponse(success=False)

            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            self.logger.debug("TOOLS DEBUG: Creating list '%s' in folder_id: %s", new_name.strip(), folder_id)

            # Pass folder_id as the third parameter to create_list (name, description, folder_id)
            result = query_manager.create_list(new_name.strip(), "", folder_id)

            self.logger.debug("TOOLS DEBUG: create_list result: %s", result)

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{new_name}' already exists in this folder"
                else:
                    message = "Failed to create list"
                return DialogResponse(success=False, message=message)
            else:
                self.logger.info("TOOLS DEBUG: Successfully created list '%s' in folder_id: %s", new_name, folder_id)
                return DialogResponse(
                    success=True,
                    message=f"Created list: {new_name}",
                    navigate_to_folder=folder_id
                )

        except Exception as e:
            self.logger.error("Error creating list in folder: %s", e)
            return DialogResponse(success=False, message="Error creating list")

    def _create_subfolder(self, context: PluginContext, parent_folder_id: str) -> DialogResponse:
        """Create a new subfolder in the specified parent folder"""
        try:
            self.logger.debug("TOOLS DEBUG: _create_subfolder called with parent_folder_id: %s", parent_folder_id)

            # Get folder name from user
            folder_name = xbmcgui.Dialog().input(
                "Enter folder name:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not folder_name or not folder_name.strip():
                self.logger.debug("TOOLS DEBUG: User cancelled subfolder creation or entered empty name")
                return DialogResponse(success=False)

            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            self.logger.debug("TOOLS DEBUG: Creating subfolder '%s' in parent_folder_id: %s", folder_name.strip(), parent_folder_id)

            # Pass parent_folder_id as the second parameter to create_folder (name, parent_id)
            result = query_manager.create_folder(folder_name.strip(), parent_folder_id)

            self.logger.debug("TOOLS DEBUG: create_folder result: %s", result)

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{folder_name}' already exists in this location"
                else:
                    message = "Failed to create folder"
                return DialogResponse(success=False, message=message)
            else:
                self.logger.info("TOOLS DEBUG: Successfully created subfolder '%s' in parent_folder_id: %s", folder_name, parent_folder_id)

                # Navigate back to the parent folder where the subfolder was created
                return DialogResponse(
                    success=True,
                    message=f"Created subfolder: {folder_name}",
                    navigate_to_folder=parent_folder_id
                )

        except Exception as e:
            self.logger.error("Error creating subfolder: %s", e)
            return DialogResponse(success=False, message="Error creating subfolder")

    def _export_single_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Export a single list with option to export parent folder branch"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            # Get list info for confirmation
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(success=False, message="List not found")

            # Present export scope options
            import xbmcgui
            dialog = xbmcgui.Dialog()
            
            export_options = [
                f"Export only '{list_info['name']}' list",
            ]
            
            # Check if list has a parent folder for branch export option
            parent_folder_name = "Lists"  # Default for root level
            folder_id = list_info.get('folder_id')
            
            if folder_id:
                folder_info = query_manager.get_folder_by_id(folder_id)
                if folder_info:
                    parent_folder_name = folder_info['name']
                    export_options.append(f"Export '{parent_folder_name}' branch (folder + subfolders)")
            
            export_options.append("Cancel")
            
            selected_option = dialog.select(
                f"Export '{list_info['name']}'",
                export_options
            )
            
            if selected_option == -1 or selected_option == len(export_options) - 1:  # Cancel
                return DialogResponse(success=False)

            # Get export engine (lazy import)
            from lib.import_export.export_engine import get_export_engine
            export_engine = get_export_engine()
            
            if selected_option == 0:
                # Export single list only
                context_filter = {"list_id": list_id}
                result = export_engine.export_data(
                    export_types=["lists", "list_items"],
                    file_format="json",
                    context_filter=context_filter
                )
                
                if result["success"]:
                    message = (
                        f"Export completed for list '{list_info['name']}':\n"
                        f"File: {result.get('filename', 'unknown')}\n"
                        f"Items: {result.get('total_items', 0)}\n"
                        f"Size: {self._format_file_size(result.get('file_size', 0))}"
                    )
                else:
                    message = f"Export failed: {result.get('error', 'Unknown error')}"
                    
            elif selected_option == 1 and folder_id:
                # Export parent folder as branch
                context_filter = {
                    "folder_id": folder_id,
                    "include_subfolders": True
                }
                result = export_engine.export_data(
                    export_types=["lists", "list_items"],
                    file_format="json",
                    context_filter=context_filter
                )
                
                if result["success"]:
                    message = (
                        f"Export completed for branch '{parent_folder_name}':\n"
                        f"File: {result.get('filename', 'unknown')}\n"
                        f"Items: {result.get('total_items', 0)}\n"
                        f"Size: {self._format_file_size(result.get('file_size', 0))}"
                    )
                else:
                    message = f"Export failed: {result.get('error', 'Unknown error')}"
            else:
                return DialogResponse(success=False)

            # Navigate back to the original list after export
            if result["success"]:
                if selected_option == 0:  # Single list export
                    # Stay in the current list
                    return DialogResponse(
                        success=True,
                        message=message,
                        refresh_needed=True  # Refresh current list view
                    )
                else:  # Branch export
                    # Navigate back to the original list
                    return DialogResponse(
                        success=True,
                        message=message,
                        refresh_needed=True  # Refresh current view
                    )
            else:
                return DialogResponse(
                    success=False,
                    message=message,
                    refresh_needed=False
                )

        except Exception as e:
            self.logger.error("Error exporting single list: %s", e)
            return DialogResponse(success=False, message="Error exporting list")

    def _export_folder_lists(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Export lists from a folder with user choice of scope"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

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

            # Present export scope options
            import xbmcgui
            dialog = xbmcgui.Dialog()
            
            # Get subfolder count for branch export option
            subfolders = query_manager.get_all_folders(parent_id=folder_id)
            subfolder_count = len(subfolders) if subfolders else 0
            
            export_options = [
                f"Export only '{folder_info['name']}' folder ({list_count} lists)",
                f"Export '{folder_info['name']}' branch (folder + {subfolder_count} subfolders)",
                "Cancel"
            ]
            
            selected_option = dialog.select(
                f"Export from '{folder_info['name']}'",
                export_options
            )
            
            if selected_option == -1 or selected_option == 2:  # Cancel
                return DialogResponse(success=False)
            
            # Determine export scope
            include_subfolders = (selected_option == 1)  # Branch export

            # Get export engine (lazy import)
            from lib.import_export.export_engine import get_export_engine
            export_engine = get_export_engine()

            # Run contextual export with folder filtering
            context_filter = {
                "folder_id": folder_id,
                "include_subfolders": include_subfolders
            }
            
            result = export_engine.export_data(
                export_types=["lists", "list_items"],
                file_format="json",
                context_filter=context_filter
            )

            if result["success"]:
                scope_desc = "branch" if include_subfolders else "folder"
                return DialogResponse(
                    success=True,
                    message=f"Exported {scope_desc} '{folder_info['name']}':\n"
                           f"File: {result.get('filename', 'export file')}\n"
                           f"Items: {result.get('total_items', 0)}\n"
                           f"Size: {self._format_file_size(result.get('file_size', 0))}",
                    navigate_to_folder=folder_id  # Navigate back to the original folder
                )
            else:
                return DialogResponse(
                    success=False,
                    message=f"Export failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error("Error exporting folder lists: %s", e)
            return DialogResponse(success=False, message="Error exporting folder lists")

    def _handle_export_all_lists(self, context: PluginContext) -> DialogResponse:
        """Export all lists in the system"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            # Get count of all lists for user confirmation
            all_lists = query_manager.get_user_lists()
            list_count = len(all_lists) if all_lists else 0

            if list_count == 0:
                return DialogResponse(
                    success=False,
                    message="No lists found to export"
                )

            # Confirm export
            import xbmcgui
            dialog = xbmcgui.Dialog()
            if not dialog.yesno(
                "Confirm Export",
                f"Export all {list_count} lists in your library?\nThis will include all list items and metadata.",
                "Cancel",    # nolabel (No button)
                "Export"     # yeslabel (Yes button)
            ):
                return DialogResponse(success=False)

            # Get export engine
            from lib.import_export.export_engine import get_export_engine
            export_engine = get_export_engine()

            # Run export for all lists (no context filter = export everything)
            result = export_engine.export_data(
                export_types=["lists", "list_items"],
                file_format="json"
            )

            if result["success"]:
                # Ensure file_size is an integer for _format_file_size
                file_size = result.get('file_size', 0)
                if isinstance(file_size, str):
                    try:
                        file_size = int(file_size)
                    except (ValueError, TypeError):
                        file_size = 0
                elif file_size is None:
                    file_size = 0
                
                return DialogResponse(
                    success=True,
                    message=f"Exported all {list_count} lists:\n"
                           f"File: {result.get('filename', 'export file')}\n"
                           f"Items: {result.get('total_items', 0)}\n"
                           f"Size: {self._format_file_size(file_size)}",
                    navigate_to_lists=True  # Navigate back to lists main menu
                )
            else:
                return DialogResponse(
                    success=False,
                    message=f"Export failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error("Error exporting all lists: %s", e)
            return DialogResponse(success=False, message="Error exporting all lists")

    def _handle_import_lists(self, context: PluginContext) -> DialogResponse:
        """Import lists from file"""
        try:
            from lib.import_export.import_engine import get_import_engine
            
            # Show file browser for selection
            import xbmcgui
            dialog = xbmcgui.Dialog()
            file_path = dialog.browse(
                1,  # Type: ShowAndGetFile
                "Select import file",
                "files",
                ".json",
                False,  # Use thumbs
                False,  # Treat as folder
                ""      # Default path
            )
            
            if not file_path:
                return DialogResponse(success=False)  # User cancelled

            # Get import engine
            import_engine = get_import_engine()

            # Validate file first
            validation = import_engine.validate_import_file(file_path)
            if not validation["valid"]:
                errors = "\n".join(validation.get("errors", ["Unknown validation error"]))
                return DialogResponse(
                    success=False,
                    message=f"Invalid import file:\n{errors}"
                )

            # Preview import to show user what will happen
            preview = import_engine.preview_import(file_path)
            
            # Show confirmation with preview details (simplified for timestamped import folders)
            preview_text = (
                f"Import Preview (into timestamped import folder):\n"
                f"• {len(preview.lists_to_create)} lists to create\n"
                f"• {preview.items_to_add} items to add\n"
                f"• {preview.items_unmatched} items that cannot be matched"
            )
            
            if preview.warnings:
                preview_text += "\n\nWarnings:\n" + "\n".join(f"• {w}" for w in preview.warnings)

            if not dialog.yesno(
                "Confirm Import",
                preview_text + "\n\nProceed with import?",
                "Cancel",     # nolabel (No button)
                "Import"      # yeslabel (Yes button)
            ):
                return DialogResponse(success=False)

            # Perform the import
            result = import_engine.import_data(file_path)

            if result.success:
                return DialogResponse(
                    success=True,
                    message=f"Import completed successfully:\n"
                           f"• Created: {result.lists_created} lists\n"
                           f"• Added: {result.items_added} items\n"
                           f"• Unmatched: {result.items_unmatched} items",
                    navigate_to_lists=True  # Navigate back to lists main menu
                )
            else:
                errors = "\n".join(result.errors) if result.errors else "Unknown error"
                return DialogResponse(
                    success=False,
                    message=f"Import failed:\n{errors}"
                )

        except Exception as e:
            self.logger.error("Error importing lists: %s", e)
            return DialogResponse(success=False, message="Error importing lists")

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
            elif action == "manual_backup":
                return self._run_manual_backup()
            elif action == "backup_manager":
                return self._show_backup_manager()
            elif action == "restore_backup":
                return self.handle_restore_backup(params, self)
            elif action == "activate_ai_search":
                return self.handle_activate_ai_search(params, self)
            else:
                self.logger.warning("Unknown tools action: %s", action)
                return self._show_tools_menu(params)
        except Exception as e:
            self.logger.error("Error in tools handler: %s", e)
            return DialogResponse(
                success=False,
                message=f"Error: {e}"
            )

    def _show_favorites_stats(self) -> DialogResponse:
        """Show favorites statistics"""
        try:
            from lib.kodi.favorites_manager import get_phase4_favorites_manager
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
            self.logger.error("Error getting favorites stats: %s", e)
            return DialogResponse(
                success=False,
                message=f"Error getting favorites stats: {e}"
            )


    def _run_manual_backup(self) -> DialogResponse:
        """Run manual backup"""
        try:
            from lib.import_export import get_timestamp_backup_manager
            backup_manager = get_timestamp_backup_manager()

            result = backup_manager.run_automatic_backup()

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
            self.logger.error("Error running manual backup: %s", e)
            return DialogResponse(
                success=False,
                message=f"Error running manual backup: {e}"
            )

    def _show_backup_manager(self) -> DialogResponse:
        """Show backup manager with list of backups"""
        try:
            from lib.import_export import get_timestamp_backup_manager
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
            selected_index = dialog.select(L(97014), backup_options)  # "Select backup to restore"

            if selected_index < 0:
                return DialogResponse(success=False, message=L(96062))  # "Restore cancelled"

            selected_backup = backups[selected_index]

            # Confirm restore
            dialog = xbmcgui.Dialog()
            restore_message = f"{L(97007) % selected_backup['display_name']}\n{L(94014)}\n{L(94602)}"
            if not dialog.yesno(
                L(94007),  # "Restore from Backup"
                restore_message,
                nolabel=L(96003),  # "Cancel"
                yeslabel=L(94007)  # "Restore from Backup"
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
            self.logger.error("Error showing backup manager: %s", e)
            return DialogResponse(
                success=False,
                message=f"Error showing backup manager: {e}"
            )

    def restore_backup_from_settings(self) -> DialogResponse:
        """Handle restore backup from settings menu"""
        try:
            from lib.import_export import get_timestamp_backup_manager
            backup_manager = get_timestamp_backup_manager()

            import xbmcgui
            dialog = xbmcgui.Dialog()

            # Prompt for replace or append
            options = [L(97015), L(97016)] # "Replace existing data", "Append to existing data"
            selected_option = dialog.select(L(96073), options) # "Restore Backup Options"

            if selected_option == -1:  # User cancelled
                return DialogResponse(success=False, message=L(96062))  # "Restore cancelled"

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

            backup_index = dialog.select(L(96060), backup_options)  # "Select Backup File"

            if backup_index == -1:  # User cancelled
                return DialogResponse(success=False, message=L(96062))  # "Restore cancelled"

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
                self.logger.error("Error during restore_backup execution: %s", e)
                return DialogResponse(success=False, message=f"An error occurred during restore: {str(e)}")

        except Exception as e:
            self.logger.error("Error in restore backup from settings: %s", e)
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


    def _import_lists(self, context: PluginContext, target_folder_id: str = None) -> DialogResponse:
        """Import lists from file to specified folder"""
        try:
            from lib.import_export.import_engine import get_import_engine
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

            # Run import with target folder context
            result = import_engine.import_data(file_path, target_folder_id=target_folder_id)
            if result.success:
                folder_context = ""
                if target_folder_id:
                    query_manager = context.query_manager
                    if query_manager:
                        folder_info = query_manager.get_folder_by_id(target_folder_id)
                        if folder_info:
                            folder_context = f" to '{folder_info['name']}'"

                message = (
                    f"Import completed{folder_context}:\n"
                    f"Lists: {result.lists_created}\n"
                    f"Items: {result.items_added}\n"
                    f"Folders: {getattr(result, 'folders_imported', 0)}"
                )

                # Navigate appropriately based on context
                response = DialogResponse(
                    success=True,
                    message=message,
                    refresh_needed=True
                )

                if target_folder_id:
                    response.navigate_to_folder = target_folder_id
                else:
                    response.navigate_to_lists = True

                return response
            else:
                error_message = result.errors[0] if result.errors else "Unknown error"
                return DialogResponse(
                    success=False,
                    message=f"Import failed: {error_message}"
                )

        except Exception as e:
            self.logger.error("Error importing lists: %s", e)
            return DialogResponse(success=False, message="Error importing lists")

    def _export_all_lists(self, context: PluginContext) -> DialogResponse:
        """Export all lists and folders"""
        try:
            # Get export engine (lazy import)
            from lib.import_export.export_engine import get_export_engine
            export_engine = get_export_engine()

            # Get total count for confirmation
            query_manager = context.query_manager
            if query_manager:
                all_lists = query_manager.get_all_lists_with_folders()
                list_count = len(all_lists)

                # Confirm export
                dialog = xbmcgui.Dialog()
                export_message = f"{L(96070) % list_count}\n{L(96039)}"
                if not dialog.yesno(
                    L(96037),  # "Confirm Export"
                    export_message,
                    nolabel=L(96003),  # "Cancel"
                    yeslabel=L(96007)   # "Export"
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
            self.logger.error("Error exporting all lists: %s", e)
            return DialogResponse(success=False, message="Error exporting all lists")

    def _clear_search_history_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Clear all search history lists"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

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
                L(96067),  # "Clear Search History"
                f"{L(96068) % len(search_lists)}\n{L(90502)}",  # "Delete all %d search history lists?" + "This action cannot be undone."
                nolabel=L(96003),  # "Cancel"
                yeslabel=L(96069)   # "Clear"
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
                    refresh_needed=True,
                    navigate_to_main=True  # Navigate to main menu since folder is now empty
                )
            else:
                return DialogResponse(
                    success=False,
                    message="Failed to clear search history"
                )

        except Exception as e:
            self.logger.error("Error clearing search history folder: %s", e)
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
        """Convert a search history list to a regular list by moving it out of Search History folder"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            # Get search list info
            search_list_info = query_manager.get_list_by_id(search_list_id)
            if not search_list_info:
                return DialogResponse(success=False, message="Search list not found")

            # Get new name from user - suggest cleaned up search term
            original_name = search_list_info['name']
            suggested_name = original_name

            # Clean up the search list name to suggest a better regular list name
            if original_name.startswith("Search: '") and "' (" in original_name:
                # Extract just the search term
                start = len("Search: '")
                end = original_name.find("' (")
                if end > start:
                    suggested_name = original_name[start:end]

            new_name = xbmcgui.Dialog().input(
                "Enter name for new list:",
                defaultt=suggested_name,
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                return DialogResponse(success=False, message="")

            # Get all folders for destination selection
            all_folders = query_manager.get_all_folders()
            folder_options = ["Root Level"]
            folder_ids = [None]  # None means root level

            for folder in all_folders:
                if folder['name'] != 'Search History':  # Don't allow moving back to Search History
                    folder_options.append(folder['name'])
                    folder_ids.append(folder['id'])

            # Add option to create new folder
            folder_options.append("+ Create New Folder")

            # Show folder selection dialog
            selected_index = xbmcgui.Dialog().select("Move to folder:", folder_options)

            if selected_index < 0:
                return DialogResponse(success=False, message="")

            target_folder_id = None
            destination_name = "root level"

            if selected_index == len(folder_options) - 1:  # Create new folder
                folder_name = xbmcgui.Dialog().input(
                    "Enter folder name:",
                    type=xbmcgui.INPUT_ALPHANUM
                )

                if not folder_name or not folder_name.strip():
                    return DialogResponse(success=False, message="")

                # Create the folder
                folder_result = query_manager.create_folder(folder_name.strip())

                if folder_result.get("error"):
                    if folder_result["error"] == "duplicate_name":
                        message = f"Folder '{folder_name}' already exists"
                    else:
                        message = "Failed to create folder"
                    return DialogResponse(success=False, message=message)
                else:
                    target_folder_id = folder_result["folder_id"]
                    destination_name = folder_name.strip()
            else:
                target_folder_id = folder_ids[selected_index]
                destination_name = folder_options[selected_index] if selected_index < len(folder_options) else "root level"

            # Check for duplicate name in target location
            existing_lists = query_manager.get_all_lists_with_folders()
            for existing_list in existing_lists:
                if (existing_list['name'] == new_name.strip() and
                    existing_list.get('folder_id') == target_folder_id):
                    return DialogResponse(
                        success=False,
                        message=f"List '{new_name.strip()}' already exists in {destination_name}"
                    )

            # Perform the conversion with proper error handling
            try:
                with query_manager.connection_manager.transaction() as conn:
                    # Update name and set folder_id to selected destination
                    result = conn.execute("""
                        UPDATE lists
                        SET name = ?, folder_id = ?
                        WHERE id = ?
                    """, [new_name.strip(), target_folder_id, int(search_list_id)])

                    if result.rowcount == 0:
                        raise Exception("No rows updated - list may not exist")

                self.logger.info("Successfully converted search history list %s to '%s' in %s", search_list_id, new_name.strip(), destination_name)

                # Check if this was the last list in the search history folder
                search_folder_id = query_manager.get_or_create_search_history_folder()
                remaining_lists = query_manager.get_lists_in_folder(search_folder_id)

                # Navigate appropriately based on remaining search history
                if remaining_lists:
                    # Still have search history lists, navigate back to folder
                    return DialogResponse(
                        success=True,
                        message=f"Moved '{new_name.strip()}' to {destination_name}",
                        navigate_to_folder=search_folder_id
                    )
                else:
                    # No more search history lists, navigate back to main menu
                    return DialogResponse(
                        success=True,
                        message=f"Moved '{new_name.strip()}' to {destination_name}",
                        navigate_to_main=True
                    )

            except Exception as db_error:
                self.logger.error("Database error during list conversion: %s", db_error)
                return DialogResponse(
                    success=False,
                    message=f"Failed to move list: {str(db_error)}"
                )

        except Exception as e:
            self.logger.error("Error converting search history to list: %s", e)
            import traceback
            self.logger.error("Traceback: %s", traceback.format_exc())
            return DialogResponse(success=False, message="Error converting search history")

    def handle_restore_backup(self, params: dict, context) -> DialogResponse:
        """Handle backup restoration"""
        try:
            from lib.import_export.backup_manager import BackupManager
            from lib.ui.localization import L
            import xbmcgui

            backup_manager = BackupManager()

            # Get available backups
            backups = backup_manager.list_backups()
            if not backups:
                xbmcgui.Dialog().ok(L(94018), L(94018))  # "No backups found"
                return DialogResponse(success=False, message="No backups found")

            # Let user select backup
            labels = [f"{backup['name']} ({backup['date']})" for backup in backups]
            selected = xbmcgui.Dialog().select(L(97014), labels)  # "Select backup to restore"

            if selected < 0:
                return DialogResponse(success=False, message="Restore cancelled")

            selected_backup = backups[selected]

            # Confirm restoration
            if xbmcgui.Dialog().yesno(
                L(96063),  # "LibraryGenie Restore"
                L(97007) % selected_backup['name'],  # "Restore from: %s"
                L(96065)   # "This will replace all current data."
            ):
                success = backup_manager.restore_backup(selected_backup['path'])
                if success:
                    xbmcgui.Dialog().ok(L(94011), L(94011))  # "Restore completed successfully"
                    return DialogResponse(success=True, message="Restore completed successfully", refresh_needed=True)
                else:
                    xbmcgui.Dialog().ok(L(94012), L(94012))  # "Restore failed"
                    return DialogResponse(success=False, message="Restore failed")

            return DialogResponse(success=False, message="Restore cancelled")

        except Exception as e:
            context.logger.error("Error in restore backup handler: %s", e)
            return DialogResponse(success=False, message="Failed to restore backup")


    def handle_activate_ai_search(self, params: dict, context) -> DialogResponse:
        """Handle AI search activation via OTP code"""
        try:
            from lib.auth.auth_helper import get_auth_helper
            from lib.ui.localization import L
            import xbmcgui

            auth_helper = get_auth_helper()

            # Check if already authorized
            if auth_helper.verify_api_key():
                xbmcgui.Dialog().ok(
                    "Already Authorized",
                    "AI Search is already activated and working."
                )
                return DialogResponse(success=True, message="AI Search is already activated")

            # Start authorization flow
            success = auth_helper.start_device_authorization()

            if success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "AI Search activated successfully!",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )
                return DialogResponse(success=True, message="AI Search activated successfully!")

            return DialogResponse(success=False, message="AI Search activation failed")

        except Exception as e:
            context.logger.error("Error in AI search activation handler: %s", e)
            return DialogResponse(success=False, message="Failed to activate AI search")

    def _handle_local_search(self, context: PluginContext) -> DialogResponse:
        """Execute local search directly"""
        try:
            from lib.ui.handler_factory import get_handler_factory
            
            # Get search handler and execute search
            factory = get_handler_factory()
            factory.context = context
            search_handler = factory.get_search_handler()
            
            # Execute the search directly
            success = search_handler.prompt_and_search(context)
            
            if success:
                return DialogResponse(
                    success=True, 
                    message="Search completed",
                    refresh_needed=False,
                    navigate_to_main=False
                )
            else:
                return DialogResponse(
                    success=True, 
                    message="Search cancelled",
                    refresh_needed=False
                )
        except Exception as e:
            context.logger.error("Error executing search: %s", e)
            return DialogResponse(success=False, message="Failed to execute search")

    def _handle_local_episodes_search(self, context: PluginContext) -> DialogResponse:
        """Execute local episodes search directly"""
        try:
            from lib.ui.handler_factory import get_handler_factory
            
            # Get search handler and execute search
            factory = get_handler_factory()
            factory.context = context
            search_handler = factory.get_search_handler()
            
            # Execute the search directly with episode media scope
            success = search_handler.prompt_and_search(context, media_scope="episode")
            
            if success:
                return DialogResponse(
                    success=True, 
                    message="Episode search completed",
                    refresh_needed=False,
                    navigate_to_main=False
                )
            else:
                return DialogResponse(
                    success=True, 
                    message="Episode search cancelled",
                    refresh_needed=False
                )
        except Exception as e:
            context.logger.error("Error executing episode search: %s", e)
            return DialogResponse(success=False, message="Failed to execute episode search")

    def _handle_ai_search(self, context: PluginContext) -> DialogResponse:
        """Navigate to AI search"""
        try:
            import xbmc
            ai_search_url = context.build_url('ai_search_prompt')
            xbmc.executebuiltin(f'Container.Update("{ai_search_url}",replace)')
            return DialogResponse(success=True, message="Opening AI search...")
        except Exception as e:
            context.logger.error("Error navigating to AI search: %s", e)
            return DialogResponse(success=False, message="Failed to open AI search")

    def _handle_search_history(self, context: PluginContext) -> DialogResponse:
        """Navigate to search history"""
        try:
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message="Query manager not available")
                
            search_folder_id = query_manager.get_or_create_search_history_folder()
            
            if search_folder_id:
                # Navigate directly using xbmc.executebuiltin instead of relying on DialogResponse navigation
                import xbmc
                folder_url = context.build_url("show_folder", folder_id=search_folder_id)
                context.logger.debug("TOOLS: Navigating directly to search history folder %s with URL: %s", search_folder_id, folder_url)
                xbmc.executebuiltin(f'Container.Update("{folder_url}",replace)')
                # Return a simple success response without any navigation flags to avoid conflicts
                return DialogResponse(success=True, message="")
            else:
                return DialogResponse(success=False, message="Could not access search history")
        except Exception as e:
            context.logger.error("Error navigating to search history: %s", e)
            return DialogResponse(success=False, message="Failed to open search history")

    def _handle_create_folder(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new top-level folder from main lists menu"""
        try:
            self.logger.debug("TOOLS DEBUG: _handle_create_folder called for top-level folder")

            # Get folder name from user
            folder_name = xbmcgui.Dialog().input(
                "Enter folder name:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not folder_name or not folder_name.strip():
                self.logger.debug("TOOLS DEBUG: User cancelled folder creation or entered empty name")
                return DialogResponse(success=False)

            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(success=False, message=L(94306))  # "Database error"

            self.logger.debug("TOOLS DEBUG: Creating top-level folder '%s'", folder_name.strip())

            # Pass None as parent_folder_id to create a top-level folder
            result = query_manager.create_folder(folder_name.strip(), None)

            self.logger.debug("TOOLS DEBUG: create_folder result: %s", result)

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{folder_name}' already exists"
                else:
                    message = "Failed to create folder"
                return DialogResponse(success=False, message=message)
            else:
                self.logger.info("TOOLS DEBUG: Successfully created top-level folder '%s'", folder_name)

                # Navigate back to the lists main menu after creating the folder
                return DialogResponse(
                    success=True,
                    message=f"Created folder: {folder_name}",
                    navigate_to_lists=True
                )

        except Exception as e:
            self.logger.error("Error creating folder: %s", e)
            return DialogResponse(success=False, message="Error creating folder")

    def _handle_create_list(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new list from main lists menu"""
        try:
            from lib.ui.lists_handler import ListsHandler
            lists_handler = ListsHandler(context)
            result = lists_handler.create_list(context)
            
            # Navigate back to lists main menu after creation
            if result.success:
                result.navigate_to_lists = True
                
            return result
        except Exception as e:
            self.logger.error("Error creating list: %s", e)
            return DialogResponse(success=False, message="Error creating list")

    def _handle_create_backup(self, context: PluginContext) -> DialogResponse:
        """Handle creating a backup"""
        try:
            return self._run_manual_backup()
        except Exception as e:
            self.logger.error("Error creating backup: %s", e)
            return DialogResponse(success=False, message="Error creating backup")

    def _handle_restore_backup_from_tools(self, context: PluginContext) -> DialogResponse:
        """Handle restoring from backup via tools menu"""
        try:
            return self._show_backup_manager()
        except Exception as e:
            self.logger.error("Error restoring backup: %s", e)
            return DialogResponse(success=False, message="Error restoring backup")

    def _handle_open_settings(self, context: PluginContext) -> DialogResponse:
        """Handle opening addon settings"""
        try:
            import xbmc
            xbmc.executebuiltin(f'Addon.OpenSettings({context.addon.getAddonInfo("id")})')

            # Return success=False with special flag to prevent endOfDirectory call
            # Settings opening is asynchronous - prevent empty directory display
            response = DialogResponse(
                success=False,
                message=""  # No notification and no navigation - settings handles its own flow
            )
            # Add special flag to indicate this is a settings operation
            response.is_settings_operation = True
            return response
        except Exception as e:
            context.logger.error("Error opening settings: %s", e)
            return DialogResponse(
                success=False,
                message="Failed to open settings"
            )