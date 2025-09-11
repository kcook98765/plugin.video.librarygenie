#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Query Interpreter
Simplified query parsing focused on keyword extraction without complex year logic
"""

from __future__ import annotations
from typing import List

from .simple_search_query import SimpleSearchQuery
from .normalizer import get_text_normalizer
from ..utils.logger import get_logger


class SimpleQueryInterpreter:
    """Simple query interpreter focusing on keyword extraction"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.normalizer = get_text_normalizer()

    def parse_query(self, user_input: str, **kwargs) -> SimpleSearchQuery:
        """Parse user input into simplified search query"""
        query = SimpleSearchQuery()
        query.original_text = user_input or ""

        try:
            # Set scope parameters
            query.scope_type = kwargs.get("scope_type", "library")
            query.scope_id = kwargs.get("scope_id")
            query.page_size = max(25, min(kwargs.get("page_size", 50), 200))
            query.page_offset = max(kwargs.get("page_offset", 0), 0)
            
            # Always search both title and plot with all keywords
            query.search_scope = "both"
            query.match_logic = "all"

            # Extract and normalize keywords
            if user_input and user_input.strip():
                # Use normalizer to get clean tokens
                query.keywords = self.normalizer.normalize_tokens(user_input.strip())

            self.logger.debug("Parsed simple query: %s", query.to_dict())
            return query

        except Exception as e:
            self.logger.error("Error parsing simple query '%s': %s", user_input, e)
            # Return safe default query
            if user_input:
                query.keywords = user_input.strip().lower().split()
            return query

    def is_empty_query(self, query: SimpleSearchQuery) -> bool:
        """Check if query is effectively empty"""
        return not query.keywords

    def get_empty_query_hint(self) -> str:
        """Get hint text for empty queries"""
        return "Enter keywords to search for movies"

    def get_no_results_hint(self, query: SimpleSearchQuery) -> str:
        """Get hint text for no results"""
        return "Try fewer keywords or different search terms"


# Global simple query interpreter instance
_simple_query_interpreter_instance = None


def get_simple_query_interpreter():
    """Get global simple query interpreter instance"""
    global _simple_query_interpreter_instance
    if _simple_query_interpreter_instance is None:
        _simple_query_interpreter_instance = SimpleQueryInterpreter()
    return _simple_query_interpreter_instance