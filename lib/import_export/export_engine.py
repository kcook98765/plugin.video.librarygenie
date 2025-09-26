#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Export Engine
Creates JSON/CSV exports of lists, memberships, favorites, and library data
"""

import csv
import os
from datetime import datetime
from io import StringIO
from typing import List, Dict, Any, Optional, Tuple
from lib.import_export.data_schemas import ExportEnvelope
from lib.data.storage_manager import get_storage_manager
from lib.data.connection_manager import get_connection_manager
from lib.utils.kodi_log import get_kodi_logger
from lib.ui.dialog_service import get_dialog_service


class ExportEngine:
    """Handles all export operations with chunked processing"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.export_engine')
        self.conn_manager = get_connection_manager()
        self.storage_manager = get_storage_manager()
        self.chunk_size = 1000  # Process in chunks to maintain UI responsiveness

    def export_data(self, export_types: List[str], file_format: str = "json", 
                   custom_path: Optional[str] = None, context_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Export selected data types to file"""
        try:
            start_time = datetime.now()

            # Validate export types
            valid_types = {"lists", "list_items", "library_snapshot", "non_library_snapshot", "folders"}
            invalid_types = set(export_types) - valid_types
            if invalid_types:
                return {"success": False, "error": f"Invalid export types: {invalid_types}"}

            # Collect export data
            payload = {}
            total_items = 0

            for export_type in export_types:
                data, count = self._collect_export_data(export_type, context_filter)
                payload[export_type] = data
                total_items += count

                self.logger.info("Collected %s items for %s", count, export_type)

            # Create envelope
            envelope = ExportEnvelope.create(export_types, payload)

            # Generate filename and path
            export_name = "-".join(export_types)

            # Use custom path if provided, otherwise check export location setting
            if custom_path:
                file_path = custom_path
                filename = os.path.basename(file_path)
            else:
                # Check if export location is set in preferences
                from lib.config import get_config
                config = get_config()
                export_location = config.get_export_location()
                
                if not export_location:
                    # Prompt user to set export location
                    export_location = self._prompt_for_export_location(config)
                    if not export_location:
                        return {"success": False, "error": "Export location not set"}
                
                # Handle special:// paths
                if export_location.startswith('special://'):
                    import xbmcvfs
                    export_location = xbmcvfs.translatePath(export_location)
                
                # Create directory if it doesn't exist
                os.makedirs(export_location, exist_ok=True)
                
                filename = self.storage_manager.generate_filename(export_name, file_format)
                file_path = os.path.join(export_location, filename)

            # Write file
            success = False
            if file_format == "json":
                success = self._write_json_export(envelope, file_path)
            elif file_format == "csv":
                success = self._write_csv_export(payload, export_types, file_path)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            if success:
                file_size = self.storage_manager.get_file_size(file_path)
                return {
                    "success": True,
                    "file_path": file_path,
                    "filename": filename,
                    "export_types": export_types,
                    "total_items": total_items,
                    "file_size": file_size,
                    "duration_ms": duration_ms
                }
            else:
                return {"success": False, "error": "Failed to write export file"}

        except Exception as e:
            self.logger.error("Export error: %s", e)
            return {"success": False, "error": str(e)}

    def _collect_export_data(self, export_type: str, context_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], int]:
        """Collect data for specific export type with optional context filtering"""
        try:
            if export_type == "lists":
                return self._collect_lists_data(context_filter)
            elif export_type == "list_items":
                return self._collect_list_items_data(context_filter)
            elif export_type == "library_snapshot":
                return self._collect_library_snapshot_data(context_filter)
            elif export_type == "non_library_snapshot":
                return self._collect_non_library_snapshot_data(context_filter)
            elif export_type == "folders":
                return self._collect_folders_data(context_filter)
            else:
                return [], 0

        except Exception as e:
            self.logger.error("Error collecting %s data: %s", export_type, e)
            return [], 0

    def _collect_lists_data(self, context_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], int]:
        """Collect lists data with optional context filtering"""
        lists_data = []

        # Base query
        query = """
                SELECT l.id, l.name, l.created_at, '' as description,
                       COUNT(li.id) as item_count, l.folder_id
                FROM lists l
                LEFT JOIN list_items li ON l.id = li.list_id
            """
        params = []
        
        # Apply context filtering
        where_conditions = []
        if context_filter:
            if context_filter.get('list_id'):
                where_conditions.append("l.id = ?")
                params.append(context_filter['list_id'])
            elif context_filter.get('folder_id'):
                if context_filter.get('include_subfolders', False):
                    # Branch export: include current folder and ALL descendant subfolders recursively
                    where_conditions.append("""
                        l.folder_id IN (
                            WITH RECURSIVE descendant_folders(id) AS (
                                SELECT ? UNION ALL 
                                SELECT f.id FROM folders f 
                                JOIN descendant_folders df ON f.parent_id = df.id
                            )
                            SELECT id FROM descendant_folders
                        )
                    """)
                    params.append(context_filter['folder_id'])
                else:
                    # Single folder only
                    where_conditions.append("l.folder_id = ?")
                    params.append(context_filter['folder_id'])
        
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)
            
        query += " GROUP BY l.id, l.name, l.created_at, l.folder_id ORDER BY l.created_at"

        lists = self.conn_manager.execute_query(query, params)

        for list_row in lists or []:
            if hasattr(list_row, 'keys'):
                list_dict = dict(list_row)
            else:
                # Handle tuple/list format
                list_dict = {
                    'id': list_row[0],
                    'name': list_row[1],
                    'created_at': list_row[2],
                    'description': list_row[3] or "",
                    'item_count': list_row[4],
                    'folder_id': list_row[5]
                }

            lists_data.append(list_dict)

        return lists_data, len(lists_data)

    def _collect_list_items_data(self, context_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], int]:
        """Collect list items (membership) data with optional context filtering"""
        items_data = []

        # Base query
        query = """
                SELECT li.list_id, mi.kodi_id, mi.title, mi.year, mi.file_path,
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.media_type
                FROM list_items li
                INNER JOIN media_items mi ON li.media_item_id = mi.id
                WHERE mi.is_removed = 0
            """
        params = []
        
        # Apply context filtering
        additional_conditions = []
        if context_filter:
            if context_filter.get('list_id'):
                additional_conditions.append("li.list_id = ?")
                params.append(context_filter['list_id'])
            elif context_filter.get('folder_id'):
                if context_filter.get('include_subfolders', False):
                    # Branch export: include items from current folder and ALL descendant subfolders recursively
                    additional_conditions.append("""
                        li.list_id IN (
                            SELECT l.id FROM lists l 
                            WHERE l.folder_id IN (
                                WITH RECURSIVE descendant_folders(id) AS (
                                    SELECT ? UNION ALL 
                                    SELECT f.id FROM folders f 
                                    JOIN descendant_folders df ON f.parent_id = df.id
                                )
                                SELECT id FROM descendant_folders
                            )
                        )
                    """)
                    params.append(context_filter['folder_id'])
                else:
                    # Single folder only
                    additional_conditions.append("li.list_id IN (SELECT l.id FROM lists l WHERE l.folder_id = ?)")
                    params.append(context_filter['folder_id'])
        
        if additional_conditions:
            query += " AND " + " AND ".join(additional_conditions)
            
        query += " ORDER BY li.list_id, mi.title"

        items = self.conn_manager.execute_query(query, params)

        for item_row in items or []:
            if hasattr(item_row, 'keys'):
                item_dict = dict(item_row)
            else:
                # Handle tuple/list format
                item_dict = {
                    'list_id': item_row[0],
                    'kodi_id': item_row[1],
                    'title': item_row[2],
                    'year': item_row[3],
                    'file_path': item_row[4],
                    'imdb_id': item_row[5],
                    'tmdb_id': item_row[6],
                    'media_type': item_row[7]
                }

            # Add external IDs dictionary
            external_ids = {}
            if item_dict.get('imdb_id'):
                external_ids['imdb'] = item_dict['imdb_id']
            if item_dict.get('tmdb_id'):
                external_ids['tmdb'] = item_dict['tmdb_id']

            item_dict['external_ids'] = external_ids
            items_data.append(item_dict)

        return items_data, len(items_data)



    def _collect_library_snapshot_data(self, context_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], int]:
        """Collect library snapshot data"""
        library_data = []

        query = """
                SELECT kodi_id, title, year, file_path, imdbnumber as imdb_id, tmdb_id,
                       media_type, created_at, updated_at
                FROM media_items
                WHERE is_removed = 0
                ORDER BY title
            """
        params = () # Placeholder for potential future parameters

        movies = self.conn_manager.execute_query(query, params)

        for movie_row in movies or []:
            if hasattr(movie_row, 'keys'):
                movie_dict = dict(movie_row)
            else:
                # Handle tuple/list format
                movie_dict = {
                    'kodi_id': movie_row[0],
                    'title': movie_row[1],
                    'year': movie_row[2],
                    'file_path': movie_row[3],
                    'imdb_id': movie_row[4],
                    'tmdb_id': movie_row[5],
                    'media_type': movie_row[6],
                    'added_at': movie_row[7],
                    'updated_at': movie_row[8]
                }

            # Add external IDs
            external_ids = {}
            if movie_dict.get('imdb_id'):
                external_ids['imdb'] = movie_dict['imdb_id']
            if movie_dict.get('tmdb_id'):
                external_ids['tmdb'] = movie_dict['tmdb_id']

            movie_dict['external_ids'] = external_ids
            library_data.append(movie_dict)

        return library_data, len(library_data)

    def _collect_non_library_snapshot_data(self, context_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], int]:
        """Collect non-library media items data (items not currently in Kodi library)"""
        non_library_data = []

        # Query for media items that are marked as removed or not in current library
        query = """
                SELECT kodi_id, title, year, file_path, imdbnumber as imdb_id, tmdb_id,
                       media_type, created_at, updated_at
                FROM media_items
                WHERE is_removed = 1 OR kodi_id IS NULL OR kodi_id = 0
                ORDER BY title
            """
        params = ()

        items = self.conn_manager.execute_query(query, params)

        for item_row in items or []:
            if hasattr(item_row, 'keys'):
                item_dict = dict(item_row)
            else:
                # Handle tuple/list format
                item_dict = {
                    'kodi_id': item_row[0],
                    'title': item_row[1],
                    'year': item_row[2],
                    'file_path': item_row[3],
                    'imdb_id': item_row[4],
                    'tmdb_id': item_row[5],
                    'media_type': item_row[6],
                    'added_at': item_row[7],
                    'updated_at': item_row[8]
                }

            # Add external IDs
            external_ids = {}
            if item_dict.get('imdb_id'):
                external_ids['imdb'] = item_dict['imdb_id']
            if item_dict.get('tmdb_id'):
                external_ids['tmdb'] = item_dict['tmdb_id']

            item_dict['external_ids'] = external_ids
            non_library_data.append(item_dict)

        return non_library_data, len(non_library_data)

    def _collect_folders_data(self, context_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict], int]:
        """Collect folders data"""
        folders_data = []

        query = """
                SELECT f.id, f.name, f.created_at, '' as description,
                       COUNT(l.id) as list_count
                FROM folders f
                LEFT JOIN lists l ON f.id = l.folder_id
                GROUP BY f.id, f.name, f.created_at
                ORDER BY f.created_at
            """
        params = ()

        folders = self.conn_manager.execute_query(query, params)

        for folder_row in folders or []:
            if hasattr(folder_row, 'keys'):
                folder_dict = dict(folder_row)
            else:
                # Handle tuple/list format
                folder_dict = {
                    'id': folder_row[0],
                    'name': folder_row[1],
                    'created_at': folder_row[2],
                    'description': folder_row[3],
                    'list_count': folder_row[4]
                }

            folders_data.append(folder_dict)

        return folders_data, len(folders_data)

    def _write_json_export(self, envelope: ExportEnvelope, file_path: str) -> bool:
        """Write JSON export file"""
        try:
            content = envelope.to_json()
            return self.storage_manager.write_file_atomic(file_path, content)

        except Exception as e:
            self.logger.error("Error writing JSON export: %s", e)
            return False

    def _write_csv_export(self, payload: Dict[str, Any], export_types: List[str], file_path: str) -> bool:
        """Write CSV export file (for list_items mainly)"""
        try:
            if "list_items" not in export_types:
                # CSV format mainly for list memberships
                return False

            output = StringIO()
            writer = csv.writer(output)

            # Write header
            headers = ["list_id", "kodi_id", "title", "year", "file_path", "imdb_id", "tmdb_id"]
            writer.writerow(headers)

            # Write data
            for item in payload.get("list_items", []):
                row = [
                    item.get("list_id", ""),
                    item.get("kodi_id", ""),
                    item.get("title", ""),
                    item.get("year", ""),
                    item.get("file_path", ""),
                    item.get("imdb_id", ""),
                    item.get("tmdb_id", "")
                ]
                writer.writerow(row)

            content = output.getvalue()
            output.close()

            return self.storage_manager.write_file_atomic(file_path, content)

        except Exception as e:
            self.logger.error("Error writing CSV export: %s", e)
            return False

    def get_export_preview(self, export_types: List[str]) -> Dict[str, Any]:
        """Get preview of what would be exported"""
        try:
            preview = {
                "export_types": export_types,
                "totals": {},
                "estimated_size_kb": 0
            }

            for export_type in export_types:
                _, count = self._collect_export_data(export_type)
                preview["totals"][export_type] = count

            # Rough size estimate (JSON overhead + data)
            total_items = sum(preview["totals"].values())
            preview["estimated_size_kb"] = max(1, total_items * 0.5)  # ~500 bytes per item estimate

            return preview

        except Exception as e:
            self.logger.error("Error creating export preview: %s", e)
            return {"export_types": export_types, "totals": {}, "estimated_size_kb": 0}

    def _prompt_for_export_location(self, config) -> Optional[str]:
        """Prompt user to set export location and save it to settings"""
        try:
            dialog_service = get_dialog_service(logger_name='lib.import_export.export_engine._prompt_for_export_location')
            
            # Show information dialog first
            dialog_service.ok("Export Location Required", 
                     "You need to set an export location before exporting files. "
                     "Please select a folder where exported files will be saved.")
            
            # Prompt for folder selection
            export_path = dialog_service.browse(0, "Select Export Location", "files", "", False, False, "")
            
            if export_path:
                export_path = str(export_path).strip()
                
                # Save the path to settings
                config.set_export_location(export_path)
                
                self.logger.info("Export location set to: %s", export_path)
                
                # Show confirmation
                dialog_service.show_success("Export location set successfully")
                
                return export_path
            else:
                self.logger.info("User cancelled export location selection")
                return None
                
        except Exception as e:
            self.logger.error("Error prompting for export location: %s", e)
            return None


# Global export engine instance
_export_engine_instance = None


def get_export_engine():
    """Get global export engine instance"""
    global _export_engine_instance
    if _export_engine_instance is None:
        _export_engine_instance = ExportEngine()
    return _export_engine_instance