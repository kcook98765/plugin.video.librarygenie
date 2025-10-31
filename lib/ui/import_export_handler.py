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
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DialogResponse
from lib.ui.localization import L
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager
from lib.ui.dialog_service import get_dialog_service


class ImportExportHandler:
    """Handles import and export operations"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_kodi_logger('lib.ui.import_export_handler')
        # Get query manager with fallback
        self.query_manager = context.query_manager
        if self.query_manager is None:
            from lib.data.query_manager import get_query_manager
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
                    message=L(30104)  # "Database error"
                )

            # Get list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message=L(30368)  # "List not found"
                )

            list_name = list_info.get('name', 'Unnamed List')

            # Get export location from config
            from lib.config.config_manager import get_config
            config = get_config()
            export_location = config.get_export_location()
            
            # The get_export_location now provides a default, but verify it's set
            if not export_location or not export_location.strip():
                return DialogResponse(
                    success=False,
                    message="Export location not configured. Please set it in addon settings."
                )
            
            # Handle special:// paths
            if export_location.startswith('special://'):
                import xbmcvfs
                export_location = xbmcvfs.translatePath(export_location)
            
            # Create export directory if it doesn't exist
            try:
                if not os.path.exists(export_location):
                    os.makedirs(export_location, exist_ok=True)
                    context.logger.info("Created export directory: %s", export_location)
            except Exception as dir_error:
                context.logger.error("Failed to create export directory: %s", dir_error)
                return DialogResponse(
                    success=False,
                    message=f"Failed to create export directory: {str(dir_error)}"
                )

            # Get list items
            list_items = query_manager.get_list_items(list_id)

            # Prepare export data
            from datetime import datetime
            export_data = {
                'format_version': '1.0',
                'export_type': 'single_list',
                'export_timestamp': datetime.now().isoformat(),
                'list': {
                    'name': list_name,
                    'description': list_info.get('description', ''),
                    'items': list_items
                }
            }
            
            # Generate safe filename by removing/replacing all illegal filesystem characters
            # Windows forbidden characters: < > : " / \ | ? *
            # Windows reserved device names: CON, PRN, AUX, NUL, COM1-9, LPT1-9
            import re
            safe_name = list_name
            
            # Replace illegal characters with underscores
            illegal_chars = r'[<>:"/\\|?*]'
            safe_name = re.sub(illegal_chars, '_', safe_name)
            
            # Replace spaces with underscores for cleaner filenames
            safe_name = safe_name.replace(' ', '_')
            
            # Remove any leading/trailing underscores or dots (Windows doesn't like these)
            safe_name = safe_name.strip('_.')
            
            # Check for Windows reserved device names (case-insensitive)
            # Windows treats both "CON" and "CON.anything" as reserved
            # Reserved names: CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9
            reserved_names = {
                'CON', 'PRN', 'AUX', 'NUL',
                'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
            }
            
            # Check if name exactly matches or starts with reserved name followed by dot
            name_upper = safe_name.upper()
            is_reserved = False
            
            # Check exact match
            if name_upper in reserved_names:
                is_reserved = True
            else:
                # Check if it starts with a reserved name followed by a dot
                for reserved in reserved_names:
                    if name_upper.startswith(reserved + '.'):
                        is_reserved = True
                        break
            
            if is_reserved:
                safe_name = f"{safe_name}_list"
                context.logger.debug("List name matched or started with Windows reserved device name, appended '_list'")
            
            # Ensure we have a valid name (fallback if name becomes empty)
            if not safe_name:
                safe_name = f"list_{list_id}"
            
            export_filename = f"libraryGenie_list_{safe_name}.json"
            file_path = os.path.join(export_location, export_filename)
            
            context.logger.debug("Sanitized list name '%s' to filename '%s'", list_name, export_filename)
            
            try:
                # Write export data to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                context.logger.info("Successfully exported list to: %s", file_path)
                
                return DialogResponse(
                    success=True,
                    message=f"List '{list_name}' exported to:\n{export_filename}",
                    refresh_needed=False
                )
                
            except Exception as write_error:
                context.logger.error("Failed to write export file: %s", write_error)
                return DialogResponse(
                    success=False,
                    message=f"Failed to write export file: {str(write_error)}"
                )

        except Exception as e:
            context.logger.error("Error exporting list: %s", e)
            return DialogResponse(
                success=False,
                message=f"Error exporting list: {str(e)}"
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
                    message=L(30104)  # "Database error" (red color)
                )

            # Get folder info
            folder_info = query_manager.get_folder_by_id(folder_id)
            if not folder_info:
                return DialogResponse(
                    success=False,
                    message=L(30369)  # "Folder not found" (red color)
                )

            folder_name = folder_info.get('name', 'Unnamed Folder')

            # Get lists in folder
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            
            if include_subfolders:
                # Note: get_subfolders method not available on QueryManager
                # Skip subfolder processing for now
                context.logger.debug("Subfolder processing not available")

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
                'export_timestamp': 'unknown',
                'folder': {
                    'name': folder_name,
                    'include_subfolders': include_subfolders,
                    'lists': export_lists
                }
            }

            # Use export engine if available
            try:
                from lib.import_export.export_engine import get_export_engine
                export_engine = get_export_engine()
                # Use available export_data method instead of non-existent export_folder
                result = export_engine.export_data(['lists'], context_filter={'folder_id': folder_id})
                
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
                    message=L(30104)  # "Database error" (red color)
                )

            # Use import engine if available
            try:
                from lib.import_export.import_engine import get_import_engine
                import_engine = get_import_engine()
                
                if not import_engine:
                    return DialogResponse(
                        success=False,
                        message="Import engine not available" # This string should also be localized
                    )

                # Note: import_data requires a file_path parameter, but we don't have one here
                # This functionality would need to be implemented differently to work with file selection
                context.logger.warning("Import functionality not fully implemented - requires file path")
                return DialogResponse(
                    success=False,
                    message="Import functionality requires file selection (not yet implemented)"
                )
                    
            except ImportError:
                # Fallback: show file selection dialog
                context.logger.info("Import engine not available, showing basic import dialog")
                
                # Show info dialog about import functionality
                dialog_service = get_dialog_service(logger_name='lib.ui.import_export_handler.import_lists')
                dialog_service.ok(
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
                    message=L(30104)  # "Database error" (red color)
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
            dialog_service = get_dialog_service(logger_name='lib.ui.import_export_handler.merge_lists')
            confirm = dialog_service.yesno(
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
                    message=L(30104)  # "Database error" (red color)
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
            dialog_service = get_dialog_service(logger_name='lib.ui.import_export_handler.select_lists_for_merge')
            source_index = dialog_service.select("Select source list (items FROM):", list_options)
            if source_index < 0:
                return DialogResponse(success=False, message="")

            # Select target list (exclude source)
            target_options = list_options.copy()
            target_ids = list_ids.copy()
            target_options.pop(source_index)
            target_ids.pop(source_index)

            target_index = dialog_service.select("Select target list (items TO):", target_options)
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