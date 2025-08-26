#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 12 Remote Service
Main service class for remote API integration
"""

from typing import Dict, Any, List, Optional, Tuple

import xbmc

from ..utils.logger import get_logger
from ..config.settings import get_phase12_remote_settings
from .http_client import get_remote_client
from .mapper import RemoteMapper
from .cache import RemoteCache


class RemoteService:
    """Main service for remote API integration"""
    
    def __init__(self, settings_getter=None):
        self.logger = get_logger(__name__)
        self.settings_getter = settings_getter or get_phase12_remote_settings
        self.mapper = RemoteMapper()
        self.cache = RemoteCache()
        self._client = None
        self._last_settings_check = 0
    
    def is_enabled(self) -> bool:
        """Check if remote integration is enabled"""
        settings = self.settings_getter()
        return settings.get('remote_enabled', False)
    
    def is_configured(self) -> bool:
        """Check if remote service is properly configured"""
        if not self.is_enabled():
            return False
        
        settings = self.settings_getter()
        return bool(settings.get('remote_base_url')) and bool(settings.get('remote_api_key'))
    
    def get_client(self) -> Optional:
        """Get configured HTTP client or None if not available"""
        if not self.is_configured():
            return None
        
        # Check if we need to recreate client due to settings change
        import time
        current_time = time.time()
        if current_time - self._last_settings_check > 30:  # Check every 30 seconds
            self._client = None
            self._last_settings_check = current_time
        
        if self._client is None:
            settings = self.settings_getter()
            self._client = get_remote_client(
                base_url=settings.get('remote_base_url', ''),
                api_key=settings.get('remote_api_key', ''),
                timeout=settings.get('remote_timeout_seconds', 10),
                retry_count=settings.get('remote_retry_count', 2),
                rate_limit_ms=settings.get('remote_rate_limit_ms', 100),
                log_requests=settings.get('remote_log_requests', False)
            )
        
        return self._client
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to remote service"""
        if not self.is_enabled():
            return {
                'success': False,
                'message': 'Remote integration is disabled',
                'action': 'enable_remote'
            }
        
        if not self.is_configured():
            return {
                'success': False,
                'message': 'Remote service not configured (missing URL or API key)',
                'action': 'configure_remote'
            }
        
        client = self.get_client()
        if not client:
            return {
                'success': False,
                'message': 'Failed to create HTTP client',
                'action': 'check_settings'
            }
        
        try:
            result = client.health_check()
            if result.get('success'):
                self.logger.info(f"Remote connection test successful: {result.get('response_time_ms', 0)}ms")
            else:
                self.logger.warning(f"Remote connection test failed: {result.get('message')}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Connection test error: {e}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}',
                'error_type': type(e).__name__
            }
    
    def search_movies(self, query: str, **options) -> Tuple[List[Dict], bool]:
        """Search for movies, returning (results, used_remote)"""
        settings = self.settings_getter()
        
        # Check if remote search is enabled and configured
        if not (self.is_configured() and settings.get('remote_search_enabled', True)):
            return [], False
        
        # Check cache first if enabled
        if settings.get('remote_cache_enabled', True):
            cache_key = f"search:{query}:{options.get('limit', 50)}"
            cached_results = self.cache.get(cache_key)
            if cached_results is not None:
                self.logger.debug(f"Using cached remote search results for: {query}")
                mapped_results = self._map_and_filter_results(cached_results, settings)
                return mapped_results, True
        
        # Make remote request
        client = self.get_client()
        if not client:
            return [], False
        
        try:
            response = client.search_movies(query, **options)
            
            if response.get('success'):
                results = response.get('results', [])
                
                # Cache results if enabled
                if settings.get('remote_cache_enabled', True):
                    cache_key = f"search:{query}:{options.get('limit', 50)}"
                    self.cache.set(cache_key, results, ttl_hours=settings.get('remote_cache_ttl_hours', 6))
                
                # Map and filter results
                mapped_results = self._map_and_filter_results(results, settings)
                
                self.logger.info(f"Remote search for '{query}': {len(results)} results, {len(mapped_results)} mapped")
                return mapped_results, True
            
            else:
                self.logger.warning(f"Remote search failed: {response.get('message')}")
                return [], False
                
        except Exception as e:
            self.logger.error(f"Remote search error: {e}")
            return [], False
    
    def get_remote_lists(self) -> Tuple[List[Dict], bool]:
        """Get list of remote lists, returning (lists, used_remote)"""
        settings = self.settings_getter()
        
        if not (self.is_configured() and settings.get('remote_lists_enabled', True)):
            return [], False
        
        # Check cache first
        if settings.get('remote_cache_enabled', True):
            cached_lists = self.cache.get('remote_lists')
            if cached_lists is not None:
                self.logger.debug("Using cached remote lists")
                return cached_lists, True
        
        client = self.get_client()
        if not client:
            return [], False
        
        try:
            response = client.get_remote_lists()
            
            if response.get('success'):
                lists = response.get('lists', [])
                
                # Cache results
                if settings.get('remote_cache_enabled', True):
                    self.cache.set('remote_lists', lists, ttl_hours=settings.get('remote_cache_ttl_hours', 6))
                
                self.logger.info(f"Retrieved {len(lists)} remote lists")
                return lists, True
            
            else:
                self.logger.warning(f"Failed to get remote lists: {response.get('message')}")
                return [], False
                
        except Exception as e:
            self.logger.error(f"Remote lists error: {e}")
            return [], False
    
    def get_list_contents(self, list_id: str, **options) -> Tuple[List[Dict], bool]:
        """Get remote list contents, returning (items, used_remote)"""
        settings = self.settings_getter()
        
        if not (self.is_configured() and settings.get('remote_lists_enabled', True)):
            return [], False
        
        # Check cache first
        if settings.get('remote_cache_enabled', True):
            cache_key = f"list_contents:{list_id}:{options.get('limit', 100)}"
            cached_contents = self.cache.get(cache_key)
            if cached_contents is not None:
                self.logger.debug(f"Using cached remote list contents for: {list_id}")
                mapped_results = self._map_and_filter_results(cached_contents, settings)
                return mapped_results, True
        
        client = self.get_client()
        if not client:
            return [], False
        
        try:
            response = client.get_list_contents(list_id, **options)
            
            if response.get('success'):
                items = response.get('items', [])
                
                # Cache results
                if settings.get('remote_cache_enabled', True):
                    cache_key = f"list_contents:{list_id}:{options.get('limit', 100)}"
                    self.cache.set(cache_key, items, ttl_hours=settings.get('remote_cache_ttl_hours', 6))
                
                # Map and filter results
                mapped_results = self._map_and_filter_results(items, settings)
                
                self.logger.info(f"Remote list '{list_id}': {len(items)} items, {len(mapped_results)} mapped")
                return mapped_results, True
            
            else:
                self.logger.warning(f"Failed to get list contents: {response.get('message')}")
                return [], False
                
        except Exception as e:
            self.logger.error(f"Remote list contents error: {e}")
            return [], False
    
    def clear_cache(self) -> bool:
        """Clear all remote cache data"""
        try:
            self.cache.clear_all()
            self.logger.info("Remote cache cleared")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear remote cache: {e}")
            return False
    
    def _map_and_filter_results(self, remote_results: List[Dict], settings: Dict[str, Any]) -> List[Dict]:
        """Map remote results to local library and filter based on settings"""
        mapped_results = []
        show_nonlocal = settings.get('remote_show_nonlocal', False)
        
        for remote_item in remote_results:
            # Try to map to local library
            local_mapping = self.mapper.map_to_local(remote_item)
            
            if local_mapping:
                # Item found in local library - enhance with local data
                enhanced_item = {**remote_item}
                enhanced_item.update(local_mapping)
                enhanced_item['_mapped'] = True
                enhanced_item['_source'] = 'remote_local'
                mapped_results.append(enhanced_item)
                
            elif show_nonlocal:
                # Item not in library but user wants to see non-local items
                remote_item['_mapped'] = False
                remote_item['_source'] = 'remote_only'
                remote_item['_not_in_library'] = True
                mapped_results.append(remote_item)
        
        return mapped_results


# Global service instance
_remote_service = None


def get_remote_service(settings_getter=None):
    """Get global remote service instance"""
    global _remote_service
    if _remote_service is None:
        _remote_service = RemoteService(settings_getter)
    return _remote_service