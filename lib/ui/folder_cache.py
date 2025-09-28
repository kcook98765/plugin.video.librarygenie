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
        """Generate cache file path for folder ID"""
        # Sanitize folder_id for filename use
        safe_folder_id = "".join(c for c in folder_id if c.isalnum() or c in '-_').strip()
        filename = f"folder_{safe_folder_id}_anon_v{self.schema_version}.json"
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
    
    @contextmanager
    def with_build_lock(self, folder_id: str):
        """Public context manager for build operations with stampede protection"""
        with self._singleton_lock(folder_id):
            yield
    
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
    
    def pre_warm_folder(self, folder_id: str) -> bool:
        """Pre-warm cache for a single folder (background operation, no UI)"""
        try:
            # Check if already cached and fresh
            if self.is_fresh(folder_id):
                self.logger.debug("Pre-warm: folder %s already fresh, skipping", folder_id)
                return True
            
            self.logger.debug("Pre-warming cache for folder %s", folder_id)
            warm_start = time.time()
            
            # Use stampede protection
            with self.with_build_lock(folder_id):
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
                
                # Get folder navigation data
                navigation_data = query_manager.get_folder_navigation_batch(folder_id)
                
                if not navigation_data or not navigation_data.get('folder_info'):
                    self.logger.warning("Pre-warm: no data found for folder %s", folder_id)
                    return False
                
                folder_info = navigation_data['folder_info']
                subfolders = navigation_data['subfolders']
                lists_in_folder = navigation_data['lists']
                
                # Build cacheable payload (data-only, no UI operations)
                menu_items = []
                
                # Add subfolders
                for subfolder in subfolders:
                    subfolder_id = subfolder.get('id')
                    subfolder_name = subfolder.get('name', 'Unnamed Folder')
                    
                    url = f"plugin://plugin.video.librarygenie/?action=show_folder&folder_id={subfolder_id}"
                    context_menu = [
                        (f"Rename '{subfolder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_folder&folder_id={subfolder_id})"),
                        (f"Move '{subfolder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=move_folder&folder_id={subfolder_id})"),
                        (f"Delete '{subfolder_name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_folder&folder_id={subfolder_id})")
                    ]
                    
                    menu_items.append({
                        'label': f"📁 {subfolder_name}",
                        'url': url,
                        'is_folder': True,
                        'description': "Subfolder",
                        'context_menu': context_menu,
                        'icon': "DefaultFolder.png"
                    })
                
                # Add lists
                for list_item in lists_in_folder:
                    list_id = list_item.get('id')
                    name = list_item.get('name', 'Unnamed List')
                    description = list_item.get('description', '')
                    
                    url = f"plugin://plugin.video.librarygenie/?action=show_list&list_id={list_id}"
                    context_menu = [
                        (f"Rename '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})"),
                        (f"Move '{name}' to Folder", f"RunPlugin(plugin://plugin.video.librarygenie/?action=move_list_to_folder&list_id={list_id})"),
                        (f"Export '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=export_list&list_id={list_id})"),
                        (f"Delete '{name}'", f"RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_id})")
                    ]
                    
                    menu_items.append({
                        'label': name,
                        'url': url,
                        'is_folder': True,
                        'description': description,
                        'icon': "DefaultPlaylist.png",
                        'context_menu': context_menu
                    })
                
                warm_time_ms = (time.time() - warm_start) * 1000
                
                # Create cacheable payload
                cacheable_payload = {
                    'items': menu_items,
                    'update_listing': False,
                    'content_type': 'files'
                }
                
                # Cache the payload
                self.set(folder_id, cacheable_payload, int(warm_time_ms))
                
                self.logger.debug("Pre-warm: folder %s completed in %.2f ms", folder_id, warm_time_ms)
                return True
                
        except Exception as e:
            self.logger.error("Error pre-warming folder %s: %s", folder_id, e)
            return False
    
    def pre_warm_common_folders(self, max_folders: int = 5) -> Dict[str, Any]:
        """Pre-warm cache for commonly accessed folders"""
        try:
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
            
            # Always include root folder (empty string or None)
            common_folders.append("")
            
            # Get root-level subfolders (most commonly accessed)
            try:
                with query_manager.connection_manager.transaction() as conn:
                    root_subfolders = conn.execute("""
                        SELECT id, name
                        FROM folders 
                        WHERE parent_folder_id IS NULL OR parent_folder_id = ''
                        ORDER BY name
                        LIMIT ?
                    """, [max_folders - 1]).fetchall()  # -1 for root folder
                    
                    for subfolder in root_subfolders:
                        common_folders.append(str(subfolder['id']))
                        
            except Exception as e:
                self.logger.warning("Pre-warm: failed to get root subfolders: %s", e)
                # Continue with just root folder
            
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
                    if self.pre_warm_folder(folder_id):
                        results["folders_success"] += 1
                    else:
                        results["folders_failed"] += 1
                        results["errors"].append(f"Failed to warm folder {folder_id}")
                except Exception as e:
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
    
    def initialize_cache_service(self, enable_pre_warming: bool = True) -> bool:
        """Initialize cache service with optional pre-warming"""
        try:
            self.logger.info("Initializing folder cache service...")
            
            # Ensure cache directory exists
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Clean up expired files
            cleaned_count = self.cleanup_expired()
            if cleaned_count > 0:
                self.logger.info("Cache service: cleaned up %d expired files", cleaned_count)
            
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