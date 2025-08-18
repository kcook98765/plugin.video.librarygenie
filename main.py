""" /main.py """
import os
import sys
import urllib.parse # Import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode, parse_qs
from urllib.parse import quote_plus, urlparse # Import urlparse
import time # Import time module

# Import new modules
from resources.lib.kodi.url_builder import build_plugin_url, parse_params, detect_context
from resources.lib.core.options_manager import OptionsManager
from resources.lib.core.directory_builder import (
    add_context_menu_for_item, add_options_header_item,
    build_root_directory, show_empty_directory
)
from resources.lib.core.navigation_manager import get_navigation_manager
from resources.lib.data.folder_list_manager import get_folder_list_manager

from resources.lib.config.addon_helper import run_addon
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.utils.utils import utils
from resources.lib.core.route_handlers import (
    play_movie, show_item_details, create_list, rename_list, delete_list,
    remove_from_list, rename_folder, move_list
)
from resources.lib.kodi.listitem_builder import ListItemBuilder
from resources.lib.core import route_handlers


# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

ADDON_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
PLUGIN_URL = sys.argv[0] if len(sys.argv) > 0 else ""


# Global variable to track initialization
_initialized = False

# Global instances
options_manager = OptionsManager()
nav_manager = get_navigation_manager()
folder_list_manager = get_folder_list_manager()

def run_search_flow():
    """Launch search modal and navigate to results after completion"""
    utils.log("=== RUN_SEARCH_FLOW START ===", "DEBUG")

    target_url = None
    try:
        from resources.lib.kodi.window_search import SearchWindow
        utils.log("=== CREATING SearchWindow INSTANCE ===", "DEBUG")
        search_window = SearchWindow()
        utils.log("=== ABOUT TO CALL SearchWindow.doModal() ===", "DEBUG")
        search_window.doModal()
        utils.log("=== SearchWindow.doModal() COMPLETED ===", "DEBUG")

        # Get target URL if search was successful
        target_url = search_window.get_target_url()
        utils.log(f"=== SearchWindow returned target_url: {target_url} ===", "DEBUG")

        del search_window
        utils.log("=== SearchWindow INSTANCE DELETED ===", "DEBUG")

    except Exception as e:
        utils.log(f"=== ERROR IN RUN_SEARCH_FLOW: {str(e)} ===", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")

    # Navigate only after modal is completely closed
    if target_url:
        nav_manager.navigate_to_url(target_url)
    else:
        utils.log("=== NO TARGET URL - SEARCH CANCELLED OR FAILED ===", "DEBUG")

    utils.log("=== RUN_SEARCH_FLOW COMPLETE ===", "DEBUG")

def run_search(params):
    """Legacy function - redirect to new flow"""
    run_search_flow()

def browse_folder(params):
    """Browse a folder and display its contents"""
    folder_id = params.get('folder_id', [None])[0]
    if not folder_id:
        utils.log("No folder_id provided for browse_folder", "ERROR")
        return

    try:
        folder_id = int(folder_id)
        utils.log(f"Browsing folder {folder_id}", "DEBUG")

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get folder details
        folder = db_manager.fetch_folder_by_id(folder_id)
        if not folder:
            utils.log(f"Folder {folder_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found')
            return

        # Add options header with folder context - pass the actual folder_id
        ctx = detect_context({'view': 'folder', 'folder_id': folder_id})
        add_options_header_item(ctx, ADDON_HANDLE)

        # Get subfolders
        subfolders = db_manager.fetch_folders(folder_id)

        # Get lists in this folder
        lists = db_manager.fetch_lists(folder_id)

        # Add subfolders
        for subfolder in subfolders:
            li = ListItemBuilder.build_folder_item(f"📁 {subfolder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            add_context_menu_for_item(li, 'folder', folder_id=subfolder['id'])
            url = build_plugin_url({'action': 'browse_folder', 'folder_id': subfolder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)

        # Add lists
        for list_item in lists:
            list_count = db_manager.get_list_media_count(list_item['id'])

            # Check if this list contains a count pattern like "(number)" at the end
            import re
            has_count_in_name = re.search(r'\(\d+\)$', list_item['name'])

            if has_count_in_name:
                # List already has count in name (likely search history), use as-is
                display_title = list_item['name']
            else:
                # Regular list, add count
                display_title = f"{list_item['name']} ({list_count})"

            li = ListItemBuilder.build_folder_item(f"📋 {display_title}", is_folder=True, item_type='playlist')
            li.setProperty('lg_type', 'list')
            add_context_menu_for_item(li, 'list', list_id=list_item['id'])
            url = build_plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)

        xbmcplugin.endOfDirectory(ADDON_HANDLE)

    except Exception as e:
        utils.log(f"Error browsing folder: {str(e)}", "ERROR")
        import traceback
        utils.log(f"browse_folder traceback: {traceback.format_exc()}", "ERROR")
        show_empty_directory(ADDON_HANDLE, "Error loading folder contents")

def browse_list(list_id):
    """Browse items in a specific list"""
    import xbmcplugin
    import xbmcgui
    import json
    from resources.lib.config.addon_ref import get_addon
    from resources.lib.data.database_manager import DatabaseManager
    from resources.lib.config.config_manager import Config
    from resources.lib.kodi.listitem_builder import ListItemBuilder
    from resources.lib.data.query_manager import QueryManager

    addon = get_addon()
    handle = int(sys.argv[1])

    utils.log(f"=== BROWSE_LIST FUNCTION CALLED with list_id={list_id}, handle={handle} ===", "INFO")

    try:
        utils.log(f"=== BROWSE_LIST ACTION START for list_id={list_id} ===", "INFO")
        config = Config()
        query_manager = QueryManager(config.db_path)
        from resources.lib.data.results_manager import ResultsManager
        from resources.lib.kodi.listitem_builder import ListItemBuilder

        # Clear navigation flags - simplified
        nav_manager.clear_navigation_flags()
        utils.log("Cleared navigation flags at browse_list entry", "DEBUG")

        # Set proper container properties first
        xbmcplugin.setContent(handle, "movies")
        xbmcplugin.setPluginCategory(handle, f"Search Results")

        # Use policy-aware resolver
        rm = ResultsManager()
        display_items = rm.build_display_items_for_list(list_id, handle)

        if not display_items:
            utils.log(f"No display items found for list {list_id}", "WARNING")
            return
        items_added = 0
        playable_count = 0
        non_playable_count = 0

        for i, item in enumerate(display_items):
            try:
                # ResultsManager.build_display_items_for_list returns tuples: (item_url, li, is_folder)
                if isinstance(item, tuple) and len(item) >= 3:
                    item_url, li, is_folder = item
                else:
                    # Fallback for unexpected format
                    utils.log(f"Unexpected item format: {type(item)}", "WARNING")
                    continue

                # The ListItem is already fully built by ResultsManager, just use the URL and add to directory
                url = item_url
                is_playable = not is_folder

                if is_playable:
                    playable_count += 1
                else:
                    non_playable_count += 1

                # Add directory item with proper folder flag
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
                items_added += 1
            except Exception as e:
                utils.log(f"Error processing item {i+1}: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Item processing traceback: {traceback.format_exc()}", "ERROR")

        utils.log(f"Successfully added {items_added} items ({playable_count} playable, {non_playable_count} non-playable)", "INFO")

        # Check if this is a search results list with scores to preserve order
        # Get the original list items to check for search scores
        list_items = query_manager.fetch_list_items_with_details(list_id)
        has_scores = False
        for item in list_items:
            search_score = item.get('search_score', 0)
            if search_score is not None and search_score > 0:
                has_scores = True
                break

        # Always enable sort methods so users can override the default order
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_DATEADDED)

        if has_scores:
            # For search results, add unsorted method to preserve score order as default
            xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED)

        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False, updateListing=True)
        utils.log(f"=== BROWSE_LIST ACTION COMPLETE for list_id={list_id} ===", "INFO")
    except Exception as e:
        utils.log(f"Error in browse_list: {e}", "ERROR")
        import traceback
        utils.log(f"browse_list traceback: {traceback.format_exc()}", "ERROR")
        # Show error item
        from resources.lib.kodi.listitem_builder import ListItemBuilder
        error_li = ListItemBuilder.build_folder_item(f"Error loading list: {str(e)}", is_folder=False)
        xbmcplugin.addDirectoryItem(handle, "", error_li, False)
        xbmcplugin.endOfDirectory(handle, succeeded=False)

def router(paramstring):
    """Main router function to handle different actions"""
    utils.log(f"Router called with: {paramstring}", "DEBUG")

    # Initialize navigation manager first
    from resources.lib.core.navigation_manager import get_navigation_manager
    nav_manager = get_navigation_manager()

    params = parse_params(paramstring)
    action = params.get('action', [None])[0]

    # Cleanup any stuck navigation states first
    nav_manager.cleanup_stuck_navigation()

    utils.log(f"Parsed action: {action}", "DEBUG")
    utils.log(f"All params: {params}", "DEBUG")

    # Check for deferred option execution from RunScript
    if len(sys.argv) >= 3 and sys.argv[1] == 'deferred_option':
        utils.log("=== HANDLING DEFERRED OPTION EXECUTION FROM MAIN ===", "DEBUG")
        try:
            option_index = int(sys.argv[2])
            # Retrieve stored folder context
            folder_context_str = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.DeferredFolderContext)")
            folder_context = None
            if folder_context_str and folder_context_str != "None":
                try:
                    folder_context = int(folder_context_str)
                except ValueError:
                    pass
            # Clear the property
            xbmc.executebuiltin("ClearProperty(LibraryGenie.DeferredFolderContext,Home)")
            options_manager.execute_deferred_option(option_index, folder_context)
        except Exception as e:
            utils.log(f"Error in deferred option execution: {str(e)}", "ERROR")
        return

    # Check if paramstr is valid and not empty before parsing
    if not params:
        utils.log("Received empty paramstr, building root directory.", "WARNING")
        nav_manager.clear_navigation_flags()
        build_root_directory(ADDON_HANDLE)
        return

    # Parse parameters using the new utility - handle both string and dict inputs
    if isinstance(params, str):
        q = parse_params(params)
    elif isinstance(params, dict):
        q = params
    else:
        utils.log(f"Unexpected params type: {type(params)}, treating as empty", "WARNING")
        q = {}

    action = q.get("action", [""])[0] if isinstance(q.get("action", [""]), list) else q.get("action", "")

    utils.log(f"Action determined: {action}", "DEBUG")

    if action == "search":
        utils.log("Handling search action", "DEBUG")
        try:
            from resources.lib.kodi.window_search import SearchWindow
            from resources.lib.core.navigation_manager import get_navigation_manager

            search_window = SearchWindow()
            search_window.doModal()

            # Check if we need to navigate after search
            target_url = search_window.get_target_url()
            if target_url:
                utils.log(f"Navigating to search results: {target_url}", "DEBUG")
                nav_manager = get_navigation_manager()
                nav_manager.navigate_to_url(target_url, replace=False)
        except Exception as e:
            utils.log(f"Error in search action: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", "Search failed", xbmcgui.NOTIFICATION_ERROR)
    elif action == 'setup_remote_api':
        utils.log("Handling setup_remote_api action", "DEBUG")
        try:
            from resources.lib.remote_api_setup import run_setup
            run_setup()
        except Exception as e:
            utils.log(f"Error in setup_remote_api action: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", "Failed to setup Remote API", xbmcgui.NOTIFICATION_ERROR)
    elif action == 'browse_folder':
        utils.log("Handling browse_folder action", "DEBUG")
        try:
            folder_id = q.get('folder_id', [None])[0]
            if folder_id:
                nav_manager.set_navigation_in_progress(False)
                browse_folder(q) # Pass the parsed params to browse_folder
            else:
                utils.log("Missing folder_id for browse_folder action, returning to root.", "WARNING")
                build_root_directory(ADDON_HANDLE)
        except Exception as e:
            utils.log(f"Error in browse_folder action: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", "Error browsing folder", xbmcgui.NOTIFICATION_ERROR)
    elif action == 'show_options':
        utils.log("Routing to options action", "DEBUG")
        # Check if we're in the middle of navigation to prevent dialog conflicts
        if nav_manager.is_navigation_in_progress():
            utils.log("Navigation in progress, skipping options dialog", "DEBUG")
            return
        options_manager.show_options_menu(q)
        # IMPORTANT: Do NOT call endOfDirectory() here - this is a RunPlugin action
        return
    elif action == 'create_list':
        utils.log("Routing to create_list action", "DEBUG")
        create_list(q)
        return
    elif action == 'rename_list':
        utils.log("Routing to rename_list action", "DEBUG")
        rename_list(q)
        return
    elif action == 'delete_list':
        utils.log("Routing to delete_list action", "DEBUG")
        delete_list(q)
        return
    elif action == 'move_list':
        utils.log("Routing to move_list action", "DEBUG")
        move_list(q)
        return
    elif action == 'remove_from_list':
        utils.log("Routing to remove_from_list action", "DEBUG")
        remove_from_list(q)
        return
    elif action == 'rename_folder':
        utils.log("Routing to rename_folder action", "DEBUG")
        rename_folder(q)
        return
    elif action == 'refresh_movie':
        utils.log("Routing to refresh_movie action", "DEBUG")
        refresh_movie(q)
        return
    elif action == 'show_item_details':
        utils.log("Routing to show_item_details action", "DEBUG")
        show_item_details(q)
        return
    elif action == 'play_movie':
        utils.log("Routing to play_movie action", "DEBUG")
        play_movie(q)
        return
    elif action == 'browse_list':
        list_id = q.get('list_id', [None])[0]
        if list_id:
            # Set proper content for list view
            xbmcplugin.setPluginCategory(ADDON_HANDLE, "Search Results")
            xbmcplugin.setContent(ADDON_HANDLE, "movies")
            nav_manager.set_navigation_in_progress(False)
            browse_list(list_id)
        else:
            utils.log("No list_id provided for browse_list action", "WARNING")
            show_empty_directory(ADDON_HANDLE)
        return
    elif action == 'separator':
        # Do nothing for separator items
        utils.log("Received separator action, doing nothing.", "DEBUG")
        pass
    elif action == 'find_similar':
        from resources.lib.route_handlers import find_similar_movies
        find_similar_movies(params)
    elif action == 'find_similar_from_plugin':
        route_handlers.find_similar_movies_from_plugin(params)
    elif action == 'add_to_list_from_context':
        route_handlers.add_to_list_from_context(params)
    elif action == 'add_to_list':
        route_handlers.add_to_list(params)
    else:
        # Default: build root directory if action is not recognized or empty
        utils.log(f"Unrecognized action '{action}' or no action specified, building root directory.", "DEBUG")
        build_root_directory(ADDON_HANDLE)

# Expose functions that other modules need to import
def create_new_folder_at_root():
    """Wrapper for folder_list_manager function"""
    return folder_list_manager.create_new_folder_at_root()

def clear_all_local_data():
    """Wrapper for folder_list_manager function"""
    return folder_list_manager.clear_all_local_data()

def browse_search_history():
    """Wrapper for folder_list_manager function"""
    return folder_list_manager.browse_search_history()

def main():
    """Main addon entry point"""
    utils.log("=== LibraryGenie addon starting ===", "INFO")
    utils.log(f"Command line args: {sys.argv}", "DEBUG")

    try:
        utils.log("Initializing addon components", "DEBUG")

        # Check for deferred option execution from RunScript
        if len(sys.argv) >= 3 and sys.argv[1] == 'deferred_option':
            utils.log("=== HANDLING DEFERRED OPTION EXECUTION FROM MAIN ===", "DEBUG")
            try:
                option_index = int(sys.argv[2])
                # Retrieve stored folder context
                folder_context_str = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.DeferredFolderContext)")
                folder_context = None
                if folder_context_str and folder_context_str != "None":
                    try:
                        folder_context = int(folder_context_str)
                    except ValueError:
                        pass
                # Clear the property
                xbmc.executebuiltin("ClearProperty(LibraryGenie.DeferredFolderContext,Home)")
                options_manager.execute_deferred_option(option_index, folder_context)
            except Exception as e:
                utils.log(f"Error in deferred option execution: {str(e)}", "ERROR")
            return

        # Handle plugin routing
        if len(sys.argv) >= 3:
            utils.log("Plugin routing detected", "DEBUG")
            router(sys.argv[2])
            return

        # Fallback: Run the addon helper if no other conditions met
        utils.log("No specific action detected, running default addon helper.", "DEBUG")
        run_addon()

        # Ensure Search History folder exists
        utils.log("Setting up configuration and database for first run", "DEBUG")
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        db_manager.ensure_folder_exists("Search History", None) # Ensure it exists at startup
        utils.log("Configuration and database setup complete", "DEBUG")

        utils.log("=== LibraryGenie addon startup complete ===", "INFO")
    except Exception as e:
        utils.log(f"CRITICAL ERROR in main(): {str(e)}", "ERROR")
        import traceback
        utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

if __name__ == '__main__':
    main()