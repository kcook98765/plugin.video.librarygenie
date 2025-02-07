
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
                return dict(results)
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
        if result:
            return {
                'description': result['description'],
                'rpc': json.loads(result['rpc']) if result['rpc'] else None
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
        return result['COUNT(*)'] if result else 0

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

    def __del__(self):
        """Clean up connections when the instance is destroyed"""
        for conn_info in self._connection_pool:
            try:
                conn_info['connection'].close()
            except:
                pass
