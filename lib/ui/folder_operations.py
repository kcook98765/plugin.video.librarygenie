#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Folder Operations
Handles folder management operations (create, delete, rename, move)
"""

from typing import Dict, Any, Optional
import xbmcgui
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DialogResponse
from lib.ui.localization import L
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager


class FolderOperations:
    """Handles folder management operations"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_kodi_logger('lib.ui.folder_operations')
        # Get query manager with fallback
        self.query_manager = context.query_manager
        if self.query_manager is None:
            from lib.data.query_manager import get_query_manager
            self.query_manager = get_query_manager()
        self.storage_manager = context.storage_manager

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

            # Use injected query manager and create folder
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            result = self.query_manager.create_folder(folder_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"Folder '{folder_name}' already exists" # This string should also be localized
                else:
                    message = L(37021)  # "Failed to create folder" (red color)

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

    def delete_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle deleting a folder"""
        try:
            context.logger.info("Deleting folder %s", folder_id)

            # Use injected query manager
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get current folder info
            folder_info = self.query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message=L(37020)  # "Folder not found" (red color)
                )
            folder_name = folder_info.get('name', 'Unnamed Folder')

            # Check if folder has lists or subfolders
            lists_in_folder = self.query_manager.get_lists_in_folder(folder_id)
            subfolders = self.query_manager.get_all_folders(parent_id=folder_id)

            if lists_in_folder or subfolders:
                # Show warning about contents
                dialog_lines = [
                    f"Folder '{folder_name}' is not empty.",
                    "",
                    f"It contains {len(lists_in_folder)} list(s) and {len(subfolders)} subfolder(s).",
                    "",
                    "Are you sure you want to delete it?",
                    "All contents will be permanently removed."
                ]

                confirm = xbmcgui.Dialog().yesno(
                    "Delete Folder",
                    "\n".join(dialog_lines)
                )
            else:
                # Simple confirmation for empty folder
                confirm = xbmcgui.Dialog().yesno(
                    "Delete Folder",
                    f"Delete folder '{folder_name}'?"
                )

            if not confirm:
                context.logger.info("User cancelled folder deletion")
                return DialogResponse(success=False, message="")

            # Delete the folder
            result = self.query_manager.delete_folder(folder_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to delete folder" # This string should also be localized
                )
            else:
                context.logger.info("Successfully deleted folder: %s", folder_name)
                return DialogResponse(
                    success=True,
                    message=f"Deleted folder: {folder_name}", # This string should also be localized
                    navigate_to_lists=True  # Navigate away from deleted folder
                )

        except Exception as e:
            context.logger.error("Error deleting folder: %s", e)
            return DialogResponse(
                success=False,
                message="Error deleting folder" # This string should also be localized
            )

    def rename_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle renaming a folder"""
        try:
            context.logger.info("Renaming folder %s", folder_id)

            # Use injected query manager
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get current folder info
            folder_info = self.query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message=L(37020)  # "Folder not found" (red color)
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
            result = self.query_manager.rename_folder(folder_id, new_name.strip())

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

    def move_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle moving a list to a different folder"""
        try:
            context.logger.info("Moving list %s", list_id)

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get current list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message="List not found" # This string should also be localized
                )

            list_name = list_info.get('name', 'Unnamed List')
            current_folder_id = list_info.get('folder_id')

            # Get all available folders
            all_folders = self.query_manager.get_all_folders()
            folder_options = ["[ROOT] (No folder)"]  # Option for root level
            folder_ids = [None]  # None represents root level

            for folder in all_folders:
                folder_options.append(folder['name'])
                folder_ids.append(folder['id'])

            # Mark current folder if any
            if current_folder_id:
                for i, fid in enumerate(folder_ids):
                    if fid == current_folder_id:
                        folder_options[i] = f"[CURRENT] {folder_options[i]}"
                        break

            # Show folder selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(f"Move '{list_name}' to folder:", folder_options)

            if selected_index < 0:
                context.logger.info("User cancelled moving list")
                return DialogResponse(success=False, message="")

            target_folder_id = folder_ids[selected_index]

            # Check if already in selected folder
            if target_folder_id == current_folder_id:
                return DialogResponse(
                    success=False,
                    message=f"List is already in the selected location" # This string should also be localized
                )

            # Move the list
            result = self.query_manager.move_list_to_folder(list_id, target_folder_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to move list" # This string should also be localized
                )
            else:
                target_name = folder_options[selected_index].replace("[CURRENT] ", "")
                context.logger.info("Successfully moved list %s to folder: %s", list_name, target_name)
                return DialogResponse(
                    success=True,
                    message=f"Moved '{list_name}' to {target_name}" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error moving list: %s", e)
            return DialogResponse(
                success=False,
                message="Error moving list" # This string should also be localized
            )

    def move_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle moving a folder to a different parent folder"""
        try:
            context.logger.info("Moving folder %s", folder_id)

            # Use injected query manager
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get current folder info
            folder_info = self.query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message=L(37020)  # "Folder not found" (red color)
                )

            folder_name = folder_info.get('name', 'Unnamed Folder')
            current_parent_id = folder_info.get('parent_id')

            # Get all available folders (excluding current folder and its descendants)
            all_folders = self.query_manager.get_all_folders()
            folder_options = ["[ROOT] (Top level)"]  # Option for root level
            folder_ids = [None]  # None represents root level

            for folder in all_folders:
                # Skip current folder and any descendants to prevent circular references
                if folder['id'] == folder_id:
                    continue
                # TODO: Add logic to check if folder is a descendant of current folder
                folder_options.append(folder['name'])
                folder_ids.append(folder['id'])

            # Mark current parent folder if any
            if current_parent_id:
                for i, fid in enumerate(folder_ids):
                    if fid == current_parent_id:
                        folder_options[i] = f"[CURRENT] {folder_options[i]}"
                        break

            # Show folder selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select(f"Move '{folder_name}' to:", folder_options)

            if selected_index < 0:
                context.logger.info("User cancelled moving folder")
                return DialogResponse(success=False, message="")

            target_parent_id = folder_ids[selected_index]

            # Check if already in selected location
            if target_parent_id == current_parent_id:
                return DialogResponse(
                    success=False,
                    message=f"Folder is already in the selected location" # This string should also be localized
                )

            # Move the folder - use correct method name
            result = self.query_manager.move_folder(folder_id, target_parent_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to move folder" # This string should also be localized
                )
            else:
                target_name = folder_options[selected_index].replace("[CURRENT] ", "")
                context.logger.info("Successfully moved folder %s to: %s", folder_name, target_name)
                return DialogResponse(
                    success=True,
                    message=f"Moved '{folder_name}' to {target_name}" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error moving folder: %s", e)
            return DialogResponse(
                success=False,
                message="Error moving folder" # This string should also be localized
            )