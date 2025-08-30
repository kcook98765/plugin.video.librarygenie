#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Entry Point
Handles plugin URL routing and main menu display
"""

import sys
import urllib.parse
from urllib.parse import parse_qsl
from typing import Dict, Any

import xbmcaddon
import xbmcplugin
import xbmcgui
import xbmc # Added for xbmc.executebuiltin

# Import our addon modules
from lib.addon import AddonController
from lib.utils.logger import get_logger
from lib.auth.auth_helper import get_auth_helper
from lib.auth.state import is_authorized

# Import query manager for list operations
from lib.data.query_manager import get_query_manager # Assuming this path is correct

# Get logger instance
logger = get_logger(__name__)

# Placeholder for global arguments if needed by multiple functions
args = {}
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

    xbmcplugin.endOfDirectory(handle)


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
    xbmcplugin.endOfDirectory(handle)


def show_lists_menu(handle):
    """Show lists management interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35116))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle)


def show_remote_lists_menu(handle):
    """Show remote lists interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35117))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle)


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
        user_lists = query_manager.get_all_lists_with_folders()
        logger.info(f"Found {len(user_lists)} user lists")

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
        # sys.argv[0] is the plugin path
        # sys.argv[1] is the addon handle (integer)
        # sys.argv[2] is the query string, starting with '?'
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
        params = dict(parse_qsl(query_string)) # Use parse_qsl for parsing

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

        logger.info(f"Viewing list {list_id}")

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
        logger.info(f"Found {len(list_items)} items in list")

        if not list_items:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().ok(
                addon.getLocalizedString(35002),
                f"List '{list_info['name']}' is empty"
            )
            # Ensure directory is ended if list is empty
            xbmcplugin.endOfDirectory(addon_handle)
            return

        # Detect content type based on list items
        content_type = query_manager.detect_content_type(list_items)
        logger.info(f"Detected content type '{content_type}' for list '{list_info['name']}'")

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
            logger.info(f"Successfully built list directory with content_type='{content_type}'")
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
        folder_id = args.get('folder_id') # Assuming folder_id is passed
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
        folder_info = query_manager.get_folder_by_id(folder_id) # Assuming this method exists
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
        result = query_manager.rename_folder(folder_id, new_name.strip()) # Assuming this method exists

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
        folder_id = args.get('folder_id') # Assuming folder_id is passed
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
        folder_info = query_manager.get_folder_by_id(folder_id) # Assuming this method exists
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
            f"This will remove {folder_info['item_count']} items from the folder." # Assuming item_count exists
        ):
            logger.info("User cancelled folder deletion")
            return

        # Delete the folder
        result = query_manager.delete_folder(folder_id) # Assuming this method exists

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
            xbmcplugin.endOfDirectory(addon_handle)
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


# Define the route mapping for actions
action_handlers = {
    'search': show_search_menu,
    'lists': handle_lists,
    'create_list': handle_create_list,
    'view_list': handle_view_list,
    'rename_list': handle_rename_list,
    'delete_list': handle_delete_list,
    'remove_from_list': handle_remove_from_list,
    'create_folder': handle_create_folder,
    'rename_folder': handle_rename_folder,
    'delete_folder': handle_delete_folder,
    'show_folder': handle_show_folder, # Added handler for showing folder contents
    'show_list': handle_view_list, # Route show_list to handle_view_list
    'remote_lists': show_remote_lists_menu,
    'authorize': handle_authorize,
    'signout': handle_signout,
    'noop': lambda handle, base_url, params: xbmcplugin.endOfDirectory(handle, succeeded=False), # Dummy handler for noop
    'info': lambda handle, base_url, params: None # Placeholder for info action, will be handled in main
}

def main():
    """Main plugin entry point"""
    logger.debug(f"Plugin arguments: {sys.argv}")

    try:
        # Parse plugin arguments
        addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        base_url = sys.argv[0] if len(sys.argv) > 0 else ""
        query_string = sys.argv[2][1:] if len(sys.argv) > 2 and len(sys.argv[2]) > 1 else ""

        # Parse query parameters
        params = dict(parse_qsl(query_string))
        global args
        args = params # Set global args for use in handler functions

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
            elif action in ('lists', 'view_list', 'show_folder', 'show_list'):
                handler(addon_handle, base_url)
            elif action == 'context_action':
                kodi_id = int(params.get('kodi_id', [0])[0])
                context_action = params.get('context_action', [''])[0]

                logger.info(f"Handling context action '{context_action}' for kodi_id {kodi_id}")

                if context_action and kodi_id:
                    from lib.ui.context_menu import ContextMenuHandler
                    addon = xbmcaddon.Addon() # Ensure addon is available for getLocalizedString
                    handler = ContextMenuHandler(base_url, addon.getLocalizedString)
                    success = handler.handle_context_action(context_action, kodi_id)
                    if not success:
                        logger.warning(f"Context action '{context_action}' failed for kodi_id {kodi_id}")
                else:
                    logger.warning(f"Invalid context action parameters: action='{context_action}', kodi_id={kodi_id}")

                # No directory listing needed for context actions
                return

            elif action == 'info':
                # Handle info action for hijack functionality
                kodi_id = params.get('kodi_id', [''])[0]
                media_type = params.get('media_type', [''])[0]

                logger.info(f"Info action triggered for {media_type} {kodi_id} - this should trigger hijack")

                # Simply show the info dialog - the hijack manager will detect it and take over
                if kodi_id and media_type:
                    try:
                        kodi_id_int = int(kodi_id)
                        # Open info dialog which will be detected by hijack manager
                        xbmc.executebuiltin("Action(Info)")
                        logger.info(f"Opened info dialog for {media_type} {kodi_id_int} - hijack should activate")
                    except ValueError:
                        logger.error(f"Invalid kodi_id for info action: {kodi_id}")
                else:
                    logger.warning(f"Missing parameters for info action: kodi_id='{kodi_id}', media_type='{media_type}'")

                # No directory listing needed for info actions
                return
            else:
                handler() # For actions like create_list, authorize, signout, etc.
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


if __name__ == "__main__":
    main()