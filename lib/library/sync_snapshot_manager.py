#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Sync Snapshot Manager
Manages memory-efficient delta sync using database snapshots instead of in-memory operations
"""

from typing import Dict, Set, Any, Optional
from lib.data.connection_manager import get_connection_manager
from lib.kodi.json_rpc_client import KodiJsonRpcClient
from lib.utils.device_memory import get_device_memory_profiler
from lib.utils.kodi_log import get_kodi_logger


class SyncSnapshotManager:
    """Manages sync snapshot table for memory-efficient delta detection"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.library.sync_snapshot_manager')
        self.conn_manager = get_connection_manager()
        self.kodi_client = KodiJsonRpcClient()
        self.memory_profiler = get_device_memory_profiler()
        
    def create_snapshot(self, media_type: str = 'movie') -> Dict[str, Any]:
        """
        Create current library snapshot in database using memory-efficient pagination
        
        Args:
            media_type: Type of media to snapshot ('movie' or 'episode')
            
        Returns:
            Dict with success status and statistics
        """
        try:
            # Clear any existing snapshot data first
            self.cleanup_snapshot()
            
            # Get device-appropriate batch size
            batch_size = self._get_device_appropriate_batch_size()
            
            self.logger.info(f"Creating {media_type} snapshot with batch size {batch_size}")
            
            total_items = 0
            total_batches = 0
            
            if media_type == 'movie':
                total_items = self._create_movie_snapshot(batch_size)
            elif media_type == 'episode':
                total_items = self._create_episode_snapshot(batch_size)
            else:
                raise ValueError(f"Unsupported media type: {media_type}")
                
            self.logger.info(f"Snapshot created successfully: {total_items} {media_type} items")
            
            return {
                "success": True,
                "total_items": total_items,
                "batch_size": batch_size
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create {media_type} snapshot: {e}")
            # Cleanup on failure
            self.cleanup_snapshot()
            return {"success": False, "error": str(e)}
    
    def _create_movie_snapshot(self, batch_size: int) -> int:
        """Create snapshot for movies using pagination"""
        total_items = 0
        offset = 0
        
        with self.conn_manager.batched_transaction(batch_size) as batch_conn:
            while True:
                # Get movies in batches - memory efficient
                response = self.kodi_client.get_movies_quick_check_paginated(offset, batch_size)
                movies = response.get("movies", [])
                
                if not movies:
                    break
                
                # Batch insert into snapshot table
                for movie in movies:
                    batch_conn.execute("""
                        INSERT INTO sync_snapshot (kodi_id, media_type, title, file_path, dateadded)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        movie.get("movieid"),
                        "movie", 
                        movie.get("title", ""),
                        movie.get("file", ""),
                        movie.get("dateadded", "")
                    ))
                
                total_items += len(movies)
                offset += len(movies)
                
                # Log progress for large libraries
                if total_items % (batch_size * 10) == 0:
                    self.logger.debug(f"Snapshot progress: {total_items} movies processed")
                
                # If we got less than batch_size, we're done
                if len(movies) < batch_size:
                    break
                    
        return total_items
    
    def _create_episode_snapshot(self, batch_size: int) -> int:
        """Create snapshot for TV episodes using pagination"""
        total_items = 0
        offset = 0
        
        with self.conn_manager.batched_transaction(batch_size) as batch_conn:
            while True:
                # Get episodes in batches - memory efficient  
                response = self.kodi_client.get_episodes_quick_check_paginated(offset, batch_size)
                episodes = response.get("episodes", [])
                
                if not episodes:
                    break
                
                # Batch insert into snapshot table
                for episode in episodes:
                    batch_conn.execute("""
                        INSERT INTO sync_snapshot (kodi_id, media_type, title, file_path, dateadded)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        episode.get("episodeid"),
                        "episode",
                        episode.get("title", ""),
                        episode.get("file", ""),
                        episode.get("dateadded", "")
                    ))
                
                total_items += len(episodes)
                offset += len(episodes)
                
                # Log progress for large libraries
                if total_items % (batch_size * 10) == 0:
                    self.logger.debug(f"Snapshot progress: {total_items} episodes processed")
                
                # If we got less than batch_size, we're done
                if len(episodes) < batch_size:
                    break
                    
        return total_items
    
    def detect_changes(self, media_type: str = 'movie') -> Dict[str, Any]:
        """
        Use SQL to detect new/removed/existing items by comparing snapshot with media_items
        
        Args:
            media_type: Type of media to check ('movie' or 'episode')
            
        Returns:
            Dict with sets of kodi_ids for 'new', 'removed', and 'existing' items
        """
        try:
            self.logger.debug(f"Detecting {media_type} changes using SQL comparison")
            
            # Find new items (in snapshot but not in media_items)
            new_query = """
                SELECT s.kodi_id 
                FROM sync_snapshot s 
                LEFT JOIN media_items m ON m.kodi_id = s.kodi_id 
                    AND m.media_type = ? 
                    AND m.is_removed = 0
                WHERE m.kodi_id IS NULL AND s.media_type = ?
            """
            new_results = self.conn_manager.execute_query(new_query, [media_type, media_type])
            new_ids = {row["kodi_id"] for row in new_results}
            
            # Find removed items (in media_items but not in snapshot)
            removed_query = """
                SELECT m.kodi_id 
                FROM media_items m 
                LEFT JOIN sync_snapshot s ON s.kodi_id = m.kodi_id AND s.media_type = ?
                WHERE s.kodi_id IS NULL 
                    AND m.media_type = ? 
                    AND m.is_removed = 0
            """
            removed_results = self.conn_manager.execute_query(removed_query, [media_type, media_type])
            removed_ids = {row["kodi_id"] for row in removed_results}
            
            # Update timestamps for existing items directly via SQL (no Python sets needed)
            update_existing_query = """
                UPDATE media_items 
                SET updated_at = datetime('now') 
                WHERE media_type = ? 
                    AND is_removed = 0 
                    AND EXISTS (
                        SELECT 1 FROM sync_snapshot s 
                        WHERE s.kodi_id = media_items.kodi_id 
                            AND s.media_type = ?
                    )
            """
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute(update_existing_query, [media_type, media_type])
                existing_count = cursor.rowcount
            
            self.logger.info(f"Change detection results - New: {len(new_ids)}, Removed: {len(removed_ids)}, Existing: {existing_count}")
            
            return {
                "new": new_ids,
                "removed": removed_ids, 
                "existing_count": existing_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to detect {media_type} changes: {e}")
            return {"new": set(), "removed": set(), "existing_count": 0}
    
    def cleanup_snapshot(self):
        """Remove all snapshot data to prevent table bloat"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM sync_snapshot")
            self.logger.debug("Snapshot table cleaned up successfully")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup snapshot: {e}")
    
    def cleanup_stale_snapshots(self, max_age_hours: int = 1):
        """Remove snapshots older than specified age to prevent orphaned data"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    DELETE FROM sync_snapshot 
                    WHERE created_at < datetime('now', '-{} hours')
                """.format(max_age_hours))
            self.logger.debug(f"Stale snapshots older than {max_age_hours} hours cleaned up")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup stale snapshots: {e}")
    
    def get_snapshot_statistics(self) -> Dict[str, Any]:
        """Get statistics about current snapshot"""
        try:
            # Count by media type
            stats_query = """
                SELECT media_type, COUNT(*) as count 
                FROM sync_snapshot 
                GROUP BY media_type
            """
            results = self.conn_manager.execute_query(stats_query)
            
            stats = {"total": 0}
            for row in results:
                media_type = row["media_type"] 
                count = row["count"]
                stats[media_type] = count
                stats["total"] += count
                
            # Get creation time of snapshot
            time_query = "SELECT MIN(created_at) as created_at FROM sync_snapshot"
            time_result = self.conn_manager.execute_single(time_query)
            if time_result:
                stats["created_at"] = time_result["created_at"]
                
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get snapshot statistics: {e}")
            return {"total": 0}
    
    def _get_device_appropriate_batch_size(self) -> int:
        """Get batch size based on device memory capabilities"""
        try:
            memory_tier = self.memory_profiler.detect_memory_tier()
            batch_sizes = {
                'very_low': 200,   # ~100KB per batch
                'low': 500,        # ~250KB per batch  
                'medium': 1000,    # ~500KB per batch
                'high': 2000       # ~1MB per batch
            }
            batch_size = batch_sizes.get(memory_tier, 500)
            self.logger.debug(f"Using batch size {batch_size} for memory tier: {memory_tier}")
            return batch_size
        except Exception as e:
            self.logger.warning(f"Failed to detect memory tier, using default batch size: {e}")
            return 500