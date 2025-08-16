import xbmcgui
import json
from resources.lib import utils
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.remote_api_client import RemoteAPIClient
from resources.lib.query_manager import QueryManager
from resources.lib.config_manager import Config

class IMDbUploadManager:
    def __init__(self):
        self.config = Config()
        self.remote_client = RemoteAPIClient()
        self.jsonrpc = JSONRPC()

    def get_kodi_movie_collection(self, progress_dialog=None):
        """Get all movies from Kodi library with IMDb IDs (for compatibility)"""
        full_movies = self.get_full_kodi_movie_collection(progress_dialog)
        return [{'imdb_id': movie.get('imdbnumber')} for movie in full_movies
                if movie.get('imdbnumber')]

    def get_full_kodi_movie_collection(self, progress_dialog=None):
        """Get all movies from Kodi library with full details"""
        try:
            if progress_dialog:
                progress_dialog.update(0, "Scanning Kodi library for movies...")

            movies = self.jsonrpc.get_movies_with_imdb(progress_callback=progress_dialog)

            if progress_dialog:
                progress_dialog.update(90, "Processing movie data...")

            # Filter movies with valid IMDb IDs and keep full data
            valid_movies = []
            for i, movie in enumerate(movies):
                if progress_dialog and len(movies) > 100:
                    # Update progress for large collections
                    if i % 100 == 0:
                        percent = 90 + int((i / len(movies)) * 10)
                        progress_dialog.update(percent, f"Processing movie {i+1} of {len(movies)}...")
                        if progress_dialog.iscanceled():
                            return []

                # Handle both v19 and v20+ IMDb ID extraction
                imdb_id = ''

                # First try uniqueid.imdb (most reliable in both v19 and v20+)
                if 'uniqueid' in movie:
                    uniqueid = movie.get('uniqueid', {})
                    if isinstance(uniqueid, dict):
                        uniqueid_imdb = uniqueid.get('imdb', '')
                        if uniqueid_imdb:
                            imdb_id = uniqueid_imdb

                # Fallback to imdbnumber only if uniqueid.imdb is not available
                if not imdb_id:
                    fallback_id = movie.get('imdbnumber', '')
                    # Only use imdbnumber if it's a valid IMDb ID (starts with tt)
                    if fallback_id and str(fallback_id).strip().startswith('tt'):
                        imdb_id = str(fallback_id).strip()

                # Clean up IMDb ID format
                if imdb_id:
                    imdb_id = str(imdb_id).strip()

                    # Remove common prefixes that might be present
                    if imdb_id.startswith('imdb://'):
                        imdb_id = imdb_id[7:]
                    elif imdb_id.startswith('http'):
                        # Extract tt number from URLs
                        import re
                        match = re.search(r'tt\d+', imdb_id)
                        imdb_id = match.group(0) if match else ''

                if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
                    # Ensure we have the IMDB ID in the right field
                    movie['imdbnumber'] = imdb_id
                    valid_movies.append(movie)
                    utils.log(f"Found valid IMDb ID for '{movie.get('title', 'Unknown')}': {imdb_id}", "DEBUG")

            if progress_dialog:
                progress_dialog.update(100, f"Found {len(valid_movies)} movies with valid IMDb IDs")

            # Debug logging for troubleshooting
            if len(valid_movies) == 0 and len(movies) > 0:
                utils.log("=== DEBUG: No valid IMDb IDs found, analyzing first few movies ===", "WARNING")
                for i, movie in enumerate(movies[:5]):  # Check first 5 movies
                    title = movie.get('title', 'Unknown')
                    imdbnumber = movie.get('imdbnumber', '')
                    uniqueid = movie.get('uniqueid', {})
                    all_fields = list(movie.keys())
                    utils.log(f"Movie {i+1}: '{title}'", "WARNING")
                    utils.log(f"  - All fields: {all_fields}", "WARNING")
                    utils.log(f"  - imdbnumber: '{imdbnumber}' (type: {type(imdbnumber)})", "WARNING")
                    utils.log(f"  - uniqueid: {uniqueid} (type: {type(uniqueid)})", "WARNING")
                    utils.log(f"  - Raw movie data: {json.dumps(movie, indent=2)}", "WARNING")
                utils.log("=== END DEBUG ANALYSIS ===", "WARNING")

            utils.log(f"Found {len(valid_movies)} movies with valid IMDb IDs out of {len(movies)} total movies", "INFO")
            return valid_movies

        except Exception as e:
            utils.log(f"Error getting Kodi movie collection: {str(e)}", "ERROR")
            return []


    def get_full_kodi_movie_collection_and_store_locally(self, progress_dialog=None):
        """Get all movies from Kodi library and store them locally in one efficient operation."""
        try:
            if progress_dialog:
                progress_dialog.update(0, "Scanning Kodi library and storing locally...")

            # Use database manager instead of direct query manager to avoid connection conflicts
            from resources.lib.database_manager import DatabaseManager
            db_manager = DatabaseManager(Config().db_path)

            # Clear existing library data first using database manager
            try:
                db_manager.delete_data('media_items', "source = 'lib'")
                utils.log("Cleared existing library data", "DEBUG")
            except Exception as e:
                utils.log(f"Warning: Could not clear existing library data: {str(e)}", "WARNING")

            utils.log("Getting all movies with IMDb information from Kodi library", "INFO")

            batch_size = 100
            start = 0
            all_movies = []
            last_progress_log = 0

            while True:
                params = {
                    "properties": ["title", "year", "file", "imdbnumber", "uniqueid"],
                    "limits": {"start": start, "end": start + batch_size}
                }

                response = self.jsonrpc.execute("VideoLibrary.GetMovies", params)

                if 'result' not in response or 'movies' not in response['result']:
                    utils.log("No movies found in response", "DEBUG")
                    break

                movies = response['result']['movies']
                total = response['result']['limits']['total']

                # Log progress every 1000 movies or at significant milestones
                current_count = len(all_movies) + len(movies)
                if (current_count - last_progress_log >= 1000) or (start == 0) or (len(movies) < batch_size):
                    utils.log(f"Movie retrieval progress: {current_count}/{total} movies", "INFO")
                    last_progress_log = current_count

                all_movies.extend(movies)

                if len(movies) < batch_size or start + batch_size >= total:
                    break

                start += batch_size


            if progress_dialog:
                progress_dialog.update(80, "Processing and storing movie data locally...")

            valid_movies = []
            stored_count = 0

            # Process movies with transaction batching for performance
            batch_size = 500  # Larger batches for better performance
            for batch_start in range(0, len(all_movies), batch_size):
                batch_end = min(batch_start + batch_size, len(all_movies))
                batch_movies = all_movies[batch_start:batch_end]

                if progress_dialog:
                    percent = 80 + int((batch_start / len(all_movies)) * 15)
                    progress_dialog.update(percent, f"Storing batch details {batch_start+1}-{batch_end} of {len(all_movies)}...")
                    if progress_dialog.iscanceled():
                        return valid_movies

                # Begin transaction for this batch
                try:
                    db_manager.connection.execute("BEGIN TRANSACTION")

                    batch_data = []
                    for movie in batch_movies:
                        # Prioritize uniqueid.imdb over imdbnumber for v19 compatibility
                        imdb_id = ''
                        if 'uniqueid' in movie and isinstance(movie.get('uniqueid'), dict):
                            imdb_id = movie.get('uniqueid', {}).get('imdb', '')

                        # Fallback to imdbnumber only if it looks like an IMDb ID
                        if not imdb_id:
                            fallback_id = movie.get('imdbnumber', '')
                            if fallback_id and str(fallback_id).strip().startswith('tt'):
                                imdb_id = str(fallback_id).strip()

                        if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
                            movie['imdbnumber'] = imdb_id
                            valid_movies.append(movie)

                            movie_data = {
                                'kodi_id': movie.get('movieid', 0),
                                'title': movie.get('title', ''),
                                'year': movie.get('year', 0),
                                'imdbnumber': imdb_id,
                                'source': 'lib',
                                'play': movie.get('file', ''),
                                'poster': movie.get('art', {}).get('poster', '') if movie.get('art') else '',
                                'fanart': movie.get('art', {}).get('fanart', '') if movie.get('art') else '',
                                'plot': movie.get('plot', ''),
                                'rating': float(movie.get('rating', 0)),
                                'votes': int(movie.get('votes', 0)),
                                'duration': int(movie.get('runtime', 0)),
                                'mpaa': movie.get('mpaa', ''),
                                'genre': ','.join(movie.get('genre', [])) if isinstance(movie.get('genre'), list) else movie.get('genre', ''),
                                'director': ','.join(movie.get('director', [])) if isinstance(movie.get('director'), list) else movie.get('director', ''),
                                'studio': ','.join(movie.get('studio', [])) if isinstance(movie.get('studio'), list) else movie.get('studio', ''),
                                'country': ','.join(movie.get('country', [])) if isinstance(movie.get('country'), list) else movie.get('country', ''),
                                'writer': ','.join(movie.get('writer', [])) if isinstance(movie.get('writer'), list) else movie.get('writer', ''),
                                'cast': json.dumps(movie.get('cast', [])),
                                'art': json.dumps(movie.get('art', {}))
                            }
                            batch_data.append(movie_data)

                    # Bulk insert the batch using executemany for better performance
                    if batch_data:
                        columns = ', '.join(batch_data[0].keys())
                        placeholders = ', '.join(['?' for _ in batch_data[0]])
                        query = f'INSERT OR IGNORE INTO media_items ({columns}) VALUES ({placeholders})'

                        values_list = [tuple(movie_data.values()) for movie_data in batch_data]
                        db_manager.cursor.executemany(query, values_list)
                        stored_count += len(batch_data)

                    # Commit the transaction
                    db_manager.connection.commit()

                    # Log progress every batch
                    utils.log(f"Stored {stored_count} movies to local database", "DEBUG")

                except Exception as e:
                    # Rollback on error and continue with next batch
                    db_manager.connection.rollback()
                    utils.log(f"Error storing batch {batch_start}-{batch_end}: {str(e)}", "WARNING")
                    # Fall back to individual inserts for this batch
                    for movie in batch_movies:
                        try:
                            # Prioritize uniqueid.imdb over imdbnumber for v19 compatibility
                            imdb_id = ''
                            if 'uniqueid' in movie and isinstance(movie.get('uniqueid'), dict):
                                imdb_id = movie.get('uniqueid', {}).get('imdb', '')

                            # Fallback to imdbnumber only if it looks like an IMDb ID
                            if not imdb_id:
                                fallback_id = movie.get('imdbnumber', '')
                                if fallback_id and str(fallback_id).strip().startswith('tt'):
                                    imdb_id = str(fallback_id).strip()

                            if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
                                movie['imdbnumber'] = imdb_id
                                valid_movies.append(movie)

                                # Create movie_data for individual insert
                                movie_data = {
                                    'kodi_id': movie.get('movieid', 0),
                                    'title': movie.get('title', ''),
                                    'year': movie.get('year', 0),
                                    'imdbnumber': imdb_id,
                                    'source': 'lib',
                                    'play': movie.get('file', ''),
                                    'poster': movie.get('art', {}).get('poster', '') if movie.get('art') else '',
                                    'fanart': movie.get('art', {}).get('fanart', '') if movie.get('art') else '',
                                    'plot': movie.get('plot', ''),
                                    'rating': float(movie.get('rating', 0)),
                                    'votes': int(movie.get('votes', 0)),
                                    'duration': int(movie.get('runtime', 0)),
                                    'mpaa': movie.get('mpaa', ''),
                                    'genre': ','.join(movie.get('genre', [])) if isinstance(movie.get('genre'), list) else movie.get('genre', ''),
                                    'director': ','.join(movie.get('director', [])) if isinstance(movie.get('director'), list) else movie.get('director', ''),
                                    'studio': ','.join(movie.get('studio', [])) if isinstance(movie.get('studio'), list) else movie.get('studio', ''),
                                    'country': ','.join(movie.get('country', [])) if isinstance(movie.get('country'), list) else movie.get('country', ''),
                                    'writer': ','.join(movie.get('writer', [])) if isinstance(movie.get('writer'), list) else movie.get('writer', ''),
                                    'cast': json.dumps(movie.get('cast', [])),
                                    'art': json.dumps(movie.get('art', {}))
                                }

                                # Individual insert as fallback
                                db_manager.insert_data('media_items', movie_data)
                                stored_count += 1
                        except Exception as inner_e:
                            utils.log(f"Error storing individual movie {movie.get('title', 'Unknown')}: {str(inner_e)}", "WARNING")
                            continue


            if progress_dialog:
                progress_dialog.update(100, f"Found and stored {stored_count} movies with valid IMDb IDs")

            # Also populate imdb_exports table for search history lookup
            if valid_movies:
                try:
                    db_manager.insert_imdb_export(valid_movies)
                    utils.log(f"Populated imdb_exports table with {len(valid_movies)} entries", "INFO")
                except Exception as e:
                    utils.log(f"Error populating imdb_exports table: {str(e)}", "WARNING")

            utils.log(f"Found and stored {stored_count} movies with valid IMDb IDs", "INFO")
            return valid_movies

        except Exception as e:
            utils.log(f"Error getting Kodi movie collection and storing locally: {str(e)}", "ERROR")
            return []


    def upload_library_full_sync(self):
        """Upload entire Kodi library (authoritative replacement)"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        # Show progress during movie collection
        collection_progress = xbmcgui.DialogProgress()
        collection_progress.create("Preparing Upload", "Gathering movies from Kodi library...")

        try:
            # Get full movie data and store locally in single efficient step
            full_movies = self.get_full_kodi_movie_collection_and_store_locally(collection_progress)
            collection_progress.close()

            if not full_movies:
                xbmcgui.Dialog().ok("Error", "No movies with valid IMDb IDs found in Kodi library")
                return False

            # Extract just IMDB IDs for remote upload
            movies = [{'imdb_id': movie.get('imdbnumber')} for movie in full_movies
                     if movie.get('imdbnumber')]

        except Exception as e:
            collection_progress.close()
            xbmcgui.Dialog().ok("Error", f"Failed to gather movie collection: {str(e)}")
            return False

        # Show confirmation dialog
        if not xbmcgui.Dialog().yesno(
            "Full Library Sync",
            f"This will upload {len(movies)} movies to the server and replace your existing collection.\n\nContinue?"
        ):
            return False

        progress = xbmcgui.DialogProgress()
        progress.create("Uploading Library", "Starting full library sync...")

        try:
            # Create progress callback function
            def progress_callback(current_chunk, total_chunks, chunk_size, current_item=None):
                if progress.iscanceled():
                    return False  # Signal to cancel the upload

                percent = int((current_chunk / total_chunks) * 100)
                message = f"Uploading chunk {current_chunk} of {total_chunks} ({chunk_size} movies)"
                if current_item:
                    message += f"\nProcessing: {current_item}"

                utils.log(f"Progress update: {percent}% - {message}", "DEBUG")
                progress.update(percent, message)
                return True  # Continue uploading

            result = self.remote_client._chunked_movie_upload(movies, mode='replace', progress_callback=progress_callback)

            progress.close()

            if result.get('success'):
                # Try multiple ways to get the uploaded count
                uploaded_count = (
                    result.get('user_movie_count') or
                    result.get('final_tallies', {}).get('total_movies') or
                    result.get('final_tallies', {}).get('successful_imports') or
                    len(movies)
                )
                message = f"Successfully uploaded {uploaded_count} movies"
                utils.log(f"Upload result: {result}", "DEBUG")
                xbmcgui.Dialog().ok("Upload Complete", message)
                return True
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                xbmcgui.Dialog().ok("Upload Failed", f"Upload failed: {error_msg}")
                return False

        except Exception as e:
            progress.close()
            utils.log(f"Error during library upload: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Upload failed: {str(e)}")
            return False

    def upload_library_delta_sync(self):
        """Upload only new movies to server (delta sync)"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        # Show progress during movie collection
        collection_progress = xbmcgui.DialogProgress()
        collection_progress.create("Preparing Sync", "Gathering movies from Kodi library...")

        try:
            # Get full movie data and store locally in single efficient step
            full_movies = self.get_full_kodi_movie_collection_and_store_locally(collection_progress)
            collection_progress.close()

            if not full_movies:
                xbmcgui.Dialog().ok("Error", "No movies with valid IMDb IDs found in Kodi library")
                return False

            # Extract just IMDB IDs for remote upload
            movies = [{'imdb_id': movie.get('imdbnumber')} for movie in full_movies
                     if movie.get('imdbnumber')]

        except Exception as e:
            collection_progress.close()
            xbmcgui.Dialog().ok("Error", f"Failed to gather movie collection: {str(e)}")
            return False

        progress = xbmcgui.DialogProgress()
        progress.create("Syncing Library", "Checking for new movies...")

        try:
            # Create progress callback function
            def progress_callback(current_chunk, total_chunks, chunk_size, current_item=None):
                if progress.iscanceled():
                    return False  # Signal to cancel the upload

                percent = int((current_chunk / total_chunks) * 100)
                message = f"Syncing chunk {current_chunk} of {total_chunks} ({chunk_size} movies)"
                if current_item:
                    message += f"\nProcessing: {current_item}"

                utils.log(f"Progress update: {percent}% - {message}", "DEBUG")
                progress.update(percent, message)
                return True  # Continue syncing

            result = self.remote_client._chunked_movie_upload(movies, mode='merge', progress_callback=progress_callback)

            progress.close()

            if result.get('success'):
                if result.get('message') == 'Collection already up to date':
                    xbmcgui.Dialog().ok("Sync Complete", "Your collection is already up to date")
                else:
                    # Try multiple ways to get the synced count
                    synced_count = (
                        result.get('user_movie_count') or
                        result.get('final_tallies', {}).get('total_movies') or
                        result.get('final_tallies', {}).get('successful_imports') or
                        0
                    )
                    message = f"Successfully synced {synced_count} movies"
                    utils.log(f"Sync result: {result}", "DEBUG")
                    xbmcgui.Dialog().ok("Sync Complete", message)
                return True
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                xbmcgui.Dialog().ok("Sync Failed", f"Sync failed: {error_msg}")
                return False

        except Exception as e:
            progress.close()
            utils.log(f"Error during library sync: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Sync failed: {str(e)}")
            return False

    def get_upload_status(self):
        """Show current upload/sync status and history"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return

        try:
            # Get current movie count
            movie_list = self.remote_client.get_movie_list(per_page=1)
            if movie_list and movie_list.get('success'):
                total_movies = movie_list.get('user_movie_count', 0)

                # Get batch history
                batches = self.remote_client.get_batch_history()

                status_text = f"Current movies on server: {total_movies}\n\n"

                if batches:
                    status_text += "Recent uploads:\n"
                    for batch in batches[:3]:  # Show last 3 batches
                        status_text += f"• {batch.get('started_at', 'Unknown')}: {batch.get('successful_imports', 0)} movies ({batch.get('batch_type', 'unknown')})\n"
                else:
                    status_text += "No upload history found"

                xbmcgui.Dialog().ok("Upload Status", status_text)
            else:
                xbmcgui.Dialog().ok("Error", "Failed to get upload status")

        except Exception as e:
            utils.log(f"Error getting upload status: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Failed to get status: {str(e)}")

    def clear_server_library(self):
        """Clear all movies from server"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        # Double confirmation for destructive action
        if not xbmcgui.Dialog().yesno(
            "Clear Server Library",
            "This will permanently delete ALL movies from your server collection.\n\nAre you absolutely sure?"
        ):
            return False

        if not xbmcgui.Dialog().yesno(
            "Final Confirmation",
            "This action cannot be undone!\n\nProceed with clearing your entire movie collection?"
        ):
            return False

        try:
            result = self.remote_client.clear_movie_list()

            if result and result.get('success'):
                deleted_count = result.get('deleted_count', 0)
                xbmcgui.Dialog().ok("Library Cleared", f"Successfully deleted {deleted_count} movies from server")
                return True
            else:
                xbmcgui.Dialog().ok("Error", "Failed to clear library")
                return False

        except Exception as e:
            utils.log(f"Error clearing server library: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Failed to clear library: {str(e)}")
            return False