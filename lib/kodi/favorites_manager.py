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

        self.logger.info(f"Starting batch import of {len(favorites)} favorites")

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
                    self.logger.info(f"Using existing 'Kodi Favorites' list with ID {kodi_list_id}")

                # Clear existing items from the Kodi Favorites list
                deleted_count = conn.execute("DELETE FROM list_items WHERE list_id = ?", [kodi_list_id]).rowcount
                self.logger.info(f"Cleared {deleted_count} existing items from Kodi Favorites list")

                # Log database stats before processing
                media_count = conn.execute("SELECT COUNT(*) as count FROM media_items WHERE is_removed = 0").fetchone()["count"]
                self.logger.info(f"Database contains {media_count} active media items for matching")

                # Process favorites and add mapped ones to the list
                for i, favorite in enumerate(favorites):
                    favorite_name = favorite.get('name', 'unknown')
                    self.logger.info(f"Processing favorite {i+1}/{len(favorites)}: '{favorite_name}'")
                    self.logger.info(f"  Raw target: {favorite['target_raw']}")
                    self.logger.info(f"  Classification: {favorite['target_classification']}")
                    self.logger.info(f"  Normalized key: {favorite['normalized_key']}")

                    try:
                        # Try to find library match
                        library_movie_id = self._find_library_match_enhanced(
                            favorite["target_raw"],
                            favorite["target_classification"],
                            favorite["normalized_key"]
                        )

                        if library_movie_id:
                            self.logger.info(f"  ✓ MATCHED to library item ID {library_movie_id}")

                            # Add to the unified list_items table
                            conn.execute("""
                                INSERT INTO list_items (list_id, media_item_id, position, created_at)
                                VALUES (?, ?, ?, datetime('now'))
                            """, [kodi_list_id, library_movie_id, items_mapped])

                            items_mapped += 1
                            items_added += 1
                        else:
                            self.logger.info(f"  ✗ NO MATCH found for '{favorite_name}'")

                    except Exception as e:
                        self.logger.warning(f"Error processing favorite '{favorite_name}': {e}")
                        continue

                # Note: lists table doesn't have updated_at column in current schema

            self.logger.info(f"Batch import complete: {items_mapped}/{len(favorites)} mapped, {items_added} added")

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
        self.logger.info(f"    Starting library match for classification '{classification}'")

        try:
            # Strategy 1: videodb dbid matching
            if classification == 'videodb':
                self.logger.info("    Using videodb matching strategy")
                match = re.search(r'videodb://movies/titles/(\d+)', target_raw.lower())
                if match:
                    kodi_dbid = int(match.group(1))
                    self.logger.info(f"    Extracted Kodi dbid: {kodi_dbid}")

                    # Find by Kodi dbid in media_items table
                    with self.conn_manager.transaction() as conn:
                        result = conn.execute("""
                            SELECT id, title FROM media_items
                            WHERE kodi_id = ? AND is_removed = 0
                        """, [kodi_dbid]).fetchone()

                        if result:
                            self.logger.info(f"    Found videodb match: ID {result['id']} - '{result['title']}'")
                            return result["id"]
                        else:
                            self.logger.info(f"    No videodb match found for Kodi dbid {kodi_dbid}")
                else:
                    self.logger.info(f"    Could not extract dbid from videodb URL: {target_raw}")

            # Strategy 2: Normalized path matching
            elif classification == 'mappable_file':
                self.logger.info("    Using file path matching strategy")
                self.logger.info(f"    Looking for normalized_path: '{normalized_key}'")

                # Try exact normalized path match
                result = self.conn_manager.execute_single("""
                    SELECT id, title, file_path, normalized_path FROM media_items
                    WHERE normalized_path = ? AND is_removed = 0
                """, [normalized_key])

                if result:
                    self.logger.info(f"    Found exact normalized path match: ID {result['id']} - '{result['title']}'")
                    self.logger.info(f"    Matched file_path: {result['file_path']}")
                    return result["id"]
                else:
                    self.logger.info("    No exact normalized path match found")

                    # Show some sample normalized paths for debugging
                    sample_paths = self.conn_manager.execute_query("""
                        SELECT normalized_path, file_path FROM media_items 
                        WHERE is_removed = 0 AND normalized_path IS NOT NULL AND normalized_path != ''
                        LIMIT 5
                    """)

                    if sample_paths:
                        self.logger.info("    Sample normalized paths in database:")
                        for sample in sample_paths:
                            self.logger.info(f"      normalized: '{sample['normalized_path']}'")
                            self.logger.info(f"      file_path:  '{sample['file_path']}'")
                    else:
                        self.logger.info("    No normalized paths found in database")

                    # Always try file_path matching as backup
                    self.logger.info("    Trying file_path matching")
                    result = self._try_file_path_matching(normalized_key)
                    if result:
                        self.logger.info(f"    Found file_path match: ID {result}")
                        return result

                # Try fuzzy path matching for variations
                self.logger.info("    Attempting fuzzy path matching")
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    self.logger.info(f"    Fuzzy match found: ID {result}")
                    return result
                else:
                    self.logger.info("    No fuzzy match found")
            else:
                self.logger.info(f"    Classification '{classification}' not supported for matching")

            self.logger.info("    No library match found")
            return None

        except Exception as e:
            self.logger.error(f"Error finding library match for '{target_raw}': {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _try_file_path_matching(self, normalized_key: str) -> Optional[int]:
        """Attempt to match using the raw file_path with multiple strategies"""
        self.logger.info(f"    Attempting file path matching for key: '{normalized_key}'")
        try:
            with self.conn_manager.transaction() as conn:
                # Strategy 1: Try exact file path match
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE file_path = ? AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info(f"    Found exact file_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 2: Try case-insensitive file_path match
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE LOWER(file_path) = LOWER(?) AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info(f"    Found case-insensitive file_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 3: Try normalized_path match (in case it exists but wasn't found earlier)
                result = conn.execute("""
                    SELECT id, title, file_path, normalized_path FROM media_items
                    WHERE LOWER(normalized_path) = LOWER(?) AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info(f"    Found case-insensitive normalized_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 4: Try to match by converting backslashes to forward slashes in file_path
                backslash_version = normalized_key.replace('/', '\\')
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE file_path = ? AND is_removed = 0
                """, [backslash_version]).fetchone()

                if result:
                    self.logger.info(f"    Found backslash file_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 5: Try fuzzy path matching for variations
                self.logger.info("    Attempting fuzzy file_path matching")
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    self.logger.info(f"    Fuzzy file_path match found: ID {result}")
                    return result

                self.logger.info("    No file_path matches found")
                return None

        except Exception as e:
            self.logger.error(f"Error in file path matching: {e}")
            return None

    def _fuzzy_path_match(self, normalized_key: str) -> Optional[int]:
        """Fuzzy path matching for path variations"""
        try:
            # Extract just the filename for fuzzy matching
            filename = normalized_key.split('/')[-1] if '/' in normalized_key else normalized_key
            filename = filename.split('\\')[-1] if '\\' in filename else filename  # Handle backslashes too
            self.logger.info(f"      Fuzzy matching with filename: '{filename}'")

            if not filename or len(filename) < 3:
                self.logger.info(f"      Filename too short for fuzzy matching: '{filename}'")
                return None

            # Look for files with same filename but different paths
            with self.conn_manager.transaction() as conn:
                backslash_filename = filename.replace('/', '\\')
                results = conn.execute("""
                    SELECT id, title, play as file_path FROM media_items
                    WHERE is_removed = 0
                    AND (play LIKE ? OR play LIKE ?)
                    LIMIT 10
                """, [f"%{filename}%", f"%{backslash_filename}%"]).fetchall()

                self.logger.info(f"      Found {len(results)} potential fuzzy matches")

                for i, result in enumerate(results):
                    self.logger.info(f"        Match {i+1}: ID {result['id']} - '{result['title']}' - {result['file_path']}")

                if results and len(results) == 1:
                    # Exactly one match - probably correct
                    result = results[0]
                    self.logger.info(f"      Single fuzzy match selected: ID {result['id']}")
                    return result["id"]
                elif len(results) > 1:
                    # Try to find exact filename match (case insensitive)
                    for result in results:
                        result_filename = result['file_path'].split('/')[-1].split('\\')[-1].lower()
                        if result_filename == filename.lower():
                            self.logger.info(f"      Exact filename match found: ID {result['id']} - '{result['title']}'")
                            return result["id"]

                    self.logger.info("      Multiple fuzzy matches found but no exact filename match - skipping for reliability")
                else:
                    self.logger.info("      No fuzzy matches found")

                return None

        except Exception as e:
            self.logger.error(f"Error in fuzzy path matching: {e}")
            return None

    def get_mapped_favorites(self, show_unmapped: bool = False) -> List[Dict]:
        """Get favorites from unified lists table with full metadata like normal lists"""
        try:
            with self.conn_manager.transaction() as conn:
                # Get full media item data with comprehensive metadata (same as normal lists)
                favorites = conn.execute("""
                    SELECT li.id, mi.title, mi.year, mi.imdbnumber as imdb_id, mi.tmdb_id,
                           mi.kodi_id, mi.media_type, mi.poster, mi.fanart, mi.plot,
                           mi.file_path, mi.normalized_path, mi.art,
                           li.media_item_id as library_movie_id,
                           mi.title as name,  -- Use the library title as the favorite name
                           li.position,
                           -- Add all the missing metadata fields that normal lists have
                           mi.director, mi.studio, mi.country, mi.genre,
                           mi.mpaa, mi.tagline, mi.runtime, mi.votes, mi.rating,
                           mi.originaltitle, mi.sorttitle, mi.premiered,
                           mi.playcount, mi.lastplayed, mi.dateadded,
                           -- Ensure we have the play field for playback
                           mi.file_path as play
                    FROM lists l
                    JOIN list_items li ON l.id = li.list_id
                    JOIN media_items mi ON li.media_item_id = mi.id
                    WHERE l.name = 'Kodi Favorites' AND mi.is_removed = 0
                    ORDER BY li.position, mi.title
                """).fetchall()

                # Convert SQLite rows to dicts with full normalization like regular lists
                result = []
                for fav in favorites or []:
                    fav_dict = dict(fav)
                    
                    # Ensure we have a name field for the UI
                    if not fav_dict.get('name'):
                        fav_dict['name'] = fav_dict.get('title', 'Unknown Favorite')
                    
                    # Add mapped status for UI
                    fav_dict['is_mapped'] = 1  # All items in this query are mapped
                    
                    # Set default resume info (resume columns don't exist in current schema)
                    fav_dict['resume'] = {
                        'position_seconds': 0,
                        'total_seconds': 0
                    }
                    
                    # Ensure kodi_id is available for library integration
                    if fav_dict.get('kodi_id'):
                        fav_dict['movieid'] = fav_dict['kodi_id']  # Alternative field name
                    
                    # Add standard fields that normal list views expect
                    if not fav_dict.get('media_type'):
                        fav_dict['media_type'] = 'movie'  # Default for favorites
                    
                    # Ensure consistent field naming with normal lists
                    if fav_dict.get('library_movie_id'):
                        fav_dict['id'] = fav_dict['library_movie_id']  # Some views expect 'id'
                    
                    result.append(fav_dict)

                self.logger.info(f"Retrieved {len(result)} mapped favorites from unified lists with full metadata")
                return result

        except Exception as e:
            self.logger.error(f"Error getting mapped favorites: {e}")
            return []

    def get_favorites_stats(self) -> Dict[str, int]:
        """Get statistics about favorites from unified lists table"""
        try:
            with self.conn_manager.transaction() as conn:
                stats = conn.execute("""
                    SELECT COUNT(*) as total
                    FROM lists l
                    JOIN list_items li ON l.id = li.list_id
                    WHERE l.name = 'Kodi Favorites'
                """).fetchone()

                total = stats["total"] if stats else 0

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
            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    SELECT file_modified, items_found, items_mapped
                    FROM favorites_scan_log
                    WHERE file_path = ? AND success = 1
                    ORDER BY created_at DESC
                    LIMIT 1
                """, [file_path]).fetchone()

                return dict(result) if result else None

        except Exception as e:
            self.logger.debug(f"No previous scan info found: {e}")
            return None

    def _get_last_scan_info_for_display(self) -> Optional[Dict]:
        """Get last scan info for display purposes (any file path)"""
        try:
            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    SELECT file_path, file_modified, items_found, items_mapped, created_at
                    FROM favorites_scan_log
                    WHERE success = 1
                    ORDER BY created_at DESC
                    LIMIT 1
                """).fetchone()

                return dict(result) if result else None

        except Exception as e:
            self.logger.debug(f"No previous scan info found for display: {e}")
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