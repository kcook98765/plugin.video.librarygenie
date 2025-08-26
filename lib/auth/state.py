#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Authentication State Management
Handles token storage and authorization status
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

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
            token = data.get('access_token')

            if token:
                logger.debug("Access token retrieved successfully")
            else:
                logger.debug("No access token found in storage")

            return token

    except Exception as e:
        logger.error("Failed to get access token (token value not logged for security)")
        return None


def save_tokens(tokens: Dict[str, Any]):
    """Save authorization tokens to storage"""
    try:
        # Ensure profile directory exists
        if not xbmcvfs.exists(_PATH):
            xbmcvfs.mkdirs(_PATH)

        # Write tokens to file
        with xbmcvfs.File(_FILE, 'w') as f:
            f.write(json.dumps(tokens).encode('utf-8'))

        logger.info("Authorization tokens saved successfully (token values not logged for security)")

    except Exception as e:
        logger.error("Failed to save tokens (token values not logged for security)")
        raise


def get_tokens() -> Optional[Dict[str, Any]]:
    """Get stored tokens"""
    try:
        if not xbmcvfs.exists(_FILE):
            return None

        with xbmcvfs.File(_FILE, 'r') as f:
            content = f.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')

            data = json.loads(content)
            logger.debug("Token data retrieved (values not logged for security)")
            return data

    except Exception as e:
        logger.error("Failed to get tokens (token values not logged for security)")
        return None


def clear_tokens():
    """Clear stored tokens and revoke authorization"""
    try:
        if not xbmcvfs.exists(_FILE):
            logger.debug("No token file exists to clear")
            return True

        success = xbmcvfs.delete(_FILE)
        if success:
            logger.info("Authorization tokens cleared successfully")
        else:
            logger.warning("Failed to delete token file")
        return success

    except Exception as e:
        logger.error(f"Error clearing tokens: {e}")
        return False


def get_token_info() -> Dict[str, Any]:
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