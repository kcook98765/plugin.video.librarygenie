#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Import Engine
Safely imports and merges JSON/CSV data with validation and preview
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Tuple
from lib.import_export.data_schemas import ExportSchema, ImportPreview, ImportResult
from lib.data.storage_manager import get_storage_manager
from lib.data.connection_manager import get_connection_manager
from lib.data import QueryManager
from lib.utils.kodi_log import get_kodi_logger


class DataMatcher:
    """Matches imported data to existing library movies"""

    def __init__(self, conn_manager):
        self.conn_manager = conn_manager
        self.logger = get_kodi_logger('lib.import_export.import_engine')

    def match_media_item(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match imported media item based on its type (movie, episode, external)"""
        try:
            # Safe media_type handling with fallback detection
            media_type = str(item_data.get('media_type', '')).lower() if item_data.get('media_type') else ''
            
            # Handle mixed lists and fallback detection
            if media_type in {'videos', '', 'unknown'} or not media_type:
                # For mixed lists or unknown types, infer from content
                if item_data.get('tvshowtitle') or item_data.get('season') is not None or item_data.get('episode') is not None:
                    media_type = 'episode'
                else:
                    media_type = 'movie'  # Default fallback
            
            if media_type == 'episode':
                return self.match_episode(item_data)
            elif media_type == 'external':
                # External content: match by file path only to avoid wrong associations
                return self._match_by_file_path(item_data)
            else:
                # Use movie matching for movies and other content
                return self.match_movie(item_data)
                
        except Exception as e:
            self.logger.error("Error matching media item: %s", e)
            return None

    def match_movie(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match imported item to library movie, return media_item_id"""
        try:
            # Method 1: Match by Kodi ID (most reliable) - movie-specific
            if item_data.get("kodi_id"):
                movie_id = self._match_by_kodi_id_and_type(item_data["kodi_id"], 'movie')
                if movie_id:
                    return movie_id

            # Method 2: Match by external IDs (IMDb, TMDb) - movie-specific
            if item_data.get("imdb_id") or item_data.get("tmdb_id"):
                movie_id = self._match_by_external_ids_and_type(item_data, 'movie')
                if movie_id:
                    return movie_id

            # Method 3: Match by title, year, and path - movie-specific
            movie_id = self._match_by_title_year_path_and_type(item_data, 'movie')
            if movie_id:
                return movie_id

            return None

        except Exception as e:
            self.logger.error("Error matching movie: %s", e)
            return None

    def match_episode(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match imported episode to library using episode-specific logic"""
        try:
            # Method 1: Match by Kodi ID (most reliable) - episode-specific
            if item_data.get("kodi_id"):
                episode_id = self._match_by_kodi_id_and_type(item_data["kodi_id"], 'episode')
                if episode_id:
                    return episode_id

            # Method 2: Match by external IDs (rare for episodes) - episode-specific
            if item_data.get("imdb_id") or item_data.get("tmdb_id"):
                episode_id = self._match_by_external_ids_and_type(item_data, 'episode')
                if episode_id:
                    return episode_id

            # Method 3: Match by show title + season + episode (episode-specific)
            episode_id = self._match_by_show_season_episode(item_data)
            if episode_id:
                return episode_id

            # Method 4: Fallback to file path matching
            if item_data.get("file_path"):
                episode_id = self._match_by_file_path(item_data)
                if episode_id:
                    return episode_id

            return None

        except Exception as e:
            self.logger.error("Error matching episode: %s", e)
            return None

    def _match_by_kodi_id(self, kodi_id: int) -> Optional[int]:
        """Legacy method - Match by Kodi database ID (no media_type constraint)"""
        result = self.conn_manager.execute_single(
            "SELECT id FROM media_items WHERE kodi_id = ? AND is_removed = 0",
            [kodi_id]
        )

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        return None
    
    def _match_by_kodi_id_and_type(self, kodi_id: int, media_type: str) -> Optional[int]:
        """Match by Kodi database ID with media_type constraint"""
        result = self.conn_manager.execute_single(
            "SELECT id FROM media_items WHERE kodi_id = ? AND media_type = ? AND is_removed = 0",
            [kodi_id, media_type]
        )

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        return None

    def _match_by_external_ids(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Legacy method - Match by IMDb or TMDb ID (no media_type constraint)"""
        conditions = []
        params = []

        # Primary match by IMDb ID (most reliable for backup/restore)
        if item_data.get("imdb_id"):
            conditions.append("imdbnumber = ?")
            params.append(item_data["imdb_id"])

        if item_data.get("tmdb_id"):
            conditions.append("tmdb_id = ?")
            params.append(item_data["tmdb_id"])

        if not conditions:
            return None

        query = f"SELECT id FROM media_items WHERE ({' OR '.join(conditions)}) AND is_removed = 0"
        result = self.conn_manager.execute_single(query, params)

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        return None
    
    def _match_by_external_ids_and_type(self, item_data: Dict[str, Any], media_type: str) -> Optional[int]:
        """Match by IMDb or TMDb ID with media_type constraint"""
        imdb_id = item_data.get("imdb_id")
        tmdb_id = item_data.get("tmdb_id")

        if not imdb_id and not tmdb_id:
            return None

        # If both IDs present, try AND first for precision
        if imdb_id and tmdb_id:
            query = "SELECT id FROM media_items WHERE imdbnumber = ? AND tmdb_id = ? AND media_type = ? AND is_removed = 0"
            params = [imdb_id, tmdb_id, media_type]
            result = self.conn_manager.execute_single(query, params)
            if result:
                return result[0] if hasattr(result, '__getitem__') else result.get('id')

        # Fallback to OR logic (prefer IMDb when both present)
        conditions = []
        params = []

        if imdb_id:
            conditions.append("imdbnumber = ?")
            params.append(imdb_id)

        if tmdb_id:
            conditions.append("tmdb_id = ?")
            params.append(tmdb_id)

        query = f"SELECT id FROM media_items WHERE ({' OR '.join(conditions)}) AND media_type = ? AND is_removed = 0"
        params.append(media_type)
        result = self.conn_manager.execute_single(query, params)

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        return None

    def _match_by_title_year_path(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Legacy method - Match by title, year, and file path (no media_type constraint)"""
        title = item_data.get("title")
        year = item_data.get("year")
        file_path = item_data.get("file_path")

        if not title:
            return None

        # Build query conditions
        conditions = ["title = ?", "is_removed = 0"]
        params = [title]

        if year:
            conditions.append("year = ?")
            params.append(year)

        if file_path:
            conditions.append("file_path = ?")
            params.append(file_path)

        query = f"SELECT id FROM media_items WHERE {' AND '.join(conditions)}"
        result = self.conn_manager.execute_single(query, params)

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')

        # If no exact match, try fuzzy title match without path
        if file_path:
            fuzzy_query = "SELECT id FROM media_items WHERE title = ? AND is_removed = 0"
            fuzzy_params = [title]
            if year:
                fuzzy_query += " AND year = ?"
                fuzzy_params.append(year)

            result = self.conn_manager.execute_single(fuzzy_query, fuzzy_params)
            if result:
                return result[0] if hasattr(result, '__getitem__') else result.get('id')

        return None
    
    def _match_by_title_year_path_and_type(self, item_data: Dict[str, Any], media_type: str) -> Optional[int]:
        """Match by title, year, and file path with media_type constraint"""
        title = item_data.get("title")
        year = item_data.get("year")
        file_path = item_data.get("file_path")

        if not title:
            return None

        # Build query conditions
        conditions = ["title = ?", "media_type = ?", "is_removed = 0"]
        params = [title, media_type]

        if year:
            conditions.append("year = ?")
            params.append(year)

        if file_path:
            conditions.append("file_path = ?")
            params.append(file_path)

        query = f"SELECT id FROM media_items WHERE {' AND '.join(conditions)}"
        result = self.conn_manager.execute_single(query, params)

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')

        # If no exact match, try fuzzy title match without path
        if file_path:
            fuzzy_query = "SELECT id FROM media_items WHERE title = ? AND media_type = ? AND is_removed = 0"
            fuzzy_params = [title, media_type]
            if year:
                fuzzy_query += " AND year = ?"
                fuzzy_params.append(year)

            result = self.conn_manager.execute_single(fuzzy_query, fuzzy_params)
            if result:
                return result[0] if hasattr(result, '__getitem__') else result.get('id')

        return None

    def _match_by_show_season_episode(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match episode by show title + season + episode combination"""
        show_title = item_data.get("tvshowtitle")
        season = item_data.get("season")
        episode = item_data.get("episode")
        
        if not show_title or season is None or episode is None:
            return None
        
        # Safely cast season and episode to integers
        try:
            season_int = int(season)
            episode_int = int(episode)
        except (ValueError, TypeError):
            self.logger.warning("Invalid season (%s) or episode (%s) values for show '%s'", season, episode, show_title)
            return None
        
        # Use case-insensitive matching for show title with integer season/episode
        query = """
            SELECT id FROM media_items 
            WHERE LOWER(tvshowtitle) = LOWER(?) 
            AND season = ? 
            AND episode = ? 
            AND media_type = 'episode'
            AND is_removed = 0
        """
        params = [show_title, season_int, episode_int]
        
        result = self.conn_manager.execute_single(query, params)
        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        
        return None
    
    def _match_by_file_path(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match by file path as fallback (works for any media type)"""
        file_path = item_data.get("file_path")
        if not file_path:
            return None
        
        query = "SELECT id FROM media_items WHERE file_path = ? AND is_removed = 0"
        result = self.conn_manager.execute_single(query, [file_path])
        
        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        
        return None


class ImportEngine:
    """Handles import operations with safe merging"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.import_engine')
        self.conn_manager = get_connection_manager()
        self.storage_manager = get_storage_manager()
        self.query_manager = QueryManager()
        self.matcher = DataMatcher(self.conn_manager)

        # Size limits for safety
        self.max_import_size_mb = 50
        self.max_items_per_type = 10000

    def validate_import_file(self, file_path: str) -> Dict[str, Any]:
        """Validate import file structure and content"""
        try:
            # Check file exists and size
            if not self.storage_manager.validate_file_path(file_path):
                return {"valid": False, "errors": ["Invalid file path"]}

            file_size = self.storage_manager.get_file_size(file_path)
            if file_size > self.max_import_size_mb * 1024 * 1024:
                return {"valid": False, "errors": [f"File too large (max {self.max_import_size_mb}MB)"]}

            # Read and parse file
            content = self.storage_manager.read_file_safe(file_path)
            if not content:
                return {"valid": False, "errors": ["Could not read file"]}

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                return {"valid": False, "errors": [f"Invalid JSON: {e}"]}

            # Validate envelope structure
            envelope_errors = ExportSchema.validate_envelope(data)
            if envelope_errors:
                return {"valid": False, "errors": envelope_errors}

            # Validate each export type
            payload_errors = []
            for export_type in data.get("export_types", []):
                if export_type in data.get("payload", {}):
                    type_data = data["payload"][export_type]

                    # Check item count limits
                    if len(type_data) > self.max_items_per_type:
                        payload_errors.append(f"{export_type}: too many items (max {self.max_items_per_type})")
                        continue

                    # Validate structure
                    type_errors = ExportSchema.validate_export_type(export_type, type_data)
                    payload_errors.extend(type_errors)

            if payload_errors:
                return {"valid": False, "errors": payload_errors}

            return {
                "valid": True,
                "schema_version": data.get("schema_version"),
                "export_types": data.get("export_types", []),
                "generated_at": data.get("generated_at"),
                "item_counts": {
                    export_type: len(data.get("payload", {}).get(export_type, []))
                    for export_type in data.get("export_types", [])
                }
            }

        except Exception as e:
            self.logger.error("Error validating import file: %s", e)
            return {"valid": False, "errors": [str(e)]}

    def preview_import(self, file_path: str) -> ImportPreview:
        """Generate preview of import operations (simplified for timestamped import folders)"""
        try:
            # First validate the file
            validation = self.validate_import_file(file_path)
            if not validation["valid"]:
                return ImportPreview(
                    lists_to_create=[],
                    lists_to_update=[],
                    items_to_add=0,
                    items_already_present=0,
                    items_unmatched=0,
                    total_operations=0,
                    warnings=validation["errors"]
                )

            # Load and parse file
            content = self.storage_manager.read_file_safe(file_path)
            if content is None:
                return ImportPreview(
                    lists_to_create=[],
                    lists_to_update=[],
                    items_to_add=0,
                    items_already_present=0,
                    items_unmatched=0,
                    total_operations=0,
                    warnings=["Could not read file content"]
                )
            data = json.loads(content)
            payload = data.get("payload", {})

            # Initialize preview - simplified for timestamped import folders
            lists_to_create = []
            items_to_add = 0
            items_unmatched = 0
            warnings = []

            # Count lists to create (all lists will be new since importing to timestamped folder)
            if "lists" in payload:
                for list_data in payload["lists"]:
                    list_name = list_data.get("name", "")
                    if list_name:
                        lists_to_create.append(list_name)

            # Count items to add/unmatched (no duplicates since new folder)
            if "list_items" in payload:
                for item_data in payload["list_items"]:
                    media_item_id = self.matcher.match_media_item(item_data)
                    if media_item_id:
                        items_to_add += 1
                    else:
                        items_unmatched += 1

            total_operations = len(lists_to_create) + items_to_add

            # Add warnings
            if items_unmatched > 0:
                warnings.append(f"{items_unmatched} items could not be matched to library movies")

            return ImportPreview(
                lists_to_create=lists_to_create,
                lists_to_update=[],  # No updates since importing to new folder
                items_to_add=items_to_add,
                items_already_present=0,  # No duplicates since new folder
                items_unmatched=items_unmatched,
                total_operations=total_operations,
                warnings=warnings
            )

        except Exception as e:
            self.logger.error("Error creating import preview: %s", e)
            return ImportPreview(
                lists_to_create=[],
                lists_to_update=[],
                items_to_add=0,
                items_already_present=0,
                items_unmatched=0,
                total_operations=0,
                warnings=[str(e)]
            )

    def import_data(self, file_path: str) -> ImportResult:
        """Import data from file with safe merging"""
        start_time = datetime.now()

        try:
            # Create timestamped import folder first
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            import_folder_name = f"Import {timestamp}"
            
            import_folder_result = self.query_manager.create_folder(import_folder_name)
            if not import_folder_result.get("success"):
                return ImportResult(
                    success=False,
                    lists_created=0,
                    lists_updated=0,
                    items_added=0,
                    items_skipped=0,
                    items_unmatched=0,
                    unmatched_items=[],
                    errors=[f"Failed to create import folder: {import_folder_result.get('error', 'Unknown error')}"],
                    duration_ms=0
                )
            
            import_folder_id = import_folder_result.get("folder_id")
            self.logger.info("Created import folder '%s' with ID %s", import_folder_name, import_folder_id)
            
            # Validate file first
            validation = self.validate_import_file(file_path)
            if not validation["valid"]:
                return ImportResult(
                    success=False,
                    lists_created=0,
                    lists_updated=0,
                    items_added=0,
                    items_skipped=0,
                    items_unmatched=0,
                    unmatched_items=[],
                    errors=validation["errors"],
                    duration_ms=0
                )

            # Load data
            content = self.storage_manager.read_file_safe(file_path)
            if content is None:
                return ImportResult(
                    success=False,
                    lists_created=0,
                    lists_updated=0,
                    items_added=0,
                    items_skipped=0,
                    items_unmatched=0,
                    unmatched_items=[],
                    errors=["Could not read file content"],
                    duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                )
            data = json.loads(content)
            payload = data.get("payload", {})

            # Initialize counters
            lists_created = 0
            lists_updated = 0
            items_added = 0
            items_skipped = 0
            items_unmatched = 0
            unmatched_items = []
            errors = []

            # Initialize database
            self.query_manager.initialize()

            # Track old->new list ID mapping
            list_id_mapping = {}

            # Import lists first (into the timestamped folder)
            if "lists" in payload:
                created, updated, list_errors, id_mapping = self._import_lists(
                    payload["lists"], target_folder_id=import_folder_id
                )
                lists_created += created
                lists_updated += updated
                errors.extend(list_errors)
                list_id_mapping.update(id_mapping)

            # Import list items with corrected list IDs
            if "list_items" in payload:
                added, skipped, unmatched, unmatch_data, item_errors = self._import_list_items(
                    payload["list_items"], list_id_mapping=list_id_mapping
                )
                items_added += added
                items_skipped += skipped
                items_unmatched += unmatched
                unmatched_items.extend(unmatch_data)
                errors.extend(item_errors)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            success = len(errors) == 0 or (lists_created + items_added > 0)

            self.logger.info("Import completed: %s lists created, %s items added", lists_created, items_added)

            return ImportResult(
                success=success,
                lists_created=lists_created,
                lists_updated=lists_updated,
                items_added=items_added,
                items_skipped=items_skipped,
                items_unmatched=items_unmatched,
                unmatched_items=unmatched_items[:10],  # Limit to first 10 for UI
                errors=errors,
                duration_ms=duration_ms
            )

        except Exception as e:
            self.logger.error("Import error: %s", e)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return ImportResult(
                success=False,
                lists_created=0,
                lists_updated=0,
                items_added=0,
                items_skipped=0,
                items_unmatched=0,
                unmatched_items=[],
                errors=[str(e)],
                duration_ms=duration_ms
            )

    def _get_existing_list_names(self) -> Set[str]:
        """Get set of existing list names"""
        try:
            lists = self.conn_manager.execute_query("SELECT name FROM lists")
            return {list_row[0] if hasattr(list_row, '__getitem__') else list_row.get('name') for list_row in lists or []}
        except Exception:
            return set()

    def _is_item_in_list(self, library_movie_id: int, list_id: int) -> bool:
        """Check if item is already in list"""
        try:
            result = self.conn_manager.execute_single(
                "SELECT 1 FROM list_items WHERE media_item_id = ? AND list_id = ?",
                [library_movie_id, list_id]
            )
            return result is not None
        except Exception:
            return False

    def _import_lists(self, lists_data: List[Dict], replace_mode: bool = False, target_folder_id: str = None) -> Tuple[int, int, List[str], Dict[str, str]]:
        """Import lists, return (created_count, updated_count, errors, list_id_mapping)"""
        created = 0
        updated = 0
        errors = []
        list_id_mapping = {}  # old_list_id -> new_list_id

        for list_data in lists_data:
            try:
                name = list_data.get("name")
                description = list_data.get("description", "")

                if not name:
                    errors.append("List missing name, skipped")
                    continue

                # Get the original list ID for mapping
                old_list_id = str(list_data.get("id")) if list_data.get("id") else None

                if replace_mode:
                    # In replace mode, always create new lists
                    result = self.query_manager.create_list(name, description, target_folder_id)
                    if result and not result.get("error"):  # Success = no error key
                        new_list_id = result.get("id")
                        if old_list_id and new_list_id:
                            list_id_mapping[old_list_id] = str(new_list_id)
                        created += 1
                    else:
                        error_detail = result.get("error", "Unknown error") if result else "No result returned"
                        errors.append(f"Failed to create list: {name} ({error_detail})")
                else:
                    # In append mode, check if list exists in target folder
                    where_clause = "name = ? AND folder_id IS ?" if target_folder_id is None else "name = ? AND folder_id = ?"
                    existing = self.conn_manager.execute_single(
                        f"SELECT id FROM lists WHERE {where_clause}", [name, target_folder_id]
                    )

                    if existing:
                        # Update existing list description if different
                        existing_id = str(existing[0]) if hasattr(existing, '__getitem__') else str(existing.get('id'))
                        self.conn_manager.execute_single(
                            "UPDATE lists SET description = ?, updated_at = datetime('now') WHERE id = ?",
                            [description, existing_id]
                        )
                        if old_list_id and existing_id:
                            list_id_mapping[old_list_id] = str(existing_id)
                        updated += 1
                    else:
                        # Create new list in target folder
                        result = self.query_manager.create_list(name, description, target_folder_id)
                        if result and not result.get("error"):  # Success = no error key
                            new_list_id = result.get("id")
                            if old_list_id and new_list_id:
                                list_id_mapping[old_list_id] = str(new_list_id)
                            created += 1
                        else:
                            error_detail = result.get("error", "Unknown error") if result else "No result returned"
                            errors.append(f"Failed to create list: {name} ({error_detail})")

            except Exception as e:
                errors.append(f"Error importing list {list_data.get('name', 'unknown')}: {e}")

        return created, updated, errors, list_id_mapping

    def _import_list_items(self, items_data: List[Dict], replace_mode: bool = False, list_id_mapping: Dict[str, str] = None) -> Tuple[int, int, int, List[Dict], List[str]]:
        """Import list items, return (added, skipped, unmatched, unmatched_data, errors)"""
        added = 0
        skipped = 0
        unmatched = 0
        unmatched_items = []
        errors = []

        for item_data in items_data:
            try:
                old_list_id = item_data.get("list_id")
                if not old_list_id:
                    errors.append("List item missing list_id, skipped")
                    continue

                # Map old list ID to new list ID
                old_list_id = str(old_list_id)  # Ensure string format
                list_id = list_id_mapping.get(old_list_id) if list_id_mapping else old_list_id
                
                if not list_id:
                    errors.append(f"Cannot find mapped list for old ID {old_list_id}, skipped item: {item_data.get('title', 'unknown')}")
                    continue

                # Match to library media item (movie, episode, or external)
                media_item_id = self.matcher.match_media_item(item_data)

                if not media_item_id:
                    unmatched += 1
                    unmatched_items.append({
                        "title": item_data.get("title", "Unknown"),
                        "year": item_data.get("year"),
                        "file_path": item_data.get("file_path", "")
                    })
                    continue

                if replace_mode:
                    # In replace mode, add all items without checking for duplicates
                    # (existing items were already cleared)
                    try:
                        with self.conn_manager.transaction() as conn:
                            conn.execute(
                                "INSERT INTO list_items (list_id, media_item_id, created_at) VALUES (?, ?, datetime('now'))",
                                [list_id, media_item_id]
                            )
                        added += 1
                    except Exception as db_error:
                        self.logger.error("Database error adding item '%s' to list_id %s: %s", item_data.get('title', 'unknown'), list_id, db_error)
                        errors.append(f"Failed to add item to list: {item_data.get('title', 'unknown')} (DB Error: {db_error})")
                else:
                    # In append mode, check if already in list to avoid duplicates
                    if self._is_item_in_list(media_item_id, list_id):
                        skipped += 1
                        continue

                    # Add to list
                    try:
                        with self.conn_manager.transaction() as conn:
                            conn.execute(
                                "INSERT OR IGNORE INTO list_items (list_id, media_item_id, created_at) VALUES (?, ?, datetime('now'))",
                                [list_id, media_item_id]
                            )
                        added += 1
                    except Exception as db_error:
                        self.logger.error("Database error adding item '%s' to list_id %s: %s", item_data.get('title', 'unknown'), list_id, db_error)
                        errors.append(f"Failed to add item to list: {item_data.get('title', 'unknown')} (DB Error: {db_error})")

            except Exception as e:
                errors.append(f"Error importing item {item_data.get('title', 'unknown')}: {e}")

        return added, skipped, unmatched, unmatched_items, errors

    def import_from_content(self, content: str, filename: str, replace_mode: bool = False) -> Dict[str, Any]:
        """Import data from file content string (used by backup restoration)"""
        start_time = datetime.now()

        try:
            # Parse content
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Invalid JSON in {filename}: {e}"}

            # Validate envelope structure
            envelope_errors = ExportSchema.validate_envelope(data)
            if envelope_errors:
                return {"success": False, "error": f"Invalid backup format: {envelope_errors[0]}"}

            payload = data.get("payload", {})

            # Initialize counters
            lists_created = 0
            lists_updated = 0
            items_added = 0
            items_skipped = 0
            items_unmatched = 0
            errors = []

            # Initialize database
            self.query_manager.initialize()

            # Handle replace mode - clear existing lists/folders but preserve media_items
            if replace_mode:
                try:
                    self.logger.info("Replace mode enabled - clearing existing lists and folders only")
                    # Delete all list items first (foreign key constraints)
                    self.conn_manager.execute_single("DELETE FROM list_items")
                    # Delete all lists except those in system folders
                    self.conn_manager.execute_single("DELETE FROM lists WHERE folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders WHERE name = 'Search History')")
                    # Delete non-system folders
                    self.conn_manager.execute_single("DELETE FROM folders WHERE name != 'Search History'")
                    # NOTE: media_items are preserved - they contain the addon's library index
                    self.logger.info("Existing lists and folders cleared for replace mode (media_items preserved)")
                except Exception as e:
                    self.logger.error("Error clearing data for replace mode: %s", e)
                    errors.append(f"Failed to clear existing data: {e}")

            # Import lists first
            if "lists" in payload:
                created, updated, list_errors = self._import_lists(payload["lists"], replace_mode)
                lists_created += created
                lists_updated += updated
                errors.extend(list_errors)

            # Import list items
            if "list_items" in payload:
                added, skipped, unmatched, unmatch_data, item_errors = self._import_list_items(payload["list_items"], replace_mode)
                items_added += added
                items_skipped += skipped
                items_unmatched += unmatched
                errors.extend(item_errors)

            # Import folders if present
            if "folders" in payload:
                folder_errors = self._import_folders(payload["folders"])
                errors.extend(folder_errors)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            success = len(errors) == 0 or (lists_created + items_added > 0)

            self.logger.info("Backup restore completed: %s lists created, %s items added", lists_created, items_added)

            return {
                "success": success,
                "lists_created": lists_created,
                "lists_updated": lists_updated,
                "items_added": items_added,
                "items_skipped": items_skipped,
                "items_unmatched": items_unmatched,
                "errors": errors,
                "duration_ms": duration_ms
            }

        except Exception as e:
            self.logger.error("Error importing from content: %s", e)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms
            }

    def _import_folders(self, folders_data: List[Dict]) -> List[str]:
        """Import folders data"""
        errors = []

        for folder_data in folders_data:
            try:
                name = folder_data.get("name")
                description = folder_data.get("description", "")

                if not name:
                    errors.append("Folder missing name, skipped")
                    continue

                # Check if folder exists
                existing = self.conn_manager.execute_single(
                    "SELECT id FROM folders WHERE name = ?", [name]
                )

                if not existing:
                    # Create new folder
                    self.conn_manager.execute_single(
                        "INSERT INTO folders (name, description, created_at) VALUES (?, ?, datetime('now'))",
                        [name, description]
                    )

            except Exception as e:
                errors.append(f"Error importing folder {folder_data.get('name', 'unknown')}: {e}")

        return errors


# Global import engine instance
_import_engine_instance = None


def get_import_engine():
    """Get global import engine instance"""
    global _import_engine_instance
    if _import_engine_instance is None:
        _import_engine_instance = ImportEngine()
    return _import_engine_instance