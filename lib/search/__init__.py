#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Search Module
Fast, offline search across local library and lists with filters and sorting
"""

from .query_interpreter import get_query_interpreter
from .search_engine import get_search_engine

__all__ = ['get_query_interpreter', 'get_search_engine']