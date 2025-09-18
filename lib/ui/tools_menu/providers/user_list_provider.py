#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - User List Tools Provider  
Provides tools for user list context
"""

from typing import List, Any
from ..types import ToolAction, ToolsContext, ConfirmSpec
from .base_provider import BaseToolsProvider
from lib.ui.localization import L
from lib.ui.response_types import DialogResponse


class UserListToolsProvider(BaseToolsProvider):
    """Provider for user list tools"""
    
    def __init__(self):
        super().__init__()
    
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build user list tools menu"""
        try:
            # Get list info to determine available operations
            query_manager = plugin_context.query_manager
            if not query_manager or not context.list_id:
                return []
                
            list_info = query_manager.get_list_by_id(context.list_id)
            if not list_info:
                return []
                
            # Check list type to determine available operations
            is_search_history = list_info.get('folder_name') == 'Search History'
            is_kodi_favorites = list_info.get('name') == 'Kodi Favorites'
            
            # Helper to shorten names for display
            def shorten_name(name: str, max_length: int = 30) -> str:
                if len(name) <= max_length:
                    return name
                if name.startswith("Search: '") and "' (" in name:
                    search_part = name.split("' (")[0].replace("Search: '", "")
                    if len(search_part) <= max_length - 3:
                        return f"'{search_part}'"
                    else:
                        return f"'{search_part[:max_length-6]}...'"
                return f"{name[:max_length-3]}..."
            
            short_name = shorten_name(list_info['name'])
            
            if is_search_history:
                return [
                    self._create_action(
                        action_id="move_to_new_list",
                        label=L(97022),  # "Move to New List"
                        handler=self._handle_move_to_new_list,
                        payload={"list_id": context.list_id}
                    ),
                    self._create_action(
                        action_id="export_list",
                        label=L(96053).replace('%s', short_name),  # "Export %s"
                        handler=self._handle_export_list,
                        payload={"list_id": context.list_id}
                    ),
                    self._create_action(
                        action_id="delete_list",
                        label=L(96054).replace('%s', short_name),  # "Delete %s"
                        handler=self._handle_delete_list,
                        payload={"list_id": context.list_id, "is_search_history": True},
                        needs_confirmation=ConfirmSpec(
                            title="Delete List",
                            message=f"Delete list '{list_info['name']}'?"
                        )
                    )
                ]
            elif is_kodi_favorites:
                return [
                    self._create_action(
                        action_id="save_as_list",
                        label=L(96002),  # "Save As New List"
                        handler=self._handle_save_as_list
                    )
                ]
            else:
                # Standard list tools
                return [
                    self._create_action(
                        action_id="merge_lists",
                        label=L(96004).replace('%s', short_name),  # "Merge Into %s"
                        handler=self._handle_merge_lists,
                        payload={"list_id": context.list_id}
                    ),
                    self._create_action(
                        action_id="rename_list",
                        label=L(96005).replace('%s', short_name),  # "Rename '%s'"
                        handler=self._handle_rename_list,
                        payload={"list_id": context.list_id}
                    ),
                    self._create_action(
                        action_id="move_list",
                        label=L(96011).replace('%s', short_name),  # "Move '%s' to Folder"
                        handler=self._handle_move_list,
                        payload={"list_id": context.list_id}
                    ),
                    self._create_action(
                        action_id="export_list",
                        label=L(96053).replace('%s', short_name),  # "Export %s"
                        handler=self._handle_export_list,
                        payload={"list_id": context.list_id}
                    ),
                    self._create_action(
                        action_id="delete_list",
                        label=L(96054).replace('%s', short_name),  # "Delete %s"
                        handler=self._handle_delete_list,
                        payload={"list_id": context.list_id},
                        needs_confirmation=ConfirmSpec(
                            title="Delete List",
                            message=f"Delete list '{list_info['name']}'?"
                        )
                    )
                ]
                
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error building user list tools: %s", e)
            return []
    
    def _handle_move_to_new_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle moving search history to new list"""
        try:
            # Implementation mirrors _copy_search_history_to_list from original
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._copy_search_history_to_list(plugin_context, payload["list_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error moving to new list: %s", e)
            return DialogResponse(success=False, message="Error moving to new list")
    
    def _handle_merge_lists(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle merging lists"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._merge_lists(plugin_context, payload["list_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error merging lists: %s", e)
            return DialogResponse(success=False, message="Error merging lists")
    
    def _handle_rename_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle renaming list"""
        try:
            from lib.ui.lists_handler import ListsHandler
            lists_handler = ListsHandler(plugin_context)
            result = lists_handler.rename_list(plugin_context, payload["list_id"])
            
            if result.success:
                result.navigate_to_lists = True
                result.refresh_needed = False
                
            return result
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error renaming list: %s", e)
            return DialogResponse(success=False, message="Error renaming list")
    
    def _handle_move_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle moving list to folder"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._move_list_to_folder(plugin_context, payload["list_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error moving list: %s", e)
            return DialogResponse(success=False, message="Error moving list")
    
    def _handle_export_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle exporting list"""
        try:
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler._export_single_list(plugin_context, payload["list_id"])
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error exporting list: %s", e)
            return DialogResponse(success=False, message="Error exporting list")
    
    def _handle_delete_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle deleting list"""
        try:
            from lib.ui.lists_handler import ListsHandler
            lists_handler = ListsHandler(plugin_context)
            result = lists_handler.delete_list(plugin_context, payload["list_id"])
            
            # Handle special navigation for search history
            if payload.get("is_search_history") and result.success:
                query_manager = plugin_context.query_manager
                search_folder_id = query_manager.get_or_create_search_history_folder()
                remaining_lists = query_manager.get_lists_in_folder(search_folder_id)
                
                if remaining_lists:
                    result.navigate_to_folder = search_folder_id
                else:
                    result.navigate_to_main = True
                    
            return result
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error deleting list: %s", e)
            return DialogResponse(success=False, message="Error deleting list")
    
    def _handle_save_as_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle saving as new list (for Kodi Favorites)"""
        try:
            from lib.ui.favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            return favorites_handler.save_favorites_as(plugin_context)
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.user_list_provider')
            logger.error("Error saving as list: %s", e)
            return DialogResponse(success=False, message="Error saving as list")