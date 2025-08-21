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
        """Get all movies from Kodi and store locally with optional progress notifications"""
        try:
            utils.log("Starting full Kodi movie collection retrieval", "INFO")

            if use_notifications:
                utils.show_notification("LibraryGenie", "Starting library scan...", time=3000)

            # Get total count first
            count_response = self.jsonrpc.execute("VideoLibrary.GetMovies", {
                "limits": {"start": 0, "end": 1},
                "properties": ["title"]
            })

            if not count_response or 'result' not in count_response:
                utils.log("Failed to get movie count", "ERROR")
                return False

            total_movies = count_response['result']['limits']['total']
            utils.log(f"Total movies to process: {total_movies}", "INFO")

            if use_notifications:
                utils.show_notification("LibraryGenie", f"Found {total_movies} movies to scan", time=3000)

            # Process in batches
            batch_size = 100
            all_movies = []
            start = 0
            batch_num = 0
            total_batches = (total_movies + batch_size - 1) // batch_size

            while start < total_movies:
                batch_num += 1

                # Show progress notifications every 20% or for small libraries every few batches
                show_progress = False
                progress_percent = int((batch_num / total_batches) * 100)

                if total_batches <= 5:
                    # Small library - show every batch
                    show_progress = True
                elif progress_percent % 20 == 0 and batch_num > 1:
                    # Large library - show every 20%
                    show_progress = True
                elif batch_num == 1:
                    # Always show first batch
                    show_progress = True

                if use_notifications and show_progress:
                    utils.show_notification("LibraryGenie", f"Scanning library: {progress_percent}%", time=2000)

                response = self.jsonrpc.execute("VideoLibrary.GetMovies", {
                    "limits": {"start": start, "end": start + batch_size},
                    "properties": [
                        "title", "year", "plot", "rating", "runtime", "genre", "director",
                        "cast", "studio", "mpaa", "tagline", "writer", "country", "premiered",
                        "dateadded", "votes", "trailer", "file", "art", "imdbnumber", "uniqueid"
                    ]
                })

                if not response or 'result' not in response or 'movies' not in response['result']:
                    utils.log(f"No movies returned in batch {batch_num}", "WARNING")
                    break

                batch_movies = response['result']['movies']
                all_movies.extend(batch_movies)

                # Reduced logging - only log every 10th batch to reduce spam
                if batch_num % 10 == 0 or batch_num == 1 or batch_num == total_batches:
                    utils.log(f"Scan progress: {progress_percent}% - Batch {batch_num}/{total_batches} ({len(batch_movies)} movies)", "INFO")

                start += batch_size

            utils.log(f"Movie retrieval complete: {len(all_movies)} movies retrieved from Kodi library", "INFO")

            if use_notifications:
                utils.show_notification("LibraryGenie", f"Processing {len(all_movies)} movies...", time=2000)

            # Store in database
            self._store_movies_in_database(all_movies, use_notifications)

            # Simple completion notification since modal will show detailed status
            if use_notifications:
                utils.show_notification("LibraryGenie", "Scan complete!", time=2000)

            return True

        except Exception as e:
            utils.log(f"Error retrieving Kodi movie collection: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")

            if use_notifications:
                utils.show_notification("LibraryGenie", "Library scan failed", time=5000)

            return False

    def _store_movies_in_database(self, movies, use_notifications=False):
        """Store movies in database with progress tracking"""
        try:
            utils.log(f"Starting to store {len(movies)} movies in database", "INFO")

            # Clear existing data using execute_write (for DELETE operations)
            self.query_manager.execute_write("DELETE FROM imdb_exports")
            self.query_manager.execute_write("DELETE FROM media_items WHERE source = 'lib'")

            utils.log("Cleared existing library data from database", "INFO")

            # Process movies in batches for better performance
            batch_size = 50
            total_movies = len(movies)
            processed = 0
            total_batches = (total_movies + batch_size - 1) // batch_size

            for i in range(0, total_movies, batch_size):
                batch = movies[i:i + batch_size]
                batch_num = i // batch_size + 1

                # Process batch within transaction
                with self.query_manager.transaction():
                    for movie in batch:
                        self._process_single_movie(movie)
                        processed += 1

                # Show progress notifications every 25% or for small collections more frequently
                show_progress = False
                progress_percent = int((processed / total_movies) * 100)

                if total_batches <= 4:
                    # Small collection - show every batch
                    show_progress = True
                elif progress_percent % 25 == 0 and processed > 0:
                    # Large collection - show every 25%
                    show_progress = True
                elif processed == total_movies:
                    # Always show completion
                    show_progress = True

                if use_notifications and show_progress:
                    utils.show_notification("LibraryGenie", f"Processing: {progress_percent}%", time=1500)

                # Reduced logging - only log every 5th batch to reduce spam
                if batch_num % 5 == 0 or batch_num == 1 or batch_num == total_batches:
                    utils.log(f"Database progress: {progress_percent}% - Batch {batch_num}/{total_batches} ({processed}/{total_movies} movies)", "INFO")

            utils.log(f"Successfully stored {processed} movies in database", "INFO")

        except Exception as e:
            utils.log(f"Error storing movies in database: {str(e)}", "ERROR")
            raise

    def _process_single_movie(self, movie):
        """Process a single movie and store it in the database"""
        try:
            # Extract and validate IMDb ID
            imdb_id = self._extract_imdb_id(movie)

            if imdb_id:
                movie['imdbnumber'] = imdb_id

                # Prepare movie data for database
                movie_data = self._prepare_movie_data(movie, imdb_id)

                # Insert movie data
                media_item_id = self.query_manager.insert_media_item(movie_data)

                # Store heavy metadata if we have a movie ID
                movieid = movie.get('movieid')
                if movieid and media_item_id:
                    self.query_manager.store_heavy_meta_batch([movie])

                # Store in imdb_exports table
                export_data = {
                    'kodi_id': movie.get('movieid', 0),
                    'title': movie.get('title', ''),
                    'year': movie.get('year', 0),
                    'imdb_id': imdb_id
                }
                self.query_manager.execute_write(
                    "INSERT OR REPLACE INTO imdb_exports (kodi_id, title, year, imdb_id) VALUES (?, ?, ?, ?)",
                    (export_data['kodi_id'], export_data['title'], export_data['year'], export_data['imdb_id'])
                )

        except Exception as e:
            utils.log(f"Error processing movie {movie.get('title', 'Unknown')}: {str(e)}", "WARNING")

    def _clear_existing_library_data(self):
        """Clear existing library data from database tables atomically."""
        try:
            utils.log("Starting atomic clear of existing library data", "INFO")

            # Get existing count for logging - simplified approach
            existing_count = self._get_library_item_count()
            if existing_count > 0:
                utils.log(f"Found {existing_count} existing library items to clear", "INFO")
            else:
                utils.log("No existing library items found", "INFO")

            # Clear all library data in a single atomic transaction
            self._execute_library_data_clear()

            utils.log(f"Successfully cleared {existing_count} library items and all related data", "INFO")

        except Exception as e:
            utils.log(f"Error clearing existing library data: {str(e)}", "ERROR")
            # Re-raise the exception since this is a critical operation
            # The caller should decide whether to continue or abort
            raise

    def _get_library_item_count(self):
        """Get count of existing library items with robust error handling."""
        try:
            count_result = self.query_manager.execute_query(
                "SELECT COUNT(*) as lib_count FROM media_items WHERE source = 'lib'",
                fetch_one=True
            )

            if not count_result:
                return 0

            # Handle different possible return formats from execute_query
            if isinstance(count_result, dict):
                return int(count_result.get('lib_count', 0))
            elif isinstance(count_result, (list, tuple)) and len(count_result) > 0:
                first_item = count_result[0]
                if isinstance(first_item, dict):
                    return int(first_item.get('lib_count', 0))
                else:
                    # Direct numeric value
                    return int(first_item)
            else:
                # If we get here, count_result is not in expected format
                utils.log(f"Unexpected count_result format: {type(count_result)} - {count_result}", "WARNING")
                return 0

        except (ValueError, TypeError, KeyError) as e:
            utils.log(f"Error getting library item count: {str(e)}", "WARNING")
            return 0

    def _execute_library_data_clear(self):
        """Execute the actual clearing of library data in a transaction."""
        with self.query_manager.transaction():
            # Clear in dependency order to avoid foreign key conflicts
            clear_operations = [
                ("media_items WHERE source = 'lib'", "library media items"),
                ("movie_heavy_meta", "heavy metadata"),
                ("imdb_exports", "IMDb exports")
            ]

            for table_condition, description in clear_operations:
                try:
                    affected_rows = self.query_manager.execute_write(f"DELETE FROM {table_condition}")
                    utils.log(f"Cleared {description}: {affected_rows} rows affected", "DEBUG")
                except Exception as e:
                    utils.log(f"Error clearing {description}: {str(e)}", "ERROR")
                    raise  # Re-raise to trigger transaction rollback

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

            # Log detailed response data for first batch only
            if start == 0:
                utils.log("=== JSON-RPC RESPONSE ANALYSIS (FIRST BATCH ONLY) ===", "INFO")
                utils.log(f"Response keys: {list(response.keys())}", "INFO")

                if 'result' in response:
                    result = response['result']
                    utils.log(f"Result keys: {list(result.keys())}", "INFO")

                    if 'movies' in result:
                        movies = result['movies']
                        utils.log(f"Number of movies in first batch: {len(movies)}", "INFO")

                        # Log first 3 movies in detail
                        for i, movie in enumerate(movies[:3]):
                            utils.log(f"=== MOVIE {i+1} DETAILED DATA ===", "INFO")
                            for key, value in movie.items():
                                if isinstance(value, str) and len(value) > 200:
                                    utils.log(f"MOVIE_{i+1}: {key} = {value[:200]}... (truncated)", "INFO")
                                else:
                                    utils.log(f"MOVIE_{i+1}: {key} = {repr(value)}", "INFO")
                            utils.log(f"=== END MOVIE {i+1} DATA ===", "INFO")
                    else:
                        utils.log("No 'movies' key found in result", "ERROR")
                else:
                    utils.log("No 'result' key found in response", "ERROR")
                    if 'error' in response:
                        utils.log(f"Error in response: {response['error']}", "ERROR")

                utils.log("=== END JSON-RPC RESPONSE ANALYSIS ===", "INFO")

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
        """Prepare movie data for database insertion"""
        try:
            # Basic movie data preparation
            movie_data = {
                'kodi_id': movie.get('movieid', 0),
                'title': movie.get('title', ''),
                'year': movie.get('year', 0),
                'source': 'lib',
                'media_type': 'movie',
                'imdbnumber': imdb_id
            }

            # Add other available fields with proper type conversion
            for field in ['plot', 'genre', 'director', 'rating', 'duration', 'premiered', 'votes']:
                if field in movie:
                    value = movie[field]

                    # Convert lists to comma-separated strings for database storage
                    if isinstance(value, list):
                        if field in ['genre', 'director']:
                            # Join list items with comma separator
                            movie_data[field] = ', '.join(str(item) for item in value if item)
                        else:
                            # For other list fields, take first item or convert to string
                            movie_data[field] = str(value[0]) if value else ''
                    else:
                        movie_data[field] = value

            return movie_data

        except Exception as e:
            utils.log(f"Error preparing movie data: {str(e)}", "ERROR")
            return {}

    def _store_heavy_metadata_batch(self, heavy_metadata_list):
        """Store heavy metadata for multiple movies in batch using QueryManager."""
        if not heavy_metadata_list:
            return

        # Only log for first few batches and summary to reduce spam
        if len(heavy_metadata_list) <= 5:
            utils.log(f"=== STORING HEAVY METADATA BATCH: {len(heavy_metadata_list)} movies ===", "INFO")
        elif len(heavy_metadata_list) % 1000 == 0:
            utils.log(f"=== STORING HEAVY METADATA BATCH: {len(heavy_metadata_list)} movies ===", "INFO")

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
            # Check if library data already exists from service scan
            existing_count = self._get_library_item_count()

            if existing_count > 0:
                # Use existing data
                utils.log(f"Using existing library data ({existing_count} items)", "INFO")
                collection_progress.update(90, "Using existing library data...")

                # Get IMDb IDs from existing data
                imdb_results = self.query_manager.execute_query(
                    "SELECT imdb_id FROM imdb_exports WHERE imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%'",
                    fetch_all=True
                )
                movies = [{'imdb_id': result['imdb_id']} for result in imdb_results]
                collection_progress.close()

            else:
                # Need to scan library first
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

        # Show start notification
        utils.show_notification("LibraryGenie", f"Starting upload of {len(movies)} movies...", time=5000)

        try:
            # Create progress callback function with frequent percentage updates
            def progress_callback(current_chunk, total_chunks, chunk_size, current_item=None):
                percent = int((current_chunk / total_chunks) * 100)

                # Show progress notifications every 10% or at key points
                show_notification = False
                notification_message = ""

                if current_chunk == 1:
                    show_notification = True
                    notification_message = f"Upload starting... 0%"
                elif current_chunk == total_chunks:
                    show_notification = True
                    notification_message = f"Upload finalizing... 100%"
                elif percent % 10 == 0 and current_chunk > 1:
                    # Show every 10% increment
                    show_notification = True
                    notification_message = f"Upload progress: {percent}%"
                elif total_chunks <= 10:
                    # For small uploads, show every chunk
                    show_notification = True
                    notification_message = f"Upload progress: {percent}%"

                if show_notification:
                    utils.show_notification("LibraryGenie", notification_message, time=2000)

                # Log progress more frequently for debugging
                if current_chunk % 2 == 0 or current_chunk == 1 or current_chunk == total_chunks:
                    utils.log(f"Upload progress: {percent}% - Chunk {current_chunk}/{total_chunks} ({chunk_size} movies)", "INFO")

                return True  # Continue uploading

            result = self.remote_client._chunked_movie_upload(movies, mode='replace', progress_callback=progress_callback)

            if result.get('success'):
                # Get detailed upload statistics
                final_tallies = result.get('final_tallies', {})
                accepted = final_tallies.get('accepted', 0)
                duplicates = final_tallies.get('duplicates', 0)
                invalid = final_tallies.get('invalid', 0)
                user_movie_count = result.get('user_movie_count', 0)

                utils.log(f"Upload result: {result}", "DEBUG")
                utils.log(f"Upload statistics - Accepted: {accepted}, Duplicates: {duplicates}, Invalid: {invalid}, Final count: {user_movie_count}", "INFO")

                # For replace mode, focus on final count rather than duplicate detection
                # Replace mode is authoritative so duplicates are expected during replacement
                if user_movie_count > 0:
                    utils.show_notification("LibraryGenie", f"Library replaced! {user_movie_count} movies on server", time=5000)
                elif invalid > 0 and user_movie_count == 0:
                    utils.show_notification("LibraryGenie", f"Upload failed: {invalid} movies had invalid IMDb IDs", time=8000)
                else:
                    utils.show_notification("LibraryGenie", f"Upload completed but no movies were added. Check server logs.", time=8000)

                # Show addon status modal after upload (regardless of result)
                try:
                    from resources.lib.integrations.remote_api.library_status import show_library_status
                    show_library_status()
                except Exception as e:
                    utils.log(f"Error showing addon status after upload: {str(e)}", "ERROR")

                return True
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                utils.show_notification("LibraryGenie", f"Upload failed: {error_msg}", time=8000)
                return False

        except Exception as e:
            utils.log(f"Error during library upload: {str(e)}", "ERROR")
            utils.show_notification("LibraryGenie", f"Upload failed: {str(e)}", time=8000)
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