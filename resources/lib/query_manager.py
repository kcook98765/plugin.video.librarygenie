import sqlite3
import time
import json
from typing import List, Dict, Any, Optional
from resources.lib import utils
from resources.lib.singleton_base import Singleton
from resources.lib.config_manager import Config

class QueryManager(Singleton):
    def __init__(self, db_path: str):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self.pool_size = 5
            self._connection_pool = []
            self._initialize_pool()
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

    def fetch_folders_direct(self, parent_id=None):
        """Direct folder fetch without going through DatabaseManager"""
        query = """
            SELECT 
                id,
                name,
                parent_id
            FROM folders
            WHERE parent_id IS ?
            ORDER BY name COLLATE NOCASE
        """
        return self.execute_query(query, (parent_id,))

    def fetch_lists_direct(self, folder_id=None):
        """Direct lists fetch without going through DatabaseManager"""
        query = """
            SELECT 
                id,
                name,
                folder_id
            FROM lists
            WHERE folder_id IS ?
            ORDER BY name COLLATE NOCASE
        """
        return self.execute_query(query, (folder_id,))

    def insert_folder_direct(self, name, parent_id=None):
        """Direct folder insertion"""
        query = """
            INSERT INTO folders (name, parent_id)
            VALUES (?, ?)
        """
        return self.execute_query(query, (name, parent_id))

    def update_folder_name_direct(self, folder_id, new_name):
        """Direct folder name update"""
        query = """
            UPDATE folders 
            SET name = ? 
            WHERE id = ?
        """
        self.execute_query(query, (new_name, folder_id))



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
        conn_info = self._get_connection()
        try:
            query = """
                INSERT INTO original_requests (description, response_json)
                VALUES (?, ?)
            """
            cursor = conn_info['connection'].execute(query, (description, json.dumps(response_data)))
            conn_info['connection'].commit()
            return cursor.lastrowid
        finally:
            self._release_connection(conn_info)

    def get_media_by_dbid(self, db_id: int, media_type: str = 'movie') -> Dict[str, Any]:
        """Get media details by database ID"""
        query = """
            SELECT *
            FROM media_items
            WHERE kodi_id = ? AND type = ?
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

    # Predefined queries
    def get_folders(self, parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if parent_id is None:
            query = """
                SELECT id, name, parent_id
                FROM folders
                WHERE parent_id IS NULL
                ORDER BY name COLLATE NOCASE
            """
            return self.execute_query(query)
        else:
            query = """
                SELECT id, name, parent_id
                FROM folders
                WHERE parent_id = ?
                ORDER BY name COLLATE NOCASE
            """
            return self.execute_query(query, (parent_id,))

    def get_lists(self, folder_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT id, name, folder_id
            FROM lists
            WHERE folder_id IS ?
            ORDER BY name COLLATE NOCASE
        """
        return self.execute_query(query, (folder_id,))

    def get_list_items(self, list_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT m.*, li.id as list_item_id
            FROM list_items li
            JOIN media_items m ON li.media_item_id = m.id
            WHERE li.list_id = ?
        """
        return self.execute_query(query, (list_id,))



    def get_list_media_count(self, list_id: int) -> int:
        query = """
            SELECT COUNT(*)
            FROM list_items
            WHERE list_id = ?
        """
        result = self.execute_query(query, (list_id,), fetch_all=False)
        return result[0]['COUNT(*)'] if result else 0

    def fetch_list_items_with_details(self, list_id: int) -> List[Dict[str, Any]]:
        """Fetch list items with full media details"""
        query = """
            SELECT mi.*
            FROM list_items li
            JOIN media_items mi ON li.media_item_id = mi.id
            WHERE li.list_id = ?
            ORDER BY mi.title COLLATE NOCASE
        """

        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, (list_id,))
            rows = cursor.fetchall()
            items = [dict(row) for row in rows]
            utils.log(f"Fetched {len(items)} items for list {list_id}", "DEBUG")

            # Log database fetch summary
            utils.log(f"Fetched {len(items)} items from database", "DEBUG")

            return items
        finally:
            self._release_connection(conn_info)

    def fetch_lists_with_item_status(self, item_id: int) -> List[Dict[str, Any]]:
        """Fetch lists with item status"""
        query = """
            SELECT 
                lists.id, 
                lists.name,
                lists.folder_id,
                CASE 
                    WHEN list_items.media_item_id IS NOT NULL THEN 1
                    ELSE 0
                END AS is_member
            FROM lists
            LEFT JOIN list_items ON lists.id = list_items.list_id AND list_items.media_item_id IN (
                SELECT id FROM media_items WHERE kodi_id = ?
            )
            ORDER BY lists.folder_id, lists.name COLLATE NOCASE
        """
        return self.execute_query(query, (item_id,))

    def remove_media_item_from_list(self, list_id: int, media_item_id: int) -> None:
        query = """
            DELETE FROM list_items
            WHERE list_id = ? AND media_item_id = ?
        """
        self.execute_query(query, (list_id, media_item_id))

    def get_folder_depth(self, folder_id: int) -> int:
        if folder_id is None:
            return -1  # Root level is -1 so first level will be 0

        query = """
            WITH RECURSIVE parent_chain AS (
                SELECT id, parent_id, 0 as depth
                FROM folders WHERE id = ?
                UNION ALL
                SELECT f.id, f.parent_id, pc.depth + 1
                FROM folders f
                JOIN parent_chain pc ON f.id = pc.parent_id
            )
            SELECT MAX(depth) as max_depth FROM parent_chain
        """
        result = self.execute_query(query, (folder_id,), fetch_all=False)
        return result[0]['max_depth'] if result and result[0]['max_depth'] is not None else 0

    def get_folder_by_name(self, folder_name: str) -> Optional[Dict[str, Any]]:
        """Get folder by name"""
        query = "SELECT id, name, parent_id FROM folders WHERE name = ?"
        result = self.execute_query(query, (folder_name,))
        return result[0] if result else None

    def get_folder_id_by_name(self, folder_name: str) -> Optional[int]:
        """Get folder ID by name"""
        query = "SELECT id FROM folders WHERE name = ?"
        result = self.execute_query(query, (folder_name,))
        return result[0]['id'] if result else None

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
            from resources.lib import utils
            utils.log(f"Error checking if list is search history: {str(e)}", "ERROR")
            return False

    def insert_folder(self, name: str, parent_id: Optional[int] = None) -> int:
        query = """
            INSERT INTO folders (name, parent_id)
            VALUES (?, ?)
        """
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            cursor.execute(query, (name, parent_id))
            conn_info['connection'].commit()
            return cursor.lastrowid
        finally:
            self._release_connection(conn_info)

    def update_folder_name(self, folder_id: int, new_name: str) -> None:
        query = """
            UPDATE folders 
            SET name = ? 
            WHERE id = ?
        """
        self.execute_query(query, (new_name, folder_id))

    def get_folder_media_count(self, folder_id: int) -> int:
        query = """
            WITH RECURSIVE folder_tree AS (
                SELECT id FROM folders WHERE id = ?
                UNION ALL
                SELECT f.id FROM folders f
                JOIN folder_tree ft ON f.parent_id = ft.id
            )
            SELECT COUNT(*)
            FROM list_items li
            JOIN lists l ON li.list_id = l.id
            WHERE l.folder_id IN (SELECT id FROM folder_tree)
        """
        result = self.execute_query(query, (folder_id,), fetch_all=False)
        return result[0]['COUNT(*)'] if result else 0

    def fetch_all_lists_with_item_status(self, item_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                lists.id, 
                lists.name,
                lists.folder_id,
                CASE 
                    WHEN list_items.media_item_id IS NOT NULL THEN 1
                    ELSE 0
                END AS is_member
            FROM lists
            LEFT JOIN list_items ON lists.id = list_items.list_id 
            AND list_items.media_item_id IN (
                SELECT id FROM media_items WHERE kodi_id = ?
            )
            ORDER BY lists.folder_id, lists.name COLLATE NOCASE
        """
        return self.execute_query(query, (item_id,))

    def fetch_folder_by_id(self, folder_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, name, parent_id 
            FROM folders 
            WHERE id = ?
        """
        result = self.execute_query(query, (folder_id,), fetch_all=False)
        return result[0] if result else None

    def update_list_folder(self, list_id: int, folder_id: Optional[int]) -> None:
        query = """
            UPDATE lists
            SET folder_id = ?
            WHERE id = ?
        """
        self.execute_query(query, (folder_id, list_id))

    def get_list_id_by_name(self, list_name: str) -> Optional[int]:
        query = """
            SELECT id 
            FROM lists 
            WHERE name = ?
        """
        result = self.execute_query(query, (list_name,), fetch_all=False)
        return result[0]['id'] if result else None

    def get_lists_for_item(self, item_id: int) -> List[str]:
        query = """
            SELECT lists.name
            FROM list_items
            JOIN lists ON list_items.list_id = lists.id
            JOIN media_items ON list_items.media_item_id = media_items.id
            WHERE media_items.kodi_id = ?
        """
        results = self.execute_query(query, (item_id,))
        return [result['name'] for result in results]

    def get_item_id_by_title_and_list(self, list_id: int, title: str) -> Optional[int]:
        query = """
            SELECT list_items.id
            FROM list_items
            JOIN media_items ON list_items.media_item_id = media_items.id
            WHERE list_items.list_id = ? AND media_items.title = ?
        """
        result = self.execute_query(query, (list_id, title), fetch_all=False)
        return result[0]['id'] if result else None

    def delete_list_and_contents(self, list_id: int) -> None:
        queries = [
            "DELETE FROM list_items WHERE list_id = ?",
            "DELETE FROM lists WHERE id = ?"
        ]
        for query in queries:
            self.execute_query(query, (list_id,))

    def fetch_all_lists(self) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                id,
                name,
                folder_id
            FROM lists
            ORDER BY folder_id, name COLLATE NOCASE
        """
        return self.execute_query(query)

    def fetch_list_by_id(self, list_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single list by its ID"""
        query = """
            SELECT id, name, folder_id
            FROM lists
            WHERE id = ?
        """
        result = self.execute_query(query, (list_id,), fetch_all=False)
        return result[0] if result else None

    def update_folder_parent(self, folder_id: int, new_parent_id: Optional[int]) -> None:
        conn_info = self._get_connection()
        try:
            # Get current state
            cursor = conn_info['connection'].cursor()
            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            # Convert string 'None' to Python None
            if isinstance(new_parent_id, str) and new_parent_id == 'None':
                new_parent_id = None

            # Construct query based on new parent
            if new_parent_id is None:
                query = """
                    UPDATE folders 
                    SET parent_id = NULL 
                    WHERE id = ?
                """
                params = (folder_id,)
            else:
                query = """
                    UPDATE folders 
                    SET parent_id = ? 
                    WHERE id = ?
                """
                params = (new_parent_id, folder_id)

            cursor.execute(query, params)

            # Commit the change
            conn_info['connection'].commit()

            # Verify the update
            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            after_state = cursor.fetchone()

            # Validate result
            expected_parent = new_parent_id if new_parent_id is not None else None
            actual_parent = after_state['parent_id']

            if actual_parent != expected_parent:
                utils.log(f"WARNING: Parent ID mismatch - Expected:{expected_parent}, Got:{actual_parent}", "WARNING")
        finally:
            self._release_connection(conn_info)

    def get_subtree_depth(self, folder_id: int) -> int:
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
        result = self.execute_query(query, (folder_id,), fetch_all=False)
        return result[0]['MAX(depth)'] if result and result[0]['MAX(depth)'] is not None else 0

    def delete_folder_and_contents(self, folder_id: int) -> None:
        queries = [
            """WITH RECURSIVE nested_folders AS (
                SELECT id FROM folders WHERE id = ?
                UNION ALL
                SELECT f.id FROM folders f
                JOIN nested_folders nf ON f.parent_id = nf.id
            )
            DELETE FROM lists WHERE folder_id IN (SELECT id FROM nested_folders)""",
            """WITH RECURSIVE nested_folders AS (
                SELECT id FROM folders WHERE id = ?
                UNION ALL
                SELECT f.id FROM folders f
                JOIN nested_folders nf ON f.parent_id = nf.id
            )
            DELETE FROM folders WHERE id IN (SELECT id FROM nested_folders)"""
        ]
        for query in queries:
            self.execute_query(query, (folder_id,))

    def fetch_folders_with_item_status(self, item_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                folders.id,
                folders.name,
                folders.parent_id,
                CASE 
                    WHEN list_items.media_item_id IS NOT NULL THEN 1
                    ELSE 0
                END AS is_member
            FROM folders
            LEFT JOIN lists ON folders.id = lists.folder_id
            LEFT JOIN list_items ON lists.id = list_items.list_id AND list_items.media_item_id IN (
                SELECT id FROM media_items WHERE kodi_id = ?
            )
            ORDER BY folders.name COLLATE NOCASE
        """
        return self.execute_query(query, (item_id,))

    def fetch_all_folders(self) -> List[Dict[str, Any]]:
        """Fetch all folders"""
        query = """
            SELECT 
                id,
                name,
                parent_id
            FROM folders
            ORDER BY name COLLATE NOCASE
        """
        return self.execute_query(query)

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
            self.execute_query(
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
        """
        self.execute_query("DELETE FROM media_items WHERE source = 'lib'")

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
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            cursor.execute(query, (description, response_json))
            conn_info['connection'].commit()
            return cursor.lastrowid
        finally:
            self._release_connection(conn_info)

    def insert_parsed_movie(self, request_id: int, title: str, year: Optional[int], director: Optional[str]) -> None:
        """Insert a parsed movie record"""
        query = """
            INSERT INTO parsed_movies (request_id, title, year, director)
            VALUES (?, ?, ?, ?)
        """
        self.execute_query(query, (request_id, title, year, director))

    def insert_media_item(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert a media item and return its ID"""
        # Extract field names from config
        field_names = [field.split()[0] for field in Config.FIELDS]
        media_data = {key: data[key] for key in field_names if key in data}

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

        # Insert media item
        columns = ', '.join(media_data.keys())
        placeholders = ', '.join('?' for _ in media_data)
        query = f'INSERT OR IGNORE INTO media_items ({columns}) VALUES ({placeholders})'

        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].cursor()
            cursor.execute(query, tuple(media_data.values()))
            conn_info['connection'].commit()

            # Get the media item ID
            cursor.execute(
                "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
                (media_data['kodi_id'], media_data['play'])
            )
            result = cursor.fetchone()
            return result[0] if result else None
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

    def insert_list_item(self, data: Dict[str, Any]) -> None:
        """Insert a list item"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        query = f'INSERT INTO list_items ({columns}) VALUES ({placeholders})'
        self.execute_query(query, tuple(data.values()))

    def insert_generic(self, table: str, data: Dict[str, Any]) -> None:
        """Generic table insert"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
        self.execute_query(query, tuple(data.values()))

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

    def get_media_details(self, media_id: int, media_type: str = 'movie') -> dict:
        """Get media details from database"""
        query = """
            SELECT *
            FROM media_items
            WHERE kodi_id = ? AND media_type = ?
        """
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, (media_id, media_type))
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