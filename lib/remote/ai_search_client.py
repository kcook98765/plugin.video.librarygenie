
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - AI Search Client
Handles AI search server authentication and requests using OTP-based auth
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional

from ..config.settings import SettingsManager
from ..utils.logger import get_logger
from ..auth.state import is_authorized, get_api_key
from ..auth.otp_auth import exchange_otp_for_api_key, test_api_connection


class AISearchClient:
    """Client for AI search server integration using OTP authentication"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = SettingsManager()
    
    def is_configured(self) -> bool:
        """Check if AI search is properly configured"""
        return bool(
            self.settings.get_ai_search_server_url() and 
            is_authorized()
        )
    
    def is_activated(self) -> bool:
        """Check if AI search is activated (has valid API key)"""
        return is_authorized()
    
    def activate_with_otp(self, otp_code: str) -> Dict[str, Any]:
        """
        Activate AI search using OTP code
        
        Args:
            otp_code: 8-digit OTP code
            
        Returns:
            dict: Result with success status and details
        """
        server_url = self.settings.get_ai_search_server_url()
        if not server_url:
            return {
                'success': False,
                'error': 'Server URL not configured'
            }
        
        try:
            # Use the new OTP auth system
            result = exchange_otp_for_api_key(otp_code, server_url)
            
            if result['success']:
                # Update settings to reflect activation
                self.settings.set_ai_search_activated(True)
                self.settings.set_ai_search_otp_code("")  # Clear OTP code
                
                self.logger.info("AI Search activated successfully via OTP")
                
                return {
                    'success': True,
                    'user_email': result.get('user_email', 'Unknown'),
                    'message': result.get('message', 'AI Search activated successfully')
                }
            else:
                return result
                
        except Exception as e:
            self.logger.error(f"Unexpected error during AI search activation: {e}")
            return {
                'success': False,
                'error': f'Activation failed: {str(e)}'
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the AI search server connection
        
        Returns:
            dict: Connection test result
        """
        server_url = self.settings.get_ai_search_server_url()
        if not server_url:
            return {
                'success': False,
                'error': 'Server URL not configured'
            }
        
        if not is_authorized():
            return {
                'success': False,
                'error': 'No API key available'
            }
        
        try:
            return test_api_connection(server_url)
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }
    
    def search(self, query: str, **params) -> Dict[str, Any]:
        """
        Perform AI search query using the /kodi/search/movies endpoint
        
        Args:
            query: Search query string
            **params: Additional search parameters (limit, etc.)
            
        Returns:
            dict: Search results
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'AI search not configured or activated',
                'results': []
            }
        
        server_url = self.settings.get_ai_search_server_url()
        api_key = get_api_key()
        
        if not query or not query.strip():
            return {
                'success': False,
                'error': 'Search query is required',
                'results': []
            }
        
        try:
            search_url = f"{server_url.rstrip('/')}/kodi/search/movies"
            
            # Prepare search payload
            payload = {
                'query': query.strip(),
                'limit': params.get('limit', 20)
            }
            
            # Make request
            json_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                search_url,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'ApiKey {api_key}'
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.getcode() == 200:
                    response_data = response.read().decode('utf-8')
                    data = json.loads(response_data)
                    
                    if data.get('success'):
                        self.logger.info(f"AI search returned {data.get('total_results', 0)} results")
                        return data
                    else:
                        return {
                            'success': False,
                            'error': data.get('error', 'Search failed'),
                            'results': []
                        }
                else:
                    return {
                        'success': False,
                        'error': f'Server error: HTTP {response.getcode()}',
                        'results': []
                    }
                    
        except urllib.error.HTTPError as e:
            if e.code == 401:
                error_msg = 'Authentication failed - API key may be invalid'
            else:
                error_msg = f'Server error: HTTP {e.code}'
            
            self.logger.error(f"HTTP error during AI search: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'results': []
            }
            
        except urllib.error.URLError as e:
            self.logger.error(f"Network error during AI search: {e}")
            return {
                'success': False,
                'error': f'Connection failed: {str(e)}',
                'results': []
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response from AI search: {e}")
            return {
                'success': False,
                'error': 'Invalid server response',
                'results': []
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected error during AI search: {e}")
            return {
                'success': False,
                'error': f'Search failed: {str(e)}',
                'results': []
            }


def get_ai_search_client() -> AISearchClient:
    """Factory function to get AI search client"""
    return AISearchClient()
