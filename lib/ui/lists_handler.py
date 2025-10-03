#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Lists Handler
Handles lists display and navigation (refactored)
"""

import xbmcplugin
import xbmcgui
import time
import os

from typing import Dict, Any, List, Optional
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DirectoryResponse, DialogResponse
from lib.ui.localization import L
from lib.ui.breadcrumb_helper import get_breadcrumb_helper
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager
from lib.utils.kodi_version import get_kodi_major_version
from lib.ui.dialog_service import get_dialog_service

# Import the specialized operation modules
from lib.ui.list_operations import ListOperations
from lib.ui.folder_operations import FolderOperations
from lib.ui.folder_cache import get_folder_cache
from lib.ui.menu_helpers import (
    build_folder_context_menu,
    build_list_context_menu,
    build_kodi_favorites_context_menu,
    build_search_history_list_context_menu
)


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
    
    def quick_add_to_default_list(self, context: PluginContext) -> DialogResponse:
        """Quick add item to default list"""
        try:
            media_item_id = context.get_param('media_item_id')
            if not media_item_id:
                return DialogResponse(success=False, message="Missing media item ID")
            
            # TODO: Implement add_item_to_default_list method in ListOperations
            return DialogResponse(success=False, message="Method not implemented yet")
            
        except Exception as e:
            self.logger.error("Error in quick_add_to_default_list: %s", e)
            return DialogResponse(success=False, message="Failed to add item to default list")
    
    def quick_add_library_item_to_default_list(self, context: PluginContext) -> DialogResponse:
        """Quick add library item to default list"""
        try:
            media_item_id = context.get_param('media_item_id')
            if not media_item_id:
                return DialogResponse(success=False, message="Missing media item ID")
            
            # TODO: Implement add_library_item_to_default_list method in ListOperations
            return DialogResponse(success=False, message="Method not implemented yet")
            
        except Exception as e:
            self.logger.error("Error in quick_add_library_item_to_default_list: %s", e)
            return DialogResponse(success=False, message="Failed to add library item to default list")
    
    def quick_add_external_item_to_default_list(self, context: PluginContext) -> DialogResponse:
        """Quick add external item to default list"""
        try:
            media_item_id = context.get_param('media_item_id')
            if not media_item_id:
                return DialogResponse(success=False, message="Missing media item ID")
            
            # TODO: Implement add_external_item_to_default_list method in ListOperations
            return DialogResponse(success=False, message="Method not implemented yet")
            
        except Exception as e:
            self.logger.error("Error in quick_add_external_item_to_default_list: %s", e)
            return DialogResponse(success=False, message="Failed to add external item to default list")

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
            item_name = item_data.get('title', 'Unknown')
            item_type = 'folder' if 'action=show_folder' in item_data.get('url', '') else 'list' if 'action=show_list' in item_data.get('url', '') else 'unknown'

            # Check if item has custom art_data (from imported folders)
            art_data = item_data.get('art_data')
            if art_data:
                # Parse art_data if it's a JSON string
                import json
                if isinstance(art_data, str):
                    try:
                        art_data = json.loads(art_data)
                    except (json.JSONDecodeError, ValueError):
                        self.logger.warning("LISTITEM ART: Failed to parse art_data JSON for %s '%s'", item_type, item_name)
                        art_data = None
                
                # Apply custom artwork if valid
                if art_data and isinstance(art_data, dict):
                    self.logger.info("LISTITEM ART: Applying custom art to %s '%s' with %d types: %s", 
                                   item_type, item_name, len(art_data), list(art_data.keys()))
                    for art_type, art_path in art_data.items():
                        self.logger.debug("  - %s: %s", art_type, os.path.basename(art_path) if art_path and not art_path.startswith('http') else art_path[:50])
                    renderer.art_manager.apply_art(list_item, art_data, fallback_icon='DefaultFolder.png')
                    return

            # Determine if this is a list or folder based on the URL action
            url = item_data.get('url', '')

            if 'action=show_list' in url:
                # This is a user list - use list/playlist art with custom resources
                self.logger.debug("LISTITEM ART: Applying default list art to '%s'", item_name)
                renderer._apply_art(list_item, 'list')
            elif 'action=show_folder' in url:
                # This is a folder - use folder art with custom resources
                self.logger.debug("LISTITEM ART: Applying default folder art to '%s'", item_name)
                renderer._apply_art(list_item, 'folder')
            else:
                # Default/other items - use original icon if specified
                if 'icon' in item_data:
                    self.logger.debug("LISTITEM ART: Using custom icon for '%s'", item_name)
                    list_item.setArt({'icon': item_data['icon'], 'thumb': item_data['icon']})
                else:
                    # Use folder art as default for other navigable items
                    self.logger.debug("LISTITEM ART: Applying default folder art (fallback) to '%s'", item_name)
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

    def show_lists_menu(self, context: PluginContext, force_main_menu: bool = False) -> DirectoryResponse:
        """Show main lists menu with folders and lists
        
        Args:
            context: Plugin context
            force_main_menu: If True, skip startup folder redirect (for "Back to Main Menu")
        """
        try:
            show_lists_start = time.time()
            self.logger.debug("Displaying lists menu (force_main_menu=%s)", force_main_menu)

            # Check for startup folder redirect (before cache or any other operations)
            # Skip if force_main_menu is True (from "Back to Main Menu" button)
            if not force_main_menu:
                from lib.config.config_manager import get_config
                config = get_config()
                startup_folder_id = config.get('startup_folder_id', None)
                
                if startup_folder_id and startup_folder_id.strip():
                    self.logger.info("Startup folder configured (%s) - redirecting to folder", startup_folder_id)
                    # Navigate to the startup folder with special flag
                    from lib.ui.nav import push
                    url = context.build_url('show_folder', folder_id=startup_folder_id, is_startup_folder='true')
                    push(url)
                    # Return empty response since navigation is handled
                    return DirectoryResponse(items=[], success=True)

            # CACHE-FIRST: Check cache before ANY database operations (zero-DB overhead on HIT)
            folder_cache = get_folder_cache()
            folder_id = None  # Root folder
            cache_key = "root" if folder_id is None else folder_id
            cached_data = folder_cache.get(cache_key)
            
            all_lists = None
            all_folders = None
            db_query_time = 0
            cache_used = False
            query_manager = None
            
            if cached_data:
                # CACHE HIT: Use cached processed items (ZERO database overhead)
                cache_used = True
                cached_breadcrumbs = cached_data.get('breadcrumbs', {})
                build_time = cached_data.get('_build_time_ms', 0)
                processed_menu_items = cached_data.get('processed_items', [])
                # Set to empty lists since we're using cached processed items
                all_lists = []
                all_folders = []
                self.logger.debug("CACHE HIT: %d processed items (built in %d ms) - ZERO DB OVERHEAD", 
                                   len(processed_menu_items), build_time)
            else:
                # CACHE MISS: Initialize DB and query, then cache the result
                self.logger.debug("CACHE MISS: Root folder not cached, querying database")
                processed_menu_items = None
                all_lists = []
                all_folders = []
                
                # Only initialize query manager on cache miss
                query_manager = self.query_manager
                init_result = query_manager.initialize()

                if not init_result:
                    self.logger.error("Failed to initialize query manager")
                    return DirectoryResponse(
                        items=[],
                        success=False
                    )

                # Get all user lists and folders from database (BATCH for cache building)
                db_query_start = time.time()
                all_lists = query_manager.get_all_lists_with_folders()
                all_folders = query_manager.get_all_folders()
                db_query_time = (time.time() - db_query_start) * 1000
                self.logger.debug("TIMING: Database query for lists and folders took %.2f ms", db_query_time)
                
                # Build processed menu items with business logic applied (for schema v4 cache)
                processed_menu_items = self._build_processed_menu_items(
                    context, all_lists, all_folders, query_manager
                )
                
                # VALIDATION: Check for empty data before caching
                if len(processed_menu_items) == 0:
                    self.logger.info(
                        "Root folder has 0 processed items (%d lists, %d folders from DB) - caching as legitimate empty state",
                        len(all_lists), len(all_folders)
                    )
                
                # Cache the final processed view instead of raw data (schema v4)
                breadcrumb_data = {
                    'directory_title': 'Lists',
                    'tools_label': 'Lists', 
                    'tools_description': 'Search, Favorites, Import/Export & Settings'
                }
                cached_breadcrumbs = breadcrumb_data
                
                cache_payload = {
                    'processed_items': processed_menu_items,
                    'breadcrumbs': breadcrumb_data,
                    'content_type': 'files'
                }
                
                # Log what we're about to cache for debugging
                self.logger.debug(
                    "CACHE UPDATE: About to cache root folder with %d processed items from %d lists and %d folders",
                    len(processed_menu_items), len(all_lists), len(all_folders)
                )
                
                cache_key = "root" if folder_id is None else folder_id
                cache_success = folder_cache.set(cache_key, cache_payload, int(db_query_time))
                if cache_success:
                    self.logger.debug("CACHE UPDATE: Successfully stored root folder")
                else:
                    self.logger.warning("CACHE UPDATE: Failed to cache root folder (likely validation failure)")

            # Initialize user_lists for empty state check
            user_lists = []
            
            # Handle cached processed items vs building from raw data
            if cache_used:
                # Use pre-processed items directly from cache (without Tools & Options)
                menu_items = processed_menu_items if processed_menu_items else []
                self.logger.debug("Using %d pre-processed menu items from cache (Tools & Options will be added dynamically)", len(menu_items))
            else:
                # Cache miss: Build menu items from database data
                user_lists = all_lists
                self.logger.debug("Found %s total lists (cache_used: %s)", len(user_lists), cache_used)
                menu_items = self._build_processed_menu_items(context, all_lists, all_folders, query_manager)
                self.logger.debug("Built %d menu items from raw data", len(menu_items))

            # Check for empty state when no cache used
            if not cache_used:

                if not user_lists:
                    # No lists exist - show empty state instead of dialog
                    # This prevents confusing dialogs when navigating back from deletions
                    menu_items = []

                    # Add "Tools & Options" with breadcrumb context (if user preference enabled)
                    from lib.config.config_manager import get_config
                    config = get_config()
                    show_tools_item = config.get_bool('show_tools_menu_item', True)
                    
                    if show_tools_item:
                        breadcrumb_text = self.breadcrumb_helper.get_breadcrumb_for_tools_label('lists', {}, None)
                        description_prefix = self.breadcrumb_helper.get_breadcrumb_for_tools_description('lists', {}, None)

                        menu_items.append({
                            'label': f"{L(30212)} {breadcrumb_text}",
                            'url': context.build_url('show_list_tools', list_type='lists_main'),
                            'is_folder': True,
                            'icon': "DefaultAddonProgram.png",
                            'description': f"{description_prefix}{L(30218)}"  # Breadcrumb + "Access lists tools and options"
                        })

                    # Add "Create First List" option
                    menu_items.append({
                        'label': f"+ {L(30367)}",
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

            # Use cached breadcrumb data when available (ZERO DB overhead)
            if cache_used and cached_breadcrumbs:
                directory_title = cached_breadcrumbs.get('directory_title', 'Lists')
            else:
                directory_title = self.breadcrumb_helper.get_directory_title_breadcrumb(breadcrumb_action, breadcrumb_params, query_manager)
            
            if directory_title:
                try:
                    # Set the directory title in Kodi using proper window property API
                    window = xbmcgui.Window(10025)  # Video window
                    window.setProperty('FolderName', directory_title)
                    self.logger.debug("Set directory title: '%s' (cache: %s)", directory_title, cache_used)
                except Exception as e:
                    self.logger.debug("Could not set directory title: %s", e)

            # Add Tools & Options dynamically at the beginning (not cached, respects user visibility setting)
            # Use cached breadcrumb data when available (ZERO DB overhead)
            if cache_used and cached_breadcrumbs:
                tools_label = cached_breadcrumbs.get('tools_label', 'Lists')
                tools_description = cached_breadcrumbs.get('tools_description', 'Search, Favorites, Import/Export & Settings')
            else:
                breadcrumb_text, description_prefix = self.breadcrumb_helper.get_tools_breadcrumb_formatted(breadcrumb_action, breadcrumb_params, query_manager)
                tools_label = breadcrumb_text or 'Lists'
                tools_description = f"{description_prefix or ''}Search, Favorites, Import/Export & Settings"
            
            # For lists_main handler, always use 'lists_main' type
            # If viewing a folder within lists_main, the folder_id parameter provides context
            tools_item = self.breadcrumb_helper.build_tools_menu_item(
                base_url=context.base_url,
                list_type='lists_main',
                breadcrumb_text=tools_label,
                description_text=tools_description,
                folder_id=current_folder_id if current_folder_id else None
            )
            
            # Insert Tools & Options at the beginning if enabled (visibility check is in build_tools_menu_item)
            if tools_item:
                menu_items.insert(0, tools_item)

            # Search and other tools are now accessible via Tools & Options menu (if enabled) or context menus

            # Initialize favorites variables (needed for both cached and non-cached paths)
            from lib.config.config_manager import get_config
            config = get_config()
            favorites_enabled = config.get_bool('favorites_integration_enabled', False)
            kodi_favorites_item = None

            # When using cached items, skip the rebuild logic below (cached items already have everything)
            if not cache_used:
                # Find existing Kodi Favorites or create if needed
                for item in user_lists:
                    if item.get('name') == 'Kodi Favorites':
                        kodi_favorites_item = item
                        break

                if favorites_enabled and not kodi_favorites_item:
                    # Create "Kodi Favorites" list if it doesn't exist but setting is enabled
                    self.logger.info("LISTS HANDLER: Favorites integration enabled but 'Kodi Favorites' list not found, creating it")
                    try:
                        from lib.config.favorites_helper import on_favorites_integration_enabled
                        on_favorites_integration_enabled()  # This will create the list if it doesn't exist

                        # Refresh the lists to include the newly created "Kodi Favorites"
                        if query_manager is not None:
                            all_lists = query_manager.get_all_lists_with_folders()
                        else:
                            all_lists = []
                        user_lists = all_lists

                        # Find the newly created Kodi Favorites
                        for item in user_lists:
                            if item.get('name') == 'Kodi Favorites':
                                kodi_favorites_item = item
                                break

                        self.logger.info("LISTS HANDLER: Refreshed lists, now have %s total lists", len(user_lists))
                    except Exception as e:
                        self.logger.error("LISTS HANDLER: Error ensuring Kodi Favorites list exists: %s", e)

                # ADD KODI FAVORITES FIRST (before any folders or other lists)
                if favorites_enabled and kodi_favorites_item:
                    list_id = kodi_favorites_item.get('id')
                    name = kodi_favorites_item.get('name', 'Kodi Favorites')
                    description = kodi_favorites_item.get('description', '')

                    context_menu = build_kodi_favorites_context_menu(context, list_id, name)

                    menu_items.append({
                        'label': name,
                        'url': context.build_url('show_list', list_id=list_id),
                        'is_folder': True,
                        'description': description,
                        'icon': "DefaultPlaylist.png",
                        'context_menu': context_menu
                    })

                # Use cached or fetched folder data
                self.logger.debug("CACHE: Using folder data (%d folders) %s", len(all_folders), 
                                   "- ZERO DB OVERHEAD" if cache_used else "from database")

                # Add folders as navigable items (excluding Search History which is now at root level)
                for folder_info in all_folders:
                    folder_id = folder_info['id']
                    folder_name = folder_info['name']

                    # Skip the reserved "Search History" folder since it's now shown at root level
                    if folder_name == 'Search History':
                        continue

                    # Folder context menu with proper actions
                    context_menu = build_folder_context_menu(context, folder_id, folder_name)

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
                        context_menu = build_kodi_favorites_context_menu(context, list_id, name)
                    else:
                        context_menu = build_list_context_menu(context, list_id, name)

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
            gui_build_start = time.time()
            self.logger.debug("TIMING: Starting GUI building for %d items", len(menu_items))
            
            for i, item in enumerate(menu_items):
                item_start = time.time()
                
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
                
                item_time = (time.time() - item_start) * 1000
                if item_time > 5.0:  # Only log slow items to avoid spam
                    self.logger.debug("TIMING: Item %d ('%s') took %.2f ms", i, item['label'], item_time)
            
            gui_build_time = (time.time() - gui_build_start) * 1000
            self.logger.debug("TIMING: GUI building for %d items took %.2f ms (avg %.2f ms/item)", 
                                len(menu_items), gui_build_time, gui_build_time / max(1, len(menu_items)))

            # Determine if this is a refresh or initial load
            is_refresh = context.get_param('rt') is not None  # Refresh token indicates mutation/refresh

            total_time = (time.time() - show_lists_start) * 1000
            cache_status = "HIT" if cache_used else "MISS"
            self.logger.debug("TIMING: Total show_lists_menu execution took %.2f ms (cache %s)", total_time, cache_status)
            
            return DirectoryResponse(
                items=menu_items,
                success=True,
                content_type="files",
                update_listing=is_refresh,  # REPLACE semantics for refresh, PUSH for initial
                intent=None  # Pure rendering, no navigation intent
            )

        except Exception as e:
            self.logger.error("Error in show_lists_menu: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    def show_folder(self, context: PluginContext, folder_id: str) -> DirectoryResponse:
        """Display contents of a specific folder"""
        try:
            folder_start = time.time()
            self.logger.debug("Displaying folder %s", folder_id)

            # CACHE-FIRST: Check cache before ANY database operations (zero-DB overhead on HIT)
            folder_cache = get_folder_cache()
            cached_data = folder_cache.get(folder_id)
            
            # Check if using modern processed cache format (V4+)
            schema_version = cached_data.get('_schema') if cached_data else None
            
            if cached_data and schema_version in [4, 6, 7, 8, 9]:
                # V4 CACHE HIT: Use pre-built processed menu items (ultra-fast)
                cache_used = True
                processed_items = cached_data.get('processed_items', [])
                cached_breadcrumbs = cached_data.get('breadcrumbs', {})
                build_time = cached_data.get('_build_time_ms', 0)
                self.logger.debug("V4 CACHE HIT: Folder %s with %d processed items, breadcrumbs (built in %d ms) - ZERO DB OVERHEAD", 
                                   folder_id, len(processed_items), build_time)
                
                # Add Tools & Options dynamically (not cached, respects user visibility setting)
                folder_name = cached_breadcrumbs.get('folder_name', 'Unknown Folder')
                tools_item = self.breadcrumb_helper.build_tools_menu_item(
                    base_url=context.base_url,
                    list_type='folder',
                    breadcrumb_text=f"for '{folder_name}'",
                    description_text="Tools and options for this folder",
                    folder_id=folder_id,
                    icon_prefix="⚙️ "
                )
                
                if tools_item:
                    # Insert at beginning of processed items before rendering
                    processed_items.insert(0, tools_item)
                
                # Add "Back to Main Menu" item if this is the startup folder (V4 cache path)
                # Check ConfigManager directly to support all navigation paths (history/bookmarks/etc)
                from lib.config.config_manager import get_config
                config = get_config()
                startup_folder_id = config.get('startup_folder_id', None)
                if startup_folder_id and str(folder_id) == str(startup_folder_id):
                    self.logger.debug("V4 CACHE: Adding 'Back to Main Menu' item for startup folder")
                    back_to_main_item = {
                        'label': "◄ All Lists",
                        'url': context.build_url('show_main_menu_force'),
                        'is_folder': True,
                        'description': "View all lists and folders",
                        'icon': "DefaultFolderBack.png",
                        'context_menu': []
                    }
                    processed_items.append(back_to_main_item)
                
                # Convert processed items directly to ListItems for ultra-fast rendering
                gui_build_start = time.time()
                
                for item in processed_items:
                    list_item = xbmcgui.ListItem(label=item['label'], offscreen=True)
                    
                    if 'description' in item and item['description']:
                        self._set_listitem_plot(list_item, item['description'])
                    
                    if 'icon' in item:
                        list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})
                    
                    # Add context menu if present
                    if 'context_menu' in item and item['context_menu']:
                        list_item.addContextMenuItems(item['context_menu'])
                    
                    xbmcplugin.addDirectoryItem(
                        context.addon_handle,
                        item['url'],
                        list_item,
                        item.get('is_folder', True)
                    )
                
                gui_build_time = (time.time() - gui_build_start) * 1000
                self.logger.debug("V4 CACHE: Rendered %d items in %.2f ms (avg %.2f ms/item)", 
                                   len(processed_items), gui_build_time, gui_build_time / max(1, len(processed_items)))
                
                # Set directory title from cached breadcrumbs
                directory_title = cached_breadcrumbs.get('directory_title', 'Unknown Folder')
                try:
                    window = xbmcgui.Window(10025)
                    window.setProperty('FolderName', directory_title)
                    self.logger.debug("Set directory title from V4 cache: '%s'", directory_title)
                except Exception as e:
                    self.logger.debug("Could not set directory title: %s", e)
                
                # Set parent directory for navigation
                # For subfolders, parent is root lists menu
                parent_path = context.build_url('lists')
                try:
                    window = xbmcgui.Window(10025)
                    window.setProperty('ParentDir', parent_path)
                    window.setProperty('Container.ParentDir', parent_path)
                    self.logger.debug("Set parent path from V4 cache: %s", parent_path)
                except Exception as e:
                    self.logger.debug("Could not set parent path: %s", e)
                
                total_time = (time.time() - folder_start) * 1000
                self.logger.debug("TIMING: V4 cached folder %s rendered in %.2f ms total", folder_id, total_time)
                
                return DirectoryResponse(
                    items=processed_items,  # Return processed items for response tracking
                    success=True,
                    content_type="files"
                )
            
            # V3 cache or cache miss - use traditional flow
            folder_info = None
            subfolders = []
            lists_in_folder = []
            db_query_time = 0
            cache_used = False
            query_manager = None
            
            if cached_data and not schema_version:
                # V3 CACHE HIT: Use old cache format (for compatibility)
                cache_used = True
                folder_info = cached_data.get('folder_info')
                subfolders = cached_data.get('subfolders', [])
                lists_in_folder = cached_data.get('lists', [])
                cached_breadcrumbs = cached_data.get('breadcrumbs', {})
                build_time = cached_data.get('_build_time_ms', 0)
                self.logger.debug("V3 CACHE HIT: Folder %s cached with %d subfolders, %d lists, breadcrumbs (built in %d ms)", 
                                   folder_id, len(subfolders), len(lists_in_folder), build_time)
            else:
                # CACHE MISS: Initialize DB and query, then cache the result
                self.logger.debug("CACHE MISS: Folder %s not cached, querying database", folder_id)
                
                # Only initialize query manager on cache miss
                query_manager = self.query_manager
                init_result = query_manager.initialize()

                if not init_result:
                    self.logger.error("Failed to initialize query manager")
                    return DirectoryResponse(
                        items=[],
                        success=False
                    )

                # BATCH OPTIMIZATION: Get folder info, subfolders, and lists in single database call
                db_query_start = time.time()
                navigation_data = query_manager.get_folder_navigation_batch(folder_id)
                db_query_time = (time.time() - db_query_start) * 1000
                self.logger.debug("TIMING: Database batch query for folder %s took %.2f ms", folder_id, db_query_time)

                # Extract data from batch result
                folder_info = navigation_data['folder_info']
                subfolders = navigation_data['subfolders']
                lists_in_folder = navigation_data['lists']
                
                # Pre-compute breadcrumb components for subfolder
                folder_name = folder_info.get('name', 'Unknown Folder') if folder_info else 'Unknown Folder'
                cached_breadcrumbs = {
                    'directory_title': folder_name,
                    'tools_label': f"for '{folder_name}'",
                    'tools_description': f"Tools and options for this folder"
                }
                
                # Build processed menu items with business logic applied (v4 cache format)
                processed_menu_items = self._build_processed_menu_items(
                    context, lists_in_folder, subfolders, query_manager
                )
                
                # VALIDATION: Check for empty data before caching
                total_items = len(subfolders) + len(lists_in_folder)
                if total_items == 0:
                    self.logger.info(
                        "Folder %s (%s) is empty (0 subfolders, 0 lists) - caching as legitimate empty state",
                        folder_id, folder_name
                    )
                
                # Cache the v4 format with processed items
                cache_payload = {
                    'processed_items': processed_menu_items,  # V4: Store processed menu items
                    'breadcrumbs': cached_breadcrumbs,
                    'content_type': 'files'
                }
                
                # Log what we're about to cache for debugging
                self.logger.debug(
                    "CACHE UPDATE: About to cache folder %s with %d processed items (%d subfolders, %d lists), folder_info=%s",
                    folder_id, len(processed_menu_items), len(subfolders), len(lists_in_folder), folder_info is not None
                )
                
                cache_success = folder_cache.set(folder_id, cache_payload, int(db_query_time))
                if cache_success:
                    self.logger.debug("CACHE UPDATE: Successfully stored folder %s", folder_id)
                else:
                    self.logger.warning("CACHE UPDATE: Failed to cache folder %s (likely validation failure)", folder_id)

            if not folder_info:
                self.logger.error("Folder %s not found", folder_id)
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

            self.logger.debug("Setting parent path for folder %s: %s", folder_id, parent_path)
            # Set parent directory using proper window property API
            window = xbmcgui.Window(10025)  # Video window
            window.setProperty('ParentDir', parent_path)
            window.setProperty('Container.ParentDir', parent_path)

            self.logger.debug("Folder '%s' (id=%s) has %s subfolders and %s lists", folder_info['name'], folder_id, len(subfolders), len(lists_in_folder))

            # Use cached breadcrumb data for directory title (ZERO DB overhead)
            if cache_used and cached_breadcrumbs:
                directory_title = cached_breadcrumbs.get('directory_title', 'Unknown Folder')
                self.logger.debug("Using cached directory title: '%s'", directory_title)
            else:
                breadcrumb_query_manager = query_manager if query_manager is not None else None
                directory_title = self.breadcrumb_helper.get_directory_title_breadcrumb("show_folder", {"folder_id": folder_id}, breadcrumb_query_manager)
            
            if directory_title:
                try:
                    # Set the directory title in Kodi using proper window property API
                    window = xbmcgui.Window(10025)  # Video window
                    window.setProperty('FolderName', directory_title)
                    self.logger.debug("Set directory title: '%s' (cache: %s)", directory_title, cache_used)
                except Exception as e:
                    self.logger.debug("Could not set directory title: %s", e)

            menu_items = []

            # Add subfolders in this folder
            for subfolder in subfolders:
                subfolder_id = subfolder.get('id')
                subfolder_name = subfolder.get('name', 'Unnamed Folder')

                # Subfolder context menu with proper actions
                context_menu = build_folder_context_menu(context, subfolder_id, subfolder_name)

                subfolder_item = {
                    'label': f"📁 {subfolder_name}",
                    'url': context.build_url('show_folder', folder_id=subfolder_id),
                    'is_folder': True,
                    'description': f"Subfolder",
                    'context_menu': context_menu,
                    'icon': "DefaultFolder.png"
                }
                
                # Include art_data and import status if available
                if 'art_data' in subfolder:
                    subfolder_item['art_data'] = subfolder['art_data']
                if 'is_import_sourced' in subfolder:
                    subfolder_item['is_import_sourced'] = subfolder['is_import_sourced']
                
                menu_items.append(subfolder_item)

            # Add lists in this folder
            for list_item in lists_in_folder:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')

                context_menu = build_list_context_menu(context, list_id, name)

                menu_items.append({
                    'label': name,
                    'url': context.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': description,
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })

            # Add Tools & Options for folders that support it (using centralized builder with visibility check)
            if self._folder_has_tools(folder_info):
                # Use cached breadcrumb data for Tools & Options (ZERO DB overhead)
                if cache_used and cached_breadcrumbs:
                    breadcrumb_text = cached_breadcrumbs.get('tools_label', 'for folder')
                    description_text = cached_breadcrumbs.get('tools_description', 'Tools and options for this folder')
                else:
                    breadcrumb_query_manager = query_manager if query_manager is not None else None
                    breadcrumb_text = self.breadcrumb_helper.get_breadcrumb_for_tools_label(
                        'show_folder', 
                        {'folder_id': folder_id}, 
                        breadcrumb_query_manager
                    )
                    description_text = self.breadcrumb_helper.get_breadcrumb_for_tools_description(
                        'show_folder', 
                        {'folder_id': folder_id}, 
                        breadcrumb_query_manager
                    )
                
                tools_menu_item = self.breadcrumb_helper.build_tools_menu_item(
                    base_url=context.base_url,
                    list_type='folder',
                    breadcrumb_text=breadcrumb_text,
                    description_text=f"{description_text}Tools and options for this folder",
                    folder_id=folder_id,
                    icon_prefix="⚙️ "
                )
                
                # Only add if visibility setting allows it
                if tools_menu_item:
                    tools_menu_item['context_menu'] = []  # No context menu for tools item itself
                    # Insert at the beginning of the menu for visibility
                    menu_items.insert(0, tools_menu_item)

            # Add "Back to Main Menu" item if this is the startup folder
            # Check ConfigManager directly to support all navigation paths (history/bookmarks/etc)
            from lib.config.config_manager import get_config
            config = get_config()
            startup_folder_id = config.get('startup_folder_id', None)
            if startup_folder_id and str(folder_id) == str(startup_folder_id):
                self.logger.debug("Adding 'Back to Main Menu' item for startup folder")
                back_to_main_item = {
                    'label': "◄ All Lists",
                    'url': context.build_url('show_main_menu_force'),
                    'is_folder': True,
                    'description': "View all lists and folders",
                    'icon': "DefaultFolderBack.png",
                    'context_menu': []
                }
                menu_items.append(back_to_main_item)

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

            total_folder_time = (time.time() - folder_start) * 1000
            cache_status = "HIT" if cache_used else "MISS" 
            self.logger.debug("TIMING: Total show_folder execution took %.2f ms (cache %s)", total_folder_time, cache_status)

            return DirectoryResponse(
                items=menu_items,
                success=True,
                content_type="files",
                update_listing=update_listing,  # Use nav_policy decision
                intent=None  # Pure rendering, no navigation intent
            )

        except Exception as e:
            self.logger.error("Error showing folder: %s", e)
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
                context.logger.error("List %s not found in database", list_id)
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
                    # Set the directory title in Kodi using proper window property API
                    window = xbmcgui.Window(10025)  # Video window
                    window.setProperty('FolderName', directory_title)
                    self.logger.debug("Set directory title: '%s'", directory_title)
                except Exception as e:
                    self.logger.debug("Could not set directory title: %s", e)

            # Add Tools & Options using centralized builder with visibility check
            breadcrumb_text, description_prefix = self.breadcrumb_helper.get_tools_breadcrumb_formatted("show_list", {"list_id": list_id}, query_manager)
            
            tools_menu_dict = self.breadcrumb_helper.build_tools_menu_item(
                base_url=context.base_url,
                list_type='user_list',
                breadcrumb_text=breadcrumb_text,
                description_text=description_prefix + "Tools and options for this list",
                list_id=list_id
            )
            
            # Only add if visibility setting allows it
            if tools_menu_dict:
                tools_item = xbmcgui.ListItem(label=tools_menu_dict['label'], offscreen=True)
                self._set_listitem_plot(tools_item, tools_menu_dict.get('description', ''))
                tools_item.setProperty('IsPlayable', 'false')
                tools_item.setArt({'icon': tools_menu_dict['icon'], 'thumb': tools_menu_dict['icon']})

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    tools_menu_dict['url'],
                    tools_item,
                    tools_menu_dict['is_folder']
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

                context_menu = build_search_history_list_context_menu(context, list_id, name)

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
        dialog_service = get_dialog_service(logger_name='lib.ui.lists_handler._show_empty_lists_menu')
        
        if dialog_service.yesno(
            L(30136), # "LibraryGenie"
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
            
            dialog_service = get_dialog_service(logger_name='lib.ui.lists_handler.quick_add_context')

            if not default_list_id:
                dialog_service.show_warning("No default list configured")
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
            if result:
                # Get list name for notification
                list_info = query_manager.get_list_by_id(default_list_id)
                list_name = list_info.get('name', 'Default List') if list_info else 'Default List'

                dialog_service.show_success(f"Added '{title}' to {list_name}")
                return True
            else:
                dialog_service.show_error(f"Failed to add '{title}' to list")
                return False

        except Exception as e:
            context.logger.error("Error quick adding to list from context: %s", e)
            dialog_service = get_dialog_service(logger_name='lib.ui.lists_handler.quick_add_context')
            dialog_service.show_error("Quick add failed")
            return False

    def add_external_item_to_list(self, context: PluginContext) -> bool:
        """Handle adding external/plugin item to a list"""
        try:
            # Extract external item data from URL parameters
            external_data = {}
            for key, value in context.get_params().items():
                if key not in ('action', 'external_item'):
                    external_data[key] = value

            # Get title from either 'title' or 'name' parameter
            title = external_data.get('title') or external_data.get('name')
            if not title:
                context.logger.error("No title or name found for external item")
                return False
            
            # Ensure title is set for downstream processing
            external_data['title'] = title

            # Convert to format expected by add_to_list system
            # Check if this is a bookmark and set appropriate metadata
            is_bookmark = external_data.get('type') == 'bookmark'
            
            # Create stable ID for consistent deduplication across sessions
            import hashlib
            # Use 'url' field from context menu or 'file_path' if already processed
            id_source = external_data.get('url') or external_data.get('file_path', external_data['title'])
            stable_id = hashlib.sha1(id_source.encode('utf-8')).hexdigest()[:16]
            
            # Ensure file_path is set for bookmark navigation (using 'url' from context)
            if not external_data.get('file_path') and external_data.get('url'):
                external_data['file_path'] = external_data['url']
            
            # Determine database-compatible media type
            if is_bookmark:
                # Bookmarks must use 'movie' for database compatibility
                db_media_type = 'movie'
            else:
                # For non-bookmarks, check if it's an episode or default to movie
                if (external_data.get('season') is not None and 
                    external_data.get('episode') is not None):
                    db_media_type = 'episode'
                else:
                    db_media_type = external_data.get('media_type', 'movie')
                    # Ensure only valid types reach database
                    if db_media_type not in ('movie', 'episode'):
                        db_media_type = 'movie'
            
            media_item = {
                'id': f"external_{stable_id}",
                'title': external_data['title'],
                'media_type': db_media_type,
                'source': 'external'
            }
            
            # Add bookmark-specific properties for proper navigation
            if is_bookmark:
                media_item.update({
                    'type': 'bookmark',
                    'mediatype': 'folder',
                    'is_folder': True
                })

            # Copy over all the gathered metadata
            for key in ['originaltitle', 'year', 'plot', 'rating', 'votes', 'genre',
                       'director', 'studio', 'country', 'mpaa', 'runtime', 'premiered',
                       'playcount', 'lastplayed', 'poster', 'fanart', 'thumb',
                       'banner', 'clearlogo', 'imdbnumber', 'file_path']:
                if key in external_data:
                    media_item[key] = external_data[key]
            
            # Ensure the bookmark URL is stored in the play field for navigation
            if is_bookmark and external_data.get('url'):
                media_item['play'] = external_data['url']
                media_item['file_path'] = external_data['url']

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

            # Check if list_id is provided (for direct addition, e.g., from context menu)
            target_list_id = context.get_param('list_id')
            dialog_service = get_dialog_service(logger_name='lib.ui.lists_handler.add_external_item_to_list')
            
            if target_list_id:
                # Direct addition to specified list
                try:
                    selected_list_id = int(target_list_id)
                    # Verify the list exists
                    list_info = query_manager.get_list_by_id(selected_list_id)
                    if not list_info:
                        dialog_service.show_error("Target list not found") # Localize this string
                        return False
                    selected_list_name = list_info.get('name', 'Unknown List')
                except (ValueError, TypeError):
                    dialog_service.show_error("Invalid list ID") # Localize this string
                    return False
            else:
                # No list_id provided, show selection dialog
                # Get all available lists
                all_lists = query_manager.get_all_lists_with_folders()
                if not all_lists:
                    # Offer to create a new list
                    if dialog_service.yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
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
                    dialog_service.show_warning("No lists available") # Localize this string
                    return False

                # Show list selection dialog
                selected_index = dialog_service.select(
                    f"Add '{media_item['title']}' to list:", # Localize this string
                    list_options
                )

                if selected_index < 0:
                    return False  # User cancelled

                selected_list_id = int(list_ids[selected_index])  # Ensure integer
                selected_list_name = list_options[selected_index]

            # Add the external item to the selected list
            # Use direct database insertion for external items since add_item_to_list is for library items only
            try:
                with query_manager.connection_manager.transaction() as conn:
                    # Create complete media_data for external item
                    from lib.utils.kodi_version import get_kodi_major_version
                    import json
                    
                    # Use the standard add_item_to_list method and then update with bookmark data
                    result = query_manager.add_item_to_list(
                        list_id=selected_list_id,
                        title=media_item['title'],
                        year=media_item.get('year'),
                        imdb_id=media_item.get('imdbnumber'),
                        tmdb_id=media_item.get('tmdb_id'),
                        kodi_id=media_item.get('kodi_id'),
                        art_data=media_item.get('art_data', {}),
                        tvshowtitle=media_item.get('tvshowtitle'),
                        season=media_item.get('season'),
                        episode=media_item.get('episode'),
                        aired=media_item.get('aired')
                    )
                    
                    # If successful, update the media item to store the bookmark URL
                    if result and result.get('success') and result.get('media_item_id'):
                        media_item_id = result['media_item_id']
                        bookmark_url = external_data.get('url', '')
                        
                        # Update the media item to include bookmark data
                        conn.execute("""
                            UPDATE media_items 
                            SET play = ?, file_path = ?, source = 'bookmark', plot = ?
                            WHERE id = ?
                        """, [bookmark_url, bookmark_url, f"Bookmark: {media_item['title']}", media_item_id])
                
            except Exception as e:
                context.logger.error(f"Exception during bookmark save: {e}")
                result = {'success': False}
            
            if not result:
                result = {'success': False}
            success = result is not None and result.get("success", False)

            if success:
                dialog_service.show_success(f"Added '{media_item['title']}' to '{selected_list_name}'") # Localize this string
                # Refresh container to show changes
                import xbmc
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                dialog_service.show_error("Failed to add item to list") # Localize this string
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
                dialog_service = get_dialog_service(logger_name='lib.ui.lists_handler.remove_library_item_from_list')
                dialog_service.show_warning("Item not found in list")
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
    
    def _compute_full_art_dict(self, item_info: Dict[str, Any], item_type: str) -> Optional[Dict[str, str]]:
        """
        Get custom artwork dictionary for cache. Resource fallbacks are NOT computed here
        (they're computed at render time instead).
        
        Args:
            item_info: Folder or list info dict from database
            item_type: 'folder' or 'list'
            
        Returns:
            Custom art dictionary if available, None otherwise
        """
        import json
        
        # Check if item has custom art_data (from import)
        art_data = item_info.get('art_data')
        if art_data:
            # Parse if it's a JSON string
            if isinstance(art_data, str):
                try:
                    art_data = json.loads(art_data)
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.error("Failed to parse art_data JSON for %s: %s", item_type, e)
                    return None
            
            # If we have valid custom art, return it
            if art_data and isinstance(art_data, dict):
                self.logger.debug("Cached custom art_data for %s: %d art types", item_type, len(art_data))
                return art_data
        
        # No custom art - return None so ultra-fast rendering can apply resource fallbacks
        return None
    
    def _build_processed_menu_items(self, context: 'PluginContext', all_lists: List[Dict], all_folders: List[Dict], query_manager=None) -> List[Dict[str, Any]]:
        """Build processed menu items with business logic applied - for schema v4 cache"""
        menu_items = []
        
        # Determine breadcrumb context
        current_folder_id = context.get_param('folder_id')
        if current_folder_id:
            breadcrumb_params = {'folder_id': current_folder_id}
            breadcrumb_action = 'show_folder'
            tools_url = context.build_url('show_list_tools', list_type='lists_main', folder_id=current_folder_id)
        else:
            breadcrumb_params = {}
            breadcrumb_action = 'lists'
            tools_url = context.build_url('show_list_tools', list_type='lists_main')

        # Add Tools & Options first
        breadcrumb_text, description_prefix = self.breadcrumb_helper.get_tools_breadcrumb_formatted(breadcrumb_action, breadcrumb_params, query_manager)
        tools_label = breadcrumb_text or 'Lists'
        tools_description = f"{description_prefix or ''}Search, Favorites, Import/Export & Settings"

        menu_items.append({
            'label': f"Tools & Options • {tools_label}",
            'url': tools_url,
            'is_folder': True,
            'icon': "DefaultAddonProgram.png",
            'description': tools_description
        })

        # Handle Kodi Favorites integration
        from lib.config.config_manager import get_config
        config = get_config()
        favorites_enabled = config.get_bool('favorites_integration_enabled', False)
        kodi_favorites_item = None

        for item in all_lists:
            if item.get('name') == 'Kodi Favorites':
                kodi_favorites_item = item
                break

        # Add Kodi Favorites first (if enabled and exists)
        if favorites_enabled and kodi_favorites_item:
            list_id = kodi_favorites_item.get('id')
            name = kodi_favorites_item.get('name', 'Kodi Favorites')
            description = kodi_favorites_item.get('description', '')

            context_menu = build_kodi_favorites_context_menu(context, list_id, name)

            menu_items.append({
                'label': name,
                'url': context.build_url('show_list', list_id=list_id),
                'is_folder': True,
                'description': description,
                'icon': "DefaultPlaylist.png",
                'context_menu': context_menu
            })

        # Add folders (excluding Search History)
        for folder_info in all_folders:
            folder_id = folder_info['id']
            folder_name = folder_info['name']

            # Skip the reserved "Search History" folder
            if folder_name == 'Search History':
                continue

            context_menu = build_folder_context_menu(context, folder_id, folder_name)

            folder_item = {
                'label': folder_name,
                'url': context.build_url('show_folder', folder_id=folder_id),
                'is_folder': True,
                'description': f"Folder",
                'context_menu': context_menu
            }
            
            # Compute and include full art dictionary (custom or resource fallbacks)
            folder_item['art_data'] = self._compute_full_art_dict(folder_info, 'folder')
            
            # Include import status if available
            if 'is_import_sourced' in folder_info:
                folder_item['is_import_sourced'] = folder_info['is_import_sourced']
            
            menu_items.append(folder_item)

        # Add standalone lists (excluding Kodi Favorites as it's already added)
        standalone_lists = [item for item in all_lists if (not item.get('folder_name') or item.get('folder_name') == 'Root') and item.get('name') != 'Kodi Favorites']

        for list_item in standalone_lists:
            list_id = list_item.get('id')
            name = list_item.get('name', 'Unnamed List')
            description = list_item.get('description', '')

            context_menu = build_list_context_menu(context, list_id, name)

            list_cache_item = {
                'label': name,
                'url': context.build_url('show_list', list_id=list_id),
                'is_folder': True,
                'description': description,
                'icon': "DefaultPlaylist.png",
                'context_menu': context_menu
            }
            
            # Compute and include full art dictionary (custom or resource fallbacks)
            list_cache_item['art_data'] = self._compute_full_art_dict(list_item, 'list')
            
            # Include import status if available
            if 'is_import_sourced' in list_item:
                list_cache_item['is_import_sourced'] = list_item['is_import_sourced']
            
            menu_items.append(list_cache_item)

        return menu_items