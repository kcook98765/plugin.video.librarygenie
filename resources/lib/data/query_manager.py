import sqlite3
import os
import threading
import re
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union, Tuple
from resources.lib.utils import utils
from resources.lib.utils.singleton_base import Singleton
from resources.lib.config.config_manager import Config
import json


class QueryManager(Singleton):
    """Central SQLite connection manager with pooling and transaction support."""

    def __init__(self, db_path: str):
        # If the singleton was already initialized, warn on path drift and return.
        if hasattr(self, '_initialized') and self._initialized:
            if getattr(self, 'db_path', None) and self.db_path != db_path:
                utils.log(f"QueryManager: Ignoring new db_path '{db_path}' (already initialized with '{self.db_path}')", "WARNING")
            return

        self.db_path = db_path
        self._connection = None
        self._lock = threading.RLock()
        self._ensure_connection()

        # Initialize DAO with query and write executors
        from resources.lib.data.dao.listing_dao import ListingDAO
        self._listing = ListingDAO(self.execute_query, self.execute_write)

        self._initialized = True

    # -------------------------
    # Identifier/Table Guards
    # -------------------------
    @staticmethod
    def _validate_sql_identifier(identifier: str) -> bool:
        """Validate SQL identifier against safe pattern."""
        if not identifier or not isinstance(identifier, str):
            return False

        # Safe name pattern: alphanumeric + underscore, not starting with digit
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier) or len(identifier) > 64:
            return False

        sql_keywords = {
            'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter',
            'table', 'index', 'view', 'trigger', 'database', 'schema', 'from',
            'where', 'join', 'union', 'group', 'order', 'having', 'limit'
        }
        return identifier.lower() not in sql_keywords

    def _validate_table_exists(self, table_name: str) -> bool:
        """Validate table exists in sqlite_master."""
        if not self._validate_sql_identifier(table_name):
            utils.log(f"Invalid table identifier: {table_name}", "ERROR")
            return False

        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
            fetch_one=True
        )
        return result is not None

    def _validate_column_exists(self, table_name: str, column_name: str) -> bool:
        """Validate column exists in specified table."""
        if not self._validate_sql_identifier(table_name) or not self._validate_sql_identifier(column_name):
            return False
        if not self._validate_table_exists(table_name):
            return False

        rows = self.execute_query(f"PRAGMA table_info({table_name})", fetch_all=True)
        column_names = [row['name'] for row in rows]
        return column_name in column_names

    # -------------------------
    # Connection / PRAGMAs
    # -------------------------
    def _ensure_connection(self):
        """Ensure we have a properly configured SQLite connection."""
        if self._connection is not None:
            return

        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Create connection with proper settings
        self._connection = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row

        # Configure PRAGMAs
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA temp_store=MEMORY")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA cache_size=-20000")   # ~20MB cache
        self._connection.execute("PRAGMA busy_timeout=5000")   # 5s busy timeout
        self._connection.commit()

        utils.log("QueryManager: SQLite connection established with optimized settings", "DEBUG")

    def _get_connection(self):
        """Internal method to get the managed connection."""
        self._ensure_connection()
        return self._connection

    # -------------------------
    # Core Exec Helpers
    # -------------------------
    def execute_query(
        self,
        sql: str,
        params: Tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False
    ) -> Union[Dict, List[Dict], None]:
        """Execute a SELECT query and return results as dicts."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.execute(sql, params)

                if fetch_one:
                    row = cursor.fetchone()
                    result = dict(row) if row else None
                else:
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]

                cursor.close()
                return result
            except Exception as e:
                utils.log(f"QueryManager execute_query error: {str(e)}", "ERROR")
                utils.log(f"SQL: {sql}, Params: {params}", "ERROR")
                raise

    def execute_write(self, sql: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE and return lastrowid."""
        with self._lock:
            conn = self._get_connection()
            try:
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
        """Execute multiple statements and return rowcount."""
        with self._lock:
            conn = self._get_connection()
            try:
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
        """Transaction context manager for atomic operations."""
        with self._lock:
            conn = self._get_connection()
            if conn is None:
                raise RuntimeError("Failed to establish database connection")
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # -------------------------
    # Minimal, Stable Public API (non-DAO)
    # -------------------------

    def delete_folder(self, folder_id: int) -> bool:
        """Delete a folder and all its contents atomically."""
        try:
            with self.transaction() as conn:
                conn.execute("""
                    DELETE FROM list_items
                    WHERE list_id IN (SELECT id FROM lists WHERE folder_id = ?)
                """, (folder_id,))
                conn.execute("DELETE FROM lists WHERE folder_id = ?", (folder_id,))
                conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            return True
        except Exception as e:
            utils.log(f"Error deleting folder {folder_id}: {str(e)}", "ERROR")
            return False

    def clear_list_items(self, list_id: int) -> bool:
        """Clear all items from a list."""
        try:
            self.execute_write("DELETE FROM list_items WHERE list_id = ?", (list_id,))
            return True
        except Exception as e:
            utils.log(f"Error clearing list {list_id}: {str(e)}", "ERROR")
            return False

    def get_descendant_folder_ids(self, folder_id: int) -> List[int]:
        """Get all descendant folder IDs recursively (uses DAO for reads)."""
        descendant_ids: List[int] = []

        def _walk(pid: int):
            for child in self.get_folders(pid) or []:
                cid = child['id']
                descendant_ids.append(cid)
                _walk(cid)

        _walk(folder_id)
        return descendant_ids

    def get_folder_path(self, folder_id: int) -> str:
        """Get full path of a folder (uses DAO for reads)."""
        parts: List[str] = []
        current_id = folder_id

        while current_id:
            folder = self.fetch_folder_by_id(current_id)
            if not folder:
                break
            parts.insert(0, folder['name'])
            current_id = folder.get('parent_id')

        return "/".join(parts) if parts else ""

    def ensure_search_history_folder(self) -> Dict:
        """Ensure 'Search History' folder exists."""
        fid = self.get_folder_id_by_name("Search History")
        if fid:
            return {'id': fid, 'name': "Search History"}
        created = self.create_folder("Search History", None)
        return {'id': created['id'], 'name': created['name']}

    def execute_rpc_query(self, rpc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute RPC-like query and return list contents."""
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

    def save_llm_response(self, description: str, response_data: Any) -> int:
        """Save LLM API response into original_requests."""
        query = "INSERT INTO original_requests (description, response_json) VALUES (?, ?)"
        return self.execute_write(query, (description, json.dumps(response_data)))

    def insert_original_request(self, description: str, response_json: str) -> int:
        query = "INSERT INTO original_requests (description, response_json) VALUES (?, ?)"
        return self.execute_write(query, (description, response_json))

    def insert_parsed_movie(self, request_id: int, title: str, year: Optional[int], director: Optional[str]) -> int:
        query = "INSERT INTO parsed_movies (request_id, title, year, director) VALUES (?, ?, ?, ?)"
        return self.execute_write(query, (request_id, title, year, director))

    def get_media_by_dbid(self, db_id: int, media_type: str = 'movie') -> Dict[str, Any]:
        query = "SELECT * FROM media_items WHERE kodi_id = ? AND media_type = ?"
        return self.execute_query(query, (db_id, media_type), fetch_one=True) or {}

    def get_show_episode_details(self, show_id: int, season: int, episode: int) -> Dict[str, Any]:
        query = "SELECT * FROM media_items WHERE show_id = ? AND season = ? AND episode = ?"
        return self.execute_query(query, (show_id, season, episode), fetch_one=True) or {}

    def get_search_results(
        self,
        title: str,
        year: Optional[int] = None,
        director: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Basic LIKE search in media_items."""
        if not self._validate_table_exists('media_items'):
            utils.log("Table media_items does not exist", "ERROR")
            return []

        conditions = ["title LIKE ?"]
        params: List[Any] = [f"%{title}%"]
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

    def insert_media_item(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert a media item and return its ID (keeps your existing normalization)."""
        # Extract field names from config
        field_names = [field.split()[0] for field in Config.FIELDS]

        # Filter out None/empty (except whitelisted numeric fields)
        filtered: Dict[str, Any] = {}
        for key in field_names:
            if key in data:
                value = data[key]
                if value is None:
                    value = ''
                elif isinstance(value, str) and value.strip() == '':
                    value = ''
                if value != '' or key in ['kodi_id', 'year', 'rating', 'duration', 'votes']:
                    filtered[key] = value

        media_data = filtered
        media_data.setdefault('kodi_id', 0)
        media_data.setdefault('year', 0)
        media_data.setdefault('rating', 0.0)
        media_data.setdefault('duration', 0)
        media_data.setdefault('votes', 0)
        media_data.setdefault('title', 'Unknown')

        # Source default
        if 'source' not in media_data:
            media_data['source'] = 'lib' if media_data.get('kodi_id', 0) > 0 else 'unknown'
        media_data.setdefault('media_type', 'movie')

        # Optional search_score passthrough
        if 'search_score' in data and 'search_score' not in media_data:
            media_data['search_score'] = data['search_score']

        # Art normalization
        if 'art' in data:
            try:
                art_dict = data['art']
                if isinstance(art_dict, str):
                    art_dict = json.loads(art_dict)
                elif not isinstance(art_dict, dict):
                    art_dict = {}
                poster_url = (art_dict.get('poster') if isinstance(art_dict, dict) else None) or data.get('poster') or data.get('thumbnail')
                if poster_url:
                    art_dict = {'poster': poster_url, 'thumb': poster_url, 'icon': poster_url, 'fanart': data.get('fanart', '')}
                    media_data.update({'art': json.dumps(art_dict), 'poster': poster_url, 'thumbnail': poster_url})
            except Exception as e:
                utils.log(f"Error processing art data: {str(e)}", "ERROR")

        if not media_data:
            utils.log("ERROR - No valid media data to insert", "ERROR")
            return None

        # Policy: shortlist/search get REPLACE; others IGNORE
        source = media_data.get('source', '')
        query_type = 'INSERT OR REPLACE' if (source in ('shortlist_import', 'search') or media_data.get('search_score')) else 'INSERT OR IGNORE'

        columns = ', '.join(media_data.keys())
        placeholders = ', '.join('?' for _ in media_data)
        query = f'{query_type} INTO media_items ({columns}) VALUES ({placeholders})'
        return self.execute_write(query, tuple(media_data.values()))

    def upsert_reference_media_item(self, imdb_id: str, kodi_id: Optional[int] = None, source: str = 'lib') -> int:
        """Ensure a minimal media_items row exists for a library/provider item."""
        if source not in ('lib', 'provider'):
            source = 'lib'
        uniqueid_json = json.dumps({'imdb': imdb_id}) if imdb_id else None

        row = self.execute_query(
            """
            SELECT id FROM media_items
            WHERE source IN ('lib','provider')
              AND (
                    (uniqueid IS NOT NULL AND json_extract(uniqueid,'$.imdb') = ?)
                 OR (? IS NULL AND kodi_id = ?)
              )
            LIMIT 1
            """,
            (imdb_id, imdb_id, kodi_id),
            fetch_one=True
        )
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
        """Persist full metadata for a non-library item (external addon)."""
        payload = dict(payload or {})
        payload['source'] = 'external'
        payload.setdefault('media_type', 'movie')
        title = payload.get('title', '')
        year = int(payload.get('year') or 0)
        play = payload.get('play', '')
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

    def insert_list_item(self, list_id: int, media_item_id: int) -> int:
        """Insert a list item - delegate to DAO."""
        return self._listing.insert_list_item(list_id, media_item_id)

    def insert_generic(self, table: str, data: Dict[str, Any]) -> int:
        """Generic table insert with validation."""
        if not self._validate_table_exists(table):
            utils.log(f"Invalid or non-existent table: {table}", "ERROR")
            raise ValueError(f"Invalid table name: {table}")
        for column in data.keys():
            if not self._validate_column_exists(table, column):
                utils.log(f"Invalid column {column} for table {table}", "ERROR")
                raise ValueError(f"Invalid column name: {column}")

        columns = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
        return self.execute_write(query, tuple(data.values()))

    def get_matched_movies(
        self,
        title: str,
        year: Optional[int] = None,
        director: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get movies matching certain criteria with explicit columns."""
        if not self._validate_table_exists('media_items'):
            utils.log("Table media_items does not exist", "ERROR")
            return []

        conditions = ["title LIKE ?"]
        params: List[Any] = [f"%{title}%"]
        if year:
            conditions.append("year = ?")
            params.append(str(year) if str(year).isdigit() else "0")
        if director:
            conditions.append("director LIKE ?")
            params.append(f"%{director}%")

        where_clause = " AND ".join(conditions)
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

        # Normalize JSON-ish fields
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
        query = "SELECT * FROM media_items WHERE kodi_id = ? AND media_type = ?"
        return self.execute_query(query, (kodi_dbid, media_type), fetch_one=True) or {}

    # -------------------------
    # Schema Setup / Bootstrap
    # -------------------------
    def setup_database(self):
        """Setup all database tables."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        fields_str = ', '.join(Config.FIELDS)
        table_creations = [
            # IMDB exports
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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                folder_id INTEGER,
                protected INTEGER DEFAULT 0,
                FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
            )""",
            f"""CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {fields_str},
                UNIQUE (kodi_id, play)
            )""",
            """CREATE TABLE IF NOT EXISTS list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                media_item_id INTEGER NOT NULL,
                search_score REAL DEFAULT 0,
                flagged INTEGER DEFAULT 0,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE,
                FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE,
                UNIQUE(list_id, media_item_id)
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

            # Index for heavy meta lookups
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_heavy_imdb ON movie_heavy_meta (imdbnumber)")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        # Additional reference table + indices
        self.setup_movies_reference_table()

        # Ensure system lists exist
        self.ensure_system_lists()

    def setup_movies_reference_table(self):
        """Create movies_reference table and indexes."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
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
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_lib_unique
                ON movies_reference(file_path, file_name)
                WHERE source = 'Lib'
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_file_unique
                ON movies_reference(addon_file)
                WHERE source = 'File'
            """)

            conn.commit()

    def store_heavy_meta_batch(self, heavy_metadata_list: List[Dict[str, Any]]):
        """Store heavy metadata for multiple movies in batch."""
        if not heavy_metadata_list:
            return
        import time

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN")
                cursor = conn.cursor()
                current_time = int(time.time())

                for movie_data in heavy_metadata_list:
                    movieid = movie_data.get('movieid')
                    if not movieid:
                        continue

                    cast_json = json.dumps(movie_data.get('cast', []))
                    ratings_json = json.dumps(movie_data.get('ratings', {}))
                    showlink_json = json.dumps(movie_data.get('showlink', []))
                    stream_json = json.dumps(movie_data.get('streamdetails', {}))
                    uniqueid_json = json.dumps(movie_data.get('uniqueid', {}))
                    tags_json = json.dumps(movie_data.get('tag', []))

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
            except Exception as e:
                conn.rollback()
                utils.log(f"Error storing heavy metadata batch: {str(e)}", "ERROR")
                raise

    def get_heavy_meta_by_movieids(self, movieids: List[int], refresh: bool = False):
        """Get heavy metadata for multiple movie IDs with caching (delegated to DAO)."""
        return self._listing.get_heavy_meta_by_movieids(movieids, refresh)

    def get_imdb_export_stats(self) -> Dict[str, Any]:
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
        if not movies:
            return
        utils.log(f"=== INSERTING {len(movies)} MOVIES INTO IMDB_EXPORTS ===", "INFO")
        sql = "INSERT OR REPLACE INTO imdb_exports (kodi_id, imdb_id, title, year) VALUES (?, ?, ?, ?)"
        data = [(m.get('kodi_id'), m.get('imdb_id', ''), m.get('title', ''), m.get('year', 0)) for m in movies]
        if data:
            self.executemany_write(sql, data)
            utils.log(f"Successfully inserted {len(movies)} movies into imdb_exports", "INFO")

    def ensure_system_lists(self):
        """Ensure reserved system lists exist (IDs 1 and 2)."""
        # ID 1: Kodi Favorites
        existing = self.fetch_list_by_id(1)
        if not existing:
            utils.log("Creating reserved Kodi Favorites list with ID 1", "DEBUG")
            self.execute_write(
                "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
                (1, "Kodi Favorites", None, 1)
            )
        elif existing['name'] != "Kodi Favorites":
            utils.log(f"Updating list ID 1 to be Kodi Favorites (was: {existing['name']})", "DEBUG")
            self.execute_write(
                "UPDATE lists SET name=?, folder_id=NULL, protected=1 WHERE id=?",
                ("Kodi Favorites", 1)
            )

        # ID 2: Shortlist Imports
        existing = self.fetch_list_by_id(2)
        if not existing:
            utils.log("Creating reserved Shortlist Imports list with ID 2", "DEBUG")
            self.execute_write(
                "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
                (2, "Shortlist Imports", None, 1)
            )
        elif existing['name'] != "Shortlist Imports":
            utils.log(f"Updating list ID 2 to be Shortlist Imports (was: {existing['name']})", "DEBUG")
            self.execute_write(
                "UPDATE lists SET name=?, folder_id=NULL, protected=1 WHERE id=?",
                ("Shortlist Imports", 2)
            )

    def get_valid_imdb_numbers(self) -> List[str]:
        query = """
            SELECT imdb_id
            FROM imdb_exports
            WHERE imdb_id IS NOT NULL
              AND imdb_id != ''
              AND imdb_id LIKE 'tt%'
            ORDER BY imdb_id
        """
        results = self.execute_query(query, fetch_all=True)
        return [r['imdb_id'] for r in results]

    def sync_movies(self, movies: List[Dict[str, Any]]) -> None:
        """Reference-only policy: clear any legacy 'lib' rows."""
        self.execute_write("DELETE FROM media_items WHERE source = 'lib'")

    def insert_media_item_and_add_to_list(self, list_id: int, media_item_data: Dict[str, Any]) -> bool:
        """Insert media item and add to list in one transaction (DB only)."""
        try:
            with self.transaction() as conn:
                kodi_id = media_item_data.get('kodi_id', 0)
                play = media_item_data.get('play', '')

                existing = conn.execute(
                    "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
                    (kodi_id, play)
                ).fetchone()

                if existing:
                    media_id = existing[0]
                    utils.log(f"Found existing media item with ID: {media_id}", "DEBUG")
                else:
                    cols = list(media_item_data.keys())
                    placeholders = ', '.join('?' for _ in cols)
                    sql = f"INSERT OR IGNORE INTO media_items ({', '.join(cols)}) VALUES ({placeholders})"
                    cur = conn.execute(sql, tuple(media_item_data.values()))
                    media_id = cur.lastrowid
                    if not media_id:
                        found = conn.execute(
                            "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
                            (kodi_id, play)
                        ).fetchone()
                        if not found:
                            utils.log("Failed to get media item ID after insert", "ERROR")
                            return False
                        media_id = found[0]
                    utils.log(f"Created new media item with ID: {media_id}", "DEBUG")

                existing_li = conn.execute(
                    "SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?",
                    (list_id, media_id)
                ).fetchone()
                if not existing_li:
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

    def sync_store_media_item_to_list(self, list_id: int, media_item_data: Dict[str, Any]) -> bool:
        """Store media item and add to list for sync operations (DB only)."""
        try:
            with self.transaction() as conn:
                path = media_item_data.get('path', '')
                source = media_item_data.get('source', '')

                existing = conn.execute(
                    "SELECT id FROM media_items WHERE path = ? AND source = ?",
                    (path, source)
                ).fetchone()

                if existing:
                    media_id = existing[0]
                    utils.log(f"SYNC_STORE: Found existing media item with ID: {media_id}", "DEBUG")
                else:
                    cols = list(media_item_data.keys())
                    placeholders = ', '.join('?' for _ in cols)
                    sql = f"INSERT INTO media_items ({', '.join(cols)}) VALUES ({placeholders})"
                    cur = conn.execute(sql, tuple(media_item_data.values()))
                    media_id = cur.lastrowid
                    if not media_id:
                        utils.log("SYNC_STORE: Failed to get media item ID after insert", "ERROR")
                        return False
                    utils.log(f"SYNC_STORE: Created new media item with ID: {media_id}", "DEBUG")

                existing_li = conn.execute(
                    "SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?",
                    (list_id, media_id)
                ).fetchone()
                if not existing_li:
                    search_score = media_item_data.get('search_score', 0)
                    conn.execute(
                        "INSERT INTO list_items (list_id, media_item_id, search_score) VALUES (?, ?, ?)",
                        (list_id, media_id, search_score)
                    )
                    utils.log(f"SYNC_STORE: Added media item {media_id} to list {list_id}", "DEBUG")
                else:
                    utils.log(f"SYNC_STORE: Media item {media_id} already in list {list_id}", "DEBUG")
            return True
        except Exception as e:
            utils.log(f"SYNC_STORE: Error storing media item: {str(e)}", "ERROR")
            return False

    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                utils.log("QueryManager: Database connection closed", "DEBUG")

    def __del__(self):
        """Clean up connections when the instance is destroyed."""
        self.close()

    # -------------------------
    # DAO Delegation (Canonical)
    # -------------------------
    # FOLDERS
    def get_folders(self, parent_id: Optional[int] = None):
        return self._listing.get_folders(parent_id)

    def fetch_folders(self, parent_id: Optional[int] = None):
        return self._listing.get_folders(parent_id)

    def fetch_folders_direct(self, parent_id: Optional[int] = None):
        return self._listing.fetch_folders_direct(parent_id)

    def insert_folder_direct(self, name: str, parent_id: Optional[int]):
        return self._listing.insert_folder_direct(name, parent_id)

    def update_folder_name_direct(self, folder_id: int, new_name: str):
        return self._listing.update_folder_name_direct(folder_id, new_name)

    def get_folder_depth(self, folder_id: int):
        return self._listing.get_folder_depth(folder_id)

    def get_folder_by_name(self, name: str, parent_id: Optional[int] = None):
        return self._listing.get_folder_by_name(name, parent_id)

    def get_folder_id_by_name(self, name: str, parent_id: Optional[int] = None):
        return self._listing.get_folder_id_by_name(name, parent_id)

    def insert_folder(self, name: str, parent_id: Optional[int]):
        return self._listing.insert_folder(name, parent_id)

    def create_folder(self, name: str, parent_id: Optional[int]):
        return self._listing.create_folder(name, parent_id)

    def update_folder_name(self, folder_id: int, new_name: str):
        return self._listing.update_folder_name(folder_id, new_name)

    def get_folder_media_count(self, folder_id: int):
        return self._listing.get_folder_media_count(folder_id)

    def fetch_folder_by_id(self, folder_id: int):
        return self._listing.fetch_folder_by_id(folder_id)

    def update_folder_parent(self, folder_id: int, new_parent_id: Optional[int]):
        return self._listing.update_folder_parent(folder_id, new_parent_id)

    def fetch_folders_with_item_status(self, parent_id: Optional[int], media_item_id: int):
        return self._listing.fetch_folders_with_item_status(parent_id, media_item_id)

    def fetch_all_folders(self):
        return self._listing.fetch_all_folders()

    def delete_folder_and_contents(self, folder_id: int):
        return self._listing.delete_folder_and_contents(folder_id)

    # LISTS
    def get_lists(self, folder_id: Optional[int] = None):
        return self._listing.get_lists(folder_id)

    def fetch_lists(self, folder_id: Optional[int] = None):
        return self._listing.get_lists(folder_id)

    def fetch_lists_direct(self, folder_id: Optional[int] = None):
        return self._listing.fetch_lists_direct(folder_id)

    def get_list_items(self, list_id: int):
        return self._listing.get_list_items(list_id)

    def get_list_media_count(self, list_id: int):
        return self._listing.get_list_media_count(list_id)

    def fetch_lists_with_item_status(self, folder_id: Optional[int], media_item_id: int):
        return self._listing.fetch_lists_with_item_status(folder_id, media_item_id)

    def fetch_all_lists_with_item_status(self, media_item_id: int):
        return self._listing.fetch_all_lists_with_item_status(media_item_id)

    def update_list_folder(self, list_id: int, folder_id: Optional[int]):
        return self._listing.update_list_folder(list_id, folder_id)

    def get_list_id_by_name(self, name: str, folder_id: Optional[int] = None):
        return self._listing.get_list_id_by_name(name, folder_id)

    def get_lists_for_item(self, media_item_id: int):
        return self._listing.get_lists_for_item(media_item_id)

    def get_item_id_by_title_and_list(self, title: str, list_id: int):
        return self._listing.get_item_id_by_title_and_list(title, list_id)

    def create_list(self, name: str, folder_id: Optional[int] = None):
        return self._listing.create_list(name, folder_id)

    def get_unique_list_name(self, base_name: str, folder_id: Optional[int] = None):
        return self._listing.get_unique_list_name(base_name, folder_id)

    def fetch_all_lists(self):
        return self._listing.fetch_all_lists()

    def fetch_list_by_id(self, list_id: int):
        return self._listing.fetch_list_by_id(list_id)

    def remove_media_item_from_list(self, list_id: int, media_item_id: int):
        return self._listing.remove_media_item_from_list(list_id, media_item_id)

    def get_list_item_by_media_id(self, list_id: int, media_item_id: int):
        return self._listing.get_list_item_by_media_id(list_id, media_item_id)

    def fetch_list_items_with_details(self, list_id: int):
        return self._listing.fetch_list_items_with_details(list_id)

    def delete_list_and_contents(self, list_id: int):
        return self._listing.delete_list_and_contents(list_id)

    # Convenience alias preserved for backward compatibility
    def get_list_media_items(self, list_id: int) -> List[Dict]:
        return self.fetch_list_items_with_details(list_id)

    def is_reserved_list_id(self, list_id: int) -> bool:
        """Check if a list ID is reserved for system lists"""
        return list_id in [1, 2]  # IDs 1 and 2 are reserved for system lists

    def move_list_to_folder(self, list_id: int, target_folder_id: Optional[int]) -> bool:
        """Move a list to a different folder"""
        try:
            self.execute_write('UPDATE lists SET folder_id = ? WHERE id = ?', (target_folder_id, int(list_id)))
            return True
        except Exception as e:
            utils.log(f"Error moving list {list_id} to folder {target_folder_id}: {str(e)}", "ERROR")
            return False

    def ensure_kodi_favorites_list(self) -> Dict:
        """Ensure 'Kodi Favorites' list exists with ID 1"""
        existing = self.fetch_list_by_id(1)
        if existing:
            return existing
        
        # Create the list with specific ID
        self.execute_write(
            "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
            (1, "Kodi Favorites", None, 1)
        )
        return {'id': 1, 'name': "Kodi Favorites", 'folder_id': None, 'protected': 1}

    def ensure_shortlist_imports_list(self) -> Dict:
        """Ensure 'Shortlist Imports' list exists with ID 2"""
        existing = self.fetch_list_by_id(2)
        if existing:
            return existing
        
        # Create the list with specific ID
        self.execute_write(
            "INSERT INTO lists (id, name, folder_id, protected) VALUES (?, ?, ?, ?)",
            (2, "Shortlist Imports", None, 1)
        )
        return {'id': 2, 'name': "Shortlist Imports", 'folder_id': None, 'protected': 1}

    def update_data(self, table: str, data: Dict[str, Any], where_clause: str, params: Tuple) -> bool:
        """Update data in a table with validation"""
        if not self._validate_table_exists(table):
            utils.log(f"Invalid or non-existent table: {table}", "ERROR")
            return False
        
        # Validate columns exist
        for column in data.keys():
            if not self._validate_column_exists(table, column):
                utils.log(f"Invalid column {column} for table {table}", "ERROR")
                return False
        
        try:
            # Build SET clause
            set_clause = ', '.join([f"{col} = ?" for col in data.keys()])
            sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            
            # Combine data values with where parameters
            all_params = tuple(data.values()) + params
            
            self.execute_write(sql, all_params)
            return True
        except Exception as e:
            utils.log(f"Error updating {table}: {str(e)}", "ERROR")
            return False
