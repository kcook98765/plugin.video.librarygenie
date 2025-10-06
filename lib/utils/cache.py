#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Cache Helper
Provides time-based caching for API responses
"""

import time
import json
from typing import Optional, Dict, Any


class SimpleCache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if time.time() > entry['expires_at']:
            # Expired, remove it
            del self._cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Set cached value with TTL (default 1 hour)"""
        self._cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl_seconds
        }
    
    def clear(self, key: Optional[str] = None):
        """Clear specific key or all cache"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()


# Global cache instance
_global_cache = SimpleCache()


def get_cached(key: str) -> Optional[Any]:
    """Get value from global cache"""
    return _global_cache.get(key)


def set_cached(key: str, value: Any, ttl_seconds: int = 3600):
    """Set value in global cache"""
    _global_cache.set(key, value, ttl_seconds)


def clear_cache(key: Optional[str] = None):
    """Clear global cache"""
    _global_cache.clear(key)
