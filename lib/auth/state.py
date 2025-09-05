
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Authentication State Management
Handles token storage and authorization status using database
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..data.connection_manager import get_connection_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


def is_authorized():
    """Check if the device is currently authorized"""
    try:
        conn_manager = get_connection_manager()
        
        # Check for valid, non-expired token
        token_data = conn_manager.execute_single("""
            SELECT access_token, expires_at 
            FROM auth_state 
            WHERE expires_at > datetime('now')
            ORDER BY id DESC 
            LIMIT 1
        """)
        
        if token_data and token_data.get('access_token'):
            logger.debug("Device is authorized")
            return True
        
        return False

    except Exception as e:
        logger.debug(f"Authorization check failed: {e}")
        return False


def get_access_token():
    """Get the current access token if available"""
    try:
        conn_manager = get_connection_manager()
        
        token_data = conn_manager.execute_single("""
            SELECT access_token 
            FROM auth_state 
            WHERE expires_at > datetime('now')
            ORDER BY id DESC 
            LIMIT 1
        """)
        
        if token_data:
            logger.debug("Access token retrieved successfully")
            return token_data['access_token']
        else:
            logger.debug("No valid access token found")
            return None

    except Exception as e:
        logger.error("Failed to get access token")
        return None


def save_tokens(tokens: Dict[str, Any]):
    """Save authorization tokens to database"""
    try:
        conn_manager = get_connection_manager()
        
        # Calculate expiry time
        expires_at = None
        if tokens.get('expires_in'):
            expires_at = datetime.now() + timedelta(seconds=int(tokens['expires_in']))
            expires_at = expires_at.isoformat()
        
        with conn_manager.transaction() as conn:
            conn.execute("""
                INSERT INTO auth_state (access_token, expires_at, token_type, scope)
                VALUES (?, ?, ?, ?)
            """, [
                tokens.get('access_token'),
                expires_at,
                tokens.get('token_type', 'Bearer'),
                tokens.get('scope', '')
            ])

        logger.info("Authorization tokens saved successfully")

    except Exception as e:
        logger.error("Failed to save tokens")
        raise


def get_tokens() -> Optional[Dict[str, Any]]:
    """Get stored tokens"""
    try:
        conn_manager = get_connection_manager()
        
        token_data = conn_manager.execute_single("""
            SELECT access_token, expires_at, token_type, scope
            FROM auth_state 
            WHERE expires_at > datetime('now')
            ORDER BY id DESC 
            LIMIT 1
        """)
        
        if token_data:
            logger.debug("Token data retrieved")
            return dict(token_data)
        
        return None

    except Exception as e:
        logger.error("Failed to get tokens")
        return None


def clear_tokens():
    """Clear stored tokens and revoke authorization"""
    try:
        conn_manager = get_connection_manager()
        
        with conn_manager.transaction() as conn:
            conn.execute("DELETE FROM auth_state")
        
        logger.info("Authorization tokens cleared successfully")
        return True

    except Exception as e:
        logger.error(f"Error clearing tokens: {e}")
        return False


def get_token_info() -> Dict[str, Any]:
    """Get detailed token information for debugging"""
    try:
        conn_manager = get_connection_manager()
        
        token_data = conn_manager.execute_single("""
            SELECT access_token, expires_at, token_type
            FROM auth_state 
            ORDER BY id DESC 
            LIMIT 1
        """)
        
        if token_data:
            return {
                "exists": True,
                "has_access_token": bool(token_data.get('access_token')),
                "token_type": token_data.get('token_type', 'Bearer'),
                "expires_at": token_data.get('expires_at')
            }
        
        return {"exists": False}

    except Exception as e:
        logger.error(f"Failed to get token info: {e}")
        return {"exists": False, "error": str(e)}
