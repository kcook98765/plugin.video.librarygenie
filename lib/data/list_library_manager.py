#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - List-Library Integration
Handles operations between lists and library items
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from .connection_manager import get_connection_manager
from ..utils.logger import get_logger


class ListLibraryManager:
    """Manages operations between lists and library movies"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
    
    def add_library_movie_to_list(self, list_id: int, library_movie_id: int) -> Dict[str, Any]:
        """Add a library movie to a list"""
        try:
            # First check if the movie is already in the list
            existing = self.conn_manager.execute_single("""
                SELECT id FROM list_item 
                WHERE list_id = ? AND library_movie_id = ?
            """, [list_id, library_movie_id])
            
            if existing:
                return {
                    "success": False, 
                    "error": "duplicate",
                    "message": "Movie is already in this list"
                }
            
            # Get movie details for the list item
            movie = self.conn_manager.execute_single("""
                SELECT title, year, imdbnumber as imdb_id, tmdb_id, is_removed
                FROM media_items 
                WHERE id = ? AND media_type = 'movie'
            """, [library_movie_id])
            
            # Convert SQLite Row to dict if needed
            if movie and hasattr(movie, 'keys'):
                movie = dict(movie)
            
            if not movie:
                return {
                    "success": False,
                    "error": "not_found", 
                    "message": "Movie not found in library"
                }
            
            # Check if movie is removed/missing
            if movie["is_removed"]:
                return {
                    "success": False,
                    "error": "removed",
                    "message": "Cannot add removed/missing movie to list"
                }
            
            # Add the movie to the list
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO list_item 
                    (list_id, library_movie_id, title, year, imdb_id, tmdb_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    list_id, library_movie_id,
                    movie["title"], movie["year"], 
                    movie["imdb_id"], movie["tmdb_id"]
                ])
                
                list_item_id = cursor.lastrowid
                
                # Log the operation
                conn.execute("""
                    INSERT INTO list_operation_log 
                    (operation, list_id, library_movie_id, movie_title)
                    VALUES (?, ?, ?, ?)
                """, ["add", list_id, library_movie_id, movie["title"]])
            
            self.logger.info(f"Added movie '{movie['title']}' to list {list_id}")
            
            return {
                "success": True,
                "list_item_id": list_item_id,
                "movie_title": movie["title"]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add movie to list: {e}")
            return {
                "success": False,
                "error": "database_error",
                "message": str(e)
            }
    
    def remove_movie_from_list(self, list_id: int, list_item_id: int) -> Dict[str, Any]:
        """Remove a movie from a list"""
        try:
            # Get item details before deletion for logging
            item = self.conn_manager.execute_single("""
                SELECT li.title, li.library_movie_id
                FROM list_item li
                WHERE li.id = ? AND li.list_id = ?
            """, [list_item_id, list_id])
            
            if not item:
                return {
                    "success": False,
                    "error": "not_found",
                    "message": "Item not found in list"
                }
            
            # Remove the item
            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    DELETE FROM list_item 
                    WHERE id = ? AND list_id = ?
                """, [list_item_id, list_id])
                
                if result.rowcount == 0:
                    return {
                        "success": False,
                        "error": "not_found",
                        "message": "Item not found or already removed"
                    }
                
                # Log the operation
                conn.execute("""
                    INSERT INTO list_operation_log 
                    (operation, list_id, library_movie_id, movie_title)
                    VALUES (?, ?, ?, ?)
                """, ["remove", list_id, item["library_movie_id"], item["title"]])
            
            self.logger.info(f"Removed movie '{item['title']}' from list {list_id}")
            
            return {
                "success": True,
                "movie_title": item["title"]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to remove movie from list: {e}")
            return {
                "success": False,
                "error": "database_error",
                "message": str(e)
            }
    
    def move_movie_to_list(self, from_list_id: int, to_list_id: int, list_item_id: int) -> Dict[str, Any]:
        """Move a movie from one list to another"""
        try:
            # Get the item details
            item = self.conn_manager.execute_single("""
                SELECT library_movie_id, title, year, imdb_id, tmdb_id
                FROM list_item 
                WHERE id = ? AND list_id = ?
            """, [list_item_id, from_list_id])
            
            if not item:
                return {
                    "success": False,
                    "error": "not_found",
                    "message": "Item not found in source list"
                }
            
            # Check if already in target list
            existing = self.conn_manager.execute_single("""
                SELECT id FROM list_item 
                WHERE list_id = ? AND library_movie_id = ?
            """, [to_list_id, item["library_movie_id"]])
            
            if existing:
                return {
                    "success": False,
                    "error": "duplicate",
                    "message": "Movie is already in target list"
                }
            
            # Perform the move in a transaction
            with self.conn_manager.transaction() as conn:
                # Remove from source list
                conn.execute("""
                    DELETE FROM list_item 
                    WHERE id = ? AND list_id = ?
                """, [list_item_id, from_list_id])
                
                # Add to target list
                cursor = conn.execute("""
                    INSERT INTO list_item 
                    (list_id, library_movie_id, title, year, imdb_id, tmdb_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    to_list_id, item["library_movie_id"],
                    item["title"], item["year"],
                    item["imdb_id"], item["tmdb_id"]
                ])
                
                new_item_id = cursor.lastrowid
                
                # Log the operations
                conn.execute("""
                    INSERT INTO list_operation_log 
                    (operation, list_id, library_movie_id, movie_title)
                    VALUES (?, ?, ?, ?)
                """, ["remove", from_list_id, item["library_movie_id"], item["title"]])
                
                conn.execute("""
                    INSERT INTO list_operation_log 
                    (operation, list_id, library_movie_id, movie_title)
                    VALUES (?, ?, ?, ?)
                """, ["add", to_list_id, item["library_movie_id"], item["title"]])
            
            self.logger.info(f"Moved movie '{item['title']}' from list {from_list_id} to list {to_list_id}")
            
            return {
                "success": True,
                "new_item_id": new_item_id,
                "movie_title": item["title"]
            }
            
        except Exception as e:
            self.logger.error(f"Failed to move movie between lists: {e}")
            return {
                "success": False,
                "error": "database_error",
                "message": str(e)
            }
    
    def get_available_lists_for_movie(self, library_movie_id: int) -> List[Dict[str, Any]]:
        """Get lists that don't already contain this movie"""
        try:
            lists = self.conn_manager.execute_query("""
                SELECT ul.id, ul.name, ul.description,
                       COUNT(li.id) as item_count
                FROM user_list ul
                LEFT JOIN list_item li ON ul.id = li.list_id
                WHERE ul.id NOT IN (
                    SELECT list_id FROM list_item 
                    WHERE library_movie_id = ?
                )
                GROUP BY ul.id, ul.name, ul.description
                ORDER BY ul.name
            """, [library_movie_id])
            
            return lists or []
            
        except Exception as e:
            self.logger.error(f"Failed to get available lists: {e}")
            return []
    
    def get_list_items_with_library_info(self, list_id: int) -> List[Dict[str, Any]]:
        """Get list items with library movie information"""
        try:
            items = self.conn_manager.execute_query("""
                SELECT li.id as list_item_id, li.title, li.year, li.imdb_id, li.tmdb_id,
                       li.library_movie_id, li.created_at,
                       mi.is_removed, mi.updated_at as last_seen, mi.play as file_path
                FROM list_item li
                LEFT JOIN media_items mi ON li.library_movie_id = mi.id AND mi.media_type = 'movie'
                WHERE li.list_id = ?
                ORDER BY li.created_at DESC
            """, [list_id])
            
            return items or []
            
        except Exception as e:
            self.logger.error(f"Failed to get list items with library info: {e}")
            return []


# Global list-library manager instance
_list_library_instance = None


def get_list_library_manager():
    """Get global list-library manager instance"""
    global _list_library_instance
    if _list_library_instance is None:
        _list_library_instance = ListLibraryManager()
    return _list_library_instance