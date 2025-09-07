
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - AI Search Client
Handles AI search server authentication and requests
"""

import json
import requests
from typing import Dict, Any, Optional
from ..config.settings import SettingsManager
from ..utils.logger import get_logger


class AISearchClient:
    """Client for AI search server integration"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = SettingsManager()
    
    def is_configured(self) -> bool:
        """Check if AI search is properly configured"""
        return bool(
            self.settings.get_ai_search_server_url() and 
            self.settings.get_ai_search_activated()
        )
    
    def is_activated(self) -> bool:
        """Check if AI search is activated"""
        return self.settings.get_ai_search_activated()
    
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
        
        if not otp_code or len(otp_code) != 8:
            return {
                'success': False,
                'error': 'Invalid OTP code format'
            }
        
        try:
            exchange_url = f"{server_url.rstrip('/')}/pairing-code/exchange"
            payload = {"pairing_code": otp_code}
            
            self.logger.info(f"Attempting OTP exchange at: {exchange_url}")
            
            response = requests.post(
                exchange_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Store credentials
                    api_key = data.get('api_key')
                    user_email = data.get('user_email', 'Unknown')
                    
                    self.settings.set_ai_search_api_key(api_key)
                    self.settings.set_ai_search_activated(True)
                    self.settings.set_ai_search_otp_code("")  # Clear OTP
                    
                    return {
                        'success': True,
                        'user_email': user_email,
                        'message': 'AI Search activated successfully'
                    }
                else:
                    error_msg = data.get('error', 'Unknown error')
                    return {
                        'success': False,
                        'error': f'Activation failed: {error_msg}'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Server error: {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timed out'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Connection failed: {str(e)}'
            }
        except Exception as e:
            self.logger.error(f"Unexpected error during AI search activation: {e}")
            return {
                'success': False,
                'error': 'An unexpected error occurred'
            }
    
    def search(self, query: str, **params) -> Dict[str, Any]:
        """
        Perform AI search query
        
        Args:
            query: Search query string
            **params: Additional search parameters
            
        Returns:
            dict: Search results
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'AI search not configured or activated',
                'results': []
            }
        
        # TODO: Implement actual search functionality
        # This would make authenticated requests to the AI search server
        return {
            'success': False,
            'error': 'Search functionality not yet implemented',
            'results': []
        }


def get_ai_search_client() -> AISearchClient:
    """Factory function to get AI search client"""
    return AISearchClient()
