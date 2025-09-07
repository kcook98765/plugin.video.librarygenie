
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Token Refresh (DEPRECATED)
This module is no longer needed with API key authentication.
API keys don't require refresh like OAuth2 tokens.
Kept as placeholder for backward compatibility during transition.
"""

import warnings
from ..utils.logger import get_logger

logger = get_logger(__name__)

def maybe_refresh() -> bool:
    """
    Deprecated function - API keys don't require refresh
    """
    warnings.warn(
        "maybe_refresh() is deprecated. API keys don't require refresh.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.debug("Token refresh called but not needed with API key auth")
    return True  # Always return True since API keys don't expire

class RefreshError(Exception):
    """Deprecated exception class"""
    pass
