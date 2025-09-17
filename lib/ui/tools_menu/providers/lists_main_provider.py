#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Lists Main Tools Provider
Provides tools for main lists menu context
"""

from typing import List, Any
from ..types import ToolAction, ToolsContext
from .base_provider import BaseToolsProvider
from lib.ui.localization import L
from lib.ui.response_types import DialogResponse


class ListsMainToolsProvider(BaseToolsProvider):
    """Provider for lists main menu tools"""
    
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build main lists tools menu"""
        try:
            return [
                # Creation operations
                self._create_action(
                    action_id="create_new_list",
                    label=L(36009).replace(' in %s', ''),  # "Create New List"
                    handler=self._handle_create_new_list
                ),
                self._create_action(
                    action_id="create_new_folder", 
                    label=L(36010).replace(' in %s', ''),  # "Create New Folder"
                    handler=self._handle_create_new_folder
                ),
                
                # Import/Export operations
                self._create_action(
                    action_id="import_data",
                    label="Import Lists",  # TODO: Add to localization
                    handler=self._handle_import_data
                ),
                self._create_action(
                    action_id="export_all",
                    label="Export All Lists",  # TODO: Add to localization  
                    handler=self._handle_export_all
                ),
                
                # Backup operations
                self._create_action(
                    action_id="create_backup",
                    label="Create Backup",  # TODO: Add to localization
                    handler=self._handle_create_backup
                ),
                self._create_action(
                    action_id="restore_backup",
                    label="Restore Backup",  # TODO: Add to localization
                    handler=self._handle_restore_backup
                ),
                
                # Settings
                self._create_action(
                    action_id="settings",
                    label="Settings",  # TODO: Add to localization
                    handler=self._handle_settings
                ),
                
                # AI Search activation
                self._create_action(
                    action_id="ai_search_status",
                    label="AI Search Status",  # TODO: Add to localization
                    handler=self._handle_ai_search_status
                )
            ]
                
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error building main lists tools: %s", e)
            return []
    
    def _handle_create_new_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle creating new list"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._create_list_in_root(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error creating new list: %s", e)
            return DialogResponse(success=False, message="Error creating new list")
    
    def _handle_create_new_folder(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle creating new folder"""
        try:
            from lib.ui.folder_operations import FolderOperations
            folder_ops = FolderOperations(plugin_context)
            return folder_ops.create_folder(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error creating new folder: %s", e)
            return DialogResponse(success=False, message="Error creating new folder")
    
    def _handle_import_data(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle importing data"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_import(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error importing data: %s", e)
            return DialogResponse(success=False, message="Error importing data")
    
    def _handle_export_all(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle exporting all lists"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_export_all(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error exporting all: %s", e)
            return DialogResponse(success=False, message="Error exporting all")
    
    def _handle_create_backup(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle creating backup"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_backup(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error creating backup: %s", e)
            return DialogResponse(success=False, message="Error creating backup")
    
    def _handle_restore_backup(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle restoring backup"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_restore(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error restoring backup: %s", e)
            return DialogResponse(success=False, message="Error restoring backup")
    
    def _handle_settings(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle opening settings"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_settings(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error opening settings: %s", e)
            return DialogResponse(success=False, message="Error opening settings")
    
    def _handle_ai_search_status(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle AI search status"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_ai_search_activation_status(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error handling AI search status: %s", e)
            return DialogResponse(success=False, message="Error checking AI search status")