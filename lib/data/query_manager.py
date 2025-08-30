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
from ..kodi.json_rpc_helper import JsonRpcHelper as JsonRpcClient


class QueryManager:
    """Manages data queries and database operations using SQLite"""

    def __init__(self, db_manager, config_manager=None):
        self.logger = get_logger(__name__)
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.json_rpc_client = JsonRpcClient(config_manager)
        self._enrichment_counters = {
            'movies_processed': 0,
            'movies_enriched': 0,
            'episodes_processed': 0,
            'episodes_enriched': 0
        }

    def _log_enrichment_summary(self):
        """Log summary of enrichment operations and reset counters"""
        if any(self._enrichment_counters.values()):
            self.logger.info(f"ENRICHMENT BATCH SUMMARY: Movies processed: {self._enrichment_counters['movies_processed']}, "
                           f"enriched: {self._enrichment_counters['movies_enriched']}, "
                           f"Episodes processed: {self._enrichment_counters['episodes_processed']}, "
                           f"enriched: {self._enrichment_counters['episodes_enriched']}")
            # Reset counters for next batch
            self._enrichment_counters = {
                'movies_processed': 0,
                'movies_enriched': 0,
                'episodes_processed': 0,
                'episodes_enriched': 0
            }

    def _normalize_to_canonical(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize any media item to canonical format"""
        canonical = {}

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

            lists = self.connection_manager.execute_query("""
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
        """Get items from a specific list with paging, normalized to canonical format"""
        try:
            connection = self.connection_manager.get_connection()
            cursor = connection.cursor()

            # Get list items with media data
            cursor.execute("""
                SELECT
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
            """, (list_id, limit, offset))

            rows = cursor.fetchall()
            items = []

            for row in rows:
                item = self._row_to_dict(cursor, row)

                # Parse JSON data if present
                if item.get('data_json'):
                    try:
                        json_data = json.loads(item['data_json'])
                        item.update(json_data)
                    except json.JSONDecodeError:
                        pass

                # Enrich with Kodi data if available
                if item.get('kodi_id') and item.get('media_type') in ['movie', 'episode']:
                    enriched = self._enrich_with_kodi_data([item])
                    if enriched:
                        item = enriched[0]

                # Normalize to canonical format
                canonical_item = self._normalize_to_canonical(item)
                items.append(canonical_item)

            return items

        except Exception as e:
            self.logger.error(f"Error getting list items: {e}")
            return []

    def create_list(self, name, description=""):
        """Create a new list in database with proper validation"""
        if not name or not name.strip():
            self.logger.warning("Attempted to create list with empty name")
            return {"error": "empty_name"}

        name = name.strip()

        try:
            self.logger.info(f"Creating list '{name}'")

            with self.connection_manager.transaction() as conn:
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

            with self.connection_manager.transaction() as conn:
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
            result = self.connection_manager.execute_single("""
                SELECT COUNT(*) as count FROM list_item WHERE list_id = ?
            """, [int(list_id)])

            count = result['count'] if result else 0

            # If no items found, try new lists table
            if count == 0:
                result = self.connection_manager.execute_single("""
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

            with self.connection_manager.transaction() as conn:
                conn.execute("DELETE FROM user_list WHERE id = ?", [int(list_id)])

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete list {list_id}: {e}")
            return False

    def delete_item_from_list(self, list_id, item_id):
        """Delete an item from a list in database"""
        try:
            self.logger.info(f"Deleting item {item_id} from list {list_id}")

            with self.connection_manager.transaction() as conn:
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

            with self.connection_manager.transaction() as conn:
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

            with self.connection_manager.transaction() as conn:
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
            result = self.connection_manager.execute_single("""
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
            default_list = self.connection_manager.execute_single("""
                SELECT id FROM user_list WHERE name = ?
            """, ["Default"])

            if not default_list:
                self.logger.info("Creating default list")
                with self.connection_manager.transaction() as conn:
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
            folder = self.connection_manager.execute_single("""
                SELECT id FROM folders WHERE name = ? AND parent_id IS NULL
            """, ["Search History"])

            if folder:
                return folder['id']

            # Create Search History folder
            self.logger.info("Creating Search History folder")
            with self.connection_manager.transaction() as conn:
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
            with self.connection_manager.transaction() as conn:
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

            self.logger.info(f"Added {added_count} items to search history list {list_id}")
            return added_count

        except Exception as e:
            self.logger.error(f"Failed to add search results to list: {e}")
            return 0

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
        """Get all lists including those in folders (like Search History)"""
        try:
            self.logger.debug("Getting all lists with folders from database")

            # Get all lists including those in folders
            lists = self.connection_manager.execute_query("""
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

    def _get_kodi_episode_enrichment_data(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch lightweight episode metadata from Kodi JSON-RPC"""
        try:
            import xbmc

            if not kodi_ids:
                return {}

            # Handle batch logging: log details only for the first batch or single items
            if len(kodi_ids) == 1 or self._enrichment_counters['episodes_processed'] == 0:
                self.logger.info(f"Fetching JSON-RPC data for {len(kodi_ids)} episodes: {kodi_ids}")

            enriched = self.json_rpc_client.get_episodes_batch(kodi_ids)
            if not enriched:
                self.logger.warning("No JSON-RPC data returned for episodes")
                return {}

            # Process each episode
            result = {}
            success_count = 0
            for episode_data in enriched:
                episode_id = episode_data.get('episodeid')
                if not episode_id:
                    continue

                title = episode_data.get('title', 'Unknown')
                result[episode_id] = episode_data
                success_count += 1
                self._enrichment_counters['episodes_enriched'] += 1

                # Only log first enrichment in detail
                if self._enrichment_counters['episodes_enriched'] == 1:
                    self.logger.info(f"Successfully enriched episode {episode_id}: {title}")

            self._enrichment_counters['episodes_processed'] += len(kodi_ids)

            # Log summary for batches or single items after first
            if len(kodi_ids) > 1 or self._enrichment_counters['episodes_processed'] > 1:
                self.logger.info(f"Successfully enriched {success_count} out of {len(kodi_ids)} episodes")

            return result

        except Exception as e:
            self.logger.error(f"Error fetching episode enrichment data: {e}")
            import traceback
            self.logger.error(f"Enrichment error traceback: {traceback.format_exc()}")
            return {}

    def _get_kodi_enrichment_data(self, kodi_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch rich metadata from Kodi JSON-RPC for the given kodi_ids"""
        try:
            import xbmc

            if not kodi_ids:
                return {}

            # Handle batch logging: log details only for the first batch or single items
            if len(kodi_ids) == 1 or self._enrichment_counters['movies_processed'] == 0:
                self.logger.info(f"Fetching JSON-RPC data for {len(kodi_ids)} movies: {kodi_ids}")

            enriched = self.json_rpc_client.get_movies_batch(kodi_ids)
            if not enriched:
                self.logger.warning("No JSON-RPC data returned for movies")
                return {}

            # Process each movie
            result = {}
            success_count = 0
            for movie_data in enriched:
                movie_id = movie_data.get('movieid')
                if not movie_id:
                    continue

                title = movie_data.get('title', 'Unknown')
                result[movie_id] = movie_data
                success_count += 1
                self._enrichment_counters['movies_enriched'] += 1

                # Only log first enrichment in detail
                if self._enrichment_counters['movies_enriched'] == 1:
                    self.logger.info(f"Successfully enriched movie {movie_id}: {title}")

            self._enrichment_counters['movies_processed'] += len(kodi_ids)

            # Log summary for batches or single items after first
            if len(kodi_ids) > 1 or self._enrichment_counters['movies_processed'] > 1:
                self.logger.info(f"Successfully enriched {success_count} out of {len(kodi_ids)} movies")

            return result

        except Exception as e:
            self.logger.error(f"Error fetching Kodi enrichment data: {e}")
            import traceback
            self.logger.error(f"Enrichment error traceback: {traceback.format_exc()}")
            return {}

    def _enrich_with_kodi_data(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich items with data from Kodi JSON-RPC if kodi_id is available"""
        if not items:
            return []

        # Separate movie and episode IDs
        movie_ids = [item['kodi_id'] for item in items if item.get('kodi_id') and item.get('media_type') == 'movie']
        episode_ids = [item['kodi_id'] for item in items if item.get('kodi_id') and item.get('media_type') == 'episode']

        enriched_data = {}

        # Fetch movie data
        if movie_ids:
            movie_data = self._get_kodi_enrichment_data(movie_ids)
            enriched_data.update(movie_data)

        # Fetch episode data
        if episode_ids:
            episode_data = self._get_kodi_episode_enrichment_data(episode_ids)
            enriched_data.update(episode_data)

        # Log summary at the end of processing all items if any enrichment happened
        self._log_enrichment_summary()

        enriched_items = []
        for item in items:
            kodi_id = item.get('kodi_id')
            if kodi_id in enriched_data:
                # Merge enriched data, prioritizing enriched fields
                enriched_item = enriched_data[kodi_id].copy()
                # Ensure we don't overwrite existing non-Kodi data unnecessarily
                # Update item with enriched data, but keep original if not in enriched or if enriched is empty/default
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


# Global query manager instance
_query_manager_instance = None

def get_query_manager():
    """Get or create the global query manager instance"""
    global _query_manager_instance
    if _query_manager_instance is None:
        from .storage_manager import get_storage_manager
        db_manager = get_storage_manager()
        _query_manager_instance = QueryManager(db_manager)
    return _query_manager_instance


def close():
    """Close database connections"""
    global _query_manager_instance
    if _query_manager_instance:
        _query_manager_instance.close()
        _query_manager_instance = None