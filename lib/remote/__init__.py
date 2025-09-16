
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Remote Integration
AI search client and cache functionality
"""

from lib.remote.ai_search_client import AISearchClient, get_ai_search_client
from lib.remote.cache import RemoteCache

# Import deprecated modules for backward compatibility but don't export them
try:
    from lib.remote import search_client  # Keep for backward compatibility
    from lib.remote import service  # Keep for backward compatibility
except ImportError:
    pass

__all__ = [
    'AISearchClient',
    'get_ai_search_client',
    'RemoteCache'
]
