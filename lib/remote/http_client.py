#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 12 Remote HTTP Client
Safe HTTP client wrapper with timeouts, retries, and error handling
"""

import json
import time
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from lib.utils.kodi_log import get_kodi_logger
from lib.config.settings import get_phase12_remote_settings


class RemoteHTTPClient:
    """Safe HTTP client for remote API integration"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, **options):
        self.logger = get_kodi_logger('lib.remote.http_client')
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        
        # Get settings with fallbacks
        settings = get_phase12_remote_settings()
        self.timeout = options.get('timeout', settings.get('remote_timeout_seconds', 10))
        self.retry_count = options.get('retry_count', settings.get('remote_retry_count', 2))
        self.rate_limit_ms = options.get('rate_limit_ms', settings.get('remote_rate_limit_ms', 100))
        self.log_requests = options.get('log_requests', settings.get('remote_log_requests', False))
        
        self._last_request_time = 0
    
    def health_check(self) -> Dict[str, Any]:
        """Check remote service health/connectivity"""
        try:
            response = self._make_request('GET', '/health')
            
            if response.get('success', True):
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'service_info': response.get('service', {}),
                    'response_time_ms': response.get('_response_time_ms', 0)
                }
            else:
                return {
                    'success': False,
                    'message': response.get('message', 'Health check failed'),
                    'error_code': response.get('error_code')
                }
                
        except Exception as e:
            self.logger.warning("Health check failed: %s", e)
            return {
                'success': False,
                'message': f"Connection failed: {str(e)}",
                'error_type': type(e).__name__
            }
    
    def search_movies(self, query: str, **params) -> Dict[str, Any]:
        """Search for movies on remote service"""
        try:
            # Build search parameters
            search_params = {
                'q': query,
                'type': 'movie',
                'limit': params.get('limit', 50)
            }
            
            # Add optional parameters
            if params.get('year'):
                search_params['year'] = params['year']
            if params.get('sort'):
                search_params['sort'] = params['sort']
            
            response = self._make_request('GET', '/search', params=search_params)
            
            if response.get('success', True):
                return {
                    'success': True,
                    'results': response.get('results', []),
                    'total': response.get('total', 0),
                    'page': response.get('page', 1),
                    'has_more': response.get('has_more', False)
                }
            else:
                return {
                    'success': False,
                    'message': response.get('message', 'Search failed'),
                    'results': []
                }
                
        except Exception as e:
            self.logger.error("Remote search failed: %s", e)
            return {
                'success': False,
                'message': f"Search error: {str(e)}",
                'results': []
            }
    
    def get_remote_lists(self) -> Dict[str, Any]:
        """Get list of available remote lists"""
        try:
            response = self._make_request('GET', '/lists')
            
            if response.get('success', True):
                return {
                    'success': True,
                    'lists': response.get('lists', [])
                }
            else:
                return {
                    'success': False,
                    'message': response.get('message', 'Failed to fetch lists'),
                    'lists': []
                }
                
        except Exception as e:
            self.logger.error("Failed to get remote lists: %s", e)
            return {
                'success': False,
                'message': f"Lists error: {str(e)}",
                'lists': []
            }
    
    def get_list_contents(self, list_id: str, **params) -> Dict[str, Any]:
        """Get contents of a specific remote list"""
        try:
            list_params = {
                'limit': params.get('limit', 100),
                'offset': params.get('offset', 0)
            }
            
            response = self._make_request('GET', f'/lists/{list_id}', params=list_params)
            
            if response.get('success', True):
                return {
                    'success': True,
                    'list_info': response.get('list_info', {}),
                    'items': response.get('items', []),
                    'total': response.get('total', 0),
                    'has_more': response.get('has_more', False)
                }
            else:
                return {
                    'success': False,
                    'message': response.get('message', 'Failed to fetch list contents'),
                    'items': []
                }
                
        except Exception as e:
            self.logger.error("Failed to get list contents for %s: %s", list_id, e)
            return {
                'success': False,
                'message': f"List contents error: {str(e)}",
                'items': []
            }
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request with retries and error handling"""
        
        # Rate limiting
        self._enforce_rate_limit()
        
        # Build URL
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        if params:
            url += '?' + urlencode(params)
        
        # Prepare request
        request = Request(url)
        request.add_header('User-Agent', 'LibraryGenie/1.0')
        request.add_header('Accept', 'application/json')
        
        # Add authentication if available
        if self.api_key:
            request.add_header('Authorization', f'Bearer {self.api_key}')
        
        # Add request body for POST/PUT
        if data:
            request.add_header('Content-Type', 'application/json')
            request.data = json.dumps(data).encode('utf-8')
        
        if self.log_requests:
            self.logger.debug("Remote request: %s %s", method, url)
        
        # Make request with retries
        last_error = None
        start_time = time.time()
        
        for attempt in range(self.retry_count + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    response_data = response.read().decode('utf-8')
                    
                    # Parse JSON response
                    try:
                        result = json.loads(response_data)
                    except json.JSONDecodeError:
                        # If not JSON, wrap in success response
                        result = {'success': True, 'data': response_data}
                    
                    # Add response time
                    result['_response_time_ms'] = int((time.time() - start_time) * 1000)
                    
                    if self.log_requests:
                        self.logger.debug("Remote response: %s (%sms)", response.status, result.get('_response_time_ms'))
                    
                    return result
                    
            except HTTPError as e:
                last_error = e
                if e.code >= 400 and e.code < 500:
                    # Client error - don't retry
                    break
                self.logger.warning("HTTP error on attempt %s: %s", attempt + 1, e)
                
            except (URLError, OSError) as e:
                last_error = e
                self.logger.warning("Network error on attempt %s: %s", attempt + 1, e)
                
            # Wait before retry (except on last attempt)
            if attempt < self.retry_count:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        error_msg = f"Request failed after {self.retry_count + 1} attempts: {last_error}"
        self.logger.error(error_msg)
        
        return {
            'success': False,
            'error': str(last_error),
            'error_type': type(last_error).__name__,
            'attempts': self.retry_count + 1
        }
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests"""
        if self.rate_limit_ms > 0:
            elapsed = (time.time() - self._last_request_time) * 1000
            if elapsed < self.rate_limit_ms:
                sleep_time = (self.rate_limit_ms - elapsed) / 1000
                time.sleep(sleep_time)
        
        self._last_request_time = time.time()


def get_remote_client(base_url: str, api_key: Optional[str] = None, **options) -> Optional[RemoteHTTPClient]:
    """Factory function to create a remote HTTP client"""
    if not base_url:
        return None
    
    try:
        return RemoteHTTPClient(base_url, api_key, **options)
    except Exception as e:
        logger = get_kodi_logger('lib.remote.http_client')
        logger.error("Failed to create remote client: %s", e)
        return None