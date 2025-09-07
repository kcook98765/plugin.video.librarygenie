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

        logger.info(f"Attempting OTP exchange at: {exchange_url}")

        # Prepare request
        json_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            exchange_url,
            data=json_data,
            headers={'Content-Type': 'application/json'}
        )

        # Make request
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() == 200:
                response_data = response.read().decode('utf-8')
                data = json.loads(response_data)

                if data.get('success'):
                    # Extract and save API key
                    api_key = data.get('api_key')
                    user_email = data.get('user_email', 'Unknown')

                    if api_key:
                        save_api_key(api_key)
                        logger.info("API key obtained and saved successfully")

                        return {
                            'success': True,
                            'api_key': api_key,
                            'user_email': user_email,
                            'message': data.get('message', 'Authorization successful')
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'No API key in server response'
                        }
                else:
                    error_msg = data.get('error', 'Unknown error')
                    return {
                        'success': False,
                        'error': f'Server rejected OTP: {error_msg}'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Server error: HTTP {response.getcode()}'
                }

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
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


def test_api_connection(server_url: str, api_key: str = None) -> Dict[str, Any]:
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

        req = urllib.request.Request(test_url)
        req.add_header('Authorization', f'ApiKey {api_key}')

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() == 200:
                response_data = response.read().decode('utf-8')
                data = json.loads(response_data)

                if data.get('status') == 'success':
                    user_info = data.get('user', {})
                    return {
                        'success': True,
                        'message': data.get('message', 'Connection successful'),
                        'user_email': user_info.get('email', 'Unknown'),
                        'user_role': user_info.get('role', 'Unknown')
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Server returned unsuccessful status'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Server error: HTTP {response.getcode()}'
                }

    except urllib.error.HTTPError as e:
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

            progress.close()

            if result['success']:
                # Success - show confirmation
                dialog.ok(
                    "Authorization Complete",
                    f"AI Search activated successfully!\n\nUser: {result.get('user_email', 'Unknown')}"
                )

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


def is_api_key_valid(server_url: str = None, api_key: str = None) -> bool:
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
            server_url = cfg.get('ai_search_server_url', '')

        if not server_url:
            return False

        result = test_api_connection(server_url, api_key)
        return result.get('success', False)

    except Exception as e:
        logger.debug(f"API key validation failed: {e}")
        return False