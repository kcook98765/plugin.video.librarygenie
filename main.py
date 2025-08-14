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

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

ADDON_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
PLUGIN_URL = sys.argv[0] if len(sys.argv) > 0 else ""

# Import new modules
from resources.lib.url_builder import build_plugin_url, parse_params, detect_context
from resources.lib.options_manager import OptionsManager
from resources.lib.directory_builder import (
    add_context_menu_for_item, add_options_header_item,
    build_root_directory, show_empty_directory
)
from resources.lib.navigation_manager import get_navigation_manager
from resources.lib.folder_list_manager import get_folder_list_manager

from resources.lib.addon_helper import run_addon
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib import utils
from resources.lib.route_handlers import (
    play_movie, show_item_details, create_list, rename_list, delete_list,
    remove_from_list, rename_folder, refresh_movie, do_search, move_list
)
from resources.lib.listitem_builder import ListItemBuilder

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
        from resources.lib.window_search import SearchWindow
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

def run_browse(params):
    """Launch the browse lists interface"""
    utils.log("Browse action triggered", "DEBUG")
    try:
        from resources.lib.window_main import MainWindow
        # Create dummy item info for browse mode
        item_info = {
            'title': 'Browse Mode',
            'plot': 'Browse your movie lists and folders',
            'is_playable': False,
            'kodi_id': 0
        }
        main_window = MainWindow(item_info, "LibraryGenie - Browse Lists")
        main_window.doModal()
        del main_window
    except Exception as e:
        utils.log(f"Error launching browse window: {str(e)}", "ERROR")

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
    from resources.lib.addon_ref import get_addon
    from resources.lib.database_manager import DatabaseManager
    from resources.lib.config_manager import Config
    from resources.lib.listitem_builder import ListItemBuilder
    from resources.lib.query_manager import QueryManager

    addon = get_addon()
    addon_id = addon.getAddonInfo("id")
    handle = int(sys.argv[1])

    utils.log(f"=== BROWSE_LIST FUNCTION CALLED with list_id={list_id}, handle={handle} ===", "INFO")

    try:
        utils.log(f"=== BROWSE_LIST ACTION START for list_id={list_id} ===", "INFO")
        config = Config()
        query_manager = QueryManager(config.db_path)
        from resources.lib.results_manager import ResultsManager
        from resources.lib.listitem_builder import ListItemBuilder

        # Clear navigation flags - simplified
        nav_manager.clear_navigation_flags()
        utils.log("Cleared navigation flags at browse_list entry", "DEBUG")

        # Set proper container properties first
        xbmcplugin.setContent(handle, "movies")
        xbmcplugin.setPluginCategory(handle, f"Search Results")

        # Use policy-aware resolver
        utils.log(f"Creating ResultsManager for list resolution", "DEBUG")
        rm = ResultsManager()
        utils.log(f"Calling build_display_items_for_list for list_id={list_id}", "DEBUG")
        display_items = rm.build_display_items_for_list(list_id)
        utils.log(f"Resolved {len(display_items)} display items for list {list_id}", "INFO")

        if not display_items:
            utils.log(f"No display items found for list {list_id} - checking database directly", "WARNING")
            # Check if list exists and has items
            db_manager = DatabaseManager(config.db_path)
            list_info = db_manager.fetch_list_by_id(list_id)
            if list_info:
                utils.log(f"List {list_id} exists: {list_info.get('name', 'Unknown')}", "DEBUG")
                raw_items = query_manager.fetch_list_items_with_details(list_id)
                utils.log(f"Raw list items count: {len(raw_items) if raw_items else 0}", "DEBUG")
                if raw_items:
                    utils.log(f"First raw item: {raw_items[0]}", "DEBUG")
            else:
                utils.log(f"List {list_id} does not exist in database", "ERROR")

        utils.log(f"Processing {len(display_items)} display items", "DEBUG")
        items_added = 0
        playable_count = 0
        non_playable_count = 0

        for i, media in enumerate(display_items):
            try:
                li = ListItemBuilder.build_video_item(media)
                li.setProperty('lg_type', 'movie')
                li.setProperty('lg_list_id', str(list_id))
                # Handle both tuple (li, file, media) and dict formats
                if isinstance(media, tuple) and len(media) >= 3:
                    media_dict = media[2]  # Third element is the metadata dict
                elif isinstance(media, dict):
                    media_dict = media
                else:
                    media_dict = {}

                li.setProperty('lg_movie_id', str(media_dict.get('id', '')))
                add_context_menu_for_item(li, 'movie', list_id=list_id, movie_id=media_dict.get('id'))

                # Determine the URL and playability
                url = media_dict.get('file') or media_dict.get('play') or ''
                is_playable = False
                movie_id = None

                # Check if we have a valid Kodi ID for playable content
                if media_dict.get('movieid') and str(media_dict['movieid']).isdigit() and int(media_dict['movieid']) > 0:
                    movie_id = int(media_dict['movieid'])
                    is_playable = True
                elif media_dict.get('kodi_id') and str(media_dict['kodi_id']).isdigit() and int(media_dict['kodi_id']) > 0:
                    movie_id = int(media_dict['kodi_id'])
                    is_playable = True
                elif url:
                    is_playable = True

                # For Kodi library items, create a plugin URL that will handle playback
                if movie_id and is_playable:
                    url = build_plugin_url({
                        'action': 'play_movie',
                        'movieid': movie_id,
                        'list_id': list_id
                    })
                    # Also set the file path directly so Kodi can use its native playback if needed
                    if media_dict.get('file'):
                        li.setPath(media_dict['file'])
                elif url and is_playable:
                    # For items with direct file paths, use them directly
                    pass
                elif not url or not is_playable:
                    # For items without valid play URLs, create a plugin URL that will show item details
                    url = build_plugin_url({
                        'action': 'show_item_details',
                        'list_id': list_id,
                        'item_id': media_dict.get('id'),
                        'title': media_dict.get('title', 'Unknown')
                    })
                    is_playable = False

                # Set playability properties
                if is_playable:
                    li.setProperty('IsPlayable', 'true')
                    playable_count += 1
                else:
                    li.setProperty('IsPlayable', 'false')
                    non_playable_count += 1

                # Add directory item with proper folder flag
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=not is_playable)
                items_added += 1
            except Exception as e:
                utils.log(f"Error processing item {i+1} ({media_dict.get('title', 'Unknown')}): {str(e)}", "ERROR")
                import traceback
                utils.log(f"Item processing traceback: {traceback.format_exc()}", "ERROR")

        utils.log(f"Successfully added {items_added} items ({playable_count} playable, {non_playable_count} non-playable)", "INFO")

        # Check if this is a search results list with scores to preserve order
        has_scores = any(item.get('search_score', 0) > 0 for item in display_items)

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
            utils.log(f"Enabled all sort methods for search results list {list_id} with score-based default order", "DEBUG")
        else:
            utils.log(f"Enabled all sort methods for regular list {list_id}", "DEBUG")

        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False, updateListing=True)
        utils.log(f"=== BROWSE_LIST ACTION COMPLETE for list_id={list_id} ===", "INFO")
    except Exception as e:
        utils.log(f"Error in browse_list: {e}", "ERROR")
        import traceback
        utils.log(f"browse_list traceback: {traceback.format_exc()}", "ERROR")
        # Show error item
        from resources.lib.listitem_builder import ListItemBuilder
        error_li = ListItemBuilder.build_folder_item(f"Error loading list: {str(e)}", is_folder=False)
        xbmcplugin.addDirectoryItem(handle, "", error_li, False)
        xbmcplugin.endOfDirectory(handle, succeeded=False)

def router(params):
    """Route requests to appropriate handlers"""

    # Clean up any stuck navigation flags at router entry
    nav_manager.cleanup_stuck_navigation()

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
            from resources.lib.window_search import SearchWindow
            search_window = SearchWindow()
            search_window.doModal()

            # Check if we need to navigate after search
            target_url = search_window.get_target_url()
            if target_url:
                utils.log(f"Navigating to search results: {target_url}", "DEBUG")
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
    elif action == 'search_movies':
        utils.log("Routing to search_movies action", "DEBUG")
        nav_manager.set_navigation_in_progress(True)
        do_search(q)
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

        # Check if this is a program addon launch (direct launch without context)
        if len(sys.argv) == 1 or (len(sys.argv) >= 2 and ('action=program' in str(sys.argv[1]) or 'action=program' in str(sys.argv))):
            utils.log("Program addon launch detected - showing main window", "DEBUG")
            from resources.lib.window_main import MainWindow

            # Create empty item info for program launch
            item_info = {
                'title': 'LibraryGenie Browser',
                'is_playable': False,
                'kodi_id': 0
            }

            main_window = MainWindow(item_info, "LibraryGenie - Browse Lists")
            main_window.doModal()
            del main_window
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