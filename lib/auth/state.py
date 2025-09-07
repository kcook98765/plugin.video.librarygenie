
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



