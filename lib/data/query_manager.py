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

    RESERVED_FOLDERS = ["Search History"]

    def __init__(self):
        self.logger = get_logger(__name__)
        self.connection_manager = get_connection_manager()
        self.migration_manager = get_migration_manager()
        self._initialized = False

    def _normalize_to_canonical(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize any media item to canonical format"""
        canonical = {}

        # CRITICAL: Preserve the ID field from the database query
        if 'id' in item:
            canonical["id"] = item["id"]
        elif 'item_id' in item:
            canonical["id"] = item["item_id"]
        elif 'media_item_id' in item:
            canonical["id"] = item["media_item_id"]

        # Common fields
        canonical["media_type"] = item.get("media_type", item.get("type", "movie"))
        canonical["kodi_id"] = int(item["kodi_id"]) if item.get("kodi_id") else None
        canonical["title"] = str(item.get("title", ""))
        canonical["originaltitle"] = str(item.get("originaltitle", "")) if item.get("originaltitle") != canonical["title"] else ""
        canonical["sorttitle"] = str(item.get("sorttitle", ""))
        canonical["year"] = int(item.get("year", 0)) if item.get("year") else 0
        canonical["genre"] = str(item.get("genre", ""))
        canonical["plot"] = str(item.get("plot", item.get("plotoutline", "")))
        canonical["rating"] = float(item.get("rating", 0.0))
        canonical["votes"] = int(item.get("votes", 0))
        canonical["mpaa"] = str(item.get("mpaa", ""))
        canonical["studio"] = str(item.get("studio", ""))
        canonical["country"] = str(item.get("country", ""))
        canonical["premiered"] = str(item.get("premiered", item.get("dateadded", "")))

        # Duration - normalize to minutes (runtime from JSON-RPC is in minutes)
        runtime = item.get("runtime", item.get("duration", 0))
        if runtime:
            # Runtime from JSON-RPC is already in minutes, duration might be seconds
            if runtime > 1000:  # Assume seconds, convert to minutes
                canonical["duration_minutes"] = int(runtime / 60)
            else:  # Already in minutes
                canonical["duration_minutes"] = int(runtime)
        else:
            canonical["duration_minutes"] = 0

        # Art normalization - flatten art dict or use direct keys AND preserve original art dict
        art = item.get("art", {})
        if isinstance(art, dict):
            canonical["poster"] = art.get("poster", "")
            canonical["fanart"] = art.get("fanart", "")
            canonical["thumb"] = art.get("thumb", "") if art.get("thumb") else ""
            canonical["banner"] = art.get("banner", "") if art.get("banner") else ""
            canonical["landscape"] = art.get("landscape", "") if art.get("landscape") else ""
            canonical["clearlogo"] = art.get("clearlogo", "") if art.get("clearlogo") else ""
            # Preserve the original art dict for the builder
            canonical["art"] = art
        else:
            canonical["poster"] = str(item.get("poster", item.get("thumbnail", "")))
            canonical["fanart"] = str(item.get("fanart", ""))
            canonical["thumb"] = ""
            canonical["banner"] = ""
            canonical["landscape"] = ""
            canonical["clearlogo"] = ""
            # Create art dict from individual fields
            canonical["art"] = {
                "poster": canonical["poster"],
                "fanart": canonical["fanart"]
            }

        # Resume - always present for library items, in seconds
        resume_data = item.get("resume", {})
        if isinstance(resume_data, dict):
            canonical["resume"] = {
                "position_seconds": int(resume_data.get("position", resume_data.get("position_seconds", 0))),
                "total_seconds": int(resume_data.get("total", resume_data.get("total_seconds", 0)))
            }
        else:
            canonical["resume"] = {"position_seconds": 0, "total_seconds": 0}

        # Episode-specific fields
        if canonical["media_type"] == "episode":
            canonical["tvshowtitle"] = str(item.get("tvshowtitle", item.get("showtitle", "")))
            canonical["season"] = int(item.get("season", 0))
            canonical["episode"] = int(item.get("episode", 0))
            canonical["aired"] = str(item.get("aired", ""))
            canonical["playcount"] = int(item.get("playcount", 0))
            canonical["lastplayed"] = str(item.get("lastplayed", ""))

        return canonical

    def initialize(self):
        """Initialize the data layer with real SQLite database"""
        if self._initialized:
            return True

        try:
            self.logger.debug("Initializing SQLite data layer")

            # Apply migrations to ensure schema is up to date
            self.migration_manager.ensure_initialized()

            # Ensure default list exists
            self._ensure_default_list()

            self._initialized = True
            self.logger.debug("Data layer initialization complete")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize data layer: {e}")
            return False

    def get_user_lists(self):
        """Get all user lists from unified lists table"""
        try:
            self.logger.debug("Getting user lists from database")

            lists = self.connection_manager.execute_query("""
                SELECT 
                    l.id,
                    l.name,
                    l.created_at,
                    l.created_at as updated_at,
                    (SELECT COUNT(*) FROM list_items WHERE list_id = l.id) as item_count,
                    f.name as folder_name
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                ORDER BY l.created_at ASC
            """)

            # Convert to expected format
            result: List[Dict[str, Any]] = []
            for row in lists:
                # Show folder context in description if item is in a folder
                folder_context = f" ({row['folder_name']})" if row['folder_name'] else ""

                result.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "description": f"{row['item_count']} items{folder_context}",
                    "item_count": row['item_count'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                    "modified": row['updated_at'][:10] if row['updated_at'] else '',
                    "folder_name": row['folder_name']
                })

            self.logger.debug(f"Retrieved {len(result)} lists")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get user lists: {e}")
            return []

    def get_list_items(self, list_id, limit=100, offset=0):
        """Get items from a specific list with paging, normalized to canonical format"""
        try:
            self.logger.debug(f"Getting list items for list_id={list_id}, limit={limit}, offset={offset}")

            connection = self.connection_manager.get_connection()
            cursor = connection.cursor()

            # Use unified lists/list_items structure
            query = """
                SELECT 
                    li.media_item_id as id,
                    li.media_item_id as item_id,
                    li.position as order_score,
                    mi.kodi_id,
                    mi.media_type,
                    mi.title,
                    mi.year,
                    mi.imdbnumber as imdb_id,
                    mi.art as data_json
                FROM list_items li
                JOIN media_items mi ON li.media_item_id = mi.id
                WHERE li.list_id = ?
                ORDER BY li.position ASC, mi.title ASC
                LIMIT ? OFFSET ?
            """

            self.logger.debug(f"Executing query: {query}")
            self.logger.debug(f"Query parameters: list_id={list_id}, limit={limit}, offset={offset}")

            cursor.execute(query, (list_id, limit, offset))
            rows = cursor.fetchall()

            self.logger.debug(f"Query returned {len(rows)} rows")

            items = []

            for row_idx, row in enumerate(rows):
                # Convert row to dict
                item = dict(row)

                # Parse JSON data if present
                if item.get('data_json'):
                    try:
                        json_data = json.loads(item['data_json'])
                        self.logger.debug(f"Parsed JSON data: {json_data}")
                        item.update(json_data)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse JSON data: {e}")

                # Enrich with Kodi data if available
                if item.get('kodi_id') and item.get('media_type') in ['movie', 'episode']:
                    # Enrich with Kodi data
                    enriched_item = self._enrich_with_kodi_data([item])[0]

                    # Normalize to canonical format
                    canonical_item = self._normalize_to_canonical(enriched_item)
                else:
                    # Normalize to canonical format
                    canonical_item = self._normalize_to_canonical(item)

                items.append(canonical_item)

            return items

        except Exception as e:
            self.logger.error(f"Error getting list items: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def create_list(self, name, description="", folder_id=None):
        """Create a new list in unified lists table with proper validation"""
        if not name or not name.strip():
            self.logger.warning("Attempted to create list with empty name")
            return {"error": "empty_name"}

        name = name.strip()

        try:
            self.logger.debug(f"Creating list '{name}' in folder {folder_id}")

            with self.connection_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO lists (name, folder_id) VALUES (?, ?)
                """, [name, folder_id])

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

    def add_item_to_list(self, list_id, title, year=None, imdb_id=None, tmdb_id=None, kodi_id=None):
        """Add an item to a list using unified tables structure"""
        try:
            self.logger.debug(f"Adding '{title}' to list {list_id}")

            with self.connection_manager.transaction() as conn:
                # Create media item data
                media_data = {
                    'media_type': 'movie',
                    'title': title,
                    'year': year,
                    'imdbnumber': imdb_id,
                    'tmdb_id': tmdb_id,
                    'kodi_id': kodi_id,
                    'source': 'manual',
                    'play': '',
                    'poster': '',
                    'fanart': '',
                    'plot': '',
                    'rating': 0.0,
                    'votes': 0,
                    'duration': 0,
                    'mpaa': '',
                    'genre': '',
                    'director': '',
                    'studio': '',
                    'country': '',
                    'writer': '',
                    'cast': '',
                    'art': ''
                }

                # Insert or get media item
                media_item_id = self._insert_or_get_media_item(conn, media_data)

                if not media_item_id:
                    return None

                # Get next position
                position_result = conn.execute("""
                    SELECT COALESCE(MAX(position), -1) + 1 as next_position 
                    FROM list_items WHERE list_id = ?
                """, [int(list_id)]).fetchone()
                next_position = position_result['next_position'] if position_result else 0

                # Add to list
                conn.execute("""
                    INSERT OR IGNORE INTO list_items (list_id, media_item_id, position)
                    VALUES (?, ?, ?)
                """, [int(list_id), media_item_id, next_position])

            return {
                "id": str(media_item_id),
                "title": title,
                "year": year,
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id
            }

        except Exception as e:
            self.logger.error(f"Failed to add item '{title}' to list {list_id}: {e}")
            return None

    def count_list_items(self, list_id):
        """Count items in a specific list using unified table"""
        try:
            result = self.connection_manager.execute_single("""
                SELECT COUNT(*) as count FROM list_items WHERE list_id = ?
            """, [int(list_id)])

            return result['count'] if result else 0

        except Exception as e:
            self.logger.error(f"Failed to count items in list {list_id}: {e}")
            return 0

    def delete_item_from_list(self, list_id, item_id):
        """Delete an item from a list using unified tables"""
        try:
            self.logger.debug(f"Deleting item {item_id} from list {list_id}")

            with self.connection_manager.transaction() as conn:
                # Delete from list_items (item_id is media_item_id in unified structure)
                conn.execute("""
                    DELETE FROM list_items 
                    WHERE media_item_id = ? AND list_id = ?
                """, [int(item_id), int(list_id)])

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete item {item_id} from list {list_id}: {e}")
            return False

    def rename_list(self, list_id, new_name):
        """Rename a list with validation using unified lists table"""
        if not new_name or not new_name.strip():
            self.logger.warning("Attempted to rename list with empty name")
            return {"error": "empty_name"}

        new_name = new_name.strip()

        try:
            self.logger.debug(f"Renaming list {list_id} to '{new_name}'")

            with self.connection_manager.transaction() as conn:
                # Check if list exists
                existing = conn.execute(
                    "SELECT name, folder_id FROM lists WHERE id = ?", [int(list_id)]
                ).fetchone()

                if not existing:
                    return {"error": "list_not_found"}

                # Update the list name
                conn.execute("""
                    UPDATE lists 
                    SET name = ?
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
        """Delete a list and cascade delete its items using unified tables"""
        try:
            self.logger.debug(f"Deleting list {list_id}")

            with self.connection_manager.transaction() as conn:
                # Check if list exists
                existing = conn.execute(
                    "SELECT name FROM lists WHERE id = ?", [int(list_id)]
                ).fetchone()

                if not existing:
                    return {"error": "list_not_found"}

                # Delete list (items cascade automatically via foreign key)
                conn.execute("DELETE FROM lists WHERE id = ?", [int(list_id)])

            return {"success": True}

        except Exception as e:
            self.logger.error(f"Failed to delete list {list_id}: {e}")
            return {"error": "database_error"}

    def get_list_by_id(self, list_id):
        """Get list information by ID"""
        try:
            with self.connection_manager.transaction() as conn:
                result = conn.execute("""
                    SELECT l.id, l.name, l.folder_id, l.created_at,
                           f.name as folder_name,
                           COUNT(li.id) as item_count
                    FROM lists l
                    LEFT JOIN folders f ON l.folder_id = f.id
                    LEFT JOIN list_items li ON l.id = li.list_id
                    WHERE l.id = ?
                    GROUP BY l.id, l.name, l.folder_id, l.created_at, f.name
                """, [int(list_id)]).fetchone()

                if result:
                    folder_context = f" ({result['folder_name']})" if result['folder_name'] else ""
                    return {
                        "id": str(result['id']),
                        "name": result['name'],
                        "description": f"{result['item_count']} items{folder_context}",
                        "item_count": result['item_count'],
                        "created": result['created_at'][:10] if result['created_at'] else '',
                        "modified": result['created_at'][:10] if result['created_at'] else '',
                        "folder_name": result['folder_name']
                    }
                return None

        except Exception as e:
            self.logger.error(f"Error getting list by ID {list_id}: {e}")
            return None

    def get_list_by_name(self, list_name):
        """Get list information by name"""
        try:
            with self.connection_manager.transaction() as conn:
                result = conn.execute("""
                    SELECT l.id, l.name, l.folder_id, l.created_at,
                           f.name as folder_name,
                           COUNT(li.id) as item_count
                    FROM lists l
                    LEFT JOIN folders f ON l.folder_id = f.id
                    LEFT JOIN list_items li ON l.id = li.list_id
                    WHERE l.name = ?
                    GROUP BY l.id, l.name, l.folder_id, l.created_at, f.name
                """, [list_name]).fetchone()

                if result:
                    folder_context = f" ({result['folder_name']})" if result['folder_name'] else ""
                    return {
                        "id": str(result['id']),
                        "name": result['name'],
                        "description": f"{result['item_count']} items{folder_context}",
                        "item_count": result['item_count'],
                        "created": result['created_at'][:10] if result['created_at'] else '',
                        "modified": result['created_at'][:10] if result['created_at'] else '',
                        "folder_name": result['folder_name']
                    }
                return None

        except Exception as e:
            self.logger.error(f"Error getting list by name '{list_name}': {e}")
            return None


    def _ensure_default_list(self):
        """Default list creation disabled - users create their own lists"""
        pass

    def get_or_create_search_history_folder(self):
        """Get or create the Search History folder"""
        try:
            # Check if Search History folder exists
            folder = self.connection_manager.execute_single("""
                SELECT id FROM folders WHERE name = ? AND parent_id IS NULL
            """, ["Search History"])

            if folder:
                return folder['id']

            # Create Search History folder with INSERT OR IGNORE to handle duplicates
            self.logger.debug("Creating Search History folder")
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO folders (name, parent_id)
                    VALUES (?, ?)
                """, ["Search History", None])

                # If no rows were inserted (folder already existed), get the existing ID
                if cursor.rowcount == 0:
                    existing = conn.execute("""
                        SELECT id FROM folders WHERE name = ? AND parent_id IS NULL
                    """, ["Search History"]).fetchone()
                    if existing:
                        return existing['id']
                    else:
                        self.logger.error("Failed to find or create Search History folder")
                        return None
                else:
                    folder_id = cursor.lastrowid
                    self.logger.debug(f"Created Search History folder with ID: {folder_id}")
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
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO lists (name, folder_id)
                    VALUES (?, ?)
                """, [list_name, folder_id])
                list_id = cursor.lastrowid

                self.logger.debug(f"Created search history list '{list_name}' with ID: {list_id}")
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

            with self.connection_manager.transaction() as conn:
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

            self.logger.debug(f"Added {added_count} items to search history list {list_id}")
            return added_count

        except Exception as e:
            self.logger.error(f"Failed to add search results to list: {e}")
            return 0

    def remove_item_from_list(self, list_id, item_id):
        """Remove an item from a list"""
        try:
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute("""
                    DELETE FROM list_items 
                    WHERE list_id = ? AND media_item_id = ?
                """, [list_id, item_id])

                removed_count = cursor.rowcount

                if removed_count > 0:
                    self.logger.debug(f"Removed {removed_count} item(s) from list {list_id}")
                    return {"success": True, "removed_count": removed_count}
                else:
                    self.logger.warning(f"No items found to remove from list {list_id} with item_id {item_id}")
                    return {"error": "item_not_found"}

        except Exception as e:
            self.logger.error(f"Failed to remove item from list: {e}")
            return {"error": str(e)}


    def _extract_media_item_data(self, item):
        """Extract standardized media item data from various sources, normalized to canonical format"""
        # First create a basic item dict
        basic_item = {
            'kodi_id': int(item['kodi_id']) if item.get('kodi_id') else None,
            'media_type': item.get('media_type', item.get('type', 'movie')),
            'title': item.get('title', ''),
            'year': int(item.get('year', 0)) if item.get('year') else 0,
            'imdb_id': item.get('imdb_id', ''),
            'source': item.get('source', 'search'),
            'runtime': item.get('runtime', item.get('duration', 0)),
            'art': item.get('art', {}),
            'resume': item.get('resume', {})
        }

        # Add any additional fields from the original item
        for key, value in item.items():
            if key not in basic_item:
                basic_item[key] = value

        # Normalize to canonical format
        return self._normalize_to_canonical(basic_item)

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
        """Get all lists with their folder information"""
        try:
            # Get all lists with folder names
            query = """
                SELECT 
                    l.id,
                    l.name,
                    COUNT(li.id) as item_count,
                    date(l.created_at) as created,
                    date(l.created_at) as modified,
                    COALESCE(f.name, 'Root') as folder_name,
                    CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END as is_folder
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                LEFT JOIN list_items li ON l.id = li.list_id
                GROUP BY l.id, l.name, l.created_at, f.name, f.id
                ORDER BY 
                    CASE WHEN f.name = 'Search History' THEN 0 ELSE 1 END,
                    CASE WHEN f.name IS NULL THEN 1 ELSE 0 END,
                    f.name, 
                    l.created_at DESC
            """

            results = self.connection_manager.execute_query(query)

            if results:
                # Convert to list of dicts for easier handling
                formatted_results = []
                for row in results:
                    row_dict = dict(row)
                    # Ensure string conversion for compatibility
                    row_dict['id'] = str(row_dict['id'])
                    # Add description based on item count and folder
                    folder_context = f" ({row_dict['folder_name']})" if row_dict['folder_name'] != 'Root' else ""
                    row_dict['description'] = f"{row_dict['item_count']} items{folder_context}"
                    formatted_results.append(row_dict)

                self.logger.debug(f"Retrieved {len(formatted_results)} lists with folders")
                return formatted_results

            return []

        except Exception as e:
            self.logger.error(f"Failed to get lists with folders: {e}")
            return []

    def _get_kodi_episode_enrichment_data_batch(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch lightweight episode metadata from Kodi JSON-RPC using proper batch requests"""
        try:
            import json
            import xbmc

            if not kodi_ids:
                return {}

            # Build batch request array - multiple GetEpisodeDetails calls in one request
            batch_requests = []
            for i, kodi_id in enumerate(kodi_ids):
                request = {
                    "jsonrpc": "2.0",
                    "method": "VideoLibrary.GetEpisodeDetails",
                    "params": {
                        "episodeid": int(kodi_id),
                        "properties": [
                            'title', 'season', 'episode', 'showtitle', 'plot', 'runtime',
                            'rating', 'votes', 'aired', 'art', 'playcount', 'lastplayed',
                            'tvshowid', 'resume'
                        ]
                    },
                    "id": i + 1  # Unique ID for each request in the batch
                }
                batch_requests.append(request)

            # Send single batch request
            response_str = xbmc.executeJSONRPC(json.dumps(batch_requests))
            responses = json.loads(response_str)

            # Process batch responses
            enrichment_data = {}

            # Handle single response (when only one item in batch) vs array of responses
            if not isinstance(responses, list):
                responses = [responses]

            for i, response in enumerate(responses):
                if i >= len(kodi_ids):  # Safety check
                    break

                kodi_id = kodi_ids[i]

                try:
                    if "error" in response:
                        self.logger.warning(f"Batch enrichment error for episode {kodi_id}: {response['error']}")
                        continue

                    episode_details = response.get("result", {}).get("episodedetails")
                    if episode_details:
                        normalized = self._normalize_kodi_episode_details(episode_details)
                        if normalized:
                            enrichment_data[kodi_id] = normalized

                except Exception as e:
                    self.logger.error(f"Failed to process batch response for episode {kodi_id}: {e}")
                    continue

            self.logger.debug(f"Batch enriched {len(enrichment_data)} out of {len(kodi_ids)} episodes")
            return enrichment_data

        except Exception as e:
            self.logger.error(f"Error in batch episode enrichment: {e}")
            return {}

    def _get_kodi_episode_enrichment_data(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch lightweight episode metadata from Kodi JSON-RPC"""
        try:
            import json
            import xbmc

            if not kodi_ids:
                return {}

            self.logger.info(f"Fetching episode JSON-RPC data for {len(kodi_ids)} episodes: {kodi_ids}")

            enrichment_data = {}

            # Define which properties to fetch for each media type
            # Keep property sets "light" but include resume for movies/episodes
            properties = {
                'movies': [
                    'title', 'year', 'genre', 'plot', 'runtime', 'rating', 'votes', 
                    'mpaa', 'studio', 'country', 'premiered', 'art', 'playcount', 
                    'lastplayed', 'originaltitle', 'sorttitle', 'resume'
                ],
                'episodes': [
                    'title', 'season', 'episode', 'showtitle', 'plot', 'runtime',
                    'rating', 'votes', 'aired', 'art', 'playcount', 'lastplayed',
                    'tvshowid', 'resume'
                ],
                'tvshows': [
                    'title', 'year', 'genre', 'plot', 'rating', 'votes', 'mpaa',
                    'studio', 'premiered', 'art', 'playcount', 'lastplayed'
                ]
            }

            for kodi_id in kodi_ids:
                try:
                    request = {
                        "jsonrpc": "2.0",
                        "method": "VideoLibrary.GetEpisodeDetails",
                        "params": {
                            "episodeid": int(kodi_id),
                            "properties": properties.get('episodes', [])
                        },
                        "id": 1
                    }

                    response_str = xbmc.executeJSONRPC(json.dumps(request))
                    response = json.loads(response_str)

                    if "error" in response:
                        self.logger.warning(f"JSON-RPC error for episode {kodi_id}: {response['error']}")
                        continue

                    episode_details = response.get("result", {}).get("episodedetails")
                    if episode_details:
                        normalized = self._normalize_kodi_episode_details(episode_details)
                        if normalized:
                            enrichment_data[kodi_id] = normalized

                except Exception as e:
                    self.logger.error(f"Failed to fetch details for episode {kodi_id}: {e}")
                    continue

            return enrichment_data

        except Exception as e:
            self.logger.error(f"Error fetching episode enrichment data: {e}")
            return {}

    def _get_kodi_enrichment_data_batch(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch rich metadata from Kodi JSON-RPC for multiple movies using proper batch requests"""
        try:
            import json
            import xbmc

            if not kodi_ids:
                return {}

            # Build batch request array - multiple GetMovieDetails calls in one request
            batch_requests = []
            for i, kodi_id in enumerate(kodi_ids):
                request = {
                    "jsonrpc": "2.0",
                    "method": "VideoLibrary.GetMovieDetails",
                    "params": {
                        "movieid": int(kodi_id),
                        "properties": [
                            'title', 'year', 'genre', 'plot', 'runtime', 'rating', 'votes', 
                            'mpaa', 'studio', 'country', 'premiered', 'art', 'playcount', 
                            'lastplayed', 'originaltitle', 'sorttitle', 'resume'
                        ]
                    },
                    "id": i + 1  # Unique ID for each request in the batch
                }
                batch_requests.append(request)

            # Send single batch request
            response_str = xbmc.executeJSONRPC(json.dumps(batch_requests))
            responses = json.loads(response_str)

            # Process batch responses
            enrichment_data = {}

            # Handle single response (when only one item in batch) vs array of responses
            if not isinstance(responses, list):
                responses = [responses]

            for i, response in enumerate(responses):
                if i >= len(kodi_ids):  # Safety check
                    break

                kodi_id = kodi_ids[i]

                try:
                    if "error" in response:
                        self.logger.warning(f"Batch enrichment error for movie {kodi_id}: {response['error']}")
                        continue

                    movie_details = response.get("result", {}).get("moviedetails")
                    if movie_details:
                        normalized = self._normalize_kodi_movie_details(movie_details)
                        if normalized:
                            enrichment_data[kodi_id] = normalized

                except Exception as e:
                    self.logger.error(f"Failed to process batch response for movie {kodi_id}: {e}")
                    continue

            self.logger.debug(f"Batch enriched {len(enrichment_data)} out of {len(kodi_ids)} movies")
            return enrichment_data

        except Exception as e:
            self.logger.error(f"Error in batch movie enrichment: {e}")
            return {}

    def _get_kodi_enrichment_data(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch rich metadata from Kodi JSON-RPC for the given kodi_ids"""
        try:
            import json
            import xbmc

            if not kodi_ids:
                return {}

            self.logger.info(f"Fetching JSON-RPC data for {len(kodi_ids)} movies: {kodi_ids}")

            enrichment_data = {}

            # Define which properties to fetch for each media type
            # Keep property sets "light" but include resume for movies/episodes
            properties = {
                'movies': [
                    'title', 'year', 'genre', 'plot', 'runtime', 'rating', 'votes', 
                    'mpaa', 'studio', 'country', 'premiered', 'art', 'playcount', 
                    'lastplayed', 'originaltitle', 'sorttitle', 'resume'
                ],
                'episodes': [
                    'title', 'season', 'episode', 'showtitle', 'plot', 'runtime',
                    'rating', 'votes', 'aired', 'art', 'playcount', 'lastplayed',
                    'tvshowid', 'resume'
                ],
                'tvshows': [
                    'title', 'year', 'genre', 'plot', 'rating', 'votes', 'mpaa',
                    'studio', 'premiered', 'art', 'playcount', 'lastplayed'
                ]
            }

            # Fetch data for each movie
            for kodi_id in kodi_ids:
                try:
                    request = {
                        "jsonrpc": "2.0",
                        "method": "VideoLibrary.GetMovieDetails",
                        "params": {
                            "movieid": int(kodi_id),
                            "properties": properties.get('movies', [])
                        },
                        "id": 1
                    }

                    self.logger.debug(f"JSON-RPC request for movie {kodi_id}: {json.dumps(request)}")
                    response_str = xbmc.executeJSONRPC(json.dumps(request))
                    self.logger.debug(f"JSON-RPC response for movie {kodi_id}: {response_str[:200]}...")
                    response = json.loads(response_str)

                    if "error" in response:
                        self.logger.warning(f"JSON-RPC error for movie {kodi_id}: {response['error']}")
                        continue

                    movie_details = response.get("result", {}).get("moviedetails")
                    if movie_details:
                        self.logger.debug(f"Got movie details for {kodi_id}: {movie_details.get('title', 'Unknown')}")
                        # Normalize the movie data similar to how json_rpc_client does it
                        normalized = self._normalize_kodi_movie_details(movie_details)
                        if normalized:
                            enrichment_data[kodi_id] = normalized
                            self.logger.info(f"Successfully enriched movie {kodi_id}: {normalized.get('title')}")
                        else:
                            self.logger.warning(f"Failed to normalize movie details for {kodi_id}")
                    else:
                        self.logger.warning(f"No moviedetails found in response for {kodi_id}")

                except Exception as e:
                    self.logger.error(f"Failed to fetch details for movie {kodi_id}: {e}")
                    import traceback
                    self.logger.error(f"Enrichment error traceback: {traceback.format_exc()}")
                    continue

            self.logger.info(f"Successfully enriched {len(enrichment_data)} out of {len(kodi_ids)} movies")
            return enrichment_data

        except Exception as e:
            self.logger.error(f"Error fetching Kodi enrichment data: {e}")
            import traceback
            self.logger.error(f"Enrichment error traceback: {traceback.format_exc()}")
            return {}

    def _enrich_with_kodi_data(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich items with data from Kodi JSON-RPC if kodi_id is available"""
        if not items:
            return []

        # Separate movie and episode IDs, removing duplicates
        movie_ids = list(set([item['kodi_id'] for item in items if item.get('kodi_id') and item.get('media_type') == 'movie']))
        episode_ids = list(set([item['kodi_id'] for item in items if item.get('kodi_id') and item.get('media_type') == 'episode']))

        enriched_data = {}

        # Only fetch if we have IDs to process
        if movie_ids:
            movie_data = self._get_kodi_enrichment_data_batch(movie_ids)
            enriched_data.update(movie_data)

        if episode_ids:
            episode_data = self._get_kodi_episode_enrichment_data_batch(episode_ids)
            enriched_data.update(episode_data)

        # Apply enriched data to items
        enriched_items = []
        for item in items:
            kodi_id = item.get('kodi_id')
            if kodi_id and kodi_id in enriched_data:
                # Merge enriched data, prioritizing enriched fields
                enriched_item = enriched_data[kodi_id].copy()
                # Update item with enriched data, but keep original if enriched value is empty/default
                for key, value in enriched_item.items():
                    if value is not None and value != "" and value != 0 and value != 0.0:
                         item[key] = value
                item['source'] = 'lib'  # Mark as library item
                enriched_items.append(item)
            else:
                enriched_items.append(item) # Keep original item if no enrichment found

        return enriched_items


    def _match_items_to_kodi_library(self, items_to_match: List[tuple]) -> Dict[int, Optional[int]]:
        """Try to match items without kodi_id to Kodi library movies"""
        try:
            from ..kodi.json_rpc_client import get_kodi_client
            kodi_client = get_kodi_client()

            # Get a quick list of all movies in library
            library_movies = kodi_client.get_movies_quick_check()
            if not library_movies:
                self.logger.debug("No movies found in Kodi library for matching")
                return {}

            # Get full movie details for matching
            library_data = kodi_client.get_movies(limit=1000)  # Get a reasonable chunk
            if not library_data or not library_data.get('movies'):
                self.logger.debug("No detailed movie data available for matching")
                return {}

            matched_ids = {}

            for item_index, item_data in items_to_match:
                matched_kodi_id = None
                item_title = (item_data.get('title') or '').lower().strip()
                item_year = item_data.get('year')
                item_imdb = (item_data.get('imdb_id') or '').strip()

                self.logger.debug(f"Trying to match: {item_title} ({item_year}) IMDb: {item_imdb}")

                # Try to find a match in the library
                for library_movie in library_data['movies']:
                    library_title = (library_movie.get('title') or '').lower().strip()
                    library_year = library_movie.get('year')
                    library_imdb = (library_movie.get('imdb_id') or '').strip()

                    # Match by IMDb ID (most reliable)
                    if item_imdb and library_imdb and item_imdb == library_imdb:
                        matched_kodi_id = library_movie.get('kodi_id')
                        self.logger.debug(f"IMDb match: {item_title} -> kodi_id {matched_kodi_id}")
                        break

                    # Match by title and year
                    elif (item_title and library_title and 
                          item_title == library_title and 
                          item_year and library_year and 
                          int(item_year) == int(library_year)):
                        matched_kodi_id = library_movie.get('kodi_id')
                        self.logger.debug(f"Title/Year match: {item_title} ({item_year}) -> kodi_id {matched_kodi_id}")
                        break

                matched_ids[item_index] = matched_kodi_id
                if not matched_kodi_id:
                    self.logger.debug(f"No match found for: {item_title} ({item_year})")

            return matched_ids

        except Exception as e:
            self.logger.error(f"Error matching items to Kodi library: {e}")
            return {}

    def add_library_item_to_list(self, list_id, kodi_item):
        """Add a Kodi library item to a list using unified structure"""
        try:
            # Normalize the item first
            canonical_item = self._normalize_to_canonical(kodi_item)

            # Extract basic fields for media_items table
            media_data = {
                'media_type': canonical_item['media_type'],
                'title': canonical_item['title'],
                'year': canonical_item['year'],
                'imdbnumber': canonical_item.get('imdb_id', ''),
                'tmdb_id': canonical_item.get('tmdb_id', ''),
                'kodi_id': canonical_item.get('kodi_id'),
                'source': 'lib',
                'play': '',
                'poster': canonical_item.get('poster', ''),
                'fanart': canonical_item.get('fanart', ''),
                'plot': canonical_item.get('plot', ''),
                'rating': canonical_item.get('rating', 0.0),
                'votes': canonical_item.get('votes', 0),
                'duration': canonical_item.get('duration_minutes', 0),
                'mpaa': canonical_item.get('mpaa', ''),
                'genre': canonical_item.get('genre', ''),
                'director': canonical_item.get('director', ''),
                'studio': canonical_item.get('studio', ''),
                'country': canonical_item.get('country', ''),
                'writer': canonical_item.get('writer', ''),
                'cast': '',
                'art': json.dumps(canonical_item.get('art', {}))
            }

            self.logger.debug(f"Adding library item '{canonical_item['title']}' to list {list_id}")

            with self.connection_manager.transaction() as conn:
                # Insert or get media item
                media_item_id = self._insert_or_get_media_item(conn, media_data)

                if not media_item_id:
                    return None

                # Get next position
                position_result = conn.execute("""
                    SELECT COALESCE(MAX(position), -1) + 1 as next_position 
                    FROM list_items WHERE list_id = ?
                """, [int(list_id)]).fetchone()
                next_position = position_result['next_position'] if position_result else 0

                # Add to list
                conn.execute("""
                    INSERT OR IGNORE INTO list_items (list_id, media_item_id, position)
                    VALUES (?, ?, ?)
                """, [int(list_id), media_item_id, next_position])

            return {
                "id": str(media_item_id),
                "title": canonical_item['title'],
                "year": canonical_item['year']
            }

        except Exception as e:
            self.logger.error(f"Failed to add library item to list {list_id}: {e}")
            return None

    def _row_to_dict(self, cursor, row):
        """Convert SQLite row to dictionary using cursor description"""
        if not row:
            return {}

        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

    def _normalize_kodi_episode_details(self, episode_details: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Kodi JSON-RPC episode details to canonical format"""
        # Extract resume data properly
        resume_data = episode_details.get("resume", {})
        resume = {
            "position_seconds": int(resume_data.get("position", 0)),
            "total_seconds": int(resume_data.get("total", 0))
        }

        # Build item dict for normalization
        item = {
            "kodi_id": episode_details.get("episodeid"),
            "media_type": "episode",
            "title": episode_details.get("title", ""),
            "tvshowtitle": episode_details.get("showtitle", ""),
            "season": episode_details.get("season", 0),
            "episode": episode_details.get("episode", 0),
            "aired": episode_details.get("aired", ""),
            "plot": episode_details.get("plot", episode_details.get("plotoutline", "")),
            "rating": episode_details.get("rating", 0.0),
            "playcount": episode_details.get("playcount", 0),
            "lastplayed": episode_details.get("lastplayed", ""),
            "runtime": episode_details.get("runtime", 0),  # Will be converted to minutes
            "art": episode_details.get("art", {}),
            "resume": resume
        }

        return self._normalize_to_canonical(item)

    def _normalize_kodi_movie_details(self, movie_details: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Kodi JSON-RPC movie details to canonical format"""
        # Extract resume data properly
        resume_data = movie_details.get("resume", {})
        resume = {
            "position_seconds": int(resume_data.get("position", 0)),
            "total_seconds": int(resume_data.get("total", 0))
        }

        # Build item dict for normalization
        item = {
            "kodi_id": movie_details.get("movieid"),
            "media_type": "movie",
            "title": movie_details.get("title", ""),
            "originaltitle": movie_details.get("originaltitle", ""),
            "sorttitle": movie_details.get("sorttitle", ""),
            "year": movie_details.get("year", 0),
            "genre": ", ".join(movie_details.get("genre", [])) if isinstance(movie_details.get("genre"), list) else str(movie_details.get("genre", "")),
            "plot": movie_details.get("plot", movie_details.get("plotoutline", "")),
            "rating": movie_details.get("rating", 0.0),
            "votes": movie_details.get("votes", 0),
            "mpaa": movie_details.get("mpaa", ""),
            "runtime": movie_details.get("runtime", 0),  # Runtime from JSON-RPC is in minutes
            "studio": ", ".join(movie_details.get("studio", [])) if isinstance(movie_details.get("studio"), list) else str(movie_details.get("studio", "")),
            "country": ", ".join(movie_details.get("country", [])) if isinstance(movie_details.get("country"), list) else str(movie_details.get("country", "")),
            "premiered": movie_details.get("premiered", movie_details.get("dateadded", "")),
            "art": movie_details.get("art", {}),
            "resume": resume
        }

        return self._normalize_to_canonical(item)

    def detect_content_type(self, items: List[Dict[str, Any]]) -> str:
        """
        Detect the primary content type for a list of items

        Args:
            items: List of media items

        Returns:
            str: "movies", "tvshows", or "episodes"
        """
        if not items:
            return "movies"

        # Count media types
        type_counts = {}
        for item in items:
            media_type = item.get('media_type', 'movie')
            type_counts[media_type] = type_counts.get(media_type, 0) + 1

        # Return the most common type, with fallback logic
        if not type_counts:
            return "movies"

        most_common = max(type_counts.items(), key=lambda x: x[1])[0]

        # Map to Kodi content types
        type_mapping = {
            'movie': 'movies',
            'episode': 'episodes',
            'tvshow': 'tvshows',
            'musicvideo': 'musicvideos',
            'external': 'movies'  # Default external items to movies
        }

        return type_mapping.get(most_common, 'movies')

    def create_folder(self, name, parent_id=None):
        """Create a new folder"""
        try:
            # Validate name
            if not name or not name.strip():
                return {"success": False, "error": "invalid_name", "message": "Folder name cannot be empty"}

            name = name.strip()

            # Check for reserved names
            if name in self.RESERVED_FOLDERS:
                return {"success": False, "error": "reserved_name", "message": "Folder name is reserved"}

            # Check for duplicate names in same parent
            existing = self.connection_manager.execute_single("""
                SELECT id FROM folders WHERE name = ? AND parent_id IS ?
            """, [name, parent_id])

            if existing:
                return {"success": False, "error": "duplicate", "message": "Folder name already exists"}

            # Create folder
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO folders (name, parent_id)
                    VALUES (?, ?)
                """, [name, parent_id])
                folder_id = cursor.lastrowid

            self.logger.debug(f"Created folder '{name}' with ID: {folder_id}")
            return {"success": True, "folder_id": folder_id}

        except Exception as e:
            self.logger.error(f"Failed to create folder: {e}")
            return {"success": False, "error": "database_error", "message": str(e)}

    def rename_folder(self, folder_id, new_name):
        """Rename a folder"""
        try:
            # Check if folder is reserved
            if self.is_reserved_folder(folder_id):
                return {"success": False, "error": "reserved", "message": "Cannot rename reserved folder"}

            # Validate name
            if not new_name or not new_name.strip():
                return {"success": False, "error": "invalid_name", "message": "Folder name cannot be empty"}

            new_name = new_name.strip()

            # Check for reserved names
            if new_name in self.RESERVED_FOLDERS:
                return {"success": False, "error": "reserved_name", "message": "Folder name is reserved"}

            # Get current folder info
            folder = self.connection_manager.execute_single("""
                SELECT name, parent_id FROM folders WHERE id = ?
            """, [folder_id])

            if not folder:
                return {"success": False, "error": "not_found", "message": "Folder not found"}

            # Check for duplicate names in same parent
            existing = self.connection_manager.execute_single("""
                SELECT id FROM folders WHERE name = ? AND parent_id IS ? AND id != ?
            """, [new_name, folder['parent_id'], folder_id])

            if existing:
                return {"success": False, "error": "duplicate", "message": "Folder name already exists"}

            # Rename folder
            with self.connection_manager.transaction() as conn:
                conn.execute("""
                    UPDATE folders SET name = ? WHERE id = ?
                """, [new_name, folder_id])

            self.logger.debug(f"Renamed folder {folder_id} from '{folder['name']}' to '{new_name}'")
            return {"success": True}

        except Exception as e:
            self.logger.error(f"Failed to rename folder: {e}")
            return {"success": False, "error": "database_error", "message": str(e)}

    def delete_folder(self, folder_id):
        """Delete a folder (must be empty)"""
        try:
            # Check if folder is reserved
            if self.is_reserved_folder(folder_id):
                return {"success": False, "error": "reserved", "message": "Cannot delete reserved folder"}

            # Check if folder exists
            folder = self.connection_manager.execute_single("""
                SELECT name FROM folders WHERE id = ?
            """, [folder_id])

            if not folder:
                return {"success": False, "error": "not_found", "message": "Folder not found"}

            # Check if folder has lists
            lists_count = self.connection_manager.execute_single("""
                SELECT COUNT(*) as count FROM lists WHERE folder_id = ?
            """, [folder_id])

            if lists_count and lists_count['count'] > 0:
                return {"success": False, "error": "not_empty", "message": "Folder contains lists"}

            # Check if folder has subfolders
            subfolders_count = self.connection_manager.execute_single("""
                SELECT COUNT(*) as count FROM folders WHERE parent_id = ?
            """, [folder_id])

            if subfolders_count and subfolders_count['count'] > 0:
                return {"success": False, "error": "not_empty", "message": "Folder contains subfolders"}

            # Delete folder
            with self.connection_manager.transaction() as conn:
                conn.execute("DELETE FROM folders WHERE id = ?", [folder_id])

            self.logger.debug(f"Deleted folder '{folder['name']}' (ID: {folder_id})")
            return {"success": True}

        except Exception as e:
            self.logger.error(f"Failed to delete folder: {e}")
            return {"success": False, "error": "database_error", "message": str(e)}

    def is_reserved_folder(self, folder_id):
        """Check if a folder is reserved"""
        try:
            folder = self.connection_manager.execute_single("""
                SELECT name FROM folders WHERE id = ?
            """, [folder_id])

            if folder and folder['name'] in self.RESERVED_FOLDERS:
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to check if folder {folder_id} is reserved: {e}")
            return False

    def get_lists_in_folder(self, folder_id):
        """Get all lists within a specific folder"""
        try:
            self.logger.debug(f"Getting lists in folder {folder_id}")

            lists = self.connection_manager.execute_query("""
                SELECT 
                    l.id,
                    l.name,
                    l.created_at,
                    l.created_at as updated_at,
                    (SELECT COUNT(*) FROM list_items WHERE list_id = l.id) as item_count,
                    f.name as folder_name
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                WHERE l.folder_id = ?
                ORDER BY l.created_at DESC
            """, [int(folder_id)])

            # Convert to expected format
            result = []
            for row in lists:
                folder_context = f" ({row['folder_name']})" if row['folder_name'] else ""

                result.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "description": f"{row['item_count']} items{folder_context}",
                    "item_count": row['item_count'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                    "modified": row['updated_at'][:10] if row['updated_at'] else '',
                    "folder_name": row['folder_name']
                })

            self.logger.debug(f"Retrieved {len(result)} lists in folder {folder_id}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get lists in folder {folder_id}: {e}")
            return []

    def get_folder_by_id(self, folder_id):
        """Get folder information by ID"""
        try:
            result = self.connection_manager.execute_single("""
                SELECT 
                    f.id, f.name, f.created_at,
                    (SELECT COUNT(*) FROM lists WHERE folder_id = f.id) as list_count
                FROM folders f
                WHERE f.id = ?
            """, [int(folder_id)])

            if result:
                return {
                    "id": str(result['id']),
                    "name": result['name'],
                    "created": result['created_at'][:10] if result['created_at'] else '',
                    "item_count": result['list_count']  # For folders, this is the count of lists
                }

            return None

        except Exception as e:
            self.logger.error(f"Failed to get folder {folder_id}: {e}")
            return None

    def get_all_folders(self):
        """Get all folders with their list counts"""
        try:
            folders = self.connection_manager.execute_query("""
                SELECT 
                    f.id, f.name, f.created_at,
                    COUNT(l.id) as list_count
                FROM folders f
                LEFT JOIN lists l ON l.folder_id = f.id
                WHERE f.parent_id IS NULL
                GROUP BY f.id, f.name, f.created_at
                ORDER BY 
                    CASE WHEN f.name = 'Search History' THEN 0 ELSE 1 END,
                    f.name
            """)

            result = []
            for row in folders or []:
                result.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                    "list_count": row['list_count']
                })

            self.logger.debug(f"Retrieved {len(result)} folders")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get all folders: {e}")
            return []

    def close(self):
        """Close database connections"""
        self.connection_manager.close()

    def get_list_info(self, list_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a specific list"""
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT l.id, l.name, l.folder_id, l.created_at,
                           COUNT(li.id) as item_count
                    FROM lists l
                    LEFT JOIN list_items li ON l.id = li.list_id
                    WHERE l.id = ?
                    GROUP BY l.id, l.name, l.folder_id, l.created_at
                """, (list_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'name': row[1],
                        'folder_id': row[2],
                        'created_at': row[3],
                        'item_count': row[4]
                    }
                return None

        except Exception as e:
            self.logger.error(f"Error getting list info for {list_id}: {e}")
            return None

    def get_folder_info(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a specific folder"""
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT f.id, f.name, f.parent_id, f.created_at,
                           COUNT(DISTINCT l.id) as list_count,
                           COUNT(DISTINCT sf.id) as subfolder_count
                    FROM folders f
                    LEFT JOIN lists l ON f.id = l.folder_id
                    LEFT JOIN folders sf ON f.id = sf.parent_id
                    WHERE f.id = ?
                    GROUP BY f.id, f.name, f.parent_id, f.created_at
                """, (folder_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'name': row[1],
                        'parent_id': row[2],
                        'created_at': row[3],
                        'list_count': row[4],
                        'subfolder_count': row[5]
                    }
                return None

        except Exception as e:
            self.logger.error(f"Error getting folder info for {folder_id}: {e}")
            return None


# Global query manager instance
_query_manager_instance = None

def get_query_manager():
    """Get or create the global query manager instance"""
    global _query_manager_instance
    if _query_manager_instance is None:
        _query_manager_instance = QueryManager()
    return _query_manager_instance


def close():
    """Close database connections"""
    global _query_manager_instance
    if _query_manager_instance:
        _query_manager_instance.close()
        _query_manager_instance = None