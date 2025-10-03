#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Router
Handles action routing and dispatch for plugin requests
"""

from typing import Dict, Callable, Any, Optional
from lib.ui.plugin_context import PluginContext
import xbmcgui
import xbmcplugin
import time
import threading
from lib.utils.kodi_log import get_kodi_logger
from lib.ui.dialog_service import get_dialog_service
# Router uses manual error handling due to boolean return type


class Router:
    """Routes actions to appropriate handler functions"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.router')
        self._handlers: Dict[str, Callable] = {}
        self.dialog_service = get_dialog_service('lib.ui.router')

    def _get_current_route_info(self):
        """Get current route information for navigation decisions"""
        try:
            import xbmc
            current_path = xbmc.getInfoLabel('Container.FolderPath')

            # Extract action and parameters from current path
            if 'action=' in current_path:
                # Parse current route parameters
                import urllib.parse
                parsed = urllib.parse.urlparse(current_path)
                params = urllib.parse.parse_qs(parsed.query)
                # Flatten parameter values
                current_params = {k: v[0] if v else '' for k, v in params.items()}
                current_route = current_params.get('action', '')
            else:
                current_route = None
                current_params = {}

            self.logger.debug("ROUTER: Current route info - route: %s, params: %s", current_route, current_params)
            return current_route, current_params
        except Exception as e:
            self.logger.warning("ROUTER: Error getting current route info: %s", e)
            return None, {}

    def _get_safe_return_location(self, current_path: str) -> Optional[str]:
        """Get a safe return location that won't create navigation loops"""
        try:
            if not current_path or not isinstance(current_path, str):
                return None
            
            # Skip URLs that contain problematic actions that could create loops
            problematic_actions = ['show_list_tools', 'noop']
            
            if 'action=' in current_path:
                import urllib.parse
                parsed = urllib.parse.urlparse(current_path)
                params = urllib.parse.parse_qs(parsed.query)
                
                # Check if this URL contains any problematic actions
                action = params.get('action', [''])[0]
                if action in problematic_actions:
                    self.logger.debug("ROUTER: Skipping problematic action URL: %s", current_path)
                    return None
            
            # Additional safety check - avoid storing URLs with specific problematic actions
            if 'show_list_tools' in current_path:
                self.logger.debug("ROUTER: Avoiding problematic action URL: %s", current_path)
                return None
            
            # If we get here, the path should be safe to use as return location
            return current_path
            
        except Exception as e:
            self.logger.warning("ROUTER: Error filtering return location '%s': %s", current_path, e)
            return None

    def register_handler(self, action: str, handler: Callable):
        """Register a handler function for an action"""
        self._handlers[action] = handler

    def register_handlers(self, handlers: Dict[str, Callable]):
        """Register multiple handlers at once"""
        self._handlers.update(handlers)

    def _navigate_smart(self, next_route: str, reason: str = "navigation", next_params: Optional[Dict[str, Any]] = None):
        """Navigate using navigation policy to determine push vs replace"""
        try:
            from lib.ui.nav_policy import decide_mode
            from lib.ui.nav import get_navigator

            current_route, current_params = self._get_current_route_info()
            next_params = next_params or {}

            # Decide navigation mode
            mode = decide_mode(current_route, next_route, reason, current_params, next_params)

            navigator = get_navigator()
            if mode == 'push':
                navigator.push(next_route)
            else:  # replace
                navigator.replace(next_route)

            self.logger.debug("ROUTER: Smart navigation - mode: %s, route: %s", mode, next_route)

        except Exception as e:
            self.logger.error("ROUTER: Error in smart navigation: %s", e)
            # Fallback to push
            from lib.ui.nav import push
            push(next_route)

    def _handle_refresh_import(self, context: PluginContext, folder_id: str):
        """Handle refresh import action"""
        try:
            # Get folder info to retrieve import_source_id
            folder_info = context.query_manager.get_folder_info(int(folder_id))
            if not folder_info:
                self.dialog_service.ok("Error", "Folder not found.")
                return
            
            import_source_id = folder_info.get('import_source_id')
            if not import_source_id:
                self.dialog_service.ok("Error", "This folder is not from an import.")
                return
            
            # Get import source record to retrieve source_url
            conn = context.query_manager.connection_manager.get_connection()
            import_source = conn.execute(
                "SELECT source_url, folder_id FROM import_sources WHERE id = ?",
                (import_source_id,)
            ).fetchone()
            
            if not import_source:
                self.dialog_service.ok("Error", "Import source not found.")
                return
            
            source_url = import_source['source_url']
            root_folder_id = import_source['folder_id']
            folder_name = folder_info.get('name')
            
            # Show confirmation dialog
            if not self.dialog_service.yesno(
                "Refresh Import",
                f"Refresh content from:[CR]{source_url}[CR][CR]This will delete all imported content and re-scan the source."
            ):
                return
            
            # Show progress dialog
            progress = xbmcgui.DialogProgressBG()
            progress.create("Refreshing Import", "Preparing...")
            
            try:
                # Delete the import source (cascade deletes all locked content)
                progress.update(20, "Removing old content...")
                conn.execute("DELETE FROM import_sources WHERE id = ?", (import_source_id,))
                conn.commit()
                
                # Re-run the import
                progress.update(40, "Re-scanning source...")
                from lib.import_export.import_handler import ImportHandler
                import_handler = ImportHandler(context.query_manager.connection_manager)
                
                def update_progress(message):
                    progress.update(60, message)
                
                # This should always be the root wrapper folder
                # Get its parent and name for re-import
                parent_folder_id = folder_info.get('parent_id')
                root_name = folder_name
                
                result = import_handler.import_from_source(
                    source_url,
                    target_folder_id=parent_folder_id,
                    progress_callback=update_progress,
                    root_folder_name=root_name
                )
                
                progress.update(100, "Complete")
                progress.close()
                
                # Show result
                if result.get('success'):
                    self.dialog_service.ok(
                        "Import Refreshed",
                        f"Successfully refreshed:[CR]" +
                        f"Folders: {result.get('folders_created', 0)}[CR]" +
                        f"Lists: {result.get('lists_created', 0)}[CR]" +
                        f"Items: {result.get('items_imported', 0)}"
                    )
                    # Refresh the view
                    import xbmc
                    xbmc.executebuiltin('Container.Refresh')
                else:
                    errors = result.get('errors', [])
                    error_msg = errors[0] if errors else "Unknown error"
                    self.dialog_service.ok("Import Failed", f"Error: {error_msg}")
            
            except Exception as e:
                progress.close()
                self.logger.error("Error during refresh import: %s", e)
                self.dialog_service.ok("Error", f"Failed to refresh import: {str(e)}")
        
        except Exception as e:
            self.logger.error("Error in _handle_refresh_import: %s", e)
            self.dialog_service.ok("Error", f"Failed to refresh import: {str(e)}")

    def _handle_delete_files_import(self, context: PluginContext, import_source_id: int):
        """Handle delete files import action"""
        try:
            # Show confirmation dialog with warning
            if not self.dialog_service.yesno(
                "Delete Files Import",
                "This will remove the entire file structure from the top parent folder down, including all folders and lists. This cannot be undone."
            ):
                return
            
            # Delete the import_source record (cascades to delete all related folders and lists)
            conn = context.query_manager.connection_manager.get_connection()
            conn.execute("DELETE FROM import_sources WHERE id = ?", (import_source_id,))
            conn.commit()
            
            # Show success notification
            import xbmc
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Files import deleted successfully",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            
            # Refresh container
            xbmc.executebuiltin('Container.Refresh')
            
        except Exception as e:
            self.logger.error("Error in _handle_delete_files_import: %s", e)
            self.dialog_service.ok("Error", f"Failed to delete import: {str(e)}")

    def _handle_export_folder_and_lists(self, context: PluginContext, folder_id: str):
        """Handle export folder and lists action"""
        try:
            # Get folder info
            folder_info = context.query_manager.get_folder_info(int(folder_id))
            if not folder_info:
                self.dialog_service.ok("Error", "Folder not found.")
                return
            
            # Use ExportEngine to export the folder and all its lists
            from lib.import_export.export_engine import ExportEngine
            export_engine = ExportEngine()
            
            # Export lists and folders for this folder (including subfolders)
            context_filter = {
                'folder_id': int(folder_id),
                'include_subfolders': True
            }
            
            result = export_engine.export_data(
                export_types=['lists', 'list_items', 'folders'],
                context_filter=context_filter
            )
            
            # Show result dialog
            if result.get('success'):
                self.dialog_service.ok(
                    "Export Successful",
                    f"Exported to:[CR]{result.get('file_path', 'unknown')}[CR][CR]" +
                    f"Total items: {result.get('total_items', 0)}"
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                self.dialog_service.ok("Export Failed", f"Error: {error_msg}")
                
        except Exception as e:
            self.logger.error("Error in _handle_export_folder_and_lists: %s", e)
            self.dialog_service.ok("Error", f"Failed to export: {str(e)}")

    def _handle_show_context_more_menu(self, context: PluginContext):
        """Handle show context more menu action"""
        try:
            from lib.ui.localization import L
            
            # Get parameters
            item_type = context.get_param('item_type', 'folder')
            item_id = context.get_param('item_id')
            parent_folder_id = context.get_param('parent_folder_id', '')
            is_files_source = int(context.get_param('is_files_source', '0'))
            is_reserved = int(context.get_param('is_reserved', '0'))
            
            # Build options list with actions
            options = []
            actions = []
            
            # Add Move and Export options for user-created items (not file-sourced, not reserved)
            if is_files_source == 0 and is_reserved == 0:
                if item_type == 'folder':
                    options.append(L(31023) or "Move Folder")
                    actions.append('move_folder')
                    options.append(L(31024) or "Export Folder and Lists")
                    actions.append('export_folder')
                elif item_type == 'list':
                    options.append(L(30223).replace('%s', 'List') if L(30223) else "Move to Folder")
                    actions.append('move_list')
                    options.append(L(31025) or "Export List")
                    actions.append('export_list')
            
            # Add common options
            options.append("Search")
            actions.append('search')
            options.append("Settings")
            actions.append('settings')
            
            # Only add "Add Folder" and "Add List" for folders (not lists, not file-sourced, not reserved)
            # These operations need parent_folder_id context
            if item_type == 'folder' and is_files_source == 0 and is_reserved == 0:
                options.append("Add Folder")
                actions.append('add_folder')
                options.append("Add List")
                actions.append('add_list')
            
            # Show dialog
            import xbmcgui
            selected_index = xbmcgui.Dialog().select("More Options", list(options))
            
            if selected_index < 0:
                return
            
            selected_action = actions[selected_index]
            
            # Execute selected action
            if selected_action == 'move_folder':
                # Navigate to move folder action
                import xbmc
                xbmc.executebuiltin(f'RunPlugin(plugin://plugin.video.librarygenie/?action=move_folder&folder_id={item_id})')
            elif selected_action == 'export_folder':
                # Navigate to export folder action
                import xbmc
                xbmc.executebuiltin(f'RunPlugin(plugin://plugin.video.librarygenie/?action=export_folder_and_lists&folder_id={item_id})')
            elif selected_action == 'move_list':
                # Navigate to move list action
                import xbmc
                xbmc.executebuiltin(f'RunPlugin(plugin://plugin.video.librarygenie/?action=move_list_to_folder&list_id={item_id})')
            elif selected_action == 'export_list':
                # Navigate to export list action
                import xbmc
                xbmc.executebuiltin(f'RunPlugin(plugin://plugin.video.librarygenie/?action=export_list&list_id={item_id})')
            elif selected_action == 'search':
                # Navigate to search menu
                import xbmc
                xbmc.executebuiltin('ActivateWindow(Videos,plugin://plugin.video.librarygenie/?action=prompt_and_search,return)')
            elif selected_action == 'settings':
                # Open addon settings
                import xbmc
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.librarygenie)')
            elif selected_action == 'add_folder':
                # Add subfolder using the current folder as parent (item_id is the folder to add to)
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler._create_subfolder(context, str(item_id))
                
                # Handle response
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                response_handler.handle_dialog_response(result, context)
            elif selected_action == 'add_list':
                # Add list to the current folder (item_id is the folder to add to)
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler._create_list_in_folder(context, str(item_id))
                
                # Handle response
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                response_handler.handle_dialog_response(result, context)
                
        except Exception as e:
            self.logger.error("Error in _handle_show_context_more_menu: %s", e)
            self.dialog_service.ok("Error", f"Failed to show menu: {str(e)}")

    def dispatch(self, context: PluginContext) -> bool:
        """
        Dispatch request to appropriate handler based on context
        Returns True if handler was found and called, False otherwise
        """
        action = context.get_param('action', '')
        params = context.get_params() # Get all params for modular tools
        self.logger.debug("Router dispatching action: '%s'", action)

        # Generate breadcrumb context for navigation (skip for Tools & Options for performance)
        if action != "show_list_tools":
            from lib.ui.breadcrumb_helper import get_breadcrumb_helper
            breadcrumb_helper = get_breadcrumb_helper()
            # Don't auto-initialize DB for breadcrumbs - pass None to let breadcrumb helper decide
            breadcrumb_path = breadcrumb_helper.get_breadcrumb_for_action(action, params, None)
            # Add breadcrumb to context for handlers
            # Set as attribute dynamically since it's not part of the PluginContext type definition
            setattr(context, 'breadcrumb_path', breadcrumb_path)
        else:
            # Tools & Options don't need breadcrumbs - skip for performance
            setattr(context, 'breadcrumb_path', None)

        # Handle special router-managed actions
        try:
            if action == "show_list_tools":
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                from lib.ui.session_state import get_session_state

                # Store current location for returning after tools operations
                import xbmc
                current_path = xbmc.getInfoLabel('Container.FolderPath')
                session_state = get_session_state()
                
                # Filter out problematic URLs that would create navigation loops
                safe_return_path = self._get_safe_return_location(current_path)
                if safe_return_path:
                    session_state.set_tools_return_location(safe_return_path)
                    self.logger.debug("ROUTER: Set safe tools return location: %s", safe_return_path)
                else:
                    self.logger.debug("ROUTER: No safe return location found, will not set tools return location")

                factory = get_handler_factory()
                factory.context = context # Set context before using factory
                tools_handler = factory.get_tools_handler()
                response_handler = get_response_handler()

                list_type = params.get('list_type', 'unknown')
                list_id = params.get('list_id')

                result = tools_handler.show_list_tools(context, list_type, list_id)

                # Use response handler to process the result - ensure we don't return anything that would cause fallthrough
                response_handler.handle_dialog_response(result, context)

                # Check if this is a settings operation - if so, skip endOfDirectory to prevent empty list flash
                if hasattr(result, 'is_settings_operation') and result.is_settings_operation:
                    # For settings operations, don't call endOfDirectory to prevent empty directory display
                    return True
                else:
                    # End directory properly to prevent Kodi from trying to load this as a directory
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                    return True  # Always return True to prevent fallthrough to main menu
            elif action == "noop":
                return self._handle_noop(context)
            elif action == "toggle_tools_menu_item":
                return self._handle_toggle_tools_menu_item(context)
            elif action == "set_startup_folder":
                return self._handle_set_startup_folder(context)
            elif action == "clear_startup_folder":
                return self._handle_clear_startup_folder(context)
            elif action == 'lists' or action == 'show_lists_menu':
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                response_handler = get_response_handler()
                response = lists_handler.show_lists_menu(context)
                return response_handler.handle_directory_response(response, context)
            elif action == 'show_main_menu_force':
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                response_handler = get_response_handler()
                response = lists_handler.show_lists_menu(context, force_main_menu=True)
                return response_handler.handle_directory_response(response, context)
            elif action == 'prompt_and_search':
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                from lib.ui.nav import finish_directory
                
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                response_handler = get_response_handler()
                
                # Use unified search which properly handles custom panel and cancellation
                result = tools_handler._handle_unified_local_search(context)
                
                # Handle DialogResponse properly
                if hasattr(result, 'success'):
                    if result.success and not result.message.startswith("Search cancelled"):
                        # Search succeeded and wasn't cancelled
                        return True
                    else:
                        # Search was cancelled or no results - close directory gracefully
                        finish_directory(context.addon_handle, succeeded=True, update=False)
                        return True
                else:
                    # Fallback for non-DialogResponse
                    succeeded = bool(result) if result is not None else True
                    finish_directory(context.addon_handle, succeeded=succeeded, update=False)
                    return succeeded
            elif action == 'save_bookmark_from_context' or action == 'save_bookmark':
                # Redirect old bookmark actions to the new integrated approach
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()
                result = lists_handler.add_external_item_to_list(context)
                
                # Handle context menu invocation properly - always end directory for external context
                if context.is_from_outside_plugin():
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                
                return result if isinstance(result, bool) else True
                
            elif action == 'navigate_bookmark':
                # Handle bookmark navigation - navigate out of plugin to stored URL
                return self._handle_navigate_bookmark(context)
            elif action == 'rename_bookmark':
                # Handle bookmark renaming
                return self._handle_rename_bookmark(context)
            elif action == 'remove_bookmark':
                # Handle bookmark removal
                return self._handle_remove_bookmark(context)
            elif action == 'add_external_item':
                # Handle adding external item (including bookmarks) to list
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()
                result = lists_handler.add_external_item_to_list(context)
                
                # Handle context menu invocation properly - always end directory for external context
                if context.is_from_outside_plugin():
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                
                return result if isinstance(result, bool) else True
            elif action == 'import_file_media':
                # Handle Import File Media action from context menu
                source_url = context.get_param('source_url')
                succeeded = False
                
                try:
                    if not source_url:
                        self.logger.error("Import file media: missing source_url parameter")
                        import xbmcgui
                        xbmcgui.Dialog().notification(
                            "LibraryGenie",
                            "Import failed: No folder path provided",
                            xbmcgui.NOTIFICATION_ERROR,
                            3000
                        )
                    else:
                        # Get default folder name from source path (handle URLs and paths)
                        import os
                        import re
                        
                        # Strip scheme (smb://, nfs://, special://) if present
                        path_without_scheme = source_url.split('://', 1)[-1] if '://' in source_url else source_url
                        # Split on both forward and back slashes, take last non-empty segment
                        segments = [s for s in re.split(r'[/\\]+', path_without_scheme) if s]
                        default_name = segments[-1] if segments else "Imported Media"
                        
                        # Prompt user for folder name
                        import xbmcgui
                        folder_name = self.dialog_service.input(
                            "Enter name for import folder:",
                            default=default_name,
                            input_type=xbmcgui.INPUT_ALPHANUM
                        )
                        
                        # Check if user cancelled
                        if not folder_name or not folder_name.strip():
                            self.logger.debug("Import cancelled by user")
                            succeeded = False
                        else:
                            # Sanitize folder name
                            folder_name = folder_name.strip()
                            # Remove forbidden characters and control characters
                            folder_name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', '', folder_name)
                            folder_name = ' '.join(folder_name.split())  # Collapse whitespace
                            
                            if not folder_name:
                                self.logger.error("Invalid folder name after sanitization")
                                import xbmcgui
                                xbmcgui.Dialog().notification(
                                    "LibraryGenie",
                                    "Import failed: Invalid folder name",
                                    xbmcgui.NOTIFICATION_ERROR,
                                    3000
                                )
                                succeeded = False
                            else:
                                from lib.import_export.import_handler import ImportHandler
                                from lib.data.storage_manager import get_storage_manager
                                
                                storage = get_storage_manager()
                                import_handler = ImportHandler(storage)
                                results = import_handler.import_from_source(source_url, root_folder_name=folder_name)
                                
                                # Check if import actually succeeded
                                if results.get('success'):
                                    succeeded = True
                                    # Navigate directly to the imported root folder
                                    import xbmc
                                    root_folder_id = results.get('root_folder_id')
                                    if root_folder_id:
                                        folder_url = f"plugin://plugin.video.librarygenie/?action=show_folder&folder_id={root_folder_id}"
                                        xbmc.executebuiltin(f'ActivateWindow(Videos,{folder_url},return)')
                                        self.logger.info("Navigating to imported folder: %s", root_folder_id)
                                    else:
                                        # Fallback to plugin root if no folder_id (shouldn't happen)
                                        xbmc.executebuiltin('ActivateWindow(Videos,plugin://plugin.video.librarygenie/,return)')
                                else:
                                    self.logger.error("Import failed: %s", results.get('errors'))
                                    error_msg = '; '.join(results.get('errors', ['Unknown error']))[:100]
                                    import xbmcgui
                                    xbmcgui.Dialog().notification(
                                        "LibraryGenie",
                                        f"Import failed: {error_msg}",
                                        xbmcgui.NOTIFICATION_ERROR,
                                        5000
                                    )
                                    succeeded = False
                except Exception as e:
                    self.logger.error("Import file media failed: %s", str(e))
                    import xbmcgui
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Import failed: {str(e)}",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                finally:
                    # Always end directory for context menu actions
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=succeeded)
                return True
            elif action == 'add_to_list':
                media_item_id = context.get_param('media_item_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')

                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()

                # Check if this is a context action (called from outside the plugin)
                import xbmc
                container_path = xbmc.getInfoLabel('Container.FolderPath')
                is_context_action = not container_path or 'plugin.video.librarygenie' not in container_path

                if media_item_id:
                    # Handle adding existing media item to list
                    success = lists_handler.add_to_list_context(context)
                elif dbtype and dbid:
                    # Handle adding library item to list
                    success = lists_handler.add_library_item_to_list_context(context)
                else:
                    # Handle adding external item to list
                    success = lists_handler.add_external_item_to_list(context)

                # For context actions, end cleanly without navigation
                if is_context_action:
                    # End directory to prevent Kodi from trying to display plugin interface
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return True  # Prevent fallthrough to main menu
                else:
                    return success
            # Added new handler for remove_from_list
            elif action == 'remove_from_list':
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                return self._handle_remove_from_list(context, lists_handler)
            elif action == 'remove_library_item_from_list':
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')
                dbtype = context.get_param('dbtype')
                dbid = context.get_param('dbid')
                return lists_handler.remove_library_item_from_list(context, list_id, dbtype, dbid)
            elif action in ['show_list', 'view_list']:
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context  # Set context before using factory
                lists_handler = factory.get_lists_handler()
                list_id = context.get_param('list_id')

                # Special handling for Kodi Favorites - trigger scan-if-needed before showing
                if self._is_kodi_favorites_list(context, list_id):
                    self._handle_kodi_favorites_scan_if_needed(context)

                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                response = lists_handler.view_list(context, list_id)

                # Router delegates to response handler - it will process the navigation intent
                return response_handler.handle_directory_response(response, context)

            elif action == 'show_folder':
                folder_id = params.get('folder_id')

                if folder_id:
                    # Delegate to lists_handler for proper cached data handling
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.show_folder(context, str(folder_id))
                    return response_handler.handle_directory_response(response, context)
                else:
                    self.logger.error("Missing folder_id parameter")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'delete_folder':
                folder_id = params.get('folder_id')
                if folder_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.delete_folder(context, str(folder_id))
                    # Auto-refresh after successful folder deletion
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing folder_id parameter for delete_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'rename_folder':
                folder_id = params.get('folder_id')
                if folder_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.rename_folder(context, str(folder_id))
                    # Auto-refresh after successful folder rename
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing folder_id parameter for rename_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'move_folder':
                folder_id = params.get('folder_id')
                if folder_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    lists_handler = factory.get_lists_handler()
                    response_handler = get_response_handler()
                    response = lists_handler.move_folder(context, str(folder_id))
                    # Auto-refresh after successful folder move
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing folder_id parameter for move_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'refresh_import':
                folder_id = params.get('folder_id')
                if folder_id:
                    # Handle refresh import action
                    self._handle_refresh_import(context, str(folder_id))
                    return True
                else:
                    self.logger.error("Missing folder_id parameter for refresh_import")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'delete_files_import':
                import_source_id = params.get('import_source_id')
                if import_source_id:
                    self._handle_delete_files_import(context, int(import_source_id))
                    return True
                else:
                    self.logger.error("Missing import_source_id parameter for delete_files_import")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'export_folder_and_lists':
                folder_id = params.get('folder_id')
                if folder_id:
                    self._handle_export_folder_and_lists(context, str(folder_id))
                    return True
                else:
                    self.logger.error("Missing folder_id parameter for export_folder_and_lists")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'refresh_files_import':
                folder_id = params.get('folder_id')
                if folder_id:
                    # Reuse existing _handle_refresh_import
                    self._handle_refresh_import(context, str(folder_id))
                    return True
                else:
                    self.logger.error("Missing folder_id parameter for refresh_files_import")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'show_context_more_menu':
                self._handle_show_context_more_menu(context)
                return True

            elif action == 'move_list_to_folder':
                list_id = params.get('list_id')
                if list_id:
                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler
                    factory = get_handler_factory()
                    factory.context = context
                    tools_handler = factory.get_tools_handler()
                    response_handler = get_response_handler()
                    response = tools_handler.move_list_to_folder(context, str(list_id))
                    # Auto-refresh after successful list move
                    if response.success:
                        response.refresh_needed = True
                    success = response_handler.handle_dialog_response(response, context)
                    return bool(success) if success is not None else True
                else:
                    self.logger.error("Missing list_id parameter for move_list_to_folder")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == 'show_search_history':
                # Handle search history folder access - look up folder ID only when needed
                query_manager = context.query_manager
                if query_manager:
                    search_folder_id = query_manager.get_or_create_search_history_folder()
                    if search_folder_id:
                        # Use the handler factory
                        from lib.ui.handler_factory import get_handler_factory
                        factory = get_handler_factory()
                        factory.context = context
                        lists_handler = factory.get_lists_handler()
                        from lib.ui.response_handler import get_response_handler
                        response_handler = get_response_handler()
                        response = lists_handler.show_folder(context, str(search_folder_id))
                        return response_handler.handle_directory_response(response, context)
                    else:
                        self.logger.error("Could not access search history folder")
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                        return False
                else:
                    self.logger.error("Query manager not available for search history")
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False

            elif action == "restore_backup":
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler.handle_restore_backup(params, context)

                # Handle the DialogResponse
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                success = response_handler.handle_dialog_response(result, context)
                return bool(success) if success is not None else True

            elif action == "activate_ai_search":
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                tools_handler = factory.get_tools_handler()
                result = tools_handler.handle_activate_ai_search(params, context)

                # Handle the DialogResponse
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                success = response_handler.handle_dialog_response(result, context)
                return bool(success) if success is not None else True

            elif action == "authorize_ai_search":
                from lib.ui.ai_search_handler import AISearchHandler
                ai_handler = AISearchHandler()
                result = ai_handler.authorize_ai_search(context)
                return result if isinstance(result, bool) else True
            elif action == "ai_search_replace_sync":
                try:
                    from lib.ui.ai_search_handler import get_ai_search_handler
                    ai_handler = get_ai_search_handler()
                    ai_handler.trigger_replace_sync(context)
                    return True
                except Exception as e:
                    self.logger.error("Error in ai_search_replace_sync handler: %s", e)
                    return False

            elif action == "ai_search_regular_sync":
                try:
                    from lib.ui.ai_search_handler import get_ai_search_handler
                    ai_handler = get_ai_search_handler()
                    ai_handler.trigger_regular_sync(context)
                    return True
                except Exception as e:
                    self.logger.error("Error in ai_search_regular_sync handler: %s", e)
                    return False
            elif action == 'test_ai_search_connection':
                try:
                    from lib.auth.otp_auth import test_api_connection
                    from lib.config.settings import SettingsManager
                    settings = SettingsManager()
                    server_url = settings.get_remote_server_url()
                    if not server_url:
                        self.logger.error("No server URL configured for AI search connection test")
                        return False
                    result = test_api_connection(server_url)
                    return result.get('success', False)
                except Exception as e:
                    self.logger.error("Error testing AI search connection: %s", e)
                    return False

            elif action == 'find_similar_movies':
                from lib.ui.ai_search_handler import AISearchHandler
                ai_search_handler = AISearchHandler()
                return ai_search_handler.find_similar_movies(context)
            elif action.startswith('quick_add'):
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.nav import execute_intent, refresh
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()

                is_context = context.is_from_outside_plugin()

                if action == 'quick_add' and context.get_param('media_item_id'):
                    result = lists_handler.quick_add_to_default_list(context)
                elif action == 'quick_add_context':
                    result = lists_handler.quick_add_library_item_to_default_list(context)
                elif action == 'quick_add_external':
                    result = lists_handler.quick_add_external_item_to_default_list(context)
                else:
                    result = False

                # Context menu actions vs plugin actions
                if is_context:
                    # Pure context actions - no endOfDirectory, use NavigationIntent
                    if result and hasattr(result, 'intent') and result.intent:
                        execute_intent(result.intent)
                    elif result:
                        refresh()  # Fallback to refresh if no intent
                    return True
                else:
                    # For plugin actions, end directory normally
                    from lib.ui.nav import finish_directory
                    finish_directory(context.addon_handle, succeeded=bool(result))
                    return bool(result)
            elif action.startswith('add_to_list') or action.startswith('add_library_item_to_list'):
                from lib.ui.handler_factory import get_handler_factory
                from lib.ui.response_handler import get_response_handler
                from lib.ui.nav import execute_intent, refresh
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()
                response_handler = get_response_handler()

                is_context = context.is_from_outside_plugin()
                result = None

                # Dispatch based on specific action
                if action == 'add_to_list':
                    media_item_id = context.get_param('media_item_id')
                    if media_item_id:
                        result = lists_handler.add_to_list_menu(context, media_item_id)
                    else:
                        # Handle library item parameters
                        result = lists_handler.add_library_item_to_list_context(context)
                elif action == 'add_library_item_to_list':
                    result = lists_handler.add_library_item_to_list_context(context)
                elif action == 'add_external_item':
                    result = lists_handler.add_external_item_to_list(context)

                # Handle context actions differently
                if is_context:
                    # Pure context actions - no endOfDirectory, use NavigationIntent
                    intent = getattr(result, 'intent', None) if result else None
                    if intent:
                        execute_intent(intent)
                    elif result:
                        refresh()  # Fallback to refresh if no intent
                    return bool(result)
                else:
                    # For plugin directory actions, handle the response properly
                    if result and hasattr(result, 'success'):
                        # It's a DialogResponse - handle with response handler
                        from lib.ui.response_types import DialogResponse
                        if isinstance(result, DialogResponse):
                            response_handler.handle_dialog_response(result, context)
                            return result.success
                        else:
                            # It's some other object with success attribute
                            return bool(getattr(result, 'success', False))
                    else:
                        # It's a boolean or similar result
                        xbmcplugin.endOfDirectory(context.addon_handle, succeeded=bool(result))
                        return bool(result)
            else:
                # Check for registered handlers
                handler = self._handlers.get(action)
                if not handler:
                    self.logger.debug("No handler found for action '%s', will show main menu (redirecting to Lists)", action)

                    from lib.ui.handler_factory import get_handler_factory
                    from lib.ui.response_handler import get_response_handler

                    factory = get_handler_factory()
                    factory.context = context
                    response_handler = get_response_handler()

                    lists_handler = factory.get_lists_handler()

                    response = lists_handler.show_lists_menu(context)
                    success = response_handler.handle_directory_response(response, context)

                    return success
                # Use the registered handler
                handler(context)
                return True

        except Exception as e:
            self.logger.error("Error in handler for action '%s': %s", action, e)
            import traceback
            self.logger.error("Handler error traceback: %s", traceback.format_exc())

            # Show error to user
            try:
                self.dialog_service.notification(
                    f"Error in {action}",
                    icon="error",
                    title=context.addon.getLocalizedString(30136)
                )
            except Exception:
                pass

            return False

    def _handle_list_tools(self, context: PluginContext, params: Dict[str, Any]) -> bool:
        """Handle list tools action with response processing"""
        try:
            from lib.ui.handler_factory import get_handler_factory
            from lib.ui.response_handler import get_response_handler

            factory = get_handler_factory()
            factory.context = context # Set context before using factory
            tools_handler = factory.get_tools_handler()
            response_handler = get_response_handler()

            list_type = params.get('list_type', 'unknown')
            list_id = params.get('list_id')

            result = tools_handler.show_list_tools(context, list_type, list_id)

            # Use response handler to process the result
            success = response_handler.handle_dialog_response(result, context)
            return bool(success) if success is not None else True

        except Exception as e:
            self.logger.error("Error in list tools handler: %s", e)
            return False

    def _handle_noop(self, context: PluginContext) -> bool:
        """Handle no-op action"""
        try:
            # Just end the directory with no items
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
            return True
        except Exception as e:
            self.logger.error("Error in noop handler: %s", e)
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

    def _handle_toggle_tools_menu_item(self, context: PluginContext) -> bool:
        """Toggle the Tools & Options menu item visibility setting and refresh view"""
        try:
            import xbmc
            from lib.config.config_manager import get_config
            
            # Get current setting value
            config = get_config()
            current_value = config.get_bool('show_tools_menu_item', True)
            
            # Toggle the setting
            new_value = not current_value
            context.addon.setSettingBool('show_tools_menu_item', new_value)
            
            # CRITICAL: Invalidate ConfigManager cache so new value is read immediately
            config.invalidate()
            self.logger.debug("ConfigManager cache invalidated after toggling Tools & Options visibility")
            
            self.logger.info("Toggled Tools & Options visibility: %s -> %s", current_value, new_value)
            
            # Refresh the current container to show the change immediately
            xbmc.executebuiltin('Container.Refresh')
            
            # End directory for context menu invocation
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
            return True
            
        except Exception as e:
            self.logger.error("Error toggling tools menu item visibility: %s", e)
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

    def _handle_set_startup_folder(self, context: PluginContext) -> bool:
        """Set a folder as the startup folder"""
        try:
            import xbmc
            from lib.config.config_manager import get_config
            
            folder_id = context.get_param('folder_id')
            
            if not folder_id:
                self.logger.error("No folder_id provided for set_startup_folder")
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False
            
            # Set the startup folder setting
            context.addon.setSettingString('startup_folder_id', str(folder_id))
            
            # Invalidate ConfigManager cache so new value is immediately visible
            config = get_config()
            config.invalidate('startup_folder_id')
            
            self.logger.info("Set startup folder to: %s", folder_id)
            
            # Show notification
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Startup folder set successfully",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            
            # Refresh the current container
            xbmc.executebuiltin('Container.Refresh')
            
            # End directory for context menu invocation
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
            return True
            
        except Exception as e:
            self.logger.error("Error setting startup folder: %s", e)
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

    def _handle_clear_startup_folder(self, context: PluginContext) -> bool:
        """Clear the startup folder setting"""
        try:
            import xbmc
            from lib.config.config_manager import get_config
            
            # Clear the startup folder setting (set to empty string)
            context.addon.setSettingString('startup_folder_id', '')
            
            # Invalidate ConfigManager cache so cleared value is immediately visible
            config = get_config()
            config.invalidate('startup_folder_id')
            
            self.logger.info("Cleared startup folder setting")
            
            # Show notification
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Startup folder cleared",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            
            # Refresh the current container
            xbmc.executebuiltin('Container.Refresh')
            
            # End directory for context menu invocation
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
            return True
            
        except Exception as e:
            self.logger.error("Error clearing startup folder: %s", e)
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

    def _handle_remove_from_list(self, context: PluginContext, lists_handler) -> bool:
        """Handles the remove_from_list action, including fallback logic."""
        list_id = context.get_param('list_id')
        item_id = context.get_param('item_id')

        if item_id:
            # If item_id is directly provided, use it
            response = lists_handler.remove_from_list(context, list_id, item_id)
            
            # Process DialogResponse for context menu actions
            if hasattr(response, 'success'):
                from lib.ui.response_handler import get_response_handler
                from lib.ui.nav import get_navigator
                
                response_handler = get_response_handler()
                response_handler.handle_dialog_response(response, context)
                
                # For context menu actions (handle=-1) that need refresh, use updateListing mechanism
                if (context.addon_handle == -1 and response.success and 
                    getattr(response, 'refresh_needed', None)):
                    navigator = get_navigator()
                    navigator.finish_directory(context.addon_handle, succeeded=True, update=True)
                
                return response.success
            else:
                return bool(response)
        else:
            # Fallback: try to find the item_id using library identifiers
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')
            if dbtype and dbid:
                return lists_handler.remove_library_item_from_list(context, list_id, dbtype, dbid)
            else:
                self.logger.error("Cannot remove from list: missing item_id, dbtype, or dbid.")
                try:
                    self.dialog_service.notification(
                        "Could not remove item from list.",
                        icon="error",
                        title=context.addon.getLocalizedString(30136)
                    )
                except Exception:
                    pass
                return False

    def _handle_authorize_ai_search(self, context: PluginContext) -> bool:
        """Handle AI search authorization action from settings"""
        try:
            self.logger.info("Authorization button clicked from settings")

            # Get settings manager for server URL
            from lib.config.settings import SettingsManager
            settings = SettingsManager()
            server_url = settings.get_remote_server_url()

            self.logger.info("Retrieved server URL: '%s' (type: %s)", server_url, type(server_url))

            # Check server URL first
            if not server_url or len(server_url.strip()) == 0:
                self.logger.warning("Server URL validation failed - URL: '%s'", server_url)
                self.dialog_service.ok(
                    "Configuration Required",
                    "Please configure the AI Search Server URL before authorizing.\n\nMake sure it's not empty and contains a valid URL."
                )
                return False

            # Pop up keyboard for OTP entry
            otp_code = self.dialog_service.input(
                "Enter OTP Code",
                default="Enter the 8-digit OTP code from your server:"
            )

            # Check if user cancelled or entered invalid code
            if not otp_code or len(otp_code.strip()) != 8:
                if otp_code:  # User entered something but it's invalid
                    self.dialog_service.ok(
                        "Invalid OTP Code",
                        "Please enter a valid 8-digit OTP code."
                    )
                return False

            self.logger.info("User entered OTP code: %s", otp_code)
            self.logger.info("Starting OTP authorization with code: %s", otp_code)

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search Authorization", "Exchanging OTP code for API key...")

            try:
                # Exchange OTP for API key
                from lib.auth.otp_auth import exchange_otp_for_api_key
                result = exchange_otp_for_api_key(otp_code, server_url)

                progress.close()

                if result['success']:
                    # Success - activate AI Search
                    settings.set_ai_search_activated(True)
                    self.logger.info("✅ AI Search activated with server URL: %s", server_url)

                    # Show success dialog
                    self.dialog_service.ok(
                        "Authorization Complete",
                        f"AI Search activated successfully!\n\nUser: {result.get('user_email', 'Unknown')}"
                    )

                    self.logger.info("OTP authorization completed successfully from settings")
                    return True
                else:
                    # Failed - show error
                    self.dialog_service.ok(
                        "Authorization Failed",
                        f"Failed to activate AI Search:\n\n{result['error']}"
                    )

                    self.logger.warning("OTP authorization failed from settings: %s", result['error'])
                    return False

            finally:
                if progress:
                    progress.close()

        except Exception as e:
            self.logger.error("Error in authorize_ai_search handler: %s", e)
            self.dialog_service.ok(
                "Authorization Error",
                f"An unexpected error occurred:\n\n{str(e)[:100]}..."
            )
            return False

    def _is_kodi_favorites_list(self, context, list_id):
        """Check if the list being viewed is the Kodi Favorites list"""
        try:
            if not list_id:
                return False

            query_manager = context.query_manager
            if not query_manager:
                return False

            list_info = query_manager.get_list_by_id(list_id)
            if list_info and list_info.get('name') == 'Kodi Favorites':
                self.logger.debug("ROUTER: Detected Kodi Favorites list (id: %s)", list_id)
                return True

            return False
        except Exception as e:
            self.logger.error("ROUTER: Error checking if list is Kodi Favorites: %s", e)
            return False

    def _handle_kodi_favorites_scan_if_needed(self, context):
        """Trigger scan-if-needed for Kodi Favorites before showing the list"""
        try:
            self.logger.info("ROUTER: Triggering scan-if-needed for Kodi Favorites")

            # Initialize favorites manager
            favorites_manager = context.favorites_manager
            if not favorites_manager:
                self.logger.warning("ROUTER: Favorites manager not available")
                return

            # Check if scan is needed and perform if so
            result = favorites_manager.scan_favorites(force_refresh=False)
            if result.get('success'):
                scan_type = result.get('scan_type', 'unknown')
                items_found = result.get('items_found', 0)
                items_mapped = result.get('items_mapped', 0)
                self.logger.info("ROUTER: Kodi Favorites scan completed - type: %s, found: %s, mapped: %s", scan_type, items_found, items_mapped)
            else:
                self.logger.warning("ROUTER: Kodi Favorites scan failed: %s", result.get('message', 'Unknown error'))

        except Exception as e:
            self.logger.error("ROUTER: Error during Kodi Favorites scan: %s", e)

    def _handle_bookmark_save(self, context):
        """Handle saving bookmark from context menu"""
        try:
            # Get parameters from context
            url = context.get_param('url')
            name = context.get_param('name', 'Unnamed Bookmark')
            bookmark_type = context.get_param('type', 'plugin')
            metadata_json = context.get_param('metadata')
            art_json = context.get_param('art')
            
            if not url:
                self.logger.error("No URL provided for bookmark save")
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Unable to save bookmark - no URL provided",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False
            
            # Parse metadata and art from JSON
            metadata = {}
            art_data = {}
            
            import json
            
            if metadata_json:
                try:
                    metadata = json.loads(metadata_json)
                except (json.JSONDecodeError, Exception) as e:
                    self.logger.warning("Failed to parse metadata JSON: %s", e)
                    
            if art_json:
                try:
                    art_data = json.loads(art_json)
                except (json.JSONDecodeError, Exception) as e:
                    self.logger.warning("Failed to parse art JSON: %s", e)
            
            
        except Exception as e:
            self.logger.error("Error handling bookmark save with category: %s", e)
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to save bookmark",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False


    def _determine_bookmark_type(self, url):
        """Determine bookmark type from URL"""
        if url.startswith('plugin://'):
            return 'plugin'
        elif url.startswith(('http://', 'https://', 'ftp://', 'ftps://')):
            return 'network'
        elif url.startswith(('smb://', 'nfs://', 'afp://', 'sftp://')):
            return 'network'
        elif url.startswith('videodb://') or url.startswith('musicdb://'):
            return 'library'
        elif url.startswith('special://'):
            return 'special'
        else:
            return 'file'
            
    def _handle_navigate_bookmark(self, context):
        """Handle bookmark navigation - navigate out of plugin to stored URL"""
        try:
            item_id = context.get_param('item_id')
            if not item_id:
                self.logger.error("No item_id provided for bookmark navigation")
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False
            
            # Get bookmark URL from database
            query_manager = context.query_manager
            with query_manager.connection_manager.get_connection() as conn:
                result = conn.execute("""
                    SELECT play, file_path, title
                    FROM media_items 
                    WHERE id = ? AND source = 'bookmark'
                """, [int(item_id)]).fetchone()
                
                if not result:
                    self.logger.error("Bookmark not found with id: %s", item_id)
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Bookmark not found",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                
                bookmark_url = result['play'] or result['file_path']
                bookmark_title = result['title']
                
                if not bookmark_url or bookmark_url.strip() == "":
                    self.logger.error("No URL found for bookmark: %s", bookmark_title)
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"No URL found for bookmark '{bookmark_title}'",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                    
                # Additional validation for bookmark URL
                if len(bookmark_url) > 2000:
                    self.logger.warning("Very long bookmark URL (%d chars) for: %s", len(bookmark_url), bookmark_title)
                    
                # Enhanced scheme validation with more complete coverage
                known_schemes = ['videodb://', 'musicdb://', 'smb://', 'nfs://', 'ftp://', 'sftp://', 'davs://', 'dav://', 
                               'hdhomerun://', 'plugin://', 'special://', 'http://', 'https://', 'stack://', 'zip://', 'rar://', 'multipath://']
                is_windows_path = len(bookmark_url) >= 3 and bookmark_url[1:3] == ':\\'
                is_unix_path = bookmark_url.startswith('/')
                
                if not (any(bookmark_url.startswith(scheme) for scheme in known_schemes) or is_windows_path or is_unix_path):
                    self.logger.warning("Unknown URL scheme for bookmark: %s", bookmark_url[:100])
                
                # Navigate to the bookmark URL using appropriate method based on URL type
                self.logger.info("Navigating to bookmark URL: %s", bookmark_url)
                import xbmc
                xbmc.executebuiltin('Dialog.Close(busydialog)')
                
                # Use ActivateWindow for ALL bookmark navigation to maintain proper back button behavior
                if bookmark_url.startswith(('videodb://', 'musicdb://')):
                    # Use ActivateWindow for database URLs to maintain navigation history
                    xbmc.executebuiltin(f"ActivateWindow(Videos,{bookmark_url},return)")
                    self.logger.info("Used ActivateWindow for database URL")
                elif bookmark_url.startswith(('smb://', 'nfs://', 'ftp://', 'sftp://', 'davs://', 'dav://', 'hdhomerun://', 'http://', 'https://')):
                    # Use ActivateWindow for network protocols
                    xbmc.executebuiltin(f"ActivateWindow(Videos,{bookmark_url},return)")
                    self.logger.info("Used ActivateWindow for network protocol")
                elif bookmark_url.startswith('/') or (len(bookmark_url) >= 3 and bookmark_url[1:3] == ':\\'):
                    # Use ActivateWindow for local file system paths (Unix-style or Windows drive letters)
                    xbmc.executebuiltin(f"ActivateWindow(Videos,{bookmark_url},return)")
                    self.logger.info("Used ActivateWindow for file system path")
                elif bookmark_url.startswith('plugin://'):
                    # Use ActivateWindow for plugin URLs
                    xbmc.executebuiltin(f"ActivateWindow(Videos,{bookmark_url},return)")
                    self.logger.info("Used ActivateWindow for plugin URL")
                elif bookmark_url.startswith('special://'):
                    # Use ActivateWindow for special protocol URLs
                    xbmc.executebuiltin(f"ActivateWindow(Videos,{bookmark_url},return)")
                    self.logger.info("Used ActivateWindow for special protocol URL")
                else:
                    # Generic fallback - use ActivateWindow to maintain navigation history
                    xbmc.executebuiltin(f"ActivateWindow(Videos,{bookmark_url},return)")
                    self.logger.info("Used ActivateWindow as fallback")
                
                # End the directory since we're navigating away
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True
                
        except Exception as e:
            self.logger.error("Error navigating to bookmark: %s", e)
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to navigate to bookmark",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False
    
    def _handle_rename_bookmark(self, context):
        """Handle bookmark renaming"""
        try:
            import xbmcgui
            bookmark_id = context.get_param('bookmark_id')
            if not bookmark_id:
                self.logger.error("No bookmark_id provided for rename")
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "No bookmark ID provided",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False
            
            # Get current bookmark name from database
            query_manager = context.query_manager
            with query_manager.connection_manager.get_connection() as conn:
                result = conn.execute("""
                    SELECT title, id FROM media_items 
                    WHERE id = ? AND source = 'bookmark'
                """, [int(bookmark_id)]).fetchone()
                
                if not result:
                    self.logger.error("Bookmark not found with id: %s", bookmark_id)
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Bookmark not found",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                
                current_name = result['title']
                
                # Show rename dialog
                dialog = xbmcgui.Dialog()
                new_name = dialog.input("Rename Bookmark", current_name)
                
                if not new_name or new_name.strip() == "":
                    # User cancelled or entered empty name
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                
                # Update bookmark name in database
                conn.execute("""
                    UPDATE media_items 
                    SET title = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND source = 'bookmark'
                """, [new_name.strip(), int(bookmark_id)])
                
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Renamed bookmark to '{new_name.strip()}'",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True
                
        except Exception as e:
            self.logger.error("Error renaming bookmark: %s", e)
            import xbmcgui
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to rename bookmark",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False
    
    def _handle_remove_bookmark(self, context):
        """Handle bookmark removal"""
        try:
            import xbmcgui
            bookmark_id = context.get_param('bookmark_id')
            if not bookmark_id:
                self.logger.error("No bookmark_id provided for removal")
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "No bookmark ID provided",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False
            
            # Get bookmark info for confirmation
            query_manager = context.query_manager
            with query_manager.connection_manager.get_connection() as conn:
                result = conn.execute("""
                    SELECT title, id FROM media_items 
                    WHERE id = ? AND source = 'bookmark'
                """, [int(bookmark_id)]).fetchone()
                
                if not result:
                    self.logger.error("Bookmark not found with id: %s", bookmark_id)
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Bookmark not found",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                
                bookmark_name = result['title']
                
                # Show confirmation dialog
                dialog = xbmcgui.Dialog()
                confirmed = dialog.yesno(
                    "Remove Bookmark",
                    f"Remove bookmark '{bookmark_name}'?",
                    "",
                    "This action cannot be undone."
                )
                
                if not confirmed:
                    # User cancelled
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                
                # Remove bookmark from database
                # First remove from any lists
                conn.execute("""
                    DELETE FROM list_items 
                    WHERE media_item_id = ?
                """, [int(bookmark_id)])
                
                # Then remove the bookmark itself
                conn.execute("""
                    DELETE FROM media_items 
                    WHERE id = ? AND source = 'bookmark'
                """, [int(bookmark_id)])
                
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Removed bookmark '{bookmark_name}'",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                return True
                
        except Exception as e:
            self.logger.error("Error removing bookmark: %s", e)
            import xbmcgui
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to remove bookmark",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False
    
    def _handle_show_folder_cached(self, context, folder_id: str) -> bool:
        """Handle show_folder with cache-first approach and background refresh"""
        try:
            start_time = time.time()
            
            # Get folder cache instance
            from lib.ui.folder_cache import get_folder_cache
            folder_cache = get_folder_cache()
            
            # Check cache first
            cached_payload = folder_cache.get(folder_id, allow_stale=True)
            
            if cached_payload:
                # We have cached data - serve it immediately
                is_fresh = folder_cache.is_fresh(folder_id)
                
                self.logger.debug("CACHE HIT for folder %s (%s) - serving cached payload", 
                                folder_id, "fresh" if is_fresh else "stale")
                
                # Convert cached payload back to DirectoryResponse and use ResponseHandler
                from lib.ui.response_types import DirectoryResponse
                cached_response = DirectoryResponse(
                    items=cached_payload.get('items', []),
                    success=True,
                    content_type=cached_payload.get('content_type', 'files'),
                    update_listing=cached_payload.get('update_listing', False),
                    intent=None
                )
                
                # Use ResponseHandler to maintain consistent UI behavior
                from lib.ui.response_handler import get_response_handler
                response_handler = get_response_handler()
                success = response_handler.handle_directory_response(cached_response, context)
                
                # If cache is stale, trigger background refresh
                if not is_fresh and folder_cache.is_stale_but_usable(folder_id):
                    self.logger.debug("Triggering background refresh for stale folder %s", folder_id)
                    self._trigger_background_folder_refresh(folder_cache, folder_id)
                
                cache_serve_time = (time.time() - start_time) * 1000
                self.logger.debug("CACHE SERVE: folder %s served in %.2f ms", folder_id, cache_serve_time)
                
                return success
            else:
                # Cache miss - build folder synchronously
                self.logger.debug("CACHE MISS for folder %s - building fresh", folder_id)
                return self._build_and_cache_folder(folder_cache, context, folder_id)
                
        except Exception as e:
            self.logger.error("Error in cached folder handling for %s: %s", folder_id, e)
            # Fall back to normal folder handling
            return self._fallback_to_normal_folder_handling(context, folder_id)
    
    def _build_and_cache_folder(self, folder_cache, context, folder_id: str) -> bool:
        """Build folder payload and cache it"""
        try:
            build_start = time.time()
            
            # Use stampede protection when building
            with folder_cache.with_build_lock(folder_id):
                # Check cache again in case another thread built it while we waited
                cached_payload = folder_cache.get(folder_id)
                if cached_payload:
                    self.logger.debug("Found fresh cache after lock for folder %s", folder_id)
                    # Convert to DirectoryResponse and use ResponseHandler
                    from lib.ui.response_types import DirectoryResponse
                    cached_response = DirectoryResponse(
                        items=cached_payload.get('items', []),
                        success=True,
                        content_type=cached_payload.get('content_type', 'files'),
                        update_listing=cached_payload.get('update_listing', False),
                        intent=None
                    )
                    from lib.ui.response_handler import get_response_handler
                    response_handler = get_response_handler()
                    return response_handler.handle_directory_response(cached_response, context)
                
                # Build folder using original handler
                from lib.ui.handler_factory import get_handler_factory
                factory = get_handler_factory()
                factory.context = context
                lists_handler = factory.get_lists_handler()
                
                # Get the directory response
                response = lists_handler.show_folder(context, folder_id)
                
                if response.success:
                    build_time_ms = (time.time() - build_start) * 1000
                    
                    # Note: Caching now handled in lists_handler.py with raw database data
                    # Don't cache UI items here as it interferes with proper data caching
                    
                    self.logger.debug("CACHE SET: folder %s built and cached in %.2f ms", 
                                    folder_id, build_time_ms)
                    
                    # Use response handler to serve the response
                    from lib.ui.response_handler import get_response_handler
                    response_handler = get_response_handler()
                    return response_handler.handle_directory_response(response, context)
                else:
                    self.logger.error("Failed to build folder %s", folder_id)
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                    return False
                    
        except Exception as e:
            self.logger.error("Error building and caching folder %s: %s", folder_id, e)
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False
    
    def _trigger_background_folder_refresh(self, folder_cache, folder_id: str):
        """Trigger background refresh for stale folder (non-blocking)"""
        def background_refresh():
            try:
                self.logger.debug("Background refresh started for folder %s", folder_id)
                
                # Build fresh payload (no UI operations in background thread)
                with folder_cache.with_build_lock(folder_id):
                    refresh_start = time.time()
                    
                    # Create minimal context for data operations only
                    from lib.data.query_manager import get_query_manager
                    query_manager = get_query_manager()
                    
                    if not query_manager.initialize():
                        self.logger.error("Failed to initialize query manager for background refresh")
                        return
                    
                    # Get folder navigation data directly
                    navigation_data = query_manager.get_folder_navigation_batch(folder_id)
                    
                    if navigation_data and navigation_data.get('folder_info'):
                        folder_info = navigation_data['folder_info']
                        subfolders = navigation_data['subfolders']
                        lists_in_folder = navigation_data['lists']
                        
                        # Build menu items (data only, no Kodi UI calls)
                        menu_items = []
                        
                        # Get toggle entry once for both folders and lists
                        from lib.config.config_manager import get_config
                        config = get_config()
                        is_visible = config.get_bool('show_tools_menu_item', True)
                        toggle_label = "Hide Tools & Options Menu Item" if is_visible else "Show Tools & Options Menu Item"
                        
                        # Add subfolders
                        for subfolder in subfolders:
                            subfolder_id = subfolder.get('id')
                            subfolder_name = subfolder.get('name', 'Unnamed Folder')
                            
                            # Build URL and context menu data
                            url = f"plugin://plugin.video.librarygenie/?action=show_folder&folder_id={subfolder_id}"
                            
                            context_menu = [
                                (f"Rename '{subfolder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_folder&folder_id={subfolder_id})"),
                                (f"Move '{subfolder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=move_folder&folder_id={subfolder_id})"),
                                (f"Delete '{subfolder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_folder&folder_id={subfolder_id})"),
                                (toggle_label, f"RunPlugin(plugin://plugin.video.librarygenie/?action=toggle_tools_menu_item)")
                            ]
                            
                            menu_items.append({
                                'label': f"📁 {subfolder_name}",
                                'url': url,
                                'is_folder': True,
                                'description': "Subfolder",
                                'context_menu': context_menu,
                                'icon': "DefaultFolder.png"
                            })
                        
                        # Add lists
                        for list_item in lists_in_folder:
                            list_id = list_item.get('id')
                            name = list_item.get('name', 'Unnamed List')
                            description = list_item.get('description', '')
                            
                            url = f"plugin://plugin.video.librarygenie/?action=show_list&list_id={list_id}"
                            
                            # Get toggle entry (reuse config from subfolder loop above)
                            context_menu = [
                                (f"Rename '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})"),
                                (f"Move '{name}' to Folder", f"RunPlugin(plugin://plugin.video.librarygenie/?action=move_list_to_folder&list_id={list_id})"),
                                (f"Export '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=export_list&list_id={list_id})"),
                                (f"Delete '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_id})"),
                                (toggle_label, f"RunPlugin(plugin://plugin.video.librarygenie/?action=toggle_tools_menu_item)")
                            ]
                            
                            menu_items.append({
                                'label': name,
                                'url': url,
                                'is_folder': True,
                                'description': description,
                                'icon': "DefaultPlaylist.png",
                                'context_menu': context_menu
                            })
                        
                        refresh_time_ms = (time.time() - refresh_start) * 1000
                        
                        # Note: Background refresh not needed - caching handled in lists_handler.py with raw data
                        # Don't cache UI items here as it interferes with proper data caching
                        
                        self.logger.debug("Background refresh completed for folder %s in %.2f ms", 
                                        folder_id, refresh_time_ms)
                    else:
                        self.logger.warning("Background refresh failed for folder %s - no data", folder_id)
                        
            except Exception as e:
                self.logger.error("Error in background refresh for folder %s: %s", folder_id, e)
        
        # Start background thread
        refresh_thread = threading.Thread(target=background_refresh, daemon=True)
        refresh_thread.start()
    
    def _fallback_to_normal_folder_handling(self, context, folder_id: str) -> bool:
        """Fallback to normal folder handling when caching fails"""
        try:
            self.logger.debug("Falling back to normal folder handling for %s", folder_id)
            
            from lib.ui.handler_factory import get_handler_factory
            factory = get_handler_factory()
            factory.context = context
            lists_handler = factory.get_lists_handler()
            from lib.ui.response_handler import get_response_handler
            response_handler = get_response_handler()
            response = lists_handler.show_folder(context, folder_id)
            return response_handler.handle_directory_response(response, context)
            
        except Exception as e:
            self.logger.error("Error in fallback folder handling: %s", e)
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False