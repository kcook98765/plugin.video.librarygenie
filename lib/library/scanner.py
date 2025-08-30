#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Library Scanner
Handles full scans and delta detection of Kodi's video library
"""

import time
from datetime import datetime
from typing import List, Dict, Set, Any, Optional

from ..data import QueryManager
from ..data.connection_manager import get_connection_manager
from ..kodi.json_rpc_client import get_kodi_client
from ..utils.logger import get_logger


class LibraryScanner:
    """Scans and indexes Kodi's video library"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.query_manager = QueryManager()
        self.kodi_client = get_kodi_client()
        self.conn_manager = get_connection_manager()
        self.batch_size = 200  # Batch size for database operations

    def perform_full_scan(self) -> Dict[str, Any]:
        """Perform a complete library scan"""
        self.logger.info("Starting full library scan")

        # Initialize query manager
        if not self.query_manager.initialize():
            self.logger.error("Failed to initialize database for full scan")
            return {"success": False, "error": "Database initialization failed"}

        scan_start = datetime.now().isoformat()
        scan_id = self._log_scan_start("full", scan_start)

        try:
            # Clear existing data (full refresh)
            self._clear_library_index()

            # Get total count for progress tracking
            total_movies = self.kodi_client.get_movie_count()
            self.logger.info(f"Full scan: {total_movies} movies to process")

            if total_movies == 0:
                self._log_scan_complete(scan_id, scan_start, 0, 0, 0, 0)
                return {"success": True, "items_found": 0, "items_added": 0}

            # Process movies in pages
            offset = 0
            total_added = 0

            while offset < total_movies:
                response = self.kodi_client.get_movies(offset, self.batch_size)
                movies = response.get("movies", [])

                if not movies:
                    break

                # Batch insert movies
                added_count = self._batch_insert_movies(movies)
                total_added += added_count

                offset += len(movies)
                self.logger.debug(f"Full scan progress: {offset}/{total_movies} movies processed")

            scan_end = datetime.now().isoformat()
            self._log_scan_complete(scan_id, scan_start, total_movies, total_added, 0, 0, scan_end)

            self.logger.info(f"Full scan complete: {total_added} movies indexed")

            return {
                "success": True,
                "items_found": total_movies,
                "items_added": total_added,
                "scan_time": scan_end
            }

        except Exception as e:
            self.logger.error(f"Full scan failed: {e}")
            self._log_scan_complete(scan_id, scan_start, 0, 0, 0, 0, error=str(e))
            return {"success": False, "error": str(e)}

    def perform_delta_scan(self) -> Dict[str, Any]:
        """Perform a delta scan to detect changes"""
        self.logger.debug("Starting delta library scan")

        if not self.query_manager.initialize():
            self.logger.error("Failed to initialize database for delta scan")
            return {"success": False, "error": "Database initialization failed"}

        scan_start = datetime.now().isoformat()
        scan_id = self._log_scan_start("delta", scan_start)

        try:
            # Get current Kodi library state (quick check)
            current_movies = self.kodi_client.get_movies_quick_check()
            current_ids = {movie["movieid"] for movie in current_movies}

            # Get our indexed movies
            indexed_movies = self._get_indexed_movies()
            indexed_ids = {movie["kodi_id"] for movie in indexed_movies}

            # Detect changes
            new_ids = current_ids - indexed_ids
            removed_ids = indexed_ids - current_ids

            items_added = 0
            items_updated = 0
            items_removed = 0

            # Process new movies
            if new_ids:
                self.logger.debug(f"Delta scan: {len(new_ids)} new movies detected")
                new_movies_data = self._fetch_movies_by_ids(new_ids)
                items_added = self._batch_insert_movies(new_movies_data)

            # Mark removed movies
            if removed_ids:
                self.logger.debug(f"Delta scan: {len(removed_ids)} removed movies detected")
                items_removed = self._mark_movies_removed(removed_ids)

            # Update last_seen for existing movies
            existing_ids = current_ids & indexed_ids
            if existing_ids:
                items_updated = self._update_last_seen(existing_ids)

            scan_end = datetime.now().isoformat()
            self._log_scan_complete(
                scan_id, scan_start, len(current_movies),
                items_added, items_updated, items_removed, scan_end
            )

            if items_added > 0 or items_removed > 0:
                self.logger.info(f"Delta scan complete: +{items_added} -{items_removed} movies")
            else:
                self.logger.debug("Delta scan complete: no changes detected")

            return {
                "success": True,
                "items_found": len(current_movies),
                "items_added": items_added,
                "items_updated": items_updated,
                "items_removed": items_removed,
                "scan_time": scan_end
            }

        except Exception as e:
            self.logger.error(f"Delta scan failed: {e}")
            self._log_scan_complete(scan_id, scan_start, 0, 0, 0, 0, error=str(e))
            return {"success": False, "error": str(e)}

    def get_library_stats(self) -> Dict[str, Any]:
        """Get library indexing statistics"""
        try:
            stats = {}

            # Movie counts
            total_result = self.conn_manager.execute_single(
                "SELECT COUNT(*) as total FROM media_items WHERE media_type = 'movie'"
            )
            stats["total_movies"] = total_result["total"] if total_result else 0

            # Removed movies don't exist in new schema - set to 0
            stats["removed_movies"] = 0

            # Last scan info
            last_scan = self.conn_manager.execute_single("""
                SELECT scan_type, end_time, total_items, items_added, items_removed
                FROM library_scan_log
                WHERE end_time IS NOT NULL
                ORDER BY id DESC LIMIT 1
            """)

            if last_scan:
                stats["last_scan_type"] = last_scan["scan_type"]
                stats["last_scan_time"] = last_scan["end_time"]
                stats["last_scan_found"] = last_scan["total_items"]
                stats["last_scan_added"] = last_scan["items_added"]
                stats["last_scan_removed"] = last_scan["items_removed"]
            else:
                stats["last_scan_type"] = None
                stats["last_scan_time"] = None

            return stats

        except Exception as e:
            self.logger.error(f"Failed to get library stats: {e}")
            return {"total_movies": 0, "removed_movies": 0}

    def get_indexed_movies(self, include_removed: bool = False, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get indexed movies from the database"""
        try:
            where_clause = "" if include_removed else "WHERE is_removed = 0"

            movies = self.conn_manager.execute_query(f"""
                SELECT kodi_id, title, year, imdb_id, tmdb_id, file_path,
                       date_added, last_seen, is_removed, created_at,
                       poster, fanart, thumb, plot, plotoutline, runtime,
                       rating, genre, mpaa, director, country, studio,
                       playcount, resume_time
                FROM library_movie
                {where_clause}
                ORDER BY title, year
                LIMIT ? OFFSET ?
            """, [limit, offset])

            return movies or []

        except Exception as e:
            self.logger.error(f"Failed to get indexed movies: {e}")
            return []

    def is_library_indexed(self) -> bool:
        """Check if the library has been indexed"""
        try:
            # Ensure database is initialized first
            if not self.query_manager.initialize():
                self.logger.warning("Database not initialized, library not indexed")
                return False

            result = self.conn_manager.execute_single(
                "SELECT COUNT(*) as count FROM media_items WHERE media_type = 'movie'"
            )
            return (result["count"] if result else 0) > 0
        except Exception as e:
            self.logger.debug(f"Error checking if library is indexed: {e}")
            return False

    def _clear_library_index(self):
        """Clear the existing library index"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM media_items WHERE media_type = 'movie'")
            self.logger.debug("Library index cleared for full scan")
        except Exception as e:
            self.logger.error(f"Failed to clear library index: {e}")
            raise

    def _batch_insert_movies(self, movies: List[Dict[str, Any]]) -> int:
        """Insert movies in batches"""
        if not movies:
            return 0

        try:
            inserted_count = 0

            with self.conn_manager.transaction() as conn:
                for movie in movies:
                    try:
                        # For Kodi library items, store core identification fields plus plot
                        # Rich metadata will be fetched via JSON-RPC when needed
                        plot_data = movie.get("plot", "")

                        # Debug log to verify plot data
                        if plot_data:
                            self.logger.debug(f"Storing plot for '{movie['title']}': {len(plot_data)} characters")

                        conn.execute("""
                            INSERT INTO media_items
                            (media_type, kodi_id, title, year, imdbnumber, tmdb_id, play, plot, source, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        """, [
                            'movie',
                            movie["kodi_id"],
                            movie["title"],
                            movie.get("year"),
                            movie.get("imdb_id"),
                            movie.get("tmdb_id"),
                            movie["file_path"],
                            plot_data,
                            'lib'  # Mark as Kodi library item
                        ])
                        inserted_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to insert movie '{movie.get('title', 'Unknown')}': {e}")

            self.logger.debug(f"Batch inserted {inserted_count}/{len(movies)} movies")
            return inserted_count

        except Exception as e:
            self.logger.error(f"Batch insert failed: {e}")
            return 0

    def _get_indexed_movies(self) -> List[Dict[str, Any]]:
        """Get all indexed movies (internal use)"""
        try:
            movies = self.conn_manager.execute_query("""
                SELECT kodi_id, title, year, play as file_path
                FROM media_items
                WHERE media_type = 'movie'
            """)
            return movies or []
        except Exception as e:
            self.logger.error(f"Failed to get indexed movies: {e}")
            return []

    def _fetch_movies_by_ids(self, kodi_ids: Set[int]) -> List[Dict[str, Any]]:
        """Fetch detailed movie data for specific Kodi IDs"""
        # This is a simplified implementation - in practice we'd need to make
        # individual requests or batch requests for specific IDs
        # For now, do a small scan to catch new movies
        response = self.kodi_client.get_movies(0, 50)  # Small batch to find new ones
        movies = response.get("movies", [])

        # Filter to just the IDs we want
        filtered_movies = [m for m in movies if m["kodi_id"] in kodi_ids]
        return filtered_movies

    def _mark_movies_removed(self, kodi_ids: Set[int]) -> int:
        """Mark movies as removed (soft delete)"""
        if not kodi_ids:
            return 0

        try:
            removed_count = 0

            with self.conn_manager.transaction() as conn:
                for kodi_id in kodi_ids:
                    result = conn.execute("""
                        UPDATE library_movie
                        SET is_removed = 1, last_seen = datetime('now')
                        WHERE kodi_id = ? AND is_removed = 0
                    """, [kodi_id])

                    if result.rowcount > 0:
                        removed_count += 1

            self.logger.debug(f"Marked {removed_count} movies as removed")
            return removed_count

        except Exception as e:
            self.logger.error(f"Failed to mark movies as removed: {e}")
            return 0

    def _update_last_seen(self, kodi_ids: Set[int]) -> int:
        """Update last_seen timestamp for existing movies"""
        if not kodi_ids:
            return 0

        try:
            updated_count = 0

            with self.conn_manager.transaction() as conn:
                for kodi_id in kodi_ids:
                    result = conn.execute("""
                        UPDATE library_movie
                        SET last_seen = datetime('now')
                        WHERE kodi_id = ? AND is_removed = 0
                    """, [kodi_id])

                    if result.rowcount > 0:
                        updated_count += 1

            self.logger.debug(f"Updated last_seen for {updated_count} movies")
            return updated_count

        except Exception as e:
            self.logger.error(f"Failed to update last_seen: {e}")
            return 0

    def _log_scan_start(self, scan_type: str, started_at: str) -> Optional[int]:
        """Log the start of a scan"""
        try:
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO library_scan_log (scan_type, start_time)
                    VALUES (?, ?)
                """, [scan_type, started_at])
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Failed to log scan start: {e}")
            return None

    def _log_scan_complete(self, scan_id: Optional[int], started_at: str,
                          items_found: int, items_added: int, items_updated: int, items_removed: int,
                          completed_at: Optional[str] = None, error: Optional[str] = None):
        """Log the completion of a scan"""
        if not scan_id:
            return

        try:
            completed_at = completed_at or datetime.now().isoformat()

            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    UPDATE library_scan_log
                    SET end_time = ?, total_items = ?, items_added = ?,
                        items_updated = ?, items_removed = ?, error = ?
                    WHERE id = ?
                """, [completed_at, items_found, items_added, items_updated, items_removed, error, scan_id])
        except Exception as e:
            self.logger.error(f"Failed to log scan completion: {e}")


# Global scanner instance
_scanner_instance = None


def get_library_scanner():
    """Get global library scanner instance"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = LibraryScanner()
    return _scanner_instance