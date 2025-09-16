#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Module
Simple keyword-based search across title and plot fields
"""

# Simple search components
from lib.search.simple_query_interpreter import get_simple_query_interpreter
from lib.search.simple_search_engine import get_simple_search_engine
from lib.search.simple_search_query import SimpleSearchQuery

# Utility classes
from lib.search.normalizer import get_text_normalizer

__all__ = [
    'get_simple_query_interpreter',
    'get_simple_search_engine', 
    'SimpleSearchQuery',
    'get_text_normalizer'
]