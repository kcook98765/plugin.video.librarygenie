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
from ..config.settings import SettingsManager


logger = get_logger(__name__)


def is_authorized() -> bool:
    """Check if the device has a valid API key"""
    try:
        api_key = get_api_key()
        return bool(api_key and api_key.strip())
    except Exception as e:
        logger.debug("Authorization check failed: %s", e)
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

        if result and result['api_key']:
            logger.debug("API key retrieved successfully")
            return result['api_key']
        else:
            logger.debug("No API key found")
            return None

    except Exception as e:
        logger.error("Failed to get API key: %s", e)
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

            # Check if token_type column exists (new schema)
            cursor = conn.execute("PRAGMA table_info(auth_state)")
            columns = [column[1] for column in cursor.fetchall()]
            has_token_type = 'token_type' in columns
            has_scope = 'scope' in columns

            # Insert new API key using appropriate schema
            if has_token_type and has_scope:
                # New schema with token_type and scope columns
                conn.execute("""
                    INSERT INTO auth_state (api_key, created_at, token_type, scope)
                    VALUES (?, ?, ?, ?)
                """, [
                    api_key.strip(),
                    datetime.now().isoformat(),
                    'ApiKey',
                    'ai_search'
                ])
                logger.info("API key saved with new schema (token_type + scope)")
            elif has_token_type:
                # Schema with token_type but no scope
                conn.execute("""
                    INSERT INTO auth_state (api_key, created_at, token_type)
                    VALUES (?, ?, ?)
                """, [
                    api_key.strip(),
                    datetime.now().isoformat(),
                    'ApiKey'
                ])
                logger.info("API key saved with partial new schema (token_type only)")
            else:
                # Old schema without token_type or scope
                conn.execute("""
                    INSERT INTO auth_state (api_key, created_at)
                    VALUES (?, ?)
                """, [
                    api_key.strip(),
                    datetime.now().isoformat()
                ])
                logger.info("API key saved with legacy schema")

        logger.info("API key saved successfully")
        return True

    except Exception as e:
        logger.error("Failed to save API key: %s", e)
        return False


def save_tokens(api_key: Optional[str] = None, access_token: Optional[str] = None, refresh_token: Optional[str] = None, expires_at: Optional[str] = None) -> bool:
    """Save authentication tokens to addon settings"""
    try:
        settings = SettingsManager()

        if api_key is not None:
            settings.set_ai_search_api_key(api_key)
        if access_token is not None:
            settings.set_setting('access_token', access_token)
        if refresh_token is not None:
            settings.set_setting('refresh_token', refresh_token)
        if expires_at is not None:
            settings.set_setting('token_expires_at', expires_at)

        logger.debug("Authentication tokens saved")
        return True

    except Exception as e:
        logger.error("Error saving tokens: %s", e)
        return False


def get_tokens() -> Dict[str, str]:
    """Get all stored authentication tokens"""
    try:
        settings = SettingsManager()
        
        return {
            'api_key': settings.get_ai_search_api_key() or '',
            'access_token': settings.addon.getSetting('access_token'),
            'refresh_token': settings.addon.getSetting('refresh_token'),
            'expires_at': settings.addon.getSetting('token_expires_at')
        }

    except Exception as e:
        logger.error("Error getting tokens: %s", e)
        return {
            'api_key': '',
            'access_token': '',
            'refresh_token': '',
            'expires_at': ''
        }


def clear_tokens() -> bool:
    """Clear stored authentication tokens"""
    try:
        settings = SettingsManager()
        settings.set_ai_search_api_key('')
        settings.set_setting('refresh_token', '')
        settings.set_setting('access_token', '')
        settings.set_setting('token_expires_at', '')

        logger.info("Authentication tokens cleared")
        return True

    except Exception as e:
        logger.error("Error clearing tokens: %s", e)
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
        logger.error("Error clearing auth data: %s", e)
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
        logger.error("Failed to get auth info: %s", e)
        return {
            "has_api_key": False,
            "is_authorized": False,
            "error": str(e)
        }