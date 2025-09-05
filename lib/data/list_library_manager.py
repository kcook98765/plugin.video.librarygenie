#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - List Library Manager
Manages the library movies table and provides methods for library item operations
"""

import json
from typing import List, Dict, Any, Optional

from .connection_manager import get_connection_manager
from ..utils.logger import get_logger


class ListLibraryManager:
    """Manages library movie operations using standard connection manager"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()

    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a library item by ID"""
        try:
            result = self.conn_manager.execute_single("""
                SELECT * FROM media_items WHERE id = ?
            """, [item_id])

            if result:
                return dict(result)
            return None

        except Exception as e:
            self.logger.error(f"Error getting item by ID {item_id}: {e}")
            return None

    def find_by_imdb(self, imdb_id: str) -> Optional[Dict[str, Any]]:
        """Find library item by IMDb ID"""
        try:
            result = self.conn_manager.execute_single("""
                SELECT * FROM media_items WHERE imdbnumber = ?
            """, [imdb_id])

            if result:
                return dict(result)
            return None

        except Exception as e:
            self.logger.error(f"Error finding item by IMDb {imdb_id}: {e}")
            return None

    def find_by_title_year(self, title: str, year: int) -> Optional[Dict[str, Any]]:
        """Find library item by title and year"""
        try:
            result = self.conn_manager.execute_single("""
                SELECT * FROM media_items WHERE title = ? AND year = ?
            """, [title, year])

            if result:
                return dict(result)
            return None

        except Exception as e:
            self.logger.error(f"Error finding item by title/year {title}/{year}: {e}")
            return None

    def get_all_items(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all library items with limit"""
        try:
            results = self.conn_manager.execute_query("""
                SELECT * FROM media_items ORDER BY title LIMIT ?
            """, [limit])

            return [dict(row) for row in results]

        except Exception as e:
            self.logger.error(f"Error getting all items: {e}")
            return []

    def update_item(self, item_id: int, data: Dict[str, Any]) -> bool:
        """Update a library item"""
        try:
            # Build update query dynamically based on provided data
            update_fields = []
            params = []

            for key, value in data.items():
                if key != 'id':  # Don't update ID field
                    update_fields.append(f"{key} = ?")
                    params.append(value)

            if not update_fields:
                return True  # No fields to update

            params.append(item_id)  # Add ID for WHERE clause

            with self.conn_manager.transaction() as conn:
                conn.execute(f"""
                    UPDATE media_items 
                    SET {', '.join(update_fields)}, updated_at = datetime('now')
                    WHERE id = ?
                """, params)

            return True

        except Exception as e:
            self.logger.error(f"Error updating item {item_id}: {e}")
            return False

    def delete_item(self, item_id: int) -> bool:
        """Delete a library item"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM media_items WHERE id = ?", [item_id])
            return True

        except Exception as e:
            self.logger.error(f"Error deleting item {item_id}: {e}")
            return False

    def insert_or_update_item(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert or update a library item, return the item ID"""
        try:
            # Try to find existing item
            existing = None
            if data.get('imdbnumber'):
                existing = self.find_by_imdb(data['imdbnumber'])
            elif data.get('title') and data.get('year'):
                existing = self.find_by_title_year(data['title'], data['year'])

            if existing:
                # Update existing item
                if self.update_item(existing['id'], data):
                    return existing['id']
                return None
            else:
                # Insert new item
                with self.conn_manager.transaction() as conn:
                    cursor = conn.execute("""
                        INSERT INTO media_items 
                        (media_type, title, year, imdbnumber, tmdb_id, kodi_id, source, 
                         play, poster, fanart, plot, rating, votes, duration, mpaa, 
                         genre, director, studio, country, writer, cast, art)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        data.get('media_type', 'movie'),
                        data.get('title', ''),
                        data.get('year', 0),
                        data.get('imdbnumber', ''),
                        data.get('tmdb_id', ''),
                        data.get('kodi_id'),
                        data.get('source', ''),
                        data.get('play', ''),
                        data.get('poster', ''),
                        data.get('fanart', ''),
                        data.get('plot', ''),
                        data.get('rating', 0.0),
                        data.get('votes', 0),
                        data.get('duration', 0),
                        data.get('mpaa', ''),
                        data.get('genre', ''),
                        data.get('director', ''),
                        data.get('studio', ''),
                        data.get('country', ''),
                        data.get('writer', ''),
                        data.get('cast', ''),
                        data.get('art', '')
                    ])
                    return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error inserting/updating item: {e}")
            return None

    def get_stats(self) -> Dict[str, int]:
        """Get library statistics"""
        try:
            total_result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM media_items
            """)

            movies_result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM media_items WHERE media_type = 'movie'
            """)

            episodes_result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM media_items WHERE media_type = 'episode'
            """)

            return {
                'total_items': total_result['count'] if total_result else 0,
                'movies': movies_result['count'] if movies_result else 0,
                'episodes': episodes_result['count'] if episodes_result else 0
            }

        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {'total_items': 0, 'movies': 0, 'episodes': 0}


# Global instance
_list_library_manager_instance = None

def get_list_library_manager():
    """Get or create the global list library manager instance"""
    global _list_library_manager_instance
    if _list_library_manager_instance is None:
        _list_library_manager_instance = ListLibraryManager()
    return _list_library_manager_instance