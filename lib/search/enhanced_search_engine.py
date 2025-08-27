#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Enhanced Search Engine
Enhanced SQL building, paging UI, and performance optimizations
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple

from .enhanced_query_interpreter import SearchQuery
from .normalizer import get_text_normalizer
from ..data import get_connection_manager
from ..utils.logger import get_logger


class SearchResult:
    """Enhanced search result object with paging improvements"""

    def __init__(self):
        self.items = []  # Search result items
        self.total_count = 0  # Total results (for pagination)
        self.current_page = 1
        self.page_count = 1
        self.has_next_page = False
        self.has_prev_page = False
        self.query_summary = ""  # Human-readable query description
        self.search_duration_ms = 0
        self.scope_description = ""  # "All library" or "List - Movie Night"
        self.sort_description = ""  # "Title (A-Z)"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "items": self.items,
            "total_count": self.total_count,
            "current_page": self.current_page,
            "page_count": self.page_count,
            "has_next_page": self.has_next_page,
            "has_prev_page": self.has_prev_page,
            "query_summary": self.query_summary,
            "search_duration_ms": self.search_duration_ms,
            "scope_description": self.scope_description,
            "sort_description": self.sort_description
        }


class EnhancedSearchEngine:
    """Enhanced search engine with improved SQL building and paging"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.normalizer = get_text_normalizer()

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute search query with enhancements"""
        start_time = datetime.now()
        result = SearchResult()

        try:
            # Validate query
            if not self._is_valid_query(query):
                result.query_summary = "Empty search"
                result.scope_description = self._get_scope_description(query)
                return result

            # Enhanced SQL building with improved parameterization
            sql_query, params = self._build_enhanced_sql_query(query)

            # Efficient pagination with "has-next-page" check
            result = self._execute_paginated_search(sql_query, params, query)

            # Generate enhanced descriptions
            result.query_summary = self._generate_enhanced_query_summary(query, result.total_count)
            result.scope_description = self._get_scope_description(query)
            result.sort_description = self._get_sort_description(query.sort_method)

            # Calculate duration
            duration = datetime.now() - start_time
            result.search_duration_ms = int(duration.total_seconds() * 1000)

            # Log search
            self._log_search(query, result)

            self.logger.debug(f"Search completed: {result.total_count} results in {result.search_duration_ms}ms")
            return result

        except Exception as e:
            self.logger.error(f"Search error: {e}")
            result.query_summary = "Search error"
            return result

    def _is_valid_query(self, query: SearchQuery) -> bool:
        """Check if query has searchable content"""
        return bool(query.tokens) or query.year_filter is not None

    def _build_enhanced_sql_query(self, query: SearchQuery) -> Tuple[str, List[Any]]:
        """Enhanced SQL builder with improved parameterization"""
        params = []
        where_clauses = ["1=1"]  # Always true condition since media_items doesn't have is_removed column

        # Base SELECT with required fields
        if query.scope_type == "list":
            select_clause = """
                SELECT DISTINCT mi.id, mi.kodi_id, mi.title, mi.year, mi.play as file_path, 
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.created_at, 
                       mi.poster, mi.fanart, mi.plot, mi.rating, mi.duration as runtime,
                       mi.genre, mi.director, 0 as playcount
                FROM media_items mi
                INNER JOIN list_items li ON li.media_item_id = mi.id
            """
            where_clauses.append("li.list_id = ?")
            params.append(query.scope_id)
        else:
            select_clause = """
                SELECT mi.id, mi.kodi_id, mi.title, mi.year, mi.play as file_path, 
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.created_at, 
                       mi.poster, mi.fanart, mi.plot, mi.rating, mi.duration as runtime,
                       mi.genre, mi.director, 0 as playcount
                FROM media_items mi
            """

        # Enhanced text search with match modes
        if query.tokens:
            text_clauses = []

            for i, token in enumerate(query.tokens):
                token_clauses = []

                # Normalize the token for comparison
                normalized_token = self.normalizer.normalize(token)

                # Title search with match mode
                if query.match_mode == "starts_with" and i == 0:
                    # First token must start the title - use LOWER() for case-insensitive comparison
                    token_clauses.append("LOWER(mi.title) LIKE ?")
                    params.append(f"{normalized_token}%")
                else:
                    # Contains mode for all tokens or non-first tokens in starts_with
                    token_clauses.append("LOWER(mi.title) LIKE ?")
                    params.append(f"%{normalized_token}%")

                # Optional file path search
                if query.include_file_path:
                    token_clauses.append("LOWER(mi.play) LIKE ?")
                    params.append(f"%{normalized_token}%")

                # Combine token clauses with OR
                if token_clauses:
                    text_clauses.append(f"({' OR '.join(token_clauses)})")

            # All tokens must match (AND)
            if text_clauses:
                where_clauses.append(f"({' AND '.join(text_clauses)})")

        # Enhanced year filtering
        if query.year_filter is not None:
            if isinstance(query.year_filter, tuple):
                # Year range
                where_clauses.append("mi.year BETWEEN ? AND ?")
                params.extend([query.year_filter[0], query.year_filter[1]])
            else:
                # Exact year
                where_clauses.append("mi.year = ?")
                params.append(query.year_filter)

        # Build final query
        where_clause = " AND ".join(where_clauses)
        order_clause = self._get_sort_clause(query.sort_method)

        full_query = f"{select_clause} WHERE {where_clause} ORDER BY {order_clause}"

        return full_query, params

    def _execute_paginated_search(self, sql_query: str, params: List[Any], query: SearchQuery) -> SearchResult:
        """Efficient pagination with has-next-page check"""
        result = SearchResult()

        try:
            # Phase 5: Use page_size + 1 trick to avoid expensive COUNT(*)
            limit = query.page_size + 1
            paginated_sql = f"{sql_query} LIMIT ? OFFSET ?"
            paginated_params = params + [limit, query.page_offset]

            # Execute query
            movies = self.conn_manager.execute_query(paginated_sql, paginated_params)
            items = [dict(movie) if hasattr(movie, 'keys') else movie for movie in movies or []]

            # Calculate pagination info
            has_more = len(items) > query.page_size
            if has_more:
                items = items[:-1]  # Remove the extra item

            result.items = items
            result.current_page = (query.page_offset // query.page_size) + 1
            result.has_next_page = has_more
            result.has_prev_page = query.page_offset > 0

            # For total count, use a separate optimized query when needed
            if query.page_offset == 0 and not has_more:
                # First page and no more pages - exact count
                result.total_count = len(items)
                result.page_count = 1
            else:
                # Need approximate count
                result.total_count = self._get_approximate_count(sql_query, params, query)
                result.page_count = max(1, (result.total_count + query.page_size - 1) // query.page_size)

            return result

        except Exception as e:
            self.logger.error(f"Paginated search error: {e}")
            return result

    def _get_approximate_count(self, sql_query: str, params: List[Any], query: SearchQuery) -> int:
        """Get approximate total count for pagination"""
        try:
            # Convert to count query
            count_sql = self._build_count_query(sql_query)
            result = self.conn_manager.execute_single(count_sql, params)

            if result:
                if isinstance(result, int):
                    return result
                elif hasattr(result, 'keys'):
                    return result.get('COUNT(*)', 0)
                elif hasattr(result, '__getitem__'):
                    return result[0] if len(result) > 0 else 0
                else:
                    return int(result)
            return 0

        except Exception as e:
            self.logger.debug(f"Count query error, using estimate: {e}")
            # Fallback estimate based on current position
            return query.page_offset + query.page_size + (50 if query.page_offset > 0 else 0)

    def _build_count_query(self, main_sql: str) -> str:
        """Convert main query to count query"""
        import re

        # Remove ORDER BY clause
        count_sql = re.sub(r'\s+ORDER\s+BY\s+.*$', '', main_sql, flags=re.IGNORECASE)

        # Replace SELECT fields with COUNT(*)
        select_pattern = r'SELECT\s+.*?\s+FROM'
        count_sql = re.sub(select_pattern, 'SELECT COUNT(*) FROM', count_sql, flags=re.IGNORECASE | re.DOTALL)

        return count_sql

    def _get_sort_clause(self, sort_method: str) -> str:
        """Get SQL ORDER BY clause for sort method"""
        sort_mapping = {
            "title_asc": "mi.title ASC",
            "title_desc": "mi.title DESC",
            "year_asc": "mi.year ASC, mi.title ASC",
            "year_desc": "mi.year DESC, mi.title ASC",
            "added_desc": "mi.created_at DESC",
            "added_asc": "mi.created_at ASC"
        }

        return sort_mapping.get(sort_method, "mi.title ASC")

    def _generate_enhanced_query_summary(self, query: SearchQuery, total_count: int) -> str:
        """Generate enhanced query summary"""
        parts = []

        if query.tokens:
            parts.append(f'"{" ".join(query.tokens)}"')

        if query.year_filter:
            if isinstance(query.year_filter, tuple):
                parts.append(f"({query.year_filter[0]}–{query.year_filter[1]})")
            else:
                parts.append(f"({query.year_filter})")

        if query.include_file_path:
            parts.append("including paths")

        # Include match mode if not default
        if query.match_mode == "starts_with":
            parts.append("starts with")

        summary = " • ".join(parts) if parts else "all movies"
        return f"Results: {total_count} • {summary}"

    def _get_scope_description(self, query: SearchQuery) -> str:
        """Get human-readable scope description"""
        if query.scope_type == "list":
            # TODO: Get actual list name from database
            return f"List"  # Could be enhanced to show list name
        else:
            return "All library"

    def _get_sort_description(self, sort_method: str) -> str:
        """Get human-readable sort description"""
        sort_descriptions = {
            "title_asc": "Title (A–Z)",
            "title_desc": "Title (Z–A)",
            "year_asc": "Year (oldest first)",
            "year_desc": "Year (newest first)",
            "added_desc": "Recently added",
            "added_asc": "Oldest added"
        }

        return sort_descriptions.get(sort_method, "Title (A–Z)")

    def _log_search(self, query: SearchQuery, result: SearchResult):
        """Log search for analytics"""
        try:
            year_filter_str = None
            if query.year_filter:
                if isinstance(query.year_filter, tuple):
                    year_filter_str = f"{query.year_filter[0]}-{query.year_filter[1]}"
                else:
                    year_filter_str = str(query.year_filter)

            # Log to search_history table
            self.conn_manager.execute_single("""
                INSERT INTO search_history 
                (query_text, scope_type, scope_id, year_filter, sort_method, 
                 include_file_path, result_count, search_duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                query.text, query.scope_type, query.scope_id, year_filter_str,
                query.sort_method, 1 if query.include_file_path else 0,
                result.total_count, result.search_duration_ms
            ])

        except Exception as e:
            self.logger.error(f"Error logging search: {e}")


# Global enhanced search engine instance
_enhanced_search_engine_instance = None


def get_enhanced_search_engine():
    """Get global enhanced search engine instance"""
    global _enhanced_search_engine_instance
    if _enhanced_search_engine_instance is None:
        _enhanced_search_engine_instance = EnhancedSearchEngine()
    return _enhanced_search_engine_instance