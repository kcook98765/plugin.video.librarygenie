import os
import sqlite3
import json
import time
from resources.lib import utils
from resources.lib.config_manager import Config

from resources.lib.singleton_base import Singleton

class DatabaseManager(Singleton):
    def __init__(self, db_path):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self.config = Config()  # Instantiate Config to access FIELDS
            self._connect()
            self._initialized = True

    def _connect(self):
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)

            self.connection = sqlite3.connect(self.db_path, timeout=30.0)
            self.cursor = self.connection.cursor()
            self.cursor.execute('PRAGMA foreign_keys = ON')
        except Exception as e:
            utils.log(f"Database connection error: {str(e)}", "ERROR")
            raise

    def _execute_with_retry(self, func, *args, **kwargs):
        retries = 5
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    utils.log(f"Database is locked, retrying... ({i+1}/{retries})", "WARNING")
                    time.sleep(0.5)  # Wait for 0.5 seconds before retrying
                else:
                    raise

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

    def get_folder_depth(self, folder_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_folder_depth(folder_id)

    def insert_folder(self, name, parent_id=None):
        if parent_id is not None:
            current_depth = self.get_folder_depth(parent_id)
            max_depth = self.config.max_folder_depth - 1  # -1 because we're adding a new level
            if current_depth >= max_depth:
                raise ValueError(f"Maximum folder depth of {self.config.max_folder_depth} exceeded")

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

    def insert_data(self, table, data):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)

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
        elif table == 'list_items':
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
            # For other tables, use generic insert
            query_manager.insert_generic(table, data)

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

    def update_data(self, table, data, condition):
        columns = ', '.join(f'{col} = ?' for col in data)
        query = f'UPDATE {table} SET {columns} WHERE {condition}'
        utils.log(f"Executing SQL: {query} with data={data}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
        self.connection.commit()

    def delete_list(self, list_id):
        """Delete a list and all its related records"""
        try:
            self.connection.execute("BEGIN")
            # Delete from genie_lists first
            self._execute_with_retry(self.cursor.execute, 
                "DELETE FROM genie_lists WHERE list_id = ?", 
                (list_id,))

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

    def update_folder_parent(self, folder_id, new_parent_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        
        if new_parent_id is not None:
            # Get the depth of the subtree being moved
            subtree_depth = query_manager.get_subtree_depth(folder_id)

            # Get the depth at the new location
            target_depth = query_manager.get_folder_depth(new_parent_id)

            # Calculate total depth after move
            total_depth = target_depth + subtree_depth + 1

            if total_depth > self.config.max_folder_depth:
                raise ValueError(f"Moving folder would exceed maximum depth of {self.config.max_folder_depth}")

            # Check if move would create a cycle
            temp_parent = new_parent_id
            while temp_parent is not None:
                if temp_parent == folder_id:
                    raise ValueError("Cannot move folder: would create a cycle")
                folder = query_manager.fetch_folder_by_id(temp_parent)
                temp_parent = folder['parent_id'] if folder else None

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

            # Delete lists in all nested folders
            placeholders = ','.join('?' * len(folder_ids))
            self._execute_with_retry(self.cursor.execute, 
                f"DELETE FROM lists WHERE folder_id IN ({placeholders})", 
                folder_ids)

            # Delete all nested folders
            self._execute_with_retry(self.cursor.execute, 
                f"DELETE FROM folders WHERE id IN ({placeholders})", 
                folder_ids)

            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
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

    def get_genie_list(self, list_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        return query_manager.get_genie_list(list_id)

    def update_genie_list(self, list_id, description, rpc):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.update_genie_list(list_id, description, rpc)
        utils.log(f"Updated genie_list for list_id={list_id}", "DEBUG")

    def insert_genie_list(self, list_id, description, rpc):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.insert_genie_list(list_id, description, rpc)
        utils.log(f"Inserted genie_list for list_id={list_id}", "DEBUG")

    def delete_genie_list(self, list_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.delete_genie_list_direct(list_id)

    def remove_genielist_entries(self, list_id):
        from resources.lib.query_manager import QueryManager
        query_manager = QueryManager(self.db_path)
        query_manager.remove_genielist_entries_direct(list_id)
        utils.log(f"Removed GenieList entries for list_id={list_id}", "DEBUG")

    def insert_genielist_entries(self, list_id, media_items):
        for item in media_items:
            fields_keys = [field.split()[0] for field in Config.FIELDS]
            data = {field: item.get(field) for field in fields_keys}

            # Ensure data types are correct
            data['kodi_id'] = int(data['kodi_id']) if data['kodi_id'] and data['kodi_id'].isdigit() else 0
            data['duration'] = int(data['duration']) if data['duration'] and data['duration'].isdigit() else 0
            data['rating'] = float(data['rating']) if data['rating'] else 0.0
            data['votes'] = int(data['votes']) if data['votes'] else 0
            data['year'] = int(data['year']) if data['year'] else 0
            data['source'] = 'genielist'
            data['country'] = ','.join(data['country']) if isinstance(data['country'], list) else data['country']
            data['director'] = ','.join(data['director']) if isinstance(data['director'], list) else data['director']
            data['genre'] = ','.join(data['genre']) if isinstance(data['genre'], list) else data['genre']
            data['studio'] = ','.join(data['studio']) if isinstance(data['studio'], list) else data['studio']
            data['writer'] = ','.join(data['writer']) if isinstance(data['writer'], list) else data['writer']

            if 'cast' in data and isinstance(data['cast'], list):
                data['cast'] = json.dumps(data['cast'])

            self.insert_data('media_items', data)
            media_item_id = self.cursor.lastrowid
            list_item_data = {'list_id': list_id, 'media_item_id': media_item_id}
            self.insert_data('list_items', list_item_data)

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
            
            # Convert remote API results to our format
            formatted_results = []
            for movie in results:
                formatted_movie = {
                    'title': movie.get('title', ''),
                    'year': movie.get('year', 0),
                    'rating': movie.get('rating', 0.0),
                    'plot': movie.get('overview', ''),
                    'genre': ', '.join(movie.get('genres', [])),
                    'imdbnumber': movie.get('id', ''),
                    'art': {
                        'poster': movie.get('poster_url', ''),
                        'fanart': movie.get('backdrop_url', '')
                    },
                    'source': 'remote_api'
                }
                formatted_results.append(formatted_movie)
            
            utils.log(f"Remote API search returned {len(formatted_results)} movies", "DEBUG")
            return formatted_results
            
        except Exception as e:
            utils.log(f"Error searching remote movies: {str(e)}", "ERROR")
            return []

    def __del__(self):
        if getattr(self, 'connection', None):
            self.connection.close()