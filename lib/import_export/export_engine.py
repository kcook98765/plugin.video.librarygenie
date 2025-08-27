#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Export Engine
Creates JSON/CSV exports of lists, memberships, favorites, and library data
"""

import csv
import json
import os
from datetime import datetime
from io import StringIO
from typing import List, Dict, Any, Optional, Set, Tuple
from .data_schemas import ExportEnvelope, ExportedList, ExportedListItem, ExportedFavorite, ExportedLibraryItem
from .storage_manager import get_storage_manager
from ..data.connection_manager import get_connection_manager
from ..utils.logger import get_logger


class ExportEngine:
    """Handles all export operations with chunked processing"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.storage_manager = get_storage_manager()
        self.chunk_size = 1000  # Process in chunks to maintain UI responsiveness

    def export_data(self, export_types: List[str], file_format: str = "json", 
                   custom_path: Optional[str] = None) -> Dict[str, Any]:
        """Export selected data types to file"""
        try:
            start_time = datetime.now()

            # Validate export types
            valid_types = {"lists", "list_items", "favorites", "library_snapshot"}
            invalid_types = set(export_types) - valid_types
            if invalid_types:
                return {"success": False, "error": f"Invalid export types: {invalid_types}"}

            # Collect export data
            payload = {}
            total_items = 0

            for export_type in export_types:
                data, count = self._collect_export_data(export_type)
                payload[export_type] = data
                total_items += count

                self.logger.info(f"Collected {count} items for {export_type}")

            # Create envelope
            envelope = ExportEnvelope.create(export_types, payload)

            # Generate filename and path
            export_name = "-".join(export_types)
            filename = self.storage_manager.generate_filename(export_name, file_format)

            if custom_path:
                file_path = os.path.join(custom_path, filename)
            else:
                file_path = os.path.join(self.storage_manager.get_profile_path(), filename)

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
            self.logger.error(f"Export error: {e}")
            return {"success": False, "error": str(e)}

    def _collect_export_data(self, export_type: str) -> Tuple[List[Dict], int]:
        """Collect data for specific export type"""
        try:
            if export_type == "lists":
                return self._collect_lists_data()
            elif export_type == "list_items":
                return self._collect_list_items_data()
            elif export_type == "favorites":
                return self._collect_favorites_data()
            elif export_type == "library_snapshot":
                return self._collect_library_snapshot_data()
            else:
                return [], 0

        except Exception as e:
            self.logger.error(f"Error collecting {export_type} data: {e}")
            return [], 0

    def _collect_lists_data(self) -> Tuple[List[Dict], int]:
        """Collect lists data"""
        lists_data = []

        query = """
            SELECT l.id, l.name, l.description, l.created_at, l.updated_at,
                   COUNT(li.id) as item_count
            FROM list l
            LEFT JOIN list_item li ON l.id = li.list_id AND li.library_movie_id IS NOT NULL
            GROUP BY l.id, l.name, l.description, l.created_at, l.updated_at
            ORDER BY l.created_at
        """

        lists = self.conn_manager.execute_query(query)

        for list_row in lists or []:
            if hasattr(list_row, 'keys'):
                list_dict = dict(list_row)
            else:
                # Handle tuple/list format
                list_dict = {
                    'id': list_row[0],
                    'name': list_row[1],
                    'description': list_row[2],
                    'created_at': list_row[3],
                    'updated_at': list_row[4],
                    'item_count': list_row[5]
                }

            lists_data.append(list_dict)

        return lists_data, len(lists_data)

    def _collect_list_items_data(self) -> Tuple[List[Dict], int]:
        """Collect list items (membership) data"""
        items_data = []

        query = """
            SELECT li.list_id, lm.kodi_id, lm.title, lm.year, lm.file_path,
                   lm.imdb_id, lm.tmdb_id
            FROM list_item li
            INNER JOIN library_movie lm ON li.library_movie_id = lm.id
            WHERE lm.is_removed = 0
            ORDER BY li.list_id, lm.title
        """

        items = self.conn_manager.execute_query(query)

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
                    'tmdb_id': item_row[6]
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

    def _collect_favorites_data(self) -> Tuple[List[Dict], int]:
        """Collect favorites mirror data (mapped items only)"""
        favorites_data = []

        query = """
            SELECT kf.name, lm.kodi_id, lm.title, lm.year, lm.file_path,
                   kf.normalized_path, lm.imdb_id, lm.tmdb_id
            FROM kodi_favorite kf
            INNER JOIN library_movie lm ON kf.library_movie_id = lm.id
            WHERE lm.is_removed = 0
            ORDER BY kf.name
        """

        favorites = self.conn_manager.execute_query(query)

        for fav_row in favorites or []:
            if hasattr(fav_row, 'keys'):
                fav_dict = dict(fav_row)
            else:
                # Handle tuple/list format
                fav_dict = {
                    'name': fav_row[0],
                    'kodi_id': fav_row[1],
                    'title': fav_row[2],
                    'year': fav_row[3],
                    'file_path': fav_row[4],
                    'normalized_path': fav_row[5],
                    'imdb_id': fav_row[6],
                    'tmdb_id': fav_row[7]
                }

            favorites_data.append(fav_dict)

        return favorites_data, len(favorites_data)

    def _collect_library_snapshot_data(self) -> Tuple[List[Dict], int]:
        """Collect library snapshot data"""
        library_data = []

        query = """
            SELECT kodi_id, title, year, file_path, imdb_id, tmdb_id, created_at
            FROM library_movie
            WHERE is_removed = 0 AND kodi_id IS NOT NULL
            ORDER BY title
        """

        movies = self.conn_manager.execute_query(query)

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
                    'added_at': movie_row[6]
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

    def _write_json_export(self, envelope: ExportEnvelope, file_path: str) -> bool:
        """Write JSON export file"""
        try:
            content = envelope.to_json()
            return self.storage_manager.write_file_atomic(file_path, content)

        except Exception as e:
            self.logger.error(f"Error writing JSON export: {e}")
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
            self.logger.error(f"Error writing CSV export: {e}")
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
            self.logger.error(f"Error creating export preview: {e}")
            return {"export_types": export_types, "totals": {}, "estimated_size_kb": 0}


# Global export engine instance
_export_engine_instance = None


def get_export_engine():
    """Get global export engine instance"""
    global _export_engine_instance
    if _export_engine_instance is None:
        _export_engine_instance = ExportEngine()
    return _export_engine_instance