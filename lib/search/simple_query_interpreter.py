#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Query Interpreter
Simplified query parsing focused on keyword extraction without complex year logic
"""

from __future__ import annotations
from typing import List

from lib.search.simple_search_query import SimpleSearchQuery
from lib.search.normalizer import get_text_normalizer
from lib.utils.kodi_log import get_kodi_logger
from lib.config.settings import SettingsManager


class SimpleQueryInterpreter:
    """Simple query interpreter focusing on keyword extraction"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.search.simple_query_interpreter')
        self.normalizer = get_text_normalizer()
        self.settings = SettingsManager()

    def parse_query(self, user_input: str, **kwargs) -> SimpleSearchQuery:
        """Parse user input into simplified search query"""
        query = SimpleSearchQuery()
        query.original_text = user_input or ""

        try:
            # Set scope parameters
            query.scope_type = kwargs.get("scope_type", "library")
            query.scope_id = kwargs.get("scope_id")
            default_page_size = self.settings.get_search_page_size()
            query.page_size = max(25, min(kwargs.get("page_size", default_page_size), 500))
            query.page_offset = max(kwargs.get("page_offset", 0), 0)
            
            # Set media types to search (defaults to movies for backward compatibility)
            query.media_types = kwargs.get("media_types", ["movie"])
            
            # Set search scope and match logic (defaults for backward compatibility)
            query.search_scope = kwargs.get("search_scope", "both")
            query.match_logic = kwargs.get("match_logic", "all")

            # Extract and normalize keywords
            if user_input and user_input.strip():
                original_input = user_input.strip()
                # For phrase matching, keep the original phrase intact
                if query.match_logic == "phrase":
                    query.keywords = [original_input]
                else:
                    # Use normalizer to get clean tokens for keyword matching
                    query.keywords = self.normalizer.normalize_tokens(original_input)
                self.logger.debug("DEBUG: Query parsing - original input: '%s', normalized keywords: %s", original_input, query.keywords)

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