#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Directory Cache Manager
Lightweight caching for plugin directory views without database dependencies
"""

import time
import json
import threading
import os
from typing import Dict, Any, Optional, List
from lib.utils.kodi_log import get_kodi_logger


class DirectoryCacheManager:
    """
    Lightweight cache for plugin directory data that can be checked
    without database initialization or connection overhead.
    
    Optimized for low-power devices with adaptive TTL and memory management.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DirectoryCacheManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = get_kodi_logger('lib.ui.directory_cache')
        self._memory_cache = {}  # {cache_key: cache_entry}
        self._cache_lock = threading.Lock()
        self._max_entries = 20  # Limit for low-power devices
        self._default_ttl_minutes = 5  # Conservative default
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'stores': 0
        }
        
        # Cross-invocation persistence for low-power devices
        self._cache_file = None
        self._cache_schema_version = 1
        self._initialized = True
        
        # Initialize persistent cache file path
        self._init_cache_file_path()
        
        # Load existing cache on startup
        self._load_cache_from_disk()
        
        self.logger.debug("DirectoryCacheManager initialized (max_entries: %d, default_ttl: %d min, persistent: %s)", 
                         self._max_entries, self._default_ttl_minutes, bool(self._cache_file))
    
    def _generate_cache_key(self, action: str, params: Dict[str, Any], refresh_token: int) -> str:
        """Generate cache key from action, parameters, and refresh token"""
        # Normalize parameters for consistent caching
        folder_id = params.get('folder_id', 'root')
        list_id = params.get('list_id', '')
        
        if action == 'show_lists_menu':
            return f"dir:lists:root:rt{refresh_token}"
        elif action == 'show_folder':
            return f"dir:folder:{folder_id}:rt{refresh_token}"
        else:
            return f"dir:{action}:{folder_id}:{list_id}:rt{refresh_token}"
    
    def _create_cache_entry(self, data: Any, ttl_minutes: int) -> Dict[str, Any]:
        """Create cache entry with metadata"""
        return {
            'data': data,
            'timestamp': time.time(),
            'ttl_seconds': ttl_minutes * 60,
            'access_count': 0,
            'last_accessed': time.time()
        }
    
    def _is_cache_valid(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid (not expired)"""
        current_time = time.time()
        age_seconds = current_time - entry['timestamp']
        return age_seconds < entry['ttl_seconds']
    
    def _evict_oldest_entries(self):
        """Evict oldest entries when cache is full"""
        if len(self._memory_cache) <= self._max_entries:
            return
            
        # Sort by last accessed time and remove oldest
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: x[1]['last_accessed']
        )
        
        # Remove oldest entries to make room
        entries_to_remove = len(self._memory_cache) - self._max_entries + 1
        for i in range(entries_to_remove):
            key_to_remove = sorted_entries[i][0]
            del self._memory_cache[key_to_remove]
            self._stats['evictions'] += 1
            
        self.logger.debug("Evicted %d old cache entries", entries_to_remove)
    
    def get_cached_directory(self, action: str, params: Dict[str, Any], refresh_token: int) -> Optional[Any]:
        """
        Get cached directory data if available and valid.
        Returns None if cache miss or invalid.
        
        This method has NO database dependencies and is very fast.
        """
        try:
            cache_key = self._generate_cache_key(action, params, refresh_token)
            
            with self._cache_lock:
                entry = self._memory_cache.get(cache_key)
                
                if not entry:
                    self._stats['misses'] += 1
                    self.logger.debug("Cache MISS for key: %s", cache_key)
                    return None
                
                if not self._is_cache_valid(entry):
                    # Entry expired, remove it
                    del self._memory_cache[cache_key]
                    self._stats['misses'] += 1
                    self.logger.debug("Cache EXPIRED for key: %s", cache_key)
                    return None
                
                # Cache hit - update access tracking
                entry['access_count'] += 1
                entry['last_accessed'] = time.time()
                self._stats['hits'] += 1
                
                self.logger.debug("Cache HIT for key: %s (age: %.1fs)", 
                                cache_key, time.time() - entry['timestamp'])
                return entry['data']
                
        except Exception as e:
            self.logger.error("Error getting cached directory: %s", e)
            return None
    
    def cache_directory(self, action: str, params: Dict[str, Any], refresh_token: int, 
                       data: Any, ttl_minutes: Optional[int] = None) -> bool:
        """
        Cache directory data with specified TTL.
        
        Args:
            action: The action being cached (show_lists_menu, show_folder)
            params: Parameters dict (folder_id, etc.)
            refresh_token: Current refresh token for invalidation
            data: Directory data to cache (menu_items list)
            ttl_minutes: Cache TTL in minutes (None = use default)
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(action, params, refresh_token)
            ttl = ttl_minutes or self._default_ttl_minutes
            
            with self._cache_lock:
                # Evict old entries if cache is full
                if len(self._memory_cache) >= self._max_entries:
                    self._evict_oldest_entries()
                
                # Store the cache entry
                entry = self._create_cache_entry(data, ttl)
                self._memory_cache[cache_key] = entry
                self._stats['stores'] += 1
                
                self.logger.debug("Cached directory for key: %s (ttl: %d min, entries: %d)", 
                                cache_key, ttl, len(self._memory_cache))
                
                # Save to disk for cross-invocation persistence
                self._save_cache_to_disk()
                return True
                
        except Exception as e:
            self.logger.error("Error caching directory: %s", e)
            return False
    
    def invalidate_cache(self, reason: str = "manual"):
        """
        Clear all cached directory data.
        Called when structural changes occur that affect navigation.
        """
        try:
            with self._cache_lock:
                entries_cleared = len(self._memory_cache)
                self._memory_cache.clear()
                
            # Clear persistent cache file as well
            self._clear_cache_file()
            
            self.logger.info("Cache invalidated - cleared %d entries (reason: %s)", 
                           entries_cleared, reason)
            
        except Exception as e:
            self.logger.error("Error invalidating cache: %s", e)
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match against cache keys
                    - "folder:{folder_id}" - specific folder
                    - "lists" - main lists view
                    - "all" - everything
        """
        try:
            with self._cache_lock:
                keys_to_remove = []
                
                for cache_key in self._memory_cache.keys():
                    if pattern == "all":
                        keys_to_remove.append(cache_key)
                    elif pattern == "lists" and "dir:lists:" in cache_key:
                        keys_to_remove.append(cache_key)
                    elif pattern.startswith("folder:") and f"dir:folder:{pattern[7:]}:" in cache_key:
                        keys_to_remove.append(cache_key)
                
                for key in keys_to_remove:
                    del self._memory_cache[key]
                
                # Save updated cache to disk if entries were removed
                if keys_to_remove:
                    self._save_cache_to_disk()
                
                self.logger.debug("Invalidated %d cache entries matching pattern: %s", 
                                len(keys_to_remove), pattern)
                
        except Exception as e:
            self.logger.error("Error invalidating cache pattern '%s': %s", pattern, e)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self._cache_lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'entries': len(self._memory_cache),
                'max_entries': self._max_entries,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate_percent': round(hit_rate, 1),
                'stores': self._stats['stores'],
                'evictions': self._stats['evictions'],
                'default_ttl_minutes': self._default_ttl_minutes
            }
    
    def adapt_ttl_for_device(self, avg_query_time_ms: float):
        """
        Adapt cache TTL based on device performance.
        Slower devices get longer cache times to reduce load.
        """
        if avg_query_time_ms > 500:  # Slow device
            self._default_ttl_minutes = 8
        elif avg_query_time_ms > 200:  # Medium device  
            self._default_ttl_minutes = 5
        else:  # Fast device
            self._default_ttl_minutes = 3
            
        self.logger.debug("Adapted TTL to %d minutes based on query time %.1fms", 
                         self._default_ttl_minutes, avg_query_time_ms)

    def _init_cache_file_path(self):
        """Initialize the path for persistent cache storage"""
        try:
            import xbmcvfs
            import xbmcaddon
            
            addon = xbmcaddon.Addon()
            profile_dir = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
            
            # Ensure profile directory exists
            if not xbmcvfs.exists(profile_dir):
                xbmcvfs.mkdirs(profile_dir)
            
            self._cache_file = os.path.join(profile_dir, 'directory_cache.json')
            self.logger.debug("Cache file path: %s", self._cache_file)
            
        except Exception as e:
            self.logger.warning("Failed to initialize cache file path: %s", e)
            self._cache_file = None

    def _load_cache_from_disk(self):
        """Load cached data from disk on startup"""
        if not self._cache_file or not os.path.exists(self._cache_file):
            return
            
        try:
            with open(self._cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Validate schema version
            if cache_data.get('schema_version') != self._cache_schema_version:
                self.logger.debug("Cache schema version mismatch, clearing cache")
                self._clear_cache_file()
                return
            
            # Load cache entries
            current_time = time.time()
            valid_entries = 0
            
            for cache_key, entry in cache_data.get('cache_entries', {}).items():
                # Skip expired entries
                if self._is_cache_valid(entry):
                    self._memory_cache[cache_key] = entry
                    valid_entries += 1
            
            self.logger.debug("Loaded %d valid cache entries from disk", valid_entries)
            
        except Exception as e:
            self.logger.warning("Failed to load cache from disk: %s", e)
            self._clear_cache_file()

    def _save_cache_to_disk(self):
        """Save current cache state to disk for cross-invocation persistence"""
        if not self._cache_file:
            return
            
        try:
            # Only save valid, non-expired entries to keep file size small
            current_time = time.time()
            valid_entries = {}
            
            for cache_key, entry in self._memory_cache.items():
                if self._is_cache_valid(entry):
                    valid_entries[cache_key] = entry
            
            cache_data = {
                'schema_version': self._cache_schema_version,
                'saved_at': current_time,
                'cache_entries': valid_entries
            }
            
            # Atomic write to prevent corruption
            temp_file = self._cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, separators=(',', ':'))  # Compact format
            
            # Atomic replace
            if os.path.exists(self._cache_file):
                os.remove(self._cache_file)
            os.rename(temp_file, self._cache_file)
            
            self.logger.debug("Saved %d cache entries to disk", len(valid_entries))
            
        except Exception as e:
            self.logger.warning("Failed to save cache to disk: %s", e)

    def _clear_cache_file(self):
        """Clear the persistent cache file"""
        try:
            if self._cache_file and os.path.exists(self._cache_file):
                os.remove(self._cache_file)
                self.logger.debug("Cleared cache file")
        except Exception as e:
            self.logger.warning("Failed to clear cache file: %s", e)


# Global cache manager instance
_cache_manager_instance = None


def get_directory_cache_manager() -> DirectoryCacheManager:
    """Get singleton directory cache manager instance"""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = DirectoryCacheManager()
    return _cache_manager_instance