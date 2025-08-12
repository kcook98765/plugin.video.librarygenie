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

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

ADDON_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
PLUGIN_URL = sys.argv[0] if len(sys.argv) > 0 else ""

def _plugin_url(params: dict) -> str:
    """Build plugin URL with clean parameters (no empty values)"""
    # Drop None / '' / False and only encode the rest
    cleaned = {k: str(v) for k, v in params.items() if v not in (None, '', False)}
    addon_id = xbmcaddon.Addon().getAddonInfo('id')
    base_url = f"plugin://{addon_id}/"
    return base_url + ('?' + urlencode(cleaned, doseq=True) if cleaned else '')

def _detect_context(ctx_params: dict) -> dict:
    """
    Decide what screen we're on so we can tailor actions.
    view: root | lists | list | folder | search | other
    """
    view = ctx_params.get('view') or 'root'
    ctx = {'view': view}
    if 'list_id' in ctx_params:
        ctx['list_id'] = ctx_params.get('list_id')
    if 'folder' in ctx_params:
        ctx['folder'] = ctx_params.get('folder')
    return ctx

def add_options_header_item(ctx: dict):
    """Add the options and tools header item as a non-folder RunPlugin item"""
    try:
        # Check if navigation is in progress - skip adding options header during navigation
        navigating = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.Navigating)")
        if navigating == "true":
            utils.log("Navigation in progress, skipping options header item", "DEBUG")
            return

        # Create list item for options as non-folder
        li = xbmcgui.ListItem(label="[B]🔧 Options & Tools[/B]")
        li.setInfo('video', {
            'title': '🔧 Options & Tools',
            'plot': 'Access list management tools, search options, and addon settings.',
            'mediatype': 'video'
        })

        # Build URL with current context using centralized URL builder
        url = _plugin_url({
            'action': 'options',
            'view': ctx.get('view'),
            # Only include list_id/folder if they exist
            **({'list_id': ctx['list_id']} if ctx.get('list_id') else {}),
            **({'folder': ctx['folder']} if ctx.get('folder') else {}),
        })

        # Add as non-folder item so Kodi uses RunPlugin instead of trying to render directory
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=False)

    except Exception as e:
        utils.log(f"Error adding options header: {str(e)}", "ERROR")

def _add_context_menu_for_item(li: xbmcgui.ListItem, item_type: str, **ids):
    """
    Attach context actions per item type.
    item_type: 'list' | 'movie' | 'folder'
    ids may include: list_id, movie_id, folder
    """
    cm = []
    if item_type == 'list':
        list_id = ids.get('list_id', '')
        cm += [
            ('Rename list',
             f'RunPlugin({_plugin_url({"action":"rename_list","list_id":list_id})})'),
            ('Delete list',
             f'RunPlugin({_plugin_url({"action":"delete_list","list_id":list_id})})'),
        ]
    elif item_type == 'movie':
        list_id = ids.get('list_id', '')
        movie_id = ids.get('movie_id', '')
        cm += [
            ('Remove movie from list',
             f'RunPlugin({_plugin_url({"action":"remove_from_list","list_id":list_id,"movie_id":movie_id})})'),
            ('Refresh metadata',
             f'RunPlugin({_plugin_url({"action":"refresh_movie","movie_id":movie_id})})'),
        ]
    elif item_type == 'folder':
        folder = ids.get('folder', '')
        if folder:
            cm += [
                ('Rename folder',
                 f'RunPlugin({_plugin_url({"action":"rename_folder","folder":folder})})'),
            ]
    if cm:
        li.addContextMenuItems(cm, replaceItems=False)
    return li

from resources.lib.addon_helper import run_addon
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib import utils
from resources.lib.route_handlers import (
    play_movie, show_item_details, create_list, rename_list, delete_list,
    remove_from_list, rename_folder, refresh_movie, do_search
)

# Global variable to track initialization
_initialized = False

# Global navigation state to prevent dialog conflicts
_navigation_in_progress = False
_last_navigation_time = 0

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
        utils.log(f"=== PERFORMING DELAYED NAVIGATION TO: {target_url} ===", "DEBUG")
        # Set navigation flag
        xbmc.executebuiltin("SetProperty(LibraryGenie.NavInProgress,1,Home)")
        # Let GUI settle before navigation
        xbmc.sleep(100)
        # Navigate with proper quoting and replace parameter
        xbmc.executebuiltin(f'Container.Update("{target_url}", replace)')
        xbmc.sleep(50)
        # Clear navigation flag
        xbmc.executebuiltin("ClearProperty(LibraryGenie.NavInProgress,Home)")
        utils.log("=== DELAYED NAVIGATION COMPLETED ===", "DEBUG")
    else:
        utils.log("=== NO TARGET URL - SEARCH CANCELLED OR FAILED ===", "DEBUG")

    utils.log("=== RUN_SEARCH_FLOW COMPLETE ===", "DEBUG")

def run_search(params=None):
    """Legacy function - redirect to new flow"""
    run_search_flow()

def run_browse(params=None):
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

def browse_folder(folder_id):
    """Browse a specific folder"""
    import xbmcplugin
    import xbmcgui
    from resources.lib.addon_ref import get_addon
    from resources.lib.database_manager import DatabaseManager
    from resources.lib.config_manager import Config

    addon = get_addon()
    addon_id = addon.getAddonInfo("id")
    handle = int(sys.argv[1])

    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Add options header
        ctx = _detect_context({'view': 'folder', 'folder_id': str(folder_id)})
        add_options_header_item(ctx)

        # Get subfolders of this folder
        subfolders = db_manager.fetch_folders(folder_id)

        # Get lists in this folder
        folder_lists = db_manager.fetch_lists(folder_id)

        # Add subfolders
        for folder in subfolders:
            from resources.lib.listitem_builder import ListItemBuilder
            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            _add_context_menu_for_item(li, 'folder', folder_id=folder['id'])
            url = _plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Add lists in this folder
        for list_item in folder_lists:
            list_count = db_manager.get_list_media_count(list_item['id'])
            from resources.lib.listitem_builder import ListItemBuilder
            li = ListItemBuilder.build_folder_item(f"📋 {list_item['name']} ({list_count})", is_folder=True)
            li.setProperty('lg_type', 'list')
            _add_context_menu_for_item(li, 'list', list_id=list_item['id'])
            url = _plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    except Exception as e:
        utils.log(f"Error browsing folder {folder_id}: {str(e)}", "ERROR")

    xbmcplugin.endOfDirectory(handle)

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
        global _navigation_in_progress
        _navigation_in_progress = False
        xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
        utils.log("Cleared navigation flags at browse_list entry", "DEBUG")

        # Set proper container properties first
        xbmcplugin.setContent(handle, "movies")
        xbmcplugin.setPluginCategory(handle, f"Search Results")

        # Add options header
        ctx = _detect_context({'view': 'list', 'list_id': str(list_id)})
        add_options_header_item(ctx)
        utils.log(f"Added options header item", "DEBUG")

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
        for i, media in enumerate(display_items):
            utils.log(f"Processing item {i+1}/{len(display_items)}: {media.get('title', 'Unknown')}", "DEBUG")
            try:
                li = ListItemBuilder.build_video_item(media)
                li.setProperty('lg_type', 'movie')
                li.setProperty('lg_list_id', str(list_id))
                li.setProperty('lg_movie_id', str(media.get('id')))
                _add_context_menu_for_item(li, 'movie', list_id=list_id, movie_id=media.get('id'))

                # Determine the URL and playability
                url = media.get('file') or media.get('play') or ''
                is_playable = False
                movie_id = None

                # Check if we have a valid Kodi ID for playable content
                if media.get('movieid') and str(media['movieid']).isdigit() and int(media['movieid']) > 0:
                    movie_id = int(media['movieid'])
                    is_playable = True
                    utils.log(f"Item {i+1}: Using Kodi movieid {movie_id} for playback", "DEBUG")
                elif media.get('kodi_id') and str(media['kodi_id']).isdigit() and int(media['kodi_id']) > 0:
                    movie_id = int(media['kodi_id'])
                    is_playable = True
                    utils.log(f"Item {i+1}: Using Kodi kodi_id {movie_id} for playback", "DEBUG")
                elif url:
                    is_playable = True
                    utils.log(f"Item {i+1}: Using existing URL for playback: {url}", "DEBUG")

                # For Kodi library items, create a plugin URL that will handle playback
                if movie_id and is_playable:
                    url = _plugin_url({
                        'action': 'play_movie',
                        'movieid': movie_id,
                        'list_id': list_id
                    })
                    # Also set the file path directly so Kodi can use its native playback if needed
                    if media.get('file'):
                        li.setPath(media['file'])
                    utils.log(f"Item {i+1}: Created plugin playback URL for Kodi movie {movie_id}: {url}", "DEBUG")
                elif url and is_playable:
                    # For items with direct file paths, use them directly
                    utils.log(f"Item {i+1}: Using direct file path for playback: {url}", "DEBUG")
                elif not url or not is_playable:
                    # For items without valid play URLs, create a plugin URL that will show item details
                    url = _plugin_url({
                        'action': 'show_item_details',
                        'list_id': list_id,
                        'item_id': media.get('id'),
                        'title': media.get('title', 'Unknown')
                    })
                    is_playable = False
                    utils.log(f"Item {i+1}: Created details URL for non-playable item: {url}", "DEBUG")

                # Set playability properties
                if is_playable:
                    li.setProperty('IsPlayable', 'true')
                else:
                    li.setProperty('IsPlayable', 'false')

                # Log the item being added for debugging
                utils.log(f"Adding item {i+1}: title='{media.get('title', 'Unknown')}', url='{url}', isFolder={not is_playable}, playable={is_playable}", "DEBUG")

                # Add directory item with proper folder flag
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=not is_playable)
                items_added += 1
                utils.log(f"Successfully added item {i+1}: {media.get('title', 'Unknown')} (playable: {is_playable})", "DEBUG")
            except Exception as e:
                utils.log(f"Error processing item {i+1} ({media.get('title', 'Unknown')}): {str(e)}", "ERROR")
                import traceback
                utils.log(f"Item processing traceback: {traceback.format_exc()}", "ERROR")

        utils.log(f"Successfully added {items_added} out of {len(display_items)} items to directory", "INFO")

        # Always complete directory - this route must always produce a directory
        if items_added > 0:
            utils.log("Completing directory with items", "DEBUG")
            xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_TITLE)
            xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False, updateListing=True)
        else:
            utils.log("No items added - showing empty message", "WARNING")
            from resources.lib.listitem_builder import ListItemBuilder
            empty_li = ListItemBuilder.build_folder_item("No movies found in this list", is_folder=False)
            xbmcplugin.addDirectoryItem(handle, "", empty_li, False)
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


def build_root():
    """Build the root directory with search option"""
    import xbmcplugin
    import xbmcgui
    from resources.lib.addon_ref import get_addon

    addon = get_addon()
    addon_id = addon.getAddonInfo("id")
    handle = int(sys.argv[1])

    # Add options header
    ctx = _detect_context({'view': 'root'})
    add_options_header_item(ctx)

    # Legacy search and browse items removed - now available via Options & Tools

    # Add list and folder items here based on existing database content
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get top-level folders
        top_level_folders = db_manager.fetch_folders(None) # None for root

        # Get top-level lists
        top_level_lists = db_manager.fetch_lists(None) # None for root

        # Import set_info_tag for list item creation
        from resources.lib.listitem_infotagvideo import set_info_tag

        # Import ListItemBuilder
        from resources.lib.listitem_builder import ListItemBuilder

        # Add top-level folders
        for folder in top_level_folders:
            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            _add_context_menu_for_item(li, 'folder', folder_id=folder['id'])
            url = _plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Add top-level lists
        for list_item in top_level_lists:
            list_count = db_manager.get_list_media_count(list_item['id'])
            li = ListItemBuilder.build_folder_item(f"📋 {list_item['name']} ({list_count})", is_folder=True)
            li.setProperty('lg_type', 'list')
            _add_context_menu_for_item(li, 'list', list_id=list_item['id'])
            url = _plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    except Exception as e:
        utils.log(f"Error populating root directory with lists/folders: {str(e)}", "ERROR")

    xbmcplugin.endOfDirectory(handle)

def router(params):
    """Route plugin calls to appropriate handlers"""
    global _navigation_in_progress
    utils.log(f"Router called with params: {params}", "DEBUG")

    # Clean up any stuck navigation flags at router entry
    try:
        import time
        current_time = time.time()
        last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
        time_since_nav = current_time - last_navigation

        if time_since_nav > 15.0:  # Clear flags if stuck for more than 15 seconds
            utils.log(f"=== ROUTER: CLEARING STUCK NAVIGATION FLAGS (stuck for {time_since_nav:.1f}s) ===", "DEBUG")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
            _navigation_in_progress = False
    except (ValueError, TypeError):
        pass

    # Handle deferred option execution from RunScript
    if isinstance(params, str) and params.startswith('deferred_option'):
        utils.log("=== HANDLING DEFERRED OPTION EXECUTION ===", "DEBUG")
        try:
            # Extract option index from params
            parts = params.split(',')
            if len(parts) >= 2:
                option_index = int(parts[1])
                execute_deferred_option(option_index)
            else:
                utils.log("Invalid deferred option format", "ERROR")
        except Exception as e:
            utils.log(f"Error in deferred option execution: {str(e)}", "ERROR")
        return

    # Check if paramstr is valid and not empty before parsing
    if not params:
        utils.log("Received empty paramstr, building root directory.", "WARNING")
        # Clear navigation flags when building root
        xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
        xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
        _navigation_in_progress = False
        build_root()
        return

    # Ensure we are parsing the query string part of the URL
    try:
        # Handle both full URLs and query strings
        if params.startswith('?'):
            query_string = params[1:]  # Remove leading '?'
        else:
            parsed_url = urlparse(params)
            query_string = parsed_url.query

        q = parse_qs(query_string) if query_string else {}
    except Exception as e:
        utils.log(f"Error parsing paramstr '{params}': {str(e)}", "ERROR")
        build_root() # Fallback to building root on parsing error
        return

    action = q.get("action", [""])[0]

    utils.log(f"Action determined: {action}", "DEBUG")

    if action == "search":
        utils.log("Routing to search action", "DEBUG")
        # Set navigation flag before starting search
        _navigation_in_progress = True
        xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
        run_search()
        return
    elif action == "browse":
        utils.log("Routing to browse action", "DEBUG")
        # Set navigation flag before starting browse
        _navigation_in_progress = True
        xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
        run_browse()
        return
    elif action == 'options':
        utils.log("Routing to options action", "DEBUG")
        # Check if we're in the middle of navigation to prevent dialog conflicts
        if _navigation_in_progress:
            utils.log("Navigation in progress, skipping options dialog", "DEBUG")
            return
        show_options(q)
        # IMPORTANT: Do NOT call endOfDirectory() here - this is a RunPlugin action
        return
    elif action == 'search_movies':
        utils.log("Routing to search_movies action", "DEBUG")
        # Set navigation flag before starting search
        _navigation_in_progress = True
        xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
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
    elif action == 'browse_folder':
        utils.log("Routing to browse_folder action", "DEBUG")
        folder_id = q.get('folder_id', [None])[0]
        if folder_id:
            # Clear navigation flag when we reach the target
            _navigation_in_progress = False
            xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
            browse_folder(int(folder_id))
        else:
            utils.log("Missing folder_id for browse_folder action, returning to root.", "WARNING")
            build_root()
        return
    elif action == 'browse_list':
        list_id = q.get('list_id', [None])[0]
        if list_id:
            # Set proper content for list view
            xbmcplugin.setPluginCategory(ADDON_HANDLE, "Search Results")
            xbmcplugin.setContent(ADDON_HANDLE, "movies")
            # Clear navigation flag when we reach the target
            _navigation_in_progress = False
            xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
            browse_list(list_id)
        else:
            utils.log("No list_id provided for browse_list action", "WARNING")
            show_empty_directory()
        return
    elif action == 'separator':
        # Do nothing for separator items
        utils.log("Received separator action, doing nothing.", "DEBUG")
        pass
    else:
        # Default: build root directory if action is not recognized or empty
        utils.log(f"Unrecognized action '{action}' or no action specified, building root directory.", "DEBUG")
        build_root()

def show_options(params):
    """Show the Options & Tools menu"""
    utils.log("=== OPTIONS DIALOG REQUEST START ===", "DEBUG")
    utils.log("Showing Options & Tools menu", "DEBUG")

    # Get current window info for debugging
    current_window_id = xbmcgui.getCurrentWindowId()
    utils.log(f"Current window ID before options: {current_window_id}", "DEBUG")

    # Check for navigation protection with automatic cleanup
    navigation_active = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.Navigating)")
    if navigation_active == "true":
        # Check if navigation has been stuck for too long (more than 10 seconds)
        try:
            import time
            current_time = time.time()
            last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
            time_since_nav = current_time - last_navigation

            if time_since_nav > 10.0:  # Clear stuck navigation flag after 10 seconds
                utils.log(f"=== CLEARING STUCK NAVIGATION FLAG (stuck for {time_since_nav:.1f}s) ===", "WARNING")
                xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
                xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
            else:
                utils.log(f"=== OPTIONS BLOCKED: NAVIGATION IN PROGRESS ({time_since_nav:.1f}s) ===", "WARNING")
                return
        except (ValueError, TypeError):
            # If we can't get timestamps, clear the flag anyway
            utils.log("=== CLEARING NAVIGATION FLAG (timestamp error) ===", "WARNING")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")

    # Time-based protection to prevent immediate re-triggering after navigation
    try:
        last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
        import time
        current_time = time.time()
        time_since_nav = current_time - last_navigation

        if time_since_nav < 3.0:  # Increased back to 3 seconds for better stability
            utils.log(f"=== OPTIONS BLOCKED: TOO SOON AFTER NAVIGATION ({time_since_nav:.1f}s) ===", "WARNING")
            return
    except (ValueError, TypeError):
        pass  # If property doesn't exist or isn't a number, continue

    # Additional protection: check if we just completed a search
    try:
        search_modal_active = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.SearchModalActive)")
        if search_modal_active == "true":
            utils.log("=== OPTIONS BLOCKED: SEARCH MODAL STILL ACTIVE ===", "WARNING")
            return
    except:
        pass

    utils.log(f"Current window ID: {current_window_id}", "DEBUG")

    options = [
        "- Search Movies",
        "- Browse Lists",
        "- Create New List",
        "- Create New Folder",
        "- Upload Library to Server (Full)",
        "- Sync Library with Server (Delta)",
        "- View Upload Status",
        "- Clear Server Library",
        "- Clear All Local Data",
        "- Settings",
        "- Authenticate with Server"
    ]

    try:
        utils.log("=== ABOUT TO SHOW OPTIONS MODAL DIALOG ===", "DEBUG")
        utils.log(f"Pre-modal window state: {xbmcgui.getCurrentWindowId()}", "DEBUG")
        utils.log("=== CREATING xbmcgui.Dialog() INSTANCE ===", "DEBUG")

        # Use a timeout mechanism to prevent hanging
        dialog_start_time = time.time()
        dialog = xbmcgui.Dialog()
        utils.log("=== CALLING dialog.select() METHOD ===", "DEBUG")

        # Set a property to track dialog state
        xbmc.executebuiltin("SetProperty(LibraryGenie.DialogActive,true,Home)")

        selected_option = dialog.select("LibraryGenie - Options & Tools", options)

        # Clear dialog state property
        xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")

        dialog_duration = time.time() - dialog_start_time
        utils.log(f"=== OPTIONS MODAL DIALOG CLOSED, SELECTION: {selected_option}, DURATION: {dialog_duration:.1f}s ===", "DEBUG")
        utils.log(f"Post-modal window state: {xbmcgui.getCurrentWindowId()}", "DEBUG")

        # Check for timeout condition
        if dialog_duration > 4.0:  # If dialog took more than 4 seconds
            utils.log(f"=== WARNING: Dialog took {dialog_duration:.1f}s - near timeout threshold ===", "WARNING")

    except Exception as e:
        utils.log(f"=== ERROR IN OPTIONS DIALOG CREATION: {str(e)} ===", "ERROR")
        xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
        return

    if selected_option == -1:
        utils.log("User cancelled options menu", "DEBUG")
        utils.log("=== OPTIONS DIALOG CANCELLED BY USER ===", "DEBUG")
        # Clear any lingering properties
        xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
        return

    # Early validation
    if selected_option < 0 or selected_option >= len(options):
        utils.log(f"Invalid option selected: {selected_option}", "ERROR")
        xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
        return

    selected_text = options[selected_option]
    utils.log(f"User selected option: {selected_text}", "DEBUG")
    utils.log(f"=== EXECUTING SELECTED OPTION: {selected_text} ===", "DEBUG")

    # Check remaining time budget
    execution_start_time = time.time()
    remaining_time = 4.0 - (execution_start_time - dialog_start_time)

    if remaining_time < 1.0:  # Less than 1 second left
        utils.log(f"=== INSUFFICIENT TIME REMAINING ({remaining_time:.1f}s) - DEFERRING EXECUTION ===", "WARNING")
        # Defer execution using RunScript to avoid timeout
        # Use the correct addon format for RunScript
        xbmc.executebuiltin(f"RunScript(plugin.video.librarygenie,deferred_option,{selected_option})")
        return

    # Minimal dialog cleanup before option execution
    utils.log("=== QUICK DIALOG CLEANUP BEFORE OPTION EXECUTION ===", "DEBUG")
    xbmc.executebuiltin("Dialog.Close(all,true)")
    xbmc.sleep(50)
    utils.log("=== COMPLETED QUICK CLEANUP ===", "DEBUG")

    try:
        if "Search Movies" in selected_text:
            utils.log("=== EXECUTING: SEARCH MOVIES ===", "DEBUG")
            utils.log("=== ABOUT TO CALL run_search_flow() - MODAL WILL OPEN ===", "DEBUG")
            run_search_flow()
            utils.log("=== COMPLETED: SEARCH MOVIES - ALL MODALS CLOSED ===", "DEBUG")
        elif "Browse Lists" in selected_text:
            utils.log("=== EXECUTING: BROWSE LISTS ===", "DEBUG")
            utils.log("=== ABOUT TO CALL run_browse() - MODAL WILL OPEN ===", "DEBUG")
            run_browse()
            utils.log("=== COMPLETED: BROWSE LISTS - ALL MODALS CLOSED ===", "DEBUG")
        elif "Create New List" in selected_text:
            utils.log("=== EXECUTING: CREATE NEW LIST ===", "DEBUG")
            utils.log("=== ABOUT TO CALL create_list() - MODAL WILL OPEN ===", "DEBUG")
            create_list({})
            utils.log("=== COMPLETED: CREATE NEW LIST - ALL MODALS CLOSED ===", "DEBUG")
        elif "Create New Folder" in selected_text:
            utils.log("=== EXECUTING: CREATE NEW FOLDER ===", "DEBUG")
            utils.log("=== ABOUT TO CALL create_new_folder_at_root() - MODAL WILL OPEN ===", "DEBUG")
            create_new_folder_at_root()
            utils.log("=== COMPLETED: CREATE NEW FOLDER - ALL MODALS CLOSED ===", "DEBUG")
        elif "Upload Library to Server (Full)" in selected_text:
            utils.log("=== EXECUTING: FULL LIBRARY UPLOAD ===", "DEBUG")
            utils.log("=== LIBRARY UPLOAD MAY SHOW PROGRESS MODALS ===", "DEBUG")
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.upload_library_full_sync()
            utils.log("=== COMPLETED: FULL LIBRARY UPLOAD - ALL MODALS CLOSED ===", "DEBUG")
        elif "Sync Library with Server (Delta)" in selected_text:
            utils.log("=== EXECUTING: DELTA LIBRARY SYNC ===", "DEBUG")
            utils.log("=== DELTA SYNC MAY SHOW PROGRESS MODALS ===", "DEBUG")
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.upload_library_delta_sync()
            utils.log("=== COMPLETED: DELTA LIBRARY SYNC - ALL MODALS CLOSED ===", "DEBUG")
        elif "View Upload Status" in selected_text:
            utils.log("=== EXECUTING: VIEW UPLOAD STATUS ===", "DEBUG")
            utils.log("=== UPLOAD STATUS WILL SHOW INFO MODAL ===", "DEBUG")
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.get_upload_status()
            utils.log("=== COMPLETED: VIEW UPLOAD STATUS - INFO MODAL CLOSED ===", "DEBUG")
        elif "Clear Server Library" in selected_text:
            utils.log("=== EXECUTING: CLEAR SERVER LIBRARY ===", "DEBUG")
            utils.log("=== CLEAR SERVER MAY SHOW CONFIRMATION MODAL ===", "DEBUG")
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.clear_server_library()
            utils.log("=== COMPLETED: CLEAR SERVER LIBRARY - ALL MODALS CLOSED ===", "DEBUG")
        elif "Clear All Local Data" in selected_text:
            utils.log("=== EXECUTING: CLEAR ALL LOCAL DATA ===", "DEBUG")
            utils.log("=== ABOUT TO CALL clear_all_local_data() - CONFIRMATION MODAL WILL OPEN ===", "DEBUG")
            clear_all_local_data()
            utils.log("=== COMPLETED: CLEAR ALL LOCAL DATA - ALL MODALS CLOSED ===", "DEBUG")
        elif "Settings" in selected_text:
            utils.log("=== EXECUTING: OPEN SETTINGS ===", "DEBUG")
            utils.log("=== ABOUT TO OPEN SETTINGS WINDOW ===", "DEBUG")
            xbmc.executebuiltin("Addon.OpenSettings(plugin.video.librarygenie)")
            utils.log("=== COMPLETED: OPEN SETTINGS - SETTINGS WINDOW CLOSED ===", "DEBUG")
        elif "Authenticate with Server" in selected_text:
            utils.log("=== EXECUTING: AUTHENTICATE WITH SERVER ===", "DEBUG")
            utils.log("=== ABOUT TO CALL authenticate_with_code() - INPUT MODAL WILL OPEN ===", "DEBUG")
            from resources.lib.authenticate_code import authenticate_with_code
            authenticate_with_code()
            utils.log("=== COMPLETED: AUTHENTICATE WITH SERVER - ALL MODALS CLOSED ===", "DEBUG")
        else:
            utils.log(f"=== UNKNOWN OPTION SELECTED: {selected_text} ===", "WARNING")

    except Exception as e:
        utils.log(f"=== ERROR EXECUTING SELECTED OPTION: {str(e)} ===", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
    finally:
        # Note: Navigation flag is now handled in individual flows (like run_search_flow)
        utils.log("=== OPTIONS DIALOG REQUEST COMPLETE ===", "DEBUG")

def execute_deferred_option(option_index):
    """Execute an option that was deferred due to timeout concerns"""
    utils.log(f"=== EXECUTING DEFERRED OPTION {option_index} ===", "DEBUG")

    options = [
        "- Search Movies",
        "- Browse Lists",
        "- Create New List",
        "- Create New Folder",
        "- Upload Library to Server (Full)",
        "- Sync Library with Server (Delta)",
        "- View Upload Status",
        "- Clear Server Library",
        "- Clear All Local Data",
        "- Settings",
        "- Authenticate with Server"
    ]

    if option_index < 0 or option_index >= len(options):
        utils.log(f"Invalid deferred option index: {option_index}", "ERROR")
        return

    selected_text = options[option_index]
    utils.log(f"Executing deferred option: {selected_text}", "DEBUG")

    try:
        # Execute the option with the same logic as show_options
        if "Search Movies" in selected_text:
            utils.log("=== DEFERRED: EXECUTING SEARCH MOVIES ===", "DEBUG")
            run_search()
        elif "Browse Lists" in selected_text:
            utils.log("=== DEFERRED: EXECUTING BROWSE LISTS ===", "DEBUG")
            run_browse()
        elif "Create New List" in selected_text:
            utils.log("=== DEFERRED: EXECUTING CREATE NEW LIST ===", "DEBUG")
            create_list({})
        elif "Create New Folder" in selected_text:
            utils.log("=== DEFERRED: EXECUTING CREATE NEW FOLDER ===", "DEBUG")
            create_new_folder_at_root()
        elif "Settings" in selected_text:
            utils.log("=== DEFERRED: EXECUTING OPEN SETTINGS ===", "DEBUG")
            xbmc.executebuiltin("Addon.OpenSettings(plugin.video.librarygenie)")
        # Add other options as needed...
        else:
            utils.log(f"=== DEFERRED OPTION NOT IMPLEMENTED: {selected_text} ===", "WARNING")

    except Exception as e:
        utils.log(f"Error in deferred option execution: {str(e)}", "ERROR")

def _close_all_dialogs():
    """Close all open dialogs with minimal cleanup"""
    utils.log("=== STARTING MINIMAL DIALOG CLOSURE ===", "DEBUG")

    # Simple single dialog close
    xbmc.executebuiltin("Dialog.Close(all,true)")
    utils.log("=== EXECUTED Dialog.Close(all,true) ===", "DEBUG")
    xbmc.sleep(100)  # Short wait

    utils.log("=== DIALOG CLOSURE COMPLETE ===", "DEBUG")


def create_new_folder_at_root():
    """Create a new folder at root level"""
    utils.log("=== CREATE_NEW_FOLDER: ABOUT TO SHOW INPUT MODAL ===", "DEBUG")
    name = xbmcgui.Dialog().input('New folder name', type=xbmcgui.INPUT_ALPHANUM)
    utils.log("=== CREATE_NEW_FOLDER: INPUT MODAL CLOSED ===", "DEBUG")
    if not name:
        utils.log("CREATE_NEW_FOLDER: No name entered, cancelling", "DEBUG")
        return
    try:
        from resources.lib.database_manager import DatabaseManager
        from resources.lib.config_manager import Config
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Create in root folder (None parent)
        db_manager.insert_folder(name, None)
        utils.log("=== CREATE_NEW_FOLDER: ABOUT TO SHOW SUCCESS NOTIFICATION ===", "DEBUG")
        xbmcgui.Dialog().notification('LibraryGenie', f'Folder "{name}" created')
        utils.log("=== CREATE_NEW_FOLDER: SUCCESS NOTIFICATION CLOSED ===", "DEBUG")
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error creating folder: {str(e)}", "ERROR")
        utils.log("=== CREATE_NEW_FOLDER: ABOUT TO SHOW ERROR NOTIFICATION ===", "DEBUG")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create folder')
        utils.log("=== CREATE_NEW_FOLDER: ERROR NOTIFICATION CLOSED ===", "DEBUG")

def clear_all_local_data():
    """Clear all local folders/lists data but preserve IMDB exports"""
    from resources.lib.addon_helper import clear_all_local_data as clear_data
    clear_data()

def main():
    """Main addon entry point"""
    utils.log("=== LibraryGenie addon starting ===", "INFO")
    utils.log(f"Command line args: {sys.argv}", "DEBUG")

    try:
        utils.log("Initializing addon components", "DEBUG")

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
        # This initialization should probably happen earlier or be handled by Config/DBManager on first use.
        # For now, keeping it here as per original structure.
        utils.log("Setting up configuration and database for first run", "DEBUG")
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        utils.log("Configuration and database setup complete", "DEBUG")

        utils.log("=== LibraryGenie addon startup complete ===", "INFO")
    except Exception as e:
        utils.log(f"CRITICAL ERROR in main(): {str(e)}", "ERROR")
        import traceback
        utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

if __name__ == '__main__':
    main()

def show_empty_directory():
    """Show an empty directory message"""
    try:
        from resources.lib.listitem_builder import ListItemBuilder
        li = ListItemBuilder.build_folder_item("Directory is empty", is_folder=False)
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, "", li, False)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
    except Exception as e:
        utils.log(f"Error showing empty directory: {str(e)}", "ERROR")

# Helper class for Kodi list item management
class KodiHelper:
    def __init__(self, handle):
        self.handle = handle

    def list_items(self, items):
        """Add multiple directory items to Kodi listing."""
        for item_data in items:
            try:
                li = xbmcgui.ListItem(label=item_data.get('title', 'Unknown'))
                li.setInfo('video', {
                    'title': item_data.get('title', 'Unknown'),
                    'plot': item_data.get('plot', ''),
                    'year': item_data.get('year', 0),
                    'genre': item_data.get('genre', ''),
                    'rating': item_data.get('rating', 0.0),
                    'mediatype': 'video'
                })

                # Set artwork
                art = item_data.get('art', {})
                art_dict = {
                    'icon': art.get('thumb', ''),
                    'thumb': art.get('thumb', ''),
                    'poster': art.get('poster', ''),
                    'fanart': art.get('fanart', '')
                }
                # Filter out empty values
                art_dict = {k: v for k, v in art_dict.items() if v}
                if art_dict:
                    li.setArt(art_dict)

                # Determine play URL
                play_url = item_data.get('file', item_data.get('play'))
                if not play_url and item_data.get('imdb'):
                    # If no direct URL, use a plugin call for playback
                    play_url = _plugin_url({'action': 'play_movie', 'imdb_id': item_data.get('imdb')})
                elif not play_url and item_data.get('kodi_id'):
                    # Fallback to kodi_id if available
                    play_url = _plugin_url({'action': 'play_movie', 'movieid': item_data.get('kodi_id')})

                # Add directory item
                if play_url:
                    xbmcplugin.addDirectoryItem(self.handle, play_url, li, isFolder=False)
                else:
                    # If no play URL can be determined, still add as a folder to allow context menu
                    utils.log(f"No play URL found for item: {item_data.get('title')}. Adding as folder.", "WARNING")
                    xbmcplugin.addDirectoryItem(self.handle, "", li, isFolder=True)

            except Exception as e:
                utils.log(f"Error processing item for Kodi listing: {str(e)}", "ERROR")

# Placeholder for browse_list_action function
# This function is called by router, and its implementation should be correct.
# The changes from the prompt should have already been integrated into the main function.
def browse_list_action(list_id):
    """Browse items in a specific list"""
    try:
        # Get database manager
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get list details and items
        list_details = db_manager.get_list_details(list_id)
        if not list_details:
            utils.log(f"List with ID {list_id} not found", "ERROR")
            show_empty_directory()
            return

        # Set the plugin category to the list name
        xbmcplugin.setPluginCategory(ADDON_HANDLE, list_details['name'])

        # Add options and tools header
        add_options_header_item({'view': 'list', 'list_id': str(list_id)})

        # Get list items
        list_items = db_manager.get_list_items(list_id)
        utils.log(f"Retrieved {len(list_items)} items for list {list_id}", "DEBUG")

        # Build items for display
        kodi_helper = KodiHelper(ADDON_HANDLE)
        items = []

        for list_item in list_items:
            media_item = db_manager.get_media_item(list_item['media_item_id'])
            if media_item:
                # Convert database item to display format
                item = {
                    'id': media_item['id'],
                    'title': media_item.get('title', 'Unknown'),
                    'plot': media_item.get('plot', ''),
                    'year': media_item.get('year', 0),
                    'genre': media_item.get('genre', ''),
                    'rating': media_item.get('rating', 0.0),
                    'imdb': media_item.get('imdbnumber', ''),
                    'art': {
                        'poster': media_item.get('art_poster', ''),
                        'fanart': media_item.get('art_fanart', ''),
                        'thumb': media_item.get('art_thumb', '')
                    }
                }
                items.append(item)

        # Display items
        if items:
            kodi_helper.list_items(items)
        else:
            # Add "No items found" entry
            from resources.lib.listitem_builder import ListItemBuilder
            list_item = ListItemBuilder.build_folder_item("No items found in this list", is_folder=False)
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, "", list_item, False)

        # Finish with proper list container behavior
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, updateListing=True, cacheToDisc=False)

    except Exception as e:
        utils.log(f"Error in browse_list_action: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
        show_empty_directory()