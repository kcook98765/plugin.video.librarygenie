#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 4 Enhanced Favorites Manager
Robust favorites integration with reliable mapping, idempotent updates, and batch processing
"""

import re
from datetime import datetime
from typing import List, Dict, Set, Any, Optional

from ..data import get_connection_manager
from ..utils.logger import get_logger
from .favorites_parser import get_phase4_favorites_parser


class Phase4FavoritesManager:
    """Phase 4: Enhanced favorites manager with reliable mapping and batch processing"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.parser = get_phase4_favorites_parser()

    def scan_favorites(self, file_path: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Scan and import favorites with mtime checking and batch processing"""
        start_time = datetime.now()

        try:
            # Find favorites file if not provided
            if not file_path:
                file_path = self.parser.find_favorites_file()
                if not file_path:
                    self.logger.info("Favorites file not found - showing empty state")
                    return {
                        "success": True,
                        "scan_type": "empty_state",
                        "items_found": 0,
                        "items_mapped": 0,
                        "message": "No favorites file found"
                    }

            # Get file modification time
            file_modified = self.parser.get_file_modified_time(file_path)

            # Phase 4: Check if we need to scan (mtime-based)
            if not force_refresh:
                last_scan = self._get_last_scan_info(file_path)
                if last_scan and last_scan.get("file_modified") == file_modified:
                    self.logger.debug("Favorites file unchanged since last scan")
                    return {
                        "success": True,
                        "scan_type": "check",
                        "items_found": last_scan.get("items_found", 0),
                        "items_mapped": last_scan.get("items_mapped", 0),
                        "message": "No changes detected"
                    }

            # Parse favorites file with enhanced parser
            favorites = self.parser.parse_favorites_file(file_path)

            # Phase 4: Process in batches with reliable mapping
            result = self._import_favorites_batch(favorites)

            # Calculate duration
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Log scan result
            self._log_scan_result(
                scan_type="full",
                file_path=file_path,
                file_modified=file_modified,
                items_found=len(favorites),
                items_mapped=result["items_mapped"],
                items_added=result["items_added"],
                items_updated=result["items_updated"],
                duration_ms=duration_ms,
                success=True
            )

            self.logger.info(f"Favorites scan complete: {result['items_mapped']}/{len(favorites)} mapped, {result['items_added']} added, {result['items_updated']} updated")

            return {
                "success": True,
                "scan_type": "full",
                "items_found": len(favorites),
                "items_mapped": result["items_mapped"],
                "items_added": result["items_added"],
                "items_updated": result["items_updated"],
                "duration_ms": duration_ms,
                "message": f"Processed {len(favorites)} favorites"
            }

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Log error
            if file_path:
                self._log_scan_result(
                    scan_type="full",
                    file_path=file_path,
                    file_modified=file_modified,
                    items_found=0,
                    items_mapped=0,
                    items_added=0,
                    items_updated=0,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=str(e)
                )

            self.logger.error(f"Favorites scan failed: {e}")
            return {
                "success": False,
                "error": "scan_error",
                "message": str(e),
                "duration_ms": duration_ms
            }

    def _import_favorites_batch(self, favorites: List[Dict]) -> Dict[str, int]:
        """Import favorites into unified lists table as 'Kodi Favorites' list"""
        items_added = 0
        items_updated = 0
        items_mapped = 0

        try:
            with self.conn_manager.transaction() as conn:
                # Ensure 'Kodi Favorites' list exists in the unified lists table
                kodi_list = conn.execute("""
                    SELECT id FROM lists WHERE name = 'Kodi Favorites'
                """).fetchone()

                if not kodi_list:
                    # Create the Kodi Favorites list
                    cursor = conn.execute("""
                        INSERT INTO lists (name, created_at)
                        VALUES ('Kodi Favorites', datetime('now'))
                    """)
                    kodi_list_id = cursor.lastrowid
                    self.logger.info("Created 'Kodi Favorites' list in unified lists table")
                else:
                    kodi_list_id = kodi_list["id"]

                # Clear existing items from the Kodi Favorites list
                conn.execute("DELETE FROM list_items WHERE list_id = ?", [kodi_list_id])

                # Process favorites and add mapped ones to the list
                for favorite in favorites:
                    try:
                        # Try to find library match
                        library_movie_id = self._find_library_match_enhanced(
                            favorite["target_raw"],
                            favorite["target_classification"],
                            favorite["normalized_key"]
                        )

                        if library_movie_id:
                            # Add to the unified list_items table
                            conn.execute("""
                                INSERT INTO list_items (list_id, media_item_id, position, created_at)
                                VALUES (?, ?, ?, datetime('now'))
                            """, [kodi_list_id, library_movie_id, items_mapped])

                            items_mapped += 1
                            items_added += 1

                    except Exception as e:
                        self.logger.warning(f"Error processing favorite '{favorite.get('name', 'unknown')}': {e}")
                        continue

                # Update the list's updated_at timestamp
                conn.execute("""
                    UPDATE lists SET updated_at = datetime('now') WHERE id = ?
                """, [kodi_list_id])

            self.logger.info(f"Imported {items_mapped} Kodi favorites into unified list")

            return {
                "items_added": items_added,
                "items_updated": items_updated,
                "items_mapped": items_mapped
            }

        except Exception as e:
            self.logger.error(f"Error in batch import: {e}")
            return {
                "items_added": 0,
                "items_updated": 0,
                "items_mapped": 0
            }

    def _find_library_match_enhanced(self, target_raw: str, classification: str, normalized_key: str) -> Optional[int]:
        """Phase 4: Enhanced library matching with multiple strategies"""
        try:
            # Strategy 1: videodb dbid matching
            if classification == 'videodb':
                match = re.search(r'videodb://movies/titles/(\d+)', target_raw.lower())
                if match:
                    kodi_dbid = int(match.group(1))

                    # Find by Kodi dbid
                    result = self.conn_manager.execute_single("""
                        SELECT id FROM media_items
                        WHERE kodi_id = ? AND is_removed = 0
                    """, [kodi_dbid])

                    if result:
                        return result["id"] if hasattr(result, 'keys') else result.get("id")

            # Strategy 2: Normalized path matching
            if classification == 'mappable_file':
                # Try exact normalized path match
                result = self.conn_manager.execute_single("""
                    SELECT id FROM media_items
                    WHERE normalized_path = ? AND is_removed = 0
                """, [normalized_key])

                if result:
                    return result["id"] if hasattr(result, 'keys') else result.get("id")

                # Try fuzzy path matching for variations
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    return result

            # Strategy 3: External ID matching (fallback for Phase 4)
            # This would be implemented if we stored external IDs in favorites
            # For now, keep simple and reliable

            return None

        except Exception as e:
            self.logger.debug(f"Error finding library match for '{target_raw}': {e}")
            return None

    def _fuzzy_path_match(self, normalized_key: str) -> Optional[int]:
        """Fuzzy path matching for path variations"""
        try:
            # Extract just the filename for fuzzy matching
            filename = normalized_key.split('/')[-1] if '/' in normalized_key else normalized_key

            if not filename or len(filename) < 3:
                return None

            # Look for files with same filename but different paths
            results = self.conn_manager.execute_query("""
                SELECT id, file_path FROM media_items
                WHERE is_removed = 0
                AND file_path LIKE ?
                LIMIT 5
            """, [f"%{filename}%"])

            if results and len(results) == 1:
                # Exactly one match - probably correct
                result = results[0]
                return result["id"] if hasattr(result, 'keys') else result.get("id")

            # Multiple matches - too ambiguous, skip for reliability
            return None

        except Exception:
            return None

    def get_mapped_favorites(self, show_unmapped: bool = False) -> List[Dict]:
        """Get favorites from unified lists table"""
        try:
            query = """
                SELECT li.id, mi.title, mi.year, mi.imdbnumber as imdb_id, mi.tmdb_id,
                       mi.kodi_id, mi.media_type, mi.poster, mi.fanart, mi.plot,
                       mi.rating, mi.votes, mi.duration, mi.genre, mi.director,
                       mi.studio, mi.country, mi.art, li.media_item_id as library_movie_id
                FROM lists l
                JOIN list_items li ON l.id = li.list_id
                JOIN media_items mi ON li.media_item_id = mi.id
                WHERE l.name = 'Kodi Favorites'
                ORDER BY li.position, mi.title
            """

            favorites = self.conn_manager.execute_query(query)

            # Convert SQLite rows to dicts
            result = []
            for fav in favorites or []:
                if hasattr(fav, 'keys'):
                    result.append(dict(fav))
                else:
                    result.append(fav)

            return result

        except Exception as e:
            self.logger.error(f"Error getting mapped favorites: {e}")
            return []

    def get_favorites_stats(self) -> Dict[str, int]:
        """Get statistics about favorites from unified lists table"""
        try:
            stats = self.conn_manager.execute_single("""
                SELECT COUNT(*) as total
                FROM lists l
                JOIN list_items li ON l.id = li.list_id
                WHERE l.name = 'Kodi Favorites'
            """)

            total = stats.get("total", 0) if stats else 0

            return {
                "total": total,
                "present": total,
                "mapped": total,
                "unmapped": 0,
                "missing": 0
            }

        except Exception as e:
            self.logger.error(f"Error getting favorites stats: {e}")
            return {"total": 0, "present": 0, "mapped": 0, "unmapped": 0, "missing": 0}

    def add_favorites_to_list(self, list_id: int, favorite_ids: List[int]) -> Dict[str, Any]:
        """Add mapped favorites to a list with duplicate detection"""
        try:
            added_count = 0
            skipped_count = 0

            with self.conn_manager.transaction() as conn:
                for favorite_id in favorite_ids:
                    # Get favorite from unified lists (Kodi Favorites list)
                    favorite = conn.execute("""
                        SELECT li.media_item_id, mi.title
                        FROM lists l
                        JOIN list_items li ON l.id = li.list_id
                        JOIN media_items mi ON li.media_item_id = mi.id
                        WHERE l.name = 'Kodi Favorites' AND li.id = ?
                    """, [favorite_id]).fetchone()

                    if not favorite or not favorite["media_item_id"]:
                        skipped_count += 1
                        continue

                    # Check if already in target list
                    existing = conn.execute("""
                        SELECT id FROM list_items
                        WHERE list_id = ? AND media_item_id = ?
                    """, [list_id, favorite["media_item_id"]]).fetchone()

                    if existing:
                        skipped_count += 1
                        continue

                    # Add to list
                    conn.execute("""
                        INSERT INTO list_items (list_id, media_item_id, created_at)
                        VALUES (?, ?, datetime('now'))
                    """, [list_id, favorite["media_item_id"]])

                    added_count += 1

            message = f"Added {added_count} favorites to list"
            if skipped_count > 0:
                message += f", skipped {skipped_count} (duplicates or unmapped)"

            return {
                "success": True,
                "added_count": added_count,
                "skipped_count": skipped_count,
                "message": message
            }

        except Exception as e:
            self.logger.error(f"Error adding favorites to list: {e}")
            return {
                "success": False,
                "error": "operation_error",
                "message": str(e)
            }

    def _get_last_scan_info(self, file_path: str) -> Optional[Dict]:
        """Get last scan info for favorites file"""
        try:
            result = self.conn_manager.execute_single("""
                SELECT file_modified, items_found, items_mapped
                FROM favorites_scan_log
                WHERE file_path = ? AND success = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, [file_path])

            return dict(result) if result else None

        except Exception as e:
            self.logger.debug(f"No previous scan info found: {e}")
            return None

    def _log_scan_result(self, scan_type: str, file_path: str, file_modified: str = None,
                        items_found: int = 0, items_mapped: int = 0, items_added: int = 0,
                        items_updated: int = 0, duration_ms: int = 0, success: bool = True,
                        error_message: str = None):
        """Log scan result to database"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO favorites_scan_log
                    (scan_type, file_path, file_modified, items_found, items_mapped,
                     items_added, items_updated, scan_duration_ms, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    scan_type, file_path, file_modified, items_found, items_mapped,
                    items_added, items_updated, duration_ms, 1 if success else 0, error_message
                ])

        except Exception as e:
            self.logger.error(f"Error logging scan result: {e}")


# Global Phase 4 favorites manager instance
_phase4_favorites_manager_instance = None


def get_phase4_favorites_manager():
    """Get global Phase 4 favorites manager instance"""
    global _phase4_favorites_manager_instance
    if _phase4_favorites_manager_instance is None:
        _phase4_favorites_manager_instance = Phase4FavoritesManager()
    return _phase4_favorites_manager_instance