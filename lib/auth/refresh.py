
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Token Refresh
Handles automatic token refresh for LibraryGenie server
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ..config import get_config
from ..utils.logger import get_logger
from .state import get_tokens, save_tokens, is_authorized


class RefreshError(Exception):
    """Exception for token refresh errors"""
    pass


def maybe_refresh() -> bool:
    """
    Check if token needs refresh and refresh if necessary
    Returns True if token is valid (refreshed or not), False otherwise
    """
    logger = get_logger(__name__)
    
    if not is_authorized():
        return False
    
    try:
        tokens = get_tokens()
        if not tokens or "refresh_token" not in tokens:
            logger.debug("No refresh token available")
            return False
        
        # Check if token needs refresh (refresh 5 minutes before expiry)
        if not _needs_refresh(tokens):
            return True
        
        logger.debug("Access token needs refresh, attempting refresh")
        
        # Attempt refresh
        new_tokens = _refresh_token(tokens["refresh_token"])
        if new_tokens:
            save_tokens(new_tokens)
            logger.info("Successfully refreshed access token")
            return True
        else:
            logger.warning("Token refresh failed")
            return False
            
    except Exception as e:
        logger.error(f"Token refresh check failed: {e}")
        return False


def _needs_refresh(tokens: Dict[str, Any]) -> bool:
    """Check if token needs refresh based on expires_at"""
    try:
        expires_at_str = tokens.get("expires_at")
        if not expires_at_str:
            # No expiry info, assume needs refresh
            return True
        
        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        now = datetime.now(expires_at.tzinfo)
        
        # Refresh 5 minutes before expiry
        refresh_threshold = expires_at - timedelta(minutes=5)
        
        return now >= refresh_threshold
        
    except Exception:
        # If we can't parse expiry, assume needs refresh
        return True


def _refresh_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """Refresh the access token using refresh token"""
    logger = get_logger(__name__)
    config = get_config()
    
    try:
        base_url = config.get("remote_base_url", "").rstrip("/")
        if not base_url:
            logger.error("No remote base URL configured")
            return None
        
        url = f"{base_url}/auth/refresh"
        
        data = json.dumps({"refresh_token": refresh_token}).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "LibraryGenie-Kodi/1.0"
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                
                # Extract tokens
                access_token = result.get("access_token")
                new_refresh_token = result.get("refresh_token", refresh_token)
                expires_in = result.get("expires_in", 3600)
                
                if access_token:
                    # Calculate expiry time
                    expires_at = datetime.now() + timedelta(seconds=expires_in)
                    
                    return {
                        "access_token": access_token,
                        "refresh_token": new_refresh_token,
                        "expires_at": expires_at.isoformat(),
                        "token_type": "Bearer"
                    }
            else:
                logger.error(f"Refresh request failed with status {response.status}")
                return None
                
    except Exception as e:
        logger.error(f"Token refresh request failed: {e}")
        return None
    
    return None
