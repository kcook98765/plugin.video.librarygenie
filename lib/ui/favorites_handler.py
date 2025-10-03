#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Handler
Handles Kodi favorites integration and management
"""

import xbmcplugin
import xbmcgui
from datetime import datetime
from typing import Dict, Any, List, Optional
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DirectoryResponse, DialogResponse
from lib.ui.localization import L
from lib.utils.kodi_log import get_kodi_logger
# Error handling now consolidated in DialogService
from lib.ui.dialog_service import get_dialog_service


class FavoritesHandler:
    """Handles Kodi favorites operations"""

    def __init__(self, context: Optional[PluginContext] = None):
        self.logger = get_kodi_logger('lib.ui.favorites_handler')
        # Unified dialog service handles both UI interactions and error handling
        self.dialog_service = get_dialog_service('lib.ui.favorites_handler')
        
        # Initialize context and related components
        self.plugin_context = context
        if context:
            self.query_manager = context.query_manager
            # Lazy load listitem_builder when needed
            self._listitem_builder = None
        else:
            self.query_manager = None
            self._listitem_builder = None

    def _set_listitem_plot(self, list_item: xbmcgui.ListItem, plot: str):
        """Set plot metadata in version-compatible way to avoid v21 setInfo() deprecation warnings"""
        from lib.utils.kodi_version import get_kodi_major_version
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

    @property
    def listitem_builder(self):
        """Get listitem builder singleton (lazy loaded)"""
        if self._listitem_builder is None and self.plugin_context:
            from lib.ui.listitem_renderer import get_listitem_renderer
            self._listitem_builder = get_listitem_renderer(
                self.plugin_context.addon_handle,
                self.plugin_context.addon_id,
                self.plugin_context
            )
        return self._listitem_builder
    
    def _build_unmapped_favorite_item(self, favorite: Dict[str, Any]):
        """Build listitem for unmapped favorite using favorite data"""
        try:
            # Create basic listitem from favorite data
            title = favorite.get('name', 'Unknown Title')
            listitem = xbmcgui.ListItem(label=title, offscreen=True)
            
            # Set basic metadata if available
            if 'plot' in favorite:
                self._set_listitem_plot(listitem, favorite['plot'])
                
            # Set art if available
            art_dict = {}
            if 'thumb' in favorite:
                art_dict['thumb'] = favorite['thumb']
            if 'icon' in favorite:
                art_dict['icon'] = favorite['icon']
            if art_dict:
                listitem.setArt(art_dict)
                
            # Build URL for playback
            url = favorite.get('path', '')
            if not url and self.plugin_context:
                url = self.plugin_context.build_url('play_favorite', favorite_id=favorite.get('id', ''))
            
            return listitem, url
            
        except Exception as e:
            self.logger.error("Error building unmapped favorite item: %s", e)
            # Return basic fallback
            fallback_item = xbmcgui.ListItem(label="Error Loading Item", offscreen=True)
            return fallback_item, ""
    
    def show_favorites_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main Kodi favorites menu"""
        # Update context reference if provided
        if context and not self.plugin_context:
            self.plugin_context = context
            self.query_manager = context.query_manager
        """Show main Kodi favorites menu"""
        try:
            self.logger.info("Displaying Kodi favorites menu")

            # Initialize favorites manager
            favorites_manager = context.favorites_manager
            if not favorites_manager:
                self.logger.error("Failed to get favorites manager")
                return DirectoryResponse(
                    items=[],
                    success=False
                )

            # Get favorites for display
            favorites = favorites_manager.get_mapped_favorites(show_unmapped=True)
            self.logger.info("Found %s favorites to display", len(favorites))

            # Set directory title with breadcrumb context
            from lib.ui.breadcrumb_helper import get_breadcrumb_helper
            breadcrumb_helper = get_breadcrumb_helper()

            directory_title = breadcrumb_helper.get_directory_title_breadcrumb("kodi_favorites", {}, None)
            if directory_title:
                try:
                    # Set the directory title in Kodi using proper window property API
                    window = xbmcgui.Window(10025)  # Video window
                    window.setProperty('FolderName', directory_title)
                    context.logger.debug("Set directory title: '%s'", directory_title)
                except Exception as e:
                    context.logger.debug("Could not set directory title: %s", e)

            # Add Tools & Options with unified breadcrumb approach (if enabled by user)
            from lib.config.config_manager import get_config
            config = get_config()
            show_tools_item = config.get_bool('show_tools_menu_item', True)
            
            if show_tools_item:
                breadcrumb_text, description_text = breadcrumb_helper.get_tools_breadcrumb_formatted("kodi_favorites", {}, None)

                tools_item = xbmcgui.ListItem(label=f"{L(30212)} {breadcrumb_text}", offscreen=True)
                self._set_listitem_plot(tools_item, description_text + "Tools and options for favorites")
                tools_item.setProperty('IsPlayable', 'false')
                tools_item.setArt({'icon': "DefaultAddonProgram.png", 'thumb': "DefaultAddonProgram.png"})

                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('show_list_tools', list_type='favorites'),
                    tools_item,
                    True
                )

            menu_items = []

            favorites_items = favorites  # No conversion needed - data is already in standard list format

            if not favorites_items:
                # No favorites found - show empty message
                # Add empty state message
                empty_item = xbmcgui.ListItem(label=L(32006), offscreen=True)
                self._set_listitem_plot(empty_item, 'No Kodi favorites found or none mapped to library.')
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )

                # Set content type and finish directory using Navigator
                xbmcplugin.setContent(context.addon_handle, 'movies')
                from lib.ui.nav import finish_directory
                finish_directory(
                    context.addon_handle,
                    succeeded=True,
                    update=True
                )

                return DirectoryResponse(
                    items=[],
                    success=True,
                    content_type="movies"
                )
            else:
                # Use existing list building infrastructure for favorites
                context.logger.info("Using ListItemRenderer to build %s favorites", len(favorites_items))

                # Get query manager for content type detection
                from lib.data.query_manager import get_query_manager
                query_manager = get_query_manager()

                # Detect appropriate content type based on favorites contents
                detected_content_type = query_manager.detect_content_type(favorites_items)
                context.logger.debug("Detected content type: %s for %s favorites", detected_content_type, len(favorites_items))

                # Context menus now handled by global context.py

                # Build favorites items
                from lib.ui.listitem_renderer import get_listitem_renderer
                renderer = get_listitem_renderer(context.addon_handle, context.addon.getAddonInfo('id'))

                success = renderer.render_media_items(
                    favorites_items,
                    content_type=detected_content_type,
                    context_menu_callback=None # Context menus are now handled globally
                )

                # Return based on renderer success
                return DirectoryResponse(
                    items=favorites_items,
                    success=success,
                    content_type=detected_content_type
                )

        except Exception as e:
            self.logger.error("Error in show_favorites_menu: %s", e)
            return DirectoryResponse(
                items=[],
                success=False
            )

    def scan_favorites(self, context: PluginContext) -> DialogResponse:
        """Handle scanning Kodi favorites"""
        try:
            self.logger.info("Handling scan favorites request")

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("Scanning Favorites", "Checking favorites file...")
            progress.update(10)

            # Initialize favorites manager
            favorites_manager = context.favorites_manager
            if not favorites_manager:
                progress.close()
                return DialogResponse(
                    success=False,
                    message="Failed to initialize favorites manager"
                )

            progress.update(30, "Scanning favorites...")

            # Perform the scan
            result = favorites_manager.scan_favorites(force_refresh=True)

            progress.update(100, "Scan complete!")
            progress.close()

            if result is None:
                result = {"success": False, "message": "Scan returned no result"}

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message="Favorites scanned successfully",
                )
            else:
                error_msg = result.get("message", "Unknown error occurred")
                return DialogResponse(
                    success=False,
                    message=f"Scan failed: {error_msg}"
                )

        except Exception as e:
            self.logger.error("Error scanning favorites: %s", e)
            return DialogResponse(
                success=False,
                message="Error scanning favorites"
            )

    def add_favorite_to_list(self, context: PluginContext, imdb_id: str) -> DialogResponse:
        """Handle adding a favorite to a user list"""
        try:
            self.logger.info("Adding favorite with IMDb ID %s to list", imdb_id)

            # Get available lists
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            all_lists = query_manager.get_all_lists_with_folders()

            # Include all lists including "Kodi Favorites" for user selection
            user_lists = all_lists

            if not user_lists:
                # No lists available, offer to create one
                if self.dialog_service.yesno(
                    L(30136),  # "LibraryGenie"
                    L(30241),  # "No lists found. Create a new list first?"
                    yes_label=L(30367),   # "Create New List"
                    no_label=L(30215)  # "Cancel"
                ):
                    # Redirect to create list
                    from lib.ui.lists_handler import ListsHandler
                    lists_handler = ListsHandler(context)
                    return lists_handler.create_list(context)
                else:
                    return DialogResponse(success=False)

            # Show list selection dialog
            list_names = [lst['name'] for lst in user_lists]
            selected_index = self.dialog_service.select(L(31100), list_names)  # "Select a list"

            if selected_index < 0:
                self.logger.info("User cancelled list selection")
                return DialogResponse(success=False)

            selected_list = user_lists[selected_index]

            # Add item to the selected list
            result = query_manager.add_item_to_list(
                selected_list['id'],
                title="Unknown",  # Will be resolved by IMDb ID
                imdb_id=imdb_id
            )

            if result is None:
                result = {"success": False, "error": "Operation returned no result"}

            if result.get("success"):
                return DialogResponse(
                    success=True,
                    message=f"Added to list: {selected_list['name']}",
                    refresh_needed=False
                )
            elif result.get("error") == "duplicate":
                return DialogResponse(
                    success=False,
                    message=f"Item already in list: {selected_list['name']}"
                )
            else:
                return DialogResponse(
                    success=False,
                    message="Failed to add item to list"
                )

        except Exception as e:
            self.logger.error("Error adding favorite to list: %s", e)
            return DialogResponse(
                success=False,
                message="Error adding favorite to list"
            )

    def save_favorites_as(self, context: PluginContext) -> DialogResponse:
        """Handle saving Kodi favorites as a new list"""
        try:
            self.logger.info("Handling save favorites as request")

            # Get current favorites count
            favorites_manager = context.favorites_manager
            if not favorites_manager:
                return DialogResponse(
                    success=False,
                    message="Failed to initialize favorites manager"
                )

            favorites = favorites_manager.get_mapped_favorites()
            if not favorites:
                return DialogResponse(
                    success=False,
                    message="No mapped favorites found to save"
                )

            # Prompt for new list name
            default_name = f"Kodi Favorites Copy - {datetime.now().strftime('%Y-%m-%d')}"
            new_list_name = self.dialog_service.input(L(30590), default=default_name)  # "Enter list name"

            if not new_list_name or not new_list_name.strip():
                self.logger.info("User cancelled or entered empty list name")
                return DialogResponse(success=False)

            new_list_name = new_list_name.strip()

            # Get available folders for organization
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            all_folders = query_manager.get_all_folders()
            
            # Filter out file-sourced folders
            selectable_folders = [f for f in all_folders if not query_manager.folder_contains_file_sourced_lists(f['id'])]

            # Ask user if they want to place it in a folder
            folder_names = [L(30303)] + [str(f["name"]) for f in selectable_folders]  # "[Root Level]"
            selected_folder_index = self.dialog_service.select(L(30301), list(folder_names))  # "Select destination folder:"

            if selected_folder_index < 0:
                self.logger.info("User cancelled folder selection")
                return DialogResponse(success=False)

            folder_id = None
            if selected_folder_index > 0:  # Not root level
                folder_id = selectable_folders[selected_folder_index - 1]["id"]

            # Create the list using QueryManager
            create_result = query_manager.create_list(new_list_name, "", folder_id)

            if create_result.get("error"):
                error_msg = create_result.get("error", "Failed to create list")
                return DialogResponse(
                    success=False,
                    message=f"Failed to create list: {error_msg}"
                )

            new_list_id = create_result["id"]
            self.logger.info("Created new list '%s' with ID %s", new_list_name, new_list_id)

            # Add all favorites to the new list
            added_count = 0
            failed_count = 0

            for favorite in favorites:
                media_item_id = favorite.get('media_item_id') or favorite.get('id')
                if media_item_id:
                    # Use remove_item_from_list logic but in reverse - add to list
                    result = query_manager.add_library_item_to_list(new_list_id, favorite)
                    if result:
                        added_count += 1
                    else:
                        failed_count += 1
                        self.logger.warning("Failed to add favorite '%s' to new list", favorite.get('title'))
                else:
                    failed_count += 1
                    self.logger.warning("No media_item_id found for favorite '%s'", favorite.get('title'))

            # Prepare result message
            message = f"Created list '{new_list_name}' with {added_count} items"
            if failed_count > 0:
                message += f"\nFailed to add {failed_count} items"

            return DialogResponse(
                success=True,
                message=message,
                refresh_needed=False
            )

        except Exception as e:
            self.logger.error("Error saving favorites as list: %s", e)
            return DialogResponse(
                success=False,
                message="Error saving favorites as list"
            )

    def show_favorites_tools(self, context: PluginContext) -> DialogResponse:
        """Show Tools & Options modal for Kodi favorites"""
        try:
            self.logger.info("Showing favorites tools & options")

            # Use the modular tools handler
            from lib.ui.tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler.show_list_tools(context, "favorites")

        except Exception as e:
            self.logger.error("Error showing favorites tools: %s", e)
            return DialogResponse(
                success=False,
                message="Error showing tools & options"
            )

    def handle_scan_favorites(self, context: PluginContext) -> None:
        """Handle scan favorites action with navigation"""
        try:
            response = self.scan_favorites(context)

            if isinstance(response, DialogResponse) and response.success:
                if hasattr(response, 'navigate_to_favorites') and response.navigate_to_favorites:
                    # OPTION A FIX: Use direct rendering to bypass V22 navigation race condition
                    # This eliminates the Container.Update + finish_directory race condition
                    success = self._render_favorites_directly(context)
                    if success:
                        self.logger.debug("FAVORITES: Successfully displayed favorites using direct rendering")
                        return
                    else:
                        self.logger.warning("FAVORITES: Failed direct rendering, falling back to container refresh")
                        # Fallback to just refreshing instead of navigation
                        import xbmc
                        xbmc.executebuiltin('Container.Refresh')
                        return

                if hasattr(response, 'refresh_needed') and response.refresh_needed:
                    # Refresh the container to show updated favorites
                    import xbmc
                    xbmc.executebuiltin('Container.Refresh')

                if response.message:
                    self.dialog_service.log_and_notify_success(
                        f"Favorites scan completed: {response.message}",
                        response.message,
                        5000
                    )
            elif isinstance(response, DialogResponse):
                # Show error message
                self.dialog_service.log_and_notify_error(
                    f"Favorites scan failed: {response.message or 'Unknown error'}",
                    response.message or "Scan failed",
                    timeout_ms=5000
                )

        except Exception as e:
            self.dialog_service.handle_exception(
                "scan favorites handler",
                e,
                "scanning favorites",
                timeout_ms=3000
            )

    def _render_favorites_directly(self, context: PluginContext) -> bool:
        """Directly render favorites list without Container.Update redirect"""
        try:
            self.logger.debug("FAVORITES: Directly rendering favorites list")

            # Import handler factory and response handler
            from lib.ui.handler_factory import get_handler_factory
            from lib.ui.response_handler import get_response_handler

            factory = get_handler_factory()
            factory.context = context
            response_handler = get_response_handler()

            # Call show_favorites directly to get DirectoryResponse
            directory_response = self.show_favorites_menu(context)

            # Handle the DirectoryResponse
            success = response_handler.handle_directory_response(directory_response, context)

            if success:
                self.logger.debug("FAVORITES: Successfully rendered favorites directly")
                return True
            else:
                self.logger.warning("FAVORITES: Failed to handle directory response")
                return False

        except Exception as e:
            self.logger.error("FAVORITES: Error rendering favorites directly: %s", e)
            import traceback
            self.logger.error("FAVORITES: Direct rendering traceback: %s", traceback.format_exc())
            return False

    def handle_save_favorites_as(self, context: PluginContext) -> None:
        """Handle save favorites as action with navigation"""
        try:
            response = self.save_favorites_as(context)

            if isinstance(response, DialogResponse) and response.success:
                self.dialog_service.log_and_notify_success(
                    f"Favorites saved as new list: {response.message or 'Success'}",
                    response.message or "Favorites saved as new list",
                    5000
                )

                # Optionally refresh to show new list
                if hasattr(response, 'refresh_needed') and response.refresh_needed:
                    import xbmc
                    xbmc.executebuiltin('Container.Refresh')

            elif isinstance(response, DialogResponse):
                if response.message:
                    self.dialog_service.log_and_notify_error(
                        f"Failed to save favorites as new list: {response.message}",
                        response.message,
                        timeout_ms=5000
                    )

        except Exception as e:
            self.dialog_service.handle_exception(
                "save favorites as handler",
                e,
                "saving favorites",
                timeout_ms=3000
            )

    def _convert_favorite_to_list_item_data(self, favorite: Dict[str, Any]) -> Dict[str, Any]:
        """Convert favorite data to list item format with complete metadata"""
        return {
            'id': favorite.get('id'),
            'title': favorite.get('title') or favorite.get('name', 'Unknown Favorite'),
            'year': favorite.get('year'),
            'imdb_id': favorite.get('imdb_id'),
            'tmdb_id': favorite.get('tmdb_id'),
            'kodi_id': favorite.get('kodi_id'),
            'media_type': favorite.get('media_type', 'movie'),
            'plot': favorite.get('plot'),
            'rating': favorite.get('rating'),
            'votes': favorite.get('votes'),
            'mpaa': favorite.get('mpaa'),
            'genre': favorite.get('genre'),
            'director': favorite.get('director'),
            'studio': favorite.get('studio'),
            'country': favorite.get('country'),
            'writer': favorite.get('writer'),
            'cast': favorite.get('cast'),
            'duration': favorite.get('duration'),
            'runtime': favorite.get('runtime'),
            'duration_minutes': favorite.get('duration_minutes'),
            'premiered': favorite.get('premiered'),
            'dateadded': favorite.get('dateadded'),
            'playcount': favorite.get('playcount'),
            'lastplayed': favorite.get('lastplayed'),
            'file_path': favorite.get('file_path'),
            'play': favorite.get('play'),
            'source': favorite.get('source', 'lib'),
            'is_mapped': favorite.get('is_mapped', False),
            'thumb_ref': favorite.get('thumb_ref'),
            'description': favorite.get('plot') or f"Favorite: {favorite.get('original_path', '')}",
            # Artwork - map all available art fields
            'poster': favorite.get('poster'),
            'fanart': favorite.get('fanart'),
            'art': favorite.get('art'),  # JSON art dict
            'thumb': favorite.get('thumb'),
            'banner': favorite.get('banner'),
            'landscape': favorite.get('landscape'),
            'clearlogo': favorite.get('clearlogo'),
            'clearart': favorite.get('clearart'),
            'discart': favorite.get('discart'),
            'icon': favorite.get('icon'),
            # Episode-specific fields
            'tvshowid': favorite.get('tvshowid'),
            'tvshowtitle': favorite.get('tvshowtitle'),
            'showtitle': favorite.get('showtitle'),
            'season': favorite.get('season'),
            'episode': favorite.get('episode'),
            'aired': favorite.get('aired'),
            # Resume information
            'resume': favorite.get('resume', {'position_seconds': 0, 'total_seconds': 0}),
            'resume_position': favorite.get('resume_position', 0),
            'resume_total': favorite.get('resume_total', 0),
            # Additional IDs for compatibility
            'movieid': favorite.get('movieid') or favorite.get('kodi_id'),
            'episodeid': favorite.get('episodeid'),
            'media_item_id': favorite.get('media_item_id')
        }

    def _render_favorites_list(self, favorites: List[Dict[str, Any]]) -> None:
        """Render favorites list efficiently using enhanced media_items data"""
        try:
            if not favorites:
                # Show empty message
                empty_item = xbmcgui.ListItem(label=L(32006), offscreen=True)
                if self.plugin_context:
                    self.plugin_context.add_item(
                        url="plugin://plugin.video.librarygenie/?action=empty",
                        listitem=empty_item,
                        isFolder=False
                    )
                return

            self.logger.debug("Rendering %s favorites using enhanced data", len(favorites))

            # Group favorites by mapping status
            mapped_favorites = []
            unmapped_favorites = []

            for fav in favorites:
                if fav.get('is_mapped') and fav.get('media_item_id'):
                    mapped_favorites.append(fav)
                else:
                    unmapped_favorites.append(fav)

            # Render mapped favorites using enhanced media data
            for fav in mapped_favorites:
                try:
                    # Get enhanced media item data for mapped favorite
                    # Note: get_media_item_by_id method does not exist on QueryManager
                    # Use fallback to basic favorite data
                    media_item = None
                    if media_item:
                        # Use enhanced media_items data - no JSON RPC calls needed
                        # Use available listitem builder method
                        if self.listitem_builder and hasattr(self.listitem_builder, 'build_media_listitem'):
                            listitem, url = self.listitem_builder.build_media_listitem(media_item)
                        else:
                            # Fallback to unmapped item builder
                            listitem, url = self._build_unmapped_favorite_item(fav)
                    else:
                        # Fallback for missing media item
                        listitem, url = self._build_unmapped_favorite_item(fav)

                    # Add to response
                    if self.plugin_context:
                        self.plugin_context.add_item(
                            url=url,
                            listitem=listitem,
                            isFolder=False
                        )

                except Exception as e:
                    self.logger.error("Failed to render mapped favorite: %s", e)
                    continue

            # Render unmapped favorites
            for fav in unmapped_favorites:
                try:
                    listitem, url = self._build_unmapped_favorite_item(fav)
                    if self.plugin_context:
                        self.plugin_context.add_item(
                            url=url,
                            listitem=listitem,
                            isFolder=False
                        )
                except Exception as e:
                    self.logger.error("Failed to render unmapped favorite: %s", e)
                    continue

            # Set content type
            if self.plugin_context:
                self.plugin_context.set_content_type('files')

            self.logger.debug("Successfully rendered %s favorites", len(favorites))

        except Exception as e:
            self.logger.error("Failed to render favorites list: %s", e)