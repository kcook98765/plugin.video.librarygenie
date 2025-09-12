#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 12 Remote Cache
Local caching for remote API results with TTL support
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from ..utils.kodi_log import get_kodi_logger
from ..data.connection_manager import get_connection_manager


class RemoteCache:
    """Local cache for remote API results"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.remote.cache')
        self.conn_manager = get_connection_manager()
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        """Ensure the remote cache table exists"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS remote_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        hit_count INTEGER DEFAULT 0,
                        last_accessed TEXT
                    )
                """)

                # Create index for cleanup
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_remote_cache_expires 
                    ON remote_cache(expires_at)
                """)

        except Exception as e:
            self.logger.error("Failed to create remote cache table: %s", e)

    def get(self, cache_key: str) -> Optional[Any]:
        """Get cached data by key, returns None if not found or expired"""
        try:
            now = datetime.now().isoformat()

            result = self.conn_manager.execute_single("""
                SELECT data, expires_at, hit_count
                FROM remote_cache 
                WHERE cache_key = ? AND expires_at > ?
            """, [cache_key, now])

            if result:
                # Update hit count and last accessed
                with self.conn_manager.transaction() as conn:
                    conn.execute("""
                        UPDATE remote_cache 
                        SET hit_count = hit_count + 1, last_accessed = ?
                        WHERE cache_key = ?
                    """, [now, cache_key])

                # Parse and return data
                try:
                    return json.loads(result['data'])
                except json.JSONDecodeError as e:
                    self.logger.warning("Failed to parse cached data for %s: %s", cache_key, e)
                    self.delete(cache_key)

            return None

        except Exception as e:
            self.logger.error("Error getting cached data for %s: %s", cache_key, e)
            return None

    def set(self, cache_key: str, data: Any, ttl_hours: int = 6) -> bool:
        """Set cached data with TTL"""
        try:
            now = datetime.now()
            expires_at = now + timedelta(hours=ttl_hours)

            # Serialize data
            try:
                serialized_data = json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                self.logger.warning("Failed to serialize data for cache key %s: %s", cache_key, e)
                return False

            # Store in cache
            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO remote_cache 
                    (cache_key, data, created_at, expires_at, hit_count, last_accessed)
                    VALUES (?, ?, ?, ?, 0, ?)
                """, [
                    cache_key,
                    serialized_data,
                    now.isoformat(),
                    expires_at.isoformat(),
                    now.isoformat()
                ])

            self.logger.debug("Cached data for key %s (TTL: %sh)", cache_key, ttl_hours)
            return True

        except Exception as e:
            self.logger.error("Error setting cached data for %s: %s", cache_key, e)
            return False

    def delete(self, cache_key: str) -> bool:
        """Delete specific cache entry"""
        try:
            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    DELETE FROM remote_cache WHERE cache_key = ?
                """, [cache_key])

                deleted = result.rowcount > 0
                if deleted:
                    self.logger.debug("Deleted cache entry: %s", cache_key)

                return deleted

        except Exception as e:
            self.logger.error("Error deleting cache entry %s: %s", cache_key, e)
            return False

    def clear_all(self) -> bool:
        """Clear all cached data"""
        try:
            with self.conn_manager.transaction() as conn:
                result = conn.execute("DELETE FROM remote_cache")

                cleared_count = result.rowcount
                self.logger.info("Cleared %s cache entries", cleared_count)
                return True

        except Exception as e:
            self.logger.error("Error clearing cache: %s", e)
            return False

    def clear_expired(self) -> int:
        """Clear expired cache entries, returns number of entries cleared"""
        try:
            now = datetime.now().isoformat()

            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    DELETE FROM remote_cache WHERE expires_at <= ?
                """, [now])

                cleared_count = result.rowcount
                if cleared_count > 0:
                    self.logger.debug("Cleared %s expired cache entries", cleared_count)

                return cleared_count

        except Exception as e:
            self.logger.error("Error clearing expired cache: %s", e)
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            now = datetime.now().isoformat()

            # Get total entries
            total_result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as total FROM remote_cache
            """)
            total_entries = total_result['total'] if total_result else 0

            # Get active (non-expired) entries
            active_result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as active FROM remote_cache WHERE expires_at > ?
            """, [now])
            active_entries = active_result['active'] if active_result else 0

            # Get expired entries
            expired_entries = total_entries - active_entries

            # Get total hit count
            hits_result = self.conn_manager.execute_single("""
                SELECT SUM(hit_count) as total_hits FROM remote_cache
            """)
            total_hits = hits_result['total_hits'] if hits_result and hits_result['total_hits'] else 0

            return {
                'total_entries': total_entries,
                'active_entries': active_entries,
                'expired_entries': expired_entries,
                'total_hits': total_hits,
                'cache_table_exists': True
            }

        except Exception as e:
            self.logger.error("Error getting cache stats: %s", e)
            return {
                'total_entries': 0,
                'active_entries': 0,
                'expired_entries': 0,
                'total_hits': 0,
                'cache_table_exists': False,
                'error': str(e)
            }

    def cleanup_old_entries(self, max_entries: int = 1000) -> int:
        """Clean up old entries when cache grows too large"""
        try:
            # First clear expired entries
            expired_cleared = self.clear_expired()

            # Check if we still have too many entries
            current_result = self.conn_manager.execute_single("""
                SELECT COUNT(*) as count FROM remote_cache
            """)
            current_count = current_result['count'] if current_result else 0

            if current_count <= max_entries:
                return expired_cleared

            # Remove oldest entries by last accessed time
            entries_to_remove = current_count - max_entries

            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    DELETE FROM remote_cache 
                    WHERE cache_key IN (
                        SELECT cache_key FROM remote_cache 
                        ORDER BY last_accessed ASC 
                        LIMIT ?
                    )
                """, [entries_to_remove])

                removed_count = result.rowcount
                total_cleared = expired_cleared + removed_count

                if total_cleared > 0:
                    self.logger.info("Cache cleanup: %s expired + %s old = %s entries removed", expired_cleared, removed_count, total_cleared)

                return total_cleared

        except Exception as e:
            self.logger.error("Error during cache cleanup: %s", e)
            return 0


def get_remote_cache():
    """Get global remote cache instance"""
    return RemoteCache()