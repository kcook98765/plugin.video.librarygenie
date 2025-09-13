#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Import/Export Handler
Handles import and export operations for lists and folders
"""

from typing import Dict, Any, Optional, List
import xbmcgui
import json
import os
from .plugin_context import PluginContext
from .response_types import DialogResponse
from .localization import L
from ..utils.kodi_log import get_kodi_logger
from ..data.query_manager import get_query_manager


class ImportExportHandler:
    """Handles import and export operations"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_kodi_logger('lib.ui.import_export_handler')
        # Get query manager with fallback
        self.query_manager = context.query_manager
        if self.query_manager is None:
            from ..data.query_manager import get_query_manager
            self.query_manager = get_query_manager()
        self.storage_manager = context.storage_manager

    def export_single_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Export a single list to a file"""
        try:
            context.logger.info("Exporting list %s", list_id)

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message="List not found" # This string should also be localized
                )

            list_name = list_info.get('name', 'Unnamed List')

            # Get list items
            list_items = query_manager.get_list_items(list_id)

            # Prepare export data
            export_data = {
                'format_version': '1.0',
                'export_type': 'single_list',
                'export_timestamp': str(context.get_current_timestamp() if hasattr(context, 'get_current_timestamp') else 'unknown'),
                'list': {
                    'name': list_name,
                    'description': list_info.get('description', ''),
                    'items': list_items
                }
            }

            # Use basic JSON export functionality
            context.logger.info("Using basic export functionality")
            
            # Basic JSON export
            export_filename = f"libraryGenie_list_{list_name.replace(' ', '_')}.json"
            
            try:
                # Create export data
                json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
                
                # For now, just show success message
                # TODO: Implement actual file writing when file system access is available
                return DialogResponse(
                    success=True,
                    message=f"Export data prepared for '{list_name}'" # This string should also be localized
                )
                
            except Exception as json_error:
                context.logger.error("JSON export failed: %s", json_error)
                return DialogResponse(
                    success=False,
                    message="Failed to prepare export data" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error exporting list: %s", e)
            return DialogResponse(
                success=False,
                message="Error exporting list" # This string should also be localized
            )

    def export_folder_lists(self, context: PluginContext, folder_id: str, include_subfolders: bool = False) -> DialogResponse:
        """Export all lists in a folder"""
        try:
            context.logger.info("Exporting folder %s (include_subfolders=%s)", folder_id, include_subfolders)

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get folder info
            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message="Folder not found" # This string should also be localized
                )

            folder_name = folder_info.get('name', 'Unnamed Folder')

            # Get lists in folder
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            
            if include_subfolders:
                # Get subfolders and their lists too
                subfolders = query_manager.get_subfolders(folder_id)
                for subfolder in subfolders:
                    subfolder_lists = query_manager.get_lists_in_folder(subfolder['id'])
                    lists_in_folder.extend(subfolder_lists)

            if not lists_in_folder:
                return DialogResponse(
                    success=False,
                    message=f"No lists found in folder '{folder_name}'" # This string should also be localized
                )

            # Prepare export data for all lists
            export_lists = []
            for list_item in lists_in_folder:
                list_id = list_item['id']
                list_items = query_manager.get_list_items(list_id)
                export_lists.append({
                    'name': list_item['name'],
                    'description': list_item.get('description', ''),
                    'items': list_items
                })

            export_data = {
                'format_version': '1.0',
                'export_type': 'folder_lists',
                'export_timestamp': str(context.get_current_timestamp() if hasattr(context, 'get_current_timestamp') else 'unknown'),
                'folder': {
                    'name': folder_name,
                    'include_subfolders': include_subfolders,
                    'lists': export_lists
                }
            }

            # Use export engine if available
            try:
                from ..engines.export_engine import get_export_engine
                export_engine = get_export_engine()
                result = export_engine.export_folder(folder_id, folder_name, include_subfolders)
                
                if result and result.get('success'):
                    return DialogResponse(
                        success=True,
                        message=f"Exported {len(lists_in_folder)} lists from folder '{folder_name}'"
                    )
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'Export engine failed'
                    return DialogResponse(
                        success=False,
                        message=f"Export failed: {error_msg}"
                    )
                    
            except ImportError:
                # Fallback export
                context.logger.info("Export engine not available, using basic export")
                return DialogResponse(
                    success=True,
                    message=f"Export data prepared for folder '{folder_name}' ({len(lists_in_folder)} lists)"
                )

        except Exception as e:
            context.logger.error("Error exporting folder: %s", e)
            return DialogResponse(
                success=False,
                message="Error exporting folder" # This string should also be localized
            )

    def import_lists(self, context: PluginContext) -> DialogResponse:
        """Import lists from a file"""
        try:
            context.logger.info("Starting list import process")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Use import engine if available
            try:
                from ..engines.import_engine import get_import_engine
                import_engine = get_import_engine()
                
                if not import_engine:
                    return DialogResponse(
                        success=False,
                        message="Import engine not available" # This string should also be localized
                    )

                result = import_engine.import_lists()
                
                if result and result.get('success'):
                    imported_count = result.get('imported_count', 0)
                    return DialogResponse(
                        success=True,
                        message=f"Successfully imported {imported_count} lists",
                        refresh_needed=True
                    )
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'Import failed'
                    return DialogResponse(
                        success=False,
                        message=f"Import failed: {error_msg}"
                    )
                    
            except ImportError:
                # Fallback: show file selection dialog
                context.logger.info("Import engine not available, showing basic import dialog")
                
                # Show info dialog about import functionality
                xbmcgui.Dialog().ok(
                    "Import Lists",
                    "Import functionality requires the import engine to be available.\n\n"
                    "Please ensure the import engine is properly configured."
                )
                
                return DialogResponse(
                    success=False,
                    message="Import engine not available" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error importing lists: %s", e)
            return DialogResponse(
                success=False,
                message="Error importing lists" # This string should also be localized
            )

    def merge_lists(self, context: PluginContext, source_list_id: str, target_list_id: str) -> DialogResponse:
        """Merge items from source list into target list"""
        try:
            context.logger.info("Merging list %s into %s", source_list_id, target_list_id)

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Validate both lists exist
            source_list = query_manager.get_list_by_id(source_list_id)
            target_list = query_manager.get_list_by_id(target_list_id)

            if not source_list:
                return DialogResponse(
                    success=False,
                    message="Source list not found" # This string should also be localized
                )

            if not target_list:
                return DialogResponse(
                    success=False,
                    message="Target list not found" # This string should also be localized
                )

            source_name = source_list.get('name', 'Unnamed List')
            target_name = target_list.get('name', 'Unnamed List')

            # Get items from source list
            source_items = query_manager.get_list_items(source_list_id)

            if not source_items:
                return DialogResponse(
                    success=False,
                    message=f"Source list '{source_name}' is empty" # This string should also be localized
                )

            # Show confirmation dialog
            confirm = xbmcgui.Dialog().yesno(
                "Merge Lists",
                f"Merge {len(source_items)} items from '{source_name}' into '{target_name}'?\n\n"
                f"Duplicate items will be skipped."
            )

            if not confirm:
                context.logger.info("User cancelled list merge")
                return DialogResponse(success=False, message="")

            # Perform the merge
            merged_count = 0
            skipped_count = 0

            for item in source_items:
                item_id = item.get('id')
                if item_id:
                    result = query_manager.add_item_to_list(target_list_id, item_id)
                    if result and result.get("success"):
                        merged_count += 1
                    elif result and result.get("error") == "duplicate":
                        skipped_count += 1
                    else:
                        context.logger.warning("Failed to merge item %s", item_id)

            # Prepare result message
            if merged_count > 0:
                message = f"Merged {merged_count} items into '{target_name}'"
                if skipped_count > 0:
                    message += f" ({skipped_count} duplicates skipped)"
                
                return DialogResponse(
                    success=True,
                    message=message
                )
            else:
                return DialogResponse(
                    success=False,
                    message=f"No items were merged (all {skipped_count} were duplicates)" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error merging lists: %s", e)
            return DialogResponse(
                success=False,
                message="Error merging lists" # This string should also be localized
            )

    def select_lists_for_merge(self, context: PluginContext) -> DialogResponse:
        """Show UI for selecting source and target lists for merging"""
        try:
            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            
            if len(all_lists) < 2:
                return DialogResponse(
                    success=False,
                    message="Need at least 2 lists to perform merge" # This string should also be localized
                )

            # Build list options
            list_options = []
            list_ids = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    display_name = lst['name']
                else:
                    display_name = f"{folder_name}/{lst['name']}"
                list_options.append(display_name)
                list_ids.append(lst['id'])

            # Select source list
            source_index = xbmcgui.Dialog().select("Select source list (items FROM):", list_options)
            if source_index < 0:
                return DialogResponse(success=False, message="")

            # Select target list (exclude source)
            target_options = list_options.copy()
            target_ids = list_ids.copy()
            target_options.pop(source_index)
            target_ids.pop(source_index)

            target_index = xbmcgui.Dialog().select("Select target list (items TO):", target_options)
            if target_index < 0:
                return DialogResponse(success=False, message="")

            # Perform the merge
            source_list_id = list_ids[source_index]
            target_list_id = target_ids[target_index]

            return self.merge_lists(context, source_list_id, target_list_id)

        except Exception as e:
            context.logger.error("Error in select_lists_for_merge: %s", e)
            return DialogResponse(
                success=False,
                message="Error selecting lists for merge" # This string should also be localized
            )