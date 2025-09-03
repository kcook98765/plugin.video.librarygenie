#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any
from .plugin_context import PluginContext
import xbmcgui # Import xbmcgui for dialogs
import xbmc # Import xbmc for executebuiltin
import xbmcplugin # Import xbmcplugin for endOfDirectory
from .response_types import DirectoryResponse, DialogResponse # Import response types
from ..utils.logger import get_logger # Import logger


class Router:
    """Routes actions to appropriate handler functions"""

    def __init__(self):
        self.logger = None  # Will be set from context
        self._handlers: Dict[str, Callable] = {}
        self.favorites_handler = None # Placeholder for favorites handler
        self.tools_handler = None # Placeholder for tools handler

    def register_handler(self, action: str, handler: Callable):
        """Register a handler function for an action"""
        self._handlers[action] = handler

    def register_handlers(self, handlers: Dict[str, Callable]):
        """Register multiple handlers at once"""
        self._handlers.update(handlers)

    def dispatch(self, context: PluginContext) -> bool:
        """
        Dispatch request to appropriate handler based on context
        Returns True if handler was found and called, False otherwise
        """
        if self.logger is None:
            self.logger = get_logger(__name__)

        action = context.get_param('action', '')
        params = context.get_params() # Get all params for modular tools
        self.logger.debug(f"Router dispatching action: '{action}'")

        # Generate breadcrumb context for navigation
        from .breadcrumb_helper import get_breadcrumb_helper
        breadcrumb_helper = get_breadcrumb_helper()
        breadcrumb_path = breadcrumb_helper.get_breadcrumb_for_action(action, params, context.query_manager)

        # Add breadcrumb to context for handlers
        context.breadcrumb_path = breadcrumb_path

        try:
            # Handle special cases first
            if action == "scan_favorites_execute":
                # Assuming favorites_handler is initialized elsewhere or dynamically
                if not self.favorites_handler:
                    from .favorites_handler import FavoritesHandler
                    self.favorites_handler = FavoritesHandler()
                return self.favorites_handler.scan_favorites(context)

            elif action == "show_favorites_tools":
                if not self.favorites_handler:
                    from .favorites_handler import FavoritesHandler
                    self.favorites_handler = FavoritesHandler()
                return self.favorites_handler.show_favorites_tools(context)

            elif action == "save_favorites_as":
                if not self.favorites_handler:
                    from .favorites_handler import FavoritesHandler
                    self.favorites_handler = FavoritesHandler()
                return self.favorites_handler.save_favorites_as(context)

            elif action == "show_list_tools":
                from .tools_handler import ToolsHandler
                # Instantiate ToolsHandler here if it's not a singleton or managed globally
                if not self.tools_handler:
                    self.tools_handler = ToolsHandler()
                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')
                result = self.tools_handler.show_list_tools(context, list_type, list_id)

                # Handle DialogResponse - show notification if there's a message
                if hasattr(result, 'message') and result.message:
                    notification_type = xbmcgui.NOTIFICATION_INFO if result.success else xbmcgui.NOTIFICATION_ERROR
                    xbmcgui.Dialog().notification("LibraryGenie", result.message, notification_type)

                # Handle navigation flags for successful operations that require navigation
                if hasattr(result, 'success') and result.success:
                    if hasattr(result, 'navigate_to_folder') and result.navigate_to_folder:
                        # Navigate to specific folder (for search history deletion)
                        import xbmc
                        folder_id = result.navigate_to_folder
                        xbmc.executebuiltin(f'Container.Update({context.build_url("show_folder", folder_id=folder_id)},replace)')
                        # End directory properly to prevent fallback navigation
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'navigate_to_lists') and result.navigate_to_lists:
                        # Navigate to main lists menu (for list/folder deletion)
                        import xbmc
                        xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')
                        # End directory properly to prevent fallback navigation
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'navigate_to_main') and result.navigate_to_main:
                        # Navigate to main menu (for search history cleanup)
                        import xbmc
                        xbmc.executebuiltin(f'Container.Update({context.build_url("main_menu")},replace)')
                        # End directory properly to prevent fallback navigation
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'navigate_to_favorites') and result.navigate_to_favorites:
                        # Navigate back to favorites view after successful scan
                        import xbmc
                        xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')
                        # End directory properly
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                    elif hasattr(result, 'refresh_needed') and result.refresh_needed:
                        # Just refresh the current directory
                        import xbmc
                        xbmc.executebuiltin('Container.Refresh')
                        # End directory properly
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                        return True  # Prevent further processing
                elif hasattr(result, 'success') and not result.success:
                    # For failed/canceled operations, navigate back to the appropriate view
                    import xbmc
                    if list_type == 'folder' and list_id:
                        # Navigate back to the folder view
                        xbmc.executebuiltin(f'Container.Update({context.build_url("show_folder", folder_id=list_id)},replace)')
                    elif list_type == 'user_list' and list_id:
                        # Navigate back to the list view
                        xbmc.executebuiltin(f'Container.Update({context.build_url("show_list", list_id=list_id)},replace)')
                    elif list_type == 'favorites':
                        # Navigate back to favorites view
                        xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')
                    elif list_type == 'lists_main':
                        # Navigate back to main lists menu
                        xbmc.executebuiltin(f'Container.Update({context.build_url("lists")},replace)')

                return result.success if hasattr(result, 'success') else True

            elif action == "add_to_list":
                # Handle add to list from context menu
                success = self._handle_add_to_list_context(context)
                if success:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        "Added to list successfully", 
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )

            elif action == "quick_add":
                # Handle quick add to default list
                success = self._handle_quick_add_context(context)
                if success:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        "Quick added to default list", 
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )

            else:
                # Check for registered handlers for other actions
                handler = self._handlers.get(action)
                if not handler:
                    self.logger.debug(f"No handler found for action '{action}', will show main menu")
                    return False
                # Use the registered handler
                handler(context)
            return True

        except Exception as e:
            self.logger.error(f"Error in handler for action '{action}': {e}")
            import traceback
            self.logger.error(f"Handler error traceback: {traceback.format_exc()}")

            # Show error to user
            try:
                xbmcgui.Dialog().notification(
                    context.addon.getLocalizedString(35002),
                    f"Error in {action}",
                    xbmcgui.NOTIFICATION_ERROR
                )
            except Exception:
                pass

            return False

    def _handle_add_to_list(self, context: PluginContext, media_item_id: str) -> bool:
        """Handle adding media item to a list"""
        try:
            if not media_item_id:
                context.logger.error("No media item ID provided")
                return False

            query_manager = context.query_manager
            if not query_manager:
                context.logger.error("Failed to get query manager")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"):
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    result = lists_handler.create_list(context)
                    if result.success:
                        # Refresh lists and continue
                        all_lists = query_manager.get_all_lists_with_folders()
                    else:
                        return False
                else:
                    return False

            # Build list options for selection
            list_options = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(f"{lst['name']} ({lst['item_count']} items)")
                else:
                    list_options.append(f"{folder_name}/{lst['name']} ({lst['item_count']} items)")

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]")

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options)

            if selected_index < 0:
                return False

            # Handle selection
            if selected_index == len(list_options) - 1:  # Create new list
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                result = lists_handler.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders()
                if all_lists:
                    target_list_id = all_lists[-1]['id']  # Assume last created
                else:
                    return False
            else:
                target_list_id = all_lists[selected_index]['id']

            # Add item to selected list
            result = query_manager.add_item_to_list(target_list_id, media_item_id)

            if result.get("success"):
                list_name = all_lists[selected_index]['name'] if selected_index < len(all_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'",
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list",
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Failed to add to list",
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            context.logger.error(f"Error adding to list: {e}")
            return False

    def _handle_add_to_list_context(self, context: PluginContext) -> bool:
        """Handle adding media item to a list from context menu"""
        try:
            media_item_id = context.get_param('media_item_id')
            if not media_item_id:
                context.logger.error("No media item ID provided for context menu add")
                return False

            query_manager = context.query_manager
            if not query_manager:
                context.logger.error("Failed to get query manager for context menu add")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"):
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    result = lists_handler.create_list(context)
                    if result.success:
                        all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                    else:
                        return False
                else:
                    return False

            if not all_lists: # Still no lists after offering to create
                xbmcgui.Dialog().notification("LibraryGenie", "No lists available to add to.", xbmcgui.NOTIFICATION_WARNING)
                return False
            
            # Build list options for selection
            list_options = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(f"{lst['name']} ({lst['item_count']} items)")
                else:
                    list_options.append(f"{folder_name}/{lst['name']} ({lst['item_count']} items)")

            # Add option to create new list
            list_options.append("[COLOR yellow]+ Create New List[/COLOR]")

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options)

            if selected_index < 0:
                return False # User cancelled

            # Handle selection
            target_list_id = None
            if selected_index == len(list_options) - 1:  # Create new list
                from .lists_handler import ListsHandler
                lists_handler = ListsHandler()
                result = lists_handler.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                if all_lists:
                    target_list_id = all_lists[-1]['id']  # Assume last created
                else:
                    return False # Should not happen if create_list succeeded
            else:
                target_list_id = all_lists[selected_index]['id']

            if target_list_id is None:
                return False

            # Add item to selected list
            result = query_manager.add_item_to_list(target_list_id, media_item_id)

            if result.get("success"):
                list_name = all_lists[selected_index]['name'] if selected_index < len(all_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'",
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list",
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Failed to add to list",
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            self.logger.error(f"Error adding to list from context: {e}")
            return False

    def _handle_quick_add_context(self, context: PluginContext) -> bool:
        """Handle quick add to default list from context menu"""
        try:
            # Get parameters
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')

            # Get settings
            from ..config.settings import SettingsManager
            settings = SettingsManager()
            default_list_id = settings.get_default_list_id()

            if not default_list_id:
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "No default list configured", 
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return False

            # Initialize query manager
            query_manager = context.query_manager
            if not query_manager:
                return False

            # Create external item data
            external_item = {
                'title': context.get_param('title', 'Unknown'),
                'dbtype': dbtype,
                'dbid': dbid,
                'source': 'context_menu'
            }

            # Add to default list
            result = query_manager.add_external_item_to_list(default_list_id, external_item)
            return result.get('success', False)

        except Exception as e:
            self.logger.error(f"Error quick adding to list from context: {e}")
            return False

    def _handle_add_external_item_to_list(self, context: PluginContext) -> bool:
        """Handle adding external/plugin item to a list"""
        try:
            # Extract external item data from URL parameters
            external_data = {}
            for key, value in context.get_params().items():
                if key not in ('action', 'external_item'):
                    external_data[key] = value

            if not external_data.get('title'):
                context.logger.error("No title found for external item")
                return False

            # Convert to format expected by add_to_list system
            media_item = {
                'id': f"external_{hash(external_data.get('file_path', external_data['title']))}",
                'title': external_data['title'],
                'media_type': external_data.get('media_type', 'movie'),
                'source': 'external'
            }

            # Copy over all the gathered metadata
            for key in ['originaltitle', 'year', 'plot', 'rating', 'votes', 'genre', 
                       'director', 'studio', 'country', 'mpaa', 'runtime', 'premiered',
                       'playcount', 'lastplayed', 'poster', 'fanart', 'thumb', 
                       'banner', 'clearlogo', 'imdbnumber', 'file_path']:
                if key in external_data:
                    media_item[key] = external_data[key]

            # Episode-specific fields
            if external_data.get('media_type') == 'episode':
                for key in ['tvshowtitle', 'season', 'episode', 'aired']:
                    if key in external_data:
                        media_item[key] = external_data[key]

            # Music video-specific fields
            elif external_data.get('media_type') == 'musicvideo':
                for key in ['artist', 'album']:
                    if key in external_data:
                        media_item[key] = external_data[key]

            context.logger.info(f"Processing external item: {media_item['title']} (type: {media_item['media_type']})")

            # Use existing add_to_list flow with the external media item
            query_manager = context.query_manager
            if not query_manager:
                context.logger.error("Failed to get query manager")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"):
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    result = lists_handler.create_list(context)
                    if result.success:
                        # Refresh lists and continue
                        all_lists = query_manager.get_all_lists_with_folders()
                    else:
                        return False
                else:
                    return False

            # Build list selection options
            list_options = []
            list_ids = []

            for item in all_lists:
                if item.get('type') == 'list':
                    list_name = item['name']
                    list_options.append(list_name)
                    list_ids.append(item['id'])

            if not list_options:
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "No lists available", 
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return False

            # Show list selection dialog
            selected_index = xbmcgui.Dialog().select(
                f"Add '{media_item['title']}' to list:",
                list_options
            )

            if selected_index < 0:
                return False  # User cancelled

            selected_list_id = list_ids[selected_index]
            selected_list_name = list_options[selected_index]

            # Add the external item to the selected list
            success = query_manager.add_external_item_to_list(selected_list_id, media_item)

            if success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    f"Added '{media_item['title']}' to '{selected_list_name}'", 
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                # Refresh container to show changes
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "Failed to add item to list", 
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False

        except Exception as e:
            context.logger.error(f"Error in _handle_add_external_item_to_list: {e}")
            return False

    def _handle_favorites(self, context: PluginContext) -> None:
        """Handle favorites menu action"""
        try:
            from .favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            response = favorites_handler.show_favorites_menu(context)

            if isinstance(response, DirectoryResponse):
                # Directory response is already handled by show_favorites_menu
                return
            else:
                # Fallback if unexpected response type
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)

        except Exception as e:
            self.logger.error(f"Error in favorites handler: {e}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)

    def _handle_scan_favorites(self, context: PluginContext) -> None:
        """Handle scan favorites action"""
        try:
            from .favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            response = favorites_handler.scan_favorites(context)

            if isinstance(response, DialogResponse) and response.success:
                if response.refresh_needed:
                    # Refresh the container to show updated favorites
                    xbmc.executebuiltin('Container.Refresh')

                if response.message:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )
            elif isinstance(response, DialogResponse):
                # Show error message
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message or "Scan failed",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )

        except Exception as e:
            self.logger.error(f"Error in scan favorites handler: {e}")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Error scanning favorites",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

    def _handle_save_favorites_as(self, context: PluginContext) -> None:
        """Handle save favorites as action"""
        try:
            from .favorites_handler import FavoritesHandler
            favorites_handler = FavoritesHandler()
            response = favorites_handler.save_favorites_as(context)

            if isinstance(response, DialogResponse) and response.success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message or "Favorites saved as new list",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )

                # Optionally refresh to show new list
                if response.refresh_needed:
                    xbmc.executebuiltin('Container.Refresh')

            elif isinstance(response, DialogResponse):
                if response.message:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )

        except Exception as e:
            self.logger.error(f"Error in save favorites as handler: {e}")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Error saving favorites",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

    def _handle_noop(self, context: PluginContext) -> None:
        """Handle no-op action"""
        try:
            # Just end the directory with no items
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
        except Exception as e:
            self.logger.error(f"Error in noop handler: {e}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)