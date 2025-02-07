import sqlite3
import time
import json
from typing import List, Dict, Any, Optional
from resources.lib import utils
from resources.lib.singleton_base import Singleton

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

    def delete_genie_list_direct(self, list_id):
        """Direct genie list deletion"""
        query = "DELETE FROM genie_lists WHERE list_id = ?"
        self.execute_query(query, (list_id,))

    def remove_genielist_entries_direct(self, list_id):
        """Direct removal of genie list entries"""
        query = """
            DELETE FROM list_items
            WHERE list_id = ? AND media_item_id IN (
                SELECT id FROM media_items WHERE source = 'genielist'
            )
        """
        self.execute_query(query, (list_id,))

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
        query = """
            SELECT id, name, parent_id
            FROM folders
            WHERE parent_id IS ?
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

    def get_genie_list(self, list_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT description, rpc 
            FROM genie_lists 
            WHERE list_id = ?
        """
        result = self.execute_query(query, (list_id,), fetch_all=False)
        if result and result[0]:
            return {
                'description': result[0]['description'],
                'rpc': json.loads(result[0]['rpc']) if result[0]['rpc'] else None
            }
        return None

    def insert_genie_list(self, list_id: int, description: str, rpc: Dict[str, Any]) -> None:
        query = """
            INSERT INTO genie_lists (list_id, description, rpc)
            VALUES (?, ?, ?)
        """
        self.execute_query(query, (list_id, description, json.dumps(rpc)))

    def update_genie_list(self, list_id: int, description: str, rpc: Dict[str, Any]) -> None:
        query = """
            UPDATE genie_lists 
            SET description = ?, rpc = ? 
            WHERE list_id = ?
        """
        self.execute_query(query, (description, json.dumps(rpc), list_id))

    def get_list_media_count(self, list_id: int) -> int:
        query = """
            SELECT COUNT(*)
            FROM list_items
            WHERE list_id = ?
        """
        result = self.execute_query(query, (list_id,), fetch_all=False)
        return result[0]['COUNT(*)'] if result else 0

    def fetch_list_items_with_details(self, list_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT m.*, li.id as list_item_id, li.flagged
            FROM list_items li
            JOIN media_items m ON li.media_item_id = m.id
            WHERE li.list_id = ?
            ORDER BY m.title COLLATE NOCASE
        """
        return self.execute_query(query, (list_id,))

    def fetch_lists_with_item_status(self, item_id: int) -> List[Dict[str, Any]]:
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

    def get_folder_by_name(self, folder_name: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, name, parent_id
            FROM folders
            WHERE name = ?
        """
        result = self.execute_query(query, (folder_name,), fetch_all=False)
        return result[0] if result else None
        
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
        return self.execute_query(query, (folder_id,), fetch_all=False)

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
        return result['id'] if result else None

    def delete_list_and_contents(self, list_id: int) -> None:
        queries = [
            "DELETE FROM genie_lists WHERE list_id = ?",
            "DELETE FROM list_items WHERE list_id = ?",
            "DELETE FROM lists WHERE id = ?"
        ]
        for query in queries:
            self.execute_query(query, (list_id,))

    def fetch_all_folders(self) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                id,
                name,
                parent_id
            FROM folders
            ORDER BY parent_id, name COLLATE NOCASE
        """
        return self.execute_query(query)

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

    def update_folder_parent(self, folder_id: int, new_parent_id: Optional[int]) -> None:
        query = """
            UPDATE folders 
            SET parent_id = ? 
            WHERE id = ?
        """
        self.execute_query(query, (new_parent_id, folder_id))

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
            INSERT INTO imdb_exports 
            (kodi_id, imdb_id, title, year, filename, path)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        for movie in movies:
            file_path = movie.get('file', '')
            filename = file_path.split('/')[-1] if file_path else ''
            path = '/'.join(file_path.split('/')[:-1]) if file_path else ''
            self.execute_query(
                query,
                (
                    movie.get('movieid'), 
                    movie.get('imdbnumber'),
                    movie.get('title'),
                    movie.get('year'),
                    filename,
                    path
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
        """Sync movies with the database"""
        # First, clear existing entries
        self.execute_query("DELETE FROM media_items WHERE source = 'lib'")

        # Insert new entries
        for movie in movies:
            # Prepare movie data
            movie_data = {
                'kodi_id': movie.get('movieid', 0),
                'title': movie.get('title', ''),
                'year': movie.get('year', 0),
                'source': 'lib',
                'play': movie.get('file', ''),
                'poster': movie.get('art', {}).get('poster', ''),
                'fanart': movie.get('art', {}).get('fanart', ''),
                'plot': movie.get('plot', ''),
                'rating': float(movie.get('rating', 0)),
                'votes': int(movie.get('votes', 0)),
                'duration': int(movie.get('runtime', 0)),
                'mpaa': movie.get('mpaa', ''),
                'genre': ','.join(movie.get('genre', [])),
                'director': ','.join(movie.get('director', [])),
                'studio': ','.join(movie.get('studio', [])),
                'country': ','.join(movie.get('country', [])),
                'writer': ','.join(movie.get('writer', []))
            }

            # Handle cast data
            if 'cast' in movie:
                movie_data['cast'] = json.dumps(movie['cast'])

            # Handle art data
            if 'art' in movie:
                movie_data['art'] = json.dumps(movie['art'])

            # Execute insert
            columns = ', '.join(movie_data.keys())
            placeholders = ', '.join(['?' for _ in movie_data])
            query = f"INSERT INTO media_items ({columns}) VALUES ({placeholders})"
            self.execute_query(query, tuple(movie_data.values()))

    def __del__(self):
        """Clean up connections when the instance is destroyed"""
        for conn_info in self._connection_pool:
            try:
                conn_info['connection'].close()
            except:
                pass

    def insert_original_request(self, description: str, response_json: str) -> int:
        """Insert an original request and return its ID"""
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        self.execute_query(query, (description, response_json))
        return self.cursor.lastrowid

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
            params.append(year)
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
        return self.execute_query(query, tuple(params))

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

    def insert_media_item(self, media_data: dict) -> int:
        """Insert media item and return its ID"""
        columns = ', '.join(media_data.keys())
        placeholders = ', '.join('?' for _ in media_data)
        query = f"""
            INSERT OR REPLACE INTO media_items ({columns})
            VALUES ({placeholders})
        """
        conn_info = self._get_connection()
        try:
            cursor = conn_info['connection'].execute(query, tuple(media_data.values()))
            conn_info['connection'].commit()
            return cursor.lastrowid
        finally:
            self._release_connection(conn_info)