import sqlite3
import time
import json
from typing import List, Dict, Any, Optional
from resources.lib.utils import utils
from resources.lib.utils.singleton_base import Singleton
from resources.lib.config.config_manager import Config

class QueryManager(Singleton):
    def __init__(self, db_path: str):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self.pool_size = 5
            self._connection_pool = []
            self._initialize_pool()
            
            # Initialize DAO with query and write executors
            from resources.lib.data.dao.listing_dao import ListingDAO
            self._listing = ListingDAO(self.execute_query, self.execute_write)
            
            self._initialized = True

    def _initialize_pool(self):
        """Initialize the connection pool"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys = ON')
            self._connection_pool.append({'connection': conn, 'in_use': False})

    def _get_connection(self):
        """Get an available connection from the pool"""
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            for conn_info in self._connection_pool:
                if not conn_info['in_use']:
                    conn_info['in_use'] = True
                    return conn_info

            time.sleep(0.1)
            retry_count += 1

        raise Exception("No available connections in the pool")

    def _release_connection(self, conn_info):
        """Release a connection back to the pool"""
        conn_info['in_use'] = False

    # =========================
    # FOLDER DELEGATION METHODS
    # =========================
    
    def get_folders(self, parent_id=None):
        return self._listing.get_folders(parent_id)
    
    def fetch_folders_direct(self, parent_id=None):
        return self._listing.fetch_folders_direct(parent_id)
    
    def insert_folder_direct(self, name, parent_id):
        return self._listing.insert_folder_direct(name, parent_id)
    
    def update_folder_name_direct(self, folder_id, new_name):
        return self._listing.update_folder_name_direct(folder_id, new_name)
    
    def get_folder_depth(self, folder_id):
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
    
    def delete_folder_and_contents(self, folder_id):
        """Delete folder and all its contents in a single transaction"""
        conn_info = self._get_connection()
        try:
            # Begin transaction
            conn_info['connection'].execute('BEGIN')
            
            # Perform the recursive deletion via DAO
            result = self._listing.delete_folder_and_contents(folder_id)
            
            # Commit transaction
            conn_info['connection'].commit()
            return result
            
        except Exception as e:
            # Rollback on any error
            conn_info['connection'].rollback()
            utils.log(f"Transaction rolled back during folder deletion: {str(e)}", "ERROR")
            raise
        finally:
            self._release_connection(conn_info)
    
    def fetch_folders_with_item_status(self, parent_id, media_item_id):
        return self._listing.fetch_folders_with_item_status(parent_id, media_item_id)
    
    def fetch_all_folders(self):
        return self._listing.fetch_all_folders()

    # =========================
    # LIST DELEGATION METHODS
    # =========================
    
    def get_lists(self, folder_id=None):
        return self._listing.get_lists(folder_id)
    
    def fetch_lists_direct(self, folder_id=None):
        return self._listing.fetch_lists_direct(folder_id)
    
    def get_list_items(self, list_id):
        return self._listing.get_list_items(list_id)
    
    def fetch_list_items_with_details(self, list_id):
        return self._listing.fetch_list_items_with_details(list_id)
    
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
        return self._listing.delete_list_and_contents(list_id)
    
    def fetch_all_lists(self):
        return self._listing.fetch_all_lists()
    
    def fetch_list_by_id(self, list_id):
        return self._listing.fetch_list_by_id(list_id)
    
    def remove_media_item_from_list(self, list_id, media_item_id):
        return self._listing.remove_media_item_from_list(list_id, media_item_id)
    
    def execute_rpc_query(self, rpc):
        """Execute RPC query and return results"""
        conn_info = self._get_connection()
        try:
            query = """
                SELECT *
                FROM media_items
                WHERE id IN (
                    SELECT media_item_id 
                    FROM list_items 
                    WHERE list_id = ?
                )
            """
            cursor = conn_info['connection'].execute(query, (rpc.get('list_id'),))
            results = cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            self._release_connection(conn_info)

    def save_llm_response(self, description, response_data):
        """Save LLM API response"""
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        result = self.execute_write(query, (description, json.dumps(response_data)))
        return result['lastrowid']

    def get_media_by_dbid(self, db_id: int, media_type: str = 'movie') -> Dict[str, Any]:
        """Get media details by database ID"""
        query = """
            SELECT *
            FROM media_items
            WHERE kodi_id = ? AND media_type = ?
        """
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, (db_id, media_type))
            result = cursor.fetchone()
            return dict(result) if result else {}
        finally:
            self._release_connection(conn_info)

    def get_show_episode_details(self, show_id: int, season: int, episode: int) -> Dict[str, Any]:
        """Get TV show episode details"""
        query = """
            SELECT *
            FROM media_items
            WHERE show_id = ? AND season = ? AND episode = ?
        """
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, (show_id, season, episode))
            result = cursor.fetchone()
            return dict(result) if result else {}
        finally:
            self._release_connection(conn_info)

    def get_search_results(self, title: str, year: Optional[int] = None, director: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get search results from media_items table"""
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

        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, tuple(params))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self._release_connection(conn_info)

    def execute_query(self, query: str, params: tuple = (), fetch_all: bool = True) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            cursor.execute(query, params)

            if fetch_all:
                results = cursor.fetchall()
            else:
                results = cursor.fetchone()

            conn_info['connection'].commit()

            if results:
                if fetch_all:
                    return [dict(row) for row in results]
                else:
                    return [dict(results)]
            return []
        except Exception as e:
            utils.log(f"Query execution error: {str(e)}", "ERROR")
            raise
        finally:
            self._release_connection(conn_info)

    def execute_write(self, sql: str, params: tuple = ()) -> Dict[str, int]:
        """Execute a write operation (INSERT/UPDATE/DELETE) and return metadata"""
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            cursor.execute(sql, params)
            conn_info['connection'].commit()
            
            return {
                'lastrowid': cursor.lastrowid or 0,
                'rowcount': cursor.rowcount or 0
            }
        except Exception as e:
            utils.log(f"Write execution error: {str(e)}", "ERROR")
            raise
        finally:
            self._release_connection(conn_info)

    



    

    

    def is_search_history(self, list_id):
        """Check if a list is in the Search History folder"""
        try:
            # Get the list data
            list_data = self.fetch_list_by_id(list_id)
            if not list_data:
                return False

            # Get the Search History folder ID
            search_history_folder_id = self.get_folder_id_by_name("Search History")
            if not search_history_folder_id:
                return False

            # Check if the list's folder_id matches the Search History folder
            return list_data.get('folder_id') == search_history_folder_id
        except Exception as e:
            utils.log(f"Error checking if list is search history: {str(e)}", "ERROR")
            return False

    def ensure_search_history_folder(self):
        return self._listing.ensure_search_history_folder()

    

    def insert_media_item_and_add_to_list(self, list_id: int, media_data: Dict[str, Any]) -> bool:
        """Insert a media item and add it to a list in one operation"""
        try:
            utils.log(f"=== INSERT_MEDIA_ITEM_AND_ADD_TO_LIST: Starting for list_id {list_id} ===", "DEBUG")

            # Insert the media item
            media_item_id = self.insert_media_item(media_data)
            if not media_item_id:
                utils.log("=== INSERT_MEDIA_ITEM_AND_ADD_TO_LIST: Failed to insert media item ===", "ERROR")
                return False

            utils.log(f"=== INSERT_MEDIA_ITEM_AND_ADD_TO_LIST: Inserted media item with ID: {media_item_id} ===", "DEBUG")

            # Add to the list using DAO
            self._listing.insert_list_item(list_id, media_item_id)
            utils.log(f"=== INSERT_MEDIA_ITEM_AND_ADD_TO_LIST: Added media item {media_item_id} to list {list_id} ===", "DEBUG")

            return True

        except Exception as e:
            utils.log(f"=== INSERT_MEDIA_ITEM_AND_ADD_TO_LIST: Error: {str(e)} ===", "ERROR")
            return False

    

    def get_imdb_export_stats(self) -> Dict[str, Any]:
        """Get statistics about IMDB numbers in exports"""
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%' THEN 1 ELSE 0 END) as valid_imdb
            FROM imdb_exports
        """
        result = self.execute_query(query, fetch_all=False)
        total = result[0]['total'] if result else 0
        valid_imdb = result[0]['valid_imdb'] if result else 0
        return {
            'total': total,
            'valid_imdb': valid_imdb,
            'percentage': (valid_imdb / total * 100) if total > 0 else 0
        }

    def insert_imdb_export(self, movies: List[Dict[str, Any]]) -> None:
        """Insert multiple movies into imdb_exports table"""
        query = """
            INSERT OR REPLACE INTO imdb_exports 
            (kodi_id, imdb_id, title, year)
            VALUES (?, ?, ?, ?)
        """
        for movie in movies:
            self.execute_write(
                query,
                (
                    movie.get('movieid') or movie.get('kodi_id'), 
                    movie.get('imdbnumber'),
                    movie.get('title'),
                    movie.get('year')
                )
            )

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
        results = self.execute_query(query)
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
        for conn_info in self._connection_pool:
            try:
                conn_info['connection'].close()
            except sqlite3.Error:
                pass  # Ignore errors during cleanup

    def insert_original_request(self, description: str, response_json: str) -> int:
        """Insert an original request and return its ID"""
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        result = self.execute_write(query, (description, response_json))
        return result['lastrowid']

    def insert_parsed_movie(self, request_id: int, title: str, year: Optional[int], director: Optional[str]) -> int:
        """Insert a parsed movie record"""
        query = """
            INSERT INTO parsed_movies (request_id, title, year, director)
            VALUES (?, ?, ?, ?)
        """
        result = self.execute_write(query, (request_id, title, year, director))
        return result['lastrowid']

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
        media_data.setdefault('source', 'unknown')
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

        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            cursor.execute(query, tuple(media_data.values()))
            conn_info['connection'].commit()

            inserted_id = cursor.lastrowid
            if inserted_id and inserted_id > 0:
                utils.log(f"Successfully inserted media item with ID: {inserted_id} for source: {source}", "DEBUG")
                return inserted_id

            # If lastrowid is None/0, try to find the record by unique fields
            if source == 'shortlist_import':
                # For shortlist imports, look up by title, year, and play path
                title = media_data.get('title', '')
                year = media_data.get('year', 0)
                play = media_data.get('play', '')

                cursor.execute(
                    "SELECT id FROM media_items WHERE title = ? AND year = ? AND play = ? AND source = ?",
                    (title, year, play, source)
                )
                result = cursor.fetchone()
                if result:
                    utils.log(f"Found existing shortlist import record with ID: {result[0]}", "DEBUG")
                    return result[0]

            elif source in ('search', 'lib') and media_data.get('imdbnumber'):
                # Look up by IMDb ID and source
                cursor.execute(
                    "SELECT id FROM media_items WHERE imdbnumber = ? AND source = ?",
                    (media_data.get('imdbnumber'), source)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]

            else:
                # Original lookup logic for other sources
                lookup_kodi_id = media_data.get('kodi_id', 0)
                lookup_play = media_data.get('play', '')

                cursor.execute(
                    "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
                    (lookup_kodi_id, lookup_play)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]

            utils.log(f"Could not determine inserted record ID for source: {source}", "WARNING")
            return None

        except Exception as e:
            utils.log(f"SQL Error inserting media item: {str(e)}", "ERROR")
            utils.log(f"Failed data: {media_data}", "ERROR")
            raise
        finally:
            self._release_connection(conn_info)

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
        row = self.execute_query(query, (imdb_id, imdb_id, kodi_id))
        if row:
            rec = row[0]
            try:
                return rec['id']
            except KeyError:
                utils.log("ID not found in query result", "WARNING")
                return 0

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
            (title, year, play)
        )
        if existing:
            rec = existing[0]
            try:
                return rec['id']
            except KeyError:
                utils.log("ID not found in query result", "WARNING")
                return 0
        return self.insert_media_item(payload) or 0

    def insert_list_item(self, list_id, media_item_id):
        """Insert a list item - delegate to DAO"""
        return self._listing.insert_list_item(list_id, media_item_id)

    def insert_generic(self, table: str, data: Dict[str, Any]) -> int:
        """Generic table insert"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
        result = self.execute_write(query, tuple(data.values()))
        return result['lastrowid']

    def get_matched_movies(self, title: str, year: Optional[int] = None, director: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get movies matching certain criteria"""
        conditions = ["title LIKE ?"]
        params = [f"%{title}%"]

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
        results = self.execute_query(query, tuple(params))

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
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, (kodi_dbid, media_type))
            result = cursor.fetchone()
            return dict(result) if result else {}
        finally:
            self._release_connection(conn_info)

    def setup_database(self):
        """Setup all database tables"""
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
            # IMDB holding table for upload process, likely not needed, comment out for now
#            '''CREATE TABLE IF NOT EXISTS imdb_holding (
#                id INTEGER PRIMARY KEY AUTOINCREMENT,
#                kodi_id INTEGER,
#                title TEXT,
#                year INTEGER,
#                imdb_id TEXT,
#                raw_uniqueid TEXT,
#                raw_imdbnumber TEXT,
#                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#            )''',
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
                file TEXT,
                UNIQUE (kodi_id, play)
            )""",
            """CREATE TABLE IF NOT EXISTS list_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER,
                media_item_id INTEGER,
                flagged INTEGER DEFAULT 0,
                FOREIGN KEY (list_id) REFERENCES lists (id),
                FOREIGN KEY (media_item_id) REFERENCES media_items (id)
            )""",
            """CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER,
                title TEXT,
                FOREIGN KEY (list_id) REFERENCES lists (id)
            )""",
            """CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER,
                title TEXT,
                FOREIGN KEY (list_id) REFERENCES lists (id)
            )""",

            """CREATE TABLE IF NOT EXISTS original_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT,
                response_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS parsed_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                title TEXT,
                year INTEGER,
                director TEXT,
                FOREIGN KEY (request_id) REFERENCES original_requests (id)
            )"""
        ]

        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            for create_sql in table_creations:
                utils.log(f"Executing SQL: {create_sql}", "DEBUG")
                cursor.execute(create_sql)
            conn_info['connection'].commit()

            # Add migration for search_score column if it doesn't exist
            try:
                cursor.execute("SELECT search_score FROM media_items LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                utils.log("Adding search_score column to media_items table", "INFO")
                cursor.execute("ALTER TABLE media_items ADD COLUMN search_score REAL")
                conn_info['connection'].commit()

            # Add migration for file column if it doesn't exist
            try:
                cursor.execute("SELECT file FROM media_items LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                utils.log("Adding file column to media_items table", "INFO")
                cursor.execute("ALTER TABLE media_items ADD COLUMN file TEXT")
                conn_info['connection'].commit()

        finally:
            self._release_connection(conn_info)

        # Setup movies reference table as well
        self.setup_movies_reference_table()

    def setup_movies_reference_table(self):
        """Create movies_reference table and indexes"""
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()

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

            conn_info['connection'].commit()
        finally:
            self._release_connection(conn_info)