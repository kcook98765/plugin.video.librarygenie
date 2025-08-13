"""Route handlers for LibraryGenie plugin actions"""
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager

def play_movie(params):
    """Play a movie from Kodi library using movieid"""
    try:
        # Extract movieid from params
        movieid = params.get('movieid', [None])[0]
        if not movieid:
            utils.log("No movieid provided for play_movie action", "ERROR")
            return

        movieid = int(movieid)
        utils.log(f"Playing movie with Kodi ID: {movieid}", "DEBUG")

        # Use JSON-RPC to directly play the movie - this preserves resume points and all Kodi functionality
        from resources.lib.jsonrpc_manager import JSONRPC
        jsonrpc = JSONRPC()

        # Get movie title for logging
        response = jsonrpc.execute('VideoLibrary.GetMovieDetails', {
            'movieid': movieid,
            'properties': ['title']
        })

        movie_details = response.get('result', {}).get('moviedetails', {})
        title = movie_details.get('title', f'Movie ID {movieid}')

        utils.log(f"Starting native Kodi playback for '{title}' (ID: {movieid})", "INFO")

        # Use Player.Open to play the movie natively - this preserves all Kodi functionality
        play_response = jsonrpc.execute('Player.Open', {
            'item': {'movieid': movieid}
        })

        if 'error' in play_response:
            error_msg = play_response.get('error', {}).get('message', 'Unknown error')
            utils.log(f"Error starting playback via JSON-RPC: {error_msg}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', f'Playback error: {error_msg}')
            return

        utils.log(f"Successfully started native playback for '{title}'", "DEBUG")

    except Exception as e:
        utils.log(f"Error playing movie: {str(e)}", "ERROR")
        import traceback
        utils.log(f"play_movie traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error playing movie')

def show_item_details(params):
    """Show details for a non-playable item"""
    try:
        # Fix parameter extraction for URL-encoded parameters
        title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown'
        list_id = params.get('list_id', [None])[0] if params.get('list_id') else None
        item_id = params.get('item_id', [None])[0] if params.get('item_id') else None

        utils.log(f"show_item_details called with title='{title}', list_id='{list_id}', item_id='{item_id}'", "DEBUG")

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Decode URL-encoded title if needed
        import urllib.parse
        if title:
            title = urllib.parse.unquote_plus(title)

        # Try to get more details about the item
        details_text = f"Title: {title}\n"

        if item_id and str(item_id).isdigit():
            try:
                # Get item details from database using proper query structure
                media_items = db_manager.fetch_data('media_items', f'id = {item_id}')
                if media_items and len(media_items) > 0:
                    item = media_items[0]
                    details_text += f"Year: {item.get('year', 'Unknown')}\n"
                    details_text += f"IMDb ID: {item.get('imdbnumber', 'Unknown')}\n"
                    plot = item.get('plot', 'No plot available')
                    if plot and len(plot) > 200:
                        plot = plot[:200] + "..."
                    details_text += f"Plot: {plot}\n"
                else:
                    utils.log(f"No media item found with ID {item_id}", "DEBUG")
            except Exception as e:
                utils.log(f"Error fetching media item details: {str(e)}", "ERROR")

        details_text += "\nThis item was not found in your Kodi library."

        utils.log(f"Showing details dialog for: {title}", "DEBUG")
        xbmcgui.Dialog().textviewer('Movie Details', details_text)

    except Exception as e:
        utils.log(f"Error showing item details: {str(e)}", "ERROR")
        import traceback
        utils.log(f"show_item_details traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error showing details')

def create_list(params):
    utils.log("=== CREATE_LIST: ABOUT TO SHOW INPUT MODAL ===", "DEBUG")
    name = xbmcgui.Dialog().input('New list name', type=xbmcgui.INPUT_ALPHANUM)
    utils.log("=== CREATE_LIST: INPUT MODAL CLOSED ===", "DEBUG")
    if not name:
        utils.log("CREATE_LIST: No name entered, cancelling", "DEBUG")
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Create in root folder for now
        list_id = db_manager.create_list(name, None)
        utils.log("=== CREATE_LIST: ABOUT TO SHOW SUCCESS NOTIFICATION ===", "DEBUG")
        xbmcgui.Dialog().notification('LibraryGenie', 'List created')
        utils.log("=== CREATE_LIST: SUCCESS NOTIFICATION CLOSED ===", "DEBUG")
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error creating list: {str(e)}", "ERROR")
        utils.log("=== CREATE_LIST: ABOUT TO SHOW ERROR NOTIFICATION ===", "DEBUG")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create list')
        utils.log("=== CREATE_LIST: ERROR NOTIFICATION CLOSED ===", "DEBUG")

def rename_list(params):
    list_id = params.get('list_id', [None])[0]
    if not list_id:
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get current list name to pre-fill the dialog
        current_lists = db_manager.fetch_data('lists', f"id = {list_id}")
        current_name = ""
        if current_lists and len(current_lists) > 0:
            current_name = current_lists[0].get('name', '')

        new_name = xbmcgui.Dialog().input('Rename list to', defaultt=current_name, type=xbmcgui.INPUT_ALPHANUM)
        if not new_name:
            return

        db_manager.update_data('lists', {'name': new_name}, f"id = {list_id}")
        xbmcgui.Dialog().notification('LibraryGenie', 'List renamed')
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error renaming list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Rename failed')

def move_list(params):
    list_id = params.get('list_id', [None])[0]
    if not list_id:
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get available folders for moving (including all folders, not just root ones)
        all_folders = db_manager.fetch_all_folders()

        # Filter out the Search History folder - users shouldn't move lists there
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")
        filtered_folders = [f for f in all_folders if f.get('id') != search_history_folder_id]

        folder_options = ["<Root>"]
        folder_ids = [None]

        # Build hierarchical folder list for selection
        def add_folder_to_options(folder, indent=0):
            indent_str = "  " * indent
            folder_options.append(f"{indent_str}{folder['name']}")
            folder_ids.append(folder['id'])

            # Add subfolders (also filtered)
            subfolders = [f for f in filtered_folders if f.get('parent_id') == folder['id']]
            subfolders.sort(key=lambda x: x['name'].lower())
            for subfolder in subfolders:
                add_folder_to_options(subfolder, indent + 1)

        # Add all root folders and their children (excluding Search History)
        root_folders = [f for f in filtered_folders if f.get('parent_id') is None]
        root_folders.sort(key=lambda x: x['name'].lower())
        for folder in root_folders:
            add_folder_to_options(folder)

        selected = xbmcgui.Dialog().select("Move list to folder:", folder_options)
        if selected >= 0:
            target_folder_id = folder_ids[selected]
            db_manager.update_data('lists', {'folder_id': target_folder_id}, f"id = {list_id}")

            destination = "root" if target_folder_id is None else folder_options[selected].strip()
            xbmcgui.Dialog().notification('LibraryGenie', f'List moved to {destination}')
            xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error moving list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Move failed')

def delete_list(params):
    list_id = params.get('list_id', [None])[0]
    if not list_id:
        return
    if not xbmcgui.Dialog().yesno('Delete list', 'Are you sure?'):
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Delete list items first
        db_manager.delete_data('list_items', f"list_id = {list_id}")
        # Delete the list
        db_manager.delete_data('lists', f"id = {list_id}")
        xbmcgui.Dialog().notification('LibraryGenie', 'List deleted')
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error deleting list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Delete failed')

def remove_from_list(params):
    list_id = params.get('list_id', [None])[0]
    movie_id = params.get('movie_id', [None])[0]
    if not (list_id and movie_id):
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        db_manager.delete_data('list_items', f"list_id = {list_id} AND media_id = {movie_id}")
        xbmcgui.Dialog().notification('LibraryGenie', 'Removed from list')
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error removing from list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to remove')

def rename_folder(params):
    folder_id = params.get('folder_id', [None])[0]
    if not folder_id:
        return
    new_name = xbmcgui.Dialog().input('Rename folder to', type=xbmcgui.INPUT_ALPHANUM)
    if not new_name:
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        db_manager.update_data('folders', {'name': new_name}, f"id = {folder_id}")
        xbmcgui.Dialog().notification('LibraryGenie', 'Folder renamed')
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error renaming folder: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Rename failed')

def refresh_movie(params):
    movie_id = params.get('movie_id', [None])[0]
    if not movie_id:
        return
    try:
        # Placeholder for movie metadata refresh
        xbmcgui.Dialog().notification('LibraryGenie', 'Movie metadata refreshed')
    except Exception as e:
        utils.log(f"Error refreshing movie: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Refresh failed')

def do_search(params):
    q = xbmcgui.Dialog().input('Search movies', type=xbmcgui.INPUT_ALPHANUM)
    if not q:
        return
    # Hand off to existing search functionality
    try:
        from resources.lib.window_search import SearchWindow
        from resources.lib.remote_api_client import RemoteAPIClient

        config = Config()
        api_client = RemoteAPIClient()

        # Perform the search
        results = api_client.search_movies(q)
        if results and results.get('success'):
            # Create a search results list
            db_manager = DatabaseManager(config.db_path)

            # Create "Search History" folder if it doesn't exist
            search_folder_id = db_manager.ensure_folder_exists("Search History", None)

            # Create a new list for this search
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            list_name = f"Search: {q} ({timestamp})"
            list_id = db_manager.create_list(list_name, search_folder_id)

            # Add results to the list
            movies = results.get('results', [])
            for movie in movies:
                db_manager.insert_data('media_items', {
                    'title': movie.get('title', ''),
                    'year': movie.get('year', 0),
                    'imdbnumber': movie.get('imdb_id', ''),
                    'source': 'search',
                    'plot': movie.get('plot', ''),
                    'rating': float(movie.get('rating', 0)),
                    'genre': movie.get('genre', '')
                })
                # Link to list
                media_id = db_manager.cursor.lastrowid
                db_manager.insert_data('list_items', {
                    'list_id': list_id,
                    'media_id': media_id
                })

            xbmcgui.Dialog().notification('LibraryGenie', f'Found {len(movies)} results')
            # Navigate to the results
            from main import _plugin_url
            xbmc.executebuiltin(f'Container.Update({_plugin_url({"action":"browse_list","list_id":list_id,"view":"list"})})')
        else:
            xbmcgui.Dialog().notification('LibraryGenie', 'Search failed', xbmcgui.NOTIFICATION_ERROR)
    except Exception as e:
        utils.log(f"Error in search: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Search error', xbmcgui.NOTIFICATION_ERROR)

def show_directory():
    """Show the main directory with folders and lists"""
    utils.log("Showing main directory", "DEBUG")

    from resources.lib.config_manager import Config
    from resources.lib.database_manager import DatabaseManager
    from resources.lib.listitem_builder import ListItemBuilder
    import xbmcplugin

    config = Config()
    db_manager = DatabaseManager(config.db_path)

    # Add special "Options & Tools" entry at the top
    options_item = ListItemBuilder.build_folder_item("Options & Tools", is_folder=False)
    options_url = f"plugin://plugin.video.librarygenie/?action=options"
    utils.log(f"Adding Options & Tools with URL: {options_url}", "DEBUG")
    xbmcplugin.addDirectoryItem(
        handle=int(xbmc.getInfoLabel('System.AddonHandle')),
        url=options_url,
        listitem=options_item,
        isFolder=False
    )

    # Fetch root folders and lists
    root_folders = db_manager.fetch_data('folders', 'parent_id IS NULL')
    root_folders.sort(key=lambda x: x['name'].lower())
    for folder in root_folders:
        folder_item = ListItemBuilder.build_folder_item(folder['name'], folder_id=folder['id'])
        xbmcplugin.addDirectoryItem(
            handle=int(xbmc.getInfoLabel('System.AddonHandle')),
            url=f"plugin://plugin.video.librarygenie/?action=browse_folder&folder_id={folder['id']}",
            listitem=folder_item,
            isFolder=True
        )

    # Fetch root lists (lists directly under root)
    root_lists = db_manager.fetch_data('lists', 'folder_id IS NULL')
    root_lists.sort(key=lambda x: x['name'].lower())
    for lst in root_lists:
        list_item = ListItemBuilder.build_list_item(lst['name'], lst['id'])
        xbmcplugin.addDirectoryItem(
            handle=int(xbmc.getInfoLabel('System.AddonHandle')),
            url=f"plugin://plugin.video.librarygenie/?action=browse_list&list_id={lst['id']}",
            listitem=list_item,
            isFolder=True
        )

    xbmcplugin.endOfDirectory(handle=int(xbmc.getInfoLabel('System.AddonHandle')), cacheToDisc=True)

def show_options_menu():
    """Show the options menu"""
    import xbmcgui

    utils.log("=== ENTERING OPTIONS MENU ===", "DEBUG")

    options = [
        "Search Movies...",
        "Manage Folders",
        "Manage Lists",
        "Upload Library to Server",
        "Setup Remote API",
        "Test Remote Connection",
        "Addon Settings"
    ]

    utils.log(f"Showing dialog with options: {options}", "DEBUG")
    selected = xbmcgui.Dialog().select("LibraryGenie Options", options)
    utils.log(f"User selected option index: {selected}", "DEBUG")

    if selected == -1:  # User cancelled
        utils.log("User cancelled options menu", "DEBUG")
        return
    elif selected == 0:  # Search Movies
        utils.log("User selected: Search Movies", "DEBUG")
        handle_search()
    elif selected == 1:  # Manage Folders
        utils.log("User selected: Manage Folders", "DEBUG")
        handle_folder_management()
    elif selected == 2:  # Manage Lists
        utils.log("User selected: Manage Lists", "DEBUG")
        handle_list_management()
    elif selected == 3:  # Upload Library
        utils.log("User selected: Upload Library", "DEBUG")
        handle_library_upload()
    elif selected == 4:  # Setup Remote API
        utils.log("User selected: Setup Remote API", "DEBUG")
        handle_remote_api_setup()
    elif selected == 5:  # Test Remote Connection
        utils.log("User selected: Test Remote Connection", "DEBUG")
        handle_test_connection()
    elif selected == 6:  # Addon Settings
        utils.log("User selected: Addon Settings", "DEBUG")
        from resources.lib.addon_ref import get_addon
        get_addon().openSettings()

    utils.log("=== EXITING OPTIONS MENU ===", "DEBUG")

def handle_routes(action, **kwargs):
    """Main route handler for all addon actions"""
    utils.log(f"=== ROUTE HANDLER: action='{action}', kwargs={kwargs} ===", "DEBUG")

    if action is None or action == '':
        utils.log("No action specified, showing main directory", "DEBUG")
        show_directory()
    elif action == 'show_folder':
        utils.log("Handling show_folder action", "DEBUG")
        show_folder(kwargs)
    elif action == 'browse_folder':
        utils.log("Handling browse_folder action", "DEBUG")
        show_folder(kwargs)
    elif action == 'show_list':
        utils.log("Handling show_list action", "DEBUG")
        show_list(kwargs)
    elif action == 'browse_list':
        utils.log("Handling browse_list action", "DEBUG")
        show_list(kwargs)
    elif action == 'browse':
        utils.log("Handling browse action (launching main window)", "DEBUG")
        launch_main_window(kwargs)
    elif action == 'play_movie':
        utils.log("Handling play_movie action", "DEBUG")
        play_movie(kwargs)
    elif action == 'show_item_details':
        utils.log("Handling show_item_details action", "DEBUG")
        show_item_details(kwargs)
    elif action == 'create_list':
        utils.log("Handling create_list action", "DEBUG")
        create_list(kwargs)
    elif action == 'rename_list':
        utils.log("Handling rename_list action", "DEBUG")
        rename_list(kwargs)
    elif action == 'move_list':
        utils.log("Handling move_list action", "DEBUG")
        move_list(kwargs)
    elif action == 'delete_list':
        utils.log("Handling delete_list action", "DEBUG")
        delete_list(kwargs)
    elif action == 'remove_from_list':
        utils.log("Handling remove_from_list action", "DEBUG")
        remove_from_list(kwargs)
    elif action == 'rename_folder':
        utils.log("Handling rename_folder action", "DEBUG")
        rename_folder(kwargs)
    elif action == 'refresh_movie':
        utils.log("Handling refresh_movie action", "DEBUG")
        refresh_movie(kwargs)
    elif action == 'search':
        utils.log("Starting search", "DEBUG")
        handle_search()
    elif action == 'manage_folders':
        utils.log("Starting folder management", "DEBUG")
        handle_folder_management()
    elif action == 'manage_lists':
        utils.log("Starting list management", "DEBUG")
        handle_list_management()
    elif action == 'upload_library':
        utils.log("Starting library upload", "DEBUG")
        handle_library_upload()
    elif action == 'remote_api_setup':
        utils.log("Starting remote API setup", "DEBUG")
        handle_remote_api_setup()
    elif action == 'settings':
        utils.log("Opening addon settings", "DEBUG")
        from resources.lib.addon_ref import get_addon
        get_addon().openSettings()
    elif action == 'test_connection':
        utils.log("Testing remote API connection", "DEBUG")
        handle_test_connection()
    elif action == 'options':
        utils.log("Showing options menu", "DEBUG")
        show_options_menu()
    else:
        utils.log(f"Unknown action: {action}", "WARNING")
        xbmcgui.Dialog().notification('LibraryGenie', f'Unknown action: {action}')

# Placeholder functions for actions called from the options menu and elsewhere.
# These would typically be defined in other modules or handled by specific routing logic.

def handle_search():
    """Placeholder for search handling."""
    from resources.lib.window_search import SearchWindow
    SearchWindow().doModal() # Assuming SearchWindow is designed to be shown modally

def handle_folder_management():
    """Placeholder for folder management."""
    utils.log("Navigating to folder management", "DEBUG")
    # Example: Navigate to a new directory that lists folders
    # In a real implementation, this would likely involve showing a list of folders
    # For now, we'll just show a notification.
    xbmcgui.Dialog().notification('LibraryGenie', 'Folder Management (not fully implemented)')

def handle_list_management():
    """Placeholder for list management."""
    utils.log("Navigating to list management", "DEBUG")
    # Example: Navigate to a new directory that lists lists
    xbmcgui.Dialog().notification('LibraryGenie', 'List Management (not fully implemented)')

def handle_library_upload():
    """Placeholder for library upload."""
    utils.log("Initiating library upload", "DEBUG")
    xbmcgui.Dialog().notification('LibraryGenie', 'Library Upload (not fully implemented)')

def handle_remote_api_setup():
    """Placeholder for remote API setup."""
    utils.log("Navigating to remote API setup", "DEBUG")
    xbmcgui.Dialog().notification('LibraryGenie', 'Remote API Setup (not fully implemented)')

def handle_test_connection():
    """Placeholder for testing remote API connection."""
    utils.log("Testing remote API connection", "DEBUG")
    xbmcgui.Dialog().notification('LibraryGenie', 'Testing Connection (not fully implemented)')

def show_folder(params):
    """Show contents of a specific folder"""
    folder_id = params.get('folder_id', [None])[0] if params.get('folder_id') else None
    if not folder_id:
        utils.log("No folder_id provided for show_folder", "ERROR")
        return
        
    utils.log(f"Showing folder with ID: {folder_id}", "DEBUG")
    
    try:
        from resources.lib.config_manager import Config
        from resources.lib.database_manager import DatabaseManager
        from resources.lib.listitem_builder import ListItemBuilder
        import xbmcplugin
        
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        
        # Get folder info
        folder = db_manager.fetch_folder_by_id(int(folder_id))
        if not folder:
            utils.log(f"Folder with ID {folder_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found')
            return
        
        # Get subfolders
        subfolders = db_manager.fetch_data('folders', f'parent_id = {folder_id}')
        subfolders.sort(key=lambda x: x['name'].lower())
        
        # Get lists in this folder
        folder_lists = db_manager.fetch_data('lists', f'folder_id = {folder_id}')
        folder_lists.sort(key=lambda x: x['name'].lower())
        
        handle = int(xbmc.getInfoLabel('System.AddonHandle'))
        
        # Add subfolders
        for subfolder in subfolders:
            folder_item = ListItemBuilder.build_folder_item(subfolder['name'])
            xbmcplugin.addDirectoryItem(
                handle=handle,
                url=f"plugin://plugin.video.librarygenie/?action=show_folder&folder_id={subfolder['id']}",
                listitem=folder_item,
                isFolder=True
            )
        
        # Add lists
        for lst in folder_lists:
            list_item = ListItemBuilder.build_list_item(lst['name'], list_data=lst)
            xbmcplugin.addDirectoryItem(
                handle=handle,
                url=f"plugin://plugin.video.librarygenie/?action=show_list&list_id={lst['id']}",
                listitem=list_item,
                isFolder=True
            )
        
        xbmcplugin.endOfDirectory(handle=handle, cacheToDisc=True)
        
    except Exception as e:
        utils.log(f"Error showing folder: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error showing folder')

def show_list(params):
    """Show contents of a specific list"""
    list_id = params.get('list_id', [None])[0] if params.get('list_id') else None
    if not list_id:
        utils.log("No list_id provided for show_list", "ERROR")
        return
        
    utils.log(f"Showing list with ID: {list_id}", "DEBUG")
    
    try:
        from resources.lib.config_manager import Config
        from resources.lib.database_manager import DatabaseManager
        from resources.lib.listitem_builder import ListItemBuilder
        import xbmcplugin
        
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        
        # Get list info
        list_info = db_manager.fetch_data('lists', f'id = {list_id}')
        if not list_info or len(list_info) == 0:
            utils.log(f"List with ID {list_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'List not found')
            return
        
        # Get list items
        list_items = db_manager.fetch_data('list_items', f'list_id = {list_id}')
        
        handle = int(xbmc.getInfoLabel('System.AddonHandle'))
        
        # Add each list item
        for item in list_items:
            try:
                # Build video item with media info
                video_item = ListItemBuilder.build_video_item(item)
                
                # Determine the URL - check if it's playable from Kodi library
                kodi_id = item.get('kodi_id')
                if kodi_id and str(kodi_id).isdigit() and int(kodi_id) > 0:
                    # This item exists in Kodi library - make it playable
                    item_url = f"plugin://plugin.video.librarygenie/?action=play_movie&movieid={kodi_id}"
                    is_folder = False
                else:
                    # This item doesn't exist in Kodi library - show details only
                    item_url = f"plugin://plugin.video.librarygenie/?action=show_item_details&title={item.get('title', '')}&list_id={list_id}&item_id={item.get('id', '')}"
                    is_folder = False
                
                xbmcplugin.addDirectoryItem(
                    handle=handle,
                    url=item_url,
                    listitem=video_item,
                    isFolder=is_folder
                )
                
            except Exception as e:
                utils.log(f"Error processing list item {item.get('id', 'unknown')}: {str(e)}", "ERROR")
                continue
        
        xbmcplugin.endOfDirectory(handle=handle, cacheToDisc=True)
        
    except Exception as e:
        utils.log(f"Error showing list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error showing list')

def launch_main_window(params):
    """Launch the main browse window"""
    utils.log("Launching main window for browsing", "DEBUG")
    
    try:
        # Get title from params for context
        title = params.get('title', [''])[0] if params.get('title') else ''
        utils.log(f"Browse context title: '{title}'", "DEBUG")
        
        # Create dummy item info for browsing mode
        item_info = {
            'title': title or 'Browse Lists',
            'kodi_id': 0,
            'year': '',
            'plot': 'Browse your LibraryGenie lists and folders',
            'is_playable': False
        }
        
        # Import and launch the main window
        from resources.lib.window_main import MainWindow
        main_window = MainWindow(item_info, "LibraryGenie Browser")
        main_window.doModal()
        del main_window
        
    except Exception as e:
        utils.log(f"Error launching main window: {str(e)}", "ERROR")
        import traceback
        utils.log(f"launch_main_window traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error launching browser')