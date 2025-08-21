

import xbmcgui
import json
from resources.lib.utils import utils
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC
from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
from resources.lib.config.config_manager import Config
from resources.lib.data.query_manager import QueryManager
import time

class IMDbUploadManager:
    def __init__(self):
        self.config = Config()
        self.remote_client = RemoteAPIClient()
        self.jsonrpc = JSONRPC()
        self.query_manager = QueryManager(self.config.db_path)

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

            # Use the internal method to retrieve movies
            movies = self._retrieve_all_movies_from_kodi(use_notifications=False)

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

                # Prioritized IMDb ID extraction based on version compatibility
                imdb_id = ''

                # Method 1: uniqueid.imdb (most reliable for both v19 and v20+)
                if 'uniqueid' in movie and isinstance(movie.get('uniqueid'), dict):
                    uniqueid_imdb = movie.get('uniqueid', {}).get('imdb', '')
                    if uniqueid_imdb and str(uniqueid_imdb).startswith('tt'):
                        imdb_id = str(uniqueid_imdb).strip()

                # Method 2: imdbnumber fallback (only for v20+ or when it contains valid tt format)
                if not imdb_id:
                    fallback_id = movie.get('imdbnumber', '')
                    if fallback_id:
                        fallback_str = str(fallback_id).strip()
                        # Only accept if it's a proper IMDb ID format (starts with tt)
                        if fallback_str.startswith('tt') and len(fallback_str) > 2:
                            imdb_id = fallback_str

                # Clean IMDb ID if found
                if imdb_id:
                    # Remove URL prefixes if present
                    if imdb_id.startswith('imdb://'):
                        imdb_id = imdb_id[7:]
                    elif 'imdb.com' in imdb_id:
                        import re
                        match = re.search(r'tt\d+', imdb_id)
                        imdb_id = match.group(0) if match else ''

                # Validate and store
                if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
                    movie['imdbnumber'] = imdb_id
                    valid_movies.append(movie)

                    # Log only for first movie to avoid spam
                    if len(valid_movies) == 1:
                        utils.log(f"IMDb extraction method working - first valid ID: '{imdb_id}' for '{movie.get('title', 'Unknown')}'", "INFO")

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


    def get_full_kodi_movie_collection_and_store_locally(self, use_notifications=False):
        """Get complete Kodi movie collection with all metadata and store locally for caching"""
        try:
            utils.log("=== STARTING FULL KODI MOVIE COLLECTION AND LOCAL STORAGE ===", "INFO")

            # Get movie data using JSONRPC manager
            full_movies = self._retrieve_all_movies_from_kodi(use_notifications)

            if not full_movies:
                utils.log("No movies found in Kodi library", "WARNING")
                return []

            utils.log(f"Retrieved {len(full_movies)} movies from Kodi", "INFO")

            if use_notifications:
                from resources.lib.utils import utils as notification_utils
                notification_utils.show_notification("LibraryGenie", f"Processing {len(full_movies)} movies...", time=3000)

            # Log sample movie data
            if full_movies:
                utils.log("=== SAMPLE MOVIE DATA ===", "INFO")
                sample_movie = full_movies[0]
                for key, value in sample_movie.items():
                    if isinstance(value, str) and len(value) > 200:
                        utils.log(f"MOVIE_DATA: {key} = {value[:200]}... (truncated)", "INFO")
                    else:
                        utils.log(f"MOVIE_DATA: {key} = {repr(value)}", "INFO")
                utils.log("=== END SAMPLE MOVIE DATA ===", "INFO")

            # Store basic data in imdb_exports table (only light fields for search)
            export_movies = []
            heavy_metadata_list = []

            for movie in full_movies:
                imdb_id = movie.get('imdbnumber', '')
                if imdb_id and imdb_id.startswith('tt'):
                    # Only store basic search data in imdb_exports
                    export_movie = {
                        'imdb_id': imdb_id,
                        'title': movie.get('title', ''),
                        'year': movie.get('year', 0)
                    }
                    export_movies.append(export_movie)

                    # Prepare heavy metadata for separate storage
                    movieid = movie.get('movieid')
                    if movieid:
                        heavy_metadata_list.append(movie)

            if export_movies:
                utils.log(f"Storing {len(export_movies)} movies in imdb_exports table (light fields only)", "INFO")

                # Log sample export data before storage
                if export_movies:
                    utils.log("=== SAMPLE EXPORT DATA FOR IMDB_EXPORTS TABLE ===", "INFO")
                    sample_export = export_movies[0]
                    for key, value in sample_export.items():
                        utils.log(f"EXPORT_DATA: {key} = {repr(value)}", "INFO")
                    utils.log("=== END SAMPLE EXPORT DATA ===", "INFO")

                # Use QueryManager to store data
                self.query_manager.insert_imdb_export(export_movies)

                # Store heavy metadata separately in movie_heavy_meta table
                if heavy_metadata_list:
                    utils.log(f"Storing heavy metadata for {len(heavy_metadata_list)} movies", "INFO")
                    self.query_manager.store_heavy_meta_batch(heavy_metadata_list)

                # Verify what was actually stored
                utils.log("=== VERIFYING STORED DATA IN IMDB_EXPORTS ===", "INFO")
                sample_imdb = export_movies[0]['imdb_id']
                stored_data = self.query_manager.execute_query(
                    "SELECT * FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1",
                    (sample_imdb,), fetch_one=True
                )
                if stored_data:
                    utils.log("=== STORED DATA VERIFICATION ===", "INFO")
                    for key, value in stored_data.items():
                        utils.log(f"STORED: {key} = {repr(value)}", "INFO")
                    utils.log("=== END STORED DATA VERIFICATION ===", "INFO")

            utils.log(f"Successfully processed {len(full_movies)} movies with complete metadata", "INFO")
            return full_movies

        except Exception as e:
            utils.log(f"Error getting full Kodi movie collection: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return []

    def _clear_existing_library_data(self):
        """Clear existing library data from database tables atomically."""
        try:
            utils.log("Starting atomic clear of existing library data", "INFO")

            # Get existing count for logging with explicit alias
            count_result = self.query_manager.execute_query(
                "SELECT COUNT(*) as lib_count FROM media_items WHERE source = 'lib'",
                fetch_one=True
            )
            existing_count = count_result['lib_count'] if count_result else 0

            if existing_count > 0:
                utils.log(f"Found {existing_count} existing library items to clear", "INFO")

            # Clear all library data in a single transaction using public transaction context
            with self.query_manager.transaction():
                # Clear media_items table
                self.query_manager.execute_write("DELETE FROM media_items WHERE source = 'lib'")
                
                # Clear heavy metadata table
                self.query_manager.execute_write("DELETE FROM movie_heavy_meta")
                
                # Clear imdb_exports table
                self.query_manager.execute_write("DELETE FROM imdb_exports")

            utils.log(f"Successfully cleared {existing_count} library items and all related data", "INFO")

        except Exception as e:
            utils.log(f"Warning: Could not clear existing library data: {str(e)}", "WARNING")
            utils.log("Continuing with upload process despite clearing failure", "INFO")

    def _retrieve_all_movies_from_kodi(self, use_notifications):
        """Retrieve all movies from Kodi library using JSON-RPC."""
        utils.log("Getting all movies with IMDb information from Kodi library", "INFO")

        batch_size = 100
        start = 0
        all_movies = []
        last_notification = 0
        total = 0

        while True:
            # Execute JSON-RPC call
            params = {
                "properties": ["title", "year", "file", "imdbnumber", "uniqueid", "cast", "ratings", "showlink", "streamdetails", "tag"],
                "limits": {"start": start, "end": start + batch_size}
            }

            response = self.jsonrpc.execute("VideoLibrary.GetMovies", params)

            if 'result' not in response or 'movies' not in response['result']:
                break

            movies = response['result']['movies']
            total = response['result']['limits']['total']

            # Update progress tracking (less frequent logging)
            current_count = len(all_movies) + len(movies)
            if use_notifications and (current_count - last_notification >= 2000):
                utils.show_notification("LibraryGenie", f"Scanned {current_count} of {total} movies...", time=2000)
                last_notification = current_count

            all_movies.extend(movies)

            # Check if we're done
            if len(movies) < batch_size or start + batch_size >= total:
                break

            start += batch_size

        utils.log(f"Movie retrieval complete: {len(all_movies)} movies retrieved from Kodi library", "INFO")

        if use_notifications:
            utils.show_notification("LibraryGenie", f"Scan complete! Processing {len(all_movies)} movies...", time=3000)

        return all_movies

    def _process_and_store_movies(self, all_movies, use_notifications):
        """Process movies and store them in database with batching."""
        utils.log("Starting movie processing and storage phase", "INFO")

        batch_size = 100
        valid_movies = []
        stored_count = 0
        last_notification_stored = 0
        total_batches = (len(all_movies) + batch_size - 1) // batch_size

        for batch_start in range(0, len(all_movies), batch_size):
            batch_end = min(batch_start + batch_size, len(all_movies))
            batch_movies = all_movies[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1

            # Process this batch
            batch_valid_movies, batch_stored_count = self._process_movie_batch(
                batch_movies, batch_num
            )

            valid_movies.extend(batch_valid_movies)
            stored_count += batch_stored_count

            # Show progress notifications (less frequent)
            if use_notifications and (stored_count - last_notification_stored >= 2000):
                utils.show_notification("LibraryGenie", f"Processed {stored_count} movies with IMDb IDs...", time=2000)
                last_notification_stored = stored_count

        # Summary logging
        utils.log(f"=== MOVIE PROCESSING SUMMARY ===", "INFO")
        utils.log(f"Total movies processed: {len(all_movies)}", "INFO")
        utils.log(f"Movies with valid IMDb IDs: {len(valid_movies)}", "INFO")
        utils.log(f"Movies stored in database: {stored_count}", "INFO")
        utils.log(f"Batches processed: {total_batches}", "INFO")
        utils.log(f"=== PROCESSING COMPLETE ===", "INFO")

        return valid_movies, stored_count

    def _process_movie_batch(self, batch_movies, batch_num):
        """Process a single batch of movies with transaction management."""        
        batch_valid_movies = []
        batch_stored_count = 0

        try:
            # Use public transaction context manager
            with self.query_manager.transaction():
                batch_data = []
                heavy_metadata_list = []

                for movie in batch_movies:
                    # Extract and validate IMDb ID
                    imdb_id = self._extract_imdb_id(movie)

                    if imdb_id:
                        movie['imdbnumber'] = imdb_id
                        batch_valid_movies.append(movie)

                        # Prepare movie data for database
                        movie_data = self._prepare_movie_data(movie, imdb_id)
                        batch_data.append(movie_data)

                        # Prepare heavy metadata
                        movieid = movie.get('movieid')
                        if movieid:
                            heavy_metadata_list.append(movie)

                # Bulk insert batch data using public executemany_write
                if batch_data:
                    batch_stored_count = self._bulk_insert_movies(batch_data)

                # Store heavy metadata in same transaction using public methods
                if heavy_metadata_list:
                    self._store_heavy_metadata_batch(heavy_metadata_list)

        except Exception as e:
            utils.log(f"Batch {batch_num} error: {str(e)}", "ERROR")

        return batch_valid_movies, batch_stored_count

    def _extract_imdb_id(self, movie):
        """Extract IMDb ID from movie data with v19/v20+ compatibility."""
        imdb_id = ''

        # Method 1: uniqueid.imdb (preferred for v19 compatibility)
        if 'uniqueid' in movie and isinstance(movie.get('uniqueid'), dict):
            imdb_id = movie.get('uniqueid', {}).get('imdb', '')

        # Method 2: imdbnumber fallback (only if it looks like an IMDb ID)
        if not imdb_id:
            fallback_id = movie.get('imdbnumber', '')
            if fallback_id and str(fallback_id).strip().startswith('tt'):
                imdb_id = str(fallback_id).strip()

        # Validate IMDb ID format
        if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
            return imdb_id

        return None

    def _prepare_movie_data(self, movie, imdb_id):
        """Prepare movie data dictionary for database insertion."""
        return {
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

    def _store_heavy_metadata_batch(self, heavy_metadata_list):
        """Store heavy metadata for multiple movies in batch using QueryManager."""
        if not heavy_metadata_list:
            return

        utils.log(f"Storing heavy metadata for {len(heavy_metadata_list)} movies in transaction", "DEBUG")
        
        # Use QueryManager's store_heavy_meta_batch method
        self.query_manager.store_heavy_meta_batch(heavy_metadata_list)

    def _bulk_insert_movies(self, batch_data):
        """Bulk insert movie data into database using QueryManager."""
        if not batch_data:
            return 0

        utils.log(f"Inserting {len(batch_data)} valid movies into database", "DEBUG")
        columns = ', '.join(batch_data[0].keys())
        placeholders = ', '.join(['?' for _ in batch_data[0]])
        query = f'INSERT OR IGNORE INTO media_items ({columns}) VALUES ({placeholders})'

        values_list = [tuple(movie_data.values()) for movie_data in batch_data]
        self.query_manager.executemany_write(query, values_list)

        return len(batch_data)

    def _populate_imdb_exports(self, valid_movies):
        """Populate imdb_exports table for search functionality."""
        if valid_movies:
            try:
                utils.log("Populating imdb_exports table for search functionality", "INFO")
                self.query_manager.insert_imdb_export(valid_movies)
                utils.log(f"Populated imdb_exports table with {len(valid_movies)} entries", "INFO")
            except Exception as e:
                utils.log(f"Error populating imdb_exports table: {str(e)}", "WARNING")

    def upload_library_full_sync(self):
        """Upload entire Kodi library (authoritative replacement)"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        # Show progress during movie collection
        collection_progress = xbmcgui.DialogProgress()
        collection_progress.create("Preparing Upload", "Gathering movies from Kodi library...")

        try:
            # Get full movie data and store locally in single efficient step, using notifications
            full_movies = self.get_full_kodi_movie_collection_and_store_locally(use_notifications=True)
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

        # Show confirmation dialog before upload
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

                # Only log every 4th chunk to reduce spam
                if current_chunk % 4 == 0 or current_chunk == 1 or current_chunk == total_chunks:
                    utils.log(f"Upload progress: {percent}% - Chunk {current_chunk}/{total_chunks}", "INFO")

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
            # Get full movie data and store locally in single efficient step, using notifications
            full_movies = self.get_full_kodi_movie_collection_and_store_locally(use_notifications=True)
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

                # Only log every 4th chunk to reduce spam
                if current_chunk % 4 == 0 or current_chunk == 1 or current_chunk == total_chunks:
                    utils.log(f"Sync progress: {percent}% - Chunk {current_chunk}/{total_chunks}", "INFO")

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

