#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Folder Tools Provider
Provides tools for folder context
"""

from typing import List, Any
from ..types import ToolAction, ToolsContext, ConfirmSpec
from .base_provider import BaseToolsProvider
from lib.ui.localization import L
from lib.ui.response_types import DialogResponse


class FolderToolsProvider(BaseToolsProvider):
    """Provider for folder tools"""
    
    def __init__(self):
        super().__init__()
    
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build folder tools menu"""
        try:
            # Get folder info to determine available operations
            query_manager = plugin_context.query_manager
            if not query_manager or not context.folder_id:
                return []
                
            folder_info = query_manager.get_folder_by_id(context.folder_id)
            if not folder_info:
                return []
                
            # Check if this is a reserved folder (Search History)
            is_reserved = folder_info.get('is_reserved', False)
            folder_name = folder_info['name']
            
            if is_reserved:
                # Search History folder - limited operations
                return [
                    self._create_action(
                        action_id="export_folder",
                        label=L(36012).replace('%s', folder_name),  # "Export All Lists in '%s'"
                        handler=self._handle_export_folder,
                        payload={"folder_id": context.folder_id}
                    ),
                    self._create_action(
                        action_id="clear_search_history",
                        label=L(37023),  # "Clear All Search History"
                        handler=self._handle_clear_search_history,
                        payload={"folder_id": context.folder_id},
                        needs_confirmation=ConfirmSpec(
                            title="Clear Search History",
                            message="Clear all search history lists?"
                        )
                    )
                ]
            else:
                # Standard folder - full operations
                return [
                    # Creation operations
                    self._create_action(
                        action_id="create_list",
                        label=L(36009).replace('%s', folder_name),  # "Create New List in '%s'"
                        handler=self._handle_create_list,
                        payload={"folder_id": context.folder_id}
                    ),
                    self._create_action(
                        action_id="create_subfolder",
                        label=L(36010).replace('%s', folder_name),  # "Create New Subfolder in '%s'"
                        handler=self._handle_create_subfolder,
                        payload={"folder_id": context.folder_id}
                    ),
                    
                    # Management operations
                    self._create_action(
                        action_id="rename_folder",
                        label=L(36005).replace('%s', folder_name),  # "Rename '%s'"
                        handler=self._handle_rename_folder,
                        payload={"folder_id": context.folder_id}
                    ),
                    self._create_action(
                        action_id="move_folder", 
                        label=L(36011).replace('%s', folder_name),  # "Move '%s' to Folder"
                        handler=self._handle_move_folder,
                        payload={"folder_id": context.folder_id}
                    ),
                    
                    # Export operations
                    self._create_action(
                        action_id="export_folder",
                        label=L(36012).replace('%s', folder_name),  # "Export All Lists in '%s'"
                        handler=self._handle_export_folder,
                        payload={"folder_id": context.folder_id}
                    ),
                    
                    # Destructive operations
                    self._create_action(
                        action_id="delete_folder",
                        label=L(36008).replace('%s', folder_name),  # "Delete '%s'"
                        handler=self._handle_delete_folder,
                        payload={"folder_id": context.folder_id},
                        needs_confirmation=ConfirmSpec(
                            title="Delete Folder",
                            message=f"Delete folder '{folder_name}'?"
                        )
                    )
                ]
                
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error building folder tools: %s", e)
            return []
    
    def _handle_create_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle creating new list in folder"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._create_list_in_folder(plugin_context, payload["folder_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error creating list: %s", e)
            return DialogResponse(success=False, message="Error creating list")
    
    def _handle_create_subfolder(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle creating subfolder"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._create_subfolder(plugin_context, payload["folder_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error creating subfolder: %s", e)
            return DialogResponse(success=False, message="Error creating subfolder")
    
    def _handle_rename_folder(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle renaming folder"""
        try:
            from lib.ui.lists_handler import ListsHandler
            lists_handler = ListsHandler(plugin_context)
            result = lists_handler.rename_folder(plugin_context, payload["folder_id"])
            
            if result.success:
                result.navigate_to_folder = payload["folder_id"]
                result.refresh_needed = False
                result.navigate_to_main = False
                result.navigate_to_lists = False
                
            return result
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error renaming folder: %s", e)
            return DialogResponse(success=False, message="Error renaming folder")
    
    def _handle_move_folder(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle moving folder"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._move_folder(plugin_context, payload["folder_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error moving folder: %s", e)
            return DialogResponse(success=False, message="Error moving folder")
    
    def _handle_export_folder(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle exporting folder"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._export_folder_lists(plugin_context, payload["folder_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error exporting folder: %s", e)
            return DialogResponse(success=False, message="Error exporting folder")
    
    def _handle_delete_folder(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle deleting folder"""
        try:
            from lib.ui.lists_handler import ListsHandler
            lists_handler = ListsHandler(plugin_context)
            return lists_handler.delete_folder(plugin_context, payload["folder_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error deleting folder: %s", e)
            return DialogResponse(success=False, message="Error deleting folder")
    
    def _handle_clear_search_history(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle clearing search history"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._clear_search_history_folder(plugin_context, payload["folder_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.folder_provider')
            logger.error("Error clearing search history: %s", e)
            return DialogResponse(success=False, message="Error clearing search history")