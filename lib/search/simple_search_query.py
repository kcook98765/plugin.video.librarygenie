#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Search Query
Simplified search query class focusing on keyword-based search across title and plot fields
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any


class SimpleSearchQuery:
    """Simplified search query object for keyword-based search"""

    def __init__(self):
        self.keywords: List[str] = []        # Individual search keywords
        self.original_text: str = ""         # User's original input
        self.search_scope: str = "both"      # "title", "plot", "both"
        self.match_logic: str = "all"        # "any", "all" 
        self.scope_type: str = "library"     # "library" or "list"
        self.scope_id: Optional[int] = None  # list_id if searching within list
        self.page_size: int = 50
        self.page_offset: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging"""
        return {
            "keywords": self.keywords,
            "original_text": self.original_text,
            "search_scope": self.search_scope,
            "match_logic": self.match_logic,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "page_size": self.page_size,
            "page_offset": self.page_offset
        }

    def is_valid(self) -> bool:
        """Check if query has searchable content"""
        return bool(self.keywords and self.original_text.strip())

    def get_summary(self) -> str:
        """Get human-readable query summary"""
        if not self.keywords:
            return "Empty search"
        
        keywords_text = f"'{' '.join(self.keywords)}'"
        return f"Search for {keywords_text}"