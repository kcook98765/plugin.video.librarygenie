
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
from ..utils.logger import get_logger


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
                    message="Unknown list type"
                )

        except Exception as e:
            self.logger.error(f"Error showing list tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing tools & options"
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
            scan_option = "🔄 Scan Favorites"
            
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
                    
                    scan_option = f"🔄 Scan Favorites ({time_ago})"
                except Exception as e:
                    context.logger.debug(f"Could not parse last scan time: {e}")

            # Build options for favorites
            options = [
                scan_option,
                "💾 Save As New List",
                "❌ Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Favorites Tools & Options", options)

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

            # Build options for user lists
            options = [
                f"✏️ Rename '{list_info['name']}'",
                f"📤 Export '{list_info['name']}'",
                f"🗑️ Delete '{list_info['name']}'",
                "❌ Cancel"
            ]

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("List Tools & Options", options)

            if selected_index < 0 or selected_index == 3:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if selected_index == 0:  # Rename
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.rename_list(context, list_id)
            elif selected_index == 1:  # Export
                # TODO: Implement export functionality
                return DialogResponse(
                    success=False,
                    message="Export functionality coming soon"
                )
            elif selected_index == 2:  # Delete
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

            # Build options for folders
            options = []
            if not is_reserved:
                options.extend([
                    f"✏️ Rename '{folder_info['name']}'",
                    f"🗑️ Delete '{folder_info['name']}'"
                ])
            
            options.extend([
                f"📤 Export All Lists in '{folder_info['name']}'",
                "❌ Cancel"
            ])

            # Show selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Folder Tools & Options", options)

            if selected_index < 0 or selected_index == len(options) - 1:  # Cancel
                return DialogResponse(success=False)

            # Handle selected option
            if not is_reserved and selected_index == 0:  # Rename
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.rename_folder(context, folder_id)
            elif not is_reserved and selected_index == 1:  # Delete
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                return lists_handler.delete_folder(context, folder_id)
            elif (not is_reserved and selected_index == 2) or (is_reserved and selected_index == 0):  # Export
                # TODO: Implement export functionality
                return DialogResponse(
                    success=False,
                    message="Export functionality coming soon"
                )

            return DialogResponse(success=False)

        except Exception as e:
            self.logger.error(f"Error showing folder tools: {e}")
            return DialogResponse(
                success=False,
                message="Error showing folder tools"
            )
