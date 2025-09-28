#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - File-Based Folder Cache
Zero-database caching for folder view payloads with TTL and background refresh support
"""

import os
import json
import time
import threading
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from lib.utils.kodi_log import get_kodi_logger


class FolderCache:
    """
    File-based caching system for folder view payloads.
    Eliminates database overhead by using JSON files with filesystem timestamps for TTL.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, schema_version: int = 1):
        self.logger = get_kodi_logger('lib.ui.folder_cache')
        self.schema_version = schema_version
        self.fresh_ttl_hours = 12  # Fresh TTL: 12 hours
        self.hard_expiry_hours = 24 * 30  # Hard expiry: 30 days
        
        # Default cache directory in Kodi's profile directory
        if cache_dir is None:
            import xbmcvfs
            profile_dir = xbmcvfs.translatePath('special://profile/')
            cache_dir = os.path.join(profile_dir, 'addon_data', 'plugin.video.librarygenie', 'cache', 'folders')
        
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
        
        # Singleton lock for stampede protection
        self._locks = {}
        self._locks_mutex = threading.Lock()
        
        # Stats for monitoring
        self._stats = {
            'hits': 0,
            'misses': 0,
            'writes': 0,
            'deletes': 0,
            'errors': 0
        }
        self._stats_lock = threading.Lock()
        
        self.logger.debug("FolderCache initialized - dir: %s, schema: v%d", cache_dir, schema_version)
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
                self.logger.debug("Created cache directory: %s", self.cache_dir)
        except Exception as e:
            self.logger.error("Failed to create cache directory %s: %s", self.cache_dir, e)
    
    def _get_cache_file_path(self, folder_id: str) -> str:
        """Generate safe cache file path for folder ID using hash"""
        # Hash folder_id for filename safety (prevents path traversal)
        folder_hash = hashlib.sha1(folder_id.encode('utf-8')).hexdigest()[:16]
        filename = f"folder_{folder_hash}_anon_v{self.schema_version}.json"
        return os.path.join(self.cache_dir, filename)
    
    def _is_file_fresh(self, file_path: str) -> bool:
        """Check if cache file is within fresh TTL"""
        try:
            if not os.path.exists(file_path):
                return False
            
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            cutoff_time = datetime.now() - timedelta(hours=self.fresh_ttl_hours)
            
            is_fresh = file_time > cutoff_time
            self.logger.debug("File freshness check - %s: %s (modified: %s)", 
                            os.path.basename(file_path), is_fresh, file_time.isoformat())
            return is_fresh
            
        except Exception as e:
            self.logger.warning("Error checking file freshness for %s: %s", file_path, e)
            return False
    
    def _is_file_expired(self, file_path: str) -> bool:
        """Check if cache file is beyond hard expiry"""
        try:
            if not os.path.exists(file_path):
                return True
            
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            cutoff_time = datetime.now() - timedelta(hours=self.hard_expiry_hours)
            
            return file_time <= cutoff_time
            
        except Exception as e:
            self.logger.warning("Error checking file expiry for %s: %s", file_path, e)
            return True
    
    def _is_file_stale_but_usable(self, file_path: str) -> bool:
        """Check if file is stale (past fresh TTL) but still usable (before hard expiry)"""
        try:
            if not os.path.exists(file_path):
                return False
            
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            now = datetime.now()
            fresh_cutoff = now - timedelta(hours=self.fresh_ttl_hours)
            hard_cutoff = now - timedelta(hours=self.hard_expiry_hours)
            
            # Stale but usable: between fresh and hard expiry
            return file_time <= fresh_cutoff and file_time > hard_cutoff
            
        except Exception as e:
            self.logger.warning("Error checking file staleness for %s: %s", file_path, e)
            return False
    
    @contextmanager
    def _singleton_lock(self, folder_id: str):
        """Singleton lock for preventing duplicate folder builds"""
        with self._locks_mutex:
            if folder_id not in self._locks:
                self._locks[folder_id] = threading.Lock()
            lock = self._locks[folder_id]
        
        acquired = lock.acquire(blocking=True, timeout=10.0)  # 10 second timeout
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for folder {folder_id}")
        
        try:
            yield
        finally:
            lock.release()
            # Clean up lock if no longer needed
            with self._locks_mutex:
                if folder_id in self._locks and not self._locks[folder_id].locked():
                    del self._locks[folder_id]
    
    def get(self, folder_id: str, allow_stale: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get cached folder payload if exists and is fresh (or stale if allowed)
        
        Args:
            folder_id: Unique folder identifier
            allow_stale: If True, return stale cache (past fresh TTL but before hard expiry)
            
        Returns:
            Dict with folder payload or None if cache miss
        """
        try:
            file_path = self._get_cache_file_path(folder_id)
            
            # Check if file exists and is not hard expired
            if self._is_file_expired(file_path):
                with self._stats_lock:
                    self._stats['misses'] += 1
                self.logger.debug("Cache MISS for folder %s - file expired", folder_id)
                return None
            
            # Check freshness - if not fresh and stale not allowed, miss
            if not self._is_file_fresh(file_path) and not allow_stale:
                with self._stats_lock:
                    self._stats['misses'] += 1
                self.logger.debug("Cache MISS for folder %s - file not fresh", folder_id)
                return None
            
            # Read and parse cached data
            with open(file_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            
            # Validate payload structure
            if not isinstance(payload, dict) or '_schema' not in payload:
                self.logger.warning("Invalid cache payload for folder %s - missing schema", folder_id)
                self.delete(folder_id)
                return None
            
            # Check schema compatibility
            if payload.get('_schema') != self.schema_version:
                self.logger.debug("Schema mismatch for folder %s - expected v%d, got v%s", 
                                folder_id, self.schema_version, payload.get('_schema'))
                self.delete(folder_id)
                return None
            
            with self._stats_lock:
                self._stats['hits'] += 1
            
            freshness = "fresh" if self._is_file_fresh(file_path) else "stale"
            self.logger.debug("Cache HIT for folder %s - %d items (%s)", 
                            folder_id, len(payload.get('items', [])), freshness)
            return payload
            
        except Exception as e:
            with self._stats_lock:
                self._stats['errors'] += 1
            self.logger.error("Error reading cache for folder %s: %s", folder_id, e)
            return None
    
    def set(self, folder_id: str, payload: Dict[str, Any], build_time_ms: Optional[int] = None) -> bool:
        """
        Store folder payload in cache with stampede protection
        
        Args:
            folder_id: Unique folder identifier
            payload: Folder data to cache (will be augmented with metadata)
            build_time_ms: Time taken to build folder (for metrics)
            
        Returns:
            bool: True if successful
        """
        try:
            with self._singleton_lock(folder_id):
                # Augment payload with cache metadata
                cache_payload = {
                    **payload,
                    '_built_at': datetime.now().isoformat(),
                    '_folder_id': folder_id,
                    '_schema': self.schema_version
                }
                
                if build_time_ms is not None:
                    cache_payload['_build_time_ms'] = build_time_ms
                
                file_path = self._get_cache_file_path(folder_id)
                
                # Write atomically using temp file
                temp_path = file_path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(cache_payload, f, ensure_ascii=False, indent=None, separators=(',', ':'))
                
                # Atomic move
                os.replace(temp_path, file_path)
                
                with self._stats_lock:
                    self._stats['writes'] += 1
                
                item_count = len(payload.get('items', []))
                self.logger.debug("Cached folder %s - %d items, %d ms build time", 
                                folder_id, item_count, build_time_ms or 0)
                return True
            
        except Exception as e:
            with self._stats_lock:
                self._stats['errors'] += 1
            self.logger.error("Error caching folder %s: %s", folder_id, e)
            # Clean up temp file if it exists
            temp_path = self._get_cache_file_path(folder_id) + '.tmp'
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False
    
    def delete(self, folder_id: str) -> bool:
        """
        Delete cached folder entry
        
        Args:
            folder_id: Folder identifier to remove
            
        Returns:
            bool: True if file was deleted or didn't exist
        """
        try:
            file_path = self._get_cache_file_path(folder_id)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                with self._stats_lock:
                    self._stats['deletes'] += 1
                self.logger.debug("Deleted cache for folder %s", folder_id)
            
            return True
            
        except Exception as e:
            with self._stats_lock:
                self._stats['errors'] += 1
            self.logger.error("Error deleting cache for folder %s: %s", folder_id, e)
            return False
    
    def is_fresh(self, folder_id: str) -> bool:
        """Check if folder cache is fresh (within fresh TTL)"""
        file_path = self._get_cache_file_path(folder_id)
        return self._is_file_fresh(file_path)
    
    def is_stale_but_usable(self, folder_id: str) -> bool:
        """Check if folder cache is stale but still usable for immediate serving"""
        file_path = self._get_cache_file_path(folder_id)
        return self._is_file_stale_but_usable(file_path)
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired cache files
        
        Returns:
            int: Number of files cleaned up
        """
        cleaned_count = 0
        try:
            if not os.path.exists(self.cache_dir):
                return 0
            
            cutoff_time = datetime.now() - timedelta(hours=self.hard_expiry_hours)
            
            for filename in os.listdir(self.cache_dir):
                if not filename.startswith('folder_') or not filename.endswith('.json'):
                    continue
                
                file_path = os.path.join(self.cache_dir, filename)
                try:
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_time:
                        os.remove(file_path)
                        cleaned_count += 1
                        self.logger.debug("Cleaned expired cache file: %s", filename)
                        
                except Exception as e:
                    self.logger.warning("Error cleaning cache file %s: %s", filename, e)
            
            if cleaned_count > 0:
                self.logger.info("Cache cleanup completed - removed %d expired files", cleaned_count)
            
        except Exception as e:
            self.logger.error("Error during cache cleanup: %s", e)
        
        return cleaned_count
    
    def cleanup_old_schemas(self, keep_current_only: bool = True) -> int:
        """
        Clean up cache files from old schema versions
        
        Args:
            keep_current_only: If True, only keep current schema version
            
        Returns:
            int: Number of files cleaned up
        """
        cleaned_count = 0
        try:
            if not os.path.exists(self.cache_dir):
                return 0
            
            for filename in os.listdir(self.cache_dir):
                if not filename.startswith('folder_') or not filename.endswith('.json'):
                    continue
                
                # Extract schema version from filename
                try:
                    # Format: folder_{id}_anon_v{schema}.json
                    parts = filename.replace('.json', '').split('_v')
                    if len(parts) >= 2:
                        file_schema = int(parts[-1])
                        if keep_current_only and file_schema != self.schema_version:
                            file_path = os.path.join(self.cache_dir, filename)
                            os.remove(file_path)
                            cleaned_count += 1
                            self.logger.debug("Cleaned old schema cache file: %s (v%d)", filename, file_schema)
                
                except (ValueError, IndexError) as e:
                    self.logger.debug("Could not parse schema from filename %s: %s", filename, e)
            
            if cleaned_count > 0:
                self.logger.info("Schema cleanup completed - removed %d old schema files", cleaned_count)
            
        except Exception as e:
            self.logger.error("Error during schema cleanup: %s", e)
        
        return cleaned_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self._stats_lock:
            stats = self._stats.copy()
        
        total_requests = stats['hits'] + stats['misses']
        hit_rate = (stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Get cache directory info
        cache_info = {}
        try:
            if os.path.exists(self.cache_dir):
                cache_files = [f for f in os.listdir(self.cache_dir) 
                             if f.startswith('folder_') and f.endswith('.json')]
                cache_info = {
                    'cached_folders': len(cache_files),
                    'cache_dir_size_mb': sum(
                        os.path.getsize(os.path.join(self.cache_dir, f)) 
                        for f in cache_files
                    ) / (1024 * 1024)
                }
        except Exception as e:
            self.logger.warning("Error getting cache directory info: %s", e)
        
        return {
            'performance': {
                **stats,
                'hit_rate_percent': round(hit_rate, 2)
            },
            'cache_info': cache_info,
            'config': {
                'schema_version': self.schema_version,
                'fresh_ttl_hours': self.fresh_ttl_hours,
                'hard_expiry_hours': self.hard_expiry_hours,
                'cache_dir': self.cache_dir
            }
        }


# Global instance
_folder_cache_instance = None
_instance_lock = threading.Lock()


def get_folder_cache(schema_version: int = 1) -> FolderCache:
    """Get global folder cache instance"""
    global _folder_cache_instance
    
    with _instance_lock:
        if _folder_cache_instance is None or _folder_cache_instance.schema_version != schema_version:
            _folder_cache_instance = FolderCache(schema_version=schema_version)
    
    return _folder_cache_instance