
"""
ListingDAO - Data Access Object for folder and list operations
Extracted from QueryManager to separate concerns while maintaining the same API
"""

import sqlite3
import time
from contextlib import contextmanager
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config

class ListingDAO:
    """Data Access Object for folder and list database operations"""

    def __init__(self, execute_query_callable, execute_write_callable):
        """
        Initialize DAO with injected query executors

        Args:
            execute_query_callable: Function to execute SELECT queries
                                   Signature: execute_query(sql: str, params: tuple, fetch_all: bool) -> List[Dict]
            execute_write_callable: Function to execute INSERT/UPDATE/DELETE
                                   Signature: execute_write(sql: str, params: tuple) -> int
        """
        self.execute_query = execute_query_callable
        self.execute_write = execute_write_callable

    # =========================
    # FOLDER OPERATIONS
    # =========================

    def get_folders(self, parent_id=None):
        """Get folders by parent ID"""
        if parent_id is None:
            sql = "SELECT * FROM folders WHERE parent_id IS NULL ORDER BY name"
            params = ()
        else:
            sql = "SELECT * FROM folders WHERE parent_id = ? ORDER BY name"
            params = (parent_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_folders_direct(self, parent_id=None):
        """Direct folder fetch without transformation"""
        return self.get_folders(parent_id)

    def insert_folder_direct(self, name, parent_id):
        """Direct folder insertion"""
        sql = "INSERT INTO folders (name, parent_id) VALUES (?, ?)"
        return self.execute_write(sql, (name, parent_id))

    def update_folder_name_direct(self, folder_id, new_name):
        """Direct folder name update"""
        sql = "UPDATE folders SET name = ? WHERE id = ?"
        return self.execute_write(sql, (new_name, folder_id))

    def get_folder_depth(self, folder_id):
        """Calculate folder depth in hierarchy"""
        if folder_id is None:
            return 0

        depth = 0
        current_id = folder_id

        while current_id is not None:
            folder = self.fetch_folder_by_id(current_id)
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
        if parent_id is None:
            sql = "SELECT * FROM folders WHERE name = ? AND parent_id IS NULL"
            params = (name,)
        else:
            sql = "SELECT * FROM folders WHERE name = ? AND parent_id = ?"
            params = (name, parent_id)
        return self.execute_query(sql, params, fetch_one=True)

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
        direct_count_sql = """
            SELECT COUNT(*) as count
            FROM list_items li
            JOIN lists l ON li.list_id = l.id
            WHERE l.folder_id = ?
        """
        direct_result = self.execute_query(direct_count_sql, (folder_id,), fetch_one=True)
        direct_count = direct_result['count'] if direct_result else 0

        # Count items in subfolders recursively
        subfolder_count = 0
        subfolders = self.get_folders(folder_id)
        for subfolder in subfolders:
            subfolder_count += self.get_folder_media_count(subfolder['id'])

        return direct_count + subfolder_count

    def fetch_folder_by_id(self, folder_id):
        """Fetch folder by ID"""
        sql = "SELECT * FROM folders WHERE id = ?"
        return self.execute_query(sql, (folder_id,), fetch_one=True)

    def update_folder_parent(self, folder_id, new_parent_id):
        """Update folder parent"""
        sql = "UPDATE folders SET parent_id = ? WHERE id = ?"
        self.execute_write(sql, (new_parent_id, folder_id))
        return True

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
        self.execute_write("DELETE FROM folders WHERE id = ?", (folder_id,))
        return True

    def fetch_folders_with_item_status(self, parent_id, media_item_id):
        """Fetch folders with status for a media item"""
        sql = """
            SELECT f.*, 
                   CASE WHEN EXISTS (
                       SELECT 1 FROM lists l 
                       JOIN list_items li ON l.id = li.list_id 
                       WHERE l.folder_id = f.id AND li.media_item_id = ?
                   ) THEN 1 ELSE 0 END as has_item
            FROM folders f
            WHERE f.parent_id = ?
            ORDER BY f.name
        """
        if parent_id is None:
            sql = sql.replace("WHERE f.parent_id = ?", "WHERE f.parent_id IS NULL")
            params = (media_item_id,)
        else:
            params = (media_item_id, parent_id)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_all_folders(self):
        """Fetch all folders"""
        sql = "SELECT * FROM folders ORDER BY name"
        return self.execute_query(sql, fetch_all=True)

    # =========================
    # LIST OPERATIONS
    # =========================

    def get_lists(self, folder_id=None):
        """Get lists by folder ID"""
        if folder_id is None:
            sql = "SELECT * FROM lists WHERE folder_id IS NULL ORDER BY name"
            params = ()
        else:
            sql = "SELECT * FROM lists WHERE folder_id = ? ORDER BY name"
            params = (folder_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_lists_direct(self, folder_id=None):
        """Direct list fetch without transformation"""
        return self.get_lists(folder_id)

    def get_list_items(self, list_id):
        """Get items in a list"""
        sql = "SELECT * FROM list_items WHERE list_id = ?"
        return self.execute_query(sql, (list_id,), fetch_all=True)

    def fetch_list_items_with_details(self, list_id):
        """Fetch list items with detailed information including search scores"""
        sql = """
            SELECT m.*, li.search_score
            FROM list_items li
            JOIN media_items m ON li.media_item_id = m.id
            WHERE li.list_id = ?
            ORDER BY li.search_score DESC, m.title ASC
        """
        return self.execute_query(sql, (list_id,), fetch_all=True)

    def get_list_media_count(self, list_id):
        """Get media count for a list"""
        sql = "SELECT COUNT(*) as count FROM list_items WHERE list_id = ?"
        result = self.execute_query(sql, (list_id,), fetch_one=True)
        return result['count'] if result else 0

    def fetch_lists_with_item_status(self, folder_id, media_item_id):
        """Fetch lists with status for a media item"""
        sql = """
            SELECT l.*, 
                   CASE WHEN EXISTS (
                       SELECT 1 FROM list_items li 
                       WHERE li.list_id = l.id AND li.media_item_id = ?
                   ) THEN 1 ELSE 0 END as has_item
            FROM lists l
            WHERE l.folder_id = ?
            ORDER BY l.name
        """
        if folder_id is None:
            sql = sql.replace("WHERE l.folder_id = ?", "WHERE l.folder_id IS NULL")
            params = (media_item_id,)
        else:
            params = (media_item_id, folder_id)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_all_lists_with_item_status(self, media_item_id):
        """Fetch all lists with status for a media item"""
        sql = """
            SELECT l.*, 
                   CASE WHEN EXISTS (
                       SELECT 1 FROM list_items li 
                       WHERE li.list_id = l.id AND li.media_item_id = ?
                   ) THEN 1 ELSE 0 END as has_item
            FROM lists l
            ORDER BY l.name
        """
        return self.execute_query(sql, (media_item_id,), fetch_all=True)

    def update_list_folder(self, list_id, folder_id):
        """Update list's folder"""
        sql = "UPDATE lists SET folder_id = ? WHERE id = ?"
        self.execute_write(sql, (folder_id, list_id))
        return True

    def get_list_id_by_name(self, name, folder_id=None):
        """Get list ID by name and folder"""
        if folder_id is None:
            sql = "SELECT id FROM lists WHERE name = ? AND folder_id IS NULL"
            params = (name,)
        else:
            sql = "SELECT id FROM lists WHERE name = ? AND folder_id = ?"
            params = (name, folder_id)
        result = self.execute_query(sql, params, fetch_one=True)
        return result['id'] if result else None

    def get_lists_for_item(self, media_item_id):
        """Get all lists containing a media item"""
        sql = """
            SELECT l.*
            FROM lists l
            JOIN list_items li ON l.id = li.list_id
            WHERE li.media_item_id = ?
        """
        return self.execute_query(sql, (media_item_id,), fetch_all=True)

    def get_item_id_by_title_and_list(self, title, list_id):
        """Get media item ID by title within a specific list"""
        sql = """
            SELECT m.id
            FROM media_items m
            JOIN list_items li ON m.id = li.media_item_id
            WHERE m.title = ? AND li.list_id = ?
        """
        result = self.execute_query(sql, (title, list_id), fetch_one=True)
        return result['id'] if result else None

    def create_list(self, name, folder_id=None):
        """Create a new list"""
        sql = "INSERT INTO lists (name, folder_id) VALUES (?, ?)"
        list_id = self.execute_write(sql, (name, folder_id))
        return {'id': list_id, 'name': name, 'folder_id': folder_id}

    def get_unique_list_name(self, base_name, folder_id=None):
        """Generate a unique list name in the given folder"""
        counter = 1
        test_name = base_name

        while True:
            existing_id = self.get_list_id_by_name(test_name, folder_id)
            if not existing_id:
                return test_name

            counter += 1
            test_name = f"{base_name} ({counter})"

    def delete_list_and_contents(self, list_id):
        """Delete list and all its contents"""
        # Delete list items first
        self.execute_write("DELETE FROM list_items WHERE list_id = ?", (list_id,))

        # Delete the list itself
        self.execute_write("DELETE FROM lists WHERE id = ?", (list_id,))
        return True

    def fetch_all_lists(self):
        """Fetch all lists"""
        sql = "SELECT * FROM lists ORDER BY name"
        return self.execute_query(sql, fetch_all=True)

    def fetch_list_by_id(self, list_id):
        """Fetch list by ID"""
        sql = "SELECT * FROM lists WHERE id = ?"
        return self.execute_query(sql, (list_id,), fetch_one=True)

    def insert_list_item(self, list_id, media_item_id):
        """Insert item into list"""
        sql = "INSERT INTO list_items (list_id, media_item_id) VALUES (?, ?)"
        return self.execute_write(sql, (list_id, media_item_id))

    def remove_media_item_from_list(self, list_id, media_item_id):
        """Remove media item from list"""
        sql = "DELETE FROM list_items WHERE list_id = ? AND media_item_id = ?"
        self.execute_write(sql, (list_id, media_item_id))
        return True

    def get_list_item_by_media_id(self, list_id, media_item_id):
        """Get list item by list_id and media_item_id"""
        sql = "SELECT * FROM list_items WHERE list_id = ? AND media_item_id = ?"
        return self.execute_query(sql, (list_id, media_item_id), fetch_one=True)

    def upsert_heavy_meta(self, movieid, imdbnumber, cast_json, ratings_json, showlink_json, stream_json, uniqueid_json, tags_json, connection=None):
        """Upsert heavy metadata for a movie - uses query manager executors only"""
        import time

        try:
            current_time = int(time.time())
            
            # Always use query manager executors for consistency
            # First try to update existing record
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
                            stream_json, uniqueid_json, tags_json, current_time, movieid)

            self.execute_write(update_sql, update_params)

            # Check if record exists (since execute_write doesn't return rowcount)
            check_sql = "SELECT kodi_movieid FROM movie_heavy_meta WHERE kodi_movieid = ?"
            existing = self.execute_query(check_sql, (movieid,), fetch_one=True)
            
            if not existing:
                # No record found, try insert
                insert_sql = """
                    INSERT OR IGNORE INTO movie_heavy_meta
                        (kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json,
                         stream_json, uniqueid_json, tags_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                insert_params = (movieid, imdbnumber, cast_json, ratings_json, showlink_json, 
                               stream_json, uniqueid_json, tags_json, current_time)
                self.execute_write(insert_sql, insert_params)

            return movieid

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

            # Store fresh data in cache
            if fresh_data:
                fresh_list = [data for data in fresh_data.values()]
                utils.log(f"HEAVY_META: Storing {len(fresh_list)} movies in cache", "INFO")
                self._store_heavy_meta_batch_via_dao(fresh_list)

        # Combine cached and fresh data
        result = {}
        result.update(cached_data)
        result.update(fresh_data)

        utils.log(f"HEAVY_META: Final result contains {len(result)} movies", "INFO")
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
            results = self.execute_query(query, tuple(movieids), fetch_all=True)
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
        """Store heavy metadata batch using query manager executors"""
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
                # Try update first using query manager executor
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

                self.execute_write(update_sql, update_params)

                # Check if record exists (since execute_write doesn't return rowcount)
                check_sql = "SELECT kodi_movieid FROM movie_heavy_meta WHERE kodi_movieid = ?"
                existing = self.execute_query(check_sql, (movieid,), fetch_one=True)

                if not existing:
                    # No record found, try insert
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
                    self.execute_write(insert_sql, insert_params)

            except Exception as e:
                utils.log(f"Error storing heavy metadata for movie ID {movieid}: {str(e)}", "WARNING")
                continue

        utils.log(f"_STORE_HEAVY_META_BATCH_VIA_DAO: Completed storing batch", "INFO")
