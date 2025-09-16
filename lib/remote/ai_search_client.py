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
import time
from typing import Dict, Any, Optional, List

from lib.config.settings import SettingsManager
from lib.utils.kodi_log import get_kodi_logger
from lib.auth.state import is_authorized, get_api_key
# Removed import of otp_auth to resolve circular dependency
# from ..auth.otp_auth import exchange_otp_for_api_key, test_api_connection


class AISearchClient:
    """Client for AI search server integration using OTP authentication"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.remote.ai_search_client')
        self.settings = SettingsManager()
        # Initialize attributes
        self._api_key: Optional[str] = get_api_key()
        self._is_activated: bool = is_authorized()


    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Get standard headers for API requests"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'LibraryGenie-Kodi/1.0'
        }

        api_key = get_api_key()
        if api_key:
            headers['Authorization'] = f'ApiKey {api_key}'

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _make_public_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None,
                            headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Make HTTP request to AI search server without authentication (for public endpoints)"""
        server_url = self.settings.get_remote_server_url()
        if not server_url:
            self.logger.error("No server URL configured")
            return None

        url = f"{server_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # Log the complete URL for endpoint verification
        self.logger.info("🌐 PUBLIC API REQUEST: %s %s", method, url)

        # Use minimal headers for public endpoints
        request_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'LibraryGenie-Kodi/1.0'
        }

        if headers:
            request_headers.update(headers)

        try:
            # Prepare request data
            json_data = None
            if data:
                json_data = json.dumps(data).encode('utf-8')

            # Create request
            req = urllib.request.Request(url, data=json_data, headers=request_headers)
            req.get_method = lambda: method

            # Make request with configurable timeout
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.getcode() == 200:
                    response_data = response.read().decode('utf-8')
                    return json.loads(response_data)
                else:
                    self.logger.error("HTTP %s from %s", response.getcode(), endpoint)
                    return None

        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8')
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', 'Unknown')
                self.logger.error("HTTP %s error: %s", e.code, error_msg)
                return {'error': error_msg}
            except:
                self.logger.error("HTTP %s error from %s", e.code, endpoint)
                return {'error': f'HTTP {e.code} error'}

        except urllib.error.URLError as e:
            self.logger.error("Network error: %s", e)
            return {'error': f'Network error: {str(e)}'}

        except Exception as e:
            self.logger.error("Request failed: %s", e)
            return {'error': f'Request failed: {str(e)}'}

    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None,
                     headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Make HTTP request to AI search server"""
        server_url = self.settings.get_remote_server_url()
        if not server_url:
            self.logger.error("No server URL configured")
            return None

        url = f"{server_url.rstrip('/')}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers(headers)

        # Log the complete URL for endpoint verification
        self.logger.info("🌐 API REQUEST: %s %s", method, url)

        try:
            # Prepare request data
            json_data = None
            if data:
                json_data = json.dumps(data).encode('utf-8')

            # Create request
            req = urllib.request.Request(url, data=json_data, headers=request_headers)
            req.get_method = lambda: method

            # Make request with configurable timeout
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.getcode() == 200:
                    response_data = response.read().decode('utf-8')
                    return json.loads(response_data)
                elif response.getcode() == 304:
                    return {'_not_modified': True}
                else:
                    self.logger.error("HTTP %s from %s", response.getcode(), endpoint)
                    return None

        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8')
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', 'Unknown')

                # Handle API key expiration/invalidation
                if e.code == 401:
                    self.logger.warning("API key appears to be invalid/expired")
                    # Clear invalid API key to prevent repeated failed requests
                    from lib.auth.state import clear_auth_data
                    clear_auth_data()

                self.logger.error("HTTP %s error: %s", e.code, error_msg)
                return {'error': error_msg}
            except:
                self.logger.error("HTTP %s error from %s", e.code, endpoint)
                return {'error': f'HTTP {e.code} error'}

        except urllib.error.URLError as e:
            self.logger.error("Network error: %s", e)
            return {'error': f'Network error: {str(e)}'}

        except Exception as e:
            self.logger.error("Request failed: %s", e)
            return {'error': f'Request failed: {str(e)}'}

    def is_configured(self) -> bool:
        """Check if AI search is properly configured"""
        return bool(
            self.settings.get_remote_server_url() and
            is_authorized()
        )

    def is_activated(self) -> bool:
        """Check if AI search is activated (has valid API key)"""
        return is_authorized()

    def activate_with_otp(self, otp_code: str) -> Dict[str, Any]:
        """
        Activate AI search using OTP code with replace sync

        Args:
            otp_code: 8-digit OTP code from website

        Returns:
            Dict with success status and details
        """
        try:
            # Exchange OTP for API key directly using HTTP client
            result = self._exchange_otp_for_api_key_direct(otp_code)

            if result.get('success'):
                # Store the API key
                api_key = result.get('api_key')
                user_email = result.get('user_email', '')

                if api_key:
                    from lib.auth.state import save_api_key
                    save_api_key(api_key)

                    # Update internal state
                    self._api_key = api_key
                    self._is_activated = True

                    self.logger.info("AI SEARCH: Successfully activated with OTP for user: %s", user_email)

                    # Trigger replace sync after successful activation
                    self._trigger_post_activation_sync()

                    return {
                        'success': True,
                        'user_email': user_email,
                        'message': 'AI Search activated successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'No API key received from server'
                    }
            else:
                return result

        except Exception as e:
            self.logger.error("AI SEARCH: Error in OTP activation: %s", e)
            return {
                'success': False,
                'error': f'Activation failed: {str(e)}'
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the AI search server connection using /kodi/test endpoint

        Returns:
            dict: Connection test result
        """
        server_url = self.settings.get_remote_server_url()
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
            # Test connection by making a request to the kodi/test endpoint
            response = self._make_request('kodi/test', 'GET', timeout=10)
            
            if response and response.get('status') == 'success':
                user_info = response.get('user', {})
                return {
                    'success': True,
                    'message': response.get('message', 'Connection successful'),
                    'user_email': user_info.get('email', 'Unknown'),
                    'service': response.get('service', 'Unknown')
                }
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response'
                return {
                    'success': False,
                    'error': f'Connection test failed: {error_msg}'
                }

        except Exception as e:
            self.logger.error("Connection test failed: %s", e)
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }

    def search_movies(self, query: str, limit: int = 50) -> Optional[Dict[str, Any]]:
        """
        Perform AI-powered movie search using /kodi/search/movies endpoint

        Args:
            query: Search query string
            limit: Maximum number of results (default: 50, max: 100)

        Returns:
            Search results or None if search fails
        """
        if not self.is_activated():
            self.logger.warning("AI search not activated - cannot perform search")
            return None

        try:
            search_data = {
                'query': query,
                'limit': min(limit, 100)
            }

            response = self._make_request('kodi/search/movies', 'POST', search_data)

            if response and response.get('success'):
                # Validate response structure
                results = response.get('results', [])
                if not isinstance(results, list):
                    self.logger.error("Invalid response format: results is not a list")
                    return None

                self.logger.info("AI search completed: %s results", len(results))
                return response
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response'
                self.logger.error("AI search failed: %s", error_msg)
                return None

        except Exception as e:
            self.logger.error("Error performing AI search: %s", e)
            return None

    def get_library_version(self) -> Optional[Dict[str, Any]]:
        """
        Get current library hash for delta sync using Main API

        Returns:
            Library hash info or None if request fails
        """
        if not self.is_activated():
            return None

        try:
            response = self._make_request('library/hash', 'GET')
            if response and response.get('success'):
                return response
            return None

        except Exception as e:
            self.logger.error("Error getting library hash: %s", e)
            return None

    def sync_media_batch(self, media_items: List[Dict[str, Any]], batch_size: int = 500, use_replace_mode: bool = False, progress_callback=None) -> Optional[Dict[str, Any]]:
        """
        Sync a batch of media items with the AI search server using Main API

        Args:
            media_items: List of media item dictionaries with imdb_id
            batch_size: Items per chunk (max 1000)
            use_replace_mode: If True, use "replace" mode for authoritative sync
            progress_callback: Optional callback function(current, total, message) for progress updates

        Returns:
            Sync result or None if sync fails
        """
        if not self.is_activated():
            self.logger.warning("AI search not activated - cannot perform sync")
            return None

        if not media_items:
            return {'success': True, 'results': {'accepted': 0, 'duplicates': 0, 'invalid': 0}}

        try:
            # Extract IMDb IDs from media items
            imdb_ids = []
            for item in media_items:
                imdb_id = item.get('imdb_id')
                if imdb_id and imdb_id.startswith('tt'):
                    imdb_ids.append(imdb_id)

            if not imdb_ids:
                self.logger.warning("No valid IMDb IDs found in media items")
                return {'success': False, 'error': 'No valid IMDb IDs found'}

            # Start batch upload session
            sync_mode = 'replace' if use_replace_mode else 'merge'
            batch_start_data = {
                'mode': sync_mode,
                'total_count': len(imdb_ids),
                'source': 'kodi'
            }

            self.logger.info("Starting batch sync in '%s' mode with %s items", sync_mode, len(imdb_ids))
            start_response = self._make_request('library/batch/start', 'POST', batch_start_data)
            if not start_response or not start_response.get('success'):
                error_msg = start_response.get('error', 'Failed to start batch session') if start_response else 'No response'
                self.logger.error("Failed to start batch upload session: %s", error_msg)
                return {'success': False, 'error': error_msg}

            # Get upload_id from start response
            upload_id = start_response.get('upload_id')
            if not upload_id:
                self.logger.error("No upload_id received from batch start")
                return {'success': False, 'error': 'No upload_id in start response'}

            # Validate and adjust chunk size according to API limits
            chunk_size = min(max(batch_size, 1), 1000)  # Main API max chunk size is 1000
            results = {
                'accepted': 0,
                'duplicates': 0,
                'invalid': 0
            }

            chunk_index = 0
            total_chunks = (len(imdb_ids) + chunk_size - 1) // chunk_size
            
            for i in range(0, len(imdb_ids), chunk_size):
                chunk_imdb_ids = imdb_ids[i:i + chunk_size]

                # Update progress if callback provided
                if progress_callback:
                    progress_callback(chunk_index, total_chunks, f"Uploading batch {chunk_index + 1}/{total_chunks}")

                # Prepare chunk data
                chunk_items = [{'imdb_id': imdb_id} for imdb_id in chunk_imdb_ids]
                chunk_data = {
                    'chunk_index': chunk_index,
                    'items': chunk_items
                }

                # Generate idempotency key for this chunk
                import uuid
                idempotency_key = str(uuid.uuid4())

                # Upload chunk using Main API
                response = self._make_request(
                    f'library/batch/{upload_id}/chunk',
                    'PUT',
                    chunk_data,
                    {'Idempotency-Key': idempotency_key}
                )

                if response and response.get('success'):
                    chunk_results = response.get('results', {})
                    results['accepted'] += chunk_results.get('accepted', 0)
                    results['duplicates'] += chunk_results.get('duplicates', 0)
                    results['invalid'] += chunk_results.get('invalid', 0)

                    self.logger.debug("Uploaded chunk %s: %s", chunk_index + 1, chunk_results)

                    # Rate limiting - wait between chunks
                    if i + chunk_size < len(imdb_ids):
                        time.sleep(1)  # 1 second wait between chunks

                else:
                    error_msg = response.get('error', 'Unknown error') if response else 'No response'
                    self.logger.warning("Chunk upload failed: %s", error_msg)

                    # For certain errors, continue with next chunk instead of failing completely
                    if 'rate limit' in error_msg.lower() or 'timeout' in error_msg.lower():
                        self.logger.info("Recoverable error, continuing with next chunk after delay")
                        time.sleep(30)  # Extended delay for rate limits
                        continue

                    return {'success': False, 'error': error_msg}

                chunk_index += 1

            # Commit the batch - REQUIRED for replace-sync operations            
            self.logger.info("Committing batch upload for %s", upload_id)
            commit_response = self._make_request(f'library/batch/{upload_id}/commit', 'POST')
            
            if not commit_response or not commit_response.get('success'):
                error_msg = commit_response.get('error', 'Failed to commit batch') if commit_response else 'No response'
                self.logger.error("Failed to commit batch: %s", error_msg)
                return {'success': False, 'error': f'Commit failed: {error_msg}'}

            # Get final results from commit response
            final_tallies = commit_response.get('final_tallies', results)
            user_movie_count = commit_response.get('user_movie_count', 0)
            removed_count = commit_response.get('removed_count', 0)

            self.logger.info("Media batch sync completed: %s", final_tallies)
            if use_replace_mode and removed_count > 0:
                self.logger.info("Replace sync removed %s movies not in current batch", removed_count)

            return {
                'success': True,
                'results': final_tallies,
                'total_processed': len(imdb_ids),
                'user_movie_count': user_movie_count,
                'removed_count': removed_count if use_replace_mode else 0
            }

        except Exception as e:
            self.logger.error("Error performing media batch sync: %s", e)
            return {'success': False, 'error': f'Sync failed: {str(e)}'}

    def get_library_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive library statistics

        Returns:
            Statistics or None if request fails
        """
        if not self.is_activated():
            return None

        try:
            response = self._make_request('users/me/library/stats', 'GET')
            if response and response.get('success'):
                return response.get('stats')
            return None

        except Exception as e:
            self.logger.error("Error getting library stats: %s", e)
            return None

    def search_similar_movies(self, reference_imdb_id: str, facets: Dict[str, bool]) -> Optional[List[str]]:
        """
        Find movies similar to reference movie using /similar_to endpoint
        Note: This is a public endpoint that doesn't require authentication

        Args:
            reference_imdb_id: IMDb ID of reference movie
            facets: Dict with keys: plot, mood, themes, genre (all bool)

        Returns:
            List of similar IMDb IDs or None if failed
        """
        try:
            # Validate inputs
            if not reference_imdb_id or not reference_imdb_id.startswith('tt'):
                self.logger.error("Invalid IMDb ID format")
                return None

            # Build request data
            request_data = {
                'reference_imdb_id': reference_imdb_id,
                'include_plot': facets.get('plot', False),
                'include_mood': facets.get('mood', False),
                'include_themes': facets.get('themes', False),
                'include_genre': facets.get('genre', False)
            }

            # Ensure at least one facet is enabled
            if not any(request_data[key] for key in ['include_plot', 'include_mood', 'include_themes', 'include_genre']):
                self.logger.warning("No facets selected for similarity search")
                return None

            # Make request without authentication (public endpoint)
            response = self._make_public_request('similar_to', 'POST', request_data)

            if response and response.get('success'):
                results = response.get('results', [])
                self.logger.info("Found %s similar movies for %s", len(results), reference_imdb_id)
                return results

            return None

        except Exception as e:
            self.logger.error("Error finding similar movies: %s", e)
            return None

    def _trigger_post_activation_sync(self):
        """Internal method to trigger post-activation sync operations."""
        self.logger.info("AI SEARCH: Triggering post-activation sync...")
        # This method would typically perform a full library sync or other setup tasks.
        # For this example, we'll just log that it's being called.
        pass # Placeholder for actual sync logic

    # Added direct OTP exchange method to avoid circular import
    def _exchange_otp_for_api_key_direct(self, otp_code: str) -> Dict[str, Any]:
        """
        Exchange OTP code for API key directly (avoiding circular import)

        Args:
            otp_code: 8-digit OTP code

        Returns:
            Dict with success status and API key details
        """
        try:
            if not otp_code or len(otp_code.strip()) != 8:
                return {
                    'success': False,
                    'error': 'OTP code must be exactly 8 characters'
                }

            otp_code = otp_code.strip().upper()

            # Make request to exchange OTP for API key
            # Note: This requires 'requests' library. Ensure it's installed.
            # If 'requests' is not available, this method will fail.
            try:
                import requests
                http_client = requests
            except ImportError:
                self.logger.error("The 'requests' library is required for direct OTP exchange.")
                return {
                    'success': False,
                    'error': 'Missing required library: requests'
                }

            server_url = self.settings.get_remote_server_url()
            if not server_url:
                return {
                    'success': False,
                    'error': 'Server URL not configured'
                }
            
            endpoint = f"{server_url.rstrip('/')}/otp/exchange"
            payload = {'otp_code': otp_code}

            self.logger.info("OTP EXCHANGE: Attempting to exchange OTP code at %s", endpoint)

            # Use the imported requests library
            response = http_client.post(endpoint, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()

                if data.get('success'):
                    api_key = data.get('api_key')
                    user_email = data.get('user_email', '')

                    self.logger.info("OTP EXCHANGE: Successfully exchanged OTP for API key")

                    return {
                        'success': True,
                        'api_key': api_key,
                        'user_email': user_email
                    }
                else:
                    error_msg = data.get('error', 'Unknown error from server')
                    self.logger.error("OTP EXCHANGE: Server returned error: %s", error_msg)
                    return {
                        'success': False,
                        'error': error_msg
                    }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', error_msg)
                except:
                    pass # If response is not JSON, keep the HTTP status code error message

                self.logger.error("OTP EXCHANGE: HTTP error %s: %s", response.status_code, error_msg)
                return {
                    'success': False,
                    'error': f'Server error: {error_msg}'
                }

        except Exception as e:
            self.logger.error("OTP EXCHANGE: Exception during OTP exchange: %s", e)
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }

def get_ai_search_client() -> AISearchClient:
    """Factory function to get AI search client"""
    return AISearchClient()