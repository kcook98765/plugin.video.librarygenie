
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Data Layer
Database operations and query management
"""

from .query_manager import QueryManager

# Global query manager instance
_query_manager = None

def get_query_manager() -> QueryManager:
    """Get or create the global query manager instance"""
    global _query_manager
    if _query_manager is None:
        _query_manager = QueryManager()
    return _query_manager

# Export main classes and functions
__all__ = [
    'QueryManager',
    'get_query_manager'
]
