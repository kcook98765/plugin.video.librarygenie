#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Hot Use Cases
Performance-optimized consolidation of the most frequently used business logic
This module minimizes imports and consolidates hot-path operations for low-power devices
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Only import essentials - lazy load everything else
from ..utils.logger import get_logger
from ..data import get_connection_manager, get_query_manager


class HotUseCases:
    """Consolidated hot-path business logic with minimal import overhead"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.query_manager = get_query_manager()
        
        # Cache frequently used queries
        self._query_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
    # --- SEARCH OPERATIONS ---
    
    def search_basic(self, search_terms: str, search_scope: str = "both", match_logic: str = "all", 
                    scope_type: str = None, scope_id: str = None, page_size: int = 100) -> Dict[str, Any]:
        """
        Basic search with minimal imports - consolidated from SimpleSearchEngine
        Returns: {items: [], total_count: int, query_summary: str, search_duration_ms: int}
        """
        start_time = datetime.now()
        
        try:
            if not search_terms or not search_terms.strip():
                return {
                    "items": [],
                    "total_count": 0,
                    "query_summary": "Empty search",
                    "search_duration_ms": 0
                }
            
            # Normalize keywords inline to avoid imports
            keywords = [kw.lower().strip() for kw in search_terms.split() if kw.strip()]
            
            # Build SQL query directly (consolidated logic)
            sql_query, params = self._build_search_sql(
                keywords, search_scope, match_logic, scope_type, scope_id, page_size
            )
            
            # Execute search
            items = self.conn_manager.execute_query(sql_query, params)
            result_items = [dict(item) if hasattr(item, 'keys') else item for item in items or []]
            
            # Calculate duration
            duration = datetime.now() - start_time
            duration_ms = int(duration.total_seconds() * 1000)
            
            result = {
                "items": result_items,
                "total_count": len(result_items),
                "query_summary": f"Search for: {search_terms}",
                "search_duration_ms": duration_ms
            }
            
            self.logger.debug(f"Basic search completed: {result['total_count']} results in {duration_ms}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"Basic search error: {e}")
            return {
                "items": [],
                "total_count": 0,
                "query_summary": "Search error",
                "search_duration_ms": 0
            }
    
    def _build_search_sql(self, keywords: List[str], search_scope: str, match_logic: str,
                         scope_type: str, scope_id: str, page_size: int) -> Tuple[str, List[Any]]:
        """Build search SQL with ranking - consolidated logic"""
        params = []
        
        # Base SELECT with ranking
        if scope_type == "list" and scope_id:
            select_clause = """
                SELECT DISTINCT mi.id, mi.kodi_id, mi.title, mi.year, mi.play as file_path, 
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.created_at, 
                       mi.poster, mi.fanart, mi.plot, mi.rating, mi.duration as runtime,
                       mi.genre, mi.director, 0 as playcount, mi.kodi_id as movieid,
                       {ranking_expression} as search_rank
                FROM media_items mi
                INNER JOIN list_items li ON li.media_item_id = mi.id
            """
            where_clauses = ["li.list_id = ?"]
            params.append(scope_id)
        else:
            select_clause = """
                SELECT mi.id, mi.kodi_id, mi.title, mi.year, mi.play as file_path, 
                       mi.imdbnumber as imdb_id, mi.tmdb_id, mi.created_at, 
                       mi.art, mi.plot, mi.rating, mi.duration as runtime,
                       mi.genre, mi.director, 0 as playcount, mi.kodi_id as movieid,
                       {ranking_expression} as search_rank
                FROM media_items mi
            """
            where_clauses = ["1=1"]
        
        # Build search conditions inline
        title_conditions = []
        plot_conditions = []
        
        for keyword in keywords:
            if search_scope in ["title", "both"]:
                title_conditions.append("LOWER(mi.title) LIKE ?")
                params.append(f"%{keyword}%")
            
            if search_scope in ["plot", "both"]:
                plot_conditions.append("LOWER(mi.plot) LIKE ?")
                params.append(f"%{keyword}%")
        
        # Combine conditions
        field_conditions = []
        
        if title_conditions:
            if match_logic == "all":
                field_conditions.append(f"({' AND '.join(title_conditions)})")
            else:
                field_conditions.append(f"({' OR '.join(title_conditions)})")
        
        if plot_conditions:
            if match_logic == "all":
                field_conditions.append(f"({' AND '.join(plot_conditions)})")
            else:
                field_conditions.append(f"({' OR '.join(plot_conditions)})")
        
        # Main search condition
        if field_conditions:
            if search_scope == "both":
                main_condition = f"({' OR '.join(field_conditions)})"
            else:
                main_condition = field_conditions[0]
            where_clauses.append(main_condition)
        
        # Build ranking expression inline
        ranking_expr = self._build_ranking_expr(keywords)
        
        # Complete query
        select_clause = select_clause.format(ranking_expression=ranking_expr)
        where_clause = " AND ".join(where_clauses)
        order_clause = "search_rank ASC, LOWER(mi.title) ASC"
        
        full_query = f"{select_clause} WHERE {where_clause} ORDER BY {order_clause}"
        
        if page_size > 0:
            full_query += f" LIMIT {page_size}"
        
        return full_query, params
    
    def _build_ranking_expr(self, keywords: List[str]) -> str:
        """Build ranking expression - prioritizes title matches"""
        if not keywords:
            return "999"
        
        title_matches = []
        plot_matches = []
        
        for keyword in keywords:
            title_matches.append(f"CASE WHEN LOWER(mi.title) LIKE '%{keyword}%' THEN 1 ELSE 0 END")
            plot_matches.append(f"CASE WHEN LOWER(mi.plot) LIKE '%{keyword}%' THEN 1 ELSE 0 END")
        
        title_count = " + ".join(title_matches)
        plot_count = " + ".join(plot_matches)
        total_keywords = len(keywords)
        
        return f"""
            CASE 
                WHEN ({title_count}) = {total_keywords} THEN 1
                WHEN ({title_count}) > 0 THEN 2
                WHEN ({plot_count}) = {total_keywords} THEN 3
                WHEN ({plot_count}) > 0 THEN 4
                ELSE 5
            END
        """
    
    # --- LIST OPERATIONS ---
    
    def list_browse_basic(self, list_id: Optional[str] = None, folder_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Basic list browsing with caching - consolidated from ListsHandler
        Returns: {lists: [], folders: [], total_count: int}
        """
        cache_key = f"browse_{list_id}_{folder_id}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            if not self.query_manager.initialize():
                return {"lists": [], "folders": [], "total_count": 0}
            
            if list_id:
                # Get specific list items
                items = self.query_manager.get_list_items(list_id)
                result = {
                    "items": items or [],
                    "total_count": len(items or []),
                    "list_id": list_id
                }
            else:
                # Get all lists and folders
                all_lists = self.query_manager.get_all_lists_with_folders()
                all_folders = self.query_manager.get_all_folders()
                
                # Filter by folder if specified
                if folder_id:
                    all_lists = [item for item in all_lists if item.get('folder_id') == folder_id]
                
                # Filter out Kodi Favorites from main view
                user_lists = [item for item in all_lists if item.get('name') != 'Kodi Favorites']
                
                result = {
                    "lists": user_lists,
                    "folders": all_folders or [],
                    "total_count": len(user_lists) + len(all_folders or [])
                }
            
            # Cache result
            self._cache_result(cache_key, result)
            return result
            
        except Exception as e:
            self.logger.error(f"List browse error: {e}")
            return {"lists": [], "folders": [], "total_count": 0}
    
    # --- FAVORITES OPERATIONS ---
    
    def get_favorites_minimal(self, show_unmapped: bool = True) -> List[Dict[str, Any]]:
        """
        Get favorites with minimal processing - consolidated from FavoritesHandler
        """
        cache_key = f"favorites_{show_unmapped}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Lazy import favorites manager only when needed
            from ..kodi.favorites_manager import get_favorites_manager
            
            favorites_manager = get_favorites_manager()
            if not favorites_manager:
                return []
            
            favorites = favorites_manager.get_mapped_favorites(show_unmapped=show_unmapped)
            
            # Cache for 5 minutes
            self._cache_result(cache_key, favorites)
            return favorites
            
        except Exception as e:
            self.logger.error(f"Get favorites error: {e}")
            return []
    
    # --- CACHING ---
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached result if not expired"""
        if cache_key in self._query_cache:
            cached_item = self._query_cache[cache_key]
            if datetime.now().timestamp() - cached_item['timestamp'] < self._cache_ttl:
                return cached_item['data']
            else:
                del self._query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, data: Any):
        """Cache result with timestamp"""
        self._query_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now().timestamp()
        }
    
    def clear_cache(self):
        """Clear all cached results"""
        self._query_cache.clear()


# Global instance
_hot_use_cases_instance = None


def get_hot_use_cases():
    """Get global hot use cases instance"""
    global _hot_use_cases_instance
    if _hot_use_cases_instance is None:
        _hot_use_cases_instance = HotUseCases()
    return _hot_use_cases_instance