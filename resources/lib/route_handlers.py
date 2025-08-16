"""Route handlers for LibraryGenie plugin actions"""
import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
import json # Added for json.loads
import threading

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
            list(folder_options)
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



def find_similar_movies(params):
    """Handler for similarity search from native Kodi context menu (via context.py)"""
    try:
        # Extract parameters
        imdb_id = params.get('imdb_id', [None])[0] if params.get('imdb_id') else None
        title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown'

        if not imdb_id or not imdb_id.startswith('tt'):
            xbmcgui.Dialog().ok('LibraryGenie', "This item doesn't have a valid IMDb ID.")
            return

        # URL decode the title
        import urllib.parse
        title = urllib.parse.unquote_plus(title)

        # This action is triggered from context.py (native context menu), so use context menu navigation
        _perform_similarity_search(imdb_id, title, from_context_menu=True)

    except Exception as e:
        utils.log(f"Error in find_similar_movies: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Similarity search error', xbmcgui.NOTIFICATION_ERROR)

def find_similar_movies_from_plugin(params):
    """Handler for similarity search from plugin ListItems (context menu items added by listitem_builder.py)"""
    try:
        # Extract parameters
        imdb_id = params.get('imdb_id', [None])[0] if params.get('imdb_id') else None
        title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown'

        if not imdb_id or not imdb_id.startswith('tt'):
            xbmcgui.Dialog().ok('LibraryGenie', "This item doesn't have a valid IMDb ID.")
            return

        # URL decode the title
        import urllib.parse
        title = urllib.parse.unquote_plus(title)

        # This is from plugin context items, so use plugin navigation
        _perform_similarity_search(imdb_id, title, from_context_menu=False)

    except Exception as e:
        utils.log(f"Error in find_similar_movies_from_plugin: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Similarity search error', xbmcgui.NOTIFICATION_ERROR)

def find_similar_movies_from_context(params):
    """Handler for similarity search from native Kodi context menu"""
    try:
        # Get focused item info from Kodi
        import xbmc
        
        # Get IMDb ID from our custom property (set by listitem_builder.py)
        imdb_id = xbmc.getInfoLabel('ListItem.Property(LibraryGenie.IMDbID)')
        
        # Simple fallback for non-LibraryGenie items
        if not imdb_id:
            fallback_candidates = [
                xbmc.getInfoLabel('ListItem.IMDBNumber'),
                xbmc.getInfoLabel('ListItem.UniqueID(imdb)')
            ]
            for candidate in fallback_candidates:
                if candidate and str(candidate).startswith('tt'):
                    imdb_id = candidate
                    break
        
        if imdb_id:
            utils.log(f"Similarity search found IMDb ID: {imdb_id}", "INFO")
                
        title = xbmc.getInfoLabel('ListItem.Title')
        year = xbmc.getInfoLabel('ListItem.Year')
        
        utils.log(f"Similarity search - Title: {title}, Year: {year}, IMDb: {imdb_id}", "DEBUG")

        if not imdb_id or not imdb_id.startswith('tt'):
            utils.log("Similarity search failed - no valid IMDb ID found", "WARNING")
            xbmcgui.Dialog().ok('LibraryGenie', "This item doesn't have a valid IMDb ID.")
            return

        # Use title with year if available
        display_title = f"{title} ({year})" if year and year != '0' else title

        # Perform similarity search with context menu flag
        _perform_similarity_search(imdb_id, display_title, from_context_menu=True)

    except Exception as e:
        utils.log(f"Error in find_similar_movies_from_context: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Similarity search error', xbmcgui.NOTIFICATION_ERROR)

def _perform_similarity_search(imdb_id, title, from_context_menu=False):
    """Perform the actual similarity search and create list"""
    try:
        from resources.lib.remote_api_client import RemoteAPIClient
        from resources.lib.config_manager import Config
        from resources.lib.query_manager import QueryManager

        config = Config()

        # Show facet selection dialog
        available_facets = ["Plot", "Mood/tone", "Themes", "Genre"]
        facet_descriptions = [
            "Plot - Story structure and narrative elements",
            "Mood/tone - Emotional atmosphere and feel",
            "Themes - Underlying messages and concepts", 
            "Genre - Movie categories and tropes"
        ]

        utils.log(f"=== SIMILARITY_SEARCH: Showing facet selection dialog ===", "DEBUG")
        
        # Show multi-select dialog for facets
        selected_indices = xbmcgui.Dialog().multiselect(
            f"Select similarity aspects for '{title}':",
            list(facet_descriptions)
        )

        if selected_indices is None or len(selected_indices) == 0:
            utils.log("User cancelled facet selection or selected no facets", "DEBUG")
            return

        # Convert selections to facet list
        facets_list = [available_facets[i] for i in selected_indices]
        utils.log(f"User selected facets: {facets_list}", "DEBUG")

        # Save user's selection for future use
        config.set_setting('similarity_facets', json.dumps(facets_list))

        # Convert to API parameters
        facet_params = {
            'plot': 'Plot' in facets_list,
            'mood': 'Mood/tone' in facets_list,
            'themes': 'Themes' in facets_list,
            'genre': 'Genre' in facets_list
        }

        utils.log(f"Making similarity request for {imdb_id} with facets: plot={facet_params['plot']}, mood={facet_params['mood']}, themes={facet_params['themes']}, genre={facet_params['genre']}", "DEBUG")

        # Make API request
        client = RemoteAPIClient()
        similar_movies = client.find_similar_movies(
            imdb_id,
            include_plot=facet_params['plot'],
            include_mood=facet_params['mood'],
            include_themes=facet_params['themes'],
            include_genre=facet_params['genre']
        )

        if not similar_movies:
            xbmcgui.Dialog().ok('LibraryGenie', 'No similar movies found.')
            return

        utils.log(f"Found {len(similar_movies)} similar movies", "INFO")
        utils.log(f"=== SIMILARITY_SEARCH: Raw API response sample (first 3): {similar_movies[:3]} ===", "DEBUG")

        # Create list name with facet description
        facet_names = [name for name, enabled in zip(['Plot', 'Mood/tone', 'Themes', 'Genre'], 
                                                    [facet_params['plot'], facet_params['mood'], 
                                                     facet_params['themes'], facet_params['genre']]) 
                      if enabled]
        facet_desc = ' + '.join(facet_names)

        # Get search history folder
        query_manager = QueryManager(config.db_path)
        search_folder = query_manager.ensure_search_history_folder()

        # Check if search folder was created successfully
        if search_folder is None:
            utils.log("Failed to ensure search history folder. Cannot proceed.", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to find/create necessary folder', xbmcgui.NOTIFICATION_ERROR)
            return

        # Create unique list name
        base_name = f"Similar to {title} ({facet_desc})"
        list_name = query_manager.get_unique_list_name(base_name, search_folder['id'])
        utils.log(f"=== SIMILARITY_SEARCH: Creating list '{list_name}' in folder {search_folder['id']} ===", "DEBUG")

        # Create the list
        new_list = query_manager.create_list(list_name, search_folder['id'])
        if not new_list:
            xbmcgui.Dialog().ok('LibraryGenie', 'Failed to create similarity list.')
            return

        utils.log(f"=== SIMILARITY_SEARCH: Created list with ID {new_list['id']} ===", "DEBUG")

        # Process similar movies following the same flow as regular search
        utils.log(f"=== SIMILARITY_SEARCH: Processing {len(similar_movies)} IMDb IDs ===", "DEBUG")

        # Step 1: Convert IMDb IDs to format expected by search results
        search_results = []
        for i, movie_data in enumerate(similar_movies):
            # Handle both string format (just IMDb ID) and object format
            if isinstance(movie_data, str):
                imdb = movie_data
                score = len(similar_movies) - i  # Use reverse index as score for ordering
            else:
                imdb = movie_data.get('imdb_id', '')
                score = movie_data.get('score', 0)

            if imdb and imdb.startswith('tt'):
                search_results.append({
                    'imdbnumber': imdb,
                    'score': score,
                    'search_score': score
                })

        utils.log(f"=== SIMILARITY_SEARCH: Converted to {len(search_results)} search results ===", "DEBUG")

        if search_results:
            # Step 2: Create media items for each search result following the search pattern
            utils.log(f"=== SIMILARITY_SEARCH: Creating media items for {len(search_results)} results ===", "DEBUG")
            
            for i, result in enumerate(search_results):
                imdb_id = result['imdbnumber']
                search_score = result.get('search_score', 0)
                
                utils.log(f"=== SIMILARITY_SEARCH: Processing result {i+1}/{len(search_results)}: {imdb_id} (score: {search_score}) ===", "DEBUG")
                
                # Look up title and year from imdb_exports if available
                title_lookup = ''
                year_lookup = 0
                
                try:
                    lookup_query = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                    lookup_result = query_manager.execute_query(lookup_query, (imdb_id,))
                    if lookup_result:
                        title_lookup = lookup_result[0].get('title', '')
                        year_lookup = int(lookup_result[0].get('year', 0) or 0)
                        utils.log(f"=== SIMILARITY_SEARCH: Found title/year for {imdb_id}: '{title_lookup}' ({year_lookup}) ===", "DEBUG")
                    else:
                        utils.log(f"=== SIMILARITY_SEARCH: No imdb_exports entry for {imdb_id} ===", "DEBUG")
                except Exception as e:
                    utils.log(f"=== SIMILARITY_SEARCH: Error looking up title/year for {imdb_id}: {str(e)} ===", "ERROR")
                
                # Create media item with available data
                media_item_data = {
                    'kodi_id': 0,
                    'title': title_lookup or f'IMDB: {imdb_id}',
                    'year': year_lookup,
                    'imdbnumber': imdb_id,
                    'source': 'search',
                    'plot': '',
                    'rating': 0.0,
                    'search_score': search_score,
                    'media_type': 'movie'
                }
                
                utils.log(f"=== SIMILARITY_SEARCH: Creating media item: title='{media_item_data['title']}', year={media_item_data['year']}, imdb={imdb_id} ===", "DEBUG")
                
                # Insert media item and add to list
                try:
                    success = query_manager.insert_media_item_and_add_to_list(new_list['id'], media_item_data)
                    if success:
                        utils.log(f"=== SIMILARITY_SEARCH: Successfully added {imdb_id} to list ===", "DEBUG")
                    else:
                        utils.log(f"=== SIMILARITY_SEARCH: Failed to add {imdb_id} to list ===", "ERROR")
                except Exception as e:
                    utils.log(f"=== SIMILARITY_SEARCH: Error adding {imdb_id} to list: {str(e)} ===", "ERROR")

        utils.log(f"=== SIMILARITY_SEARCH: Finished processing {len(search_results)} movies into list {new_list['id']} ===", "DEBUG")

        # Show confirmation and navigate based on context
        xbmcgui.Dialog().notification('LibraryGenie', f'Created similarity list with {len(similar_movies)} movies', xbmcgui.NOTIFICATION_INFO)

        if from_context_menu:
            # For context menu execution, use ActivateWindow for more reliable navigation
            target_url = _build_plugin_url({
                'action': 'browse_list',
                'list_id': new_list['id'],
            })
            
            if target_url:
                utils.log(f"=== SIMILARITY_SEARCH: Using ActivateWindow navigation from context menu: {target_url} ===", "DEBUG")
                # Use ActivateWindow for context menu navigation
                import threading
                import time
                
                def delayed_activate():
                    time.sleep(1.5)  # Wait for notification to show
                    utils.log(f"=== CONTEXT_MENU_NAVIGATION: Activating window: {target_url} ===", "DEBUG")
                    xbmc.executebuiltin(f'ActivateWindow(videos,"{target_url}",return)')
                    utils.log(f"=== CONTEXT_MENU_NAVIGATION: ActivateWindow completed ===", "DEBUG")
                
                nav_thread = threading.Thread(target=delayed_activate)
                nav_thread.daemon = True
                nav_thread.start()
        else:
            # For plugin execution, use Container.Update
            target_url = _build_plugin_url({
                'action': 'browse_list',
                'list_id': new_list['id'],
            })
            
            if target_url:
                utils.log(f"=== SIMILARITY_SEARCH: Using Container.Update navigation from plugin: {target_url} ===", "DEBUG")
                # Use delayed navigation similar to SearchWindow pattern
                _schedule_delayed_navigation(target_url)
        
        utils.log(f"=== SIMILARITY_SEARCH: Similarity search complete - list ID: {new_list['id']} ===", "INFO")

    except Exception as e:
        utils.log(f"Error in similarity search: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Similarity search traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Similarity search failed', xbmcgui.NOTIFICATION_ERROR)


def _build_plugin_url(params):
    """Build a clean plugin URL with proper encoding"""
    try:
        from urllib.parse import urlencode
        from resources.lib.addon_ref import get_addon

        addon = get_addon()
        addon_id = addon.getAddonInfo("id")
        base_url = f"plugin://{addon_id}/"

        # Clean params - only include non-empty values
        cleaned_params = {k: str(v) for k, v in params.items() if v not in (None, '', False)}

        if cleaned_params:
            query_string = urlencode(cleaned_params)
            return f"{base_url}?{query_string}"
        else:
            return base_url

    except Exception as e:
        utils.log(f"Error building URL: {str(e)}", "ERROR")
        return None

def _schedule_delayed_navigation(target_url):
    """Schedule delayed navigation after modal cleanup"""
    def delayed_navigate():
        try:
            # Wait for modal cleanup
            import time
            time.sleep(2.0)  # Give time for notification and modal cleanup
            
            utils.log(f"=== DELAYED_NAVIGATION: Starting navigation to: {target_url} ===", "DEBUG")
            
            # Clear any lingering modal states
            xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
            xbmc.executebuiltin("Dialog.Close(all,true)")
            
            # Brief wait for cleanup
            time.sleep(0.5)
            
            # Navigate using Container.Update for reliable plugin navigation
            utils.log(f"=== DELAYED_NAVIGATION: Using Container.Update to navigate ===", "DEBUG")
            xbmc.executebuiltin(f'Container.Update({target_url})')
            
            utils.log(f"=== DELAYED_NAVIGATION: Navigation completed ===", "DEBUG")
            
        except Exception as e:
            utils.log(f"Error in delayed navigation: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Delayed navigation traceback: {traceback.format_exc()}", "ERROR")
    
    # Start navigation in background thread
    nav_thread = threading.Thread(target=delayed_navigate)
    nav_thread.daemon = True
    nav_thread.start()
