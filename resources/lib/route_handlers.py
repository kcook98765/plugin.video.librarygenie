"""Route handlers for LibraryGenie plugin actions"""
import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
import sys
import xbmcplugin

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
        details_text += "Source: External addon/non-library item\n"

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
        folder_options = ["Root (No folder)"]
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

                    folder_options.append(folder_path)
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

def find_similar_movies(params):
    """Find movies similar to the selected movie"""
    try:
        # Extract parameters
        imdb_id = params.get('imdb_id', [None])[0] if params.get('imdb_id') else None
        movie_title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown Movie'

        if not imdb_id:
            xbmcgui.Dialog().notification('LibraryGenie', 'No IMDb ID found for this movie', xbmcgui.NOTIFICATION_ERROR)
            return

        # Decode URL-encoded title if needed
        import urllib.parse
        movie_title = urllib.parse.unquote_plus(movie_title)

        utils.log(f"Finding similar movies for '{movie_title}' (IMDb: {imdb_id})", "INFO")

        # Use the similar movies manager
        from resources.lib.similar_movies_manager import SimilarMoviesManager
        similar_manager = SimilarMoviesManager()
        similar_manager.show_similar_movies_dialog(imdb_id, movie_title)

        # IMPORTANT: This is a RunPlugin action - no directory listing needed
        # The navigation is handled by the similar movies manager
        utils.log("Similar movies action completed - plugin execution ending", "DEBUG")

    except Exception as e:
        utils.log(f"Error in find_similar_movies: {str(e)}", "ERROR")
        import traceback
        utils.log(f"find_similar_movies traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error finding similar movies', xbmcgui.NOTIFICATION_ERROR)

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

def browse_list(params):
    """Browse items in a specific list - delegate to main.py implementation"""
    try:
        utils.log(f"[BROWSE LIST HANDLER] Routing to main.browse_list implementation", "INFO")
        list_id = params.get('list_id', [None])[0]

        if not list_id:
            utils.log("[BROWSE LIST HANDLER] ERROR: No list_id provided", "ERROR")
            # Import here to avoid circular imports
            import xbmcplugin
            import sys
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
            return

        # Call the main browse_list function which has proper plugin handling
        from main import browse_list as main_browse_list
        main_browse_list(list_id)

    except Exception as e:
        utils.log(f"[BROWSE LIST HANDLER] ERROR: {str(e)}", "ERROR")
        import traceback
        utils.log(f"[BROWSE LIST HANDLER] Traceback: {traceback.format_exc()}", "ERROR")
        # Ensure plugin ends gracefully
        import xbmcplugin
        import sys
        try:
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        except:
            pass

def browse_folder(params):
    """Browse the contents of a specific folder"""
    try:
        utils.log(f"[BROWSE FOLDER] Starting browse_folder with params: {params}", "INFO")
        folder_id = params.get('folder_id', [None])[0]

        utils.log(f"[BROWSE FOLDER] Extracted folder_id: {folder_id}", "DEBUG")

        if folder_id is None:
            utils.log("[BROWSE FOLDER] ERROR: No folder_id provided for browse_folder", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not specified', xbmcgui.NOTIFICATION_ERROR)
            return

        try:
            folder_id = int(folder_id)
            utils.log(f"[BROWSE FOLDER] Converted folder_id to integer: {folder_id}", "DEBUG")
        except (ValueError, TypeError) as e:
            utils.log(f"[BROWSE FOLDER] ERROR: Invalid folder_id format '{folder_id}': {str(e)}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Invalid folder ID', xbmcgui.NOTIFICATION_ERROR)
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Fetch folder details
        folder_details = db_manager.fetch_folder_by_id(folder_id)
        if not folder_details:
            utils.log(f"[BROWSE FOLDER] ERROR: Folder with ID {folder_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found', xbmcgui.NOTIFICATION_ERROR)
            return

        folder_name = folder_details['name']
        parent_folder_id = folder_details.get('parent_id') # This could be None for root

        utils.log(f"[BROWSE FOLDER] Browsing folder: '{folder_name}' (ID: {folder_id}, ParentID: {parent_folder_id})", "INFO")

        # Get lists within this folder
        lists_in_folder = db_manager.fetch_lists_by_folder(folder_id)
        utils.log(f"[BROWSE FOLDER] Found {len(lists_in_folder)} lists in folder '{folder_name}'", "INFO")

        # Get subfolders within this folder
        subfolders = db_manager.fetch_folders_by_parent_id(folder_id)
        utils.log(f"[BROWSE FOLDER] Found {len(subfolders)} subfolders in folder '{folder_name}'", "INFO")

        listitems = []

        # Add subfolders to the list
        for subfolder in subfolders:
            subfolder_name = subfolder['name']
            subfolder_id = subfolder['id']
            subfolder_listitem = xbmcgui.ListItem(label=subfolder_name)
            subfolder_listitem.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            subfolder_listitem.setProperty('IsFolder', 'true')

            # Context menu for subfolder
            cm_subfolder = []
            cm_subfolder.append(('Rename Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "rename_folder", "folder_id": subfolder_id})})'))
            # Add option to move folder if not protected
            if not db_manager.is_folder_protected(subfolder_id):
                 cm_subfolder.append(('Move Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "move_folder", "folder_id": subfolder_id})})'))
            # Add option to delete folder if not protected
            if not db_manager.is_folder_protected(subfolder_id):
                 cm_subfolder.append(('Delete Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "delete_folder", "folder_id": subfolder_id})})'))

            subfolder_listitem.addContextMenuItems(cm_subfolder)

            # Add to listitems
            listitems.append((utils.build_plugin_url({"action": "browse_folder", "folder_id": subfolder_id}), subfolder_listitem, True))

        # Add lists within the folder to the list
        for list_data in lists_in_folder:
            list_name = list_data['name']
            list_id = list_data['id']
            list_type = list_data['type']

            list_listitem = xbmcgui.ListItem(label=list_name)
            # Set appropriate art based on list type
            if list_type == 'folder': # This case should ideally not happen if structure is maintained
                list_listitem.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            elif list_type == 'search':
                list_listitem.setArt({'icon': 'DefaultSearch.png', 'thumb': 'DefaultSearch.png'})
            else: # Default for regular lists
                list_listitem.setArt({'icon': 'DefaultProgram.png', 'thumb': 'DefaultProgram.png'})

            list_listitem.setProperty('IsFolder', 'true') # Treat lists as folders for navigation purposes

            # Context menu for the list
            cm_list = []
            cm_list.append(('Rename List', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "rename_list", "list_id": list_id})})'))
            cm_list.append(('Move List', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "move_list", "list_id": list_id})})'))
            # Add option to delete list if not protected
            if not db_manager.is_list_protected(list_id):
                cm_list.append(('Delete List', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "delete_list", "list_id": list_id})})'))
            list_listitem.addContextMenuItems(cm_list)

            # Add to listitems
            listitems.append((utils.build_plugin_url({"action": "browse_list", "list_id": list_id}), list_listitem, True))


        # Set content type for the folder view
        xbmcplugin.setContent(int(sys.argv[1]), "files") # Generic content type for folders

        # Add directory items
        utils.log(f"[BROWSE FOLDER] Setting directory with {len(listitems)} items for folder '{folder_name}'", "INFO")
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), listitems, len(listitems))

        # Add "Go Up" item if not in root folder
        if parent_folder_id is not None:
            parent_folder_details = db_manager.fetch_folder_by_id(parent_folder_id)
            if parent_folder_details:
                parent_folder_name = parent_folder_details['name']
                parent_folder_label = f".. ({parent_folder_name})"
                parent_listitem = xbmcgui.ListItem(label=parent_folder_label)
                parent_listitem.setArt({'icon': 'DefaultFolderBack.png', 'thumb': 'DefaultFolderBack.png'})
                parent_listitem.setProperty('IsFolder', 'true')

                # Context menu for parent folder
                cm_parent = []
                cm_parent.append(('Rename Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "rename_folder", "folder_id": parent_folder_id})})'))
                parent_listitem.addContextMenuItems(cm_parent)

                go_up_action_url = utils.build_plugin_url({"action": "browse_folder", "folder_id": parent_folder_id})
                xbmcplugin.addDirectoryItem(int(sys.argv[1]), go_up_action_url, parent_listitem, isFolder=True)
            else:
                utils.log(f"[BROWSE FOLDER] WARN: Parent folder details not found for ID {parent_folder_id}", "WARNING")
        else:
            # If in root, add option to create a new list or folder in root
            list_cm = []
            list_cm.append(('Create New List in Root', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "create_list", "folder_id": None})})'))
            list_cm.append(('Create New Folder in Root', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "create_folder", "parent_id": None})})'))
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), '', xbmcgui.ListItem(label='Options'), isFolder=False)
            xbmcgui.Window(10000).currentItem.addContextMenuItems(list_cm)


        # Add context menu for the folder itself (e.g., rename, delete, move)
        folder_cm = []
        # Add option to rename folder if not protected
        if not db_manager.is_folder_protected(folder_id):
            folder_cm.append(('Rename Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "rename_folder", "folder_id": folder_id})})'))
            folder_cm.append(('Move Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "move_folder", "folder_id": folder_id})})'))
            folder_cm.append(('Delete Folder', f'XBMC.RunPlugin({utils.build_plugin_url({"action": "delete_folder", "folder_id": folder_id})})'))

        if folder_cm:
             xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_ASC)
             xbmcplugin.addDirectoryItem(int(sys.argv[1]), '', xbmcgui.ListItem(label='Options'), isFolder=False)
             xbmcgui.Window(10000).currentItem.addContextMenuItems(folder_cm)

        # Finalize directory listing
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=False)
        utils.log(f"[BROWSE FOLDER] Successfully finished browsing folder '{folder_name}'", "INFO")

    except Exception as e:
        utils.log(f"[BROWSE FOLDER] ERROR: Exception occurred - {str(e)}", "ERROR")
        import traceback
        utils.log(f"[BROWSE FOLDER] Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', f'Error browsing folder: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        # Ensure plugin ends even on error
        import xbmcplugin
        import sys
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False, cacheToDisc=False)

def create_folder(params):
    """Create a new folder"""
    utils.log(f"[CREATE FOLDER] Starting create_folder with params: {params}", "INFO")
    parent_id = params.get('parent_id', [None])[0]
    if parent_id is None:
        parent_id = None # Ensure it's None if not provided or is an empty list
    elif isinstance(parent_id, list):
        parent_id = parent_id[0]

    if parent_id and str(parent_id).isdigit():
        parent_id = int(parent_id)
    else:
        parent_id = None # If not a valid ID, treat as root

    utils.log(f"[CREATE FOLDER] Parent ID determined as: {parent_id}", "DEBUG")

    folder_name = xbmcgui.Dialog().input('New folder name', type=xbmcgui.INPUT_ALPHANUM)
    utils.log(f"[CREATE FOLDER] Input dialog closed. Name entered: '{folder_name}'", "DEBUG")

    if not folder_name:
        utils.log("[CREATE FOLDER] No folder name entered. Cancelling.", "INFO")
        return

    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Check if a folder with the same name already exists in the same parent
        existing_folders = db_manager.fetch_folders_by_parent_id(parent_id)
        for folder in existing_folders:
            if folder['name'].lower() == folder_name.lower():
                utils.log(f"[CREATE FOLDER] ERROR: Folder with name '{folder_name}' already exists in parent ID {parent_id}.", "ERROR")
                xbmcgui.Dialog().notification('LibraryGenie', 'Folder with this name already exists', xbmcgui.NOTIFICATION_ERROR)
                return

        # Create the folder
        folder_id = db_manager.create_folder(folder_name, parent_id)
        utils.log(f"[CREATE FOLDER] Folder '{folder_name}' created with ID: {folder_id}", "INFO")
        xbmcgui.Dialog().notification('LibraryGenie', 'Folder created')

        # Refresh the container to show the new folder
        xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        utils.log(f"[CREATE FOLDER] ERROR: Failed to create folder '{folder_name}': {str(e)}", "ERROR")
        import traceback
        utils.log(f"[CREATE FOLDER] Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create folder', xbmcgui.NOTIFICATION_ERROR)

def delete_folder(params):
    """Delete a folder and all its contents"""
    folder_id = params.get('folder_id', [None])[0]
    if not folder_id:
        utils.log("[DELETE FOLDER] ERROR: No folder_id provided.", "ERROR")
        return

    try:
        folder_id = int(folder_id)
        utils.log(f"[DELETE FOLDER] Received folder_id: {folder_id}", "DEBUG")
    except (ValueError, TypeError) as e:
        utils.log(f"[DELETE FOLDER] ERROR: Invalid folder_id format '{folder_id}': {str(e)}", "ERROR")
        return

    # Check if the folder is protected
    config = Config()
    db_manager = DatabaseManager(config.db_path)
    if db_manager.is_folder_protected(folder_id):
        utils.log(f"[DELETE FOLDER] WARN: Attempted to delete protected folder (ID: {folder_id}).", "WARNING")
        xbmcgui.Dialog().notification('LibraryGenie', 'Cannot delete protected folder', xbmcgui.NOTIFICATION_WARNING)
        return

    # Confirm deletion
    folder_name = db_manager.get_folder_name(folder_id) # Fetch name for confirmation dialog
    if not folder_name: folder_name = f"folder ID {folder_id}" # Fallback name

    if not xbmcgui.Dialog().yesno('Delete Folder', f'Are you sure you want to delete "{folder_name}" and all its contents?'):
        utils.log(f"[DELETE FOLDER] Deletion of folder ID {folder_id} cancelled by user.", "INFO")
        return

    try:
        utils.log(f"[DELETE FOLDER] Proceeding with deletion of folder ID: {folder_id}", "INFO")
        # Delete all lists within the folder
        lists_to_delete = db_manager.fetch_lists_by_folder(folder_id)
        for lst in lists_to_delete:
            db_manager.delete_list_and_items(lst['id']) # Use a method that handles cascading deletes

        # Delete all subfolders recursively
        subfolders_to_delete = db_manager.fetch_folders_by_parent_id(folder_id)
        for subfolder in subfolders_to_delete:
            delete_folder({'folder_id': subfolder['id']}) # Recursive call

        # Delete the folder itself
        db_manager.delete_data('folders', f"id = {folder_id}")

        utils.log(f"[DELETE FOLDER] Successfully deleted folder ID: {folder_id}", "INFO")
        xbmcgui.Dialog().notification('LibraryGenie', 'Folder deleted')
        xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        utils.log(f"[DELETE FOLDER] ERROR: Failed to delete folder ID {folder_id}: {str(e)}", "ERROR")
        import traceback
        utils.log(f"[DELETE FOLDER] Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to delete folder', xbmcgui.NOTIFICATION_ERROR)

def move_folder(params):
    """Move a folder to a different parent folder or root"""
    folder_id = params.get('folder_id', [None])[0]
    if not folder_id:
        utils.log("[MOVE FOLDER] ERROR: No folder_id provided.", "ERROR")
        return

    try:
        folder_id = int(folder_id)
        utils.log(f"[MOVE FOLDER] Received folder_id: {folder_id}", "DEBUG")
    except (ValueError, TypeError) as e:
        utils.log(f"[MOVE FOLDER] ERROR: Invalid folder_id format '{folder_id}': {str(e)}", "ERROR")
        return

    config = Config()
    db_manager = DatabaseManager(config.db_path)

    # Check if the folder is protected
    if db_manager.is_folder_protected(folder_id):
        utils.log(f"[MOVE FOLDER] WARN: Attempted to move protected folder (ID: {folder_id}).", "WARNING")
        xbmcgui.Dialog().notification('LibraryGenie', 'Cannot move protected folder', xbmcgui.NOTIFICATION_WARNING)
        return

    # Get current folder info
    current_folder_details = db_manager.fetch_folder_by_id(folder_id)
    if not current_folder_details:
        utils.log(f"[MOVE FOLDER] ERROR: Folder with ID {folder_id} not found.", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found', xbmcgui.NOTIFICATION_ERROR)
        return

    current_folder_name = current_folder_details['name']
    current_parent_id = current_folder_details.get('parent_id')

    utils.log(f"[MOVE FOLDER] Moving folder '{current_folder_name}' (ID: {folder_id}, Current Parent: {current_parent_id})", "INFO")

    # Get all available folders for selection (excluding the current folder and its descendants to prevent cycles)
    available_folders = db_manager.fetch_all_folders()
    folder_options = ["Root (No folder)"]
    folder_ids = [None] # Root folder represented as None

    # Build a set of descendant folder IDs to exclude
    descendant_ids = set()
    def get_descendants(f_id):
        for f in available_folders:
            if f['parent_id'] == f_id:
                descendant_ids.add(f['id'])
                get_descendants(f['id'])
    get_descendants(folder_id)
    descendant_ids.add(folder_id) # Include the folder itself

    for folder in available_folders:
        if folder['id'] not in descendant_ids:
            # Check if moving to this folder would exceed depth limit
            folder_depth = db_manager.get_folder_depth(folder['id'])
            if folder_depth < config.max_folder_depth:
                # Build folder path for display
                folder_path = folder['name']
                current = folder
                while current.get('parent_id'):
                    parent = db_manager.fetch_folder_by_id(current['parent_id'])
                    if parent:
                        folder_path = f"{parent['name']} > {folder_path}"
                        current = parent
                    else:
                        break
                folder_options.append(folder_path)
                folder_ids.append(folder['id'])

    # Show folder selection dialog
    selected_index = xbmcgui.Dialog().select(
        f"Move folder '{current_folder_name}' to:",
        folder_options
    )

    if selected_index == -1: # User cancelled
        utils.log(f"[MOVE FOLDER] Move operation cancelled for folder ID {folder_id}.", "INFO")
        return

    target_parent_id = folder_ids[selected_index]

    # Check if the target parent is the same as the current parent
    if target_parent_id == current_parent_id:
        utils.log(f"[MOVE FOLDER] WARN: Folder '{current_folder_name}' is already in the target location (Parent ID: {target_parent_id}).", "WARNING")
        xbmcgui.Dialog().notification('LibraryGenie', 'Folder is already in that location', xbmcgui.NOTIFICATION_INFO)
        return

    # Check if the target parent would cause a depth violation
    if target_parent_id is not None:
        new_depth = db_manager.get_folder_depth(target_parent_id) + 1
        if new_depth > config.max_folder_depth:
            utils.log(f"[MOVE FOLDER] ERROR: Moving folder '{current_folder_name}' to parent ID {target_parent_id} would exceed max folder depth ({config.max_folder_depth}).", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', f'Moving this folder would exceed the maximum folder depth of {config.max_folder_depth}.', xbmcgui.NOTIFICATION_ERROR)
            return

    try:
        utils.log(f"[MOVE FOLDER] Moving folder ID {folder_id} to parent ID {target_parent_id}", "INFO")
        db_manager.update_data('folders', {'parent_id': target_parent_id}, f"id = {folder_id}")
        utils.log(f"[MOVE FOLDER] Successfully moved folder ID {folder_id} to parent ID {target_parent_id}", "INFO")
        xbmcgui.Dialog().notification('LibraryGenie', 'Folder moved')
        xbmc.executebuiltin('Container.Refresh')
    except Exception as e:
        utils.log(f"[MOVE FOLDER] ERROR: Failed to move folder ID {folder_id}: {str(e)}", "ERROR")
        import traceback
        utils.log(f"[MOVE FOLDER] Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to move folder', xbmcgui.NOTIFICATION_ERROR)