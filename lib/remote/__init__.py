
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Remote Integration
AI search client and cache functionality
"""

from .ai_search_client import AISearchClient, get_ai_search_client
from .cache import RemoteCache

# Import deprecated modules for backward compatibility but don't export them
try:
    from . import search_client  # Keep for backward compatibility
    from . import service  # Keep for backward compatibility
except ImportError:
    pass

__all__ = [
    'AISearchClient',
    'get_ai_search_client',
    'RemoteCache'
]
