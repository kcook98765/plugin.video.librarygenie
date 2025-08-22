""" /main.py """
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin

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
from resources.lib.data.query_manager import QueryManager
from resources.lib.utils.utils import log
from resources.lib.core.route_handlers import (
    play_movie, show_item_details, create_list, rename_list, delete_list,
    remove_from_list, rename_folder, move_list, add_movies_to_list,
    clear_list, export_list, delete_folder, move_folder, create_subfolder
)
from resources.lib.kodi.listitem_builder import ListItemBuilder
from resources.lib.core import route_handlers
from urllib.parse import parse_qsl, parse_qs # Import parse_qsl and parse_qs for parameter parsing
from resources.lib.kodi.kodi_helper import KodiHelper # Import KodiHelper

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
    log("=== RUN_SEARCH_FLOW START ===", "DEBUG")

    target_url = None
    try:
        from resources.lib.kodi.window_search import SearchWindow
        log("=== CREATING SearchWindow INSTANCE ===", "DEBUG")
        search_window = SearchWindow()
        log("=== ABOUT TO CALL SearchWindow.doModal() ===", "DEBUG")
        search_window.doModal()
        log("=== SearchWindow.doModal() COMPLETED ===", "DEBUG")

        # Get target URL if search was successful
        target_url = search_window.get_target_url()
        log(f"=== SearchWindow returned target_url: {target_url} ===", "DEBUG")

        del search_window
        log("=== SearchWindow INSTANCE DELETED ===", "DEBUG")

    except Exception as e:
        log(f"=== ERROR IN RUN_SEARCH_FLOW: {str(e)} ===", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")

    # Navigate only after modal is completely closed
    if target_url:
        # Extract list ID for navigation
        list_id = target_url.split('list_id=')[1]
        log(f"=== MAIN: Scheduling navigation to list {list_id} ===", "DEBUG")

        # Use background thread navigation with proper Kodi integration
        import threading
        import time

        def navigate_to_list():
            try:
                log(f"=== MAIN_NAVIGATION: Starting navigation to list {list_id} ===", "DEBUG")

                # Build the target URL
                from resources.lib.config.addon_ref import get_addon
                from urllib.parse import urlencode
                addon = get_addon()
                addon_id = addon.getAddonInfo("id")
                params = urlencode({'action': 'browse_list', 'list_id': str(list_id)})
                final_url = f"plugin://{addon_id}/?{params}"

                log(f"=== MAIN_NAVIGATION: Target URL: {final_url} ===", "DEBUG")

                # Clear any dialog states
                xbmc.executebuiltin("Dialog.Close(all,true)")
                time.sleep(0.2)

                # Use Kodi's built-in navigation that preserves back button
                xbmc.executebuiltin(f'ActivateWindow(videos,"{final_url}",return)')

                log(f"=== MAIN_NAVIGATION: Navigation completed ===", "DEBUG")

            except Exception as e:
                log(f"Error in main navigation thread: {str(e)}", "ERROR")
                import traceback
                log(f"Main navigation traceback: {traceback.format_exc()}", "ERROR")

        # Start navigation in background
        nav_thread = threading.Thread(target=navigate_to_list)
        nav_thread.daemon = True
        nav_thread.start()
    else:
        log("=== NO TARGET URL - SEARCH CANCELLED OR FAILED ===", "DEBUG")

    log("=== RUN_SEARCH_FLOW COMPLETE ===", "DEBUG")

def run_search(params):
    """Legacy function - redirect to new flow"""
    run_search_flow()

def browse_folder(params):
    """Browse a folder and display its contents"""
    folder_id = params.get('folder_id', [None])[0]
    if not folder_id:
        log("No folder_id provided for browse_folder", "ERROR")
        return

    try:
        folder_id = int(folder_id)
        log(f"Browsing folder {folder_id}", "DEBUG")

        config = Config()
        query_manager = QueryManager(config.db_path)

        # Get folder details
        folder = query_manager.fetch_folder_by_id(folder_id)
        if not folder:
            log(f"Folder {folder_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found')
            return

        # Add options header with folder context - pass the actual folder_id
        ctx = detect_context({'view': 'folder', 'folder_id': folder_id})
        add_options_header_item(ctx, ADDON_HANDLE)

        # Get subfolders
        subfolders = query_manager.fetch_folders(folder_id)

        # Get lists in this folder
        lists = query_manager.fetch_lists(folder_id)

        # Add subfolders
        for subfolder in subfolders:
            li = ListItemBuilder.build_folder_item(f"📁 {subfolder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            add_context_menu_for_item(li, 'folder', folder_id=subfolder['id'])
            url = build_plugin_url({'action': 'browse_folder', 'folder_id': subfolder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)

        # Add lists
        for list_item in lists:
            list_count = query_manager.get_list_media_count(list_item['id'])

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
        log(f"Error browsing folder: {str(e)}", "ERROR")
        import traceback
        log(f"browse_folder traceback: {traceback.format_exc()}", "ERROR")
        show_empty_directory(ADDON_HANDLE, "Error loading folder contents")

def browse_list(list_id):
    """Browse items in a specific list"""
    import xbmcplugin
    from resources.lib.config.config_manager import Config
    from resources.lib.kodi.listitem_builder import ListItemBuilder
    from resources.lib.data.query_manager import QueryManager

    handle = int(sys.argv[1])

    log(f"=== BROWSE_LIST FUNCTION CALLED with list_id={list_id}, handle={handle} ===", "INFO")

    try:
        log(f"=== BROWSE_LIST ACTION START for list_id={list_id} ===", "INFO")
        config = Config()
        query_manager = QueryManager(config.db_path)
        from resources.lib.data.results_manager import ResultsManager
        from resources.lib.kodi.listitem_builder import ListItemBuilder

        # Clear navigation flags - simplified
        nav_manager.clear_navigation_flags()
        log("Cleared navigation flags at browse_list entry", "DEBUG")

        # Set proper container properties first
        xbmcplugin.setContent(handle, "movies")
        xbmcplugin.setPluginCategory(handle, "Search Results")

        # Use policy-aware resolver
        rm = ResultsManager()
        display_items = rm.build_display_items_for_list(list_id, handle)

        if not display_items:
            log(f"No display items found for list {list_id}", "WARNING")
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
                    log(f"Unexpected item format: {type(item)}", "WARNING")
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
                log(f"Error processing item {i+1}: {str(e)}", "ERROR")
                import traceback
                log(f"Item processing traceback: {traceback.format_exc()}", "ERROR")

        log(f"Successfully added {items_added} items ({playable_count} playable, {non_playable_count} non-playable)", "INFO")

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
        log(f"=== BROWSE_LIST ACTION COMPLETE for list_id={list_id} ===", "INFO")
    except Exception as e:
        try:
            log(f"Error in browse_list: {str(e)}", "ERROR")
            import traceback
            log(f"browse_list traceback: {traceback.format_exc()}", "ERROR")
        except Exception as log_error:
            # Fallback logging if utils still has issues
            import xbmc
            xbmc.log(f"LibraryGenie [ERROR]: Error in browse_list: {str(e)}", xbmc.LOGINFO)
            xbmc.log(f"LibraryGenie [ERROR]: Additional logging error: {str(log_error)}", xbmc.LOGINFO)
        # Show error item
        from resources.lib.kodi.listitem_builder import ListItemBuilder
        error_li = ListItemBuilder.build_folder_item(f"Error loading list: {str(e)}", is_folder=False)
        xbmcplugin.addDirectoryItem(handle, "", error_li, False)
        xbmcplugin.endOfDirectory(handle, succeeded=False)

def router(handle, paramstr):
    """Router for plugin calls"""
    log(f"Router called with handle {handle} and paramstr: {paramstr}", "DEBUG")

    # Validate handle
    if handle < 0:
        log(f"Invalid plugin handle: {handle}", "ERROR")
        return

    # Clear any stuck navigation flags
    from resources.lib.core.navigation_manager import get_navigation_manager
    nav_manager = get_navigation_manager()
    nav_manager.cleanup_stuck_navigation()

    try:
        query_params = parse_qs(paramstr.lstrip('?'))
        action = query_params.get('action', [None])[0]

        log(f"Parsed action: {action}", "DEBUG")
        log(f"All params: {query_params}", "DEBUG")

        # If no action, build root directory
        if not action:
            log("Received empty paramstr, building root directory.", "DEBUG")
            nav_manager.clear_navigation_flags()
            from resources.lib.core.directory_builder import build_root_directory
            build_root_directory(handle)
            return
    except Exception as e:
        log(f"Error parsing parameters: {str(e)}", "ERROR")
        nav_manager.clear_navigation_flags()
        from resources.lib.core.directory_builder import build_root_directory
        build_root_directory(handle)
        return

    # Handle different actions
    if action == 'browse_folder':
        folder_id = query_params.get('folder_id')
        browse_folder(query_params) # Pass the entire params dict to browse_folder
    elif action == 'browse_list':
        list_id = query_params.get('list_id')
        browse_list(list_id)
    elif action == 'search':
        run_search_flow()
    elif action == 'browse_search_history':
        browse_search_history()
    elif action == 'show_options':
        # Handle options menu
        options_manager = OptionsManager()
        # Convert params to the format expected by show_options_menu
        list_params = {}
        for key, value in query_params.items():
            if key != 'action':
                list_params[key] = [value] if not isinstance(value, list) else value
        options_manager.show_options_menu(list_params)
    else:
        # Handle other actions through route_handlers
        from resources.lib.core.route_handlers import route_action

        # Convert single values to lists for compatibility
        list_params = {}
        for key, value in query_params.items():
            if key != 'action':
                list_params[key] = [value] if not isinstance(value, list) else value

        route_action(action, list_params)


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
    from resources.lib.config.addon_helper import run_addon
    run_addon()

if __name__ == '__main__':
    main()