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
        """Import favorites with Phase 4 batch processing and reliable mapping"""
        items_added = 0
        items_updated = 0
        items_mapped = 0
        
        try:
            # Process in batches for large favorites files
            batch_size = 200
            current_normalized_keys = set()
            
            for i in range(0, len(favorites), batch_size):
                batch = favorites[i:i + batch_size]
                
                with self.conn_manager.transaction() as conn:
                    for favorite in batch:
                        try:
                            normalized_key = favorite["normalized_key"]
                            current_normalized_keys.add(normalized_key)
                            
                            # Check if favorite already exists
                            existing = conn.execute("""
                                SELECT id, library_movie_id, is_mapped, is_missing
                                FROM kodi_favorite
                                WHERE normalized_key = ?
                            """, [normalized_key]).fetchone()
                            
                            # Phase 4: Reliable mapping with multiple strategies
                            library_movie_id = self._find_library_match_enhanced(
                                favorite["target_raw"], 
                                favorite["target_classification"],
                                normalized_key
                            )
                            is_mapped = 1 if library_movie_id else 0
                            
                            if is_mapped:
                                items_mapped += 1
                            
                            # Phase 4: Idempotent upsert with first_seen/last_seen/present
                            if existing:
                                # Update existing favorite
                                conn.execute("""
                                    UPDATE kodi_favorite 
                                    SET name = ?, target_raw = ?, target_classification = ?,
                                        library_movie_id = ?, is_mapped = ?,
                                        thumb_ref = ?, present = 1,
                                        last_seen = datetime('now'), 
                                        updated_at = datetime('now'),
                                        is_missing = 0
                                    WHERE id = ?
                                """, [
                                    favorite["name"], favorite["target_raw"], favorite["target_classification"],
                                    library_movie_id, is_mapped, favorite.get("thumb_ref", ""),
                                    existing["id"]
                                ])
                                items_updated += 1
                                
                            else:
                                # Insert new favorite with first_seen
                                conn.execute("""
                                    INSERT INTO kodi_favorite 
                                    (name, normalized_path, original_path, favorite_type,
                                     target_raw, target_classification, normalized_key,
                                     library_movie_id, is_mapped, thumb_ref, present,
                                     first_seen, last_seen)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                                            datetime('now'), datetime('now'))
                                """, [
                                    favorite["name"], 
                                    favorite["normalized_key"],  # Use as normalized_path for compatibility
                                    favorite["target_raw"],      # Use as original_path for compatibility
                                    favorite["target_classification"],  # Use as favorite_type for compatibility
                                    favorite["target_raw"], 
                                    favorite["target_classification"],
                                    favorite["normalized_key"],
                                    library_movie_id, 
                                    is_mapped,
                                    favorite.get("thumb_ref", "")
                                ])
                                items_added += 1
                                
                        except Exception as e:
                            self.logger.warning(f"Error processing favorite '{favorite.get('name', 'unknown')}': {e}")
                            continue
            
            # Phase 4: Mark favorites as not present if they weren't seen in this scan
            with self.conn_manager.transaction() as conn:
                if current_normalized_keys:
                    # Build placeholders for IN clause
                    placeholders = ','.join(['?'] * len(current_normalized_keys))
                    
                    conn.execute(f"""
                        UPDATE kodi_favorite
                        SET present = 0, last_seen = datetime('now')
                        WHERE normalized_key NOT IN ({placeholders})
                        AND present = 1
                    """, list(current_normalized_keys))
                else:
                    # No favorites found - mark all as not present
                    conn.execute("""
                        UPDATE kodi_favorite
                        SET present = 0, last_seen = datetime('now')
                        WHERE present = 1
                    """)
            
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
                        SELECT id FROM library_movie 
                        WHERE kodi_id = ? AND is_removed = 0
                    """, [kodi_dbid])
                    
                    if result:
                        return result["id"] if hasattr(result, 'keys') else result.get("id")
            
            # Strategy 2: Normalized path matching
            if classification == 'mappable_file':
                # Try exact normalized path match
                result = self.conn_manager.execute_single("""
                    SELECT id FROM library_movie 
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
                SELECT id, file_path FROM library_movie 
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
        """Get favorites with Phase 4 present/mapped filtering"""
        try:
            base_query = """
                SELECT kf.id, kf.name, kf.normalized_path, kf.original_path,
                       kf.favorite_type, kf.target_raw, kf.target_classification,
                       kf.is_mapped, kf.is_missing, kf.present,
                       kf.first_seen, kf.last_seen, kf.thumb_ref,
                       lm.title as library_title, lm.year, lm.imdb_id, lm.tmdb_id,
                       kf.library_movie_id
                FROM kodi_favorite kf
                LEFT JOIN library_movie lm ON kf.library_movie_id = lm.id
                WHERE kf.present = 1
            """
            
            if not show_unmapped:
                base_query += " AND kf.is_mapped = 1"
            
            base_query += " ORDER BY kf.is_mapped DESC, kf.name"
            
            favorites = self.conn_manager.execute_query(base_query)
            
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
        """Get statistics about favorites with Phase 4 present flag"""
        try:
            stats = self.conn_manager.execute_single("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_mapped = 1 AND present = 1 THEN 1 ELSE 0 END) as mapped,
                    SUM(CASE WHEN is_missing = 1 THEN 1 ELSE 0 END) as missing,
                    SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END) as present
                FROM kodi_favorite
            """)
            
            if stats and hasattr(stats, 'keys'):
                stats = dict(stats)
            
            total_present = stats.get("present", 0) if stats else 0
            mapped = stats.get("mapped", 0) if stats else 0
            
            return {
                "total": stats.get("total", 0) if stats else 0,
                "present": total_present,
                "mapped": mapped,
                "unmapped": total_present - mapped,
                "missing": stats.get("missing", 0) if stats else 0
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
                    # Get favorite and verify it's mapped
                    favorite = conn.execute("""
                        SELECT kf.library_movie_id, kf.name, kf.is_mapped, kf.present
                        FROM kodi_favorite kf
                        WHERE kf.id = ? AND kf.is_mapped = 1 AND kf.present = 1
                    """, [favorite_id]).fetchone()
                    
                    if not favorite or not favorite["library_movie_id"]:
                        skipped_count += 1
                        continue
                    
                    # Check if already in list
                    existing = conn.execute("""
                        SELECT id FROM list_item
                        WHERE list_id = ? AND library_movie_id = ?
                    """, [list_id, favorite["library_movie_id"]]).fetchone()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Add to list
                    conn.execute("""
                        INSERT INTO list_item (list_id, library_movie_id, title, created_at)
                        VALUES (?, ?, ?, datetime('now'))
                    """, [list_id, favorite["library_movie_id"], favorite["name"]])
                    
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
        """Get information about last scan"""
        try:
            last_scan = self.conn_manager.execute_single("""
                SELECT file_modified, items_found, items_mapped
                FROM favorites_scan_log
                WHERE file_path = ? AND success = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, [file_path])
            
            if last_scan and hasattr(last_scan, 'keys'):
                return dict(last_scan)
            return last_scan
            
        except Exception as e:
            self.logger.error(f"Error getting last scan info: {e}")
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