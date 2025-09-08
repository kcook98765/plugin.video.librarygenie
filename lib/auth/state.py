#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Authentication State Management
Simplified state management for API key authentication
"""

from typing import Optional, Dict, Any
from datetime import datetime

from ..data.connection_manager import get_connection_manager
from ..utils.logger import get_logger

# Import xbmcaddon for addon settings
try:
    import xbmcaddon
except ImportError:
    # Mock xbmcaddon if not running in Kodi environment
    class MockAddon:
        def __init__(self):
            self._settings = {}

        def getSetting(self, key):
            return self._settings.get(key, '')

        def setSetting(self, key, value):
            self._settings[key] = value
    xbmcaddon = type('xbmcaddon', (object,), {'Addon': MockAddon})()


logger = get_logger(__name__)


def is_authorized() -> bool:
    """Check if the device has a valid API key"""
    try:
        api_key = get_api_key()
        return bool(api_key and api_key.strip())
    except Exception as e:
        logger.debug(f"Authorization check failed: {e}")
        return False


def get_api_key() -> Optional[str]:
    """Get the stored API key"""
    try:
        conn_manager = get_connection_manager()

        result = conn_manager.execute_single("""
            SELECT api_key 
            FROM auth_state 
            ORDER BY id DESC 
            LIMIT 1
        """)

        if result and result.get('api_key'):
            logger.debug("API key retrieved successfully")
            return result['api_key']
        else:
            logger.debug("No API key found")
            return None

    except Exception as e:
        logger.error(f"Failed to get API key: {e}")
        return None


def save_api_key(api_key: str) -> bool:
    """
    Save API key to database

    Args:
        api_key: The API key to save

    Returns:
        bool: True if saved successfully
    """
    try:
        if not api_key or not api_key.strip():
            logger.error("Cannot save empty API key")
            return False

        conn_manager = get_connection_manager()

        with conn_manager.transaction() as conn:
            # Clear any existing auth data
            conn.execute("DELETE FROM auth_state")

            # Insert new API key
            conn.execute("""
                INSERT INTO auth_state (api_key, created_at, token_type)
                VALUES (?, ?, ?)
            """, [
                api_key.strip(),
                datetime.now().isoformat(),
                'ApiKey'
            ])

        logger.info("API key saved successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to save API key: {e}")
        return False


def save_tokens(api_key: Optional[str] = None, access_token: Optional[str] = None, refresh_token: Optional[str] = None, expires_at: Optional[str] = None) -> bool:
    """Save authentication tokens to addon settings"""
    try:
        addon = xbmcaddon.Addon()

        if api_key is not None:
            addon.setSetting('api_key', api_key)
        if access_token is not None:
            addon.setSetting('access_token', access_token)
        if refresh_token is not None:
            addon.setSetting('refresh_token', refresh_token)
        if expires_at is not None:
            addon.setSetting('token_expires_at', expires_at)

        logger.debug("Authentication tokens saved")
        return True

    except Exception as e:
        logger.error(f"Error saving tokens: {e}")
        return False


def get_tokens() -> Dict[str, str]:
    """Get all stored authentication tokens"""
    try:
        addon = xbmcaddon.Addon()
        
        return {
            'api_key': addon.getSetting('api_key'),
            'access_token': addon.getSetting('access_token'),
            'refresh_token': addon.getSetting('refresh_token'),
            'expires_at': addon.getSetting('token_expires_at')
        }

    except Exception as e:
        logger.error(f"Error getting tokens: {e}")
        return {
            'api_key': '',
            'access_token': '',
            'refresh_token': '',
            'expires_at': ''
        }


def clear_tokens() -> bool:
    """Clear stored authentication tokens"""
    try:
        addon = xbmcaddon.Addon()
        addon.setSetting('api_key', '')
        addon.setSetting('refresh_token', '')
        addon.setSetting('access_token', '')
        addon.setSetting('token_expires_at', '')

        logger.info("Authentication tokens cleared")
        return True

    except Exception as e:
        logger.error(f"Error clearing tokens: {e}")
        return False


def clear_auth_data() -> bool:
    """Clear all stored authentication data"""
    try:
        conn_manager = get_connection_manager()

        with conn_manager.transaction() as conn:
            conn.execute("DELETE FROM auth_state")

        logger.info("Authentication data cleared successfully")
        return True

    except Exception as e:
        logger.error(f"Error clearing auth data: {e}")
        return False


def get_auth_info() -> Dict[str, Any]:
    """Get detailed authentication information for debugging"""
    try:
        conn_manager = get_connection_manager()

        result = conn_manager.execute_single("""
            SELECT api_key, created_at, token_type
            FROM auth_state 
            ORDER BY id DESC 
            LIMIT 1
        """)

        if result:
            # Don't log the actual API key for security
            has_key = bool(result.get('api_key'))
            key_length = len(result.get('api_key', '')) if has_key else 0

            return {
                "has_api_key": has_key,
                "api_key_length": key_length,
                "token_type": result.get('token_type', 'Unknown'),
                "created_at": result.get('created_at'),
                "is_authorized": has_key
            }

        return {
            "has_api_key": False,
            "is_authorized": False
        }

    except Exception as e:
        logger.error(f"Failed to get auth info: {e}")
        return {
            "has_api_key": False,
            "is_authorized": False,
            "error": str(e)
        }