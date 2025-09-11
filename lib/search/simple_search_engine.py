#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Search Engine
Simplified search engine with keyword ranking (title matches prioritized over plot matches)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Tuple

from .simple_search_query import SimpleSearchQuery
from .normalizer import get_text_normalizer
from ..data import get_connection_manager
from ..utils.logger import get_logger


class SimpleSearchResult:
    """Simple search result object"""

    def __init__(self):
        self.items = []  # Search result items
        self.total_count = 0  # Total results
        self.query_summary = ""  # Human-readable query description
        self.search_duration_ms = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "items": self.items,
            "total_count": self.total_count,
            "query_summary": self.query_summary,
            "search_duration_ms": self.search_duration_ms
        }


class SimpleSearchEngine:
    """Simple search engine with ranking based on title vs plot matches"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.normalizer = get_text_normalizer()

    def search(self, query: SimpleSearchQuery) -> SimpleSearchResult:
        """Execute simple search query with ranking"""
        start_time = datetime.now()
        result = SimpleSearchResult()

        try:
            # Validate query
            if not query.is_valid():
                result.query_summary = "Empty search"
                return result

            # Build SQL query with ranking
            sql_query, params = self._build_ranked_sql_query(query)

            # Log the actual SQL query being executed
            self.logger.debug("Executing search SQL: %s", sql_query)
            self.logger.debug("Search SQL parameters: %s", params)

            # Execute search
            items = self.conn_manager.execute_query(sql_query, params)
            result.items = [dict(item) if hasattr(item, 'keys') else item for item in items or []]
            result.total_count = len(result.items)

            # Generate query summary
            result.query_summary = query.get_summary()

            # Calculate duration
            duration = datetime.now() - start_time
            result.search_duration_ms = int(duration.total_seconds() * 1000)

            self.logger.debug("Simple search completed: %s results in %sms", result.total_count, result.search_duration_ms)
            return result

        except Exception as e:
            self.logger.error("Simple search error: %s", e)
            result.query_summary = "Search error"
            return result

    def _build_ranked_sql_query(self, query: SimpleSearchQuery) -> Tuple[str, List[Any]]:
        """Build SQL query with ranking logic"""
        params = []

        # Base SELECT with ranking calculation
        if query.scope_type == "list":
            select_clause = """
                SELECT DISTINCT mi.id, mi.kodi_id, mi.title, mi.year, mi.play as file_path, 
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.created_at, 
                       mi.poster, mi.fanart, mi.plot, mi.rating, mi.duration as runtime,
                       mi.genre, mi.director, 0 as playcount, mi.kodi_id as movieid,
                       {ranking_expression} as search_rank
                FROM media_items mi
                INNER JOIN list_items li ON li.media_item_id = mi.id
            """
            where_clauses = [
                "li.list_id = ?",
                "mi.media_type = 'movie'",
                "mi.source = 'library'", 
                "mi.is_removed = 0"
            ]
            params.append(query.scope_id)
        else:
            select_clause = """
                SELECT mi.id, mi.kodi_id, mi.title, mi.year, mi.play as file_path, 
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.created_at, 
                       mi.art, mi.plot, mi.rating, mi.duration as runtime,
                       mi.genre, mi.director, 0 as playcount, mi.kodi_id as movieid,
                       {ranking_expression} as search_rank
                FROM media_items mi
            """
            where_clauses = [
                "mi.media_type = 'movie'",
                "mi.source = 'library'",
                "mi.is_removed = 0"
            ]

        # Build search conditions and ranking expression
        search_conditions, ranking_expr, search_params = self._build_search_conditions(query)
        where_clauses.extend(search_conditions)
        params.extend(search_params)

        # Replace ranking placeholder
        select_clause = select_clause.format(ranking_expression=ranking_expr)

        # Build final query with ranking-based ordering
        where_clause = " AND ".join(where_clauses)
        order_clause = "search_rank ASC, LOWER(mi.title) ASC"

        full_query = f"{select_clause} WHERE {where_clause} ORDER BY {order_clause}"

        # Add pagination
        if query.page_size > 0:
            full_query += f" LIMIT {query.page_size}"
            if query.page_offset > 0:
                full_query += f" OFFSET {query.page_offset}"

        return full_query, params

    def _build_search_conditions(self, query: SimpleSearchQuery) -> Tuple[List[str], str, List[str]]:
        """Build search WHERE conditions and ranking expression"""
        conditions = []
        params = []

        # Build conditions based on search scope
        title_conditions = []
        plot_conditions = []

        for keyword in query.keywords:
            normalized_keyword = self.normalizer.normalize(keyword)

            if query.search_scope in ["title", "both"]:
                title_conditions.append("LOWER(mi.title) LIKE ?")
                params.append(f"%{normalized_keyword}%")

            if query.search_scope in ["plot", "both"]:
                plot_conditions.append("LOWER(mi.plot) LIKE ?")
                params.append(f"%{normalized_keyword}%")

        # Combine conditions based on match logic
        field_conditions = []

        if title_conditions:
            if query.match_logic == "all":
                field_conditions.append(f"({' AND '.join(title_conditions)})")
            else:  # any
                field_conditions.append(f"({' OR '.join(title_conditions)})")

        if plot_conditions:
            if query.match_logic == "all":
                field_conditions.append(f"({' AND '.join(plot_conditions)})")
            else:  # any
                field_conditions.append(f"({' OR '.join(plot_conditions)})")

        # Main search condition
        if field_conditions:
            if query.search_scope == "both":
                main_condition = f"({' OR '.join(field_conditions)})"
            else:
                main_condition = field_conditions[0]
            conditions.append(main_condition)

        # Build ranking expression
        ranking_expr = self._build_ranking_expression(query)

        return conditions, ranking_expr, params

    def _build_ranking_expression(self, query: SimpleSearchQuery) -> str:
        """Build SQL ranking expression that prioritizes title matches"""
        if not query.keywords:
            return "999"  # Default low rank

        # Count keyword matches in title and plot
        title_matches = []
        plot_matches = []

        for i, keyword in enumerate(query.keywords):
            # Using CASE WHEN for each keyword
            title_matches.append(f"CASE WHEN LOWER(mi.title) LIKE '%{self.normalizer.normalize(keyword)}%' THEN 1 ELSE 0 END")
            plot_matches.append(f"CASE WHEN LOWER(mi.plot) LIKE '%{self.normalizer.normalize(keyword)}%' THEN 1 ELSE 0 END")

        title_count = " + ".join(title_matches)
        plot_count = " + ".join(plot_matches)
        total_keywords = len(query.keywords)

        # Ranking logic:
        # 1. All keywords in title
        # 2. Some keywords in title  
        # 3. All keywords in plot
        # 4. Some keywords in plot
        ranking_expr = f"""
            CASE 
                WHEN ({title_count}) = {total_keywords} THEN 1
                WHEN ({title_count}) > 0 THEN 2
                WHEN ({plot_count}) = {total_keywords} THEN 3
                WHEN ({plot_count}) > 0 THEN 4
                ELSE 5
            END
        """

        return ranking_expr


# Global simple search engine instance
_simple_search_engine_instance = None


def get_simple_search_engine():
    """Get global simple search engine instance"""
    global _simple_search_engine_instance
    if _simple_search_engine_instance is None:
        _simple_search_engine_instance = SimpleSearchEngine()
    return _simple_search_engine_instance