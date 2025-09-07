#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Remote Search Client (DEPRECATED)
This module has been replaced by ai_search_client.py for AI-powered search.
Kept as placeholder for backward compatibility during transition.
"""

import warnings
from ..utils.logger import get_logger

logger = get_logger(__name__)

class RemoteError(Exception):
    """Remote search error (deprecated)"""
    pass

def search_remote(query, page=1, page_size=100):
    """
    Deprecated function - use ai_search_client.AISearchClient.search() instead
    """
    warnings.warn(
        "search_remote() is deprecated. Use ai_search_client.AISearchClient.search() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.warning("Deprecated remote search called - please update to use AI search client")
    raise RemoteError("Deprecated remote search - use AI search instead")