#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Handler
Handles Kodi favorites integration and management
"""

import xbmcplugin
import xbmcgui
from datetime import datetime
from typing import Dict, Any, List
from .plugin_context import PluginContext
from .response_types import DirectoryResponse, DialogResponse
from .localization import L
from ..utils.logger import get_logger


class FavoritesHandler:
    """Handles Kodi favorites operations"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def show_favorites_menu(self, context: PluginContext) -> DirectoryResponse:
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

            # Show breadcrumb notification for Kodi Favorites
            from .menu_builder import MenuBuilder
            menu_builder = MenuBuilder()
            try:
                menu_builder._add_breadcrumb_notification("Kodi Favorites")
                context.logger.debug("FAVORITES HANDLER: Showed breadcrumb notification: 'Kodi Favorites'")
            except Exception as e:
                context.logger.error(f"FAVORITES HANDLER: Failed to show breadcrumb notification: {e}")

            menu_items = []

            # Tools & Options removed - Kodi Favorites now accessed as regular list

            favorites_items = favorites  # No conversion needed - data is already in standard list format

            if not favorites_items:
                # No favorites found - show empty message
                # Add empty state message
                empty_item = xbmcgui.ListItem(label="[COLOR gray]No favorites found[/COLOR]")
                empty_item.setInfo('video', {'plot': 'No Kodi favorites found or none mapped to library.'})
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )

                # Set content type and finish directory (use default for empty)
                xbmcplugin.setContent(context.addon_handle, 'movies')
                xbmcplugin.endOfDirectory(
                    context.addon_handle,
                    succeeded=True,
                    updateListing=False,
                    cacheToDisc=True
                )

                return DirectoryResponse(
                    items=[],
                    success=True,
                    content_type="movies"
                )
            else:
                # Use existing list building infrastructure for favorites
                context.logger.info(f"Using ListItemRenderer to build {len(favorites_items)} favorites")

                # Get query manager for content type detection
                from lib.data.query_manager import get_query_manager
                query_manager = get_query_manager()
                
                # Detect appropriate content type based on favorites contents
                detected_content_type = query_manager.detect_content_type(favorites_items)
                context.logger.debug(f"Detected content type: {detected_content_type} for {len(favorites_items)} favorites")

                # Context menus now handled by global context.py

                # Build favorites items
                from .listitem_renderer import get_listitem_renderer
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
                    navigate_to_favorites=True
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
                if xbmcgui.Dialog().yesno(
                    L(35002),  # "LibraryGenie"
                    L(36071),  # "No lists found. Create a new list first?"
                    "",
                    nolabel=L(36003),  # "Cancel"
                    yeslabel=L(37018)   # "Create New List"
                ):
                    # Redirect to create list
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    return lists_handler.create_list(context)
                else:
                    return DialogResponse(success=False)

            # Show list selection dialog
            list_names = [lst['name'] for lst in user_lists]
            selected_index = xbmcgui.Dialog().select(L(31100), list_names)  # "Select a list"

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
            dialog = xbmcgui.Dialog()
            default_name = f"Kodi Favorites Copy - {datetime.now().strftime('%Y-%m-%d')}"
            new_list_name = dialog.input(L(30590), default_name)  # "Enter list name"

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

            # Ask user if they want to place it in a folder
            folder_names = [L(36031)] + [str(f["name"]) for f in all_folders]  # "[Root Level]"
            selected_folder_index = dialog.select(L(36029), list(folder_names))  # "Select destination folder:"

            if selected_folder_index < 0:
                self.logger.info("User cancelled folder selection")
                return DialogResponse(success=False)

            folder_id = None
            if selected_folder_index > 0:  # Not root level
                folder_id = all_folders[selected_folder_index - 1]["id"]

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
            self.logger.error(f"Error saving favorites as list: {e}")
            return DialogResponse(
                success=False,
                message="Error saving favorites as list"
            )

    def show_favorites_tools(self, context: PluginContext) -> DialogResponse:
        """Show Tools & Options modal for Kodi favorites"""
        try:
            self.logger.info("Showing favorites tools & options")

            # Use the modular tools handler
            from .tools_handler import ToolsHandler
            tools_handler = ToolsHandler()
            return tools_handler.show_list_tools(context, "favorites")

        except Exception as e:
            self.logger.error(f"Error showing favorites tools: {e}")
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
                    # Navigate back to favorites view after successful scan
                    import xbmc
                    xbmc.executebuiltin(f'Container.Update({context.build_url("kodi_favorites")},replace)')
                    # End directory properly
                    import xbmcplugin
                    xbmcplugin.endOfDirectory(context.addon_handle, succeeded=True)
                    return

                if hasattr(response, 'refresh_needed') and response.refresh_needed:
                    # Refresh the container to show updated favorites
                    import xbmc
                    xbmc.executebuiltin('Container.Refresh')

                if response.message:
                    import xbmcgui
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )
            elif isinstance(response, DialogResponse):
                # Show error message
                import xbmcgui
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message or "Scan failed",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )

        except Exception as e:
            self.logger.error(f"Error in scan favorites handler: {e}")
            import xbmcgui
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Error scanning favorites",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

    def handle_save_favorites_as(self, context: PluginContext) -> None:
        """Handle save favorites as action with navigation"""
        try:
            response = self.save_favorites_as(context)

            if isinstance(response, DialogResponse) and response.success:
                import xbmcgui
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    response.message or "Favorites saved as new list",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )

                # Optionally refresh to show new list
                if hasattr(response, 'refresh_needed') and response.refresh_needed:
                    import xbmc
                    xbmc.executebuiltin('Container.Refresh')

            elif isinstance(response, DialogResponse):
                if response.message:
                    import xbmcgui
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        response.message,
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )

        except Exception as e:
            self.logger.error(f"Error in save favorites as handler: {e}")
            import xbmcgui
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Error saving favorites",
                xbmcgui.NOTIFICATION_ERROR,
                3000
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
                empty_item = xbmcgui.ListItem(label="No favorites found")
                self.plugin_context.add_item(
                    url="plugin://plugin.video.librarygenie/?action=empty",
                    listitem=empty_item,
                    isFolder=False
                )
                return

            self.logger.debug(f"Rendering {len(favorites)} favorites using enhanced data")

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
                    media_item = self.query_manager.get_media_item_by_id(fav['media_item_id'])
                    if media_item:
                        # Use enhanced media_items data - no JSON RPC calls needed
                        listitem, url = self.listitem_builder.build_media_listitem(media_item)
                    else:
                        # Fallback for missing media item
                        listitem, url = self._build_unmapped_favorite_item(fav)

                    # Add to response
                    self.plugin_context.add_item(
                        url=url,
                        listitem=listitem,
                        isFolder=False
                    )

                except Exception as e:
                    self.logger.error(f"Failed to render mapped favorite: {e}")
                    continue

            # Render unmapped favorites
            for fav in unmapped_favorites:
                try:
                    listitem, url = self._build_unmapped_favorite_item(fav)
                    self.plugin_context.add_item(
                        url=url,
                        listitem=listitem,
                        isFolder=False
                    )
                except Exception as e:
                    self.logger.error(f"Failed to render unmapped favorite: {e}")
                    continue

            # Set content type
            self.plugin_context.set_content_type('files')

            self.logger.debug(f"Successfully rendered {len(favorites)} favorites")

        except Exception as e:
            self.logger.error(f"Failed to render favorites list: {e}")