import os
from resources.lib.utils import utils
from resources.lib.data.query_manager import QueryManager
from typing import Optional, List, Dict, Any, Union


class DatabaseManager:
    """Database manager that delegates all operations to QueryManager"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.query_manager = QueryManager(self.db_path)
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
            # Delegate schema setup to QueryManager's comprehensive setup method
            self.query_manager.setup_database()
            utils.log("Database schema setup completed via QueryManager", "DEBUG")

        except Exception as e:
            utils.log(f"Error setting up database schema: {str(e)}", "ERROR")
            raise

    # Delegate all operations to QueryManager
    def fetch_data(self, table: str, condition: str = "", params: tuple = ()) -> List[Dict]:
        """Fetch data from table - delegates to QueryManager"""
        return self.query_manager.fetch_data(table, condition, params)

    def insert_data(self, table: str, data: Dict) -> int:
        """Insert data into table - delegates to QueryManager"""
        return self.query_manager.insert_data(table, data)

    def update_data(self, table: str, data: Dict, condition: str, params: tuple = ()) -> None:
        """Update data in table - delegates to QueryManager"""
        self.query_manager.update_data(table, data, condition, params)

    def delete_data(self, table: str, condition: str, params: tuple = ()) -> None:
        """Delete data from table - delegates to QueryManager"""
        self.query_manager.delete_data(table, condition, params)

    def get_list_media_count(self, list_id: int) -> int:
        """Get count of media items in a list"""
        return self.query_manager.get_list_media_count(list_id)

    def fetch_list_by_id(self, list_id: int) -> Optional[Dict]:
        """Fetch list details by ID"""
        return self.query_manager.fetch_list_by_id(list_id)

    def fetch_folder_by_id(self, folder_id: int) -> Optional[Dict]:
        """Fetch folder details by ID"""
        return self.query_manager.fetch_folder_by_id(folder_id)

    def fetch_folders(self, parent_id: Optional[int] = None) -> List[Dict]:
        """Fetch folders by parent ID"""
        return self.query_manager.fetch_folders(parent_id)

    def fetch_lists(self, folder_id: Optional[int] = None) -> List[Dict]:
        """Fetch lists by folder ID"""
        return self.query_manager.fetch_lists(folder_id)

    def fetch_all_lists(self) -> List[Dict]:
        """Fetch all lists"""
        return self.query_manager.fetch_all_lists()

    def fetch_all_folders(self) -> List[Dict]:
        """Fetch all folders"""
        return self.query_manager.fetch_all_folders()

    def get_folder_id_by_name(self, name: str) -> Optional[int]:
        """Get folder ID by name"""
        return self.query_manager.get_folder_id_by_name(name)

    def create_list(self, name: str, folder_id: Optional[int] = None) -> Dict:
        """Create a new list"""
        return self.query_manager.create_list(name, folder_id)

    def create_folder(self, name: str, parent_id: Optional[int] = None) -> Dict:
        """Create a new folder"""
        return self.query_manager.create_folder(name, parent_id)

    def move_list_to_folder(self, list_id: int, folder_id: Optional[int]) -> bool:
        """Move a list to a different folder"""
        return self.query_manager.move_list_to_folder(list_id, folder_id)

    def clear_list_items(self, list_id: int) -> bool:
        """Clear all items from a list"""
        return self.query_manager.clear_list_items(list_id)

    def delete_folder(self, folder_id: int) -> bool:
        """Delete a folder and all its contents"""
        return self.query_manager.delete_folder(folder_id)

    def get_descendant_folder_ids(self, folder_id: int) -> List[int]:
        """Get all descendant folder IDs recursively"""
        return self.query_manager.get_descendant_folder_ids(folder_id)

    def get_folder_path(self, folder_id: int) -> str:
        """Get full path of a folder"""
        return self.query_manager.get_folder_path(folder_id)

    def fetch_list_items_with_details(self, list_id: int) -> List[Dict]:
        """Fetch list items with media details"""
        return self.query_manager.fetch_list_items_with_details(list_id)

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
            # Use QueryManager's atomic insert method
            return self.query_manager.insert_media_item_and_add_to_list(list_id, media_item)
        except Exception as e:
            utils.log(f"Error adding media item to list: {str(e)}", "ERROR")
            return False

    def delete_list(self, list_id: int) -> bool:
        """Delete a list and all its contents"""
        try:
            with self.query_manager.transaction() as conn:
                # Delete list items first
                cursor = conn.execute("DELETE FROM list_items WHERE list_id = ?", (list_id,))
                # Delete the list
                cursor = conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
                return cursor.rowcount > 0
        except Exception as e:
            utils.log(f"Error deleting list {list_id}: {str(e)}", "ERROR")
            return False

    def close(self):
        """Close database connection"""
        if self.query_manager:
            self.query_manager.close()

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.close()
        except:
            pass