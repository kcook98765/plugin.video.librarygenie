#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - OTP Authentication
Handles OTP/pairing code exchange for API key authentication
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import time
import xbmc
import xbmcgui
from typing import Dict, Any, Optional

from ..config import get_config
from ..utils.logger import get_logger
from .state import save_api_key, get_api_key, clear_auth_data
# Import needed for post-OTP sync functionality
from ..remote.ai_search_client import get_ai_search_client

logger = get_logger(__name__)

# Global variables for rate limiting
_last_otp_attempt = 0
_otp_attempt_count = 0

def exchange_otp_for_api_key(otp_code: str, server_url: str) -> Dict[str, Any]:
    """
    Exchange OTP code for API key using the /pairing-code/exchange endpoint

    Args:
        otp_code: 8-digit OTP code from user
        server_url: Base URL of the AI search server

    Returns:
        dict: Result with success status and details
    """
    if not otp_code or len(otp_code.strip()) != 8:
        return {
            'success': False,
            'error': 'Invalid OTP code format (must be 8 characters)'
        }

    if not server_url:
        return {
            'success': False,
            'error': 'Server URL not configured'
        }

    # Simple rate limiting check
    global _last_otp_attempt, _otp_attempt_count
    current_time = time.time()

    if current_time - _last_otp_attempt < 60:  # Within last minute
        if _otp_attempt_count >= 3:  # 3 attempts per minute max
            return {
                'success': False,
                'error': 'Too many attempts. Please wait before trying again.'
            }
        _otp_attempt_count += 1
    else:
        _otp_attempt_count = 1  # Reset counter

    _last_otp_attempt = current_time

    try:
        exchange_url = f"{server_url.rstrip('/')}/pairing-code/exchange"
        # Sanitize OTP code before sending
        sanitized_otp = otp_code.strip()
        payload = {"pairing_code": sanitized_otp}

        logger.info(f"=== OTP EXCHANGE REQUEST ===")
        logger.info(f"URL: {exchange_url}")
        logger.info(f"Method: POST")
        logger.info(f"Headers: {{'Content-Type': 'application/json'}}")
        logger.info(f"Request payload: {json.dumps(payload, indent=2)}")

        # Prepare request
        json_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            exchange_url,
            data=json_data,
            headers={'Content-Type': 'application/json'}
        )

        # Make request
        with urllib.request.urlopen(req, timeout=10) as response:
            response_code = response.getcode()
            response_data = response.read().decode('utf-8')

            logger.info(f"=== OTP EXCHANGE RESPONSE ===")
            logger.info(f"Status Code: {response_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            logger.info(f"Response Body: {response_data}")

            if response_code == 200:
                data = json.loads(response_data)

                if data.get('success'):
                    # Extract and save API key
                    api_key = data.get('api_key')
                    user_email = data.get('user_email', 'Unknown')

                    if api_key:
                        save_api_key(api_key)
                        logger.info(f"API key obtained and saved successfully for user: {user_email}")
                        logger.info(f"=== OTP EXCHANGE SUCCESS ===")

                        return {
                            'success': True,
                            'api_key': api_key,
                            'user_email': user_email,
                            'message': data.get('message', 'Authorization successful')
                        }
                    else:
                        logger.error("Server response missing API key")
                        return {
                            'success': False,
                            'error': 'No API key in server response'
                        }
                else:
                    error_msg = data.get('error', 'Unknown error')
                    logger.error(f"Server rejected OTP: {error_msg}")
                    return {
                        'success': False,
                        'error': f'Server rejected OTP: {error_msg}'
                    }
            else:
                logger.error(f"HTTP error response: {response_code}")
                return {
                    'success': False,
                    'error': f'Server error: HTTP {response_code}'
                }

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
            logger.info(f"=== OTP EXCHANGE HTTP ERROR ===")
            logger.info(f"Status Code: {e.code}")
            logger.info(f"Error Headers: {dict(e.headers) if hasattr(e, 'headers') else 'N/A'}")
            logger.info(f"Error Body: {error_body}")

            error_data = json.loads(error_body)
            error_msg = error_data.get('error', f'HTTP {e.code} error')
        except Exception:
            error_msg = f'HTTP {e.code} error'

        logger.error(f"HTTP error during OTP exchange: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }

    except urllib.error.URLError as e:
        logger.error(f"Network error during OTP exchange: {e}")
        return {
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {e}")
        return {
            'success': False,
            'error': 'Invalid server response format'
        }

    except Exception as e:
        logger.error(f"Unexpected error during OTP exchange: {e}")
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


def test_api_connection(server_url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Test API connection using the /kodi/test endpoint

    Args:
        server_url: Base URL of the AI search server
        api_key: API key to test (uses stored key if None)

    Returns:
        dict: Test result with success status
    """
    if not api_key:
        api_key = get_api_key()

    if not api_key:
        return {
            'success': False,
            'error': 'No API key available'
        }

    if not server_url:
        return {
            'success': False,
            'error': 'Server URL not configured'
        }

    try:
        test_url = f"{server_url.rstrip('/')}/kodi/test"
        headers = {'Authorization': f'ApiKey {api_key}'}

        logger.info(f"=== API CONNECTION TEST REQUEST ===")
        logger.info(f"URL: {test_url}")
        logger.info(f"Method: GET")
        logger.info(f"Headers: {headers}")

        req = urllib.request.Request(test_url)
        req.add_header('Authorization', f'ApiKey {api_key}')

        with urllib.request.urlopen(req, timeout=10) as response:
            response_code = response.getcode()
            response_data = response.read().decode('utf-8')

            logger.info(f"=== API CONNECTION TEST RESPONSE ===")
            logger.info(f"Status Code: {response_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")
            logger.info(f"Response Body: {response_data}")

            if response_code == 200:
                data = json.loads(response_data)

                if data.get('status') == 'success':
                    user_info = data.get('user', {})
                    logger.info(f"=== API CONNECTION TEST SUCCESS ===")
                    logger.info(f"User: {user_info.get('email', 'Unknown')}")
                    logger.info(f"Role: {user_info.get('role', 'Unknown')}")
                    return {
                        'success': True,
                        'message': data.get('message', 'Connection successful'),
                        'user_email': user_info.get('email', 'Unknown'),
                        'user_role': user_info.get('role', 'Unknown')
                    }
                else:
                    logger.error(f"Server returned unsuccessful status: {data}")
                    return {
                        'success': False,
                        'error': 'Server returned unsuccessful status'
                    }
            else:
                logger.error(f"HTTP error response: {response_code}")
                return {
                    'success': False,
                    'error': f'Server error: HTTP {response_code}'
                }

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
            logger.info(f"=== API CONNECTION TEST HTTP ERROR ===")
            logger.info(f"Status Code: {e.code}")
            logger.info(f"Error Headers: {dict(e.headers) if hasattr(e, 'headers') else 'N/A'}")
            logger.info(f"Error Body: {error_body}")
        except Exception:
            error_body = 'Unable to read error body'

        if e.code == 401:
            error_msg = 'Invalid or expired API key'
        else:
            error_msg = f'HTTP {e.code} error'

        logger.error(f"HTTP error during API test: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }

    except Exception as e:
        logger.error(f"Error during API test: {e}")
        return {
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }


def run_otp_authorization_flow(server_url: str) -> bool:
    """
    Run the complete OTP authorization flow with user interaction

    Args:
        server_url: Base URL of the AI search server

    Returns:
        bool: True if authorization succeeded
    """
    logger.info("Starting OTP authorization flow")

    try:
        # Get OTP code from user
        dialog = xbmcgui.Dialog()
        otp_code = dialog.input(
            "Enter OTP Code",
            "Enter the 8-digit OTP code from the website:",
            type=xbmcgui.INPUT_NUMERIC
        )

        if not otp_code:
            logger.info("User cancelled OTP entry")
            return False

        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("AI Search Authorization", "Exchanging OTP code for API key...")

        try:
            # Exchange OTP for API key
            result = exchange_otp_for_api_key(otp_code, server_url)

            if result['success']:
                # Success - show confirmation
                dialog.ok(
                    "Authorization Complete",
                    f"AI Search activated successfully!\n\nUser: {result.get('user_email', 'Unknown')}"
                )

                # Trigger authoritative sync after successful OTP authentication
                try:
                    from ..data.list_library_manager import get_list_library_manager
                    library_manager = get_list_library_manager()
                    media_items = library_manager.get_all_items(limit=10000)

                    if media_items:
                        ai_client = get_ai_search_client()
                        sync_result = ai_client.sync_after_otp(media_items)
                        if sync_result and sync_result.get('success'):
                            logger.info(f"Post-OTP authoritative sync completed: {sync_result.get('results', {})}")
                        else:
                            logger.warning("Post-OTP sync failed, but authentication was successful")
                    else:
                        logger.info("No media items found, skipping post-OTP sync")

                except Exception as e:
                    logger.warning(f"Post-OTP sync failed but authentication succeeded: {e}")

                logger.info("OTP authorization flow completed successfully")
                return True
            else:
                # Failed - show error
                dialog.ok(
                    "Authorization Failed",
                    f"Failed to activate AI Search:\n\n{result['error']}"
                )

                logger.warning(f"OTP authorization failed: {result['error']}")
                return False

        finally:
            if progress:
                progress.close()

    except Exception as e:
        logger.error(f"Error in OTP authorization flow: {e}")
        xbmcgui.Dialog().ok(
            "Authorization Error",
            f"An unexpected error occurred:\n\n{str(e)[:100]}..."
        )
        return False


def is_api_key_valid(server_url: Optional[str] = None, api_key: Optional[str] = None) -> bool:
    """
    Check if the current API key is valid by testing the connection

    Args:
        server_url: Server URL (uses config if None)
        api_key: API key to test (uses stored key if None)

    Returns:
        bool: True if API key is valid
    """
    try:
        if not server_url:
            cfg = get_config()
            server_url = str(cfg.get('ai_search_server_url', ''))

        if not server_url:
            return False

        result = test_api_connection(server_url, api_key)
        return result.get('success', False)

    except Exception as e:
        logger.debug(f"API key validation failed: {e}")
        return False