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

            # Add scan favorites option at the top
            menu_items.append({
                'label': "[COLOR yellow]🔄 Scan Favorites[/COLOR]",
                'url': context.build_url('scan_favorites_execute'),
                'is_folder': True,
                'icon': "DefaultAddSource.png",
                'description': "Scan Kodi favorites file for changes"
            })

            if not favorites:
                # No favorites found
                empty_item = xbmcgui.ListItem(label="[COLOR gray]No favorites found[/COLOR]")
                empty_item.setInfo('video', {'plot': 'No Kodi favorites found or none mapped to library'})
                xbmcplugin.addDirectoryItem(
                    context.addon_handle,
                    context.build_url('noop'),
                    empty_item,
                    False
                )
            else:
                # Build favorites items
                from lib.ui.listitem_builder import ListItemBuilder
                builder = ListItemBuilder(context.addon_handle, context.addon.getAddonInfo('id'))

                for favorite in favorites:
                    try:
                        # Build context menu for favorite
                        context_menu = []
                        addon_id = context.addon.getAddonInfo('id')
                        context_menu.append((
                            "Add to List",
                            f"RunPlugin(plugin://{addon_id}/?action=add_to_list_menu&media_item_id={favorite['id']})"
                        ))
                        context_menu.append((
                            "Remove from Favorites",
                            f"RunPlugin(plugin://{addon_id}/?action=remove_from_kodi_favorites&favorite_id={favorite['id']})"
                        ))

                        # Create list item for favorite
                        result = builder._build_single_item(favorite)

                        if result:
                            url, listitem, is_folder = result

                            # Add context menu if we have one
                            if context_menu and listitem:
                                try:
                                    listitem.addContextMenuItems(context_menu)
                                except Exception as e:
                                    self.logger.warning(f"Failed to add context menu: {e}")

                            # Add to directory
                            xbmcplugin.addDirectoryItem(
                                context.addon_handle,
                                url,
                                listitem,
                                is_folder
                            )
                        else:
                            self.logger.error(f"Failed to build item for '{favorite.get('title')}'")
                            continue

                    except Exception as e:
                        self.logger.error(f"Error building favorite item: {e}")
                        continue

            # Build directory items for menu options
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

            return DirectoryResponse(
                items=favorites,
                success=True,
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
        """Convert favorite data to list item format"""
        return {
            'id': favorite.get('id'),
            'title': favorite.get('name', 'Unknown Favorite'),
            'year': favorite.get('year'),
            'imdb_id': favorite.get('imdb_id'),
            'is_mapped': favorite.get('is_mapped', False),
            'thumb_ref': favorite.get('thumb_ref'),
            'description': f"Favorite: {favorite.get('original_path', '')}"
        }