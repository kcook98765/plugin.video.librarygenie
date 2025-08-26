#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Enhanced Query Interpreter
Enhanced search query parsing with robust year parsing and improved normalization
"""

import re
from typing import Dict, Any, List
from .normalizer import get_text_normalizer
from .year_parser import get_year_parser
from ..utils.logger import get_logger
from ..config import get_config


class SearchQuery:
    """Enhanced search query object"""
    
    def __init__(self):
        self.text = ""  # Normalized search text
        self.original_text = ""  # Original user input
        self.tokens = []  # Normalized search tokens
        self.year_filter = None  # Exact year or (start, end) tuple
        self.scope_type = "library"  # 'library' or 'list'
        self.scope_id = None  # list_id if scope_type = 'list'
        self.sort_method = "title_asc"  # 'title_asc', 'title_desc', 'year_desc', 'year_asc', 'added_desc'
        self.include_file_path = False
        self.match_mode = "contains"  # 'contains' or 'starts_with'
        self.page_size = 50
        self.page_offset = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging"""
        return {
            "text": self.text,
            "original_text": self.original_text,
            "tokens": self.tokens,
            "year_filter": self.year_filter,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "sort_method": self.sort_method,
            "include_file_path": self.include_file_path,
            "match_mode": self.match_mode,
            "page_size": self.page_size,
            "page_offset": self.page_offset
        }


class EnhancedQueryInterpreter:
    """Enhanced query interpreter with robust parsing and normalization"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.normalizer = get_text_normalizer()
        self.year_parser = get_year_parser()
    
    def parse_query(self, user_input: str, **kwargs) -> SearchQuery:
        """Parse user input into structured search query with enhancements"""
        query = SearchQuery()
        query.original_text = user_input or ""
        
        try:
            # Set defaults from kwargs and settings
            query.scope_type = kwargs.get("scope_type", "library")
            query.scope_id = kwargs.get("scope_id")
            query.sort_method = kwargs.get("sort_method", "title_asc")
            
            # Get settings with runtime clamping
            query.include_file_path = kwargs.get("include_file_path", 
                                                self._get_setting_bool("search_include_file_path", False))
            query.match_mode = kwargs.get("match_mode", 
                                        self._get_setting_string("search_match_mode", "contains"))
            query.page_size = self._clamp_page_size(kwargs.get("page_size", 
                                                              self._get_setting_int("search_page_size", 50)))
            query.page_offset = max(kwargs.get("page_offset", 0), 0)
            
            # Enhanced year parsing with explicit rules
            enable_decade_shorthand = self._get_setting_bool("search_enable_decade_shorthand", False)
            query.year_filter = self.year_parser.parse_year_filter(user_input, enable_decade_shorthand)
            
            # Remove year filters from text for clean search terms
            clean_text = self.year_parser.remove_year_filters_from_text(user_input)
            
            # Unified normalization for text and tokens
            query.text = self.normalizer.normalize(clean_text)
            query.tokens = self.normalizer.normalize_tokens(clean_text)
            
            self.logger.debug(f"Parsed query: {query.to_dict()}")
            return query
            
        except Exception as e:
            self.logger.error(f"Error parsing query '{user_input}': {e}")
            # Return safe default query
            query.text = self.normalizer.normalize(user_input) if user_input else ""
            query.tokens = self.normalizer.normalize_tokens(user_input) if user_input else []
            return query
    
    def _clamp_page_size(self, page_size: int) -> int:
        """Clamp page size to valid range"""
        return max(25, min(page_size, 200))
    
    def _get_setting_bool(self, key: str, default: bool) -> bool:
        """Get boolean setting with fallback"""
        try:
            value = self.config.get_setting(key, str(default).lower())
            return value.lower() in ('true', '1', 'yes', 'on')
        except Exception:
            return default
    
    def _get_setting_string(self, key: str, default: str) -> str:
        """Get string setting with fallback"""
        try:
            return self.config.get_setting(key, default)
        except Exception:
            return default
    
    def _get_setting_int(self, key: str, default: int) -> int:
        """Get integer setting with fallback"""
        try:
            value = self.config.get_setting(key, str(default))
            return int(value)
        except Exception:
            return default
    
    def is_empty_query(self, query: SearchQuery) -> bool:
        """Check if query is effectively empty"""
        return not query.tokens and not query.year_filter
    
    def get_empty_query_hint(self) -> str:
        """Get hint text for empty queries"""
        return "Enter search terms to find movies"  # Localized in UI
    
    def get_no_results_hint(self, query: SearchQuery) -> str:
        """Get hint text for no results"""
        if query.year_filter:
            return "Try fewer words or remove the year filter"
        else:
            return "Try different search terms or check spelling"


# Global enhanced query interpreter instance
_enhanced_query_interpreter_instance = None


def get_enhanced_query_interpreter():
    """Get global enhanced query interpreter instance"""
    global _enhanced_query_interpreter_instance
    if _enhanced_query_interpreter_instance is None:
        _enhanced_query_interpreter_instance = EnhancedQueryInterpreter()
    return _enhanced_query_interpreter_instance