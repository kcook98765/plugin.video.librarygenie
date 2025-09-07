#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Query Manager
Real SQLite-based data layer for list and item management
"""

import json
from typing import List, Dict, Any, Optional

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
        canonical["rating"] = float(item.get("rating") or 0.0)
        canonical["votes"] = int(item.get("votes") or 0)
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

        # Art normalization - use version-aware art storage
        from ..utils.kodi_version import get_kodi_major_version

        art = item.get("art", {})
        if not isinstance(art, dict):
            # Handle individual art fields
            art = {
                "poster": str(item.get("poster", item.get("thumbnail", ""))),
                "fanart": str(item.get("fanart", "")),
                "thumb": str(item.get("thumb", "")),
                "banner": str(item.get("banner", "")),
                "landscape": str(item.get("landscape", "")),
                "clearlogo": str(item.get("clearlogo", ""))
            }

        # Store art dict in format appropriate for current Kodi version
        kodi_major = get_kodi_major_version()
        canonical["art"] = self._format_art_for_kodi_version(art, kodi_major)

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

            # Use unified lists/list_items structure with comprehensive fields
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
                    mi.tmdb_id,
                    mi.plot,
                    mi.rating,
                    mi.votes,
                    mi.duration,
                    mi.mpaa,
                    mi.genre,
                    mi.director,
                    mi.studio,
                    mi.country,
                    mi.writer,
                    mi.art,
                    mi.play as file_path,
                    mi.source,
                    mi.created_at,
                    mi.updated_at
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

                # Use stored data from media_items - no more JSON-RPC enrichment needed
                # Parse additional data from stored fields
                if item.get('art') and isinstance(item['art'], str):
                    try:
                        item['art'] = json.loads(item['art'])
                    except json.JSONDecodeError:
                        item['art'] = {}

                # Normalize to canonical format using stored data
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

    def add_item_to_list(self, list_id, title, year=None, imdb_id=None, tmdb_id=None, kodi_id=None, art_data=None):
        """Add an item to a list using unified tables structure"""
        try:
            self.logger.debug(f"Adding '{title}' to list {list_id}")

            with self.connection_manager.transaction() as conn:
                # Create media item data with version-aware art storage
                from ..utils.kodi_version import get_kodi_major_version
                kodi_major = get_kodi_major_version()

                # Use provided art_data or empty dict
                art_dict = art_data or {}

                media_data = {
                    'media_type': 'movie',
                    'title': title,
                    'year': year,
                    'imdbnumber': imdb_id,
                    'tmdb_id': tmdb_id,
                    'kodi_id': kodi_id,
                    'source': 'manual',
                    'play': '',
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
                    'art': json.dumps(self._format_art_for_kodi_version(art_dict, kodi_major))
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
            result = self.connection_manager.execute_single("""
                SELECT l.id, l.name, l.folder_id, l.created_at,
                       f.name as folder_name,
                       COUNT(li.id) as item_count
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                LEFT JOIN list_items li ON l.id = li.list_id
                WHERE l.id = ?
                GROUP BY l.id, l.name, l.folder_id, l.created_at, f.name
            """, [int(list_id)])

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
            result = self.connection_manager.execute_single("""
                SELECT l.id, l.name, l.folder_id, l.created_at,
                       f.name as folder_name,
                       COUNT(li.id) as item_count
                FROM lists l
                LEFT JOIN folders f ON l.folder_id = f.id
                LEFT JOIN list_items li ON l.id = li.list_id
                WHERE l.name = ?
                GROUP BY l.id, l.name, l.folder_id, l.created_at, f.name
            """, [list_name])

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

            # Generate list name with timestamp - keep it shorter for better UI display
            from datetime import datetime
            timestamp = datetime.now().strftime("%m/%d %H:%M")

            # Shorten query if needed for display
            display_query = query if len(query) <= 20 else f"{query[:17]}..."

            list_name = f"Search: '{display_query}' ({timestamp})"

            # Truncate if too long
            if len(list_name) > 60:
                list_name = list_name[:57] + "..."

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
            'resume': item.get('resume', {})
        }

        # Collect all possible art data for version-aware storage
        art_data = {}

        # Check for existing art dictionary
        if item.get('art') and isinstance(item['art'], dict):
            art_data.update(item['art'])

        # Collect individual art fields for comprehensive coverage
        art_fields = ['poster', 'fanart', 'thumb', 'banner', 'landscape', 'clearlogo', 'clearart', 'discart', 'icon']
        for field in art_fields:
            if item.get(field):
                art_data[field] = item[field]

        # Add thumbnail fallback
        if item.get('thumbnail') and not art_data.get('thumb'):
            art_data['thumb'] = item['thumbnail']

        basic_item['art'] = art_data

        # Add any additional fields from the original item
        for key, value in item.items():
            if key not in basic_item and key not in art_fields and key != 'thumbnail':
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
                 play, plot, rating, votes, duration, mpaa, 
                 genre, director, studio, country, writer, cast, art)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                media_data['media_type'], media_data['title'], media_data['year'],
                media_data['imdbnumber'], media_data['tmdb_id'], media_data['kodi_id'],
                media_data['source'], media_data['play'], media_data['plot'], 
                media_data['rating'], media_data['votes'], media_data['duration'], 
                media_data['mpaa'], media_data['genre'], media_data['director'], 
                media_data['studio'], media_data['country'], media_data['writer'], 
                media_data['cast'], media_data['art']
            ])

            return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error inserting/getting media item: {e}")
            return None

    def get_all_lists_with_folders(self):
        """Get all lists with their folder information"""
        try:
            # Get all lists with folder names
            lists = self.connection_manager.execute_query("""
                SELECT 
                    l.id,
                    l.name,
                    COUNT(li.id) as item_count,
                    date(l.created_at) as created,
                    f.name as folder_name,
                    f.id as folder_id
                FROM lists l
                LEFT JOIN list_items li ON l.id = li.list_id
                LEFT JOIN folders f ON l.folder_id = f.id
                GROUP BY l.id, l.name, l.created_at, f.name, f.id
                ORDER BY 
                    CASE WHEN f.name IS NULL THEN 0 ELSE 1 END,
                    f.name,
                    l.created_at DESC
            """)

            if lists:
                # Convert to list of dicts for easier handling
                formatted_results = []
                for row in lists:
                    row_dict = dict(row)
                    # Ensure string conversion for compatibility
                    row_dict['id'] = str(row_dict['id'])
                    # Add description based on item count and folder
                    folder_context = f" ({row_dict['folder_name']})" if row_dict['folder_name'] else ""
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
        """Legacy method - enrichment no longer needed as data is stored in media_items"""
        # All enrichment data is now stored in media_items table during scan
        # This method is kept for backward compatibility but does nothing
        return items


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
            kodi_id = kodi_item.get('kodi_id')
            media_type = kodi_item.get('media_type', 'movie')

            self.logger.debug(f"Adding library item kodi_id={kodi_id}, media_type={media_type} to list {list_id}")

            with self.connection_manager.transaction() as conn:
                # First check if this library item already exists in media_items
                existing_item = conn.execute("""
                    SELECT id FROM media_items WHERE kodi_id = ? AND media_type = ?
                """, [kodi_id, media_type]).fetchone()

                if existing_item:
                    # Use existing media item
                    media_item_id = existing_item['id']
                    self.logger.logger.debug(f"Found existing media_item with id={media_item_id}")
                else:
                    # Create new media item - normalize the item first for proper data extraction
                    canonical_item = self._normalize_to_canonical(kodi_item)

                    # Extract basic fields for media_items table with version-aware art storage
                    from ..utils.kodi_version import get_kodi_major_version
                    kodi_major = get_kodi_major_version()

                    media_data = {
                        'media_type': canonical_item['media_type'],
                        'title': canonical_item['title'],
                        'year': canonical_item['year'],
                        'imdbnumber': canonical_item.get('imdb_id', ''),
                        'tmdb_id': canonical_item.get('tmdb_id', ''),
                        'kodi_id': canonical_item.get('kodi_id'),
                        'source': 'lib',
                        'play': '',
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
                        'art': json.dumps(self._format_art_for_kodi_version(canonical_item.get('art', {}), kodi_major))
                    }

                    media_item_id = self._insert_or_get_media_item(conn, media_data)
                    self.logger.debug(f"Created new media_item with id={media_item_id}")

                if not media_item_id:
                    return None

                # Check if item is already in the list
                existing_list_item = conn.execute("""
                    SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?
                """, [int(list_id), media_item_id]).fetchone()

                if existing_list_item:
                    self.logger.debug(f"Item already exists in list {list_id}")
                    return {
                        "id": str(media_item_id),
                        "title": kodi_item.get('title', 'Unknown'),
                        "year": kodi_item.get('year', 0),
                        "already_exists": True
                    }

                # Get next position
                position_result = conn.execute("""
                    SELECT COALESCE(MAX(position), -1) + 1 as next_position 
                    FROM list_items WHERE list_id = ?
                """, [int(list_id)]).fetchone()
                next_position = position_result['next_position'] if position_result else 0

                # Add to list
                conn.execute("""
                    INSERT INTO list_items (list_id, media_item_id, position)
                    VALUES (?, ?, ?)
                """, [int(list_id), media_item_id, next_position])

            return {
                "id": str(media_item_id),
                "title": kodi_item.get('title', 'Unknown'),
                "year": kodi_item.get('year', 0)
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

    def _format_art_for_kodi_version(self, art_dict: Dict[str, Any], kodi_major: int) -> Dict[str, Any]:
        """Format art dictionary for specific Kodi version compatibility"""
        if not isinstance(art_dict, dict):
            return {}

        # Clean up empty values
        cleaned_art = {k: v for k, v in art_dict.items() if v and str(v).strip()}

        # Kodi v19+ all support the same art format, but ensure consistency
        # Add fallbacks for missing common art types
        if cleaned_art.get("poster") and not cleaned_art.get("thumb"):
            cleaned_art["thumb"] = cleaned_art["poster"]
        if cleaned_art.get("poster") and not cleaned_art.get("icon"):
            cleaned_art["icon"] = cleaned_art["poster"]

        return cleaned_art

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

    def get_lists_in_folder(self, folder_id: Optional[str]) -> List[Dict[str, Any]]:
        """Get all lists in a specific folder"""
        try:
            self.logger.debug(f"Getting lists in folder {folder_id}")

            if folder_id is None:
                # Get lists in root (no folder)
                self.logger.debug("Querying for lists in root folder (folder_id IS NULL)")
                results = self.connection_manager.execute_query("""
                    SELECT l.*, COUNT(li.id) as item_count
                    FROM lists l
                    LEFT JOIN list_items li ON l.id = li.list_id
                    WHERE l.folder_id IS NULL
                    GROUP BY l.id
                    ORDER BY l.name
                """)
            else:
                # Get lists in specific folder
                self.logger.debug(f"Querying for lists in folder_id {folder_id}")
                results = self.connection_manager.execute_query("""
                    SELECT l.*, COUNT(li.id) as item_count
                    FROM lists l
                    LEFT JOIN list_items li ON l.id = li.list_id
                    WHERE l.folder_id = ?
                    GROUP BY l.id
                    ORDER BY l.name
                """, [int(folder_id)])

            lists = [dict(row) for row in results]
            self.logger.debug(f"Found {len(lists)} lists in folder {folder_id}")

            # Log each list found for debugging
            for lst in lists:
                self.logger.debug(f"  - List: {lst['name']} (id={lst['id']}, folder_id={lst.get('folder_id')})")

            return lists

        except Exception as e:
            self.logger.error(f"Error getting lists in folder {folder_id}: {e}")
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

    def get_all_folders(self, parent_id=None):
        """Get all folders with their list counts. If parent_id is provided, get subfolders of that folder."""
        try:
            if parent_id is None:
                # Get top-level folders
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
            else:
                # Get subfolders of specified parent
                folders = self.connection_manager.execute_query("""
                    SELECT 
                        f.id, f.name, f.created_at,
                        COUNT(l.id) as list_count
                    FROM folders f
                    LEFT JOIN lists l ON l.folder_id = f.id
                    WHERE f.parent_id = ?
                    GROUP BY f.id, f.name, f.created_at
                    ORDER BY f.name
                """, [parent_id])

            result = []
            for row in folders or []:
                result.append({
                    "id": str(row['id']),
                    "name": row['name'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                    "list_count": row['list_count']
                })

            if parent_id is None:
                self.logger.debug(f"Retrieved {len(result)} top-level folders")
            else:
                self.logger.debug(f"Retrieved {len(result)} subfolders for folder {parent_id}")
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
            result = self.connection_manager.execute_single("""
                SELECT l.id, l.name, l.folder_id, l.created_at,
                       COUNT(li.id) as item_count
                FROM lists l
                LEFT JOIN list_items li ON l.id = li.list_id
                WHERE l.id = ?
                GROUP BY l.id, l.name, l.folder_id, l.created_at
            """, [list_id])

            if result:
                return {
                    'id': result['id'],
                    'name': result['name'],
                    'folder_id': result['folder_id'],
                    'created_at': result['created_at'],
                    'item_count': result['item_count']
                }
            return None

        except Exception as e:
            self.logger.error(f"Error getting list info for {list_id}: {e}")
            return None

    def get_folder_info(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a specific folder"""
        try:
            result = self.connection_manager.execute_single("""
                SELECT f.id, f.name, f.parent_id, f.created_at,
                       COUNT(DISTINCT l.id) as list_count,
                       COUNT(DISTINCT sf.id) as subfolder_count
                FROM folders f
                LEFT JOIN lists l ON f.id = l.folder_id
                LEFT JOIN folders sf ON f.id = sf.parent_id
                WHERE f.id = ?
                GROUP BY f.id, f.name, f.parent_id, f.created_at
            """, [folder_id])

            if result:
                return {
                    'id': result['id'],
                    'name': result['name'],
                    'parent_id': result['parent_id'],
                    'created_at': result['created_at'],
                    'list_count': result['list_count'],
                    'subfolder_count': result['subfolder_count']
                }
            return None

        except Exception as e:
            self.logger.error(f"Error getting folder info for {folder_id}: {e}")
            return None

    def move_list_to_folder(self, list_id: str, target_folder_id: Optional[str]) -> Dict[str, Any]:
        """Move a list to a different folder"""
        try:
            self.logger.debug(f"Moving list {list_id} to folder {target_folder_id}")

            # Check if list exists
            existing_list = self.connection_manager.execute_single("""
                SELECT id, name FROM lists WHERE id = ?
            """, [int(list_id)])

            if not existing_list:
                return {"success": False, "error": "list_not_found"}

            # If target_folder_id is provided, verify the destination folder exists
            if target_folder_id is not None:
                destination_folder = self.connection_manager.execute_single("""
                    SELECT id FROM folders WHERE id = ?
                """, [int(target_folder_id)])

                if not destination_folder:
                    return {"success": False, "error": "destination_folder_not_found"}

            # Update the list's folder_id
            with self.connection_manager.transaction() as conn:
                result = conn.execute("""
                    UPDATE lists SET folder_id = ? WHERE id = ?
                """, [int(target_folder_id) if target_folder_id is not None else None, int(list_id)])

                if result.rowcount == 0:
                    raise Exception("No rows updated - list may not exist")

            self.logger.info(f"Successfully moved list {list_id} to folder {target_folder_id}")

            # Verify the move by checking the list is now in the target folder
            verification_query = """
                SELECT id, name, folder_id FROM lists WHERE id = ?
            """
            updated_list = self.connection_manager.execute_single(verification_query, [int(list_id)])

            if updated_list:
                actual_folder_id = updated_list['folder_id']
                expected_folder_id = int(target_folder_id) if target_folder_id is not None else None
                self.logger.debug(f"Verification: List {list_id} now has folder_id={actual_folder_id}, expected={expected_folder_id}")

                if actual_folder_id != expected_folder_id:
                    self.logger.error(f"Move verification failed: expected folder_id={expected_folder_id}, got={actual_folder_id}")
                    return {"success": False, "error": "verification_failed"}

            return {"success": True}

        except Exception as e:
            self.logger.error(f"Failed to move list {list_id} to folder {target_folder_id}: {e}")
            return {"success": False, "error": "database_error"}

    def merge_lists(self, source_list_id: str, target_list_id: str) -> Dict[str, Any]:
        """Merge items from source list into target list"""
        try:
            self.logger.debug(f"Merging list {source_list_id} into list {target_list_id}")

            # Check if both lists exist
            source_list = self.connection_manager.execute_single("""
                SELECT id, name FROM lists WHERE id = ?
            """, [int(source_list_id)])

            target_list = self.connection_manager.execute_single("""
                SELECT id, name FROM lists WHERE id = ?
            """, [int(target_list_id)])

            if not source_list or not target_list:
                return {"success": False, "error": "list_not_found"}

            # Get items from source list that aren't already in target list
            items_to_merge = self.connection_manager.execute_query("""
                SELECT DISTINCT li1.library_movie_id, li1.title, li1.year, li1.imdb_id, li1.tmdb_id
                FROM list_items li1
                WHERE li1.list_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM list_items li2 
                    WHERE li2.list_id = ? AND li2.library_movie_id = li1.library_movie_id
                )
            """, [int(source_list_id), int(target_list_id)])

            if not items_to_merge:
                return {"success": True, "items_added": 0}

            # Add items to target list
            items_added = 0
            with self.connection_manager.transaction() as conn:
                for item in items_to_merge:
                    conn.execute("""
                        INSERT INTO list_items (list_id, library_movie_id, title, year, imdb_id, tmdb_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """, [int(target_list_id), item['library_movie_id'], item['title'], 
                          item['year'], item['imdb_id'], item['tmdb_id']])
                    items_added += 1

            self.logger.debug(f"Successfully merged {items_added} items from list {source_list_id} to list {target_list_id}")
            return {"success": True, "items_added": items_added}

        except Exception as e:
            self.logger.error(f"Failed to merge list {source_list_id} into list {target_list_id}: {e}")
            return {"success": False, "error": "database_error"}

    def move_folder(self, folder_id: str, target_folder_id: Optional[str]) -> Dict[str, Any]:
        """Move a folder to a different destination folder (or root level if None)"""
        try:
            self.logger.debug(f"Moving folder {folder_id} to destination {target_folder_id}")

            # Check if folder exists
            existing_folder = self.connection_manager.execute_single("""
                SELECT id, name FROM folders WHERE id = ?
            """, [int(folder_id)])

            if not existing_folder:
                return {"success": False, "error": "folder_not_found"}

            # If target_folder_id is provided, verify the destination folder exists
            if target_folder_id is not None:
                destination_folder = self.connection_manager.execute_single("""
                    SELECT id FROM folders WHERE id = ?
                """, [int(target_folder_id)])

                if not destination_folder:
                    return {"success": False, "error": "destination_folder_not_found"}

                # Check for circular reference (folder can't be moved into itself or its children)
                if str(folder_id) == str(target_folder_id):
                    return {"success": False, "error": "circular_reference"}

            # Update the folder's parent_id to the new destination
            with self.connection_manager.transaction() as conn:
                conn.execute("""
                    UPDATE folders SET parent_id = ? WHERE id = ?
                """, [int(target_folder_id) if target_folder_id is not None else None, int(folder_id)])

            self.logger.debug(f"Successfully moved folder {folder_id} to destination {target_folder_id}")
            return {"success": True}

        except Exception as e:
            self.logger.error(f"Failed to move folder {folder_id} to destination {target_folder_id}: {e}")
            return {"success": False, "error": "database_error"}


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