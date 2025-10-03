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

# Cache schema version - single source of truth
# v7: Removed Tools & Options from cached items (added dynamically to respect visibility setting)
CACHE_SCHEMA_VERSION = 11  # v11: Fixed duplicate Tools & Options by removing from Kodi Favorites cached context menu


class FolderCache:
    """
    File-based caching system for folder view payloads.
    Eliminates database overhead by using JSON files with filesystem timestamps for TTL.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, schema_version: int = CACHE_SCHEMA_VERSION):
        self.logger = get_kodi_logger('lib.ui.folder_cache')
        self.schema_version = schema_version
        
        # Load cache configuration from settings
        self._load_configuration()
        
        # Default cache directory in Kodi's profile directory
        if cache_dir is None:
            import xbmcvfs
            profile_dir = xbmcvfs.translatePath('special://profile/')
            cache_dir = os.path.join(profile_dir, 'addon_data', 'plugin.video.librarygenie', 'cache', 'folders')
        
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
        
        # Singleton lock for stampede protection (use RLock for re-entrant access)
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
        
        self.logger.debug("FolderCache initialized - dir: %s, schema: v%d, cache_enabled: %s", 
                          cache_dir, schema_version, self.cache_enabled)
    
    def _get_tools_toggle_entry(self, base_url: str):
        """Get the Tools & Options visibility toggle context menu entry for cache building"""
        from lib.config.config_manager import get_config
        config = get_config()
        is_visible = config.get_bool('show_tools_menu_item', True)
        
        label = "Hide Tools & Options Menu Item" if is_visible else "Show Tools & Options Menu Item"
        return (label, f"RunPlugin({base_url}?action=toggle_tools_menu_item)")
    
    def _load_configuration(self):
        """Load cache configuration from settings"""
        try:
            from lib.config.settings import SettingsManager
            settings = SettingsManager()
            
            # Load cache settings
            self.cache_enabled = settings.get_folder_cache_enabled()
            self.fresh_ttl_hours = settings.get_folder_cache_fresh_ttl()
            self.hard_expiry_hours = settings.get_folder_cache_hard_expiry() * 24  # Convert days to hours
            self.prewarm_enabled = settings.get_folder_cache_prewarm_enabled()
            self.prewarm_max_folders = settings.get_folder_cache_prewarm_max_folders()
            self.debug_logging = settings.get_folder_cache_debug_logging()
            
            if self.debug_logging:
                self.logger.debug("Cache config - enabled: %s, fresh_ttl: %dh, hard_expiry: %dh, "
                                 "prewarm: %s (%d folders)", self.cache_enabled, self.fresh_ttl_hours,
                                 self.hard_expiry_hours, self.prewarm_enabled, self.prewarm_max_folders)
        except Exception as e:
            self.logger.warning("Failed to load cache configuration, using defaults: %s", e)
            # Fallback to hardcoded defaults
            self.cache_enabled = True
            self.fresh_ttl_hours = 12
            self.hard_expiry_hours = 24 * 30  # 30 days
            self.prewarm_enabled = True
            self.prewarm_max_folders = 10
            self.debug_logging = False

    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
                self.logger.debug("Created cache directory: %s", self.cache_dir)
        except Exception as e:
            self.logger.error("Failed to create cache directory %s: %s", self.cache_dir, e)
    
    def _get_cache_file_path(self, folder_id: Optional[str]) -> str:
        """Generate cache file path for folder ID"""
        # Handle None folder_id (root level)
        if folder_id is None:
            safe_folder_id = "root"
            folder_hash = hashlib.sha1("root".encode('utf-8')).hexdigest()[:8]
        else:
            # Sanitize folder_id for filename use
            safe_folder_id = "".join(c for c in str(folder_id) if c.isalnum() or c in '-_').strip()
            # Add hash of original folder_id to prevent collisions
            folder_hash = hashlib.sha1(str(folder_id).encode('utf-8')).hexdigest()[:8]
        filename = f"folder_{safe_folder_id}_{folder_hash}_anon_v{self.schema_version}.json"
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
    def _singleton_lock(self, folder_id: Optional[str]):
        """Singleton lock for preventing duplicate folder builds"""
        # Handle None folder_id (root level)
        lock_key = str(folder_id) if folder_id is not None else "root"
        
        with self._locks_mutex:
            if lock_key not in self._locks:
                self._locks[lock_key] = threading.RLock()  # Use RLock for re-entrant access
            lock = self._locks[lock_key]
        
        acquired = lock.acquire(blocking=True, timeout=60.0)  # 60 second timeout (was 10s)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for folder {folder_id}")
        
        try:
            yield
        finally:
            lock.release()
            # Note: RLock doesn't have locked() method, skip cleanup to avoid AttributeError
    
    @contextmanager
    def with_build_lock(self, folder_id: Optional[str]):
        """Public context manager for build operations with stampede protection"""
        with self._singleton_lock(folder_id):
            yield
    
    def get(self, folder_id: Optional[str], allow_stale: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get cached folder payload if exists and is fresh (or stale if allowed)
        
        Args:
            folder_id: Unique folder identifier
            allow_stale: If True, return stale cache (past fresh TTL but before hard expiry)
            
        Returns:
            Dict with folder payload or None if cache miss
        """
        # Check if caching is enabled
        if not self.cache_enabled:
            if self.debug_logging:
                self.logger.debug("Cache disabled, skipping get for folder: %s", folder_id)
            return None
            
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
            
            # Check if show_tools_menu_item setting matches cached value
            from lib.config.config_manager import get_config
            config = get_config()
            current_show_tools = config.get_bool('show_tools_menu_item', True)
            cached_show_tools = payload.get('_show_tools')
            
            if cached_show_tools is not None and cached_show_tools != current_show_tools:
                self.logger.debug("Cache invalidated for folder %s - show_tools setting changed from %s to %s",
                                folder_id, cached_show_tools, current_show_tools)
                self.delete(folder_id)
                return None
            
            # Validate folder ID matches to prevent serving wrong cache due to filename collisions
            cached_folder_id = payload.get('_folder_id')
            
            # Normalize both IDs for comparison (handle root folder special case)
            def normalize_folder_id(fid):
                if fid is None or fid == "root":
                    return None
                return str(fid)
            
            expected_folder_id = normalize_folder_id(folder_id)
            actual_folder_id = normalize_folder_id(cached_folder_id)
            
            if actual_folder_id != expected_folder_id:
                self.logger.warning("Folder ID mismatch in cache for %s - expected %s, got %s (filename collision)", 
                                  folder_id, expected_folder_id, actual_folder_id)
                self.delete(folder_id)
                return None
            
            with self._stats_lock:
                self._stats['hits'] += 1
            
            # Count items correctly based on payload structure
            if 'processed_items' in payload:
                item_count = len(payload.get('processed_items', []))  # V4 processed format
            elif 'items' in payload:
                item_count = len(payload.get('items', []))  # Legacy root folder format
            elif 'lists' in payload:
                item_count = len(payload.get('lists', []))  # Subfolder format
            else:
                item_count = 0
                
            freshness = "fresh" if self._is_file_fresh(file_path) else "stale"
            self.logger.debug("Cache HIT for folder %s - %d items (%s)", 
                            folder_id, item_count, freshness)
            return payload
            
        except Exception as e:
            with self._stats_lock:
                self._stats['errors'] += 1
            self.logger.error("Error reading cache for folder %s: %s", folder_id, e)
            return None
    
    def set(self, folder_id: Optional[str], payload: Dict[str, Any], build_time_ms: Optional[int] = None) -> bool:
        """
        Store folder payload in cache with stampede protection
        
        Args:
            folder_id: Unique folder identifier
            payload: Folder data to cache (will be augmented with metadata)
            build_time_ms: Time taken to build folder (for metrics)
            
        Returns:
            bool: True if successful
        """
        # Check if caching is enabled
        if not self.cache_enabled:
            if self.debug_logging:
                self.logger.debug("Cache disabled, skipping set for folder: %s", folder_id)
            return False
            
        try:
            with self._singleton_lock(folder_id):
                return self._set_without_lock(folder_id, payload, build_time_ms)
        except TimeoutError as e:
            # Downgrade timeout errors to warning to reduce noise
            with self._stats_lock:
                self._stats['errors'] += 1
            self.logger.warning("Lock timeout for caching folder %s: %s", folder_id, e)
            return False
        except Exception as e:
            with self._stats_lock:
                self._stats['errors'] += 1
            self.logger.error("Error acquiring lock for caching folder %s: %s", folder_id, e)
            return False
    
    def _set_without_lock(self, folder_id: Optional[str], payload: Dict[str, Any], build_time_ms: Optional[int] = None) -> bool:
        """Internal set method that doesn't acquire locks (for use within existing locks)"""
        try:
            # VALIDATION: Prevent caching empty data that could corrupt the cache
            # Count items based on payload structure
            if 'processed_items' in payload:
                item_count = len(payload.get('processed_items', []))  # V4 processed format
            elif 'items' in payload:
                item_count = len(payload.get('items', []))  # Legacy root folder format
            elif 'lists' in payload:
                item_count = len(payload.get('lists', []))  # Subfolder format
            else:
                item_count = 0
            
            # CRITICAL: Don't cache empty data unless it's explicitly an empty folder state
            # Check if we have folder_info or explicit empty state markers
            has_folder_info = 'folder_info' in payload
            has_breadcrumbs = 'breadcrumbs' in payload
            is_explicit_empty_state = has_folder_info or has_breadcrumbs
            
            if item_count == 0 and not is_explicit_empty_state:
                self.logger.warning(
                    "CACHE VALIDATION FAILED: Refusing to cache folder %s with 0 items and no folder_info/breadcrumbs. "
                    "This prevents cache corruption from empty navigation states. Payload keys: %s",
                    folder_id, list(payload.keys())
                )
                return False
            
            # Log warning for suspicious empty cache (empty but with folder_info)
            if item_count == 0 and is_explicit_empty_state:
                self.logger.info(
                    "Caching empty folder %s with folder_info/breadcrumbs (legitimate empty state)",
                    folder_id
                )
            
            # Get current show_tools_menu_item setting for cache dependency tracking
            from lib.config.config_manager import get_config
            config = get_config()
            current_show_tools = config.get_bool('show_tools_menu_item', True)
            
            # Augment payload with cache metadata
            cache_payload = {
                **payload,
                '_built_at': datetime.now().isoformat(),
                '_folder_id': folder_id,
                '_schema': self.schema_version,
                '_show_tools': current_show_tools  # Track setting for cache invalidation
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
    
    def delete(self, folder_id: Optional[str]) -> bool:
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
    
    def is_fresh(self, folder_id: Optional[str]) -> bool:
        """Check if folder cache is fresh (within fresh TTL)"""
        file_path = self._get_cache_file_path(folder_id)
        return self._is_file_fresh(file_path)
    
    def is_stale_but_usable(self, folder_id: Optional[str]) -> bool:
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
                    # Format: folder_{id}_{hash}_anon_v{schema}.json (new) or folder_{id}_anon_v{schema}.json (old)
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
    
    def get_resilient(self, folder_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Get cached folder data with fallback to stale cache during high contention
        
        This method first tries to get fresh cache. If unavailable, it checks if there's
        stale but usable cache and serves that to avoid blocking users during high contention.
        """
        # First try to get fresh cache
        cached_data = self.get(folder_id, allow_stale=False)
        if cached_data:
            return cached_data
        
        # If no fresh cache and we have stale but usable cache, serve it
        if self.is_stale_but_usable(folder_id):
            self.logger.debug("Serving stale cache for folder %s due to fresh cache miss", folder_id)
            return self.get(folder_id, allow_stale=True)
            
        # No cache available at all
        return None
    
    def cleanup(self) -> int:
        """
        Full cache cleanup - removes expired files and old schema versions
        
        Returns:
            int: Total number of files cleaned up
        """
        expired_count = self.cleanup_expired()
        schema_count = self.cleanup_old_schemas()
        
        total = expired_count + schema_count
        if total > 0:
            self.logger.info("Full cache cleanup completed - %d total files removed", total)
        
        return total
    
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
    
    def pre_warm_folder(self, folder_id: Optional[str]) -> bool:
        """Pre-warm cache for a single folder (background operation, no UI)"""
        try:
            # Check if already cached and fresh
            if self.is_fresh(folder_id):
                self.logger.debug("Pre-warm: folder %s already fresh, skipping", folder_id)
                return True
            
            warm_start = time.time()
            
            # Use stampede protection - handle None folder_id for locking
            lock_key = str(folder_id) if folder_id is not None else "root"
            
            # Check if we already have this folder cached before attempting lock
            if self.get(folder_id):
                self.logger.debug("Pre-warm: folder %s already cached, skipping lock", folder_id)
                return True
                
            try:
                with self.with_build_lock(lock_key):
                    # Double-check after acquiring lock
                    if self.is_fresh(folder_id):
                        self.logger.debug("Pre-warm: folder %s became fresh while waiting for lock", folder_id)
                        return True
                    
                    # Get data layer for folder information (no UI operations)
                    from lib.data.query_manager import get_query_manager
                    query_manager = get_query_manager()
                    
                    if not query_manager.initialize():
                        self.logger.error("Pre-warm: failed to initialize query manager for folder %s", folder_id)
                        return False
                    
                    # Use same data sources as lists handler for consistency
                    if folder_id is None:
                        # Root folder: use get_all_lists_with_folders() to match lists handler
                        lists_in_folder = query_manager.get_all_lists_with_folders()
                        all_folders = query_manager.get_all_folders()
                        folder_info = None  # Root has no folder info
                        subfolders = []     # Root uses all_folders instead
                    else:
                        # Subfolder: use batch navigation query  
                        navigation_data = query_manager.get_folder_navigation_batch(folder_id)
                        
                        if not navigation_data:
                            self.logger.warning("Pre-warm: no navigation data returned for folder %s - creating empty cache", folder_id)
                            # Create empty but valid data structure
                            navigation_data = {
                                'folder_info': {'id': folder_id, 'name': 'Unknown Folder'},
                                'subfolders': [],
                                'lists': []
                            }
                        
                        # Extract data with safe defaults
                        folder_info = navigation_data.get('folder_info')
                        subfolders = navigation_data.get('subfolders') or []
                        lists_in_folder = navigation_data.get('lists') or []
                        all_folders = []  # Not needed for subfolders
                    
                    # Validate that we have valid data structures
                    if folder_id is None:
                        # Root folder validation
                        if not isinstance(lists_in_folder, (list, tuple)):
                            self.logger.warning("Pre-warm: root lists is not iterable: %s", type(lists_in_folder))
                            lists_in_folder = []
                        if not isinstance(all_folders, (list, tuple)):
                            self.logger.warning("Pre-warm: all_folders is not iterable: %s", type(all_folders))
                            all_folders = []
                    else:
                        # Subfolder validation
                        if not isinstance(subfolders, (list, tuple)):
                            self.logger.warning("Pre-warm: subfolders is not iterable for folder %s: %s", folder_id, type(subfolders))
                            subfolders = []
                        if not isinstance(lists_in_folder, (list, tuple)):
                            self.logger.warning("Pre-warm: lists is not iterable for folder %s: %s", folder_id, type(lists_in_folder))
                            lists_in_folder = []
                    
                    warm_time_ms = (time.time() - warm_start) * 1000
                    
                    # Cache processed items for V4 cache format  
                    if folder_id is None:
                        # Root folder: Build processed menu items with business logic applied
                        processed_menu_items = self._build_root_processed_items(lists_in_folder, all_folders)
                        
                        # Pre-compute breadcrumb components for root
                        breadcrumb_data = {
                            'directory_title': 'Lists',
                            'tools_label': 'Lists', 
                            'tools_description': 'Search, Favorites, Import/Export & Settings'
                        }
                        
                        cacheable_payload = {
                            'processed_items': processed_menu_items,  # V4: Store processed menu items with business logic
                            'breadcrumbs': breadcrumb_data,
                            'content_type': 'files'
                        }
                    else:
                        # Subfolder: Build processed menu items with business logic applied
                        processed_menu_items = self._build_subfolder_processed_items(folder_info, subfolders, lists_in_folder)
                        
                        folder_name = folder_info.get('name', 'Unknown Folder') if folder_info else 'Unknown Folder'
                        
                        # Pre-compute breadcrumb components for subfolder
                        breadcrumb_data = {
                            'directory_title': folder_name,
                            'tools_label': f"for '{folder_name}'",
                            'tools_description': f"Tools and options for this folder"
                        }
                        
                        cacheable_payload = {
                            'processed_items': processed_menu_items,  # V4: Store processed menu items with business logic
                            'breadcrumbs': breadcrumb_data,
                            'content_type': 'files'
                        }
                    
                    # Cache the payload (without additional locking since we're already in a lock)
                    self._set_without_lock(folder_id, cacheable_payload, int(warm_time_ms))
                    
                    self.logger.debug("Pre-warm: folder %s completed in %.2f ms", folder_id, warm_time_ms)
                    return True
                    
            except TimeoutError as te:
                self.logger.error("Lock timeout pre-warming folder %s: %s", folder_id, te)
                return False
                
        except Exception as e:
            self.logger.error("Error pre-warming folder %s: %s", folder_id, e)
            return False
    
    def _build_root_processed_items(self, all_lists, all_folders):
        """Build processed menu items for root folder with business logic applied
        
        NOTE: Tools & Options is NOT cached - it's added dynamically by lists_handler 
        based on user visibility setting which can change without cache invalidation.
        """
        menu_items = []
        base_url = "plugin://plugin.video.librarygenie/"
        
        # Tools & Options is added dynamically by lists_handler, not cached

        # Handle Kodi Favorites integration
        try:
            from lib.config.config_manager import get_config
            config = get_config()
            favorites_enabled = config.get_bool('favorites_integration_enabled', False)
        except Exception:
            favorites_enabled = False
            
        kodi_favorites_item = None
        for item in all_lists:
            if item.get('name') == 'Kodi Favorites':
                kodi_favorites_item = item
                break

        # Add Kodi Favorites first (if enabled and exists)
        if favorites_enabled and kodi_favorites_item:
            list_id = kodi_favorites_item.get('id')
            name = kodi_favorites_item.get('name', 'Kodi Favorites')
            description = kodi_favorites_item.get('description', '')
            list_url = f"{base_url}?action=show_list&list_id={list_id}"

            # NOTE: Don't add "Tools & Options" here - it's added dynamically by lists_handler
            context_menu = [
                self._get_tools_toggle_entry(base_url)
            ]

            menu_items.append({
                'label': name,
                'url': list_url,
                'is_folder': True,
                'description': description,
                'icon': "DefaultPlaylist.png",
                'context_menu': context_menu
            })

        # Add folders (excluding Search History)
        for folder_info in all_folders:
            folder_id = folder_info['id']
            folder_name = folder_info['name']

            # Skip the reserved "Search History" folder
            if folder_name == 'Search History':
                continue

            folder_url = f"{base_url}?action=show_folder&folder_id={folder_id}"
            
            # Build context menu with startup folder option
            from lib.config.config_manager import get_config
            config = get_config()
            startup_folder_id = config.get('startup_folder_id', None)
            
            context_menu = [
                (f"Rename '{folder_name}'", f"RunPlugin({base_url}?action=rename_folder&folder_id={folder_id})"),
                (f"Move '{folder_name}'", f"RunPlugin({base_url}?action=move_folder&folder_id={folder_id})"),
                (f"Delete '{folder_name}'", f"RunPlugin({base_url}?action=delete_folder&folder_id={folder_id})"),
            ]
            
            # Add startup folder option
            if str(folder_id) == str(startup_folder_id):
                context_menu.append((f"Clear Startup Folder", f"RunPlugin({base_url}?action=clear_startup_folder)"))
            else:
                context_menu.append((f"Set as Startup Folder", f"RunPlugin({base_url}?action=set_startup_folder&folder_id={folder_id})"))
            
            context_menu.append(self._get_tools_toggle_entry(base_url))

            menu_items.append({
                'label': folder_name,
                'url': folder_url,
                'is_folder': True,
                'description': "Folder",
                'context_menu': context_menu
            })

        # Add standalone lists (excluding Kodi Favorites as it's already added)
        standalone_lists = [item for item in all_lists if (not item.get('folder_name') or item.get('folder_name') == 'Root') and item.get('name') != 'Kodi Favorites']

        for list_item in standalone_lists:
            list_id = list_item.get('id')
            name = list_item.get('name', 'Unnamed List')
            description = list_item.get('description', '')
            list_url = f"{base_url}?action=show_list&list_id={list_id}"

            context_menu = [
                (f"Rename '{name}'", f"RunPlugin({base_url}?action=rename_list&list_id={list_id})"),
                (f"Move '{name}' to Folder", f"RunPlugin({base_url}?action=move_list_to_folder&list_id={list_id})"),
                (f"Export '{name}'", f"RunPlugin({base_url}?action=export_list&list_id={list_id})"),
                (f"Delete '{name}'", f"RunPlugin({base_url}?action=delete_list&list_id={list_id})"),
                self._get_tools_toggle_entry(base_url)
            ]

            menu_items.append({
                'label': name,
                'url': list_url,
                'is_folder': True,
                'description': description,
                'icon': "DefaultPlaylist.png",
                'context_menu': context_menu
            })

        return menu_items
    
    def _build_subfolder_processed_items(self, folder_info, subfolders, lists_in_folder):
        """Build processed menu items for subfolder with business logic applied
        
        NOTE: Tools & Options is NOT cached - it's added dynamically by lists_handler 
        based on user visibility setting which can change without cache invalidation.
        """
        menu_items = []
        base_url = "plugin://plugin.video.librarygenie/"
        
        # Tools & Options is added dynamically by show_folder handler, not cached
        
        # Add subfolders in this folder
        if subfolders:
            for subfolder in subfolders:
                subfolder_id = subfolder.get('id')
                subfolder_name = subfolder.get('name', 'Unnamed Folder')
                
                subfolder_url = f"{base_url}?action=show_folder&folder_id={subfolder_id}"
                
                # Build context menu with startup folder option
                from lib.config.config_manager import get_config
                config = get_config()
                startup_folder_id = config.get('startup_folder_id', None)
                
                context_menu = [
                    (f"Rename '{subfolder_name}'", f"RunPlugin({base_url}?action=rename_folder&folder_id={subfolder_id})"),
                    (f"Move '{subfolder_name}'", f"RunPlugin({base_url}?action=move_folder&folder_id={subfolder_id})"),
                    (f"Delete '{subfolder_name}'", f"RunPlugin({base_url}?action=delete_folder&folder_id={subfolder_id})"),
                ]
                
                # Add startup folder option
                if str(subfolder_id) == str(startup_folder_id):
                    context_menu.append((f"Clear Startup Folder", f"RunPlugin({base_url}?action=clear_startup_folder)"))
                else:
                    context_menu.append((f"Set as Startup Folder", f"RunPlugin({base_url}?action=set_startup_folder&folder_id={subfolder_id})"))
                
                context_menu.append(self._get_tools_toggle_entry(base_url))
                
                menu_items.append({
                    'label': f"📁 {subfolder_name}",
                    'url': subfolder_url,
                    'is_folder': True,
                    'description': "Subfolder",
                    'context_menu': context_menu,
                    'icon': "DefaultFolder.png"
                })
        
        # Add lists in this folder
        if lists_in_folder:
            for list_item in lists_in_folder:
                list_id = list_item.get('id')
                name = list_item.get('name', 'Unnamed List')
                description = list_item.get('description', '')
                
                list_url = f"{base_url}?action=show_list&list_id={list_id}"
                context_menu = [
                    (f"Rename '{name}'", f"RunPlugin({base_url}?action=rename_list&list_id={list_id})"),
                    (f"Move '{name}' to Folder", f"RunPlugin({base_url}?action=move_list_to_folder&list_id={list_id})"),
                    (f"Export '{name}'", f"RunPlugin({base_url}?action=export_list&list_id={list_id})"),
                    (f"Delete '{name}'", f"RunPlugin({base_url}?action=delete_list&list_id={list_id})"),
                    self._get_tools_toggle_entry(base_url)
                ]
                
                menu_items.append({
                    'label': name,
                    'url': list_url,
                    'is_folder': True,
                    'description': description,
                    'icon': "DefaultPlaylist.png",
                    'context_menu': context_menu
                })
        
        return menu_items
    
    
    def pre_warm_common_folders(self, max_folders: Optional[int] = None) -> Dict[str, Any]:
        """Pre-warm cache for commonly accessed folders"""
        try:
            # Check if import is in progress - skip pre-warming to avoid race conditions
            from lib.utils.sync_lock import is_import_in_progress
            if is_import_in_progress():
                self.logger.info("Pre-warming skipped - import in progress")
                return {
                    "success": False,
                    "error": "Import in progress - pre-warming paused",
                    "folders_attempted": 0,
                    "folders_success": 0
                }
            
            # Check if pre-warming is enabled
            if not self.cache_enabled or not self.prewarm_enabled:
                self.logger.debug("Pre-warming disabled via configuration")
                return {
                    "success": False,
                    "error": "Pre-warming disabled in settings",
                    "folders_attempted": 0,
                    "folders_success": 0
                }
            
            # Use configuration value if not specified
            if max_folders is None:
                max_folders = self.prewarm_max_folders
                
            self.logger.info("Starting cache pre-warming for common folders (max: %d)", max_folders)
            pre_warm_start = time.time()
            
            # Get data layer for folder analysis
            from lib.data.query_manager import get_query_manager
            query_manager = get_query_manager()
            
            if not query_manager.initialize():
                self.logger.error("Pre-warm: failed to initialize query manager")
                return {"success": False, "error": "Failed to initialize query manager"}
            
            # Get root folder and immediate subfolders to prioritize
            common_folders = []
            
            # Always include root folder (use None for root level)
            common_folders.append(None)
            
            # Add startup folder if configured (high priority)
            from lib.config.config_manager import get_config
            config = get_config()
            startup_folder_id = config.get('startup_folder_id', None)
            if startup_folder_id:
                # Add to beginning after root for high priority
                common_folders.append(str(startup_folder_id))
                self.logger.debug("Pre-warm: included startup folder %s", startup_folder_id)
            
            # Get root-level subfolders (most commonly accessed)
            try:
                # Adjust limit to account for root and startup folder
                folders_remaining = max_folders - len(common_folders)
                with query_manager.connection_manager.transaction() as conn:
                    root_subfolders = conn.execute("""
                        SELECT id, name
                        FROM folders 
                        WHERE parent_id IS NULL OR parent_id = ''
                        ORDER BY name
                        LIMIT ?
                    """, [folders_remaining]).fetchall()
                    
                    for subfolder in root_subfolders:
                        folder_id = str(subfolder['id'])
                        # Skip startup folder if already added
                        if folder_id != startup_folder_id:
                            common_folders.append(folder_id)
                        
            except Exception as e:
                self.logger.warning("Pre-warm: failed to get root subfolders: %s", e)
                # Continue with root and startup folders
            
            # Pre-warm folders
            results = {
                "success": True,
                "folders_attempted": len(common_folders),
                "folders_success": 0,
                "folders_failed": 0,
                "errors": []
            }
            
            for folder_id in common_folders:
                try:
                    self.logger.debug("Pre-warming cache for folder %s", folder_id)
                    if self.pre_warm_folder(folder_id):
                        results["folders_success"] += 1
                    else:
                        results["folders_failed"] += 1
                        results["errors"].append(f"Failed to warm folder {folder_id}")
                except Exception as e:
                    self.logger.error("Error pre-warming folder %s: %s", folder_id, str(e))
                    results["folders_failed"] += 1
                    results["errors"].append(f"Error warming folder {folder_id}: {str(e)}")
            
            pre_warm_time = (time.time() - pre_warm_start) * 1000
            results["total_time_ms"] = int(pre_warm_time)
            
            self.logger.info("Pre-warming completed: %d/%d folders warmed in %.2f ms", 
                           results["folders_success"], results["folders_attempted"], pre_warm_time)
            
            return results
            
        except Exception as e:
            self.logger.error("Error during cache pre-warming: %s", e)
            return {"success": False, "error": str(e)}
    
    def initialize_cache_service(self, enable_pre_warming: Optional[bool] = None) -> bool:
        """Initialize cache service with optional pre-warming"""
        try:
            self.logger.info("Initializing folder cache service... (cache_enabled: %s)", self.cache_enabled)
            
            # Skip initialization if caching is disabled
            if not self.cache_enabled:
                self.logger.debug("Cache disabled via configuration, skipping service initialization")
                return True  # Return True since this is expected behavior
            
            # Ensure cache directory exists
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Clean up expired files
            cleaned_count = self.cleanup_expired()
            if cleaned_count > 0:
                self.logger.info("Cache service: cleaned up %d expired files", cleaned_count)
            
            # Use configuration setting if not explicitly specified
            if enable_pre_warming is None:
                enable_pre_warming = self.prewarm_enabled
            
            # Pre-warm common folders if enabled
            if enable_pre_warming:
                # Run pre-warming in background thread to avoid blocking startup
                import threading
                def background_pre_warm():
                    try:
                        self.logger.debug("Starting background cache pre-warming")
                        results = self.pre_warm_common_folders()
                        if results["success"]:
                            self.logger.info("Background pre-warming completed: %d folders warmed", 
                                           results["folders_success"])
                        else:
                            self.logger.warning("Background pre-warming failed: %s", results.get("error"))
                    except Exception as e:
                        self.logger.error("Error in background pre-warming: %s", e)
                
                pre_warm_thread = threading.Thread(target=background_pre_warm, daemon=True)
                pre_warm_thread.start()
                self.logger.debug("Cache service: background pre-warming thread started")
            
            self.logger.info("Folder cache service initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize cache service: %s", e)
            return False
    
    def invalidate_folder(self, folder_id: Optional[str]) -> bool:
        """Invalidate cache for a specific folder"""
        try:
            file_path = self._get_cache_file_path(folder_id)
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.debug("Invalidated cache for folder %s", folder_id)
                return True
            else:
                self.logger.debug("No cache file to invalidate for folder %s", folder_id)
                return False
        except Exception as e:
            self.logger.error("Error invalidating cache for folder %s: %s", folder_id, e)
            return False
    
    def invalidate_parent_folder(self, folder_id: Optional[str]) -> bool:
        """Invalidate cache for the parent folder of a given folder"""
        try:
            # Get parent folder information
            from lib.data.query_manager import get_query_manager
            query_manager = get_query_manager()
            
            if not query_manager.initialize():
                self.logger.error("Failed to initialize query manager for parent invalidation")
                return False
            
            # Get folder info to find parent
            with query_manager.connection_manager.transaction() as conn:
                folder_info = conn.execute("""
                    SELECT parent_id FROM folders WHERE id = ?
                """, [folder_id]).fetchone()
                
                if folder_info and folder_info['parent_id']:
                    parent_folder_id = str(folder_info['parent_id'])
                    return self.invalidate_folder(parent_folder_id)
                else:
                    # This folder is at root level, invalidate root folder (None for root)
                    return self.invalidate_folder(None)
                    
        except Exception as e:
            self.logger.error("Error invalidating parent folder for %s: %s", folder_id, e)
            return False
    
    def invalidate_folder_hierarchy(self, folder_id: Optional[str]) -> Dict[str, bool]:
        """Invalidate cache for a folder and all its subfolders"""
        try:
            self.logger.debug("Invalidating folder hierarchy for %s", folder_id)
            results = {}
            
            # Get query manager for folder hierarchy queries
            from lib.data.query_manager import get_query_manager
            query_manager = get_query_manager()
            
            if not query_manager.initialize():
                self.logger.error("Failed to initialize query manager for hierarchy invalidation")
                return {"error": True}
            
            # Get all subfolders recursively
            affected_folders = [folder_id]  # Start with the folder itself
            
            with query_manager.connection_manager.transaction() as conn:
                # Recursive query to find all subfolders
                folders_to_check = [folder_id]
                while folders_to_check:
                    current_folder = folders_to_check.pop(0)
                    
                    # Find direct subfolders
                    subfolders = conn.execute("""
                        SELECT id FROM folders WHERE parent_id = ?
                    """, [current_folder]).fetchall()
                    
                    for subfolder in subfolders:
                        subfolder_id = str(subfolder['id'])
                        affected_folders.append(subfolder_id)
                        folders_to_check.append(subfolder_id)
            
            # Invalidate all affected folders
            for affected_folder_id in affected_folders:
                results[affected_folder_id] = self.invalidate_folder(affected_folder_id)
            
            invalidated_count = sum(1 for success in results.values() if success)
            self.logger.info("Invalidated %d/%d folders in hierarchy for %s", 
                           invalidated_count, len(results), folder_id)
            
            return results
            
        except Exception as e:
            self.logger.error("Error invalidating folder hierarchy for %s: %s", folder_id, e)
            return {"error": True}
    
    def invalidate_after_folder_operation(self, operation: str, folder_id: Optional[str], **kwargs) -> bool:
        """
        Invalidate relevant caches after folder operations
        
        Args:
            operation: Type of operation ('create', 'delete', 'rename', 'move')
            folder_id: The folder ID involved in the operation
            **kwargs: Additional operation-specific parameters
                - target_parent_id: For move operations, the new parent folder
                - source_parent_id: For move operations, the old parent folder
        """
        try:
            self.logger.debug("Processing cache invalidation for %s operation on folder %s", operation, folder_id)
            
            if operation == 'create':
                # When creating a folder, invalidate the parent folder
                return self.invalidate_parent_folder(folder_id)
            
            elif operation == 'delete':
                # When deleting a folder, invalidate:
                # 1. The folder itself and all subfolders
                # 2. The parent folder (to remove the deleted folder from listings)
                hierarchy_results = self.invalidate_folder_hierarchy(folder_id)
                
                # Use passed parent_id if available, otherwise try to query (may fail if already deleted)
                if 'parent_id' in kwargs:
                    parent_id = kwargs['parent_id']
                    if parent_id:
                        parent_result = self.invalidate_folder(str(parent_id))
                    else:
                        parent_result = self.invalidate_folder(None)  # Root folder
                else:
                    # Fallback to querying parent (may fail if folder already deleted)
                    parent_result = self.invalidate_parent_folder(folder_id)
                
                # Return True if at least one invalidation succeeded
                hierarchy_success = any(result for result in hierarchy_results.values() if isinstance(result, bool))
                return hierarchy_success or parent_result
            
            elif operation == 'rename':
                # When renaming a folder, invalidate:
                # 1. The folder itself (new name needs to be cached)
                # 2. The parent folder (to show updated name in listings)
                folder_result = self.invalidate_folder(folder_id)
                parent_result = self.invalidate_parent_folder(folder_id)
                return folder_result or parent_result
            
            elif operation == 'move':
                # When moving a folder, invalidate:
                # 1. The folder itself and subfolders (new parent context)
                # 2. The old parent folder (folder no longer there)
                # 3. The new parent folder (folder now there)
                hierarchy_results = self.invalidate_folder_hierarchy(folder_id)
                
                # Invalidate source parent if provided
                source_parent_result = True
                if 'source_parent_id' in kwargs:
                    source_parent_id = kwargs['source_parent_id']
                    if source_parent_id:
                        source_parent_result = self.invalidate_folder(str(source_parent_id))
                    else:
                        source_parent_result = self.invalidate_folder(None)  # Root folder
                
                # Invalidate target parent if provided
                target_parent_result = True
                if 'target_parent_id' in kwargs:
                    target_parent_id = kwargs['target_parent_id']
                    if target_parent_id:
                        target_parent_result = self.invalidate_folder(str(target_parent_id))
                    else:
                        target_parent_result = self.invalidate_folder(None)  # Root folder
                
                # Return True if at least one invalidation succeeded
                hierarchy_success = any(result for result in hierarchy_results.values() if isinstance(result, bool))
                return hierarchy_success or source_parent_result or target_parent_result
            
            else:
                self.logger.warning("Unknown folder operation for cache invalidation: %s", operation)
                return False
                
        except Exception as e:
            self.logger.error("Error in cache invalidation for %s operation on folder %s: %s", operation, folder_id, e)
            return False


# Global instance
_folder_cache_instance = None
_instance_lock = threading.Lock()


def get_folder_cache(schema_version: int = CACHE_SCHEMA_VERSION) -> FolderCache:
    """Get global folder cache instance"""
    global _folder_cache_instance
    
    with _instance_lock:
        if _folder_cache_instance is None or _folder_cache_instance.schema_version != schema_version:
            _folder_cache_instance = FolderCache(schema_version=schema_version)
    
    return _folder_cache_instance