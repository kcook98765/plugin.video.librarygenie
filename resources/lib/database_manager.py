import os
import sqlite3
import json
import time
from resources.lib import utils
from resources.lib.config_manager import Config
from datetime import datetime # Import datetime

from resources.lib.singleton_base import Singleton

class DatabaseManager(Singleton):
    def __init__(self, db_path):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self.config = Config()  # Instantiate Config to access FIELDS
            self._connect()
            self.setup_database()
            self.ensure_search_history_folder()
            self._initialized = True

    def _connect(self):
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)

            self.connection = sqlite3.connect(self.db_path, timeout=30.0)
            self.cursor = self.connection.cursor()

            # Performance optimizations for bulk operations
            self.cursor.execute('PRAGMA foreign_keys = ON')
            self.cursor.execute('PRAGMA journal_mode = WAL')  # Write-Ahead Logging for better concurrency
            self.cursor.execute('PRAGMA synchronous = NORMAL')  # Faster writes
            self.cursor.execute('PRAGMA cache_size = 10000')  # Larger cache
            self.cursor.execute('PRAGMA temp_store = MEMORY')  # Use memory for temp tables

        except Exception as e:
            utils.log(f"Database connection error: {str(e)}", "ERROR")
            raise

    def _execute_with_retry(self, func, *args, **kwargs):
        retries = 10  # Increase retry count
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    # Exponential backoff: 0.1, 0.2, 0.4, 0.8, 1.6... seconds
                    wait_time = min(0.1 * (2 ** i), 2.0)  # Cap at 2 seconds
                    utils.log(f"Database is locked, retrying in {wait_time}s... ({i+1}/{retries})", "WARNING")
                    time.sleep(wait_time)
                else:
                    utils.log(f"Database error (non-lock): {str(e)}", "ERROR")
                    raise

        # If all retries failed
        utils.log(f"Database operation failed after {retries} retries", "ERROR")
        raise sqlite3.OperationalError("Database is locked - operation failed after retries")

    def setup_database(self):
        """Initialize database by delegating to query manager"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.setup_database()

    def fetch_folders(self, parent_id=None):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_folders_direct(parent_id)

    def fetch_lists(self, folder_id=None):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_lists_direct(folder_id)

    def fetch_data(self, table, condition=None):
        """Generic method to fetch data from a table"""
        try:
            if condition:
                query = f"SELECT * FROM {table} WHERE {condition}"
            else:
                query = f"SELECT * FROM {table}"
            self._execute_with_retry(self.cursor.execute, query)
            rows = self.cursor.fetchall()

            # Get column names
            columns = [description[0] for description in self.cursor.description]

            # Convert rows to list of dictionaries
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))

            return result
        except Exception as e:
            utils.log(f"Error fetching data from {table}: {str(e)}", "ERROR")
            return []



    def get_folder_depth(self, folder_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_folder_depth(folder_id)

    def insert_folder(self, name, parent_id=None):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.insert_folder_direct(name, parent_id)

    def update_list_folder(self, list_id, folder_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.update_list_folder(list_id, folder_id)

    def fetch_lists_with_item_status(self, item_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_lists_with_item_status(item_id)

    def fetch_all_lists_with_item_status(self, item_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_all_lists_with_item_status(item_id)

    def fetch_list_items(self, list_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_list_items_with_details(list_id)

    def truncate_data(self, data, max_length=10):
        truncated_data = {}
        for key, value in data.items():
            str_value = str(value)
            if len(str_value) > max_length:
                truncated_data[key] = str_value[:max_length] + "..."
            else:
                truncated_data[key] = str_value
        return truncated_data

    def bulk_insert_data(self, table, data_list):
        """Bulk insert multiple records in a single transaction for better performance"""
        if not data_list:
            return []

        try:
            self.connection.execute("BEGIN TRANSACTION")

            # Prepare the query
            first_item = data_list[0]
            columns = ', '.join(first_item.keys())
            placeholders = ', '.join(['?' for _ in first_item])
            query = f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})'

            # Convert cast lists to JSON strings if needed
            processed_data = []
            for data in data_list:
                if 'cast' in data and isinstance(data['cast'], list):
                    data = data.copy()  # Don't modify original
                    data['cast'] = json.dumps(data['cast'])
                processed_data.append(tuple(data.values()))

            # Execute bulk insert
            self.cursor.executemany(query, processed_data)
            self.connection.commit()

            utils.log(f"Bulk inserted {len(data_list)} records into {table}", "DEBUG")

            # Handle case where lastrowid is None (when INSERT OR IGNORE doesn't insert any rows)
            lastrowid = self.cursor.lastrowid
            if lastrowid is None:
                utils.log(f"No rows inserted into {table}. Possible conflict or ignore situation.", "WARNING")
                return []

            return [lastrowid - len(data_list) + i + 1 for i in range(len(data_list))]

        except Exception as e:
            self.connection.rollback()
            utils.log(f"Error in bulk insert to {table}: {str(e)}", "ERROR")
            raise

    def insert_data(self, table, data):
        from resources.lib.query_manager import QueryManager

        # Convert the cast list to a JSON string if it exists
        if 'cast' in data and isinstance(data['cast'], list):
            data['cast'] = json.dumps(data['cast'])

        if table == 'lists':
            utils.log(f"Inserting into lists table: {data}", "DEBUG")
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'

            self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
            self.connection.commit()
            last_id = self.cursor.lastrowid
            utils.log(f"Inserted into {table}, got ID: {last_id}", "DEBUG")
            return last_id
        elif table == 'media_items':
            # Handle media_items directly to avoid creating new connections
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})'

            try:
                cursor = self.cursor
                values = tuple(data.values())
                cursor.execute(query, values)
                self.connection.commit()
                row_id = cursor.lastrowid
                # Only log insertions for non-media_items or in debug mode
                if table != 'media_items' or utils.is_debug_enabled():
                    utils.log(f"Inserted into {table}, got ID: {row_id}", "DEBUG")
                return row_id
            except sqlite3.Error as e:
                utils.log(f"Error inserting into {table}: {str(e)}", "ERROR")
                raise
        elif table == 'list_items':
            query_manager = QueryManager(self.db_path)
            media_item_id = query_manager.insert_media_item(data)
            if media_item_id:
                list_data = {
                    'list_id': data['list_id'],
                    'media_item_id': media_item_id
                }
                query_manager.insert_list_item(list_data)
                utils.log(f"Inserted list item with media_item_id: {media_item_id}", "DEBUG")
            else:
                utils.log("No media_item_id found, insertion skipped", "ERROR")
        else:
            # For other tables, use generic insert with existing connection
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'

            self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
            self.connection.commit()

        utils.log(f"Data inserted into {table} successfully", "DEBUG")

    def _insert_or_ignore(self, table_name, data):
        # Check if data is not empty
        if not data:
            utils.log(f"_insert_or_ignore data is empty: {data}", "DEBUG")
            return

        # Prepare column names and placeholders for values
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))

        # Construct the SQL query
        query = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"

        # Execute the query with the data values
        self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
        self.connection.commit()

    def is_list_protected(self, list_id):
        """Check if a list is protected from modification"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        list_data = query_manager.fetch_list_by_id(list_id)
        return list_data and list_data.get('protected', 0) == 1

    def is_search_history_folder(self, folder_id):
        """Check if a folder is the Search History folder"""
        search_history_folder_id = self.get_folder_id_by_name("Search History")
        return folder_id == search_history_folder_id

    def delete_list(self, list_id):
        """Delete a list and all its related records"""
        # Check if list is protected (but not search history lists - only the folder is protected)
        if self.is_list_protected(list_id):
            raise ValueError("Cannot delete protected list")

        try:
            self.connection.execute("BEGIN")
            # Delete from list_items
            self._execute_with_retry(self.cursor.execute,
                "DELETE FROM list_items WHERE list_id = ?",
                (list_id,))

            # Finally delete the list itself
            self._execute_with_retry(self.cursor.execute,
                "DELETE FROM lists WHERE id = ?",
                (list_id,))

            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e

    def delete_data(self, table, condition):
        query = f'DELETE FROM {table} WHERE {condition}'
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query)
        self.connection.commit()

    def get_list_id_by_name(self, list_name):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_list_id_by_name(list_name)

    def get_lists_for_item(self, item_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_lists_for_item(item_id)

    def fetch_all_folders(self):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_all_folders()

    def fetch_lists_by_folder(self, folder_id):
        """Fetch all lists in a specific folder"""
        try:
            if folder_id is None:
                condition = "folder_id IS NULL"
            else:
                condition = f"folder_id = {folder_id}"

            lists = self.fetch_data('lists', condition)
            return lists if lists else []
        except Exception as e:
            utils.log(f"Error fetching lists by folder {folder_id}: {str(e)}", "ERROR")
            return []

    def fetch_all_lists(self):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_all_lists()

    def get_item_id_by_title_and_list(self, list_id, title):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_item_id_by_title_and_list(list_id, title)

    def get_folder_id_by_name(self, folder_name):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        result = query_manager.get_folder_by_name(folder_name)
        return result['id'] if result else None

    def update_folder_name(self, folder_id, new_name):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.update_folder_name(folder_id, new_name)

    def update_folder_parent(self, folder_id, new_parent_id, override_depth_check=False):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)

        if new_parent_id is not None:
            # Check if move would create a cycle
            temp_parent = new_parent_id
            while temp_parent is not None:
                if temp_parent == folder_id:
                    raise ValueError("Cannot move folder: would create a cycle")
                folder = query_manager.fetch_folder_by_id(temp_parent)
                temp_parent = folder['parent_id'] if folder else None

            # Check depth limit unless overridden
            if not override_depth_check:
                # Get the depth of the subtree being moved
                subtree_depth = query_manager.get_subtree_depth(folder_id)

                # Get the depth at the new location
                target_depth = query_manager.get_folder_depth(new_parent_id)

                # Calculate total depth after move
                total_depth = target_depth + subtree_depth + 1

                if total_depth > self.config.max_folder_depth:
                    raise ValueError(f"Moving folder would exceed maximum depth of {self.config.max_folder_depth}")

        query_manager.update_folder_parent(folder_id, new_parent_id)

    def _get_subtree_depth(self, folder_id):
        """Calculate the maximum depth of a folder's subtree"""
        query = """
            WITH RECURSIVE folder_tree AS (
                SELECT id, parent_id, 0 as depth
                FROM folders
                WHERE id = ?
                UNION ALL
                SELECT f.id, f.parent_id, ft.depth + 1
                FROM folders f
                JOIN folder_tree ft ON f.parent_id = ft.id
            )
            SELECT MAX(depth) FROM folder_tree
        """
        self._execute_with_retry(self.cursor.execute, query, (folder_id,))
        result = self.cursor.fetchone()
        return result[0] if result[0] is not None else 0

    def delete_folder_and_contents(self, folder_id):
        try:
            self.connection.execute("BEGIN")

            # Get all nested folder IDs
            self._execute_with_retry(self.cursor.execute, """
                WITH RECURSIVE nested_folders AS (
                    SELECT id FROM folders WHERE id = ?
                    UNION ALL
                    SELECT f.id FROM folders f
                    JOIN nested_folders nf ON f.parent_id = nf.id
                )
                SELECT id FROM nested_folders
            """, (folder_id,))
            folder_ids = [row[0] for row in self.cursor.fetchall()]

            if folder_ids:
                # Get all list IDs in these folders
                placeholders = ','.join('?' * len(folder_ids))
                self._execute_with_retry(self.cursor.execute,
                    f"SELECT id FROM lists WHERE folder_id IN ({placeholders})",
                    folder_ids)
                list_ids = [row[0] for row in self.cursor.fetchall()]

                # Delete all related records for each list
                for list_id in list_ids:
                    # Delete from list_items
                    self._execute_with_retry(self.cursor.execute,
                        "DELETE FROM list_items WHERE list_id = ?",
                        (list_id,))

                # Now delete the lists themselves
                self._execute_with_retry(self.cursor.execute,
                    f"DELETE FROM lists WHERE folder_id IN ({placeholders})",
                    folder_ids)

                # Finally delete all nested folders (in reverse order - children first)
                # Sort by depth descending to delete children before parents
                self._execute_with_retry(self.cursor.execute, """
                    WITH RECURSIVE nested_folders AS (
                        SELECT id, 0 as depth FROM folders WHERE id = ?
                        UNION ALL
                        SELECT f.id, nf.depth + 1 FROM folders f
                        JOIN nested_folders nf ON f.parent_id = nf.id
                    )
                    DELETE FROM folders WHERE id IN (
                        SELECT id FROM nested_folders ORDER BY depth DESC
                    )
                """, (folder_id,))

            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            utils.log(f"Error during folder deletion rollback: {str(e)}", "ERROR")
            raise e

    def fetch_folder_by_id(self, folder_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_folder_by_id(folder_id)

    def fetch_list_by_id(self, list_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_list_by_id(list_id)

    def fetch_folders_with_item_status(self, item_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.fetch_folders_with_item_status(item_id)

    def remove_media_item_from_list(self, list_id, media_item_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.remove_media_item_from_list(list_id, media_item_id)

    def fetch_media_items_by_folder(self, folder_id):
        """Fetch all media items from lists in a specific folder"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)

        # Get all lists in this folder
        lists_in_folder = query_manager.fetch_lists_direct(folder_id)

        all_media_items = []
        for list_item in lists_in_folder:
            # Get items from each list
            list_items = query_manager.fetch_list_items_with_details(list_item['id'])
            all_media_items.extend(list_items)

        return all_media_items



    def get_list_media_count(self, list_id):
        query = """
            SELECT COUNT(*)
            FROM list_items
            WHERE list_id = ?
        """
        self._execute_with_retry(self.cursor.execute, query, (list_id,))
        count = self.cursor.fetchone()[0]
        return count

    def get_folder_media_count(self, folder_id):
        def fetch_all_subfolder_ids(parent_id, visited=None):
            if visited is None:
                visited = set()
            if parent_id in visited:
                return []
            visited.add(parent_id)
            subfolders = [f['id'] for f in self.fetch_folders(parent_id)]
            all_subfolders = subfolders[:]
            for subfolder_id in subfolders:
                all_subfolders.extend(fetch_all_subfolder_ids(subfolder_id, visited))
            return all_subfolders

        folder_ids = [folder_id] + fetch_all_subfolder_ids(folder_id)
        folder_ids_placeholder = ', '.join('?' for _ in folder_ids)

        query = f"""
            SELECT COUNT(*)
            FROM list_items
            WHERE list_id IN (
                SELECT id FROM lists WHERE folder_id IN ({folder_ids_placeholder})
            )
        """
        self._execute_with_retry(self.cursor.execute, query, folder_ids)
        count = self.cursor.fetchone()[0]
        return count

    def insert_original_request(self, description, response_json):
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        self._execute_with_retry(self.cursor.execute, query, (description, response_json))
        self.connection.commit()
        return self.cursor.lastrowid

    def insert_parsed_movie(self, request_id, title, year, director):
        query = """
            INSERT INTO parsed_movies (request_id, title, year, director)
            VALUES (?, ?, ?, ?)
        """
        self._execute_with_retry(self.cursor.execute, query, (request_id, title, year, director))
        self.connection.commit()

    def get_imdb_export_stats(self):
        """Get statistics about IMDB numbers in exports"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_imdb_export_stats()

    def insert_imdb_export(self, movies):
        """Insert multiple movies into imdb_exports table"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.insert_imdb_export(movies)

    def get_valid_imdb_numbers(self):
        """Get all valid IMDB numbers from exports table"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_valid_imdb_numbers()

    def sync_movies(self, movies):
        """Sync movies with the database"""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.sync_movies(movies)

    def search_remote_movies(self, query, limit=20):
        """Search movies using remote API and return formatted results"""
        from resources.lib.remote_api_client import RemoteAPIClient

        remote_client = RemoteAPIClient()
        if not remote_client.api_key:
            utils.log("Remote API not configured", "WARNING")
            return []

        try:
            results = remote_client.search_movies(query, limit)

            # Convert remote API results to minimal format - only IMDB ID and score
            formatted_results = []
            for movie in results:
                formatted_movie = {
                    'imdbnumber': movie.get('imdb_id', ''),  # ONLY store IMDB ID
                    'score': movie.get('score', 0),          # ONLY store search score
                    'search_score': movie.get('score', 0)    # Alias for compatibility
                }
                formatted_results.append(formatted_movie)

            utils.log(f"Remote API semantic search returned {len(formatted_results)} movies", "DEBUG")

            # Add search history
            self.add_search_history(query, formatted_results)

            return formatted_results

        except Exception as e:
            utils.log(f"Error searching remote movies: {str(e)}", "ERROR")
            return []

    def ensure_search_history_folder(self):
        """Ensures the 'Search History' folder exists and is protected."""
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)

        search_history_folder_name = "Search History"

        # Check if the folder already exists
        existing_folder = query_manager.get_folder_by_name(search_history_folder_name)

        if not existing_folder:
            utils.log(f"Creating '{search_history_folder_name}' folder.", "INFO")
            query_manager.insert_folder_direct(search_history_folder_name, parent_id=None)

            newly_created_folder = query_manager.get_folder_by_name(search_history_folder_name)
            if newly_created_folder:
                utils.log(f"'{search_history_folder_name}' folder created with ID: {newly_created_folder['id']}", "INFO")
            else:
                utils.log(f"Failed to retrieve '{search_history_folder_name}' folder after creation.", "ERROR")
        else:
            utils.log(f"'{search_history_folder_name}' folder already exists.", "INFO")





    def add_search_history(self, query, results):
        """Adds the search results to the 'Search History' folder as a new list. Returns the list ID."""
        from resources.lib.query_manager import QueryManager

        query_manager = QueryManager(self.db_path)

        search_history_folder_id = self.get_folder_id_by_name("Search History")
        if not search_history_folder_id:
            utils.log("Search History folder not found, cannot save search results.", "ERROR")
            return None

        # Format the list name with search query, date only, and count
        timestamp = datetime.now().strftime("%Y-%m-%d")
        base_list_name = f"{query} ({timestamp}) ({len(results)})"


        # Check if a list with this name already exists and create unique name
        counter = 1
        list_name = base_list_name
        while self.get_list_id_by_name(list_name):
            list_name = f"{base_list_name} (#{counter})"
            counter += 1

        utils.log(f"Saving search results for query '{query}' into list '{list_name}'.", "INFO")

        # Create the final list (only one creation needed)
        final_list_data = {
            'name': list_name,
            'folder_id': search_history_folder_id
        }
        utils.log("=== SAVING LIST TITLE TO DATABASE ===", "INFO")
        utils.log(f"List title being saved: '{list_name}'", "INFO")
        utils.log(f"Full list data: {final_list_data}", "DEBUG")
        utils.log("=== END SAVING LIST TITLE ===", "INFO")
        final_list_id = self.insert_data('lists', final_list_data)
        utils.log(f"Created search history list with ID: {final_list_id}", "DEBUG")

        if final_list_id:
            utils.log(f"Successfully created search history list ID {final_list_id}, now adding {len(results)} items", "INFO")
            # Store only IMDB IDs and scores - no library data
            media_items_to_insert = []
            for i, result in enumerate(results):
                imdb_id = result.get('imdbnumber') or result.get('imdb_id', '')
                if not imdb_id:
                    utils.log(f"Skipping result {i+1}: No IMDB ID found", "WARNING")
                    continue

                score_display = result.get('score', result.get('search_score', 0))
                # utils.log(f"Processing search result {i+1}/{len(results)}: {imdb_id} with score {score_display}", "DEBUG")

                # Look up title and year from imdb_exports table if available
                title_from_exports = ''
                year_from_exports = 0

                try:
                    query = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                    self._execute_with_retry(self.cursor.execute, query, (imdb_id,))
                    export_result = self.cursor.fetchone()
                    if export_result:
                        title_from_exports = export_result[0] or ''
                        year_from_exports = int(export_result[1]) if export_result[1] else 0
                        # utils.log(f"Found title/year from exports for {imdb_id}: '{title}' ({year})", "DEBUG")
                    else:
                        utils.log(f"No export data found for {imdb_id}", "DEBUG")
                except Exception as e:
                    utils.log(f"Error looking up export data for {imdb_id}: {str(e)}", "DEBUG")

                # Store search data with title/year from imdb_exports if available
                plot_text = f"Search result for '{query}' - Score: {score_display}"
                if imdb_id:
                    plot_text += f" - IMDb: {imdb_id}"

                media_item_data = {
                    'kodi_id': 0,  # No Kodi ID for search results
                    'title': title_from_exports if title_from_exports else imdb_id,
                    'year': year_from_exports,    # Year from imdb_exports lookup
                    'rating': 0.0,
                    'plot': plot_text,
                    'tagline': 'Search result from LibraryGenie',
                    'genre': 'Search Result',
                    'director': '',
                    'studio': 'LibraryGenie',
                    'writer': '',
                    'country': '',
                    'cast': '[]',
                    'imdbnumber': imdb_id,  # Store IMDB ID
                    'art': '{}',
                    'poster': '',
                    'fanart': '',
                    'source': 'Lib',
                    'search_score': score_display,  # Store search score
                    'duration': 0,
                    'votes': 0,
                    'play': f"search_history://{imdb_id}"  # Unique identifier for search results
                }

                # Enhanced logging to show complete data being stored
                # utils.log(f"=== SEARCH HISTORY ITEM DETAILS FOR {imdb_id} ===", "DEBUG")
                # utils.log(f"Full media_item_data: {media_item_data}", "DEBUG")
                # utils.log(f"Original result keys: {list(result.keys())}", "DEBUG")
                # utils.log(f"Original result data: {result}", "DEBUG")
                # utils.log(f"=== END SEARCH HISTORY ITEM DETAILS ===", "DEBUG")

                media_items_to_insert.append(media_item_data)

            if media_items_to_insert:
                # Insert media items and link them to the new list
                for item_data in media_items_to_insert:
                    media_item_id = query_manager.insert_media_item(item_data)
                    if media_item_id:
                        list_item_data = {'list_id': final_list_id, 'media_item_id': media_item_id}
                        query_manager.insert_list_item(list_item_data)
                    else:
                        utils.log(f"Failed to insert media item for: {item_data.get('imdbnumber', 'N/A')}", "ERROR")
                utils.log("=== SEARCH HISTORY SAVE COMPLETE ===", "INFO")
                utils.log(f"List Name: '{list_name}'", "INFO")
                utils.log(f"List ID: {final_list_id}", "INFO")
                utils.log(f"Items Saved: {len(media_items_to_insert)}", "INFO")
                utils.log(f"Query: '{query}'", "INFO")
                utils.log("=== END SEARCH HISTORY SAVE ===", "INFO")
                return final_list_id
            else:
                utils.log(f"No valid media items to save for search query '{query}'.", "WARNING")
                # Delete the empty list if no items were added
                self.delete_list(final_list_id)
                utils.log(f"Deleted empty list '{list_name}' as no items were saved.", "INFO")
                return None

        else:
            utils.log(f"Failed to create list '{list_name}' for search history.", "ERROR")
            return None

    def __del__(self):
        if hasattr(self, 'connection') and self.connection:
            self.connection.close()


    def ensure_folder_exists(self, folder_name, parent_folder_id=None):
        """Ensure a folder exists, create if not found"""
        try:
            # Check if folder already exists using proper column name
            if parent_folder_id is None:
                condition = f"name = '{folder_name}' AND parent_id IS NULL"
            else:
                condition = f"name = '{folder_name}' AND parent_id = {parent_folder_id}"

            result = self.fetch_data('folders', condition)

            if result:
                utils.log(f"'{folder_name}' folder already exists.", "INFO")
                return result[0]['id']
            else:
                # Create the folder
                utils.log(f"Creating '{folder_name}' folder.", "INFO")
                folder_data = {
                    'name': folder_name,
                    'parent_id': parent_folder_id
                }
                folder_id = self.insert_data('folders', folder_data)
                utils.log(f"'{folder_name}' folder created with ID: {folder_id}", "INFO")
                return folder_id
        except Exception as e:
            utils.log(f"Error ensuring folder exists: {str(e)}", "ERROR")
            return None

    def create_list(self, list_name, folder_id=None):
        """Create a new list and return its ID"""
        try:
            list_data = {
                'name': list_name,
                'folder_id': folder_id
            }

            return self.insert_data('lists', list_data)

        except Exception as e:
            utils.log(f"Error creating list: {str(e)}", "ERROR")
            return None

    def update_data(self, table, data_dict, where_clause):
        """Update data in a table with a where clause"""
        try:
            set_clauses = []
            values = []

            for key, value in data_dict.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            set_clause = ", ".join(set_clauses)
            query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

            self.cursor.execute(query, values)
            self.connection.commit()

            return self.cursor.rowcount > 0

        except Exception as e:
            utils.log(f"Error updating data in {table}: {str(e)}", "ERROR")
            return False