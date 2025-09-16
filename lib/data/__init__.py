#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Data Layer
Database operations and query management
"""

from lib.data.query_manager import QueryManager, get_query_manager
from lib.data.connection_manager import get_connection_manager
from lib.data.storage_manager import get_storage_manager
from lib.data.migrations import get_migration_manager

# Export main classes and functions
__all__ = [
    'QueryManager',
    'get_query_manager',
    'get_connection_manager',
    'get_storage_manager',
    'get_migration_manager'
]