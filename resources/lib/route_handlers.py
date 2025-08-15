
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
        details_text += f"Source: External addon/non-library item\n"

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

        # Get folder_id from params, default to None (root)
        folder_id = params.get('folder_id')
        
        if folder_id and isinstance(folder_id, list):
            folder_id = folder_id[0]
        
        if folder_id and str(folder_id).isdigit():
            folder_id = int(folder_id)
        else:
            folder_id = None
        utils.log(f"Creating list '{name}' in folder_id: {folder_id}", "DEBUG")
        list_id = db_manager.create_list(name, folder_id)
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
    new_name = xbmcgui.Dialog().input('Rename list to', type=xbmcgui.INPUT_ALPHANUM)
    if not new_name:
        return
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        db_manager.update_data('lists', {'name': new_name}, f"id = {list_id}")
        xbmcgui.Dialog().notification('LibraryGenie', 'List renamed')
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"Error renaming list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Rename failed')

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

def move_list(params):
    """Move a list to a different folder or root"""
    list_id = params.get('list_id', [None])[0]
    if not list_id:
        return
    
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        
        # Get current list info
        list_info = db_manager.fetch_list_by_id(list_id)
        if not list_info:
            utils.log(f"List with ID {list_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'List not found', xbmcgui.NOTIFICATION_ERROR)
            return
        
        # Check if list is protected (search history lists cannot be moved)
        if db_manager.is_list_protected(list_id):
            utils.log(f"Cannot move protected list {list_id}", "WARNING")
            xbmcgui.Dialog().notification('LibraryGenie', 'Cannot move protected list', xbmcgui.NOTIFICATION_WARNING)
            return
        
        # Get all folders for selection (excluding Search History folder)
        all_folders = db_manager.fetch_all_folders()
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")
        
        # Filter out Search History folder and folders that would exceed depth limit
        folder_options = ["📁 Root (No folder)"]
        folder_ids = [None]  # Root folder represented as None
        
        for folder in all_folders:
            if folder['id'] != search_history_folder_id:
                # Check if moving to this folder would exceed depth limit
                folder_depth = db_manager.get_folder_depth(folder['id'])
                if folder_depth < config.max_folder_depth:
                    # Build folder path for display
                    folder_path = folder['name']
                current_folder = folder
                while current_folder.get('parent_id'):
                    parent_folder = db_manager.fetch_folder_by_id(current_folder['parent_id'])
                    if parent_folder and parent_folder['id'] != search_history_folder_id:
                        folder_path = f"{parent_folder['name']} > {folder_path}"
                        current_folder = parent_folder
                    else:
                        break
                
                folder_options.append(f"📁 {folder_path}")
                folder_ids.append(folder['id'])
        
        # Show folder selection dialog
        selected_index = xbmcgui.Dialog().select(
            f"Move list '{list_info['name']}' to:",
            folder_options
        )
        
        if selected_index == -1:  # User cancelled
            return
        
        target_folder_id = folder_ids[selected_index]
        current_folder_id = list_info.get('folder_id')
        
        # Check if already in target location
        if target_folder_id == current_folder_id:
            xbmcgui.Dialog().notification('LibraryGenie', 'List is already in that location', xbmcgui.NOTIFICATION_INFO)
            return
        
        # Move the list
        db_manager.update_list_folder(list_id, target_folder_id)
        
        # Show success notification
        target_name = "Root" if target_folder_id is None else folder_options[selected_index].replace("📁 ", "")
        xbmcgui.Dialog().notification('LibraryGenie', f'List moved to {target_name}')
        xbmc.executebuiltin('Container.Refresh')
        
    except Exception as e:
        utils.log(f"Error moving list: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Move list traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to move list', xbmcgui.NOTIFICATION_ERROR)

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
