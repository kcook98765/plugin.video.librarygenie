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
from typing import Dict, Any, Optional, List

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

    def search(self, query: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Perform AI-powered search

        Args:
            query: Search query string
            **kwargs: Additional search parameters

        Returns:
            Search results or None if search fails
        """
        if not self.is_activated():
            self.logger.warning("AI search not activated - cannot perform search")
            return None

        try:
            # Prepare search request
            search_data = {
                'query': query,
                'limit': kwargs.get('limit', 50),
                'offset': kwargs.get('offset', 0)
            }

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in ['limit', 'offset']:
                    search_data[key] = value

            # Make search request
            response = self.http_client.post('/search', search_data)

            if response and response.get('success'):
                self.logger.info(f"AI search completed: {len(response.get('results', []))} results")
                return response
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response'
                self.logger.error(f"AI search failed: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Error performing AI search: {e}")
            return None

    def sync_media_batch(self, media_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Sync a batch of media items with the AI search server

        Args:
            media_items: List of media item dictionaries with imdb_id, title, year, media_type

        Returns:
            Sync result or None if sync fails
        """
        if not self.is_activated():
            self.logger.warning("AI search not activated - cannot perform sync")
            return None

        try:
            # Prepare sync request
            sync_data = {
                'media_items': media_items,
                'sync_type': 'batch'
            }

            # Make sync request
            response = self.http_client.post('/sync', sync_data)

            if response and response.get('success'):
                synced_count = response.get('synced_count', len(media_items))
                self.logger.debug(f"Media batch sync completed: {synced_count} items synced")
                return response
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response'
                self.logger.warning(f"Media batch sync failed: {error_msg}")
                return response  # Return response even on failure for error handling

        except Exception as e:
            self.logger.error(f"Error performing media batch sync: {e}")
            return None


def get_ai_search_client() -> AISearchClient:
    """Factory function to get AI search client"""
    return AISearchClient()