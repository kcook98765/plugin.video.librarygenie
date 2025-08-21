import os
import sqlite3
from resources.lib.utils import utils
from resources.lib.data.query_manager import QueryManager
from typing import Optional, List, Dict, Any, Union


class DatabaseManager:
    """Database manager that delegates all operations to QueryManager"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._query_manager = QueryManager(self.db_path)
        self._connect()  # Keep for directory creation and schema setup

    def _connect(self):
        """Ensure database directory exists and schema is set up"""
        try:
            # Ensure directory exists using Kodi-safe path handling
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            # Set up schema if needed
            self.setup_database()

            utils.log(f"DatabaseManager initialized with path: {self.db_path}", "DEBUG")
        except Exception as e:
            utils.log(f"Database connection error: {str(e)}", "ERROR")
            raise

    def setup_database(self):
        """Set up database schema using QueryManager"""
        try:
            # Create folders table
            self._query_manager.execute_write("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    FOREIGN KEY (parent_id) REFERENCES folders (id) ON DELETE CASCADE
                )
            """)

            # Create lists table
            self._query_manager.execute_write("""
                CREATE TABLE IF NOT EXISTS lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    folder_id INTEGER,
                    FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
                )
            """)

            # Create media_items table
            self._query_manager.execute_write("""
                CREATE TABLE IF NOT EXISTS media_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kodi_id INTEGER DEFAULT 0,
                    title TEXT NOT NULL,
                    year INTEGER DEFAULT 0,
                    imdbnumber TEXT,
                    source TEXT DEFAULT 'lib',
                    plot TEXT DEFAULT '',
                    rating REAL DEFAULT 0.0,
                    poster TEXT DEFAULT '',
                    genre TEXT DEFAULT '',
                    director TEXT DEFAULT '',
                    duration TEXT DEFAULT '',
                    search_score REAL DEFAULT 0.0,
                    media_type TEXT DEFAULT 'movie'
                )
            """)

            # Create list_items table
            self._query_manager.execute_write("""
                CREATE TABLE IF NOT EXISTS list_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    media_item_id INTEGER NOT NULL,
                    search_score REAL DEFAULT 0.0,
                    FOREIGN KEY (list_id) REFERENCES lists (id) ON DELETE CASCADE,
                    FOREIGN KEY (media_item_id) REFERENCES media_items (id) ON DELETE CASCADE,
                    UNIQUE(list_id, media_item_id)
                )
            """)

            # Create imdb_exports table for search functionality
            self._query_manager.execute_write("""
                CREATE TABLE IF NOT EXISTS imdb_exports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imdb_id TEXT NOT NULL,
                    title TEXT,
                    year INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(imdb_id)
                )
            """)

            # Create indexes for performance
            self._query_manager.execute_write("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id)")
            self._query_manager.execute_write("CREATE INDEX IF NOT EXISTS idx_lists_folder ON lists(folder_id)")
            self._query_manager.execute_write("CREATE INDEX IF NOT EXISTS idx_media_imdb ON media_items(imdbnumber)")
            self._query_manager.execute_write("CREATE INDEX IF NOT EXISTS idx_list_items_list ON list_items(list_id)")
            self._query_manager.execute_write("CREATE INDEX IF NOT EXISTS idx_list_items_media ON list_items(media_item_id)")
            self._query_manager.execute_write("CREATE INDEX IF NOT EXISTS idx_imdb_exports_imdb ON imdb_exports(imdb_id)")

            utils.log("Database schema setup completed", "DEBUG")

        except Exception as e:
            utils.log(f"Error setting up database schema: {str(e)}", "ERROR")
            raise

    # Delegate all operations to QueryManager
    def fetch_data(self, table: str, condition: str = "", params: tuple = ()) -> List[Dict]:
        """Fetch data from table - delegates to QueryManager"""
        return self._query_manager.fetch_data(table, condition, params)

    def insert_data(self, table: str, data: Dict) -> int:
        """Insert data into table - delegates to QueryManager"""
        return self._query_manager.insert_data(table, data)

    def update_data(self, table: str, data: Dict, condition: str, params: tuple = ()) -> None:
        """Update data in table - delegates to QueryManager"""
        self._query_manager.update_data(table, data, condition, params)

    def delete_data(self, table: str, condition: str, params: tuple = ()) -> None:
        """Delete data from table - delegates to QueryManager"""
        self._query_manager.delete_data(table, condition, params)

    def get_list_media_count(self, list_id: int) -> int:
        """Get count of media items in a list"""
        return self._query_manager.get_list_media_count(list_id)

    def fetch_list_by_id(self, list_id: int) -> Optional[Dict]:
        """Fetch list details by ID"""
        return self._query_manager.fetch_list_by_id(list_id)

    def fetch_folder_by_id(self, folder_id: int) -> Optional[Dict]:
        """Fetch folder details by ID"""
        return self._query_manager.fetch_folder_by_id(folder_id)

    def fetch_folders(self, parent_id: Optional[int] = None) -> List[Dict]:
        """Fetch folders by parent ID"""
        return self._query_manager.fetch_folders(parent_id)

    def fetch_lists(self, folder_id: Optional[int] = None) -> List[Dict]:
        """Fetch lists by folder ID"""
        return self._query_manager.fetch_lists(folder_id)

    def fetch_all_lists(self) -> List[Dict]:
        """Fetch all lists"""
        return self._query_manager.fetch_all_lists()

    def fetch_all_folders(self) -> List[Dict]:
        """Fetch all folders"""
        return self._query_manager.fetch_all_folders()

    def get_folder_id_by_name(self, name: str) -> Optional[int]:
        """Get folder ID by name"""
        return self._query_manager.get_folder_id_by_name(name)

    def create_list(self, name: str, folder_id: Optional[int] = None) -> Dict:
        """Create a new list"""
        return self._query_manager.create_list(name, folder_id)

    def create_folder(self, name: str, parent_id: Optional[int] = None) -> Dict:
        """Create a new folder"""
        return self._query_manager.create_folder(name, parent_id)

    def move_list_to_folder(self, list_id: int, folder_id: Optional[int]) -> bool:
        """Move a list to a different folder"""
        return self._query_manager.move_list_to_folder(list_id, folder_id)

    def clear_list_items(self, list_id: int) -> bool:
        """Clear all items from a list"""
        return self._query_manager.clear_list_items(list_id)

    def delete_folder(self, folder_id: int) -> bool:
        """Delete a folder and all its contents"""
        return self._query_manager.delete_folder(folder_id)

    def get_descendant_folder_ids(self, folder_id: int) -> List[int]:
        """Get all descendant folder IDs recursively"""
        return self._query_manager.get_descendant_folder_ids(folder_id)

    def get_folder_path(self, folder_id: int) -> str:
        """Get full path of a folder"""
        return self._query_manager.get_folder_path(folder_id)

    def fetch_list_items_with_details(self, list_id: int) -> List[Dict]:
        """Fetch list items with media details"""
        return self._query_manager.fetch_list_items_with_details(list_id)

    def ensure_folder_exists(self, name: str, parent_id: Optional[int]) -> Dict:
        """Ensure a folder exists, create if it doesn't"""
        folder_id = self.get_folder_id_by_name(name)
        if folder_id:
            return {'id': folder_id, 'name': name, 'parent_id': parent_id}
        else:
            return self.create_folder(name, parent_id)

    def add_media_item(self, list_id: int, media_item: Dict) -> bool:
        """Add a media item to a list"""
        try:
            # Check if media item already exists
            existing_media = self.fetch_data('media_items', f"imdbnumber = '{media_item.get('imdbnumber', '')}'")

            if existing_media:
                media_id = existing_media[0]['id']
            else:
                # Insert new media item
                media_id = self.insert_data('media_items', media_item)

            # Check if already in list
            existing_list_item = self.fetch_data('list_items', f"list_id = {list_id} AND media_item_id = {media_id}")

            if not existing_list_item:
                # Add to list
                list_item_data = {
                    'list_id': list_id,
                    'media_item_id': media_id,
                    'search_score': media_item.get('search_score', 0)
                }
                self.insert_data('list_items', list_item_data)

            return True

        except Exception as e:
            utils.log(f"Error adding media item to list: {str(e)}", "ERROR")
            return False

    def close(self):
        """Close database connection"""
        if self._query_manager:
            self._query_manager.close()

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.close()
        except:
            pass