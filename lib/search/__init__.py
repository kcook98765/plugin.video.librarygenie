
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Module
Fast, offline search across local library and lists with filters and sorting
"""

# Enhanced search (existing)
from .enhanced_query_interpreter import get_enhanced_query_interpreter, SearchQuery
from .enhanced_search_engine import get_enhanced_search_engine

# Simple search (new)
from .simple_query_interpreter import get_simple_query_interpreter
from .simple_search_engine import get_simple_search_engine
from .simple_search_query import SimpleSearchQuery

# Utility classes
from .normalizer import get_text_normalizer
from .year_parser import get_year_parser

__all__ = [
    # Enhanced search
    'get_enhanced_query_interpreter',
    'SearchQuery', 
    'get_enhanced_search_engine',
    # Simple search
    'get_simple_query_interpreter',
    'get_simple_search_engine', 
    'SimpleSearchQuery',
    # Utils
    'get_text_normalizer',
    'get_year_parser'
]
