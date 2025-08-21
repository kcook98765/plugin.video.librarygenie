"""
ListingDAO - Data Access Object for folder and list operations
Extracted from QueryManager to separate concerns while maintaining the same API
"""

import sqlite3
import time
from contextlib import contextmanager
from resources.lib.utils import utils
from resources.lib.data.query_manager import QueryManager
from resources.lib.config.config_manager import Config

class ListingDAO:
    """Data Access Object for folder and list database operations"""

    def __init__(self):
        """
        Initialize DAO with injected query executors

        Args:
            execute_query_callable: Function to execute SELECT queries
                                   Signature: execute_query(sql: str, params: tuple, fetch_all: bool) -> List[Dict]
            execute_write_callable: Function to execute INSERT/UPDATE/DELETE
                                   Signature: execute_write(sql: str, params: tuple) -> Dict[str, int]
        """
        config = Config()
        self.query_manager = QueryManager(config.db_path)

    # =========================
    # FOLDER OPERATIONS
    # =========================

    def get_folders(self, parent_id=None):
        """Get folders by parent ID"""
        return self.query_manager.fetch_folders(parent_id)

    def fetch_folders_direct(self, parent_id=None):
        """Direct folder fetch without transformation"""
        return self.query_manager.fetch_folders(parent_id)

    def insert_folder_direct(self, name, parent_id):
        """Direct folder insertion"""
        return self.query_manager.insert_folder(name, parent_id)

    def update_folder_name_direct(self, folder_id, new_name):
        """Direct folder name update"""
        return self.query_manager.update_folder_name(folder_id, new_name)

    def get_folder_depth(self, folder_id):
        """Calculate folder depth in hierarchy"""
        if folder_id is None:
            return 0

        depth = 0
        current_id = folder_id

        while current_id is not None:
            folder = self.query_manager.fetch_folder_by_id(current_id)
            if not folder:
                break
            current_id = folder['parent_id']
            depth += 1

            # Prevent infinite loops
            if depth > 50:
                break

        return depth

    def get_folder_by_name(self, name, parent_id=None):
        """Get folder by name and parent"""
        return self.query_manager.fetch_folder_by_name(name, parent_id)

    def get_folder_id_by_name(self, name, parent_id=None):
        """Get folder ID by name and parent"""
        folder = self.get_folder_by_name(name, parent_id)
        return folder['id'] if folder else None

    def ensure_search_history_folder(self):
        """Ensure Search History folder exists and return its ID"""
        folder_id = self.get_folder_id_by_name("Search History", None)
        if folder_id:
            return folder_id
        return self.insert_folder_direct("Search History", None)

    def insert_folder(self, name, parent_id):
        """Insert folder (alias for create_folder)"""
        return self.create_folder(name, parent_id)

    def create_folder(self, name, parent_id):
        """Create a new folder"""
        return self.insert_folder_direct(name, parent_id)

    def update_folder_name(self, folder_id, new_name):
        """Update folder name"""
        return self.update_folder_name_direct(folder_id, new_name)

    def get_folder_media_count(self, folder_id):
        """Get total media count for folder (including subfolders and lists)"""
        # Count items in lists directly in this folder
        direct_count = self.query_manager.get_folder_direct_media_count(folder_id)

        # Count items in subfolders recursively
        subfolder_count = 0
        subfolders = self.get_folders(folder_id)
        for subfolder in subfolders:
            subfolder_count += self.get_folder_media_count(subfolder['id'])

        return direct_count + subfolder_count

    def fetch_folder_by_id(self, folder_id):
        """Fetch folder by ID"""
        return self.query_manager.fetch_folder_by_id(folder_id)

    def update_folder_parent(self, folder_id, new_parent_id):
        """Update folder parent"""
        return self.query_manager.update_folder_parent(folder_id, new_parent_id)

    def delete_folder_and_contents(self, folder_id):
        """Delete folder and all its contents recursively

        Note: This method should be called within a transaction managed by QueryManager
        to ensure atomicity of the entire operation.
        """
        # Get all subfolders
        subfolders = self.get_folders(folder_id)

        # Recursively delete subfolders
        for subfolder in subfolders:
            self.delete_folder_and_contents(subfolder['id'])

        # Delete all lists in this folder
        lists_in_folder = self.get_lists(folder_id)
        for list_item in lists_in_folder:
            self.delete_list_and_contents(list_item['id'])

        # Delete the folder itself
        return self.query_manager.delete_folder(folder_id)

    def fetch_folders_with_item_status(self, parent_id, media_item_id):
        """Fetch folders with status for a media item"""
        return self.query_manager.fetch_folders_with_item_status(parent_id, media_item_id)

    def fetch_all_folders(self):
        """Fetch all folders"""
        return self.query_manager.fetch_all_folders()

    # =========================
    # LIST OPERATIONS
    # =========================

    def get_lists(self, folder_id=None):
        """Get lists by folder ID"""
        return self.query_manager.fetch_lists(folder_id)

    def fetch_lists_direct(self, folder_id=None):
        """Direct list fetch without transformation"""
        return self.get_lists(folder_id)

    def get_list_items(self, list_id):
        """Get items in a list"""
        return self.query_manager.fetch_list_items(list_id)

    def fetch_list_items_with_details(self, list_id):
        """Fetch list items with detailed information including search scores"""
        return self.query_manager.fetch_list_items_with_details(list_id)

    def get_list_media_count(self, list_id):
        """Get media count for a list"""
        return self.query_manager.get_list_media_count(list_id)

    def fetch_lists_with_item_status(self, folder_id, media_item_id):
        """Fetch lists with status for a media item"""
        return self.query_manager.fetch_lists_with_item_status(folder_id, media_item_id)

    def fetch_all_lists_with_item_status(self, media_item_id):
        """Fetch all lists with status for a media item"""
        return self.query_manager.fetch_all_lists_with_item_status(media_item_id)

    def update_list_folder(self, list_id, folder_id):
        """Update list's folder"""
        return self.query_manager.update_list_folder(list_id, folder_id)

    def get_list_id_by_name(self, name, folder_id=None):
        """Get list ID by name and folder"""
        return self.query_manager.fetch_list_id_by_name(name, folder_id)

    def get_lists_for_item(self, media_item_id):
        """Get all lists containing a media item"""
        return self.query_manager.fetch_lists_for_item(media_item_id)

    def get_item_id_by_title_and_list(self, title, list_id):
        """Get media item ID by title within a specific list"""
        return self.query_manager.fetch_item_id_by_title_and_list(title, list_id)

    def create_list(self, name, folder_id=None):
        """Create a new list"""
        return self.query_manager.create_list(name, folder_id)

    def get_unique_list_name(self, base_name, folder_id=None):
        """Generate a unique list name in the given folder"""
        return self.query_manager.get_unique_list_name(base_name, folder_id)

    def delete_list_and_contents(self, list_id):
        """Delete list and all its contents"""
        # Delete list items first
        self.query_manager.delete_list_items(list_id)

        # Delete the list itself
        return self.query_manager.delete_list(list_id)

    def fetch_all_lists(self):
        """Fetch all lists"""
        return self.query_manager.fetch_all_lists()

    def fetch_list_by_id(self, list_id):
        """Fetch list by ID"""
        return self.query_manager.fetch_list_by_id(list_id)

    def insert_list_item(self, list_id, media_item_id):
        """Insert item into list"""
        return self.query_manager.insert_list_item(list_id, media_item_id)

    def remove_media_item_from_list(self, list_id, media_item_id):
        """Remove media item from list"""
        return self.query_manager.remove_media_item_from_list(list_id, media_item_id)

    def get_list_item_by_media_id(self, list_id, media_item_id):
        """Get list item by list_id and media_item_id"""
        return self.query_manager.fetch_list_item_by_media_id(list_id, media_item_id)

    def upsert_heavy_meta(self, movieid, imdbnumber, cast_json, ratings_json, showlink_json, stream_json, uniqueid_json, tags_json, connection=None):
        """Upsert heavy metadata for a movie - can use existing connection to avoid locks"""
        import time

        try:
            # Try update first
            update_sql = """
                UPDATE movie_heavy_meta SET
                    imdbnumber = ?,
                    cast_json = ?,
                    ratings_json = ?,
                    showlink_json = ?,
                    stream_json = ?,
                    uniqueid_json = ?,
                    tags_json = ?,
                    updated_at = ?
                WHERE kodi_movieid = ?
            """
            update_params = (imdbnumber, cast_json, ratings_json, showlink_json, 
                            stream_json, uniqueid_json, tags_json, int(time.time()), movieid)

            if connection:
                # Use existing connection directly to avoid lock conflicts
                cursor = connection.cursor()
                cursor.execute(update_sql, update_params)
                rowcount = cursor.rowcount

                if rowcount > 0:
                    return movieid

                # No rows updated, try insert
                insert_sql = """
                    INSERT OR IGNORE INTO movie_heavy_meta
                        (kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json,
                         stream_json, uniqueid_json, tags_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                insert_params = (movieid, imdbnumber, cast_json, ratings_json, showlink_json, 
                               stream_json, uniqueid_json, tags_json, int(time.time()))
                cursor.execute(insert_sql, insert_params)
                return movieid
            else:
                # Fall back to execute_write for backwards compatibility
                result = self.query_manager.execute_write(update_sql, update_params)

                if result['rowcount'] > 0:
                    return movieid

                # No rows updated, try insert
                insert_sql = """
                    INSERT OR IGNORE INTO movie_heavy_meta
                        (kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json,
                         stream_json, uniqueid_json, tags_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                insert_params = (movieid, imdbnumber, cast_json, ratings_json, showlink_json, 
                               stream_json, uniqueid_json, tags_json, int(time.time()))
                result = self.query_manager.execute_write(insert_sql, insert_params)
                return result['lastrowid'] or movieid

        except Exception as e:
            utils.log(f"Error storing heavy metadata for movie ID {movieid}: {str(e)}", "WARNING")
            # Don't re-raise - this is not critical for the upload process
            return movieid

    def get_heavy_meta_by_movieids(self, movieids, refresh=False):
        """Get heavy metadata for multiple movie IDs with caching"""
        if not movieids:
            return {}

        utils.log(f"=== GET_HEAVY_META_BY_MOVIEIDS: Processing {len(movieids)} movie IDs (refresh={refresh}) ===", "INFO")

        # Convert single ID to list
        if isinstance(movieids, (int, str)):
            movieids = [movieids]

        movieids = [int(mid) for mid in movieids if mid]
        if not movieids:
            return {}

        utils.log(f"HEAVY_META: Valid movieids: {movieids[:10]}{'...' if len(movieids) > 10 else ''}", "INFO")

        # Check cache first unless refresh is requested
        cached_data = {}
        missing_ids = movieids[:]

        if not refresh:
            cached_data = self._get_cached_heavy_meta(movieids)
            missing_ids = [mid for mid in movieids if mid not in cached_data]
            utils.log(f"HEAVY_META: Found {len(cached_data)} in cache, {len(missing_ids)} missing", "INFO")
        else:
            utils.log("HEAVY_META: Refresh requested, bypassing cache", "INFO")

        # Fetch missing data from Kodi
        fresh_data = {}
        if missing_ids:
            utils.log(f"HEAVY_META: Fetching {len(missing_ids)} movies from Kodi", "INFO")
            fresh_data = self._fetch_heavy_meta_from_kodi(missing_ids)
            utils.log(f"HEAVY_META: Retrieved {len(fresh_data)} fresh movies from Kodi", "INFO")

            # Log sample fresh data
            if fresh_data:
                first_movieid = list(fresh_data.keys())[0]
                sample_fresh = fresh_data[first_movieid]
                utils.log("=== SAMPLE FRESH HEAVY DATA FROM KODI ===", "INFO")
                for key, value in sample_fresh.items():
                    if isinstance(value, str) and len(value) > 200:
                        utils.log(f"FRESH_HEAVY: {key} = {value[:200]}... (truncated)", "INFO")
                    else:
                        utils.log(f"FRESH_HEAVY: {key} = {repr(value)}", "INFO")
                utils.log("=== END SAMPLE FRESH HEAVY DATA ===", "INFO")

            # Store fresh data in cache
            if fresh_data:
                fresh_list = [data for data in fresh_data.values()]
                utils.log(f"HEAVY_META: Storing {len(fresh_list)} movies in cache", "INFO")
                # Use execute_write to store the batch
                self._store_heavy_meta_batch_via_dao(fresh_list)

        # Combine cached and fresh data
        result = {}
        result.update(cached_data)
        result.update(fresh_data)

        utils.log(f"HEAVY_META: Final result contains {len(result)} movies", "INFO")

        # Log sample final result
        if result:
            first_result_id = list(result.keys())[0]
            sample_result = result[first_result_id]
            utils.log("=== SAMPLE FINAL HEAVY METADATA RESULT ===", "INFO")
            for key, value in sample_result.items():
                if isinstance(value, str) and len(value) > 200:
                    utils.log(f"FINAL_HEAVY: {key} = {value[:200]}... (truncated)", "INFO")
                else:
                    utils.log(f"FINAL_HEAVY: {key} = {repr(value)}", "INFO")
            utils.log("=== END SAMPLE FINAL HEAVY METADATA ===", "INFO")

        return result

    def _get_cached_heavy_meta(self, movieids):
        """Get heavy metadata from cache for multiple movie IDs"""
        if not movieids:
            return {}

        utils.log(f"=== _GET_CACHED_HEAVY_META: Looking up {len(movieids)} movie IDs ===", "INFO")

        # Build placeholders for the query
        placeholders = ','.join('?' * len(movieids))
        query = f"""
            SELECT kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json, 
                   stream_json, uniqueid_json, tags_json, updated_at
            FROM movie_heavy_meta 
            WHERE kodi_movieid IN ({placeholders})
        """

        try:
            results = self.query_manager.execute_query(query, tuple(movieids), fetch_all=True)
            utils.log(f"_GET_CACHED_HEAVY_META: Found {len(results)} cached entries", "INFO")

            cached_data = {}
            for row in results:
                movieid = row['kodi_movieid']

                # Parse JSON fields
                import json
                try:
                    cast_data = json.loads(row['cast_json']) if row['cast_json'] else []
                except:
                    cast_data = []

                try:
                    ratings_data = json.loads(row['ratings_json']) if row['ratings_json'] else {}
                except:
                    ratings_data = {}

                try:
                    showlink_data = json.loads(row['showlink_json']) if row['showlink_json'] else []
                except:
                    showlink_data = []

                try:
                    stream_data = json.loads(row['stream_json']) if row['stream_json'] else {}
                except:
                    stream_data = {}

                try:
                    uniqueid_data = json.loads(row['uniqueid_json']) if row['uniqueid_json'] else {}
                except:
                    uniqueid_data = {}

                try:
                    tags_data = json.loads(row['tags_json']) if row['tags_json'] else []
                except:
                    tags_data = []

                # Build the movie data structure
                movie_data = {
                    'movieid': movieid,
                    'imdbnumber': row['imdbnumber'] or '',
                    'cast': cast_data,
                    'ratings': ratings_data,
                    'showlink': showlink_data,
                    'streamdetails': stream_data,
                    'uniqueid': uniqueid_data,
                    'tag': tags_data
                }

                cached_data[movieid] = movie_data

            return cached_data

        except Exception as e:
            utils.log(f"Error getting cached heavy metadata: {str(e)}", "ERROR")
            return {}

    def _fetch_heavy_meta_from_kodi(self, movieids):
        """Fetch heavy metadata from Kodi for missing movie IDs"""
        if not movieids:
            return {}

        utils.log(f"=== _FETCH_HEAVY_META_FROM_KODI: Fetching {len(movieids)} movies ===", "INFO")

        try:
            from resources.lib.integrations.jsonrpc.jsonrpc_manager import JsonRpcManager
            jsonrpc = JsonRpcManager()

            # Define heavy properties that are expensive to fetch
            heavy_properties = [
                "cast", "ratings", "showlink", "streamdetails", "uniqueid", "tag"
            ]

            # Build filter for the specific movie IDs
            if len(movieids) == 1:
                movie_filter = {"movieid": movieids[0]}
            else:
                movie_filter = {"or": [{"movieid": mid} for mid in movieids]}

            # Make the JSON-RPC call
            response = jsonrpc.call_method("VideoLibrary.GetMovies", {
                "filter": movie_filter,
                "properties": heavy_properties
            })

            if not response or 'result' not in response:
                utils.log("No result from Kodi JSON-RPC call", "WARNING")
                return {}

            movies = response['result'].get('movies', [])
            utils.log(f"_FETCH_HEAVY_META_FROM_KODI: Got {len(movies)} movies from Kodi", "INFO")

            # Index by movieid
            heavy_data = {}
            for movie in movies:
                movieid = movie.get('movieid')
                if movieid:
                    heavy_data[movieid] = movie

            return heavy_data

        except Exception as e:
            utils.log(f"Error fetching heavy metadata from Kodi: {str(e)}", "ERROR")
            return {}

    def _store_heavy_meta_batch_via_dao(self, heavy_metadata_list):
        """Store heavy metadata batch using DAO methods"""
        if not heavy_metadata_list:
            return

        utils.log(f"=== _STORE_HEAVY_META_BATCH_VIA_DAO: Storing {len(heavy_metadata_list)} movies ===", "INFO")

        import json
        import time
        current_time = int(time.time())

        for movie_data in heavy_metadata_list:
            movieid = movie_data.get('movieid')
            if not movieid:
                continue

            # Convert complex fields to JSON
            cast_json = json.dumps(movie_data.get('cast', []))
            ratings_json = json.dumps(movie_data.get('ratings', {}))
            showlink_json = json.dumps(movie_data.get('showlink', []))
            stream_json = json.dumps(movie_data.get('streamdetails', {}))
            uniqueid_json = json.dumps(movie_data.get('uniqueid', {}))
            tags_json = json.dumps(movie_data.get('tag', []))

            try:
                # Try update first
                update_sql = """
                    UPDATE movie_heavy_meta SET
                        imdbnumber = ?,
                        cast_json = ?,
                        ratings_json = ?,
                        showlink_json = ?,
                        stream_json = ?,
                        uniqueid_json = ?,
                        tags_json = ?,
                        updated_at = ?
                    WHERE kodi_movieid = ?
                """
                update_params = (
                    movie_data.get('imdbnumber', ''),
                    cast_json,
                    ratings_json, 
                    showlink_json,
                    stream_json,
                    uniqueid_json,
                    tags_json,
                    current_time,
                    movieid
                )

                result = self.query_manager.execute_write(update_sql, update_params)

                if result['rowcount'] == 0:
                    # No rows updated, try insert
                    insert_sql = """
                        INSERT OR IGNORE INTO movie_heavy_meta
                            (kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json,
                             stream_json, uniqueid_json, tags_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    insert_params = (
                        movieid,
                        movie_data.get('imdbnumber', ''),
                        cast_json,
                        ratings_json,
                        showlink_json, 
                        stream_json,
                        uniqueid_json,
                        tags_json,
                        current_time
                    )
                    self.query_manager.execute_write(insert_sql, insert_params)

            except Exception as e:
                utils.log(f"Error storing heavy metadata for movie ID {movieid}: {str(e)}", "WARNING")
                continue

        utils.log(f"_STORE_HEAVY_META_BATCH_VIA_DAO: Completed storing batch", "INFO")