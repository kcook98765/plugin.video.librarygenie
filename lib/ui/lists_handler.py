#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Lists Handler
Handles lists display and navigation (refactored)
"""

import xbmcplugin
import xbmcgui

from typing import Dict, Any
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DirectoryResponse, DialogResponse
from lib.ui.localization import L
from lib.ui.breadcrumb_helper import get_breadcrumb_helper
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager
from lib.utils.kodi_version import get_kodi_major_version

# Import the specialized operation modules
from lib.ui.list_operations import ListOperations
from lib.ui.folder_operations import FolderOperations


class ListsHandler:
    """Handles lists operations (refactored to use specialized modules)"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_kodi_logger('lib.ui.lists_handler')
        self.query_manager = context.query_manager
        self.storage_manager = context.storage_manager

        self.breadcrumb_helper = get_breadcrumb_helper()

        # Import/export deferred for performance
        self.list_ops = ListOperations(context)
        self.folder_ops = FolderOperations(context)
        self._import_export = None  # Lazy loaded on first use


    @property
    def import_export(self):
        """Lazy load ImportExportHandler only when import/export operations are needed"""
        if self._import_export is None:
            self.logger.debug("LAZY LOAD: Loading ImportExportHandler on first use")
            from lib.ui.import_export_handler import ImportExportHandler
            self._import_export = ImportExportHandler(self.context)
        return self._import_export

    @property
    def listitem_renderer(self):
        """Lazy load ListItemRenderer only when needed for navigation rendering"""
        if not hasattr(self, '_listitem_renderer'):
            self.logger.debug("LAZY LOAD: Loading ListItemRenderer on first use")
            from lib.ui.listitem_renderer import get_listitem_renderer
            self._listitem_renderer = get_listitem_renderer(
                self.context.addon_handle,
                self.context.addon_id,
                self.context
            )
        return self._listitem_renderer

    def _create_simple_empty_state_item(self, context: PluginContext, title: str, description: str = "") -> None:
        """Create simple empty state item without loading full renderer - optimization for low-power devices"""
        try:
            # Create simple list item without heavy renderer dependencies
            list_item = xbmcgui.ListItem(label=title, offscreen=True)

            # Set basic properties without renderer
            if description:
                self._set_listitem_plot(list_item, description)

            list_item.setProperty('IsPlayable', 'false')
            list_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})

            # Add to directory
            xbmcplugin.addDirectoryItem(
                context.addon_handle,
                context.build_url('noop'),
                list_item,
                False
            )

        except Exception as e:
            self.logger.error("Failed to create simple empty state item: %s", e)

    def _set_listitem_plot(self, list_item: xbmcgui.ListItem, plot: str):
        """Set plot metadata in version-compatible way to avoid v21 setInfo() deprecation warnings"""
        kodi_major = get_kodi_major_version()
        if kodi_major >= 21:
            # v21+: Use InfoTagVideo ONLY - completely avoid setInfo()
            try:
                video_info_tag = list_item.getVideoInfoTag()
                video_info_tag.setPlot(plot)
            except Exception as e:
                self.logger.error("InfoTagVideo failed for plot: %s", e)
        else:
            # v19/v20: Use setInfo() as fallback
            list_item.setInfo('video', {'plot': plot})

    def _set_custom_art_for_item(self, list_item: xbmcgui.ListItem, item_data: Dict[str, Any]):
        """Apply custom art based on item type"""
        try:
            # Get the lazy-loaded renderer instance to use its art methods
            renderer = self.listitem_renderer

            # Determine if this is a list or folder based on the URL action
            url = item_data.get('url', '')

            if 'action=show_list' in url:
                # This is a user list - use list/playlist art with custom resources
                renderer._apply_art(list_item, 'list')
            elif 'action=show_folder' in url:
                # This is a folder - use folder art with custom resources
                renderer._apply_art(list_item, 'folder')
            else:
                # Default/other items - use original icon if specified
                if 'icon' in item_data:
                    list_item.setArt({'icon': item_data['icon'], 'thumb': item_data['icon']})
                else:
                    # Use folder art as default for other navigable items
                    renderer._apply_art(list_item, 'folder')

        except Exception as e:
            # Fallback to original behavior
            self.logger.error("Custom art failed: %s", e)
            if 'icon' in item_data:
                list_item.setArt({'icon': item_data['icon'], 'thumb': item_data['icon']})
            else:
                list_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})

    # =================================
    # LIST OPERATION METHODS (delegated to ListOperations)
    # =================================

    def create_list(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new list"""
        return self.list_ops.create_list(context)

    def delete_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle deleting a list"""
        return self.list_ops.delete_list(context, list_id)

    def rename_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle renaming a list"""
        return self.list_ops.rename_list(context, list_id)

    def remove_from_list(self, context: PluginContext, list_id: str, item_id: str) -> DialogResponse:
        """Handle removing an item from a list"""
        return self.list_ops.remove_from_list(context, list_id, item_id)

    def set_default_list(self, context: PluginContext) -> DialogResponse:
        """Handle setting the default list for quick-add functionality"""
        return self.list_ops.set_default_list(context)

    def add_to_list_menu(self, context: PluginContext, media_item_id: str) -> bool:
        """Handle adding media item to a list"""
        return self.list_ops.add_to_list_menu(context, media_item_id)

    def add_library_item_to_list_context(self, context: PluginContext) -> bool:
        """Handle adding library item to a list from context menu"""
        return self.list_ops.add_library_item_to_list_context(context)

    # =================================
    # FOLDER OPERATION METHODS (delegated to FolderOperations)
    # =================================

    def create_folder(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new folder"""
        return self.folder_ops.create_folder(context)

    def delete_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle deleting a folder"""
        return self.folder_ops.delete_folder(context, folder_id)

    def rename_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle renaming a folder"""
        return self.folder_ops.rename_folder(context, folder_id)

    def move_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle moving a list to a different folder"""
        return self.folder_ops.move_list(context, list_id)

    def move_folder(self, context: PluginContext, folder_id: str) -> DialogResponse:
        """Handle moving a folder to a different parent folder"""
        return self.folder_ops.move_folder(context, folder_id)

    # =================================
    # IMPORT/EXPORT METHODS (delegated to ImportExportHandler)
    # =================================

    def export_single_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Export a single list to a file"""
        return self.import_export.export_single_list(context, list_id)

    def export_folder_lists(self, context: PluginContext, folder_id: str, include_subfolders: bool = False) -> DialogResponse:
        """Export all lists in a folder"""
        return self.import_export.export_folder_lists(context, folder_id, include_subfolders)

    def import_lists(self, context: PluginContext) -> DialogResponse:
        """Import lists from a file"""
        return self.import_export.import_lists(context)

    def merge_lists(self, context: PluginContext, source_list_id: str, target_list_id: str) -> DialogResponse:
        """Merge items from source list into target list"""
        return self.import_export.merge_lists(context, source_list_id, target_list_id)

    def select_lists_for_merge(self, context: PluginContext) -> DialogResponse:
        """Show UI for selecting source and target lists for merging"""
        return self.import_export.select_lists_for_merge(context)

    # =================================
    # BACKWARD COMPATIBILITY ALIASES
    # =================================

    def export_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Export a single list (backward compatibility alias)"""
        return self.export_single_list(context, list_id)

    def _export_folder_lists(self, context: PluginContext, folder_id: str, include_subfolders: bool = False) -> DialogResponse:
        """Export folder lists (backward compatibility alias)"""
        return self.export_folder_lists(context, folder_id, include_subfolders)

    def _import_lists(self, context: PluginContext) -> DialogResponse:
        """Import lists (backward compatibility alias)"""
        return self.import_lists(context)

    # =================================
    # DISPLAY/UI METHODS (kept in main handler)
    # =================================

    def show_lists_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main lists menu with folders and lists"""
        try:
            context.logger.debug("Displaying lists menu")

            # Initialize query manager
            query_manager = get_query_manager()

            init_result = query_manager.initialize()

            if not init_result:
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get all user lists and folders
            all_lists = query_manager.get_all_lists_with_folders()
            context.logger.debug("Found %s total lists", len(all_lists))

            # Include all lists including "Kodi Favorites" in the main Lists menu
            user_lists = all_lists
            context.logger.debug("Found %s user lists (including Kodi Favorites)", len(user_lists))

            if not user_lists:
                # No lists exist - show empty state instead of dialog
                # This prevents confusing dialogs when navigating back from deletions
                menu_items = []

                # Add "Tools & Options" with breadcrumb context
                breadcrumb_text = self.breadcrumb_helper.get_breadcrumb_for_tools_label('lists', {}, query_manager)
                description_prefix = self.breadcrumb_helper.get_breadcrumb_for_tools_description('lists', {}, query_manager)

                menu_items.append({
                    'label': f"{L(36000)} {breadcrumb_text}",
                    'url': context.build_url('show_list_tools', list_type='lists_main'),
                    'is_folder': True,
                    'icon': "DefaultAddonProgram.png",
                    'description': f"{description_prefix}{L(36018)}"  # Breadcrumb + "Access lists tools and options"
                })

                # Add "Create First List" option
                menu_items.append({
                    'label': f"+ {L(37018)}",
                    'url': context.build_url('create_list_execute'),
                    'is_folder': True,
                    'icon': "DefaultAddSource.png",
                    'description': "Create your first list to get started"
                })

                # Build directory items
                for item in menu_items:
                    list_item = xbmcgui.ListItem(label=item['label'], offscreen=True)

                    if 'description' in item:
                        self._set_listitem_plot(list_item, item['description'])

                    if 'icon' in item:
                        list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

                    xbmcplugin.addDirectoryItem(
                        context.addon_handle,
                        item['url'],
                        list_item,
                        item['is_folder']
                    )

                # Determine if this is a refresh or initial load
                is_refresh = context.get_param('rt') is not None  # Refresh token indicates mutation/refresh

                return DirectoryResponse(
                    items=menu_items,
                    success=True,
                    content_type="files",
                    update_listing=is_refresh,  # REPLACE semantics for refresh, PUSH for initial
                    intent=None  # Pure rendering, no navigation intent
                )

            # Set directory title with breadcrumb context
            current_folder_id = context.get_param('folder_id')

            # Determine breadcrumb context based on current location
            if current_folder_id:
                breadcrumb_params = {'folder_id': current_folder_id}
                breadcrumb_action = 'show_folder'
                tools_url = context.build_url('show_list_tools', list_type='lists_main', folder_id=current_folder_id)
            else:
                breadcrumb_params = {}
                breadcrumb_action = 'lists'
                tools_url = context.build_url('show_list_tools', list_type='lists_main')

            directory_title = self.breadcrumb_helper.get_directory_title_breadcrumb(breadcrumb_action, breadcrumb_params, query_manager)
            if directory_title:
                try:
                    # Set the directory title in Kodi
                    import xbmc
                    xbmc.executebuiltin(f'SetProperty(FolderName,{directory_title})')
                    context.logger.debug("Set directory title: '%s'", directory_title)
                except Exception as e:
                    context.logger.debug("Could not set directory title: %s", e)

            # Build menu items for lists and folders
            menu_items = []

            # Add "Tools & Options" with unified breadcrumb approach
            breadcrumb_text, description_prefix = self.breadcrumb_helper.get_tools_breadcrumb_formatted(breadcrumb_action, breadcrumb_params, query_manager)

            menu_items.append({
                'label': f"Tools & Options {breadcrumb_text}",
                'url': tools_url,
                'is_folder': True,
                'icon': "DefaultAddonProgram.png",
                'description': f"{description_prefix}Search, Favorites, Import/Export & Settings"
            })

            # Search and other tools are now accessible via Tools & Options menu

            # Check if favorites integration is enabled and ensure "Kodi Favorites" appears FIRST
            from lib.config.config_manager import get_config
            config = get_config()
            favorites_enabled = config.get_bool('favorites_integration_enabled', False)
            kodi_favorites_item = None

            # Find existing Kodi Favorites or create if needed
            for item in user_lists:
                if item.get('name') == 'Kodi Favorites':
                    kodi_favorites_item = item
                    break

            if favorites_enabled and not kodi_favorites_item:
                # Create "Kodi Favorites" list if it doesn't exist but setting is enabled
                context.logger.info("LISTS HANDLER: Favorites integration enabled but 'Kodi Favorites' list not found, creating it")
                try:
                    from lib.config.favorites_helper import on_favorites_integration_enabled
                    on_favorites_integration_enabled()  # This will create the list if it doesn't exist

                    # Refresh the lists to include the newly created "Kodi Favorites"
                    all_lists = query_manager.get_all_lists_with_folders()
                    user_lists = all_lists

                    # Find the newly created Kodi Favorites
                    for item in user_lists:
                        if item.get('name') == 'Kodi Favorites':
                            kodi_favorites_item = item
                            break

                    context.logger.info("LISTS HANDLER: Refreshed lists, now have %s total lists", len(user_lists))
                except Exception as e:
                    context.logger.error("LISTS HANDLER: Error ensuring Kodi Favorites list exists: %s", e)

            # ADD KODI FAVORITES FIRST (before any folders or other lists)
            if favorites_enabled and kodi_favorites_item:
                list_id = kodi_favorites_item.get('id')
                name = kodi_favorites_item.get('name', 'Kodi Favorites')
                description = kodi_favorites_item.get('description', '')

                context_menu = [
                    (f"Tools & Options for '{name}'", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': name,
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': description,
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Get all existing folders to display as navigable items
            all_folders = query_manager.get_all_folders()

            # Add folders as navigable items (excluding Search History which is now at root level)
            for folder_info in all_folders:
                folder_id = folder_info['id']
                folder_name = folder_info['name']

                # Skip the reserved "Search History" folder since it's now shown at root level
                if folder_name == 'Search History':
                    continue

                # Folder context menu with proper actions (no Tools & Options)
                context_menu = [
                    (f"Rename '{folder_name}'", f"RunPlugin({context.build_url('rename_folder', folder_id=folder_id)})"),
                    (f"Move '{folder_name}'", f"RunPlugin({context.build_url('move_folder', folder_id=folder_id)})"),
                    (f"Delete '{folder_name}'", f"RunPlugin({context.build_url('delete_folder', folder_id=folder_id)})")
                ]

                menu_items.append({
                    'label': folder_name,
                    'url': context.build_url('show_folder', folder_id=folder_id),
                    'is_folder': True,
                    'description': f"Folder",
                    'context_menu': context_menu
                })

            # Separate standalone lists (not in any folder) - EXCLUDE "Kodi Favorites" since it's already added first
            standalone_lists = [item for item in user_lists if (not item.get('folder_name') or item.get('folder_name') == 'Root') and item.get('name') != 'Kodi Favorites']

            # Add standalone lists (not in any folder) - Kodi Favorites already added above
            for list_item in standalone_lists:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')

                # Special handling for Kodi Favorites - limited context menu
                if name == 'Kodi Favorites':
                    context_menu = [
                        (f"Tools & Options for '{name}'", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})")
                    ]
                else:
                    context_menu = [
                        (f"Rename '{name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
                        (f"Move '{name}' to Folder", f"RunPlugin({context.build_url('move_list_to_folder', list_id=list_id)})"),
                        (f"Export '{name}'", f"RunPlugin({context.build_url('export_list', list_id=list_id)})"),
                        (f"Delete '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                    ]

                menu_items.append({
                    'label': name,
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': description,
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Breadcrumb context now integrated into Tools & Options labels

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'], offscreen=True)

                if 'description' in item:
                    self._set_listitem_plot(list_item, item['description'])

                # Apply custom art based on item type
                self._set_custom_art_for_item(list_item, item)

                if 'context_menu' in item:
                    list_item.addContextMenuItems(item['context_menu'])

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    item['url'],
                    list_item,
                    item['is_folder']
                )

            # Determine if this is a refresh or initial load
            is_refresh = context.get_param('rt') is not None  # Refresh token indicates mutation/refresh

            return DirectoryResponse(
                items=menu_items,
                success=True,
                content_type="files",
                update_listing=is_refresh,  # REPLACE semantics for refresh, PUSH for initial
                intent=None  # Pure rendering, no navigation intent
            )

        except Exception as e:
            context.logger.error("Error in show_lists_menu: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    def show_folder(self, context: PluginContext, folder_id: str) -> DirectoryResponse:
        """Display contents of a specific folder"""
        try:
            context.logger.debug("Displaying folder %s", folder_id)

            # Initialize query manager
            query_manager = get_query_manager()

            init_result = query_manager.initialize()

            if not init_result:
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # BATCH OPTIMIZATION: Get folder info, subfolders, and lists in single database call
            # BATCH OPTIMIZATION: Get folder info, subfolders, and lists in single database call
            navigation_data = query_manager.get_folder_navigation_batch(folder_id)

            # Extract data from batch result
            folder_info = navigation_data['folder_info']
            subfolders = navigation_data['subfolders']
            lists_in_folder = navigation_data['lists']

            if not folder_info:
                context.logger.error("Folder %s not found", folder_id)
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Set proper parent directory for navigation
            parent_folder_id = folder_info.get('parent_folder_id')
            if parent_folder_id:
                # Navigate to parent folder
                parent_path = context.build_url('show_folder', folder_id=parent_folder_id)
            else:
                # Navigate to root plugin directory (main lists menu)
                parent_path = context.build_url('lists')  # Use 'lists' action for main menu

            context.logger.debug("Setting parent path for folder %s: %s", folder_id, parent_path)
            # Set parent directory using the correct xbmcplugin method
            import xbmc
            xbmc.executebuiltin(f'SetProperty(ParentDir,{parent_path})')
            # Also try the container method
            xbmc.executebuiltin(f'SetProperty(Container.ParentDir,{parent_path})')

            context.logger.debug("Folder '%s' (id=%s) has %s subfolders and %s lists", folder_info['name'], folder_id, len(subfolders), len(lists_in_folder))

            # Set directory title with breadcrumb context
            directory_title = self.breadcrumb_helper.get_directory_title_breadcrumb("show_folder", {"folder_id": folder_id}, query_manager)
            if directory_title:
                try:
                    # Set the directory title in Kodi
                    import xbmc
                    xbmc.executebuiltin(f'SetProperty(FolderName,{directory_title})')
                    context.logger.debug("Set directory title: '%s'", directory_title)
                except Exception as e:
                    context.logger.debug("Could not set directory title: %s", e)

            menu_items = []

            # Add subfolders in this folder
            for subfolder in subfolders:
                subfolder_id = subfolder.get('id')
                subfolder_name = subfolder.get('name', 'Unnamed Folder')

                # Subfolder context menu with proper actions (no Tools & Options)
                context_menu = [
                    (f"Rename '{subfolder_name}'", f"RunPlugin({context.build_url('rename_folder', folder_id=subfolder_id)})"),
                    (f"Move '{subfolder_name}'", f"RunPlugin({context.build_url('move_folder', folder_id=subfolder_id)})"),
                    (f"Delete '{subfolder_name}'", f"RunPlugin({context.build_url('delete_folder', folder_id=subfolder_id)})")
                ]

                menu_items.append({
                    'label': f"📁 {subfolder_name}",
                    'url': context.build_url('show_folder', folder_id=subfolder_id),
                    'is_folder': True,
                    'description': f"Subfolder",
                    'context_menu': context_menu,
                    'icon': "DefaultFolder.png"
                })

            # Add lists in this folder
            for list_item in lists_in_folder:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')

                context_menu = [
                    (f"Rename '{name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
                    (f"Move '{name}' to Folder", f"RunPlugin({context.build_url('move_list_to_folder', list_id=list_id)})"),
                    (f"Export '{name}'", f"RunPlugin({context.build_url('export_list', list_id=list_id)})"),
                    (f"Delete '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': name,
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': description,
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Add Tools & Options for folders that support it
            if self._folder_has_tools(folder_info):
                # Generate breadcrumb for Tools & Options
                breadcrumb_text = self.breadcrumb_helper.get_breadcrumb_for_tools_label(
                    'show_folder', 
                    {'folder_id': folder_id}, 
                    context.query_manager
                )
                description_text = self.breadcrumb_helper.get_breadcrumb_for_tools_description(
                    'show_folder', 
                    {'folder_id': folder_id}, 
                    context.query_manager
                )
                
                tools_menu_item = {
                    'label': f"⚙️ Tools & Options {breadcrumb_text}",
                    'url': context.build_url('show_list_tools', list_type='folder', list_id=folder_id),
                    'is_folder': True,
                    'description': f"{description_text}Tools and options for this folder",
                    'icon': "DefaultAddonProgram.png",
                    'context_menu': []  # No context menu for tools item itself
                }
                # Insert at the beginning of the menu for visibility
                menu_items.insert(0, tools_menu_item)

            # If folder is empty, show message using lightweight method to avoid loading full renderer
            if not lists_in_folder and not subfolders: # Also check for subfolders being empty
                self._create_simple_empty_state_item(
                    context,
                    "Folder is empty",  # TODO: Add L() ID for this
                    'This folder contains no lists or subfolders'  # This string should also be localized
                )

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'], offscreen=True)

                if 'description' in item:
                    self._set_listitem_plot(list_item, item['description'])

                # Apply custom art based on item type
                self._set_custom_art_for_item(list_item, item)

                if 'context_menu' in item:
                    list_item.addContextMenuItems(item['context_menu'])

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    item['url'],
                    list_item,
                    item['is_folder']
                )

            # Use navigation policy to determine navigation mode
            from lib.ui.nav_policy import decide_mode
            current_route = 'show_folder'
            next_route = current_route  # Same route for folder view
            current_params = {'folder_id': folder_id}
            next_params = current_params  # Same params for folder view
            nav_mode = decide_mode(current_route, next_route, 'folder_view', current_params, next_params)
            update_listing = (nav_mode == 'replace')

            return DirectoryResponse(
                items=menu_items,
                success=True,
                content_type="files",
                update_listing=update_listing,  # Use nav_policy decision
                intent=None  # Pure rendering, no navigation intent
            )

        except Exception as e:
            context.logger.error("Error showing folder: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    def view_list(self, context: PluginContext, list_id: str) -> DirectoryResponse:
        """Display contents of a specific list"""
        try:
            context.logger.debug("Displaying list %s", list_id)

            # Determine navigation mode (push or replace)
            nav_mode = context.get_param('nav_mode', 'push') # Default to push

            # Check for custom parent path to fix navigation from search results
            parent_path = context.get_param('parent_path')
            if parent_path:
                context.logger.debug("Setting custom parent path: %s", parent_path)
                # This will be used by Kodi for the ".." navigation
                xbmcplugin.setProperty(context.addon_handle, 'ParentDir', parent_path)

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get list info
            list_info = query_manager.get_list_by_id(list_id)
            if not list_info:
                context.logger.error("List %s not found", list_id)
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get pagination parameters
            current_page = int(context.get_param('page', '1'))

            # Import pagination manager
            from lib.ui.pagination_manager import get_pagination_manager
            pagination_manager = get_pagination_manager()

            # Get total count first for pagination calculation
            total_items = query_manager.get_list_item_count(int(list_id))

            # Calculate pagination using settings-based page size
            pagination_info = pagination_manager.calculate_pagination(
                total_items=total_items,
                current_page=current_page,
                base_page_size=100  # Base size for auto mode calculation
            )

            # Get list items with pagination
            list_items = query_manager.get_list_items(
                list_id,
                limit=pagination_info.page_size,
                offset=pagination_info.start_index
            )

            context.logger.debug("List '%s' has %s items", list_info['name'], len(list_items))

            # Set directory title with breadcrumb context
            directory_title = self.breadcrumb_helper.get_directory_title_breadcrumb("show_list", {"list_id": list_id}, query_manager)
            if directory_title:
                try:
                    # Set the directory title in Kodi
                    import xbmc
                    xbmc.executebuiltin(f'SetProperty(FolderName,{directory_title})')
                    context.logger.debug("Set directory title: '%s'", directory_title)
                except Exception as e:
                    context.logger.debug("Could not set directory title: %s", e)

            # Add Tools & Options with unified breadcrumb approach
            breadcrumb_text, description_text = self.breadcrumb_helper.get_tools_breadcrumb_formatted("show_list", {"list_id": list_id}, query_manager)

            tools_item = xbmcgui.ListItem(label=f"{L(36000)} {breadcrumb_text}", offscreen=True)
            self._set_listitem_plot(tools_item, description_text + "Tools and options for this list")
            tools_item.setProperty('IsPlayable', 'false')
            tools_item.setArt({'icon': "DefaultAddonProgram.png", 'thumb': "DefaultAddonProgram.png"})

            xbmcplugin.addDirectoryItem(
                context.addon_handle,
                context.build_url('show_list_tools', list_type='user_list', list_id=list_id),
                tools_item,
                True
            )

            # Handle empty lists using lightweight method to avoid loading full renderer
            if not list_items:
                context.logger.debug("List is empty")
                self._create_simple_empty_state_item(
                    context,
                    L(30602),
                    'This list contains no items'  # This string should also be localized
                )

                # Use navigation mode for update_listing decision
                update_listing = (nav_mode == 'replace')

                from lib.ui.response_types import NavigationIntent
                intent = NavigationIntent(mode=nav_mode if nav_mode != 'push' else None, url=None)

                return DirectoryResponse(
                    items=[],
                    success=True,
                    content_type="files",
                    update_listing=update_listing, # REPLACE for same list, PUSH for different list
                    intent=intent
                )

            # Add pagination controls if needed
            if pagination_info.total_pages > 1:
                # Build base URL for pagination navigation - use raw base URL and include all params
                base_url = context.base_url.rstrip('/')
                url_params = {
                    'action': 'show_list',
                    'list_id': list_id
                }  # Include action and list_id in parameters

                # Insert pagination controls into list_items
                list_items = pagination_manager.insert_pagination_items(
                    items=list_items,
                    pagination_info=pagination_info,
                    base_url=base_url,
                    url_params=url_params,
                    placement='bottom'
                )
                context.logger.debug("Added pagination controls to list (page %d/%d)",
                                   pagination_info.current_page, pagination_info.total_pages)

            # Build media items using ListItemBuilder
            try:
                from lib.ui.listitem_builder import ListItemBuilder
                builder = ListItemBuilder(context.addon_handle, context.addon_id, context)
                # Use auto-detect for content type (None) instead of hardcoding "movies"
                success = builder.build_directory(list_items, None)
                if success:
                    context.logger.debug("Successfully built directory with %s items", len(list_items))

                    # Determine if this is a refresh or initial load
                    is_refresh = context.get_param('rt') is not None  # Refresh token indicates mutation/refresh

                    # Use navigation mode for update_listing decision
                    update_listing = (nav_mode == 'replace')
                    from lib.ui.response_types import NavigationIntent
                    intent = NavigationIntent(mode=nav_mode if nav_mode != 'push' else None, url=None)

                    # Return proper DirectoryResponse
                    return DirectoryResponse(
                        items=list_items,
                        success=True,
                        content_type="movies" if list_items and list_items[0].get('media_type') == 'movie' else "files",
                        update_listing=update_listing, # REPLACE for same list, PUSH for different list
                        intent=intent
                    )
            except Exception as e:
                context.logger.error("Error building list items: %s", e)
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Determine content type for the list
            detected_content_type = "files"  # Default
            if list_items:
                first_item = list_items[0]
                media_type = first_item.get('media_type', 'unknown')
                if media_type in ['movie', 'tvshow']:
                    detected_content_type = "movies" if media_type == 'movie' else "tvshows"
                elif media_type == 'episode':
                    detected_content_type = "episodes"

            context.logger.debug("Using content type: %s for list with %s items", detected_content_type, len(list_items))

            # Set content type for better Kodi integration
            xbmcplugin.setContent(context.addon_handle, detected_content_type)

            # Determine if this is a refresh or initial load
            is_refresh = context.get_param('rt') is not None  # Refresh token indicates mutation/refresh

            # Use navigation mode for update_listing decision
            update_listing = (nav_mode == 'replace')
            from lib.ui.response_types import NavigationIntent
            intent = NavigationIntent(mode=nav_mode if nav_mode != 'push' else None, url=None)

            return DirectoryResponse(
                items=list_items,
                success=True,
                content_type=detected_content_type,
                update_listing=update_listing, # REPLACE for same list, PUSH for different list
                intent=intent
            )

        except Exception as e:
            context.logger.error("Error viewing list: %s", e)
            import traceback
            context.logger.error("Traceback: %s", traceback.format_exc())
            return DirectoryResponse(
                items=[],
                success=False
            )

    def show_search_history(self, context: PluginContext) -> DirectoryResponse:
        """Display search history lists"""
        try:
            context.logger.debug("Displaying search history")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get search history folder by searching all folders
            search_folder = None
            all_folders = query_manager.get_all_folders()
            for folder in all_folders:
                if folder.get('name') == 'Search History':
                    search_folder = folder
                    break

            if not search_folder:
                # Create search history folder if it doesn't exist
                result = query_manager.create_folder('Search History')
                if result.get('error'):
                    context.logger.error("Failed to create Search History folder")
                    return DirectoryResponse(
                        items=[],
                        success=False
                    )
                # Get the folder again after creation
                all_folders = query_manager.get_all_folders()
                for folder in all_folders:
                    if folder.get('name') == 'Search History':
                        search_folder = folder
                        break

            if not search_folder:
                context.logger.error("Could not access Search History folder")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get search history lists
            search_lists = query_manager.get_lists_in_folder(search_folder['id'])
            context.logger.debug("Found %s search history lists", len(search_lists))

            menu_items = []

            # Add search history lists
            for list_item in search_lists:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed Search')
                description = list_item.get('description', '')

                context_menu = [
                    (f"Delete '{name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': name,
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': description,
                    'icon': "DefaultAddonProgram.png",
                    'context_menu': context_menu
                })

            # If no search history, show message using lightweight method to avoid loading full renderer
            if not search_lists:
                self._create_simple_empty_state_item(
                    context,
                    "No search history",  # TODO: Add L() ID for this
                    'Search results will appear here'
                )

            # Build directory items
            for item in menu_items:
                list_item = xbmcgui.ListItem(label=item['label'], offscreen=True)

                if 'description' in item:
                    self._set_listitem_plot(list_item, item['description'])

                if 'icon' in item:
                    list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

                if 'context_menu' in item:
                    list_item.addContextMenuItems(item['context_menu'])

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    item['url'],
                    list_item,
                    item['is_folder']
                )

            # Determine if this is a refresh or initial load
            is_refresh = context.get_param('rt') is not None  # Refresh token indicates mutation/refresh

            return DirectoryResponse(
                items=menu_items,
                success=True,
                content_type="files",
                update_listing=is_refresh,  # REPLACE semantics for refresh, PUSH for initial
                intent=None  # Pure rendering, no navigation intent
            )

        except Exception as e:
            context.logger.error("Error showing search history: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    # =================================
    # LEGACY/COMPATIBILITY METHODS
    # =================================

    def _show_empty_lists_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show menu when no lists exist"""
        if xbmcgui.Dialog().yesno(
            L(35002), # "LibraryGenie"
            "No lists found. Create your first list?" # This string should also be localized
        ):
            create_response = self.create_list(context)
            # Convert DialogResponse to DirectoryResponse
            return DirectoryResponse(
                items=[],
                success=create_response.success,
                update_listing=False, # PUSH semantics for initial load
                intent=None # Pure rendering, no navigation intent
            )

        return DirectoryResponse(items=[], success=True, update_listing=False, intent=None)

    # Additional compatibility methods for context menus and other operations
    def add_to_list_context(self, context: PluginContext) -> bool:
        """Handle adding media item to a list from context menu"""
        try:
            media_item_id = context.get_param('media_item_id')
            if not media_item_id:
                context.logger.error("No media item ID provided for context menu add")
                return False

            return self.add_to_list_menu(context, media_item_id)

        except Exception as e:
            context.logger.error("Error adding to list from context: %s", e)
            return False

    def quick_add_context(self, context: PluginContext) -> bool:
        """Handle quick add to default list from context menu"""
        try:
            # Get parameters
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')
            title = context.get_param('title', 'Unknown')

            # Get settings
            from lib.config.settings import SettingsManager
            settings = SettingsManager()
            default_list_id = settings.get_default_list_id()

            if not default_list_id:
                import xbmcgui
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "No default list configured",
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return False

            # Create minimal library item data - add_library_item_to_list will handle metadata fetching
            library_item = {
                'title': title,
                'media_type': dbtype,
                'kodi_id': int(dbid) if dbid else None,
                'source': 'kodi_library'
            }

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                return False

            # Add to default list - this will fetch metadata if needed
            result = query_manager.add_library_item_to_list(default_list_id, library_item)

            # Show success notification
            import xbmcgui
            if result:
                # Get list name for notification
                list_info = query_manager.get_list_by_id(default_list_id)
                list_name = list_info.get('name', 'Default List') if list_info else 'Default List'

                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added '{title}' to {list_name}",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                return True
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Failed to add '{title}' to list",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False

        except Exception as e:
            context.logger.error("Error quick adding to list from context: %s", e)
            import xbmcgui
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Quick add failed",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return False

    def add_external_item_to_list(self, context: PluginContext) -> bool:
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

            context.logger.info("Processing external item: %s (type: %s)", media_item['title'], media_item['media_type'])

            # Use existing add_to_list flow with the external media item
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return False

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
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
                    "No lists available", # Localize this string
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return False

            # Show list selection dialog
            selected_index = xbmcgui.Dialog().select(
                f"Add '{media_item['title']}' to list:", # Localize this string
                list_options
            )

            if selected_index < 0:
                return False  # User cancelled

            selected_list_id = list_ids[selected_index]
            selected_list_name = list_options[selected_index]

            # Add the external item to the selected list
            result = query_manager.add_item_to_list(selected_list_id, media_item)
            success = result is not None and result.get("success", False)

            if success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added '{media_item['title']}' to '{selected_list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                # Refresh container to show changes
                import xbmc
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Failed to add item to list", # Localize this string
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False

        except Exception as e:
            context.logger.error("Error in add_external_item_to_list: %s", e)
            return False

    def remove_library_item_from_list(self, context: PluginContext, list_id: str, dbtype: str, dbid: str) -> bool:
        """Handle removing a library item from a list using dbtype and dbid"""
        try:
            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return False

            # Get list items to find the matching item
            list_items = query_manager.get_list_items(list_id)
            matching_item = None

            for item in list_items:
                if (item.get('kodi_id') == int(dbid) and
                    item.get('media_type') == dbtype):
                    matching_item = item
                    break

            if not matching_item or 'id' not in matching_item:
                context.logger.warning("Could not find library item %s:%s in list %s", dbtype, dbid, list_id)
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Item not found in list",
                    xbmcgui.NOTIFICATION_WARNING
                )
                return False

            # Use the regular remove method with the found item ID
            response = self.remove_from_list(context, list_id, str(matching_item['id']))

            # Handle the DialogResponse
            from lib.ui.response_types import DialogResponse
            from lib.ui.response_handler import get_response_handler

            if isinstance(response, DialogResponse):
                response_handler = get_response_handler()
                response_handler.handle_dialog_response(response, context)
                return response.success

            return False

        except Exception as e:
            context.logger.error("Error removing library item from list: %s", e)
            return False

    def _folder_has_tools(self, folder_info: dict) -> bool:
        """Check if a folder should have Tools & Options available"""
        try:
            # All folders should have tools available
            return True
            
        except Exception as e:
            self.logger.warning("Error checking folder tools availability: %s", e)
            return False