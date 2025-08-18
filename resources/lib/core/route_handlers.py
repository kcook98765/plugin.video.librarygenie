"""Route handlers for LibraryGenie plugin actions"""
import xbmc
import xbmcgui
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
import json
import threading
from typing import List, Union, cast

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
        from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC
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
        created_list = db_manager.create_list(name, folder_id)
        if not created_list:
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create new list', xbmcgui.NOTIFICATION_ERROR)
            return

        # Extract list ID from returned dictionary
        selected_list_id = created_list['id'] if isinstance(created_list, dict) else created_list
        utils.log(f"Created new list '{name}' with ID: {selected_list_id}", "DEBUG")
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
    media_id = params.get('media_id', [None])[0] or params.get('movie_id', [None])[0]  # Support both parameter names

    utils.log(f"remove_from_list called with list_id={list_id}, media_id={media_id}", "DEBUG")

    if not list_id:
        utils.log("remove_from_list: Missing list_id parameter", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error: Missing list ID', xbmcgui.NOTIFICATION_ERROR)
        return

    if not media_id:
        utils.log("remove_from_list: Missing media_id parameter", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error: Missing media ID', xbmcgui.NOTIFICATION_ERROR)
        return

    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get list name and media title for confirmation dialog
        list_info = db_manager.fetch_list_by_id(list_id)
        list_name = list_info.get('name', 'Unknown List') if list_info else 'Unknown List'

        # Get media info from the list_items table with media_items join
        try:
            query = """
                SELECT m.title, m.year
                FROM list_items li
                JOIN media_items m ON li.media_item_id = m.id
                WHERE li.list_id = ? AND m.id = ?
            """
            db_manager.cursor.execute(query, (list_id, media_id))
            media_result = db_manager.cursor.fetchone()
            if media_result:
                media_title = media_result[0] or 'Unknown Movie'
            else:
                media_title = 'Unknown Movie'
        except Exception as e:
            utils.log(f"Error fetching media title: {str(e)}", "WARNING")
            media_title = 'Unknown Movie'

        # Show confirmation dialog
        if not xbmcgui.Dialog().yesno(
            'Remove from List',
            f'Remove "{media_title}" from "{list_name}"?\n\nThis action cannot be undone.'
        ):
            utils.log("User cancelled removal from list", "DEBUG")
            return

        # Check if the item exists before trying to delete
        check_query = f"SELECT COUNT(*) as count FROM list_items WHERE list_id = {list_id} AND media_item_id = {media_id}"
        result = db_manager.cursor.execute(check_query).fetchone()
        item_count = result[0] if result else 0

        if item_count == 0:
            utils.log(f"Item not found in list: list_id={list_id}, media_item_id={media_id}", "WARNING")
            xbmcgui.Dialog().notification('LibraryGenie', 'Item not found in list', xbmcgui.NOTIFICATION_WARNING)
        else:
            db_manager.delete_data('list_items', f"list_id = {list_id} AND media_item_id = {media_id}")
            utils.log(f"Successfully removed item from list: list_id={list_id}, media_item_id={media_id}", "INFO")
            xbmcgui.Dialog().notification('LibraryGenie', f'Removed "{media_title}" from list')

        # Always refresh the container regardless of success/failure
        xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        utils.log(f"Error removing from list: {str(e)}", "ERROR")
        import traceback
        utils.log(f"remove_from_list traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Failed to remove from list', xbmcgui.NOTIFICATION_ERROR)
        # Still refresh container to ensure UI is updated
        xbmc.executebuiltin('Container.Refresh')

def move_list(params):
    """Move a list to a different folder"""
    try:
        list_id = params.get('list_id', [None])[0]
        if not list_id:
            utils.log("No list_id provided for move_list", "ERROR")
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get current list info
        list_info = db_manager.fetch_list_by_id(list_id)
        if not list_info:
            utils.log(f"List {list_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'List not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Get all folders for selection (excluding Search History)
        all_folders = db_manager.fetch_all_folders()
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

        # Filter out Search History folder and current folder
        available_folders = []
        for folder in all_folders:
            if (folder['id'] != search_history_folder_id and 
                folder['id'] != list_info.get('folder_id')):
                available_folders.append(folder)

        if not available_folders:
            xbmcgui.Dialog().notification('LibraryGenie', 'No target folders available', xbmcgui.NOTIFICATION_WARNING)
            return

        # Create folder selection options
        folder_options = ["Root Folder"]  # Option to move to root
        folder_ids = [None]  # None indicates root folder

        for folder in available_folders:
            folder_options.append(f"{folder['name']}")
            folder_ids.append(folder['id'])

        # Show folder selection dialog
        typed_folder_options = cast(List[Union[str, xbmcgui.ListItem]], folder_options)
        selected_index = xbmcgui.Dialog().select(
            f"Move '{list_info['name']}' to folder:",
            typed_folder_options
        )

        if selected_index == -1:  # User cancelled
            return

        target_folder_id = folder_ids[selected_index]
        target_folder_name = "Root Folder" if target_folder_id is None else available_folders[selected_index - 1]['name']

        # Confirm the move
        if not xbmcgui.Dialog().yesno(
            'LibraryGenie',
            f"Move '{list_info['name']}' to '{target_folder_name}'?",
            'This action cannot be undone.'
        ):
            return

        # Perform the move
        success = db_manager.move_list_to_folder(list_id, target_folder_id)

        if success:
            utils.log(f"Successfully moved list {list_id} to folder {target_folder_id}", "INFO")
            xbmcgui.Dialog().notification('LibraryGenie', f"Moved '{list_info['name']}' to '{target_folder_name}'", xbmcgui.NOTIFICATION_INFO)
            # Refresh the current container
            xbmc.executebuiltin('Container.Refresh')
        else:
            utils.log(f"Failed to move list {list_id} to folder {target_folder_id}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to move list', xbmcgui.NOTIFICATION_ERROR)

    except Exception as e:
        utils.log(f"Error in move_list: {str(e)}", "ERROR")
        import traceback
        utils.log(f"move_list traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error moving list', xbmcgui.NOTIFICATION_ERROR)


def add_movies_to_list(params):
    """Add additional movies to an existing list"""
    try:
        list_id = params.get('list_id', [None])[0]
        if not list_id:
            utils.log("No list_id provided for add_movies_to_list", "ERROR")
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get list info
        list_info = db_manager.fetch_list_by_id(list_id)
        if not list_info:
            utils.log(f"List {list_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'List not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Show search dialog to find movies to add
        from resources.lib.kodi.window_search import SearchWindow
        search_window = SearchWindow(f"Add Movies to '{list_info['name']}'")
        search_window.doModal()

        # Check if search was successful and get the results
        target_url = search_window.get_target_url()
        if target_url and 'list_id=' in target_url:
            # Extract the search results list ID
            import re
            match = re.search(r'list_id=(\d+)', target_url)
            if match:
                search_results_list_id = match.group(1)

                # Get all items from the search results list
                search_items = db_manager.query_manager.fetch_list_items_with_details(search_results_list_id)

                if search_items:
                    # Add each search result to the target list
                    added_count = 0
                    for item in search_items:
                        # Check if item already exists in target list
                        existing_item = db_manager.query_manager.get_list_item_by_media_id(list_id, item['id'])
                        if not existing_item:
                            # Create media item data from search result
                            media_item_data = {
                                'kodi_id': item.get('kodi_id', 0),
                                'title': item.get('title', ''),
                                'year': item.get('year', 0),
                                'imdbnumber': item.get('imdbnumber', ''),
                                'source': item.get('source', 'library'),
                                'plot': item.get('plot', ''),
                                'rating': item.get('rating', 0.0),
                                'search_score': 0,  # Reset search score for manual additions
                                'media_type': item.get('media_type', 'movie'),
                                'genre': item.get('genre', ''),
                                'director': item.get('director', ''),
                                'cast': item.get('cast', '[]'),
                                'file': item.get('file', ''),
                                'thumbnail': item.get('thumbnail', ''),
                                'poster': item.get('poster', ''),
                                'fanart': item.get('fanart', ''),
                                'art': item.get('art', '{}'),
                                'duration': item.get('duration', 0),
                                'votes': item.get('votes', 0),
                                'play': item.get('play', '')
                            }

                            success = db_manager.add_media_item(list_id, media_item_data)
                            if success:
                                added_count += 1

                    if added_count > 0:
                        xbmcgui.Dialog().notification('LibraryGenie', f"Added {added_count} movies to '{list_info['name']}'", xbmcgui.NOTIFICATION_INFO)
                        xbmc.executebuiltin('Container.Refresh')
                    else:
                        xbmcgui.Dialog().notification('LibraryGenie', 'No new movies were added', xbmcgui.NOTIFICATION_INFO)
                else:
                    xbmcgui.Dialog().notification('LibraryGenie', 'No search results found', xbmcgui.NOTIFICATION_WARNING)
        else:
            utils.log("Search was cancelled or failed", "DEBUG")

    except Exception as e:
        utils.log(f"Error in add_movies_to_list: {str(e)}", "ERROR")
        import traceback
        utils.log(f"add_movies_to_list traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error adding movies to list', xbmcgui.NOTIFICATION_ERROR)


def clear_list(params):
    """Remove all items from a list"""
    try:
        list_id = params.get('list_id', [None])[0]
        if not list_id:
            utils.log("No list_id provided for clear_list", "ERROR")
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get list info
        list_info = db_manager.fetch_list_by_id(list_id)
        if not list_info:
            utils.log(f"List {list_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'List not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Get current item count
        item_count = db_manager.get_list_media_count(list_id)

        if item_count == 0:
            xbmcgui.Dialog().notification('LibraryGenie', f"'{list_info['name']}' is already empty", xbmcgui.NOTIFICATION_INFO)
            return

        # Confirm the clear operation
        if not xbmcgui.Dialog().yesno(
            'LibraryGenie',
            f"Clear all {item_count} items from '{list_info['name']}'?",
            'This action cannot be undone.'
        ):
            return

        # Clear all items from the list
        success = db_manager.clear_list_items(list_id)

        if success:
            utils.log(f"Successfully cleared list {list_id}", "INFO")
            xbmcgui.Dialog().notification('LibraryGenie', f"Cleared '{list_info['name']}'", xbmcgui.NOTIFICATION_INFO)
            xbmc.executebuiltin('Container.Refresh')
        else:
            utils.log(f"Failed to clear list {list_id}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to clear list', xbmcgui.NOTIFICATION_ERROR)

    except Exception as e:
        utils.log(f"Error in clear_list: {str(e)}", "ERROR")
        import traceback
        utils.log(f"clear_list traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error clearing list', xbmcgui.NOTIFICATION_ERROR)


def export_list(params):
    """Export list contents to a file"""
    try:
        list_id = params.get('list_id', [None])[0]
        if not list_id:
            utils.log("No list_id provided for export_list", "ERROR")
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get list info
        list_info = db_manager.fetch_list_by_id(list_id)
        if not list_info:
            utils.log(f"List {list_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'List not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Get list items
        list_items = db_manager.fetch_list_items_with_details(list_id)
        if not list_items:
            xbmcgui.Dialog().notification('LibraryGenie', f"'{list_info['name']}' is empty", xbmcgui.NOTIFICATION_WARNING)
            return

        # Choose export format
        export_formats = ["Plain Text (.txt)", "CSV (.csv)", "JSON (.json)"]
        typed_export_formats = cast(List[Union[str, xbmcgui.ListItem]], export_formats)
        selected_format = xbmcgui.Dialog().select("Choose export format:", typed_export_formats)

        if selected_format == -1:  # User cancelled
            return

        # Generate export content based on format
        import json
        import csv
        import io
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_list_name = "".join(c for c in list_info['name'] if c.isalnum() or c in (' ', '-', '_')).strip()

        if selected_format == 0:  # Plain Text
            filename = f"LibraryGenie_{safe_list_name}_{timestamp}.txt"
            content = f"LibraryGenie List Export\n"
            content += f"List Name: {list_info['name']}\n"
            content += f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"Total Items: {len(list_items)}\n\n"

            for i, item in enumerate(list_items, 1):
                content += f"{i}. {item.get('title', 'Unknown Title')}"
                if item.get('year'):
                    content += f" ({item['year']})"
                if item.get('imdbnumber'):
                    content += f" - IMDb: {item['imdbnumber']}"
                content += "\n"

        elif selected_format == 1:  # CSV
            filename = f"LibraryGenie_{safe_list_name}_{timestamp}.csv"
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(['Title', 'Year', 'IMDb ID', 'Genre', 'Director', 'Rating', 'Plot'])

            # Write data
            for item in list_items:
                writer.writerow([
                    item.get('title', ''),
                    item.get('year', ''),
                    item.get('imdbnumber', ''),
                    item.get('genre', ''),
                    item.get('director', ''),
                    item.get('rating', ''),
                    item.get('plot', '')[:100] + ('...' if len(item.get('plot', '')) > 100 else '')
                ])

            content = output.getvalue()

        else:  # JSON
            filename = f"LibraryGenie_{safe_list_name}_{timestamp}.json"
            export_data = {
                'list_name': list_info['name'],
                'export_date': datetime.now().isoformat(),
                'total_items': len(list_items),
                'items': []
            }

            for item in list_items:
                export_data['items'].append({
                    'title': item.get('title', ''),
                    'year': item.get('year', ''),
                    'imdb_id': item.get('imdbnumber', ''),
                    'genre': item.get('genre', ''),
                    'director': item.get('director', ''),
                    'rating': item.get('rating', ''),
                    'plot': item.get('plot', ''),
                    'poster': item.get('poster', ''),
                    'duration': item.get('duration', '')
                })

            content = json.dumps(export_data, indent=2, ensure_ascii=False)

        # Get export directory (use Kodi's temp directory)
        import xbmcvfs
        temp_dir = xbmcvfs.translatePath("special://temp/")
        export_path = temp_dir + filename

        # Write file
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(content)

            utils.log(f"Successfully exported list to {export_path}", "INFO")
            xbmcgui.Dialog().ok('LibraryGenie', f"List exported successfully!", f"File saved to:", export_path)

        except Exception as write_error:
            utils.log(f"Error writing export file: {str(write_error)}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Error writing export file', xbmcgui.NOTIFICATION_ERROR)

    except Exception as e:
        utils.log(f"Error in export_list: {str(e)}", "ERROR")
        import traceback
        utils.log(f"export_list traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error exporting list', xbmcgui.NOTIFICATION_ERROR)


def delete_folder(params):
    """Delete a folder and optionally its contents"""
    try:
        folder_id = params.get('folder_id', [None])[0]
        if not folder_id:
            utils.log("No folder_id provided for delete_folder", "ERROR")
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get folder info
        folder_info = db_manager.fetch_folder_by_id(folder_id)
        if not folder_info:
            utils.log(f"Folder {folder_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Check for protected folders
        protected_folders = ["Search History"]
        if folder_info['name'] in protected_folders:
            xbmcgui.Dialog().notification('LibraryGenie', 'Cannot delete protected folder', xbmcgui.NOTIFICATION_ERROR)
            return

        # Check if folder has contents
        subfolders = db_manager.fetch_folders(folder_id)
        lists = db_manager.fetch_lists(folder_id)

        total_contents = len(subfolders) + len(lists)

        if total_contents > 0:
            # Ask user what to do with contents
            content_options = [
                f"Delete folder and all {total_contents} items inside",
                "Move contents to parent folder, then delete",
                "Cancel deletion"
            ]

            typed_content_options = cast(List[Union[str, xbmcgui.ListItem]], content_options)
            selected_option = xbmcgui.Dialog().select(
                f"Folder '{folder_info['name']}' contains {total_contents} items:",
                typed_content_options
            )

            if selected_option == -1 or selected_option == 2:  # Cancel
                return
            elif selected_option == 1:  # Move contents
                # Move all subfolders and lists to parent folder
                parent_folder_id = folder_info.get('parent_id')

                for subfolder in subfolders:
                    db_manager.move_folder_to_parent(subfolder['id'], parent_folder_id)

                for list_item in lists:
                    db_manager.move_list_to_folder(list_item['id'], parent_folder_id)

        # Final confirmation
        if not xbmcgui.Dialog().yesno(
            'LibraryGenie',
            f"Delete folder '{folder_info['name']}'?",
            'This action cannot be undone.'
        ):
            return

        # Delete the folder
        success = db_manager.delete_folder(folder_id)

        if success:
            utils.log(f"Successfully deleted folder {folder_id}", "INFO")
            xbmcgui.Dialog().notification('LibraryGenie', f"Deleted folder '{folder_info['name']}'", xbmcgui.NOTIFICATION_INFO)
            xbmc.executebuiltin('Container.Refresh')
        else:
            utils.log(f"Failed to delete folder {folder_id}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to delete folder', xbmcgui.NOTIFICATION_ERROR)

    except Exception as e:
        utils.log(f"Error in delete_folder: {str(e)}", "ERROR")
        import traceback
        utils.log(f"delete_folder traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error deleting folder', xbmcgui.NOTIFICATION_ERROR)


def move_folder(params):
    """Move a folder to a different parent folder"""
    try:
        folder_id = params.get('folder_id', [None])[0]
        if not folder_id:
            utils.log("No folder_id provided for move_folder", "ERROR")
            return

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get current folder info
        folder_info = db_manager.fetch_folder_by_id(folder_id)
        if not folder_info:
            utils.log(f"Folder {folder_id} not found", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Folder not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Check for protected folders
        protected_folders = ["Search History"]
        if folder_info['name'] in protected_folders:
            xbmcgui.Dialog().notification('LibraryGenie', 'Cannot move protected folder', xbmcgui.NOTIFICATION_ERROR)
            return

        # Get all folders for selection (excluding Search History, current folder, and its descendants)
        all_folders = db_manager.fetch_all_folders()
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")
        current_parent_id = folder_info.get('parent_id')

        # Get descendant folder IDs to exclude them
        descendant_ids = db_manager.get_descendant_folder_ids(folder_id)
        descendant_ids.append(folder_id)  # Include self

        # Filter available folders
        available_folders = []
        for folder in all_folders:
            if (folder['id'] != search_history_folder_id and 
                folder['id'] not in descendant_ids and
                folder['id'] != current_parent_id):
                available_folders.append(folder)

        # Create folder selection options
        folder_options = ["📁 Root Level"]  # Option to move to root
        folder_ids = [None]  # None indicates root level

        for folder in available_folders:
            # Build folder path for display
            folder_path = db_manager.get_folder_path(folder['id'])
            folder_options.append(f"📁 {folder_path}")
            folder_ids.append(folder['id'])

        if len(folder_options) == 1:  # Only root option available
            xbmcgui.Dialog().notification('LibraryGenie', 'No target folders available', xbmcgui.NOTIFICATION_WARNING)
            return

        # Show folder selection dialog
        typed_folder_options = cast(List[Union[str, xbmcgui.ListItem]], folder_options)
        selected_index = xbmcgui.Dialog().select(
            f"Move '{folder_info['name']}' to:",
            typed_folder_options
        )

        if selected_index == -1:  # User cancelled
            return

        target_parent_id = folder_ids[selected_index]
        target_name = "Root Level" if target_parent_id is None else available_folders[selected_index - 1]['name']

        # Confirm the move
        if not xbmcgui.Dialog().yesno(
            'LibraryGenie',
            f"Move '{folder_info['name']}' to '{target_name}'?",
            'This action cannot be undone.'
        ):
            return

        # Perform the move
        success = db_manager.move_folder_to_parent(folder_id, target_parent_id)

        if success:
            utils.log(f"Successfully moved folder {folder_id} to parent {target_parent_id}", "INFO")
            xbmcgui.Dialog().notification('LibraryGenie', f"Moved '{folder_info['name']}' to '{target_name}'", xbmcgui.NOTIFICATION_INFO)
            xbmc.executebuiltin('Container.Refresh')
        else:
            utils.log(f"Failed to move folder {folder_id} to parent {target_parent_id}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to move folder', xbmcgui.NOTIFICATION_ERROR)

    except Exception as e:
        utils.log(f"Error in move_folder: {str(e)}", "ERROR")
        import traceback
        utils.log(f"move_folder traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error moving folder', xbmcgui.NOTIFICATION_ERROR)


def create_subfolder(params):
    """Create a new subfolder within an existing folder"""
    try:
        parent_folder_id = params.get('parent_folder_id', [None])[0]
        # If no parent_folder_id specified, create at root level (parent_folder_id = None)

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # If parent specified, verify it exists
        if parent_folder_id:
            parent_folder = db_manager.fetch_folder_by_id(parent_folder_id)
            if not parent_folder:
                utils.log(f"Parent folder {parent_folder_id} not found", "ERROR")
                xbmcgui.Dialog().notification('LibraryGenie', 'Parent folder not found', xbmcgui.NOTIFICATION_ERROR)
                return
            parent_name = parent_folder['name']
        else:
            parent_name = "Root Level"

        # Get folder name from user
        new_folder_name = xbmcgui.Dialog().input(
            f'Create subfolder in "{parent_name}":',
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not new_folder_name or not new_folder_name.strip():
            utils.log("User cancelled subfolder creation or entered empty name", "DEBUG")
            return

        new_folder_name = new_folder_name.strip()

        # Check if folder name already exists in the parent
        existing_folders = db_manager.fetch_folders(parent_folder_id)
        for folder in existing_folders:
            if folder['name'].lower() == new_folder_name.lower():
                xbmcgui.Dialog().notification('LibraryGenie', 'Folder name already exists', xbmcgui.NOTIFICATION_ERROR)
                return

        # Create the folder
        new_folder = db_manager.create_folder(new_folder_name, parent_folder_id)

        if new_folder:
            utils.log(f"Successfully created subfolder '{new_folder_name}' in parent {parent_folder_id}", "INFO")
            xbmcgui.Dialog().notification('LibraryGenie', f"Created folder '{new_folder_name}'", xbmcgui.NOTIFICATION_INFO)
            xbmc.executebuiltin('Container.Refresh')
        else:
            utils.log(f"Failed to create subfolder '{new_folder_name}' in parent {parent_folder_id}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create folder', xbmcgui.NOTIFICATION_ERROR)

    except Exception as e:
        utils.log(f"Error in create_subfolder: {str(e)}", "ERROR")
        import traceback
        utils.log(f"create_subfolder traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error creating subfolder', xbmcgui.NOTIFICATION_ERROR)

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

def add_to_list(params):
    """Handler for adding items to lists from context menu - simplified version"""
    try:
        # Extract parameters
        title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown'
        item_id = params.get('item_id', [None])[0] if params.get('item_id') else None

        # URL decode the title
        import urllib.parse
        title = urllib.parse.unquote_plus(title)

        utils.log(f"add_to_list called with title='{title}', item_id='{item_id}'", "DEBUG")

        # Get IMDb ID using KodiHelper which has better detection logic
        from resources.lib.kodi.kodi_helper import KodiHelper
        kodi_helper = KodiHelper()
        imdb_id = kodi_helper.get_imdb_from_item()

        # Get year from Kodi
        import xbmc
        year_str = xbmc.getInfoLabel('ListItem.Year')
        year = ""
        if year_str and year_str.isdigit():
            year = year_str

        utils.log(f"Extracted from Kodi - Title: {title}, Year: {year}, IMDb: {imdb_id}", "DEBUG")

        if not imdb_id or not imdb_id.startswith('tt'):
            xbmcgui.Dialog().ok('LibraryGenie', "This item doesn't have a valid IMDb ID.")
            return

        # Create media item object
        media_item = {
            'title': title,
            'year': int(year) if year and year.isdigit() else 0,
            'imdbnumber': imdb_id,
            'media_type': 'movie',
            'source': 'lib'
        }

        # Use database manager to handle the add to list functionality
        from resources.lib.config.config_manager import Config
        from resources.lib.data.database_manager import DatabaseManager

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get all available lists for user selection
        all_lists = db_manager.fetch_all_lists()

        # Get Search History folder ID to exclude its lists
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

        # Filter out Search History lists
        filtered_lists = []
        for list_item in all_lists:
            if list_item.get('folder_id') != search_history_folder_id:
                filtered_lists.append(list_item)

        # Create list selection options with "New List" at top
        list_options = ["Create New List"]
        list_ids = [None]  # None indicates "create new list"

        for list_item in filtered_lists:
            # Get folder path for display
            folder_path = ""
            if list_item.get('folder_id'):
                folder = db_manager.fetch_folder_by_id(list_item['folder_id'])
                if folder:
                    folder_path = f"[{folder['name']}] "

            list_options.append(f"{folder_path}{list_item['name']}")
            list_ids.append(list_item['id'])

        # Show list selection dialog
        typed_list_options = cast(List[Union[str, xbmcgui.ListItem]], list_options)
        selected_index = xbmcgui.Dialog().select(
            f"Add '{title}' to list:",
            typed_list_options
        )

        if selected_index == -1:  # User cancelled
            utils.log("User cancelled list selection", "DEBUG")
            return

        selected_list_id = list_ids[selected_index]

        # Handle "Create New List" option
        if selected_list_id is None:
            new_list_name = xbmcgui.Dialog().input('New list name', type=xbmcgui.INPUT_ALPHANUM)
            if not new_list_name:
                utils.log("User cancelled new list creation", "DEBUG")
                return

            # Create new list at root level (folder_id=None)
            created_list = db_manager.create_list(new_list_name, None)
            if not created_list:
                xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create new list', xbmcgui.NOTIFICATION_ERROR)
                return

            # Extract list ID from returned dictionary
            selected_list_id = created_list['id'] if isinstance(created_list, dict) else created_list
            utils.log(f"Created new list '{new_list_name}' with ID: {selected_list_id}", "DEBUG")


        # Create or find the media item
        existing_media = db_manager.fetch_data('media_items', f"imdbnumber = '{imdb_id}'")

        if existing_media:
            media_id = existing_media[0]['id']
            utils.log(f"Found existing media item with ID: {media_id}", "DEBUG")
        else:
            # Insert new media item
            media_id = db_manager.insert_data('media_items', media_item)
            utils.log(f"Created new media item with ID: {media_id}", "DEBUG")

        # Check if already in list
        existing_list_item = db_manager.fetch_data('list_items', f"list_id = {selected_list_id} AND media_item_id = {media_id}")

        if existing_list_item:
            xbmcgui.Dialog().notification('LibraryGenie', f'"{title}" is already in that list', xbmcgui.NOTIFICATION_INFO, 3000)
        else:
            # Add to list using the database manager's method
            try:
                success = db_manager.add_media_item(selected_list_id, media_item)

                if success:
                    utils.log(f"Successfully added item to list: list_id={selected_list_id}, media_item_id={media_id}", "DEBUG")
                    xbmcgui.Dialog().notification('LibraryGenie', f'Added "{title}" to list', xbmcgui.NOTIFICATION_INFO, 3000)
                else:
                    utils.log(f"Failed to add item to list: list_id={selected_list_id}, media_item_id={media_id}", "ERROR")
                    xbmcgui.Dialog().notification('LibraryGenie', 'Error adding to list', xbmcgui.NOTIFICATION_ERROR, 3000)

            except Exception as insert_error:
                utils.log(f"Error inserting list item: {str(insert_error)}", "ERROR")
                xbmcgui.Dialog().notification('LibraryGenie', 'Error adding to list', xbmcgui.NOTIFICATION_ERROR, 3000)

    except Exception as e:
        utils.log(f"Error in add_to_list: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error adding to list', xbmcgui.NOTIFICATION_ERROR, 3000)

def add_to_list_from_context(params):
    """Handler for adding a movie to a list from native Kodi context menu"""
    try:
        # Extract parameters
        title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown'
        imdb_id = params.get('imdb_id', [None])[0] if params.get('imdb_id') else None
        year = params.get('year', [''])[0] if params.get('year') else ''

        # URL decode the title
        import urllib.parse
        title = urllib.parse.unquote_plus(title)

        utils.log(f"Add to list from context - Title: {title}, Year: {year}, IMDb: {imdb_id}", "DEBUG")

        if not imdb_id or not imdb_id.startswith('tt'):
            xbmcgui.Dialog().ok('LibraryGenie', "This item doesn't have a valid IMDb ID.")
            return

        # Create a media item object with the available information
        media_item = {
            'title': title,
            'year': int(year) if year and year.isdigit() else 0,
            'imdbnumber': imdb_id,
            'media_type': 'movie',
            'source': 'lib'
        }

        # Use the database manager to handle the add to list functionality
        from resources.lib.config.config_manager import Config
        from resources.lib.data.database_manager import DatabaseManager

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get all available lists for user selection
        all_lists = db_manager.fetch_all_lists()

        # Get Search History folder ID to exclude its lists
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

        # Filter out Search History lists
        filtered_lists = []
        for list_item in all_lists:
            if list_item.get('folder_id') != search_history_folder_id:
                filtered_lists.append(list_item)

        # Create list selection options with "New List" at top
        list_options = ["Create New List"]
        list_ids = [None]  # None indicates "create new list"

        for list_item in filtered_lists:
            # Get folder path for display
            folder_path = ""
            if list_item.get('folder_id'):
                folder = db_manager.fetch_folder_by_id(list_item['folder_id'])
                if folder:
                    folder_path = f"[{folder['name']}] "

            list_options.append(f"{folder_path}{list_item['name']}")
            list_ids.append(list_item['id'])

        # Show list selection dialog
        typed_list_options = cast(List[Union[str, xbmcgui.ListItem]], list_options)
        selected_index = xbmcgui.Dialog().select(
            f"Add '{title}' to list:",
            typed_list_options
        )

        if selected_index == -1:  # User cancelled
            utils.log("User cancelled list selection", "DEBUG")
            return

        selected_list_id = list_ids[selected_index]

        # Handle "Create New List" option
        if selected_list_id is None:
            new_list_name = xbmcgui.Dialog().input('New list name', type=xbmcgui.INPUT_ALPHANUM)
            if not new_list_name:
                utils.log("User cancelled new list creation", "DEBUG")
                return

            # Create new list at root level (folder_id=None)
            created_list = db_manager.create_list(new_list_name, None)
            if not created_list:
                xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create new list', xbmcgui.NOTIFICATION_ERROR)
                return

            # Extract list ID from returned dictionary
            selected_list_id = created_list['id'] if isinstance(created_list, dict) else created_list
            utils.log(f"Created new list '{new_list_name}' with ID: {selected_list_id}", "DEBUG")


        # Create or find the media item
        existing_media = db_manager.fetch_data('media_items', f"imdbnumber = '{imdb_id}'")

        if existing_media:
            media_id = existing_media[0]['id']
            utils.log(f"Found existing media item with ID: {media_id}", "DEBUG")
        else:
            # Insert new media item
            media_id = db_manager.insert_data('media_items', media_item)
            utils.log(f"Created new media item with ID: {media_id}", "DEBUG")

        # Check if already in list
        existing_list_item = db_manager.fetch_data('list_items', f"list_id = {selected_list_id} AND media_item_id = {media_id}")

        if existing_list_item:
            xbmcgui.Dialog().notification('LibraryGenie', f'"{title}" is already in that list', xbmcgui.NOTIFICATION_INFO, 3000)
        else:
            # Add to list using the database manager's method
            try:
                success = db_manager.add_media_item(selected_list_id, media_item)

                if success:
                    utils.log(f"Successfully added item to list: list_id={selected_list_id}, media_item_id={media_id}", "DEBUG")
                    xbmcgui.Dialog().notification('LibraryGenie', f'Added "{title}" to list', xbmcgui.NOTIFICATION_INFO, 3000)
                else:
                    utils.log(f"Failed to add item to list: list_id={selected_list_id}, media_item_id={media_id}", "ERROR")
                    xbmcgui.Dialog().notification('LibraryGenie', 'Error adding to list', xbmcgui.NOTIFICATION_ERROR, 3000)

            except Exception as insert_error:
                utils.log(f"Error inserting list item: {str(insert_error)}", "ERROR")
                xbmcgui.Dialog().notification('LibraryGenie', 'Error adding to list', xbmcgui.NOTIFICATION_ERROR, 3000)

    except Exception as e:
        utils.log(f"Error in add_to_list_from_context: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification('LibraryGenie', 'Error adding to list', xbmcgui.NOTIFICATION_ERROR, 3000)

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
        from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
        from resources.lib.config.config_manager import Config
        from resources.lib.data.query_manager import QueryManager

        config = Config()

        # Show facet selection dialog
        available_facets = ["Plot", "Mood/tone", "Themes", "Genre"]
        facet_descriptions = [
            "Plot - Story structure and narrative elements",
            "Mood/tone - Emotional atmosphere and feel",
            "Themes - Underlying messages and concepts",
            "Genre - Movie categories and tropes"
        ]

        utils.log("=== SIMILARITY_SEARCH: Showing facet selection dialog ===", "DEBUG")

        # Load previously selected facets if available
        cached_facets_str = config.get_setting('similarity_facets')
        preselected_indices = []
        if cached_facets_str:
            try:
                cached_facets = json.loads(cached_facets_str)
                preselected_indices = [available_facets.index(facet) for facet in cached_facets if facet in available_facets]
                utils.log(f"Loaded cached facets: {cached_facets}, preselected indices: {preselected_indices}", "DEBUG")
            except (json.JSONDecodeError, ValueError) as e:
                utils.log(f"Error loading cached facets: {e}", "WARNING")

        # Show multi-select dialog for facets with preselection
        typed_facet_descriptions = cast(List[Union[str, xbmcgui.ListItem]], list(facet_descriptions))
        selected_indices = xbmcgui.Dialog().multiselect(
            f"Select similarity aspects for '{title}':",
            typed_facet_descriptions,
            preselect=preselected_indices
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
                    utils.log("=== CONTEXT_MENU_NAVIGATION: ActivateWindow completed ===", "DEBUG")

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
        from resources.lib.config.addon_ref import get_addon

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
            utils.log("=== DELAYED_NAVIGATION: Using Container.Update to navigate ===", "DEBUG")
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