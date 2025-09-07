
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Token Refresh (DEPRECATED)
This module has been completely replaced by OTP-based authentication.
OAuth2 refresh token functionality is no longer used.
"""

import warnings
from ..utils.logger import get_logger

logger = get_logger(__name__)

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

# Clean up - remove all other functions
__all__ = []  # Export nothing
