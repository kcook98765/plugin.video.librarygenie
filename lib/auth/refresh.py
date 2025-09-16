
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Token Refresh (DEPRECATED)
This module has been completely replaced by OTP-based authentication.
OAuth2 refresh token functionality is no longer used.
"""

import warnings
from lib.utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('lib.auth.refresh')

def refresh_access_token():
    """
    DEPRECATED: Refresh tokens are not used in OTP-based auth system
    """
    warnings.warn(
        "refresh_access_token() is deprecated. OTP auth uses permanent API keys.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.error("Deprecated refresh token flow called - not needed with API keys")
    return False, "Deprecated function - API keys don't expire"

def maybe_refresh():
    """
    DEPRECATED: Token refresh not needed with API key authentication
    """
    warnings.warn(
        "maybe_refresh() is deprecated. API keys don't require refresh.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.error("Deprecated maybe_refresh called - API keys don't expire")
    return True  # Return True to indicate "auth is still valid"

# Clean up - remove all other functions
__all__ = ['maybe_refresh']  # Export only what's needed
