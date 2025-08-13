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
import time # Import time for timestamp operations

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
    """Add the options and tools header item that navigates to options directory"""
    try:
        # Create list item for options that navigates to options directory
        li = xbmcgui.ListItem(label="[B]🔧 Options & Tools[/B]")
        li.setInfo('video', {
            'title': '🔧 Options & Tools',
            'plot': 'Access list management tools, search options, and addon settings.',
            'mediatype': 'video'
        })

        # Build URL for options directory
        url = _plugin_url({'action': 'options'})

        # Add as folder item so it navigates to options directory
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)

    except Exception as e:
        utils.log(f"Error adding options header: {str(e)}", "ERROR")

def _get_folder_breadcrumb(db_manager, folder_id):
    """Build breadcrumb path for folder hierarchy"""
    breadcrumbs = ["LibraryGenie"]

    if folder_id:
        folder_path = []
        current_folder_id = folder_id

        # Build path from current folder to root
        while current_folder_id:
            folder = db_manager.fetch_folder_by_id(current_folder_id)
            if folder:
                folder_path.insert(0, folder['name'])
                current_folder_id = folder['parent_id']
            else:
                break

        breadcrumbs.extend(folder_path)

    return " / ".join(breadcrumbs)

def _get_list_breadcrumb(query_manager, list_id):
    """Build breadcrumb path for list including its folder hierarchy"""
    breadcrumbs = ["LibraryGenie"]

    if list_id:
        from resources.lib.database_manager import DatabaseManager
        from resources.lib.config_manager import Config

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get list info
        list_info = db_manager.fetch_list_by_id(list_id)
        if list_info:
            folder_id = list_info.get('folder_id')

            # Build folder hierarchy if list is in a folder
            if folder_id:
                folder_path = []
                current_folder_id = folder_id

                while current_folder_id:
                    folder = db_manager.fetch_folder_by_id(current_folder_id)
                    if folder:
                        folder_path.insert(0, folder['name'])
                        current_folder_id = folder['parent_id']
                    else:
                        break

                breadcrumbs.extend(folder_path)

            # Add list name
            breadcrumbs.append(list_info['name'])

    return " / ".join(breadcrumbs)

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
            ('Move list',
             f'RunPlugin({_plugin_url({"action":"move_list","list_id":list_id})})'),
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
    remove_from_list, rename_folder, refresh_movie, do_search, move_list
)

# Global variable to track initialization
_initialized = False

# Global navigation state to prevent dialog conflicts
_navigation_in_progress = False
_last_navigation_time = 0

def run_search_flow():
    """Launch search modal and navigate to results after completion"""
    global _navigation_in_progress
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
        utils.log("=== DELAYEDNAVIGATION COMPLETED ===", "DEBUG")
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

    utils.log(f"=== BROWSE_FOLDER FUNCTION CALLED with folder_id={folder_id}, handle={handle} ===", "INFO")

    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Set breadcrumb with folder hierarchy
        folder_breadcrumb = _get_folder_breadcrumb(db_manager, folder_id)
        xbmcplugin.setPluginCategory(handle, folder_breadcrumb)
        # Set content type to ensure proper display
        xbmcplugin.setContent(handle, "files")

        utils.log(f"Set breadcrumb: {folder_breadcrumb}", "DEBUG")

        # Add options header
        ctx = {'view': 'folder', 'folder_id': str(folder_id)}
        add_options_header_item(ctx)

        # Get subfolders of this folder
        subfolders = db_manager.fetch_folders(folder_id)
        utils.log(f"Found {len(subfolders)} subfolders", "DEBUG")

        # Get lists in this folder
        folder_lists = db_manager.fetch_lists(folder_id)
        utils.log(f"Found {len(folder_lists)} lists in folder", "DEBUG")

        items_added = 0

        # Add subfolders
        for folder in subfolders:
            from resources.lib.listitem_builder import ListItemBuilder
            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            _add_context_menu_for_item(li, 'folder', folder_id=folder['id'])
            url = _plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
            items_added += 1
            utils.log(f"Added subfolder: {folder['name']}", "DEBUG")

        # Add lists in this folder
        for list_item in folder_lists:
            list_count = db_manager.get_list_media_count(list_item['id'])
            from resources.lib.listitem_builder import ListItemBuilder
            li = ListItemBuilder.build_list_item(f"📋 {list_item['name']} ({list_count})", is_folder=True, list_data=list_item)
            li.setProperty('lg_type', 'list')
            _add_context_menu_for_item(li, 'list', list_id=list_item['id'])
            url = _plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
            items_added += 1
            utils.log(f"Added list: {list_item['name']} ({list_count})", "DEBUG")

        if items_added == 0:
            # Add empty message
            from resources.lib.listitem_builder import ListItemBuilder
            li = ListItemBuilder.build_folder_item("This folder is empty", is_folder=False)
            xbmcplugin.addDirectoryItem(handle, "", li, isFolder=False)

        utils.log(f"Successfully added {items_added} items to folder directory", "INFO")

    except Exception as e:
        utils.log(f"Error browsing folder {folder_id}: {str(e)}", "ERROR")
        import traceback
        utils.log(f"browse_folder traceback: {traceback.format_exc()}", "ERROR")

    xbmcplugin.endOfDirectory(handle, succeeded=True)

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
        _navigation_in_progress = False
        xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
        utils.log("Cleared navigation flags at browse_list entry", "DEBUG")

        # Set proper container properties first
        xbmcplugin.setContent(handle, "movies")

        # Set breadcrumb with list name and folder hierarchy
        list_breadcrumb = _get_list_breadcrumb(query_manager, list_id)
        xbmcplugin.setPluginCategory(handle, list_breadcrumb)

        # Add options header
        ctx = {'view': 'list', 'list_id': str(list_id)}
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

    # Set LibraryGenie as the main breadcrumb - this replaces "Videos"
    xbmcplugin.setPluginCategory(handle, "LibraryGenie")
    # Also set content type to ensure proper display
    xbmcplugin.setContent(handle, "files")

    # Add options header
    ctx = {'view': 'root'}
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
            li = ListItemBuilder.build_list_item(f"📋 {list_item['name']} ({list_count})", is_folder=True)
            li.setProperty('lg_type', 'list')
            _add_context_menu_for_item(li, 'list', list_id=list_item['id'])
            url = _plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    except Exception as e:
        utils.log(f"Error populating root directory with lists/folders: {str(e)}", "ERROR")

    xbmcplugin.endOfDirectory(handle)

def router(params):
    """Route requests to appropriate handlers"""
    global _navigation_in_progress
    utils.log(f"Router called with params: {params}", "DEBUG")

    # Clear any stuck navigation flags that are more than 30 seconds old
    try:
        current_time = time.time()
        last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
        time_since_nav = current_time - last_navigation
        if time_since_nav > 30:  # More than 30 seconds stuck
            utils.log(f"=== ROUTER: CLEARING STUCK NAVIGATION FLAGS (stuck for {time_since_nav}s) ===", "DEBUG")
            xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,false,Home)")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.LastNavigation,Home)")
            _navigation_in_progress = False
    except Exception:
        pass  # Ignore any errors in cleanup

    action = None

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

    action_type = q.get("action", [""])[0]

    utils.log(f"Action type determined: {action_type}", "DEBUG")

    if action_type == "search":
        utils.log("Routing to search action", "DEBUG")
        # Set navigation flag before starting search
        _navigation_in_progress = True
        xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
        run_search()
        return
    elif action_type == "browse":
        utils.log("Routing to browse action", "DEBUG")
        # Set navigation flag before starting browse
        _navigation_in_progress = True
        xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
        run_browse()
        return
    elif action_type == 'options':
        utils.log("Routing to options action", "DEBUG")
        # Check if we're in the middle of navigation to prevent dialog conflicts
        if _navigation_in_progress:
            utils.log("Navigation in progress, skipping options dialog", "DEBUG")
            return
        show_options(q)
        # IMPORTANT: Do NOT call endOfDirectory() here - this is a RunPlugin action
        return
    elif action_type == 'search_movies':
        utils.log("Routing to search_movies action", "DEBUG")
        # Set navigation flag before starting search
        _navigation_in_progress = True
        xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
        do_search(q)
        return
    elif action_type == 'create_list':
        utils.log("Routing to create_list action", "DEBUG")
        create_list(q)
        return
    elif action_type == 'rename_list':
        utils.log("Routing to rename_list action", "DEBUG")
        rename_list(q)
        return
    elif action_type == "move_list":
        utils.log("Routing to move_list action", "DEBUG")
        move_list(q)
        return
    elif action_type == 'delete_list':
        utils.log("Routing to delete_list action", "DEBUG")
        delete_list(q)
        return
    elif action_type == 'remove_from_list':
        utils.log("Routing to remove_from_list action", "DEBUG")
        remove_from_list(q)
        return
    elif action_type == 'rename_folder':
        utils.log("Routing to rename_folder action", "DEBUG")
        rename_folder(q)
        return
    elif action_type == 'refresh_movie':
        utils.log("Routing to refresh_movie action", "DEBUG")
        refresh_movie(q)
        return
    elif action_type == 'show_item_details':
        utils.log("Routing to show_item_details action", "DEBUG")
        show_item_details(q)
        return
    elif action_type == 'play_movie':
        utils.log("Routing to play_movie action", "DEBUG")
        play_movie(q)
        return
    elif action_type == 'browse_folder':
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
    elif action_type == 'browse_list':
        list_id = q.get('list_id', [None])[0]
        if list_id:
            # Set proper content for list view
            xbmcplugin.setContent(ADDON_HANDLE, "movies")
            # Clear navigation flag when we reach the target
            _navigation_in_progress = False
            xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
            browse_list(list_id)
        else:
            utils.log("No list_id provided for browse_list action", "WARNING")
            show_empty_directory()
        return
    elif action_type == 'separator':
        # Do nothing for separator items
        utils.log("Received separator action, doing nothing.", "DEBUG")
        pass
    elif action_type == "clear_all_local_data" or action_type == "clear_all_local_folders_lists":
        utils.log("=== SCRIPT ACTION: CLEAR ALL LOCAL FOLDERS/LISTS ===", "DEBUG")
        clear_all_local_data()
    elif action_type == 'new_folder':
        utils.log("Routing to new_folder action", "DEBUG")
        create_new_folder_at_root()
        return
    elif action_type == 'upload_full':
        utils.log("Routing to upload_full action", "DEBUG")
        try:
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.upload_library_full_sync()
        except Exception as e:
            utils.log(f"Error in full upload: {str(e)}", "ERROR")
        return
    elif action_type == 'upload_delta':
        utils.log("Routing to upload_delta action", "DEBUG")
        try:
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.upload_library_delta_sync()
        except Exception as e:
            utils.log(f"Error in delta sync: {str(e)}", "ERROR")
        return
    elif action_type == 'upload_status':
        utils.log("Routing to upload_status action", "DEBUG")
        try:
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.get_upload_status()
        except Exception as e:
            utils.log(f"Error viewing upload status: {str(e)}", "ERROR")
        return
    elif action_type == 'clear_server':
        utils.log("Routing to clear_server action", "DEBUG")
        try:
            from resources.lib.imdb_upload_manager import IMDbUploadManager
            upload_manager = IMDbUploadManager()
            upload_manager.clear_server_library()
        except Exception as e:
            utils.log(f"Error clearing server: {str(e)}", "ERROR")
        return
    elif action_type == 'clear_local':
        utils.log("Routing to clear_local action", "DEBUG")
        clear_all_local_data()
        return
    elif action_type == 'settings':
        utils.log("Routing to settings action", "DEBUG")
        xbmc.executebuiltin("Addon.OpenSettings(plugin.video.librarygenie)")
        return
    elif action_type == 'authenticate':
        utils.log("Routing to authenticate action", "DEBUG")
        try:
            from resources.lib.authenticate_code import authenticate_with_code
            authenticate_with_code()
        except Exception as e:
            utils.log(f"Error authenticating: {str(e)}", "ERROR")
        return
    else:
        # Default: build root directory if action is not recognized or empty
        utils.log(f"Unrecognized action '{action_type}' or no action specified, building root directory.", "DEBUG")
        build_root()

def show_options(params):
    """Show the Options & Tools menu using plugin directory listing"""
    utils.log("=== OPTIONS DIRECTORY REQUEST START ===", "DEBUG")
    
    handle = int(sys.argv[1])
    
    # Set proper breadcrumb
    xbmcplugin.setPluginCategory(handle, "LibraryGenie - Options & Tools")
    xbmcplugin.setContent(handle, "files")
    
    try:
        from resources.lib.listitem_builder import ListItemBuilder
        
        # Create menu items as directory entries
        menu_items = [
            {"label": "🔍 Search Movies", "action": "search"},
            {"label": "📁 Browse Lists", "action": "browse"},
            {"label": "➕ Create New List", "action": "create_list"},
            {"label": "📂 Create New Folder", "action": "new_folder"},
            {"label": "⬆️ Upload Library to Server (Full)", "action": "upload_full"},
            {"label": "🔄 Sync Library with Server (Delta)", "action": "upload_delta"},
            {"label": "📊 View Upload Status", "action": "upload_status"},
            {"label": "🗑️ Clear Server Library", "action": "clear_server"},
            {"label": "💾 Clear All Local Folders/Lists", "action": "clear_local"},
            {"label": "⚙️ Settings", "action": "settings"},
            {"label": "🔐 Authenticate with Server", "action": "authenticate"}
        ]
        
        for item in menu_items:
            li = ListItemBuilder.build_folder_item(item["label"], is_folder=False)
            li.setProperty('IsPlayable', 'false')
            
            # Create RunPlugin URLs for actions that don't need directory listing
            if item["action"] in ["create_list", "new_folder", "upload_full", "upload_delta", "upload_status", "clear_server", "clear_local", "settings", "authenticate"]:
                url = f'RunPlugin({_plugin_url({"action": item["action"]})})'
                li.setProperty('IsPlayable', 'false')
            else:
                # For search and browse, use regular plugin URLs
                url = _plugin_url({"action": item["action"]})
            
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
        
        utils.log("=== ADDED ALL OPTIONS MENU ITEMS ===", "DEBUG")
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        
    except Exception as e:
        utils.log(f"=== ERROR IN OPTIONS DIRECTORY: {str(e)} ===", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
        xbmcplugin.endOfDirectory(handle, succeeded=False)

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

def run_migration_if_needed():
    """Check if migration is needed and run it once"""
    try:
        from resources.lib.database_manager import DatabaseManager
        from resources.lib.config_manager import Config
        from resources.lib import utils

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Check if we need to run migration by looking for a migration marker
        migration_marker_path = os.path.join(os.path.dirname(config.db_path), '.migration_v2_complete')

        if not os.path.exists(migration_marker_path):
            utils.log("Running one-time database migration for existing installation", "INFO")
            db_manager.migrate_existing_database()

            # Create marker file to prevent re-running
            with open(migration_marker_path, 'w') as f:
                f.write("Migration v2 completed")

            utils.log("Database migration completed and marked", "INFO")
        else:
            utils.log("Migration already completed, skipping", "DEBUG")

    except Exception as e:
        # Don't fail startup if migration fails
        import xbmc
        xbmc.log(f"LibraryGenie migration warning: {str(e)}", xbmc.LOGWARNING)

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
    # Run migration check before starting the main application
    run_migration_if_needed()
    from resources.lib import runner
    runner.main()

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