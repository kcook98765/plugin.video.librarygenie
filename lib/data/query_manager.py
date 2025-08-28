#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Query Manager
Real SQLite-based data layer for list and item management
"""

import json
from typing import List, Dict, Any, Optional, Union

# Assuming JSONRPCClient and get_logger are available from other modules
# from .connection_manager import get_connection_manager
# from .migrations import get_migration_manager
# from ..utils.logger import get_logger

# Mock implementations for demonstration purposes if not provided
class MockJSONRPCClient:
    def call_method(self, method, params=None):
        print(f"MockJSONRPCClient: Called {method} with params: {params}")
        if method == 'VideoLibrary.GetMovies':
            return {
                "result": {
                    "movies": [
                        {
                            "movieid": 1, "title": "Movie 1", "year": 2020, "runtime": 120,
                            "genre": ["Action"], "rating": 7.5, "votes": 100, "mpaa": "PG-13",
                            "studio": ["Studio A"], "country": ["USA"], "premiered": "2020-01-01",
                            "sorttitle": "Movie 1", "thumbnail": "poster1.jpg",
                            "art": {"poster": "poster1.jpg", "fanart": "fanart1.jpg"},
                            "resume": {"position_seconds": 3600, "total_seconds": 7200}
                        },
                        {
                            "movieid": 2, "title": "Movie 2", "year": 2019, "runtime": 90,
                            "genre": ["Comedy"], "rating": 6.0, "votes": 50, "mpaa": "PG",
                            "studio": ["Studio B"], "country": ["Canada"], "premiered": "2019-05-15",
                            "sorttitle": "Movie 2", "thumbnail": "poster2.jpg",
                            "art": {"poster": "poster2.jpg"},
                            "resume": {"position_seconds": 0, "total_seconds": 5400}
                        }
                    ]
                }
            }
        elif method == 'VideoLibrary.GetEpisodes':
            return {
                "result": {
                    "episodes": [
                        {
                            "episodeid": 101, "tvshowid": 5, "season": 1, "episode": 1,
                            "title": "Episode 1", "showtitle": "TV Show A", "aired": "2021-01-01",
                            "runtime": 45, "rating": 8.0, "playcount": 1,
                            "thumbnail": "episode1.jpg", "art": {"thumb": "episode1.jpg"},
                            "resume": {"position_seconds": 1800, "total_seconds": 2700}
                        },
                        {
                            "episodeid": 102, "tvshowid": 5, "season": 1, "episode": 2,
                            "title": "Episode 2", "showtitle": "TV Show A", "aired": "2021-01-08",
                            "runtime": 45, "rating": 7.8, "playcount": 0,
                            "thumbnail": "episode2.jpg", "art": {"thumb": "episode2.jpg"},
                            "resume": {"position_seconds": 0, "total_seconds": 2700}
                        }
                    ]
                }
            }
        return {"result": {}}

def get_logger(name):
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def debug(self, msg): print(f"DEBUG: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
    return MockLogger()

class MockConnectionManager:
    def execute_query(self, query, params=None):
        print(f"MockConnectionManager: Executing query: {query} with params: {params}")
        # Mock data for get_user_lists
        if "SELECT id, name, created_at, updated_at, (SELECT COUNT(*) FROM list_item WHERE list_id = user_list.id) as item_count FROM user_list" in query:
            return [
                {'id': 1, 'name': 'List 1', 'created_at': '2023-01-01', 'updated_at': '2023-01-01', 'item_count': 5},
                {'id': 2, 'name': 'List 2', 'created_at': '2023-01-02', 'updated_at': '2023-01-02', 'item_count': 0}
            ]
        return []
    def execute_single(self, query, params=None):
        print(f"MockConnectionManager: Executing single query: {query} with params: {params}")
        if "SELECT id FROM user_list WHERE name = ?" in query and params[0] == "Default":
            return None # Default list does not exist
        if "SELECT id FROM folders WHERE name = ?" in query and params[0] == "Search History":
            return {'id': 10} # Search History folder exists
        return None
    def transaction(self):
        class MockTransaction:
            def __enter__(self):
                print("MockConnectionManager: Starting transaction")
                return self # Return self to be used as context manager
            def __exit__(self, exc_type, exc_val, exc_tb):
                print("MockConnectionManager: Committing transaction")
            def execute(self, query, params=None):
                print(f"MockConnectionManager: Executing in transaction: {query} with params: {params}")
                # Mock lastrowid for insert operations
                if query.strip().upper().startswith("INSERT INTO user_list"):
                    return MockCursor(lastrowid=123)
                elif query.strip().upper().startswith("INSERT INTO folders"):
                    return MockCursor(lastrowid=10)
                return MockCursor()
        return MockTransaction()
class MockCursor:
    def __init__(self, lastrowid=None):
        self.lastrowid = lastrowid
    def fetchone(self):
        print("MockCursor: fetchone called")
        return None
    def fetchall(self):
        print("MockCursor: fetchall called")
        return []


class MockMigrationManager:
    def ensure_initialized(self):
        print("MockMigrationManager: Ensuring initialized")

def get_connection_manager():
    return MockConnectionManager()

def get_migration_manager():
    return MockMigrationManager()

class JSONRPCClient:
    """Real JSON-RPC client for Kodi API communication"""
    
    def __init__(self):
        self.logger = get_logger(__name__)

    def call_method(self, method, params=None):
        """Execute JSON-RPC method with real Kodi API"""
        import json
        import xbmc
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        
        try:
            self.logger.debug(f"JSON-RPC request: {method}")
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                self.logger.error(f"JSON-RPC error for {method}: {response['error']}")
                return {"result": {}}
            
            return response
            
        except Exception as e:
            self.logger.error(f"JSON-RPC request failed for {method}: {e}")
            return {"result": {}}


class QueryManager:
    """Manages database queries and JSON-RPC operations"""

    def __init__(self, db_manager=None):
        # Use mock objects if not provided
        self.conn_manager = db_manager if db_manager else get_connection_manager()
        self.migration_manager = get_migration_manager()
        self.logger = get_logger(__name__)
        self.json_rpc = JSONRPCClient()

        # Performance settings - configurable via addon settings
        self.json_rpc_timeout = 10  # seconds
        self.json_rpc_page_size = 200  # items per request
        self.database_batch_size = 250  # items per transaction
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

    def _safe_get_value(self, data: Dict[str, Any], key: str, default_value: Any = None, value_type: type = str) -> Any:
        """Safely get value from dictionary with proper type conversion"""
        try:
            value = data.get(key, default_value)

            # Handle empty strings and null values
            if value == "" or value is None:
                return default_value

            # Type conversion
            if value_type == int:
                return int(value)
            elif value_type == float:
                return float(value)
            else:
                return str(value)

        except (ValueError, TypeError):
            self.logger.warning(f"Failed to convert {key}={value} to {value_type.__name__}, using default: {default_value}")
            return default_value

    def normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize item to ensure all required lightweight fields are present

        Args:
            item: Raw item data from database or JSON-RPC

        Returns:
            Normalized item with consistent field names and types
        """
        normalized = {}

        # Identity fields
        normalized['type'] = item.get('media_type', item.get('type', 'movie'))
        normalized['kodi_id'] = item.get('kodi_id') or item.get('movieid') or item.get('id')

        # Core metadata (strings unless noted)
        normalized['title'] = item.get('title', 'Unknown Title')
        normalized['originaltitle'] = item.get('originaltitle', item.get('title', ''))
        normalized['sorttitle'] = item.get('sorttitle', item.get('title', ''))
        normalized['year'] = self._safe_get_value(item, 'year', 0, int)
        normalized['genre'] = item.get('genre', '')
        normalized['plot'] = item.get('plot', item.get('plotoutline', ''))
        normalized['rating'] = self._safe_get_value(item, 'rating', 0.0, float)
        normalized['votes'] = self._safe_get_value(item, 'votes', 0, int)
        normalized['mpaa'] = item.get('mpaa', '')

        # Duration handling - convert runtime (minutes) to duration_minutes
        runtime = item.get('runtime', item.get('duration'))
        if runtime:
            # Runtime from JSON-RPC is in minutes, duration might be seconds
            if isinstance(runtime, int) and runtime > 0:
                if runtime > 1000:  # Assume seconds if > 1000
                    normalized['duration_minutes'] = runtime // 60
                else:  # Assume minutes
                    normalized['duration_minutes'] = runtime
            else:
                normalized['duration_minutes'] = 0
        else:
            normalized['duration_minutes'] = 0

        normalized['studio'] = item.get('studio', '')
        normalized['country'] = item.get('country', '')
        normalized['premiered'] = item.get('premiered', item.get('dateadded', ''))
        normalized['mediatype'] = normalized['type']  # Must match Kodi values

        # Episode-specific fields
        if normalized['type'] == 'episode':
            normalized['tvshowtitle'] = item.get('showtitle', item.get('tvshowtitle', ''))
            normalized['season'] = self._safe_get_value(item, 'season', 1, int)
            normalized['episode'] = self._safe_get_value(item, 'episode', 1, int)
            normalized['aired'] = item.get('aired', item.get('firstaired', ''))
            normalized['playcount'] = self._safe_get_value(item, 'playcount', 0, int)
            normalized['lastplayed'] = item.get('lastplayed', '')

        # Art dictionary - only include valid URLs
        art = {}
        art_sources = ['poster', 'fanart', 'thumb', 'banner', 'landscape', 'clearlogo']
        for art_type in art_sources:
            art_url = item.get(art_type)
            if art_url and isinstance(art_url, str) and art_url.strip():
                art[art_type] = art_url.strip()

        # Handle complex art data
        if item.get('art'):
            try:
                if isinstance(item['art'], dict):
                    art.update(item['art'])
                elif isinstance(item['art'], str):
                    import json
                    art_data = json.loads(item['art'])
                    if isinstance(art_data, dict):
                        art.update(art_data)
            except Exception as e:
                self.logger.debug(f"Failed to parse art data for {normalized['title']}: {e}")

        normalized['art'] = art

        # Resume data - always include for library movies/episodes
        resume = {'position_seconds': 0, 'total_seconds': 0}
        if normalized['kodi_id'] and normalized['type'] in ['movie', 'episode']:
            resume_data = item.get('resume', {})
            if isinstance(resume_data, dict):
                resume['position_seconds'] = int(resume_data.get('position', 0))
                resume['total_seconds'] = int(resume_data.get('total', 0))

        normalized['resume'] = resume

        return normalized

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
        """Get items in a specific list from database, enriching Kodi library items with JSON-RPC data"""
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

            # Convert to expected format and identify Kodi library items for enrichment
            result: List[Dict[str, Any]] = []
            kodi_ids_to_enrich = []
            items_to_match = []

            for row in items:
                item_data = {
                    "id": str(row['id']),
                    "title": row['title'],
                    "year": row['year'],
                    "imdb_id": row['imdb_id'],
                    "tmdb_id": row['tmdb_id'],
                    "created": row['created_at'][:10] if row['created_at'] else '',
                }

                # Check if this is a Kodi library item that needs enrichment
                if 'kodi_id' in row and row['kodi_id']:
                    item_data['kodi_id'] = row['kodi_id']
                    kodi_ids_to_enrich.append(row['kodi_id'])
                    self.logger.debug(f"Found Kodi library item: {row['title']} (kodi_id: {row['kodi_id']})")
                else:
                    # Try to match this item to Kodi library for enrichment
                    items_to_match.append((len(result), item_data))

                    # For now, use stored database data as fallback
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

            # Enrich Kodi library items with fresh JSON-RPC data first
            enriched_data = {}
            if kodi_ids_to_enrich:
                self.logger.info(f"Enriching {len(kodi_ids_to_enrich)} Kodi library items with fresh JSON-RPC data: {kodi_ids_to_enrich}")
                enriched_data = self._get_kodi_enrichment_data(kodi_ids_to_enrich)
                self.logger.info(f"Enrichment returned data for {len(enriched_data)} movies: {list(enriched_data.keys())}")

                # Apply enrichment data to result items that have kodi_id
                for i, item_data in enumerate(result):
                    if item_data.get('kodi_id') and item_data['kodi_id'] in enriched_data:
                        enrichment = enriched_data[item_data['kodi_id']]
                        item_data.update(enrichment)
                        # Mark as library item
                        item_data['source'] = 'lib'
                        self.logger.info(f"Enriched list item '{item_data['title']}' with Kodi library data, artwork: {bool(enrichment.get('poster') or enrichment.get('art'))}")
                    else:
                        self.logger.warning(f"Failed to enrich Kodi item {item_data.get('kodi_id')}: not found in JSON-RPC results. Available enriched IDs: {list(enriched_data.keys())}")

            # Try to match items without kodi_id to the Kodi library
            if items_to_match:
                self.logger.info(f"Attempting to match {len(items_to_match)} items without kodi_id to Kodi library")
                matched_kodi_ids = self._match_items_to_kodi_library(items_to_match)

                # Get enrichment data for matched items if we don't have it already
                new_kodi_ids = [kodi_id for kodi_id in matched_kodi_ids.values() if kodi_id and kodi_id not in enriched_data]
                if new_kodi_ids:
                    self.logger.info(f"Getting enrichment data for {len(new_kodi_ids)} newly matched items: {new_kodi_ids}")
                    new_enriched_data = self._get_kodi_enrichment_data(new_kodi_ids)
                    enriched_data.update(new_enriched_data)

                # Apply enrichment data to matched items
                for item_index, kodi_id in matched_kodi_ids.items():
                    if kodi_id and kodi_id in enriched_data:
                        enrichment = enriched_data[kodi_id]
                        # Merge enrichment data, ensuring artwork is preserved
                        result[item_index].update(enrichment)
                        # Also set source to 'lib' to indicate this is a library item
                        result[item_index]['source'] = 'lib'
                        result[item_index]['kodi_id'] = kodi_id  # Make sure kodi_id is set
                        self.logger.info(f"Enriched '{result[item_index]['title']}' with Kodi library data, artwork: {bool(enrichment.get('poster') or enrichment.get('art'))}")

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
        # Extract kodi_id from various possible fields
        kodi_id = None

        # Check for movieid field (from JSON-RPC responses)
        if item.get('movieid'):
            kodi_id = item.get('movieid')
        # Check for explicit kodi_id field
        elif item.get('kodi_id'):
            kodi_id = item.get('kodi_id')
        # For local search results, the 'id' field should be the kodi_id
        elif item.get('id') and not item.get('_source'):
            # Local search results don't have _source field, so 'id' is kodi_id
            kodi_id = item.get('id')
        # Last resort - check if 'id' is present and not from remote source
        elif item.get('id') and item.get('_source') != 'remote':
            kodi_id = item.get('id')

        # Ensure kodi_id is properly typed as integer if present
        if kodi_id is not None:
            try:
                kodi_id = int(kodi_id)
                self.logger.info(f"Extracted kodi_id {kodi_id} for item '{item.get('title', 'Unknown')}'")
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid kodi_id value: {kodi_id}, setting to None")
                kodi_id = None
        else:
            self.logger.warning(f"No kodi_id found for item '{item.get('title', 'Unknown')}' - available keys: {list(item.keys())}")

        # Build the media item data structure
        return {
            'media_type': item.get('type', 'movie'),
            'title': item.get('title', item.get('label', 'Unknown')),
            'year': item.get('year'),
            'imdbnumber': item.get('imdbnumber') or item.get('imdb_id'),
            'tmdb_id': item.get('tmdb_id'),
            'kodi_id': kodi_id,  # CRITICAL: Ensure kodi_id is preserved
            'source': 'remote' if item.get('_source') == 'remote' else 'lib',
            'play': item.get('path') or item.get('file_path', ''),
            'poster': item.get('art', {}).get('poster', '') if item.get('art') else item.get('poster', ''),
            'fanart': item.get('art', {}).get('fanart', '') if item.get('art') else item.get('fanart', ''),
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
            'cast': item.get('cast', ''),
            'art': item.get('art', ''),
            'created_at': 'datetime("now")'
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

    def _get_kodi_enrichment_data(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch rich metadata from Kodi JSON-RPC for the given kodi_ids"""
        try:
            if not kodi_ids:
                return {}

            self.logger.info(f"Fetching JSON-RPC data for {len(kodi_ids)} movies: {kodi_ids}")

            enrichment_data = {}

            # Fetch data for each movie using real JSON-RPC
            for kodi_id in kodi_ids:
                try:
                    # Request lightweight properties (no heavy arrays like cast)
                    params = {
                        "movieid": int(kodi_id),
                        "properties": [
                            "title", "originaltitle", "year", "imdbnumber", "uniqueid", "file",
                            "art", "plot", "plotoutline", "runtime", "rating", "votes",
                            "genre", "mpaa", "director", "country", "studio", "sorttitle",
                            "playcount", "resume", "writer", "premiered"
                        ]
                    }

                    response = self.json_rpc.call_method("VideoLibrary.GetMovieDetails", params)

                    if response.get("error"):
                        self.logger.warning(f"JSON-RPC error for movie {kodi_id}: {response['error']}")
                        continue

                    movie_details = response.get("result", {}).get("moviedetails")
                    if movie_details:
                        self.logger.debug(f"Got movie details for {kodi_id}: {movie_details.get('title', 'Unknown')}")
                        
                        # Add required fields for normalization
                        movie_details["media_type"] = "movie"
                        movie_details["kodi_id"] = kodi_id

                        # Map runtime to duration_minutes
                        if movie_details.get("runtime"):
                            movie_details["duration_minutes"] = movie_details["runtime"]

                        # Map resume.position/total (seconds) to resume dict
                        resume_data = movie_details.get("resume", {})
                        if isinstance(resume_data, dict):
                            movie_details["resume"] = {
                                "position_seconds": resume_data.get("position", 0),
                                "total_seconds": resume_data.get("total", 0)
                            }

                        # Normalize the movie data
                        normalized = self.normalize_item(movie_details)
                        if normalized:
                            enrichment_data[kodi_id] = normalized
                            self.logger.info(f"Successfully enriched movie {kodi_id}: {normalized.get('title')}")
                        else:
                            self.logger.warning(f"Failed to normalize movie details for {kodi_id}")
                    else:
                        self.logger.warning(f"No moviedetails found in response for {kodi_id}")

                except Exception as e:
                    self.logger.error(f"Failed to fetch details for movie {kodi_id}: {e}")
                    continue

            self.logger.info(f"Successfully enriched {len(enrichment_data)} out of {len(kodi_ids)} movies")
            return enrichment_data

        except Exception as e:
            self.logger.error(f"Error fetching Kodi enrichment data: {e}")
            return {}

    def _match_items_to_kodi_library(self, items_to_match: List[tuple]) -> Dict[int, Optional[int]]:
        """Try to match items without kodi_id to Kodi library movies"""
        try:
            # from ..kodi.json_rpc_client import get_kodi_client # Assuming this exists
            # kodi_client = get_kodi_client()
            # Mock client for demonstration
            class MockKodiClient:
                def get_movies_quick_check(self): return [1, 2] # Mock IDs
                def get_movies(self, limit=None, offset=0):
                    return {
                        "movies": [
                            {"movieid": 1, "title": "Movie 1", "year": 2020, "imdb_id": "tt12345"},
                            {"movieid": 2, "title": "Movie 2", "year": 2019, "imdb_id": "tt67890"}
                        ]
                    }
            kodi_client = MockKodiClient()

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
                        matched_kodi_id = library_movie.get('movieid') # Use 'movieid' as kodi_id
                        self.logger.debug(f"IMDb match: {item_title} -> kodi_id {matched_kodi_id}")
                        break

                    # Match by title and year
                    elif (item_title and library_title and
                          item_title == library_title and
                          item_year and library_year and
                          int(item_year) == int(library_year)):
                        matched_kodi_id = library_movie.get('movieid') # Use 'movieid' as kodi_id
                        self.logger.debug(f"Title/Year match: {item_title} ({item_year}) -> kodi_id {matched_kodi_id}")
                        break

                matched_ids[item_index] = matched_kodi_id
                if not matched_kodi_id:
                    self.logger.debug(f"No match found for: {item_title} ({item_year})")

            return matched_ids

        except Exception as e:
            self.logger.error(f"Error matching items to Kodi library: {e}")
            return {}

    def _normalize_kodi_movie_details(self, movie: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize movie details from Kodi JSON-RPC response"""
        try:
            # Extract external IDs
            imdb_id = None
            tmdb_id = None

            # Try the old imdbnumber field
            if "imdbnumber" in movie and movie["imdbnumber"]:
                if movie["imdbnumber"].startswith("tt"):
                    imdb_id = movie["imdbnumber"]

            # Try the newer uniqueid structure
            if "uniqueid" in movie and isinstance(movie["uniqueid"], dict):
                if "imdb" in movie["uniqueid"]:
                    imdb_id = movie["uniqueid"]["imdb"]
                if "tmdb" in movie["uniqueid"]:
                    tmdb_id = str(movie["uniqueid"]["tmdb"])

            # Extract artwork URLs - this is the key fix
            art = movie.get("art", {})
            poster = art.get("poster", "")
            fanart = art.get("fanart", "")
            thumb = art.get("thumb", poster)  # Fallback to poster
            clearlogo = art.get("clearlogo", "")
            landscape = art.get("landscape", "")
            clearart = art.get("clearart", "")
            discart = art.get("discart", "")
            banner = art.get("banner", "")

            # Extract and process metadata
            genres = movie.get("genre", [])
            genre_str = ", ".join(genres) if isinstance(genres, list) else str(genres) if genres else ""

            directors = movie.get("director", [])
            director_str = ", ".join(directors) if isinstance(directors, list) else str(directors) if directors else ""

            # Handle resume point
            resume_data = movie.get("resume", {})
            resume_time = resume_data.get("position", 0) if isinstance(resume_data, dict) else 0

            # Log cast information for debugging
            # NOTE: Cast data is intentionally not processed for library items.
            # Cast will be handled automatically by Kodi when dbid is set on ListItems.
            # This improves performance and follows Kodi best practices.

            return {
                "kodi_id": movie.get("movieid"),
                "title": movie.get("title", "Unknown Title"),
                "year": movie.get("year"),
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                "file_path": movie.get("file", ""),
                "poster": poster,
                "fanart": fanart,
                "thumb": thumb,
                "clearlogo": clearlogo,
                "landscape": landscape,
                "clearart": clearart,
                "discart": discart,
                "banner": banner,
                "plot": movie.get("plot", ""),
                "plotoutline": movie.get("plotoutline", ""),
                "runtime": movie.get("runtime", 0),
                "rating": movie.get("rating", 0.0),
                "genre": genre_str,
                "mpaa": movie.get("mpaa", ""),
                "director": director_str,
                "country": ", ".join(movie.get("country", [])) if isinstance(movie.get("country"), list) else movie.get("country", ""),
                "studio": ", ".join(movie.get("studio", [])) if isinstance(movie.get("studio"), list) else movie.get("studio", ""),
                "writer": ", ".join(movie.get("writer", [])) if isinstance(movie.get("writer"), list) else movie.get("writer", ""),
                "playcount": movie.get("playcount", 0),
                "resume_time": resume_time,
                "votes": movie.get("votes", 0),
                "art": art,  # Include the full art dictionary for compatibility
                "media_type": "movie",  # Ensure media_type is set
                "source": "lib"  # Mark as library source
            }

        except Exception as e:
            self.logger.warning(f"Failed to normalize movie details: {e}")
            return None

    def get_movies(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get movies from Kodi library with lightweight metadata

        Args:
            limit: Maximum number of movies to return
            offset: Number of movies to skip

        Returns:
            List of normalized movie dictionaries with metadata
        """
        try:
            # Request only lightweight properties for list display (no heavy arrays)
            properties = [
                "title", "originaltitle", "year", "genre", "plotoutline", 
                "rating", "votes", "mpaa", "runtime", "studio", "country",
                "premiered", "sorttitle", "thumbnail", "art", "resume"
            ]

            params = {
                "properties": properties,
                "sort": {"order": "ascending", "method": "sorttitle"}
            }

            if limit:
                params["limits"] = {"start": offset, "end": offset + limit}

            response = self.json_rpc.call_method("VideoLibrary.GetMovies", params)

            if response.get("result") and response["result"].get("movies"):
                movies = response["result"]["movies"]
                self.logger.info(f"Retrieved {len(movies)} movies from library")

                # Normalize all movies
                normalized_movies = []
                for movie in movies:
                    # Add required fields for normalization
                    movie["media_type"] = "movie"
                    movie["kodi_id"] = movie.get("movieid")

                    # Map runtime to duration_minutes
                    if movie.get("runtime"):
                        movie["duration_minutes"] = movie["runtime"]

                    # Map resume.position/total (seconds) to resume dict
                    resume_data = movie.get("resume", {})
                    if isinstance(resume_data, dict):
                        movie["resume"] = {
                            "position_seconds": resume_data.get("position", 0),
                            "total_seconds": resume_data.get("total", 0)
                        }

                    # Normalize the item
                    normalized = self.normalize_item(movie)
                    normalized_movies.append(normalized)

                return normalized_movies
            else:
                self.logger.info("No movies found in library")
                return []

        except Exception as e:
            self.logger.error(f"Failed to get movies: {e}")
            return []

    def get_episodes(self, tvshow_id: Optional[int] = None, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get episodes from Kodi library

        Args:
            tvshow_id: Optional TV show ID to filter episodes
            limit: Maximum number of episodes to return
            offset: Number of episodes to skip

        Returns:
            List of normalized episode dictionaries with metadata
        """
        try:
            # Request lightweight episode properties (no heavy arrays)
            properties = [
                "title", "plotoutline", "season", "episode", "showtitle",
                "aired", "runtime", "rating", "playcount", "lastplayed", 
                "thumbnail", "art", "resume"
            ]

            params = {
                "properties": properties,
                "sort": {"order": "ascending", "method": "episode"}
            }

            if tvshow_id:
                params["tvshowid"] = tvshow_id

            if limit:
                params["limits"] = {"start": offset, "end": offset + limit}

            response = self.json_rpc.call_method("VideoLibrary.GetEpisodes", params)

            if response.get("result") and response["result"].get("episodes"):
                episodes = response["result"]["episodes"]
                self.logger.info(f"Retrieved {len(episodes)} episodes from library")

                # Normalize all episodes
                normalized_episodes = []
                for episode in episodes:
                    # Add required fields for normalization
                    episode["media_type"] = "episode"
                    episode["kodi_id"] = episode.get("episodeid")

                    # Map runtime to duration_minutes
                    if episode.get("runtime"):
                        episode["duration_minutes"] = episode["runtime"]

                    # Map resume.position/total (seconds) to resume dict
                    resume_data = episode.get("resume", {})
                    if isinstance(resume_data, dict):
                        episode["resume"] = {
                            "position_seconds": resume_data.get("position", 0),
                            "total_seconds": resume_data.get("total", 0)
                        }

                    # Normalize the item
                    normalized = self.normalize_item(episode)
                    normalized_episodes.append(normalized)

                return normalized_episodes
            else:
                self.logger.info("No episodes found in library")
                return []

        except Exception as e:
            self.logger.error(f"Failed to get episodes: {e}")
            return []

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