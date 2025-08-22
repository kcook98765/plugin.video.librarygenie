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
from urllib.parse import parse_qsl # Import parse_qsl for parameter parsing

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

def router(paramstring):
    """
    Router function to handle plugin URLs and dispatch to appropriate handlers
    """
    try:
        log(f"Router called with: {paramstring}", "DEBUG")

        # Clean up navigation state
        from resources.lib.core.navigation_manager import get_navigation_manager
        nav_manager = get_navigation_manager()
        nav_manager.cleanup_stuck_navigation()

        # Parse parameters from URL - handle both with and without leading '?'
        clean_paramstring = paramstring.lstrip('?') if paramstring else ''
        params = dict(parse_qsl(clean_paramstring))
        action = params.get('action')

        log(f"Parsed action: {action}", "DEBUG")
        log(f"All params: {params}", "DEBUG")

        # If no action specified, build root directory
        if not action or not clean_paramstring.strip():
            log("Received empty paramstr, building root directory.", "DEBUG")
            nav_manager.clear_navigation_flags()
            build_root_directory(ADDON_HANDLE) # Pass ADDON_HANDLE to build_root_directory
            return

        # Handle different actions
        if action == 'browse_folder':
            folder_id = params.get('folder_id')
            browse_folder(params) # Pass the entire params dict to browse_folder
        elif action == 'browse_list':
            list_id = params.get('list_id')
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
            for key, value in params.items():
                if key != 'action':
                    list_params[key] = [value] if not isinstance(value, list) else value
            options_manager.show_options_menu(list_params)
        else:
            # Handle other actions through route_handlers
            from resources.lib.core.route_handlers import route_action

            # Convert single values to lists for compatibility
            list_params = {}
            for key, value in params.items():
                if key != 'action':
                    list_params[key] = [value] if not isinstance(value, list) else value

            route_action(action, list_params)

    except Exception as e:
        log(f"Error in router: {str(e)}", "ERROR")
        import traceback
        log(f"Router traceback: {traceback.format_exc()}", "ERROR")
        # Fallback: show a simple notification and then build root directory
        import xbmcgui
        xbmcgui.Dialog().notification('LibraryGenie', 'Error processing request', xbmcgui.NOTIFICATION_ERROR)
        nav_manager.clear_navigation_flags()
        build_root_directory(ADDON_HANDLE) # Pass ADDON_HANDLE to build_root_directory


# Add handle_show_options function here
def handle_show_options(params):
    """Handle the Options & Tools menu display"""
    try:
        log("=== SHOW_OPTIONS: Starting options menu display ===", "INFO")

        # Use the OptionsManager to show the options menu
        options_manager = OptionsManager()
        options_manager.show_options_menu(params)

        log("=== SHOW_OPTIONS: Options menu completed ===", "INFO")

    except Exception as e:
        log(f"Error in handle_show_options: {str(e)}", "ERROR")
        import traceback
        log(f"handle_show_options traceback: {traceback.format_exc()}", "ERROR")

        # Fallback: show a simple notification
        import xbmcgui
        xbmcgui.Dialog().notification('LibraryGenie', 'Options menu error', xbmcgui.NOTIFICATION_ERROR)


def handle_browse_folder(params):
    """Handle folder browsing with proper context detection"""
    try:
        folder_id = params.get('folder_id', [None])[0]
        if folder_id and str(folder_id).isdigit():
            folder_id = int(folder_id)
        else:
            folder_id = None

        handle = int(sys.argv[1])

        # Set up context for folder browsing
        ctx = detect_context({
            'action': 'browse_folder',
            'folder_id': folder_id,
            'view': 'folder'
        })

        # Add Options & Tools header for consistent navigation
        add_options_header_item(ctx, handle)

        # Get folder contents
        config = Config() # Assuming Config is available
        query_manager = QueryManager(config.db_path)

        subfolders = query_manager.fetch_folders(folder_id)
        lists = query_manager.fetch_lists(folder_id)

        # Build directory items
        for folder in subfolders:
            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            add_context_menu_for_item(li, 'folder', folder_id=folder['id'])
            url = build_plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        for list_item in lists:
            list_id = list_item['id']
            list_name = list_item['name']

            # Get media count for the list
            media_count = query_manager.get_list_media_count(list_id)
            display_name = f"{list_name} ({media_count})"

            li = ListItemBuilder.build_folder_item(f"📋 {display_name}", is_folder=True, item_type='playlist')
            li.setProperty('lg_type', 'list')
            add_context_menu_for_item(li, 'list', list_id=list_id)
            url = build_plugin_url({'action': 'browse_list', 'list_id': list_id, 'view': 'list'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Check if directory is empty
        if not subfolders and not lists:
            show_empty_directory(handle, "This folder is empty.")
        else:
            xbmcplugin.setContent(handle, 'files')
            xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        log(f"Error in handle_browse_folder: {str(e)}", "ERROR")
        import traceback
        log(f"handle_browse_folder traceback: {traceback.format_exc()}", "ERROR")
        show_empty_directory(handle, "Error loading folder contents.")

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
    # Library scan check removed - now handled only by service on startup

    # Only run favorites sync AFTER initial setup check passes
    # This prevents favorites from interfering with setup detection
    try:
        from resources.lib.config.settings_manager import SettingsManager
        from resources.lib.integrations.remote_api.favorites_sync_manager import FavoritesSyncManager
        from resources.lib.utils import utils
        import sys

        # Check if we're at root level (no specific action parameters)
        at_root = (len(sys.argv) <= 2 or
                  (len(sys.argv) >= 3 and (not sys.argv[2] or sys.argv[2] in ('', '?'))))

        if at_root:
            try:
                settings = SettingsManager()
                if settings.is_favorites_sync_enabled():
                    # Double-check that library data exists before running favorites sync
                    config = Config()
                    query_manager = QueryManager(config.db_path)
                    
                    # Check both tables to ensure we have actual library data
                    imdb_result = query_manager.execute_query("SELECT COUNT(*) as count FROM imdb_exports", fetch_one=True)
                    imdb_count = imdb_result['count'] if imdb_result else 0
                    
                    media_result = query_manager.execute_query("SELECT COUNT(*) as count FROM media_items WHERE source = 'lib'", fetch_one=True)
                    media_count = media_result['count'] if media_result else 0
                    
                    if imdb_count > 0 or media_count > 0:
                        utils.log("Root navigation detected - triggering favorites sync", "DEBUG")
                        sync_manager = FavoritesSyncManager()
                        # Sync in isolation - no UI operations should happen during this
                        sync_result = sync_manager.sync_favorites()
                        utils.log("Favorites sync completed", "DEBUG")
                        
                        # Small delay to ensure sync completes before UI operations
                        import time
                        time.sleep(0.1)
                    else:
                        utils.log("Skipping favorites sync - no library data available yet (initial scan needed)", "DEBUG")
            except Exception as e:
                utils.log(f"Error in root navigation favorites sync: {str(e)}", "ERROR")
                # Don't let sync errors prevent addon from loading
    except Exception as e:
        # Don't let sync errors prevent addon from loading
        utils.log(f"Error in main sync setup: {str(e)}", "ERROR")

    from resources.lib.config.addon_helper import run_addon
    run_addon()

if __name__ == '__main__':
    main()