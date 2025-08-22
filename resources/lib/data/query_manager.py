import sqlite3
import os
import threading
import re
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union, Tuple
from resources.lib.utils import utils
from resources.lib.utils.singleton_base import Singleton
from resources.lib.config.config_manager import Config
import json # Ensure json is imported


class QueryManager(Singleton):
    """Central SQLite connection manager with pooling and transaction support"""

    def __init__(self, db_path: str):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self._connection = None
            self._lock = threading.RLock()
            self._ensure_connection()

            # Initialize DAO with query and write executors
            from resources.lib.data.dao.listing_dao import ListingDAO
            self._listing = ListingDAO(self.execute_query, self.execute_write)

            self._initialized = True

    @staticmethod
    def _validate_sql_identifier(identifier):
        """Validate SQL identifier against safe pattern"""
        if not identifier or not isinstance(identifier, str):
            return False

        # Check safe name pattern: alphanumeric, underscore, no spaces, reasonable length
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier) or len(identifier) > 64:
            return False

        # Additional check: identifier must not be a SQL keyword
        sql_keywords = {
            'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter', 
            'table', 'index', 'view', 'trigger', 'database', 'schema', 'from',
            'where', 'join', 'union', 'group', 'order', 'having', 'limit'
        }

        return identifier.lower() not in sql_keywords

    def _validate_table_exists(self, table_name):
        """Validate table exists in sqlite_master"""
        if not self._validate_sql_identifier(table_name):
            utils.log(f"Invalid table identifier: {table_name}", "ERROR")
            return False

        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
            fetch_one=True
        )
        return result is not None

    def _validate_column_exists(self, table_name, column_name):
        """Validate column exists in specified table"""
        if not self._validate_sql_identifier(table_name) or not self._validate_sql_identifier(column_name):
            return False

        if not self._validate_table_exists(table_name):
            return False

        # Use PRAGMA table_info to check column existence
        result = self.execute_query(
            f"PRAGMA table_info({table_name})",
            fetch_all=True
        )

        column_names = [row['name'] for row in result]
        return column_name in column_names


    def _ensure_connection(self):
        """Ensure we have a properly configured SQLite connection"""
        if self._connection is None:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            # Create connection with proper settings
            self._connection = sqlite3.connect(
                self.db_path, 
                timeout=30.0, 
                check_same_thread=False
            )

            # Set row factory for dict-like access
            self._connection.row_factory = sqlite3.Row

            # Configure SQLite with performance and safety PRAGMAs
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            self._connection.execute("PRAGMA temp_store=MEMORY")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA cache_size=-20000")  # ~20MB cache
            self._connection.commit()

            utils.log("QueryManager: SQLite connection established with optimized settings", "DEBUG")

    def _get_connection(self):
        """Internal method to get the managed connection"""
        self._ensure_connection()
        return self._connection

    def execute_query(self, sql: str, params: Tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> Union[Dict, List[Dict], None]:
        """Execute a SELECT query and return results"""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.execute(sql, params)

                if fetch_one:
                    row = cursor.fetchone()
                    result = dict(row) if row else None
                elif fetch_all:
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]
                else:
                    # Default to fetchall for backwards compatibility
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]

                cursor.close()
                return result

            except Exception as e:
                utils.log(f"QueryManager execute_query error: {str(e)}", "ERROR")
                utils.log(f"SQL: {sql}, Params: {params}", "ERROR")
                raise

    def execute_write(self, sql: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE and return lastrowid"""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.execute(sql, params)
                lastrowid = cursor.lastrowid
                conn.commit()
                cursor.close()
                return lastrowid

            except Exception as e:
                conn.rollback()
                utils.log(f"QueryManager execute_write error: {str(e)}", "ERROR")
                utils.log(f"SQL: {sql}, Params: {params}", "ERROR")
                raise

    def executemany_write(self, sql: str, seq_of_params: List[Tuple]) -> int:
        """Execute multiple statements and return rowcount"""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.executemany(sql, seq_of_params)
                rowcount = cursor.rowcount
                conn.commit()
                cursor.close()
                return rowcount

            except Exception as e:
                conn.rollback()
                utils.log(f"QueryManager executemany_write error: {str(e)}", "ERROR")
                utils.log(f"SQL: {sql}, Params count: {len(seq_of_params)}", "ERROR")
                raise

    @contextmanager
    def transaction(self):
        """Transaction context manager for atomic operations"""
        with self._lock:
            conn = self._get_connection()
            if conn is None:
                raise RuntimeError("Failed to establish database connection")
            try:
                conn.execute('BEGIN')
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # Legacy compatibility methods (to be removed later)
    def fetch_data(self, table: str, condition: str = "", params: Tuple = ()) -> List[Dict]:
        """Legacy method - fetch data from table"""
        if condition:
            sql = f"SELECT * FROM {table} WHERE {condition}"
        else:
            sql = f"SELECT * FROM {table}"
        return self.execute_query(sql, params, fetch_all=True)

    def insert_data(self, table: str, data: Dict) -> int:
        """Legacy method - insert data into table"""
        columns = list(data.keys())
        placeholders = ['?' for _ in columns]
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        params = tuple(data.values())
        return self.execute_write(sql, params)

    def update_data(self, table: str, data: Dict, condition: str, params: Tuple = ()) -> None:
        """Legacy method - update data in table"""
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        update_params = tuple(data.values()) + params
        self.execute_write(sql, update_params)

    def delete_data(self, table: str, condition: str, params: Tuple = ()) -> None:
        """Legacy method - delete data from table"""
        sql = f"DELETE FROM {table} WHERE {condition}"
        self.execute_write(sql, params)

    def get_list_media_count(self, list_id: int) -> int:
        """Get count of media items in a list"""
        sql = "SELECT COUNT(*) as count FROM list_items WHERE list_id = ?"
        result = self.execute_query(sql, (list_id,), fetch_one=True)
        return result['count'] if result else 0

    def fetch_list_by_id(self, list_id: int) -> Optional[Dict]:
        """Fetch list details by ID"""
        sql = "SELECT * FROM lists WHERE id = ?"
        return self.execute_query(sql, (list_id,), fetch_one=True)

    def fetch_folder_by_id(self, folder_id: int) -> Optional[Dict]:
        """Fetch folder details by ID"""
        sql = "SELECT * FROM folders WHERE id = ?"
        return self.execute_query(sql, (folder_id,), fetch_one=True)

    def fetch_folders(self, parent_id: Optional[int] = None) -> List[Dict]:
        """Fetch folders by parent ID"""
        if parent_id is None:
            sql = "SELECT * FROM folders WHERE parent_id IS NULL ORDER BY name"
            params = ()
        else:
            sql = "SELECT * FROM folders WHERE parent_id = ? ORDER BY name"
            params = (parent_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_lists(self, folder_id: Optional[int] = None) -> List[Dict]:
        """Fetch lists by folder ID"""
        if folder_id is None:
            sql = "SELECT * FROM lists WHERE folder_id IS NULL ORDER BY name"
            params = ()
        else:
            sql = "SELECT * FROM lists WHERE folder_id = ? ORDER BY name"
            params = (folder_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_all_lists(self) -> List[Dict]:
        """Fetch all lists"""
        sql = "SELECT * FROM lists ORDER BY name"
        return self.execute_query(sql, fetch_all=True)

    def fetch_all_folders(self) -> List[Dict]:
        """Fetch all folders"""
        sql = "SELECT * FROM folders ORDER BY name"
        return self.execute_query(sql, fetch_all=True)

    def get_folder_id_by_name(self, name: str) -> Optional[int]:
        """Get folder ID by name"""
        sql = "SELECT id FROM folders WHERE name = ?"
        result = self.execute_query(sql, (name,), fetch_one=True)
        return result['id'] if result else None

    def create_list(self, name: str, folder_id: Optional[int] = None) -> Dict:
        """Create a new list (skips reserved IDs 1-10)"""
        # For system lists like Kodi Favorites, use specific methods
        if name == "Kodi Favorites":
            return self.ensure_kodi_favorites_list()
        elif name == "Shortlist Imports":
            return self.ensure_shortlist_imports_list()
            
        data = {'name': name, 'folder_id': folder_id, 'protected': 0}
        list_id = self.insert_data('lists', data)
        return {'id': list_id, 'name': name, 'folder_id': folder_id}
    
    def ensure_kodi_favorites_list(self) -> Dict:
        """Ensure Kodi Favorites list exists with reserved ID 1"""
        existing_list = self.fetch_list_by_id(1)
        
        if existing_list:
            # Verify it's the correct list - if not, update it
            if existing_list['name'] != "Kodi Favorites":
                self.update_data('lists', {'name': 'Kodi Favorites', 'folder_id': None, 'protected': 1}, 'id = ?', (1,))
            return {'id': 1, 'name': 'Kodi Favorites', 'folder_id': None}
        
        # Create list with reserved ID 1
        self.execute_write(
            "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
            (1, "Kodi Favorites", None, 1)
        )
        
        return {'id': 1, 'name': 'Kodi Favorites', 'folder_id': None}
    
    def is_reserved_list_id(self, list_id: int) -> bool:
        """Check if list ID is reserved (1-10)"""
        return 1 <= list_id <= 10

    def create_folder(self, name: str, parent_id: Optional[int] = None) -> Dict:
        """Create a new folder"""
        data = {'name': name, 'parent_id': parent_id}
        folder_id = self.insert_data('folders', data)
        return {'id': folder_id, 'name': name, 'parent_id': parent_id}

    def move_list_to_folder(self, list_id: int, folder_id: Optional[int]) -> bool:
        """Move a list to a different folder"""
        try:
            self.update_data('lists', {'folder_id': folder_id}, 'id = ?', (list_id,))
            return True
        except Exception as e:
            utils.log(f"Error moving list {list_id} to folder {folder_id}: {str(e)}", "ERROR")
            return False

    def clear_list_items(self, list_id: int) -> bool:
        """Clear all items from a list"""
        try:
            self.delete_data('list_items', 'list_id = ?', (list_id,))
            return True
        except Exception as e:
            utils.log(f"Error clearing list {list_id}: {str(e)}", "ERROR")
            return False

    def delete_folder(self, folder_id: int) -> bool:
        """Delete a folder and all its contents atomically"""
        try:
            with self.transaction() as conn:
                # Delete all list items in lists within this folder
                conn.execute("""
                    DELETE FROM list_items 
                    WHERE list_id IN (SELECT id FROM lists WHERE folder_id = ?)
                """, (folder_id,))

                # Delete all lists in this folder
                conn.execute("DELETE FROM lists WHERE folder_id = ?", (folder_id,))

                # Delete the folder itself
                conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))

            return True
        except Exception as e:
            utils.log(f"Error deleting folder {folder_id}: {str(e)}", "ERROR")
            return False

    def update_folder_parent(self, folder_id: int, parent_id: Optional[int]) -> bool:
        """Update folder's parent"""
        try:
            self.update_data('folders', {'parent_id': parent_id}, 'id = ?', (folder_id,))
            return True
        except Exception as e:
            utils.log(f"Error updating folder parent: {str(e)}", "ERROR")
            return False

    def get_descendant_folder_ids(self, folder_id: int) -> List[int]:
        """Get all descendant folder IDs recursively"""
        descendant_ids = []

        def _get_children(parent_id):
            children = self.fetch_folders(parent_id)
            for child in children:
                descendant_ids.append(child['id'])
                _get_children(child['id'])  # Recurse

        _get_children(folder_id)
        return descendant_ids

    def get_folder_path(self, folder_id: int) -> str:
        """Get full path of a folder"""
        path_parts = []
        current_id = folder_id

        while current_id:
            folder = self.fetch_folder_by_id(current_id)
            if not folder:
                break
            path_parts.insert(0, folder['name'])
            current_id = folder.get('parent_id')

        return '/'.join(path_parts) if path_parts else ''

    def fetch_list_items_with_details(self, list_id: int) -> List[Dict]:
        """Fetch list items with media details"""
        sql = """
            SELECT m.*, li.search_score
            FROM list_items li
            JOIN media_items m ON li.media_item_id = m.id
            WHERE li.list_id = ?
            ORDER BY li.search_score DESC, m.title ASC
        """
        return self.execute_query(sql, (list_id,), fetch_all=True)

    def ensure_search_history_folder(self) -> Dict:
        """Ensure Search History folder exists"""
        folder_id = self.get_folder_id_by_name("Search History")
        if folder_id:
            return {'id': folder_id, 'name': "Search History"}
        else:
            return self.create_folder("Search History", None)

    def get_unique_list_name(self, base_name: str, folder_id: Optional[int]) -> str:
        """Get a unique list name by appending numbers if needed"""
        counter = 1
        test_name = base_name

        while True:
            existing = self.execute_query(
                "SELECT id FROM lists WHERE name = ? AND folder_id = ?",
                (test_name, folder_id),
                fetch_one=True
            )
            if not existing:
                return test_name

            counter += 1
            test_name = f"{base_name} ({counter})"

    def insert_media_item_and_add_to_list(self, list_id: int, media_item_data: Dict) -> bool:
        """Insert media item and add to list atomically"""
        try:
            with self.transaction() as conn:
                # Try to find existing media item first
                kodi_id = media_item_data.get('kodi_id', 0)
                play = media_item_data.get('play', '')
                
                existing_check = conn.execute(
                    "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
                    (kodi_id, play)
                ).fetchone()
                
                if existing_check:
                    media_id = existing_check[0]
                    utils.log(f"Found existing media item with ID: {media_id}", "DEBUG")
                else:
                    # Insert new media item using INSERT OR IGNORE to handle duplicates
                    columns = list(media_item_data.keys())
                    placeholders = ['?' for _ in columns]
                    sql = f"INSERT OR IGNORE INTO media_items ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    cursor = conn.execute(sql, tuple(media_item_data.values()))
                    media_id = cursor.lastrowid
                    
                    # If lastrowid is 0, the item already existed, so get its ID
                    if not media_id:
                        existing_result = conn.execute(
                            "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
                            (kodi_id, play)
                        ).fetchone()
                        if existing_result:
                            media_id = existing_result[0]
                        else:
                            utils.log("Failed to get media item ID after insert", "ERROR")
                            return False
                    
                    utils.log(f"Created new media item with ID: {media_id}", "DEBUG")

                # Check if already in list
                existing_list_item = conn.execute(
                    "SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?",
                    (list_id, media_id)
                ).fetchone()
                
                if not existing_list_item:
                    # Add to list with search score
                    search_score = media_item_data.get('search_score', 0)
                    conn.execute(
                        "INSERT INTO list_items (list_id, media_item_id, search_score) VALUES (?, ?, ?)",
                        (list_id, media_id, search_score)
                    )
                    utils.log(f"Added media item {media_id} to list {list_id}", "DEBUG")
                else:
                    utils.log(f"Media item {media_id} already in list {list_id}", "DEBUG")

            return True
        except Exception as e:
            utils.log(f"Error inserting media item and adding to list: {str(e)}", "ERROR")
            return False

    def close(self):
        """Close the database connection"""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                utils.log("QueryManager: Database connection closed", "DEBUG")

    # --- Methods from original QueryManager that need to be reimplemented or adapted ---

    def delete_folder_and_contents(self, folder_id):
        """Delete folder and all its contents in a single transaction"""
        utils.log(f"Deleting folder and contents for folder_id: {folder_id}", "DEBUG")
        return self.delete_folder(folder_id)

    def execute_rpc_query(self, rpc):
        """Execute RPC query and return results"""
        list_id = rpc.get('list_id')
        if not list_id:
            raise ValueError("list_id is required for execute_rpc_query")

        query = """
            SELECT m.*
            FROM media_items m
            JOIN list_items li ON m.id = li.media_item_id
            WHERE li.list_id = ?
            ORDER BY li.search_score DESC, m.title ASC
        """
        return self.execute_query(query, (list_id,), fetch_all=True)

    def save_llm_response(self, description, response_data):
        """Save LLM API response"""
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        return self.execute_write(query, (description, json.dumps(response_data)))

    def get_media_by_dbid(self, db_id: int, media_type: str = 'movie') -> Dict[str, Any]:
        """Get media details by database ID"""
        query = """
            SELECT *
            FROM media_items
            WHERE kodi_id = ? AND media_type = ?
        """
        return self.execute_query(query, (db_id, media_type), fetch_one=True) or {}

    def get_show_episode_details(self, show_id: int, season: int, episode: int) -> Dict[str, Any]:
        """Get TV show episode details"""
        query = """
            SELECT *
            FROM media_items
            WHERE show_id = ? AND season = ? AND episode = ?
        """
        return self.execute_query(query, (show_id, season, episode), fetch_one=True) or {}

    def get_search_results(self, title: str, year: Optional[int] = None, director: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get search results from media_items table"""
        # Validate table exists
        if not self._validate_table_exists('media_items'):
            utils.log("Table media_items does not exist", "ERROR")
            return []

        conditions = ["title LIKE ?"]
        params = [f"%{title}%"]

        if year:
            conditions.append("year = ?")
            params.append(str(year))
        if director:
            conditions.append("director LIKE ?")
            params.append(f"%{director}%")

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT DISTINCT *
            FROM media_items
            WHERE {where_clause}
            ORDER BY title COLLATE NOCASE
        """
        return self.execute_query(query, tuple(params), fetch_all=True)

    def insert_original_request(self, description: str, response_json: str) -> int:
        """Insert an original request and return its ID"""
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        return self.execute_write(query, (description, response_json))

    def insert_parsed_movie(self, request_id: int, title: str, year: Optional[int], director: Optional[str]) -> int:
        """Insert a parsed movie record"""
        query = """
            INSERT INTO parsed_movies (request_id, title, year, director)
            VALUES (?, ?, ?, ?)
        """
        return self.execute_write(query, (request_id, title, year, director))

    def insert_media_item(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert a media item and return its ID"""
        # Extract field names from config
        field_names = [field.split()[0] for field in Config.FIELDS]

        # Filter out None values and empty strings to prevent SQL issues
        filtered_data = {}
        for key in field_names:
            if key in data:
                value = data[key]
                # Convert None to empty string and ensure we have valid data
                if value is None:
                    value = ''
                elif isinstance(value, str) and value.strip() == '':
                    value = ''
                # Only include non-empty values or essential fields
                if value != '' or key in ['kodi_id', 'year', 'rating', 'duration', 'votes']:
                    filtered_data[key] = value

        media_data = filtered_data

        # Ensure essential fields have default values
        media_data.setdefault('kodi_id', 0)
        media_data.setdefault('year', 0)
        media_data.setdefault('rating', 0.0)
        media_data.setdefault('duration', 0)
        media_data.setdefault('votes', 0)
        media_data.setdefault('title', 'Unknown')

        # Set proper source based on kodi_id presence
        if 'source' not in media_data:
            if media_data.get('kodi_id', 0) > 0:
                media_data['source'] = 'lib'
            else:
                media_data['source'] = 'unknown'

        media_data.setdefault('media_type', 'movie')

        # Ensure search_score is included if present in input data
        if 'search_score' in data and 'search_score' not in media_data:
            media_data['search_score'] = data['search_score']

        # Process art data
        if 'art' in data:
            try:
                art_dict = data['art']

                if isinstance(art_dict, str):
                    art_dict = json.loads(art_dict)
                elif not isinstance(art_dict, dict):
                    art_dict = {}

                poster_url = (art_dict.get('poster') if isinstance(art_dict, dict) else None)
                if not poster_url:
                    poster_url = data.get('poster') or data.get('thumbnail')

                if poster_url:
                    art_dict = {
                        'poster': poster_url,
                        'thumb': poster_url,
                        'icon': poster_url,
                        'fanart': data.get('fanart', '')
                    }
                    media_data.update({
                        'art': json.dumps(art_dict),
                        'poster': poster_url,
                        'thumbnail': poster_url
                    })
            except Exception as e:
                utils.log(f"Error processing art data: {str(e)}", "ERROR")

        # Validate media_data before building query
        if not media_data:
            utils.log("ERROR - No valid media data to insert", "ERROR")
            return None

        # For shortlist imports and search results, always use INSERT to ensure new records are created
        source = media_data.get('source', '')
        if source in ('shortlist_import', 'search') or media_data.get('search_score'):
            query_type = 'INSERT OR REPLACE'
        else:
            query_type = 'INSERT OR IGNORE'

        columns = ', '.join(media_data.keys())
        placeholders = ', '.join('?' for _ in media_data)
        query = f'{query_type} INTO media_items ({columns}) VALUES ({placeholders})'

        return self.execute_write(query, tuple(media_data.values()))


    def upsert_reference_media_item(self, imdb_id: str, kodi_id: Optional[int] = None, source: str = 'lib') -> int:
        """Ensure a minimal media_items row exists for a library/provider item.
        Only identifiers are stored. Returns media_items.id.
        """
        if source not in ('lib', 'provider'):
            source = 'lib'
        uniqueid_json = json.dumps({'imdb': imdb_id}) if imdb_id else None

        # Try find existing
        query = """
            SELECT id FROM media_items
            WHERE source IN ('lib','provider')
              AND (
                    (uniqueid IS NOT NULL AND json_extract(uniqueid,'$.imdb') = ?)
                 OR (? IS NULL AND kodi_id = ?)
              )
            LIMIT 1
        """
        row = self.execute_query(query, (imdb_id, imdb_id, kodi_id), fetch_one=True)
        if row:
            return row['id'] or 0

        data = {
            'kodi_id': int(kodi_id or 0),
            'title': '',
            'year': 0,
            'source': source,
            'media_type': 'movie',
            'play': '',
            'uniqueid': uniqueid_json,
        }
        return self.insert_media_item(data) or 0

    def upsert_external_media_item(self, payload: dict) -> int:
        """Persist full metadata for a non-library item (external addon).
        Returns media_items.id.
        """
        payload = dict(payload or {})
        payload['source'] = 'external'
        payload.setdefault('media_type', 'movie')
        title = payload.get('title','')
        year = int(payload.get('year') or 0)
        play = payload.get('play','')
        existing = self.execute_query(
            """
            SELECT id FROM media_items
            WHERE source='external' AND title=? AND year=? AND COALESCE(play,'')=COALESCE(?, '')
            LIMIT 1
            """,
            (title, year, play),
            fetch_one=True
        )
        if existing:
            return existing['id'] or 0
        return self.insert_media_item(payload) or 0

    def insert_list_item(self, list_id, media_item_id):
        """Insert a list item - delegate to DAO"""
        return self._listing.insert_list_item(list_id, media_item_id)

    def insert_generic(self, table: str, data: Dict[str, Any]) -> int:
        """Generic table insert with validation"""
        # Validate table name
        if not self._validate_table_exists(table):
            utils.log(f"Invalid or non-existent table: {table}", "ERROR")
            raise ValueError(f"Invalid table name: {table}")

        # Validate all column names
        for column in data.keys():
            if not self._validate_column_exists(table, column):
                utils.log(f"Invalid column {column} for table {table}", "ERROR")
                raise ValueError(f"Invalid column name: {column}")

        columns = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
        return self.execute_write(query, tuple(data.values()))

    def get_matched_movies(self, title: str, year: Optional[int] = None, director: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get movies matching certain criteria"""
        # Validate table exists
        if not self._validate_table_exists('media_items'):
            utils.log("Table media_items does not exist", "ERROR")
            return []

        conditions = ["title LIKE ?"]
        params = [f"%{title}%"]

        if year:
            conditions.append("year = ?")
            params.append(str(year) if str(year).isdigit() else "0")
        if director:
            conditions.append("director LIKE ?")
            params.append(f"%{director}%")

        where_clause = " AND ".join(conditions)

        # Use explicit column list (all validated as existing columns)
        query = f"""
            SELECT DISTINCT
                id, kodi_id, title, year, plot, genre, director, cast,
                rating, file, thumbnail, fanart, duration, tagline,
                writer, imdbnumber, premiered, mpaa, trailer, votes,
                country, dateadded, studio, art, play, poster,
                media_type, source, path
            FROM media_items
            WHERE {where_clause}
            ORDER BY title COLLATE NOCASE
        """
        results = self.execute_query(query, tuple(params), fetch_all=True)

        # Process results to ensure all metadata is properly formatted
        for item in results:
            if 'art' in item and isinstance(item['art'], str):
                try:
                    item['art'] = json.loads(item['art'])
                except json.JSONDecodeError:
                    item['art'] = {}
            if 'cast' in item and isinstance(item['cast'], str):
                try:
                    item['cast'] = json.loads(item['cast'])
                except json.JSONDecodeError:
                    item['cast'] = []

        return results

    def get_media_details(self, kodi_dbid: int, media_type: str = 'movie') -> dict:
        """Get media details from database by Kodi database ID"""
        query = """
            SELECT *
            FROM media_items
            WHERE kodi_id = ? AND media_type = ?
        """
        return self.execute_query(query, (kodi_dbid, media_type), fetch_one=True) or {}

    def setup_database(self):
        """Setup all database tables"""
        # Ensure database directory exists first
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        fields_str = ', '.join(Config.FIELDS)

        table_creations = [
            # IMDB exports table for tracking exported data
            '''CREATE TABLE IF NOT EXISTS imdb_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kodi_id INTEGER,
                title TEXT,
                year INTEGER,
                imdb_id TEXT,
                exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',

            """CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                parent_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                folder_id INTEGER,
                protected INTEGER DEFAULT 0,
                FOREIGN KEY (folder_id) REFERENCES folders (id)
            )""",
            f"""CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {fields_str},
                UNIQUE (kodi_id, play)
            )""",
            """CREATE TABLE IF NOT EXISTS list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER,
                media_item_id INTEGER,
                search_score REAL DEFAULT 0,
                flagged INTEGER DEFAULT 0,
                FOREIGN KEY (list_id) REFERENCES lists (id),
                FOREIGN KEY (media_item_id) REFERENCES media_items (id)
            )""",


            """CREATE TABLE IF NOT EXISTS original_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT,
                response_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",


            """CREATE TABLE IF NOT EXISTS movie_heavy_meta (
                kodi_movieid INTEGER PRIMARY KEY,
                imdbnumber TEXT,
                cast_json TEXT,
                ratings_json TEXT,
                showlink_json TEXT,
                stream_json TEXT,
                uniqueid_json TEXT,
                tags_json TEXT,
                updated_at INTEGER NOT NULL
            )"""
        ]

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            for create_sql in table_creations:
                utils.log(f"Executing SQL: {create_sql}", "DEBUG")
                cursor.execute(create_sql)
            conn.commit()



            # Create index for movie_heavy_meta table
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_heavy_imdb ON movie_heavy_meta (imdbnumber)")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        # Setup movies reference table as well
        self.setup_movies_reference_table()
        
        # Ensure system lists exist
        self.ensure_system_lists()

    def setup_movies_reference_table(self):
        """Create movies_reference table and indexes"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create table
            create_table_sql = """
                CREATE TABLE IF NOT EXISTS movies_reference (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path   TEXT,
                    file_name   TEXT,
                    movieid     INTEGER,
                    imdbnumber  TEXT,
                    tmdbnumber  TEXT,
                    tvdbnumber  TEXT,
                    addon_file  TEXT,
                    source      TEXT NOT NULL CHECK(source IN ('Lib','File'))
                )
            """
            utils.log(f"Executing SQL: {create_table_sql}", "DEBUG")
            cursor.execute(create_table_sql)

            # Create indexes
            create_lib_index_sql = """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_lib_unique
                ON movies_reference(file_path, file_name)
                WHERE source = 'Lib'
            """
            utils.log(f"Executing SQL: {create_lib_index_sql}", "DEBUG")
            cursor.execute(create_lib_index_sql)

            create_file_index_sql = """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_file_unique
                ON movies_reference(addon_file)
                WHERE source = 'File'
            """
            utils.log(f"Executing SQL: {create_file_index_sql}", "DEBUG")
            cursor.execute(create_file_index_sql)

            conn.commit()

    def store_heavy_meta_batch(self, heavy_metadata_list):
        """Store heavy metadata for multiple movies in batch"""
        if not heavy_metadata_list:
            return

        # Minimal logging for heavy metadata storage
        if len(heavy_metadata_list) <= 5:
            utils.log(f"Storing heavy metadata: {len(heavy_metadata_list)} movies", "DEBUG")

        import time

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN")
                cursor = conn.cursor()

                current_time = int(time.time())

                # Log sample data before storage (only for first batch to reduce spam)
                if heavy_metadata_list and len(heavy_metadata_list) == 1:
                    sample_movie = heavy_metadata_list[0]
                    utils.log("=== SAMPLE HEAVY METADATA BEFORE STORAGE ===", "DEBUG")
                    for key, value in sample_movie.items():
                        if isinstance(value, str) and len(value) > 200:
                            utils.log(f"BEFORE_STORAGE: {key} = {value[:200]}... (truncated)", "DEBUG")
                        else:
                            utils.log(f"BEFORE_STORAGE: {key} = {repr(value)}", "DEBUG")
                    utils.log("=== END SAMPLE BEFORE STORAGE ===", "DEBUG")

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

                    # Log what's being stored for first movie (only for single movie batches to reduce spam)
                    if movie_data == heavy_metadata_list[0] and len(heavy_metadata_list) == 1:
                        utils.log("=== JSON FIELDS BEING STORED ===", "DEBUG")
                        utils.log(f"STORAGE_JSON: cast_json = {cast_json[:200]}{'...' if len(cast_json) > 200 else ''}", "DEBUG")
                        utils.log(f"STORAGE_JSON: ratings_json = {ratings_json}", "DEBUG")
                        utils.log(f"STORAGE_JSON: showlink_json = {showlink_json}", "DEBUG")
                        utils.log(f"STORAGE_JSON: stream_json = {stream_json[:200]}{'...' if len(stream_json) > 200 else ''}", "DEBUG")
                        utils.log(f"STORAGE_JSON: uniqueid_json = {uniqueid_json}", "DEBUG")
                        utils.log(f"STORAGE_JSON: tags_json = {tags_json}", "DEBUG")
                        utils.log("=== END JSON FIELDS BEING STORED ===", "DEBUG")

                    # Insert or replace heavy metadata
                    cursor.execute("""
                        INSERT OR REPLACE INTO movie_heavy_meta 
                        (kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json, 
                         stream_json, uniqueid_json, tags_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        movieid,
                        movie_data.get('imdbnumber', ''),
                        cast_json,
                        ratings_json, 
                        showlink_json,
                        stream_json,
                        uniqueid_json,
                        tags_json,
                        current_time
                    ))

                conn.commit()
                # Only log transaction commits for larger batches
                if len(heavy_metadata_list) > 50:
                    utils.log(f"Committed heavy metadata transaction: {len(heavy_metadata_list)} movies", "DEBUG")


                # Verify storage by checking first movie (only for first batch to reduce spam)
                if heavy_metadata_list and len(heavy_metadata_list) == 1:
                    first_movieid = heavy_metadata_list[0].get('movieid')
                    if first_movieid:
                        cursor.execute("SELECT * FROM movie_heavy_meta WHERE kodi_movieid = ?", (first_movieid,))
                        stored_row = cursor.fetchone()
                        if stored_row:
                            # Get column names
                            column_names = [description[0] for description in cursor.description]
                            stored_dict = dict(zip(column_names, stored_row))
                            utils.log("=== VERIFICATION OF STORED HEAVY METADATA ===", "DEBUG")
                            for key, value in stored_dict.items():
                                if isinstance(value, str) and len(value) > 200:
                                    utils.log(f"STORED_VERIFY: {key} = {value[:200]}... (truncated)", "DEBUG")
                                else:
                                    utils.log(f"STORED_VERIFY: {key} = {repr(value)}", "DEBUG")
                            utils.log("=== END VERIFICATION ===", "DEBUG")
                        else:
                            utils.log(f"ERROR: No stored heavy metadata found for movieid {first_movieid}", "ERROR")

            except Exception as e:
                conn.rollback()
                utils.log(f"Error storing heavy metadata batch: {str(e)}", "ERROR")
                raise

    def get_heavy_meta_by_movieids(self, movieids, refresh=False):
        """Get heavy metadata for multiple movie IDs with caching"""
        # This method relies on ListingDAO. If ListingDAO is not updated to use the new
        # QueryManager methods correctly, this might break. Assuming ListingDAO is compatible.
        return self._listing.get_heavy_meta_by_movieids(movieids, refresh)

    def get_imdb_export_stats(self) -> Dict[str, Any]:
        """Get statistics about IMDB numbers in exports"""
        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%' THEN 1 ELSE 0 END) as valid_imdb
            FROM imdb_exports
        """
        result = self.execute_query(query, fetch_one=True)
        total = result['total'] if result else 0
        valid_imdb = result['valid_imdb'] if result else 0
        return {
            'total': total,
            'valid_imdb': valid_imdb,
            'percentage': (valid_imdb / total * 100) if total > 0 else 0
        }

    def insert_imdb_export(self, movies: List[Dict[str, Any]]) -> None:
        """Insert multiple movies into imdb_exports table"""
        if not movies:
            return

        utils.log(f"=== INSERTING {len(movies)} MOVIES INTO IMDB_EXPORTS ===", "INFO")

        sql = """
            INSERT OR REPLACE INTO imdb_exports 
            (kodi_id, imdb_id, title, year)
            VALUES (?, ?, ?, ?)
        """

        data_to_insert = []
        for movie in movies:
            data_to_insert.append((
                movie.get('kodi_id'),
                movie.get('imdb_id', ''),
                movie.get('title', ''),
                movie.get('year', 0)
            ))

        if data_to_insert:
            self.executemany_write(sql, data_to_insert)
            utils.log(f"Successfully inserted {len(movies)} movies into imdb_exports", "INFO")

            # Verify insertion by checking first movie if available
            if movies:
                first_imdb = movies[0].get('imdb_id', '')
                if first_imdb:
                    verify_sql = "SELECT * FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"
                    stored_row = self.execute_query(verify_sql, (first_imdb,), fetch_one=True)
                    if stored_row:
                        utils.log("=== VERIFICATION OF IMDB_EXPORTS INSERTION ===", "INFO")
                        for key, value in stored_row.items():
                            utils.log(f"EXPORTS_VERIFY: {key} = {repr(value)}", "INFO")
                        utils.log("=== END EXPORTS VERIFICATION ===", "INFO")
                    else:
                        utils.log(f"ERROR: No stored export data found for imdb_id {first_imdb}", "ERROR")

    def ensure_shortlist_imports_list(self) -> Dict:
        """Ensure Shortlist Imports list exists with reserved ID 2"""
        existing_list = self.fetch_list_by_id(2)
        
        if existing_list:
            # Verify it's the correct list - if not, update it
            if existing_list['name'] != "Shortlist Imports":
                self.update_data('lists', {'name': 'Shortlist Imports', 'folder_id': None, 'protected': 1}, 'id = ?', (2,))
            return {'id': 2, 'name': 'Shortlist Imports', 'folder_id': None}
        
        # Create list with reserved ID 2
        self.execute_write(
            "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
            (2, "Shortlist Imports", None, 1)
        )
        
        return {'id': 2, 'name': 'Shortlist Imports', 'folder_id': None}

    def ensure_system_lists(self):
        """Ensure reserved system lists exist"""
        # Ensure Kodi Favorites list exists with ID 1
        existing_list = self.fetch_list_by_id(1)
        if not existing_list:
            utils.log("Creating reserved Kodi Favorites list with ID 1", "DEBUG")
            self.execute_write(
                "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
                (1, "Kodi Favorites", None, 1)
            )
        elif existing_list['name'] != "Kodi Favorites":
            utils.log(f"Updating list ID 1 to be Kodi Favorites (was: {existing_list['name']})", "DEBUG")
            self.update_data('lists', {'name': 'Kodi Favorites', 'folder_id': None, 'protected': 1}, 'id = ?', (1,))

        # Ensure Shortlist Imports list exists with ID 2
        existing_list = self.fetch_list_by_id(2)
        if not existing_list:
            utils.log("Creating reserved Shortlist Imports list with ID 2", "DEBUG")
            self.execute_write(
                "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
                (2, "Shortlist Imports", None, 1)
            )
        elif existing_list['name'] != "Shortlist Imports":
            utils.log(f"Updating list ID 2 to be Shortlist Imports (was: {existing_list['name']})", "DEBUG")
            self.update_data('lists', {'name': 'Shortlist Imports', 'folder_id': None, 'protected': 1}, 'id = ?', (2,))

    def get_valid_imdb_numbers(self) -> List[str]:
        """Get all valid IMDB numbers from exports table"""
        query = """
            SELECT imdb_id
            FROM imdb_exports
            WHERE imdb_id IS NOT NULL
            AND imdb_id != ''
            AND imdb_id LIKE 'tt%'
            ORDER BY imdb_id
        """
        results = self.execute_query(query, fetch_all=True)
        return [result['imdb_id'] for result in results]

    def sync_movies(self, movies: List[Dict[str, Any]]) -> None:
        """Sync movies with the database (reference-only policy).
        Legacy behavior inserted full library metadata into media_items.
        Under the new policy we only clear any stale 'lib' rows; library data
        is fetched on-demand via JSON-RPC when rendering lists.
        Search results (source='search') and other sources are preserved.
        """
        self.execute_write("DELETE FROM media_items WHERE source = 'lib'")

    def __del__(self):
        """Clean up connections when the instance is destroyed"""
        self.close()

    # --- DAO Delegation Methods (kept for compatibility with existing calls) ---
    # These methods delegate to the ListingDAO instance.

    # FOLDER DELEGATION METHODS
    def get_folders(self, parent_id=None):
        return self._listing.get_folders(parent_id)

    def fetch_folders_direct(self, parent_id=None):
        return self._listing.fetch_folders_direct(parent_id)

    def insert_folder_direct(self, name, parent_id):
        return self._listing.insert_folder_direct(name, parent_id)

    def update_folder_name_direct(self, folder_id, new_name):
        return self._listing.update_folder_name_direct(folder_id, new_name)

    def get_folder_depth(self, folder_id):
        # This method might need specific implementation if not covered by existing DAO methods
        # or if it relies on specific traversal logic. For now, assume it's handled.
        return self._listing.get_folder_depth(folder_id)

    def get_folder_by_name(self, name, parent_id=None):
        return self._listing.get_folder_by_name(name, parent_id)

    def get_folder_id_by_name(self, name, parent_id=None):
        return self._listing.get_folder_id_by_name(name, parent_id)

    def insert_folder(self, name, parent_id):
        return self._listing.insert_folder(name, parent_id)

    def create_folder(self, name, parent_id):
        return self._listing.create_folder(name, parent_id)

    def update_folder_name(self, folder_id, new_name):
        return self._listing.update_folder_name(folder_id, new_name)

    def get_folder_media_count(self, folder_id):
        return self._listing.get_folder_media_count(folder_id)

    def fetch_folder_by_id(self, folder_id):
        return self._listing.fetch_folder_by_id(folder_id)

    def update_folder_parent(self, folder_id, new_parent_id):
        return self._listing.update_folder_parent(folder_id, new_parent_id)

    def fetch_folders_with_item_status(self, parent_id, media_item_id):
        return self._listing.fetch_folders_with_item_status(parent_id, media_item_id)

    def fetch_all_folders(self):
        return self._listing.fetch_all_folders()

    # LIST DELEGATION METHODS
    def get_lists(self, folder_id=None):
        return self._listing.get_lists(folder_id)

    def fetch_lists_direct(self, folder_id=None):
        return self._listing.fetch_lists_direct(folder_id)

    def get_list_items(self, list_id):
        return self._listing.get_list_items(list_id)

    def get_list_media_count(self, list_id):
        return self._listing.get_list_media_count(list_id)

    def fetch_lists_with_item_status(self, folder_id, media_item_id):
        return self._listing.fetch_lists_with_item_status(folder_id, media_item_id)

    def fetch_all_lists_with_item_status(self, media_item_id):
        return self._listing.fetch_all_lists_with_item_status(media_item_id)

    def update_list_folder(self, list_id, folder_id):
        return self._listing.update_list_folder(list_id, folder_id)

    def get_list_id_by_name(self, name, folder_id=None):
        return self._listing.get_list_id_by_name(name, folder_id)

    def get_lists_for_item(self, media_item_id):
        return self._listing.get_lists_for_item(media_item_id)

    def get_item_id_by_title_and_list(self, title, list_id):
        return self._listing.get_item_id_by_title_and_list(title, list_id)

    def create_list(self, name, folder_id=None):
        return self._listing.create_list(name, folder_id)

    def get_unique_list_name(self, base_name, folder_id=None):
        return self._listing.get_unique_list_name(base_name, folder_id)

    def delete_list_and_contents(self, list_id):
        """Delete a list and all its contents"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM list_items WHERE list_id = ?", (list_id,))
            conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        self._log_operation("DELETE", f"List {list_id} and contents")

    def clear_list_contents(self, list_id):
        """Clear all items from a list without deleting the list itself"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM list_items WHERE list_id = ?", (list_id,))
        self._log_operation("DELETE", f"Contents of list {list_id}")

    def fetch_all_lists(self):
        return self._listing.fetch_all_lists()

    def fetch_list_by_id(self, list_id):
        return self._listing.fetch_list_by_id(list_id)

    def remove_media_item_from_list(self, list_id, media_item_id):
        return self._listing.remove_media_item_from_list(list_id, media_item_id)

    def get_list_item_by_media_id(self, list_id, media_item_id):
        return self._listing.get_list_item_by_media_id(list_id, media_item_id)

    def fetch_list_items_with_details(self, list_id):
        return self._listing.fetch_list_items_with_details(list_id)