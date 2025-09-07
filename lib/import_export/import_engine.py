#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Import Engine
Safely imports and merges JSON/CSV data with validation and preview
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Tuple
from .data_schemas import ExportSchema, ImportPreview, ImportResult
from .storage_manager import get_storage_manager
from ..data.connection_manager import get_connection_manager
from ..data import QueryManager
from ..utils.logger import get_logger


class DataMatcher:
    """Matches imported data to existing library movies"""

    def __init__(self, conn_manager):
        self.conn_manager = conn_manager
        self.logger = get_logger(__name__)

    def match_movie(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match imported item to library movie, return library_movie_id"""
        try:
            # Method 1: Match by Kodi ID (most reliable)
            if item_data.get("kodi_id"):
                movie_id = self._match_by_kodi_id(item_data["kodi_id"])
                if movie_id:
                    return movie_id

            # Method 2: Match by external IDs (IMDb, TMDb)
            if item_data.get("imdb_id") or item_data.get("tmdb_id"):
                movie_id = self._match_by_external_ids(item_data)
                if movie_id:
                    return movie_id

            # Method 3: Match by title, year, and path
            movie_id = self._match_by_title_year_path(item_data)
            if movie_id:
                return movie_id

            return None

        except Exception as e:
            self.logger.error(f"Error matching movie: {e}")
            return None

    def _match_by_kodi_id(self, kodi_id: int) -> Optional[int]:
        """Match by Kodi database ID"""
        result = self.conn_manager.execute_single(
            "SELECT id FROM media_items WHERE kodi_id = ? AND is_removed = 0",
            [kodi_id]
        )

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')
        return None

    def _match_by_external_ids(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match by IMDb or TMDb ID"""
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

    def _match_by_title_year_path(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Match by title, year, and file path"""
        title = item_data.get("title")
        year = item_data.get("year")
        normalized_path = item_data.get("normalized_path") or item_data.get("file_path")  # fallback for old exports

        if not title:
            return None

        # Build query conditions
        conditions = ["title = ?", "is_removed = 0"]
        params = [title]

        if year:
            conditions.append("year = ?")
            params.append(year)

        if normalized_path:
            conditions.append("normalized_path = ?")
            params.append(normalized_path)

        query = f"SELECT id FROM media_items WHERE {' AND '.join(conditions)}"
        result = self.conn_manager.execute_single(query, params)

        if result:
            return result[0] if hasattr(result, '__getitem__') else result.get('id')

        # If no exact match, try fuzzy title match without path
        if normalized_path:
            fuzzy_query = "SELECT id FROM media_items WHERE title = ? AND is_removed = 0"
            fuzzy_params = [title]
            if year:
                fuzzy_query += " AND year = ?"
                fuzzy_params.append(year)

            result = self.conn_manager.execute_single(fuzzy_query, fuzzy_params)
            if result:
                return result[0] if hasattr(result, '__getitem__') else result.get('id')

        return None


class ImportEngine:
    """Handles import operations with safe merging"""

    def __init__(self):
        self.logger = get_logger(__name__)
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
            self.logger.error(f"Error validating import file: {e}")
            return {"valid": False, "errors": [str(e)]}

    def preview_import(self, file_path: str) -> ImportPreview:
        """Generate preview of import operations"""
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

            # Initialize preview
            lists_to_create = []
            lists_to_update = []
            items_to_add = 0
            items_already_present = 0
            items_unmatched = 0
            warnings = []

            # Check lists
            if "lists" in payload:
                existing_lists = self._get_existing_list_names()

                for list_data in payload["lists"]:
                    list_name = list_data.get("name", "")
                    if list_name in existing_lists:
                        lists_to_update.append(list_name)
                    else:
                        lists_to_create.append(list_name)

            # Check list items
            if "list_items" in payload:
                for item_data in payload["list_items"]:
                    movie_id = self.matcher.match_movie(item_data)
                    if movie_id:
                        # Check if already in list
                        list_id = item_data.get("list_id")
                        if self._is_item_in_list(movie_id, list_id):
                            items_already_present += 1
                        else:
                            items_to_add += 1
                    else:
                        items_unmatched += 1

            total_operations = len(lists_to_create) + len(lists_to_update) + items_to_add

            # Add warnings
            if items_unmatched > 0:
                warnings.append(f"{items_unmatched} items could not be matched to library movies")

            if items_already_present > 0:
                warnings.append(f"{items_already_present} items are already in lists (will be skipped)")

            return ImportPreview(
                lists_to_create=lists_to_create,
                lists_to_update=lists_to_update,
                items_to_add=items_to_add,
                items_already_present=items_already_present,
                items_unmatched=items_unmatched,
                total_operations=total_operations,
                warnings=warnings
            )

        except Exception as e:
            self.logger.error(f"Error creating import preview: {e}")
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

            # Import lists first
            if "lists" in payload:
                created, updated, list_errors = self._import_lists(payload["lists"])
                lists_created += created
                lists_updated += updated
                errors.extend(list_errors)

            # Import list items
            if "list_items" in payload:
                added, skipped, unmatched, unmatch_data, item_errors = self._import_list_items(payload["list_items"])
                items_added += added
                items_skipped += skipped
                items_unmatched += unmatched
                unmatched_items.extend(unmatch_data)
                errors.extend(item_errors)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            success = len(errors) == 0 or (lists_created + items_added > 0)

            self.logger.info(f"Import completed: {lists_created} lists created, {items_added} items added")

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
            self.logger.error(f"Import error: {e}")
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

    def _import_lists(self, lists_data: List[Dict], replace_mode: bool = False) -> Tuple[int, int, List[str]]:
        """Import lists, return (created_count, updated_count, errors)"""
        created = 0
        updated = 0
        errors = []

        for list_data in lists_data:
            try:
                name = list_data.get("name")
                description = list_data.get("description", "")

                if not name:
                    errors.append("List missing name, skipped")
                    continue

                if replace_mode:
                    # In replace mode, always create new lists
                    result = self.query_manager.create_list(name, description)
                    if result and result.get("success"):
                        created += 1
                    else:
                        errors.append(f"Failed to create list: {name}")
                else:
                    # In append mode, check if list exists
                    existing = self.conn_manager.execute_single(
                        "SELECT id FROM lists WHERE name = ?", [name]
                    )

                    if existing:
                        # Update existing list description if different
                        self.conn_manager.execute_single(
                            "UPDATE lists SET description = ?, updated_at = datetime('now') WHERE name = ?",
                            [description, name]
                        )
                        updated += 1
                    else:
                        # Create new list
                        result = self.query_manager.create_list(name, description)
                        if result and result.get("success"):
                            created += 1
                        else:
                            errors.append(f"Failed to create list: {name}")

            except Exception as e:
                errors.append(f"Error importing list {list_data.get('name', 'unknown')}: {e}")

        return created, updated, errors

    def _import_list_items(self, items_data: List[Dict], replace_mode: bool = False) -> Tuple[int, int, int, List[Dict], List[str]]:
        """Import list items, return (added, skipped, unmatched, unmatched_data, errors)"""
        added = 0
        skipped = 0
        unmatched = 0
        unmatched_items = []
        errors = []

        for item_data in items_data:
            try:
                list_id = item_data.get("list_id")
                if not list_id:
                    errors.append("List item missing list_id, skipped")
                    continue

                # Match to library movie
                movie_id = self.matcher.match_movie(item_data)

                if not movie_id:
                    unmatched += 1
                    unmatched_items.append({
                        "title": item_data.get("title", "Unknown"),
                        "year": item_data.get("year"),
                        "normalized_path": item_data.get("normalized_path") or item_data.get("file_path", "")
                    })
                    continue

                if replace_mode:
                    # In replace mode, add all items without checking for duplicates
                    # (existing items were already cleared)
                    success = self.conn_manager.execute_single(
                        "INSERT INTO list_items (list_id, media_item_id, created_at) VALUES (?, ?, datetime('now'))",
                        [list_id, movie_id]
                    )
                    if success is not None:
                        added += 1
                    else:
                        errors.append(f"Failed to add item to list: {item_data.get('title', 'unknown')}")
                else:
                    # In append mode, check if already in list to avoid duplicates
                    if self._is_item_in_list(movie_id, list_id):
                        skipped += 1
                        continue

                    # Add to list
                    success = self.conn_manager.execute_single(
                        "INSERT OR IGNORE INTO list_items (list_id, media_item_id, created_at) VALUES (?, ?, datetime('now'))",
                        [list_id, movie_id]
                    )

                    if success is not None:
                        added += 1
                    else:
                        errors.append(f"Failed to add item to list: {item_data.get('title', 'unknown')}")

            except Exception as e:
                errors.append(f"Error importing item {item_data.get('title', 'unknown')}: {e}")

        return added, skipped, unmatched, unmatched_items, errors

    def import_from_content(self, content: str, filename: str, replace_mode: bool = False) -> Dict[str, Any]:
        """Import data from file content string (used by backup restoration)"""
        start_time = datetime.now()

        try:
            self.logger.info(f"RESTORE_DEBUG: Starting import from content, filename: {filename}, replace_mode: {replace_mode}")

            # Parse content
            try:
                data = json.loads(content)
                self.logger.debug(f"RESTORE_DEBUG: Successfully parsed JSON, keys: {list(data.keys())}")
            except json.JSONDecodeError as e:
                self.logger.error(f"RESTORE_DEBUG: JSON decode error: {e}")
                return {"success": False, "error": f"Invalid JSON in {filename}: {e}"}

            # Validate envelope structure
            envelope_errors = ExportSchema.validate_envelope(data)
            if envelope_errors:
                self.logger.error(f"RESTORE_DEBUG: Envelope validation errors: {envelope_errors}")
                return {"success": False, "error": f"Invalid backup format: {envelope_errors[0]}"}

            payload = data.get("payload", {})
            self.logger.debug(f"RESTORE_DEBUG: Payload keys: {list(payload.keys())}")

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
                    self.logger.error(f"Error clearing data for replace mode: {e}")
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

            self.logger.info(f"Backup restore completed: {lists_created} lists created, {items_added} items added")

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
            self.logger.error(f"Error importing from content: {e}")
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