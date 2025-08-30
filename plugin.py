#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Entry Point
Handles plugin URL routing and main menu display
"""

import sys
import urllib.parse
from urllib.parse import parse_qsl
try:
    from typing import Dict, Any
except ImportError:
    # Python < 3.5 fallback
    Dict = dict
    Any = object

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

# Import test info variants module
import test_info_variants as tiv

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

    # Test Info Variants (debug/development tool) - now uses test_info_variants module
    test_item = xbmcgui.ListItem(label="[COLOR gray]Test Info Variants[/COLOR]")
    test_url = f"{sys.argv[0]}?action=test_info_variants&dbtype=movie&dbid=883"
    logger.info(f"[TEST-HARNESS] Adding test menu item with URL: {test_url}")
    xbmcplugin.addDirectoryItem(handle, test_url, test_item, True)

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
        search_history_items = [item for item in user_lists if 'Search History' in str(item.get('name', ''))]
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

        # Build menu items for lists
        menu_items = []

        # Add "Create New List" option at the top
        menu_items.append({
            "title": "[COLOR yellow]+ Create New List[/COLOR]",
            "action": "create_list",
            "description": "Create a new list",
            "is_folder": False,
            "icon": "DefaultAddSource.png"
        })

        # Add separator
        menu_items.append({
            "title": "─" * 30,
            "action": "",
            "description": "",
            "is_folder": False
        })

        # Add each list/folder
        for list_item in user_lists:
            menu_items.append({
                "title": f"{list_item['name']} ({list_item['item_count']} items)",
                "action": "view_list",
                "list_id": list_item['id'],
                "description": f"Created: {list_item['created']}",
                "is_folder": True,
                "icon": "DefaultFolder.png",
                "context_menu": [
                    (f"Rename '{list_item['name']}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_item['id']})"),
                    (f"Delete '{list_item['name']}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_item['id']})")
                ]
            })

        # Use menu builder to display
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

        # Use ListItemBuilder to create proper videodb URLs for library items
        from lib.ui.listitem_builder import ListItemBuilder
        builder = ListItemBuilder(addon_handle, "plugin.video.librarygenie")

        # Set category for better navigation
        xbmcplugin.setPluginCategory(addon_handle, f"List: {list_info['name']}")

        # Build each item with proper URLs and context menus
        for item in list_items:
            try:
                # Use builder to get proper URL, listitem, and folder status
                result = builder._build_single_item(item)
                if not result:
                    logger.warning(f"Skipping item '{item.get('title', 'Unknown')}' - failed to build")
                    continue

                url, list_item, is_folder = result

                # Add context menu for removal from list
                context_menu = [
                    (f"Remove from '{list_info['name']}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={list_id}&item_id={item.get('id')})")
                ]
                list_item.addContextMenuItems(context_menu)

                # Add to directory with proper URL (videodb:// for library items)
                xbmcplugin.addDirectoryItem(
                    addon_handle,
                    url,
                    list_item,
                    isFolder=is_folder
                )

            except Exception as e:
                logger.error(f"Error building list item '{item.get('title', 'Unknown')}': {e}")

        # Finish the directory
        xbmcplugin.endOfDirectory(addon_handle)

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
        import re, xbmc, xbmcplugin

        logger.info(f"=== ON_SELECT HANDLER CALLED ===")
        logger.info(f"Handling on_select with params: {params}")
        logger.info(f"Addon handle: {addon_handle}")

        dbtype = params.get("dbtype", "movie")
        dbid = int(params.get("dbid", "0"))
        tvshowid = params.get("tvshowid")
        season = params.get("season")
        tvshowid = int(tvshowid) if tvshowid and tvshowid.isdigit() else None
        season = int(season) if season and season.isdigit() else None

        vdb = _videodb_path(dbtype, dbid, tvshowid, season)  # must be a videodb:// path
        pref = get_select_pref()  # 'play' or 'info'

        # Parse major Kodi version (19, 20, 21, ...)
        ver_str = xbmc.getInfoLabel('System.BuildVersion')
        try:
            kodi_major = int(re.split(r'[^0-9]', ver_str, 1)[0])
        except Exception:
            kodi_major = 0

        logger.info(f"on_select: dbtype={dbtype}, dbid={dbid}, videodb_path={vdb}, preference={pref}, kodi_major={kodi_major}")

        if pref == "play":
            logger.info(f"Playing media: {vdb}")
            xbmc.executebuiltin(f'PlayMedia("{vdb}")')
        else:
            # IMPORTANT:
            # - On v19, open the *library* item’s info dialog explicitly so Kodi fetches cast from DB.
            # - On v20+, your existing indicators usually make Action(Info) fine; if you want to be
            #   100% consistent, you can also open by videodb path here too.
            if kodi_major <= 19:
                logger.info("Opening DialogVideoInfo for videodb item (Matrix)")
                xbmc.executebuiltin(f'ActivateWindow(DialogVideoInfo,"{vdb}",return)')
            else:
                logger.info("Opening info dialog for focused item (Nexus+)")
                xbmc.executebuiltin('Action(Info)')
                # If you prefer forcing DB context on v20+ as well, use:
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


def handle_settings():
    """Handle settings menu"""
    logger.info("Opening addon settings")
    xbmcaddon.Addon().openSettings()





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

        if action == 'search':
            show_search_menu(addon_handle)
        elif action == 'lists':
            handle_lists(addon_handle, base_url)
        elif action == 'create_list':
            handle_create_list()
        elif action == 'view_list':
            handle_view_list(addon_handle, base_url)
        elif action == 'rename_list':
            handle_rename_list()
        elif action == 'delete_list':
            handle_delete_list()
        elif action == 'remote_lists':
            show_remote_lists_menu(addon_handle)
        elif action == 'authorize':
            handle_authorize()
        elif action == 'signout':
            handle_signout()
        elif action == 'on_select':
            # Legacy handler - library items now use videodb:// URLs for native behavior
            logger.info(f"ROUTING: on_select action detected (legacy) with params: {params}")
            logger.info(f"Library items now use videodb:// URLs for native Kodi behavior")
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        elif action == 'test_info_variants':
            logger.info(f"[TEST-HARNESS] ROUTING: test_info_variants action detected - using new module")
            tiv.add_menu(addon_handle, base_url, dbtype='movie', dbid=883)
        elif action in ('test_matrix', 'test_nexus', 'nexus_info_click'):
            logger.info(f"[TEST-HARNESS] ROUTING: {action} action detected - using new module")
            logger.info(f"[TEST-HARNESS] Params: {params}")
            # pass handle & base_url for test_nexus so it can build the one-item list
            tiv.handle_click(params, handle=addon_handle, base_url=base_url)
        elif action == 'noop':
            logger.info(f"[TEST-HARNESS] ROUTING: noop action (test baseline)")
            logger.info(f"[TEST-HARNESS] Noop params: {params}")
            logger.info(f"[TEST-HARNESS] This is a no-op test variant - ending directory")
            # No-op action for test variants - just end directory
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        else:
            # Show main menu by default
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