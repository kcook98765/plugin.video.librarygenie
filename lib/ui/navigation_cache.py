#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Navigation State Caching
Lightweight caching layer for frequently accessed Kodi navigation properties
"""

import time
import threading
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
import xbmc
from ..utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('lib.ui.navigation_cache')

class NavigationStateCache:
    """
    Singleton cache for Kodi navigation properties with TTL and generation-based invalidation.
    Optimizes repeated Container.* and System.* calls during navigation operations.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(NavigationStateCache, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._cache = {}  # {label: {value, timestamp, generation}}
        self._generation = 0
        self._enabled = True
        self._default_ttl_ms = 200
        self._lock = threading.Lock()
        self._initialized = True
        
        logger.debug("NavigationStateCache initialized (TTL: %dms)", self._default_ttl_ms)
    
    def enable(self, enabled: bool = True):
        """Enable or disable caching globally"""
        self._enabled = enabled
        if not enabled:
            self.clear()
        logger.debug("NavigationStateCache %s", "enabled" if enabled else "disabled")
    
    def clear(self):
        """Clear all cached entries"""
        with self._lock:
            self._cache.clear()
            logger.debug("NavigationStateCache cleared")
    
    def bump_generation(self):
        """Invalidate all cached entries by bumping generation ID"""
        with self._lock:
            self._generation += 1
            logger.debug("NavigationStateCache generation bumped to %d", self._generation)
    
    def get(self, label: str, ttl_ms: Optional[int] = None) -> str:
        """
        Get cached value for a Kodi info label with TTL check.
        
        Args:
            label: Kodi info label (e.g., "Container.FolderPath")
            ttl_ms: TTL in milliseconds (default: 200ms)
            
        Returns:
            str: Cached or fresh value from xbmc.getInfoLabel()
        """
        if not self._enabled:
            return xbmc.getInfoLabel(label)
        
        ttl_ms = ttl_ms or self._default_ttl_ms
        now = time.monotonic()
        
        with self._lock:
            entry = self._cache.get(label)
            
            # Check if entry is valid (exists, not expired, current generation)
            if entry and (
                now - entry['timestamp'] <= ttl_ms / 1000.0 and
                entry['generation'] == self._generation
            ):
                logger.debug("Cache HIT for '%s': %s", label, entry['value'])
                return entry['value']
        
        # Cache miss - fetch fresh value
        value = xbmc.getInfoLabel(label)
        
        with self._lock:
            self._cache[label] = {
                'value': value,
                'timestamp': now,
                'generation': self._generation
            }
        
        logger.debug("Cache MISS for '%s': %s", label, value)
        return value
    
    def get_many(self, labels: List[str], ttl_ms: Optional[int] = None) -> Dict[str, str]:
        """
        Get multiple cached values efficiently.
        
        Args:
            labels: List of Kodi info labels
            ttl_ms: TTL in milliseconds (default: 200ms)
            
        Returns:
            dict: Mapping of label -> value
        """
        if not self._enabled:
            return {label: xbmc.getInfoLabel(label) for label in labels}
        
        result = {}
        missing_labels = []
        
        ttl_ms = ttl_ms or self._default_ttl_ms
        now = time.monotonic()
        
        # Check cache for existing entries
        with self._lock:
            for label in labels:
                entry = self._cache.get(label)
                
                if entry and (
                    now - entry['timestamp'] <= ttl_ms / 1000.0 and
                    entry['generation'] == self._generation
                ):
                    result[label] = entry['value']
                    logger.debug("Cache HIT for '%s': %s", label, entry['value'])
                else:
                    missing_labels.append(label)
        
        # Fetch missing values
        for label in missing_labels:
            value = xbmc.getInfoLabel(label)
            result[label] = value
            
            with self._lock:
                self._cache[label] = {
                    'value': value,
                    'timestamp': now,
                    'generation': self._generation
                }
            
            logger.debug("Cache MISS for '%s': %s", label, value)
        
        if missing_labels:
            logger.debug("get_many: %d hits, %d misses", len(labels) - len(missing_labels), len(missing_labels))
        
        return result
    
    def snapshot(self, ttl_ms: Optional[int] = None) -> Dict[str, str]:
        """
        Get a snapshot of all common navigation properties in one batch call.
        
        Args:
            ttl_ms: TTL in milliseconds (default: 200ms)
            
        Returns:
            dict: Navigation state snapshot with keys:
                - folder_path, current_item, num_items, current_window, 
                - current_control, focused_label, viewmode
        """
        labels = [
            'Container.FolderPath',
            'Container.CurrentItem', 
            'Container.NumItems',
            'System.CurrentWindow',
            'System.CurrentControlId',
            'Container.ListItem().Label',
            'Container.Viewmode'
        ]
        
        values = self.get_many(labels, ttl_ms)
        
        # Return with friendly keys
        return {
            'folder_path': values.get('Container.FolderPath', ''),
            'current_item': values.get('Container.CurrentItem', ''),
            'num_items': values.get('Container.NumItems', ''),
            'current_window': values.get('System.CurrentWindow', ''),
            'current_control': values.get('System.CurrentControlId', ''),
            'focused_label': values.get('Container.ListItem().Label', ''),
            'viewmode': values.get('Container.Viewmode', '')
        }
    
    @contextmanager
    def nav_mutation(self, grace_ms: int = 150):
        """
        Context manager for navigation operations that may change UI state.
        Bumps generation before and after the operation with a grace period.
        
        Args:
            grace_ms: Grace period in milliseconds to allow UI to settle
            
        Usage:
            with cache.nav_mutation():
                xbmc.executebuiltin("Action(Down)")
        """
        logger.debug("nav_mutation: Starting (grace: %dms)", grace_ms)
        
        # Invalidate cache before navigation
        self.bump_generation()
        
        try:
            yield
        finally:
            # Allow UI to settle, then invalidate again
            if grace_ms > 0:
                time.sleep(grace_ms / 1000.0)
            self.bump_generation()
            logger.debug("nav_mutation: Completed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for debugging"""
        with self._lock:
            return {
                'enabled': self._enabled,
                'generation': self._generation,
                'cached_entries': len(self._cache),
                'default_ttl_ms': self._default_ttl_ms,
                'labels': list(self._cache.keys())
            }

# Global singleton instance
_nav_cache = None

def get_navigation_cache() -> NavigationStateCache:
    """Get the global NavigationStateCache instance"""
    global _nav_cache
    if _nav_cache is None:
        _nav_cache = NavigationStateCache()
    return _nav_cache

# Convenience functions for direct use
def get_cached_info(label: str, ttl_ms: Optional[int] = None) -> str:
    """Get cached Kodi info label value"""
    return get_navigation_cache().get(label, ttl_ms)

def get_navigation_snapshot(ttl_ms: Optional[int] = None) -> Dict[str, str]:
    """Get cached navigation state snapshot"""
    return get_navigation_cache().snapshot(ttl_ms)

def invalidate_navigation_cache():
    """Invalidate the navigation cache"""
    get_navigation_cache().bump_generation()

@contextmanager
def navigation_action(grace_ms: int = 150):
    """Context manager for navigation actions"""
    with get_navigation_cache().nav_mutation(grace_ms):
        yield