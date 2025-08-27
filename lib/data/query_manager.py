#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Query Manager
Real SQLite-based data layer for list and item management
"""

import json
from typing import List, Dict, Any, Optional, Union

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
            result: List[Dict[str, Any]] = []
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

            # First try to get items from user_list table (legacy lists)
            items = self.conn_manager.execute_query("""
                SELECT id, title, year, imdb_id, tmdb_id, created_at
                FROM list_item 
                WHERE list_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, [int(list_id), limit, offset])

            # If no items found, try the new lists table (search history lists)
            if not items:
                items = self.conn_manager.execute_query("""
                    SELECT 
                        li.id, 
                        mi.title, 
                        mi.year, 
                        mi.imdbnumber as imdb_id, 
                        mi.tmdb_id,
                        mi.kodi_id,
                        mi.poster,
                        mi.fanart,
                        mi.plot,
                        mi.rating,
                        mi.duration as runtime,
                        mi.genre,
                        mi.director,
                        mi.play as file_path,
                        li.created_at
                    FROM list_items li
                    JOIN media_items mi ON li.media_item_id = mi.id
                    WHERE li.list_id = ?
                    ORDER BY li.position ASC, li.created_at DESC
                    LIMIT ? OFFSET ?
                """, [int(list_id), limit, offset])

            # Convert to expected format
            result: List[Dict[str, Any]] = []
            for row in items:
                item_data = {
                    "id": str(row['id']),
                    "title": row['title'],
                    "year": row['year'],
                    "imdb_id": row['imdb_id'],
                    "tmdb_id": row['tmdb_id'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                }

                # Add additional fields if available (from media_items table)
                if 'kodi_id' in row and row['kodi_id']:
                    item_data['kodi_id'] = row['kodi_id']
                if 'poster' in row and row['poster']:
                    item_data['poster'] = row['poster']
                if 'fanart' in row and row['fanart']:
                    item_data['fanart'] = row['fanart']
                if 'plot' in row and row['plot']:
                    item_data['plot'] = row['plot']
                if 'rating' in row and row['rating']:
                    item_data['rating'] = row['rating']
                if 'runtime' in row and row['runtime']:
                    item_data['runtime'] = row['runtime']
                if 'genre' in row and row['genre']:
                    item_data['genre'] = row['genre']
                if 'director' in row and row['director']:
                    item_data['director'] = row['director']
                if 'file_path' in row and row['file_path']:
                    item_data['file_path'] = row['file_path']

                result.append(item_data)

            self.logger.debug(f"Retrieved {len(result)} items for list {list_id}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get list items: {e}")
            import traceback
            self.logger.error(f"Get list items traceback: {traceback.format_exc()}")
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
            # First try user_list table
            result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM list_item WHERE list_id = ?
            """, [int(list_id)])

            count = result['count'] if result else 0

            # If no items found, try new lists table
            if count == 0:
                result = self.conn_manager.execute_single("""
                    SELECT COUNT(*) as count FROM list_items WHERE list_id = ?
                """, [int(list_id)])
                count = result['count'] if result else 0

            return count

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
        """Ensure default list exists"""
        try:
            # Check if default list exists
            default_list = self.conn_manager.execute_single("""
                SELECT id FROM user_list WHERE name = ?
            """, ["Default"])

            if not default_list:
                self.logger.info("Creating default list")
                with self.conn_manager.transaction() as conn:
                    conn.execute("""
                        INSERT INTO user_list (name)
                        VALUES (?)
                    """, ["Default"])

        except Exception as e:
            self.logger.error(f"Failed to create default list: {e}")

    def get_or_create_search_history_folder(self):
        """Get or create the Search History folder"""
        try:
            # Check if Search History folder exists
            folder = self.conn_manager.execute_single("""
                SELECT id FROM folders WHERE name = ? AND parent_id IS NULL
            """, ["Search History"])

            if folder:
                return folder['id']

            # Create Search History folder
            self.logger.info("Creating Search History folder")
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO folders (name, parent_id)
                    VALUES (?, NULL)
                """, ["Search History"])
                folder_id = cursor.lastrowid
                self.logger.info(f"Created Search History folder with ID: {folder_id}")
                return folder_id

        except Exception as e:
            self.logger.error(f"Failed to create Search History folder: {e}")
            return None

    def create_search_history_list(self, query, search_type, result_count):
        """Create a new search history list"""
        try:
            folder_id = self.get_or_create_search_history_folder()
            if not folder_id:
                self.logger.error("Could not get/create Search History folder")
                return None

            # Generate list name with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            list_name = f"Search: '{query}' ({search_type}) - {timestamp}"

            # Truncate if too long
            if len(list_name) > 100:
                list_name = list_name[:97] + "..."

            # Create the list
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO lists (name, folder_id)
                    VALUES (?, ?)
                """, [list_name, folder_id])
                list_id = cursor.lastrowid

                self.logger.info(f"Created search history list '{list_name}' with ID: {list_id}")
                return list_id

        except Exception as e:
            self.logger.error(f"Failed to create search history list: {e}")
            return None

    def add_search_results_to_list(self, list_id, search_results):
        """Add search results to a list as media items"""
        try:
            if not search_results or not search_results.get('items'):
                return 0

            added_count = 0

            with self.conn_manager.transaction() as conn:
                for position, item in enumerate(search_results['items']):
                    try:
                        # Extract media item data
                        media_data = self._extract_media_item_data(item)

                        # Insert or get existing media item
                        media_item_id = self._insert_or_get_media_item(conn, media_data)

                        if media_item_id:
                            # Add to list
                            conn.execute("""
                                INSERT OR IGNORE INTO list_items (list_id, media_item_id, position)
                                VALUES (?, ?, ?)
                            """, [list_id, media_item_id, position])
                            added_count += 1

                    except Exception as e:
                        self.logger.error(f"Error adding search result item: {e}")
                        continue

            self.logger.info(f"Added {added_count} items to search history list {list_id}")
            return added_count

        except Exception as e:
            self.logger.error(f"Failed to add search results to list: {e}")
            return 0

    def _extract_media_item_data(self, item):
        """Extract media item data from search result item"""
        return {
            'media_type': item.get('type', 'movie'),
            'title': item.get('title', item.get('label', 'Unknown')),
            'year': item.get('year'),
            'imdbnumber': item.get('imdbnumber'),
            'tmdb_id': item.get('tmdb_id'),
            'kodi_id': item.get('movieid') or item.get('id'),
            'source': 'remote' if item.get('_source') == 'remote' else 'lib',
            'play': item.get('path', ''),
            'poster': item.get('art', {}).get('poster', ''),
            'fanart': item.get('art', {}).get('fanart', ''),
            'plot': item.get('plot', ''),
            'rating': item.get('rating'),
            'votes': item.get('votes'),
            'duration': item.get('runtime'),
            'mpaa': item.get('mpaa', ''),
            'genre': ','.join(item.get('genre', [])) if isinstance(item.get('genre'), list) else item.get('genre', ''),
            'director': ','.join(item.get('director', [])) if isinstance(item.get('director'), list) else item.get('director', ''),
            'studio': ','.join(item.get('studio', [])) if isinstance(item.get('studio'), list) else item.get('studio', ''),
            'country': ','.join(item.get('country', [])) if isinstance(item.get('country'), list) else item.get('country', ''),
            'writer': ','.join(item.get('writer', [])) if isinstance(item.get('writer'), list) else item.get('writer', ''),
            'cast': json.dumps(item.get('cast', [])) if item.get('cast') else None,
            'art': json.dumps(item.get('art', {})) if item.get('art') else None
        }

    def _insert_or_get_media_item(self, conn, media_data):
        """Insert or get existing media item"""
        try:

            # Try to find existing item by IMDb ID first
            if media_data.get('imdbnumber'):
                existing = conn.execute("""
                    SELECT id FROM media_items WHERE imdbnumber = ?
                """, [media_data['imdbnumber']]).fetchone()

                if existing:
                    return existing['id']

            # Try to find by title and year
            if media_data.get('title') and media_data.get('year'):
                existing = conn.execute("""
                    SELECT id FROM media_items 
                    WHERE title = ? AND year = ? AND media_type = ?
                """, [media_data['title'], media_data['year'], media_data['media_type']]).fetchone()

                if existing:
                    return existing['id']

            # Insert new media item
            cursor = conn.execute("""
                INSERT INTO media_items 
                (media_type, title, year, imdbnumber, tmdb_id, kodi_id, source, 
                 play, poster, fanart, plot, rating, votes, duration, mpaa, 
                 genre, director, studio, country, writer, cast, art)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                media_data['media_type'], media_data['title'], media_data['year'],
                media_data['imdbnumber'], media_data['tmdb_id'], media_data['kodi_id'],
                media_data['source'], media_data['play'], media_data['poster'],
                media_data['fanart'], media_data['plot'], media_data['rating'],
                media_data['votes'], media_data['duration'], media_data['mpaa'],
                media_data['genre'], media_data['director'], media_data['studio'],
                media_data['country'], media_data['writer'], media_data['cast'],
                media_data['art']
            ])

            return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error inserting/getting media item: {e}")
            return None

    def get_all_lists_with_folders(self):
        """Get all lists including those in folders (like Search History)"""
        try:
            self.logger.debug("Getting all lists with folders from database")

            # Get all lists including those in folders
            lists = self.conn_manager.execute_query("""
                SELECT 
                    l.id,
                    l.name,
                    l.folder_id,
                    l.created_at,
                    datetime('now') as updated_at,
                    (SELECT COUNT(*) FROM list_items WHERE list_id = l.id) as item_count,
                    f.name as folder_name
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id

                UNION ALL

                SELECT 
                    ul.id,
                    ul.name,
                    NULL as folder_id,
                    ul.created_at,
                    ul.updated_at,
                    (SELECT COUNT(*) FROM list_item WHERE list_id = ul.id) as item_count,
                    NULL as folder_name
                FROM user_list ul

                ORDER BY created_at ASC
            """)

            # Convert to expected format
            result: List[Dict[str, Any]] = []
            for row in lists:
                result.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "description": f"{row['item_count']} items",
                    "item_count": row['item_count'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                    "modified": row['updated_at'][:10] if row['updated_at'] else '',
                    "folder_name": row['folder_name'],
                    "is_folder": True
                })

            self.logger.debug(f"Retrieved {len(result)} lists with folders")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get all lists with folders: {e}")
            import traceback
            self.logger.error(f"Get all lists error traceback: {traceback.format_exc()}")
            return []


# Global query manager instance
_query_manager_instance = None

def get_query_manager():
    """Get or create the global query manager instance"""
    global _query_manager_instance
    if _query_manager_instance is None:
        _query_manager_instance = QueryManager()
    return _query_manager_instance


    def close(self):
        """Close database connections"""
        if self._initialized:
            self.logger.info("Closing data layer connections")
            self.conn_manager.close()
            self._initialized = False