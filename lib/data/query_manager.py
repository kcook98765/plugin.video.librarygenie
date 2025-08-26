#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Query Manager
Real SQLite-based data layer for list and item management
"""

from .connection_manager import get_connection_manager
from .migrations import get_migration_manager
from ..utils.logger import get_logger


class QueryManager:
    """Manages data queries and database operations using SQLite"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.migration_manager = get_migration_manager()
        self._initialized = False

    def initialize(self):
        """Initialize the data layer with real SQLite database"""
        if self._initialized:
            return True

        try:
            self.logger.info("Initializing SQLite data layer")
            
            # Apply migrations to ensure schema is up to date
            self.migration_manager.ensure_initialized()
            
            # Ensure default list exists
            self._ensure_default_list()
            
            self._initialized = True
            self.logger.info("Data layer initialization complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize data layer: {e}")
            return False

    def get_user_lists(self):
        """Get all user lists from database"""
        try:
            self.logger.debug("Getting user lists from database")
            
            lists = self.conn_manager.execute_query("""
                SELECT 
                    id,
                    name,
                    created_at,
                    updated_at,
                    (SELECT COUNT(*) FROM list_item WHERE list_id = user_list.id) as item_count
                FROM user_list 
                ORDER BY created_at ASC
            """)
            
            # Convert to expected format
            result = []
            for row in lists:
                result.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "description": f"{row['item_count']} items",
                    "item_count": row['item_count'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                    "modified": row['updated_at'][:10] if row['updated_at'] else '',
                })
            
            self.logger.debug(f"Retrieved {len(result)} lists")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get user lists: {e}")
            return []

    def get_list_items(self, list_id, limit=100, offset=0):
        """Get items in a specific list from database"""
        try:
            self.logger.debug(f"Getting items for list {list_id}")
            
            items = self.conn_manager.execute_query("""
                SELECT id, title, year, imdb_id, tmdb_id, created_at
                FROM list_item 
                WHERE list_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, [int(list_id), limit, offset])
            
            # Convert to expected format
            result = []
            for row in items:
                result.append({
                    "id": str(row['id']),
                    "title": row['title'],
                    "year": row['year'],
                    "imdb_id": row['imdb_id'],
                    "tmdb_id": row['tmdb_id'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                })
            
            self.logger.debug(f"Retrieved {len(result)} items for list {list_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get list items: {e}")
            return []

    def create_list(self, name, description=""):
        """Create a new list in database with proper validation"""
        if not name or not name.strip():
            self.logger.warning("Attempted to create list with empty name")
            return {"error": "empty_name"}
        
        name = name.strip()
        
        try:
            self.logger.info(f"Creating list '{name}'")
            
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO user_list (name) VALUES (?)
                """, [name])
                
                list_id = cursor.lastrowid
                
            return {
                "id": str(list_id),
                "name": name,
                "description": description
            }
            
        except Exception as e:
            error_msg = str(e).lower()
            if "unique constraint" in error_msg:
                self.logger.warning(f"List name '{name}' already exists")
                return {"error": "duplicate_name"}
            else:
                self.logger.error(f"Failed to create list '{name}': {e}")
                return {"error": "database_error"}

    def add_item_to_list(self, list_id, title, year=None, imdb_id=None, tmdb_id=None):
        """Add an item to a list in database"""
        try:
            self.logger.info(f"Adding '{title}' to list {list_id}")
            
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO list_item (list_id, title, year, imdb_id, tmdb_id)
                    VALUES (?, ?, ?, ?, ?)
                """, [int(list_id), title, year, imdb_id, tmdb_id])
                
                item_id = cursor.lastrowid
            
            return {
                "id": str(item_id),
                "title": title,
                "year": year,
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add item '{title}' to list {list_id}: {e}")
            return None

    def count_list_items(self, list_id):
        """Count items in a specific list"""
        try:
            result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM list_item WHERE list_id = ?
            """, [int(list_id)])
            
            return result['count'] if result else 0
            
        except Exception as e:
            self.logger.error(f"Failed to count items in list {list_id}: {e}")
            return 0

    def delete_list(self, list_id):
        """Delete a list from database"""
        try:
            self.logger.info(f"Deleting list {list_id}")
            
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM user_list WHERE id = ?", [int(list_id)])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete list {list_id}: {e}")
            return False

    def delete_item_from_list(self, list_id, item_id):
        """Delete an item from a list in database"""
        try:
            self.logger.info(f"Deleting item {item_id} from list {list_id}")
            
            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    DELETE FROM list_item 
                    WHERE id = ? AND list_id = ?
                """, [int(item_id), int(list_id)])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete item {item_id} from list {list_id}: {e}")
            return False

    def rename_list(self, list_id, new_name):
        """Rename a list with validation"""
        if not new_name or not new_name.strip():
            self.logger.warning("Attempted to rename list with empty name")
            return {"error": "empty_name"}
        
        new_name = new_name.strip()
        
        try:
            self.logger.info(f"Renaming list {list_id} to '{new_name}'")
            
            with self.conn_manager.transaction() as conn:
                # Check if list exists
                existing = conn.execute(
                    "SELECT name FROM user_list WHERE id = ?", [int(list_id)]
                ).fetchone()
                
                if not existing:
                    return {"error": "list_not_found"}
                
                # Update the list name
                conn.execute("""
                    UPDATE user_list 
                    SET name = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, [new_name, int(list_id)])
                
            return {"success": True, "name": new_name}
            
        except Exception as e:
            error_msg = str(e).lower()
            if "unique constraint" in error_msg:
                self.logger.warning(f"List name '{new_name}' already exists")
                return {"error": "duplicate_name"}
            else:
                self.logger.error(f"Failed to rename list {list_id}: {e}")
                return {"error": "database_error"}

    def delete_list(self, list_id):
        """Delete a list and cascade delete its items"""
        try:
            self.logger.info(f"Deleting list {list_id}")
            
            with self.conn_manager.transaction() as conn:
                # Check if list exists
                existing = conn.execute(
                    "SELECT name FROM user_list WHERE id = ?", [int(list_id)]
                ).fetchone()
                
                if not existing:
                    return {"error": "list_not_found"}
                
                # Delete list (items cascade automatically via foreign key)
                conn.execute("DELETE FROM user_list WHERE id = ?", [int(list_id)])
            
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Failed to delete list {list_id}: {e}")
            return {"error": "database_error"}

    def get_list_by_id(self, list_id):
        """Get a specific list by ID"""
        try:
            result = self.conn_manager.execute_single("""
                SELECT 
                    id, name, created_at, updated_at,
                    (SELECT COUNT(*) FROM list_item WHERE list_id = user_list.id) as item_count
                FROM user_list 
                WHERE id = ?
            """, [int(list_id)])
            
            if result:
                return {
                    "id": str(result['id']),
                    "name": result['name'],
                    "description": f"{result['item_count']} items",
                    "item_count": result['item_count'],
                    "created": result['created_at'][:10] if result['created_at'] else '',
                    "modified": result['updated_at'][:10] if result['updated_at'] else '',
                }
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get list {list_id}: {e}")
            return None

    def _ensure_default_list(self):
        """Ensure a default list exists"""
        try:
            # Check if any lists exist
            result = self.conn_manager.execute_single(
                "SELECT COUNT(*) as count FROM user_list"
            )
            
            if result and result['count'] == 0:
                self.logger.info("No lists found, creating default list")
                result = self.create_list("Default")
                if result and "error" in result:
                    self.logger.warning("Failed to create default list, continuing anyway")
                
        except Exception as e:
            self.logger.error(f"Failed to ensure default list: {e}")

    def close(self):
        """Close database connections"""
        if self._initialized:
            self.logger.info("Closing data layer connections")
            self.conn_manager.close()
            self._initialized = False