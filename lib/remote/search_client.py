
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Remote Search Client (DEPRECATED)
This module has been completely replaced by ai_search_client.py for AI-powered search.
All remote search functionality now uses the new OTP-based authentication system.
"""

import warnings
from ..utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('lib.remote.search_client')

# Deprecated exception kept for backward compatibility
class RemoteError(Exception):
    """Remote search error (deprecated)"""
    pass

def search_remote(query, page=1, page_size=100):
    """
    DEPRECATED: Use ai_search_client.AISearchClient.search_movies() instead
    """
    warnings.warn(
        "search_remote() is deprecated. Use ai_search_client.AISearchClient.search_movies() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.error("Deprecated remote search called - functionality removed")
    raise RemoteError("Deprecated remote search - use AISearchClient.search_movies() instead")

# Remove any other old functions that might exist
__all__ = ['RemoteError']  # Only export the exception for compatibility
