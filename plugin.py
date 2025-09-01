#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Entry Point
Handles plugin URL routing and main menu display
"""

import sys
from urllib.parse import parse_qsl
from typing import Dict, Any

import xbmcaddon
import xbmcplugin
import xbmcgui
import xbmc  # Added for xbmc.executebuiltin

# Import our addon modules
from lib.addon import AddonController
from lib.utils.logger import get_logger
from lib.auth.auth_helper import get_auth_helper
from lib.auth.state import is_authorized

# Import query manager for list operations
from lib.data.query_manager import get_query_manager  # Assuming this path is correct

# Get logger instance
logger = get_logger(__name__)

# Placeholder for global arguments if needed by multiple functions
args: Dict[str, Any] = {}
base_url = ""


def show_main_menu(handle):
    """Show main menu with auth-aware options"""
    addon = xbmcaddon.Addon()

    # Search (always visible)
    search_item = xbmcgui.ListItem(label=addon.getLocalizedString(35014))  # "Search"
    search_url = f"{sys.argv[0]}?action=search"
    xbmcplugin.addDirectoryItem(handle, search_url, search_item, True)

    # Lists (always visible)
    lists_item = xbmcgui.ListItem(label=addon.getLocalizedString(35016))  # "Lists"
    lists_url = f"{sys.argv[0]}?action=lists"
    xbmcplugin.addDirectoryItem(handle, lists_url, lists_item, True)

    # Kodi Favorites (always visible)
    favorites_item = xbmcgui.ListItem(label="Kodi Favorites")
    favorites_url = f"{sys.argv[0]}?action=kodi_favorites"
    xbmcplugin.addDirectoryItem(handle, favorites_url, favorites_item, True)

    # Auth-dependent menu items
    if is_authorized():
        # Sign out (visible only when authorized)
        signout_item = xbmcgui.ListItem(label=addon.getLocalizedString(35027))  # "Sign out"
        signout_url = f"{sys.argv[0]}?action=signout"
        xbmcplugin.addDirectoryItem(handle, signout_url, signout_item, False)

        # Remote features (when authorized)
        remote_lists_item = xbmcgui.ListItem(label=addon.getLocalizedString(35017))  # "Remote Lists"
        remote_lists_url = f"{sys.argv[0]}?action=remote_lists"
        xbmcplugin.addDirectoryItem(handle, remote_lists_url, remote_lists_item, True)
    else:
        # Authorize device (visible only when not authorized)
        auth_item = xbmcgui.ListItem(label=addon.getLocalizedString(35028))  # "Authorize device"
        auth_url = f"{sys.argv[0]}?action=authorize"
        xbmcplugin.addDirectoryItem(handle, auth_url, auth_item, False)

    xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True)


def show_search_menu(handle):
    """Show search interface"""
    try:
        from lib.ui.search_handler import SearchHandler

        search_handler = SearchHandler(handle)
        search_handler.prompt_and_show()
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error importing or using SearchHandler: {e}")
        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            f"Search error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def show_remote_search_menu(handle):
    """Show remote search interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35115))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True)


def show_lists_menu(handle):
    """Show lists management interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35116))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True)


def show_remote_lists_menu(handle):
    """Show remote lists interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35117))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True)


def handle_authorize():
    """Handle device authorization"""
    auth_helper = get_auth_helper()
    auth_helper.start_device_authorization()


def handle_signout():
    """Handle user sign out"""
    from lib.auth.state import clear_tokens

    addon = xbmcaddon.Addon()

    # Confirm sign out
    if xbmcgui.Dialog().yesno(
        addon.getLocalizedString(35029),  # "Sign out"
        addon.getLocalizedString(35030)   # "Are you sure you want to sign out?"
    ):
        if clear_tokens():
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35031),  # "Signed out successfully"
                xbmcgui.NOTIFICATION_INFO
            )
        else:
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35032),  # "Sign out failed"
                xbmcgui.NOTIFICATION_ERROR
            )


def _check_and_trigger_initial_scan():
    """Check if library needs initial scan and trigger if needed"""
    try:
        from lib.library.scanner import get_library_scanner
        from lib.data.migrations import get_migration_manager

        logger = get_logger(__name__)

        # Ensure database is initialized first
        migration_manager = get_migration_manager()
        migration_manager.ensure_initialized()

        # Check if library needs indexing
        scanner = get_library_scanner()
        if not scanner.is_library_indexed():
            logger.info("Library not indexed - triggering initial scan")

            # Run scan in background thread to avoid blocking UI
            import threading

            def run_initial_scan():
                try:
                    result = scanner.perform_full_scan()
                    if result.get("success"):
                        logger.info(f"Initial library scan completed: {result.get('items_added', 0)} movies indexed")
                    else:
                        logger.warning(f"Initial library scan failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Initial library scan thread failed: {e}")

            scan_thread = threading.Thread(target=run_initial_scan)
            scan_thread.daemon = True  # Don't block Kodi shutdown
            scan_thread.start()

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to check/trigger initial scan: {e}")


def handle_lists(addon_handle, base_url):
    """Handle lists menu - Phase 5 implementation"""
    try:
        logger.info("Displaying lists menu")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Database error",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        # Get all user lists and folders
        all_lists = query_manager.get_all_lists_with_folders()
        logger.info(f"Found {len(all_lists)} total lists")

        # Filter out the special "Kodi Favorites" list from the main Lists menu
        user_lists = [item for item in all_lists if item.get('name') != 'Kodi Favorites']
        logger.info(f"Found {len(user_lists)} user lists (excluding Kodi Favorites)")

        # Debug: Check for Search History folder specifically
        search_history_items = [item for item in user_lists if item.get('folder_name') == 'Search History']
        logger.info(f"Found {len(search_history_items)} Search History items: {search_history_items}")

        if not user_lists:
            # No lists exist, offer to create one
            addon = xbmcaddon.Addon()
            if xbmcgui.Dialog().yesno(
                addon.getLocalizedString(35002),
                "No lists found. Create your first list?"
            ):
                handle_create_list()
            return

        # Build menu items for lists and folders
        menu_items = []

        # Add "Create New List" option at the top
        menu_items.append({
            "title": "[COLOR yellow]+ Create New List[/COLOR]",
            "action": "create_list",
            "description": "Create a new list",
            "is_folder": False,
            "icon": "DefaultAddSource.png"
        })

        # Add "Create New Folder" option
        menu_items.append({
            "title": "[COLOR cyan]+ Create New Folder[/COLOR]",
            "action": "create_folder",
            "description": "Create a new folder",
            "is_folder": False,
            "icon": "DefaultFolder.png"
        })

        # Get all existing folders to display as navigable items
        all_folders = query_manager.get_all_folders()

        # Add folders as navigable items
        for folder_info in all_folders:
            folder_id = folder_info['id']
            folder_name = folder_info['name']
            list_count = folder_info['list_count']

            # Check if it's the reserved "Search History" folder
            is_reserved_folder = folder_name == 'Search History'
            folder_context_menu = []

            if not is_reserved_folder:
                folder_context_menu = [
                    (f"Rename Folder '{folder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_folder&folder_id={folder_id})"),
                    (f"Delete Folder '{folder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_folder&folder_id={folder_id})")
                ]

            # Add the folder as a navigable item
            menu_items.append({
                "title": f"[COLOR cyan]📁 {folder_name}[/COLOR]",
                "action": "show_folder",
                "folder_id": folder_id,
                "description": f"Folder with {list_count} lists",
                "is_folder": True,
                "context_menu": folder_context_menu
            })

        # Separate standalone lists (not in any folder)
        standalone_lists = [item for item in user_lists if not item.get('folder_name') or item.get('folder_name') == 'Root']

        # Add standalone lists (not in any folder)
        for list_item in standalone_lists:
            list_id = list_item.get('id')
            name = list_item.get('name', 'Unnamed List')
            description = list_item.get('description', '')
            item_count = list_item.get('item_count', 0)

            menu_items.append({
                "title": f"[COLOR yellow]📋 {name}[/COLOR]",
                "action": "show_list",
                "list_id": list_id,
                "description": description,
                "is_folder": True,
                "icon": "DefaultPlaylist.png",
                "context_menu": [
                    (f"Rename List '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})"),
                    (f"Delete List '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_id})")
                ]
            })

        # Build and display the menu
        from lib.ui.menu_builder import MenuBuilder
        menu_builder = MenuBuilder()
        menu_builder.build_menu(menu_items, addon_handle, base_url)

    except Exception as e:
        logger.error(f"Error in handle_lists: {e}")
        import traceback
        logger.error(f"Lists error traceback: {traceback.format_exc()}")

        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            "Lists error",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_create_list():
    """Handle creating a new list"""
    try:
        logger.info("Handling create list request")

        # Get list name from user
        addon = xbmcaddon.Addon()
        list_name = xbmcgui.Dialog().input(
            "Enter list name:",
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not list_name or not list_name.strip():
            logger.info("User cancelled list creation or entered empty name")
            return

        # Initialize query manager and create list
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        result = query_manager.create_list(list_name.strip())

        if result.get("error"):
            if result["error"] == "duplicate_name":
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    f"List '{list_name}' already exists"
                )
            else:
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    "Failed to create list"
                )
        else:
            logger.info(f"Successfully created list: {list_name}")
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Created list: {list_name}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            # Refresh the lists view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error creating list: {e}")
        import traceback
        logger.error(f"Create list error traceback: {traceback.format_exc()}")


def handle_view_list(addon_handle, base_url):
    """Handle viewing a specific list"""
    try:
        # Parse plugin arguments from sys.argv
        if len(sys.argv) < 3 or not sys.argv[2].startswith('?'):
            logger.error("Invalid arguments received for handle_view_list")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Invalid arguments",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        query_string = sys.argv[2][1:]  # Remove leading '?'
        params = dict(parse_qsl(query_string))  # Use parse_qsl for parsing

        list_id = params.get('list_id')
        if not list_id:
            logger.error("No list_id provided for view_list")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Invalid list ID",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        logger.debug(f"Viewing list {list_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Database error",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        # Get list info
        list_info = query_manager.get_list_by_id(list_id)
        if not list_info:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "List not found"
            )
            return

        # Get list items (already normalized by get_list_items)
        list_items = query_manager.get_list_items(list_id)
        logger.debug(f"Found {len(list_items)} items in list")

        if not list_items:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                f"List '{list_info['name']}' is empty"
            )
            # Ensure directory is ended if list is empty
            xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return

        # Detect content type based on list items
        content_type = query_manager.detect_content_type(list_items)
        logger.debug(f"Detected content type '{content_type}' for list '{list_info['name']}'")

        # Use MenuBuilder instead of ListItemBuilder for list contents to avoid InfoHijack
        from lib.ui.menu_builder import MenuBuilder
        menu_builder = MenuBuilder()

        # Set category for better navigation
        xbmcplugin.setPluginCategory(addon_handle, f"List: {list_info['name']}")

        # Set content type for proper skin support
        xbmcplugin.setContent(addon_handle, content_type)

        # Convert list items to menu items format
        menu_items = []
        for item in list_items:
            # Build display title
            title = item.get('title', 'Unknown')
            year = item.get('year')
            display_title = f"{title} ({year})" if year else title

            # Create context menu for list item
            context_menu = [
                (f"Remove from '{list_info['name']}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={list_id}&item_id={item.get('id')})")
            ]

            # For library items, use on_select action to handle play/info preference
            kodi_id = item.get('kodi_id') or item.get('movieid') or item.get('episodeid')
            if kodi_id:
                # Library item - use on_select action
                menu_item = {
                    "title": display_title,
                    "action": "on_select",
                    "dbtype": item.get('media_type', 'movie'),
                    "dbid": kodi_id,
                    "description": f"Rating: {item.get('rating', 'N/A')} | {item.get('plot', '')[:100]}...",
                    "is_folder": False,
                    "icon": "DefaultMovies.png",
                    "context_menu": context_menu,
                    "movie_data": item  # For enhanced rendering
                }

                # Add episode-specific data for videodb URL construction
                if item.get('media_type') == 'episode':
                    if item.get('tvshowid'):
                        menu_item["tvshowid"] = item['tvshowid']
                    if item.get('season'):
                        menu_item["season"] = item['season']
            else:
                # External item - use plugin URL
                menu_item = {
                    "title": display_title,
                    "action": "play_external",
                    "item_id": item.get('id', ''),
                    "description": f"Rating: {item.get('rating', 'N/A')} | {item.get('plot', '')[:100]}...",
                    "is_folder": False,
                    "icon": "DefaultMovies.png",
                    "context_menu": context_menu,
                    "movie_data": item  # For enhanced rendering
                }

            menu_items.append(menu_item)

        # Build menu using MenuBuilder
        menu_builder.build_menu(menu_items, addon_handle, base_url)
        success = True

        if success:
            logger.debug(f"Successfully built list directory with content_type='{content_type}'")
        else:
            logger.error(f"Failed to build list directory")

        return  # build_directory() already handles endOfDirectory()

    except Exception as e:
        logger.error(f"Error viewing list: {e}")
        import traceback
        logger.error(f"View list error traceback: {traceback.format_exc()}")

        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            "Lists error",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_rename_list():
    """Handle renaming a list"""
    try:
        list_id = args.get('list_id')
        if not list_id:
            logger.error("No list_id provided for rename_list")
            return

        logger.info(f"Renaming list {list_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Get current list info
        list_info = query_manager.get_list_by_id(list_id)
        if not list_info:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "List not found"
            )
            return

        # Get new name from user
        addon = xbmcaddon.Addon()
        new_name = xbmcgui.Dialog().input(
            "Enter new list name:",
            defaultt=list_info['name'],
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not new_name or not new_name.strip():
            logger.info("User cancelled rename or entered empty name")
            return

        # Rename the list
        result = query_manager.rename_list(list_id, new_name.strip())

        if result.get("error"):
            if result["error"] == "duplicate_name":
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    f"List '{new_name}' already exists"
                )
            else:
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    "Failed to rename list"
                )
        else:
            logger.info(f"Successfully renamed list to: {new_name}")
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Renamed to: {new_name}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            # Refresh the lists view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error renaming list: {e}")
        import traceback
        logger.error(f"Rename list error traceback: {traceback.format_exc()}")


def handle_delete_list():
    """Handle deleting a list"""
    try:
        list_id = args.get('list_id')
        if not list_id:
            logger.error("No list_id provided for delete_list")
            return

        logger.info(f"Deleting list {list_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Get current list info
        list_info = query_manager.get_list_by_id(list_id)
        if not list_info:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "List not found"
            )
            return

        # Confirm deletion
        addon = xbmcaddon.Addon()
        if not xbmcgui.Dialog().yesno(
            addon.getLocalizedString(35002),
            f"Delete list '{list_info['name']}'?",
            f"This will remove {list_info['item_count']} items from the list."
        ):
            logger.info("User cancelled list deletion")
            return

        # Delete the list
        result = query_manager.delete_list(list_id)

        if result.get("error"):
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Failed to delete list"
            )
        else:
            logger.info(f"Successfully deleted list: {list_info['name']}")
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Deleted list: {list_info['name']}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            # Refresh the lists view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error deleting list: {e}")
        import traceback
        logger.error(f"Delete list error traceback: {traceback.format_exc()}")


def handle_create_folder():
    """Handle creating a new folder"""
    try:
        logger.info("Handling create folder request")

        # Get folder name from user
        addon = xbmcaddon.Addon()
        folder_name = xbmcgui.Dialog().input(
            "Enter folder name:",
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not folder_name or not folder_name.strip():
            logger.info("User cancelled folder creation or entered empty name")
            return

        # Initialize query manager and create folder
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Check if folder name is reserved
        if folder_name.strip() == "Search History":
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Cannot create 'Search History' folder. It is a reserved folder."
            )
            return

        result = query_manager.create_folder(folder_name.strip())

        if result.get("error"):
            if result["error"] == "duplicate_name":
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    f"Folder '{folder_name}' already exists"
                )
            else:
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    "Failed to create folder"
                )
        else:
            logger.info(f"Successfully created folder: {folder_name}")
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Created folder: {folder_name}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            # Refresh the lists view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        import traceback
        logger.error(f"Create folder error traceback: {traceback.format_exc()}")


def handle_rename_folder():
    """Handle renaming a folder"""
    try:
        folder_id = args.get('folder_id')  # Assuming folder_id is passed
        if not folder_id:
            logger.error("No folder_id provided for rename_folder")
            return

        logger.info(f"Renaming folder {folder_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Get current folder info
        folder_info = query_manager.get_folder_by_id(folder_id)  # Assuming this method exists
        if not folder_info:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Folder not found"
            )
            return

        # Check if it's the reserved "Search History" folder
        if folder_info['name'] == "Search History":
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Cannot rename the reserved 'Search History' folder."
            )
            return

        # Get new name from user
        addon = xbmcaddon.Addon()
        new_name = xbmcgui.Dialog().input(
            "Enter new folder name:",
            defaultt=folder_info['name'],
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not new_name or not new_name.strip():
            logger.info("User cancelled rename or entered empty name")
            return

        # Rename the folder
        result = query_manager.rename_folder(folder_id, new_name.strip())  # Assuming this method exists

        if result.get("error"):
            if result["error"] == "duplicate_name":
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    f"Folder '{new_name}' already exists"
                )
            else:
                xbmcgui.Dialog().ok(
                    addon.getLocalizedString(35002),
                    "Failed to rename folder"
                )
        else:
            logger.info(f"Successfully renamed folder to: {new_name}")
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Renamed folder to: {new_name}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            # Refresh the lists view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error renaming folder: {e}")
        import traceback
        logger.error(f"Rename folder error traceback: {traceback.format_exc()}")


def handle_delete_folder():
    """Handle deleting a folder"""
    try:
        folder_id = args.get('folder_id')  # Assuming folder_id is passed
        if not folder_id:
            logger.error("No folder_id provided for delete_folder")
            return

        logger.info(f"Deleting folder {folder_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Get current folder info
        folder_info = query_manager.get_folder_by_id(folder_id)  # Assuming this method exists
        if not folder_info:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Folder not found"
            )
            return

        # Check if it's the reserved "Search History" folder
        if folder_info['name'] == "Search History":
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Cannot delete the reserved 'Search History' folder."
            )
            return

        # Confirm deletion
        addon = xbmcaddon.Addon()
        if not xbmcgui.Dialog().yesno(
            addon.getLocalizedString(35002),
            f"Delete folder '{folder_info['name']}'?",
            f"This will remove {folder_info['item_count']} items from the folder."
        ):
            logger.info("User cancelled folder deletion")
            return

        # Delete the folder
        result = query_manager.delete_folder(folder_id)  # Assuming this method exists

        if result.get("error"):
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Failed to delete folder"
            )
        else:
            logger.info(f"Successfully deleted folder: {folder_info['name']}")
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Deleted folder: {folder_info['name']}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            # Refresh the lists view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        import traceback
        logger.error(f"Delete folder error traceback: {traceback.format_exc()}")


def handle_remove_from_list():
    """Handle removing an item from a list"""
    try:
        list_id = args.get('list_id')
        item_id = args.get('item_id')

        if not list_id or not item_id:
            logger.error("Missing list_id or item_id for remove_from_list")
            return

        logger.info(f"Removing item {item_id} from list {list_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Remove the item from the list
        result = query_manager.remove_item_from_list(list_id, item_id)

        if result.get("error"):
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Failed to remove item from list"
            )
        else:
            logger.info(f"Successfully removed item from list")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Item removed from list",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            # Refresh the current view
            xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error removing item from list: {e}")
        import traceback
        logger.error(f"Remove from list error traceback: {traceback.format_exc()}")


def handle_show_folder(addon_handle, base_url):
    """Handle showing the contents of a folder"""
    try:
        # Parse plugin arguments
        if len(sys.argv) < 3 or not sys.argv[2].startswith('?'):
            logger.error("Invalid arguments received for handle_show_folder")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Invalid arguments",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        query_string = sys.argv[2][1:]
        params = dict(parse_qsl(query_string))
        folder_id = params.get('folder_id')

        if not folder_id:
            logger.error("No folder_id provided for show_folder")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Invalid folder ID",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        logger.info(f"Showing contents of folder {folder_id}")

        # Initialize query manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Database error",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        # Get folder info to set category
        folder_info = query_manager.get_folder_by_id(folder_id)
        if not folder_info:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Folder not found"
            )
            return

        xbmcplugin.setPluginCategory(addon_handle, f"Folder: {folder_info['name']}")

        # Get all lists within this folder
        folder_lists = query_manager.get_lists_in_folder(folder_id)
        logger.info(f"Found {len(folder_lists)} lists in folder {folder_id}")

        if not folder_lists:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                f"Folder '{folder_info['name']}' is empty."
            )
            xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
            return

        menu_items = []
        # Build menu items for lists within the folder
        for list_item in folder_lists:
            list_id = list_item.get('id')
            name = list_item.get('name', 'Unnamed List')
            description = list_item.get('description', '')

            # Check if it's in Search History folder to prevent deletion
            is_search_history = folder_info['name'] == 'Search History'
            context_menu = []

            if not is_search_history:
                context_menu = [
                    (f"Rename List '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})"),
                    (f"Delete List '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_id})")
                ]

            menu_items.append({
                "title": f"[COLOR yellow]📋 {name}[/COLOR]",
                "action": "show_list",
                "list_id": list_id,
                "description": description,
                "is_folder": True,
                "icon": "DefaultPlaylist.png",
                "context_menu": context_menu
            })

        # Build and display the menu for the folder contents
        from lib.ui.menu_builder import MenuBuilder
        menu_builder = MenuBuilder()
        menu_builder.build_menu(menu_items, addon_handle, base_url)

    except Exception as e:
        logger.error(f"Error showing folder contents: {e}")
        import traceback
        logger.error(f"Show folder error traceback: {traceback.format_exc()}")
        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            "Folder error",
            xbmcgui.NOTIFICATION_ERROR
        )


def _videodb_path(dbtype: str, dbid: int, tvshowid=None, season=None) -> str:
    """Build videodb:// path for Kodi library items"""
    if dbtype == "movie":
        return f'videodb://movies/titles/{dbid}'
    if dbtype == "episode":
        if isinstance(tvshowid, int) and isinstance(season, int):
            return f'videodb://tvshows/titles/{tvshowid}/{season}/{dbid}'
        return f'videodb://episodes/{dbid}'
    return ""


def handle_on_select(params: dict, addon_handle: int):
    """Handle library item selection - play or show info based on user preference"""
    try:
        from lib.config.config_manager import get_select_pref
        import re

        logger.debug(f"=== ON_SELECT HANDLER CALLED ===")
        logger.debug(f"Handling on_select with params: {params}")
        logger.debug(f"Addon handle: {addon_handle}")

        dbtype = params.get("dbtype", "movie")
        dbid = int(params.get("dbid", "0"))
        tvshowid = params.get("tvshowid")
        season = params.get("season")
        tvshowid = int(tvshowid) if tvshowid and str(tvshowid).isdigit() else None
        season = int(season) if season and str(season).isdigit() else None

        vdb = _videodb_path(dbtype, dbid, tvshowid, season)  # must be a videodb:// path
        pref = get_select_pref()  # 'play' or 'info'

        # Parse major Kodi version (19, 20, 21, ...)
        ver_str = xbmc.getInfoLabel('System.BuildVersion')
        try:
            kodi_major = int(re.split(r'[^0-9]', ver_str, 1)[0])
        except Exception:
            kodi_major = 0

        logger.debug(f"on_select: dbtype={dbtype}, dbid={dbid}, videodb_path={vdb}, preference={pref}, kodi_major={kodi_major}")

        if pref == "play":
            logger.info(f"Playing media: {vdb}")
            xbmc.executebuiltin(f'PlayMedia("{vdb}")')
        else:
            if kodi_major <= 19:
                logger.info("Opening DialogVideoInfo for videodb item (Matrix)")
                xbmc.executebuiltin(f'ActivateWindow(DialogVideoInfo,"{vdb}",return)')
            else:
                logger.debug("Opening info dialog for focused item (Nexus+)")
                xbmc.executebuiltin('Action(Info)')
                # Optionally force DB context on v20+:
                # xbmc.executebuiltin(f'ActivateWindow(VideoInformation,"{vdb}",return)')

        # Don’t render a directory for this action
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error in handle_on_select: {e}")
        import traceback
        logger.error(f"on_select error traceback: {traceback.format_exc()}")
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass


def handle_kodi_favorites(addon_handle, base_url):
    """Handle Kodi favorites menu - show as unified list"""
    try:
        logger.info("Displaying Kodi favorites as unified list")

        # Initialize favorites manager early to avoid UnboundLocalError
        from lib.kodi.favorites_manager import get_phase4_favorites_manager
        favorites_manager = get_phase4_favorites_manager()

        # Initialize query manager to access the Kodi Favorites list
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                "Database error",
                xbmcgui.NOTIFICATION_ERROR
            )
            return

        # Get the Kodi Favorites list
        kodi_list = query_manager.get_list_by_name('Kodi Favorites')
        if not kodi_list:
            # Show scan option if no Kodi Favorites list exists
            addon = xbmcaddon.Addon()
            if xbmcgui.Dialog().yesno(
                addon.getLocalizedString(35002),
                "No Kodi favorites found. Scan for favorites?"
            ):
                # Trigger scan
                result = favorites_manager.scan_favorites(force_refresh=True)

                if result.get("success"):
                    items_found = result.get("items_found", 0)
                    items_mapped = result.get("items_mapped", 0)

                    xbmcgui.Dialog().notification(
                        addon.getLocalizedString(35002),
                        f"Scanned: {items_mapped}/{items_found} favorites mapped",
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )

                    # Refresh and try again
                    kodi_list = query_manager.get_list_by_name('Kodi Favorites')
                else:
                    xbmcgui.Dialog().notification(
                        addon.getLocalizedString(35002),
                        f"Scan failed: {result.get('message', 'Unknown error')}",
                        xbmcgui.NOTIFICATION_ERROR
                    )

            if not kodi_list:
                xbmcplugin.endOfDirectory(addon_handle, succeeded=True, updateListing=False, cacheToDisc=True)
                return

        # Get the Kodi Favorites list items using the exact same query as normal lists
        list_items = query_manager.get_list_items(kodi_list['id']) if kodi_list else []

        # Set category for proper navigation breadcrumbs
        xbmcplugin.setPluginCategory(addon_handle, "Kodi Favorites")

        # Set content type first
        xbmcplugin.setContent(addon_handle, "movies")

        # Add "Sync Favorites" as the first item - BEFORE any ListItemBuilder processing
        last_scan_info = favorites_manager._get_last_scan_info_for_display()
        time_ago_text = ""
        if last_scan_info:
            last_scan_time = last_scan_info.get('created_at')
            if last_scan_time:
                time_ago = _format_time_ago(last_scan_time)
                time_ago_text = f" (last scan: {time_ago})"

        sync_label = f"[COLOR yellow]🔄 Sync Favorites[/COLOR]{time_ago_text}"
        sync_item = xbmcgui.ListItem(label=sync_label)
        sync_item.setProperty('IsPlayable', 'false')
        plot_text = 'Scan Kodi favorites and update the list with any new favorites found.'
        if last_scan_info:
            items_found = last_scan_info.get('items_found', 0)
            items_mapped = last_scan_info.get('items_mapped', 0)
            plot_text += f' Last scan found {items_mapped}/{items_found} mapped favorites.'
        sync_item.setInfo('video', {'plot': plot_text})
        # Use static artwork that Kodi can resolve, not from URLs that cause artwork extraction
        sync_item.setArt({'icon': 'DefaultAddonService.png', 'thumb': 'DefaultAddonService.png'})
        sync_url = f"RunPlugin({base_url}?action=scan_favorites)"
        xbmcplugin.addDirectoryItem(addon_handle, sync_url, sync_item, False)
        logger.debug(f"KODI FAVORITES: Added 'Sync Favorites' action item with time info: {time_ago_text}")

        if not list_items:
            no_items_item = xbmcgui.ListItem(label="[COLOR gray]No mapped favorites found[/COLOR]")
            no_items_item.setProperty('IsPlayable', 'false')
            no_items_item.setInfo('video', {
                'plot': 'Use "Sync Favorites" above to scan for Kodi favorites that can be mapped to your library.'
            })
            # Use static artwork that Kodi can resolve
            no_items_item.setArt({'icon': 'DefaultAddonNone.png', 'thumb': 'DefaultAddonNone.png'})
            xbmcplugin.addDirectoryItem(addon_handle, "", no_items_item, False)
            logger.debug(f"KODI FAVORITES: Added 'no favorites' info item")

            xbmcplugin.endOfDirectory(addon_handle, succeeded=True)
            return

        # ONLY use ListItemBuilder for the actual favorite media items
        from lib.ui.listitem_builder import ListItemBuilder

        builder = ListItemBuilder(addon_handle, xbmcaddon.Addon().getAddonInfo('id'))

        def favorites_context_menu(listitem, item):
            """Add context menu items for favorite media items"""
            try:
                context_items = []
                item_title = item.get('title', 'Unknown')

                logger.debug(f"FAVORITES CONTEXT: Starting context menu setup for '{item_title}'")

                # Add standard context items for mapped favorites
                kodi_id = item.get('kodi_id')
                if kodi_id:
                    add_url = f"RunPlugin({base_url}?action=add_favorite_to_list&favorite_id={kodi_id})"
                    context_items.append(("Add to List", add_url))
                    logger.debug(f"FAVORITES CONTEXT: Added 'Add to List' -> {add_url}")

                if context_items:
                    listitem.addContextMenuItems(context_items)
                    logger.debug(f"FAVORITES CONTEXT: ✅ Added context menu for '{item_title}'")
                else:
                    logger.warning(f"FAVORITES CONTEXT: No context items to add for '{item_title}'")

            except Exception as e:
                logger.error(f"FAVORITES CONTEXT: Failed to add context menu for '{item.get('title', 'Unknown')}': {e}")
                import traceback
                logger.error(f"FAVORITES CONTEXT: Traceback: {traceback.format_exc()}")

        success = builder.build_directory(list_items, content_type="movies", context_menu_callback=favorites_context_menu)

        if not success:
            logger.error("Failed to build favorites directory")
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)

    except Exception as e:
        logger.error(f"Error in handle_kodi_favorites: {e}")
        import traceback
        logger.error(f"Kodi favorites error traceback: {traceback.format_exc()}")

        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            "Favorites error",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_scan_favorites():
    """Handle scanning favorites"""
    try:
        logger.info("Scanning Kodi favorites")

        from lib.kodi.favorites_manager import get_phase4_favorites_manager
        favorites_manager = get_phase4_favorites_manager()

        # Perform scan
        result = favorites_manager.scan_favorites(force_refresh=True)

        addon = xbmcaddon.Addon()
        if result.get("success"):
            items_found = result.get("items_found", 0)
            items_mapped = result.get("items_mapped", 0)

            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Scanned: {items_mapped}/{items_found} favorites mapped",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
        else:
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                f"Scan failed: {result.get('message', 'Unknown error')}",
                xbmcgui.NOTIFICATION_ERROR
            )

        # Refresh the view
        xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        logger.error(f"Error scanning favorites: {e}")
        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            "Scan error",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_add_favorite_to_list():
    """Handle adding a favorite to a user list"""
    try:
        favorite_id = args.get('favorite_id')  # Changed from 'kodi_id' to 'favorite_id'
        if not favorite_id:
            logger.error("No favorite_id provided for add_favorite_to_list")
            return

        logger.info(f"Adding favorite {favorite_id} to list")

        # Get available lists
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return

        # Get the favorite info
        from lib.kodi.favorites_manager import get_phase4_favorites_manager
        favorites_manager = get_phase4_favorites_manager()

        # Get all favorites and find the one we want
        all_favorites = favorites_manager.get_mapped_favorites(show_unmapped=False)
        target_favorite = None
        for fav in all_favorites:
            if str(fav.get('id')) == str(favorite_id):
                target_favorite = fav
                break

        if not target_favorite or not target_favorite.get('library_movie_id'):
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "Favorite not found or not mapped to library"
            )
            return

        # Get available lists
        from lib.data.list_library_manager import get_list_library_manager
        list_manager = get_list_library_manager()
        available_lists = list_manager.get_available_lists_for_movie(target_favorite['library_movie_id'])

        if not available_lists:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                "No available lists or favorite already in all lists"
            )
            return

        # Let user pick a list
        list_names = [list_item['name'] for list_item in available_lists]
        selected_index = xbmcgui.Dialog().select("Add to list:", list_names)

        if selected_index >= 0:
            selected_list = available_lists[selected_index]

            # Add to the selected list
            result = list_manager.add_library_movie_to_list(
                selected_list['id'],
                target_favorite['library_movie_id']
            )

            if result.get("success"):
                xbmcgui.Dialog().notification(
                    addon.getLocalizedString(35002),
                    f"Added '{target_favorite['name']}' to '{selected_list['name']}'",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            else:
                xbmcgui.Dialog().notification(
                    addon.getLocalizedString(35002),
                    f"Failed to add to list: {result.get('message', 'Unknown error')}",
                    xbmcgui.NOTIFICATION_ERROR
                )

    except Exception as e:
        logger.error(f"Error adding favorite to list: {e}")
        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35002),
            "Add to list error",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_settings():
    """Handle settings menu"""
    logger.info("Opening addon settings")
    xbmcaddon.Addon().openSettings()


def _format_time_ago(timestamp_str):
    """Format timestamp as human readable 'time ago' string"""
    if not timestamp_str:
        return "never"

    try:
        from datetime import datetime, timezone

        # Parse the timestamp - handle both Z suffix and +00:00 formats
        if timestamp_str.endswith('Z'):
            normalized_timestamp = timestamp_str.replace('Z', '+00:00')
        elif '+' not in timestamp_str and timestamp_str.count(':') >= 2:
            normalized_timestamp = timestamp_str + '+00:00'
        else:
            normalized_timestamp = timestamp_str

        scan_time = datetime.fromisoformat(normalized_timestamp)

        if scan_time.tzinfo is None:
            scan_time = scan_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        diff = now - scan_time
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            return "just now"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = total_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"

    except Exception as e:
        logger.debug(f"Error formatting timestamp '{timestamp_str}': {e}")
        return "unknown"


def handle_shortlist_import():
    """Handle ShortList import action from settings"""
    import xbmcgui
    from lib.import_export.shortlist_importer import get_shortlist_importer

    try:
        # Show confirmation dialog
        dialog = xbmcgui.Dialog()
        if not dialog.yesno(
            "ShortList Import",
            "This will import all items from ShortList addon into a 'ShortList Import' list.",
            "Only items that match movies in your Kodi library will be imported.",
            "Continue?"
        ):
            return

        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("ShortList Import", "Checking ShortList addon...")
        progress.update(10)

        importer = get_shortlist_importer()

        # Check if ShortList is available
        if not importer.is_shortlist_installed():
            progress.close()
            dialog.notification(
                "LibraryGenie",
                "ShortList addon not found or not enabled",
                xbmcgui.NOTIFICATION_WARNING,
                5000
            )
            return

        progress.update(30, "Scanning ShortList data...")

        # Perform the import
        result = importer.import_shortlist_items()

        progress.update(100, "Import complete!")
        progress.close()

        if result.get("success"):
            message = (
                f"Import completed!\n"
                f"Processed: {result.get('total_items', 0)} items\n"
                f"Added to list: {result.get('items_added', 0)} movies\n"
                f"Unmapped: {result.get('items_unmapped', 0)} items"
            )
            dialog.ok("ShortList Import", message)
        else:
            error_msg = result.get("error", "Unknown error occurred")
            dialog.ok("ShortList Import", f"Import failed: {error_msg}")

    except Exception as e:
        logger.error(f"ShortList import handler error: {e}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Import failed with error",
            xbmcgui.NOTIFICATION_ERROR,
            5000
        )


def handle_noop():
    """No-op handler that safely ends the directory without args mismatches"""
    try:
        addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        if addon_handle >= 0:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
    except Exception:
        pass


# Define the route mapping for actions
action_handlers = {
    'search': show_search_menu,
    'lists': handle_lists,
    'kodi_favorites': handle_kodi_favorites,
    'scan_favorites': handle_scan_favorites,
    'add_favorite_to_list': handle_add_favorite_to_list,
    'create_list': handle_create_list,
    'view_list': handle_view_list,
    'rename_list': handle_rename_list,
    'delete_list': handle_delete_list,
    'remove_from_list': handle_remove_from_list,
    'create_folder': handle_create_folder,
    'rename_folder': handle_rename_folder,
    'delete_folder': handle_delete_folder,
    'show_folder': handle_show_folder,  # Added handler for showing folder contents
    'show_list': handle_view_list,      # Route show_list to handle_view_list
    'remote_lists': show_remote_lists_menu,
    'authorize': handle_authorize,
    'signout': handle_signout,
    'on_select': handle_on_select,      # Special case handled in main
    'noop': handle_noop,                # No-arg safe noop
    'import_shortlist': handle_shortlist_import
}


def main():
    """Main plugin entry point"""

    # Log complete plugin invocation details at entry
    logger.debug(f"=== PLUGIN INVOCATION ===")
    logger.debug(f"Full sys.argv: {sys.argv}")

    # Log current window and control state
    try:
        current_window = xbmc.getInfoLabel("System.CurrentWindow")
        current_control = xbmc.getInfoLabel("System.CurrentControl")
        container_path = xbmc.getInfoLabel("Container.FolderPath")
        container_label = xbmc.getInfoLabel("Container.FolderName")

        logger.debug(f"Window state at plugin entry:")
        logger.debug(f"  Current window: {current_window}")
        logger.debug(f"  Current control: {current_control}")
        logger.debug(f"  Container path: {container_path}")
        logger.debug(f"  Container label: {container_label}")

        # Check specific window visibility states
        myvideo_nav_visible = xbmc.getCondVisibility("Window.IsVisible(MyVideoNav.xml)")
        dialog_video_info_visible = xbmc.getCondVisibility("Window.IsVisible(DialogVideoInfo.xml)")
        dialog_video_info_active = xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)")
        keyboard_visible = xbmc.getCondVisibility("Window.IsVisible(DialogKeyboard.xml)")

        logger.debug(f"  MyVideoNav.xml visible: {myvideo_nav_visible}")
        logger.debug(f"  DialogVideoInfo.xml visible: {dialog_video_info_visible}")
        logger.debug(f"  DialogVideoInfo.xml active: {dialog_video_info_active}")
        logger.debug(f"  DialogKeyboard.xml visible: {keyboard_visible}")

    except Exception as e:
        logger.warning(f"Failed to log window state at plugin entry: {e}")

    logger.debug(f"Plugin arguments: {sys.argv}")

    try:
        # Parse plugin arguments
        addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        base = sys.argv[0] if len(sys.argv) > 0 else ""
        query_string = sys.argv[2][1:] if len(sys.argv) > 2 and len(sys.argv[2]) > 1 else ""

        # Parse query parameters
        params = dict(parse_qsl(query_string))
        global args, base_url
        args = params  # Set global args for use in handler functions
        base_url = base

        logger.debug(
            f"Plugin called with handle={addon_handle}, url={base_url}, params={params}"
        )

        # Check if this is first run and trigger library scan if needed
        _check_and_trigger_initial_scan()

        # Route based action parameter
        action = params.get('action', '')

        # Log all routing for test harness tracking
        if action.startswith('test_') or action == 'noop':
            logger.info(f"[TEST-HARNESS] NAVIGATION: User triggered action '{action}'")
            logger.info(f"[TEST-HARNESS] NAVIGATION: Full routing context - handle={addon_handle}, base_url={base_url}")

        # Call the appropriate handler
        handler = action_handlers.get(action)

        if handler:
            # Special handling for actions that require specific arguments or logic
            if action == 'search':
                handler(addon_handle)
            elif action in ('lists', 'view_list', 'show_folder', 'show_list', 'kodi_favorites'):
                handler(addon_handle, base_url)
            elif action == 'on_select':
                # handle_on_select expects params and addon_handle
                handler(params, addon_handle)
            elif action in ('import_shortlist', 'noop', 'create_list', 'authorize', 'signout',
                            'rename_list', 'delete_list', 'remove_from_list',
                            'create_folder', 'rename_folder', 'delete_folder',
                            'scan_favorites', 'add_favorite_to_list', 'remote_lists',
                            'show_remote_search', 'settings'):
                # Zero-arg or internal handlers
                handler()
            else:
                # Fallback: try zero-arg call
                handler()
        else:
            # Show main menu by default if action is not recognized or is empty
            show_main_menu(addon_handle)

    except Exception as e:
        logger.error(f"Fatal error in plugin main: {e}")
        # Try to show error to user if possible
        try:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35013),
                xbmcgui.NOTIFICATION_ERROR
            )
        except Exception:
            pass


if __name__ == '__main__':
    main()
