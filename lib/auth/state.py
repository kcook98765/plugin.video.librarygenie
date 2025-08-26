
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Authentication State Management
Handles token storage and authorization status
"""

import json
import os
import xbmcaddon
import xbmcvfs
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Token storage path in addon profile directory
_PATH = xbmcaddon.Addon().getAddonInfo('profile')
_FILE = os.path.join(_PATH, 'tokens.json')


def is_authorized():
    """Check if the device is currently authorized"""
    try:
        if not xbmcvfs.exists(_FILE):
            return False
            
        with xbmcvfs.File(_FILE, 'r') as f:
            content = f.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            data = json.loads(content)
            access_token = data.get('access_token')
            
            if not access_token:
                return False
                
            # TODO: Check token expiry in future phases
            logger.debug("Device is authorized")
            return True
            
    except Exception as e:
        logger.debug(f"Authorization check failed: {e}")
        return False


def get_access_token():
    """Get the current access token if available"""
    try:
        if not xbmcvfs.exists(_FILE):
            return None
            
        with xbmcvfs.File(_FILE, 'r') as f:
            content = f.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            data = json.loads(content)
            return data.get('access_token')
            
    except Exception as e:
        logger.error(f"Failed to get access token: {e}")
        return None


def save_tokens(tokens: dict):
    """Save authorization tokens to storage"""
    try:
        # Ensure profile directory exists
        if not xbmcvfs.exists(_PATH):
            xbmcvfs.mkdirs(_PATH)
        
        # Write tokens to file
        with xbmcvfs.File(_FILE, 'w') as f:
            token_data = json.dumps(tokens, indent=2)
            f.write(bytearray(token_data, 'utf-8'))
        
        logger.info("Authorization tokens saved successfully")
        
    except Exception as e:
        logger.error(f"Failed to save tokens: {e}")
        raise


def clear_tokens():
    """Clear stored authorization tokens"""
    try:
        if xbmcvfs.exists(_FILE):
            xbmcvfs.delete(_FILE)
            logger.info("Authorization tokens cleared")
        else:
            logger.debug("No tokens to clear")
            
    except Exception as e:
        logger.error(f"Failed to clear tokens: {e}")


def get_token_info():
    """Get detailed token information for debugging"""
    try:
        if not xbmcvfs.exists(_FILE):
            return {"exists": False}
            
        with xbmcvfs.File(_FILE, 'r') as f:
            content = f.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            data = json.loads(content)
            
            # Return sanitized info (no actual tokens)
            return {
                "exists": True,
                "has_access_token": bool(data.get('access_token')),
                "has_refresh_token": bool(data.get('refresh_token')),
                "token_type": data.get('token_type', 'Bearer')
            }
            
    except Exception as e:
        logger.error(f"Failed to get token info: {e}")
        return {"exists": False, "error": str(e)}
