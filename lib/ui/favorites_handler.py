#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Handler
Handles Kodi favorites integration and management
"""

import xbmcplugin
import xbmcgui
from typing import List, Dict, Any
from .plugin_context import PluginContext
from .response_types import DirectoryResponse, DialogResponse
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
            self.logger.info(f"Found {len(favorites)} favorites to display")

            menu_items = []

            # Get last scan info for display
            last_scan_info = favorites_manager._get_last_scan_info_for_display()
            scan_label = "[COLOR yellow]🔄 Scan Favorites[/COLOR]"
            
            if last_scan_info:
                # Calculate time since last scan
                from datetime import datetime
                try:
                    last_scan_time = datetime.fromisoformat(last_scan_info['created_at'])
                    current_time = datetime.now()
                    time_diff = current_time - last_scan_time
                    
                    if time_diff.total_seconds() < 60:
                        time_ago = "just now"
                    elif time_diff.total_seconds() < 3600:  # Less than 1 hour
                        minutes = int(time_diff.total_seconds() / 60)
                        time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    elif time_diff.total_seconds() < 86400:  # Less than 1 day
                        hours = int(time_diff.total_seconds() / 3600)
                        time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
                    else:  # 1 or more days
                        days = int(time_diff.total_seconds() / 86400)
                        time_ago = f"{days} day{'s' if days != 1 else ''} ago"
                    
                    scan_label = f"[COLOR yellow]🔄 Scan Favorites[/COLOR] [COLOR gray]({time_ago})[/COLOR]"
                except Exception as e:
                    context.logger.debug(f"Could not parse last scan time: {e}")

            # Add scan favorites option at the top
            menu_items.append({
                'label': scan_label,
                'url': context.build_url('scan_favorites_execute'),
                'is_folder': True,
                'icon': "DefaultAddSource.png",
                'description': "Scan Kodi favorites file for changes"
            })

            favorites_items = favorites  # No conversion needed - data is already in standard list format

            if not favorites_items:
                # No favorites found
                empty_item = xbmcgui.ListItem(label="[COLOR gray]No favorites found[/COLOR]")
                empty_item.setInfo('video', {'plot': 'No Kodi favorites found or none mapped to library'})
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )
                # Build directory items for menu options if no favorites are displayed
                for item in menu_items:
                    list_item = xbmcgui.ListItem(label=item['label'])

                    if 'description' in item:
                        list_item.setInfo('video', {'plot': item['description']})

                    if 'icon' in item:
                        list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

                    xbmcplugin.addDirectoryItem(
                        context.addon_handle,
                        item['url'],
                        list_item,
                        item['is_folder']
                    )

                # Set content type and finish directory
                xbmcplugin.setContent(context.addon_handle, 'movies')
                xbmcplugin.endOfDirectory(
                    context.addon_handle,
                    succeeded=True,
                    updateListing=False,
                    cacheToDisc=True
                )
            else:
                # First add the Sync Favorites menu option at the top
                for item in menu_items:
                    list_item = xbmcgui.ListItem(label=item['label'])

                    if 'description' in item:
                        list_item.setInfo('video', {'plot': item['description']})

                    if 'icon' in item:
                        list_item.setArt({'icon': item['icon'], 'thumb': item['icon']})

                    xbmcplugin.addDirectoryItem(
                        context.addon_handle,
                        item['url'],
                        list_item,
                        item['is_folder']
                    )

                # Then use existing list building infrastructure for favorites
                context.logger.info(f"Using ListItemRenderer to build {len(favorites_items)} favorites")

                # Add context menu callback for removing from favorites
                def add_favorites_context_menu(listitem, item):
                    """Add favorites-specific context menu items"""
                    try:
                        context_menu = []
                        # Use the correct ID field - favorites use 'id' or 'media_item_id'
                        item_id = item.get('id') or item.get('media_item_id') or item.get('kodi_id', '')
                        context_menu.append((
                            "Remove from Favorites",
                            f"RunPlugin({context.build_url('remove_from_favorites', item_id=item_id)})"
                        ))
                        
                        # Also add "Add to List" option for favorites
                        if item.get('imdb_id'):
                            context_menu.append((
                                "Add to List",
                                f"RunPlugin({context.build_url('add_to_list_menu', media_item_id=item.get('media_item_id') or item.get('id'))})"
                            ))
                        
                        listitem.addContextMenuItems(context_menu)
                    except Exception as e:
                        context.logger.warning(f"Failed to add favorites context menu: {e}")

                # Use the existing renderer with our context menu callback
                from .listitem_renderer import get_listitem_renderer
                renderer = get_listitem_renderer(context.addon_handle, context.addon.getAddonInfo('id'))

                success = renderer.render_media_items(
                    favorites_items,
                    content_type="movies",
                    context_menu_callback=add_favorites_context_menu
                )

                # Return based on renderer success
                return DirectoryResponse(
                    items=favorites_items,
                    success=success,
                    content_type="movies"
                )

        except Exception as e:
            self.logger.error(f"Error in show_favorites_menu: {e}")
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

            if result.get("success"):
                message = (
                    f"Favorites scan completed!\n"
                    f"Found: {result.get('items_found', 0)} favorites\n"
                    f"Mapped: {result.get('items_mapped', 0)} to library\n"
                    f"Added: {result.get('items_added', 0)} new\n"
                    f"Updated: {result.get('items_updated', 0)} existing"
                )

                return DialogResponse(
                    success=True,
                    message="Favorites scanned successfully",
                    refresh_needed=True
                )
            else:
                error_msg = result.get("message", "Unknown error occurred")
                return DialogResponse(
                    success=False,
                    message=f"Scan failed: {error_msg}"
                )

        except Exception as e:
            self.logger.error(f"Error scanning favorites: {e}")
            return DialogResponse(
                success=False,
                message="Error scanning favorites"
            )

    def add_favorite_to_list(self, context: PluginContext, imdb_id: str) -> DialogResponse:
        """Handle adding a favorite to a user list"""
        try:
            self.logger.info(f"Adding favorite with IMDb ID {imdb_id} to list")

            # Get available lists
            query_manager = context.query_manager
            if not query_manager:
                return DialogResponse(
                    success=False,
                    message="Database error"
                )

            all_lists = query_manager.get_all_lists()

            # Filter out special lists like "Kodi Favorites"
            user_lists = [lst for lst in all_lists if lst.get('name') != 'Kodi Favorites']

            if not user_lists:
                # No lists available, offer to create one
                if xbmcgui.Dialog().yesno(
                    context.addon.getLocalizedString(35002),
                    "No lists found. Create a new list first?"
                ):
                    # Redirect to create list
                    from .lists_handler import ListsHandler
                    lists_handler = ListsHandler()
                    return lists_handler.create_list(context)
                else:
                    return DialogResponse(success=False)

            # Show list selection dialog
            list_names = [lst['name'] for lst in user_lists]
            selected_index = xbmcgui.Dialog().select("Select list:", list_names)

            if selected_index < 0:
                self.logger.info("User cancelled list selection")
                return DialogResponse(success=False)

            selected_list = user_lists[selected_index]

            # Add item to the selected list
            from lib.data.list_library_manager import get_list_library_manager
            list_manager = get_list_library_manager()

            result = list_manager.add_to_list_by_imdb(selected_list['id'], imdb_id)

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
            self.logger.error(f"Error adding favorite to list: {e}")
            return DialogResponse(
                success=False,
                message="Error adding favorite to list"
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