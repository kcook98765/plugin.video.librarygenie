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
    
    def __init__(self):
        super().__init__()
    
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build main lists tools menu"""
        try:
            actions = []
            
            # Search operations - Unified Local Search (with AI toggle when activated)
            actions.append(self._create_action(
                action_id="local_search",
                label="Local Search",
                handler=self._handle_local_search
            ))
            
            actions.append(self._create_action(
                action_id="search_history",
                label="Search History",  # TODO: Add to localization
                handler=self._handle_search_history
            ))
            
            # Creation operations
            actions.append(self._create_action(
                action_id="create_new_list",
                label="Create New List",  # TODO: Add to localization
                handler=self._handle_create_new_list
            ))
            actions.append(self._create_action(
                action_id="create_new_folder", 
                label="Create New Folder",  # TODO: Add to localization
                handler=self._handle_create_new_folder
            ))
            
            # Import/Export operations  
            actions.append(self._create_action(
                action_id="import_data",
                label="Import Lists from File",  # Match old system label
                handler=self._handle_import_data
            ))
            actions.append(self._create_action(
                action_id="export_all",
                label="Export All Lists",  # Match old system label
                handler=self._handle_export_all
            ))
            
            # Settings
            actions.append(self._create_action(
                action_id="settings",
                label="Settings & Preferences",  # Match old system label
                handler=self._handle_settings
            ))
            
            # Backup operations
            actions.append(self._create_action(
                action_id="create_backup",
                label="Database Backup",  # Match old system label
                handler=self._handle_create_backup
            ))
            actions.append(self._create_action(
                action_id="restore_backup",
                label="Restore from Backup",  # Match old system label
                handler=self._handle_restore_backup
            ))
            
            return actions
                
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
            return tools_handler._handle_create_list(plugin_context)
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
            return tools_handler._handle_import_lists(plugin_context)
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
            return tools_handler._handle_export_all_lists(plugin_context)
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
            return tools_handler._handle_create_backup(plugin_context)
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
            return tools_handler._handle_restore_backup_from_tools(plugin_context)
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
            return tools_handler._handle_open_settings(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error opening settings: %s", e)
            return DialogResponse(success=False, message="Error opening settings")
    
    def _handle_local_search(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle unified local search (movies and series)"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_unified_local_search(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error handling local search: %s", e)
            return DialogResponse(success=False, message="Error opening local search")

    def _handle_search_history(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle search history"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._handle_search_history(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.lists_main_provider')
            logger.error("Error handling search history: %s", e)
            return DialogResponse(success=False, message="Error opening search history")