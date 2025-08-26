#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Phase 5 Search Handler
UI integration for Phase 5 enhanced search functionality
"""

import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode
from typing import Dict, Any, Optional, List

from ..search.enhanced_query_interpreter import get_enhanced_query_interpreter, SearchQuery
from ..search.enhanced_search_engine import get_enhanced_search_engine, SearchResult
from ..ui.listitem_renderer import get_listitem_renderer
from ..config import get_config
from ..utils.logger import get_logger


class SearchHandler:
    """Phase 5: Enhanced search handler with improved UI and navigation"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.query_interpreter = get_enhanced_query_interpreter()
        self.search_engine = get_enhanced_search_engine()
        self.movie_renderer = get_listitem_renderer()

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform search and return results list"""
        try:
            if not query or not query.strip():
                return []

            self.logger.info(f"Performing search for: '{query}'")

            # Parse the query using enhanced query interpreter
            parsed_query = self.query_interpreter.parse_query(query)
            self.logger.debug(f"Parsed query: {parsed_query}")

            # Execute search using enhanced search engine
            search_results = self.search_engine.search(parsed_query)
            self.logger.debug(f"Found {len(search_results)} search results")

            # Convert search results to list format
            results = []
            for result in search_results:
                # Convert SearchResult to dict format expected by listitem renderer
                item_dict = {
                    'title': result.title,
                    'year': result.year,
                    'plot': getattr(result, 'plot', ''),
                    'poster': getattr(result, 'poster', ''),
                    'fanart': getattr(result, 'fanart', ''),
                    'rating': getattr(result, 'rating', 0.0),
                    'genre': getattr(result, 'genre', ''),
                    'director': getattr(result, 'director', ''),
                    'cast': getattr(result, 'cast', ''),
                    'play': getattr(result, 'play_url', ''),
                    'media_type': getattr(result, 'media_type', 'movie')
                }
                results.append(item_dict)

            return results

        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []

    def show_search_dialog(self) -> bool:
        """Show search input dialog with Phase 5 enhancements"""
        try:
            keyboard = xbmcgui.Dialog().input(
                heading="Search Movies",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not keyboard:
                return False

            query = keyboard.strip()
            if not query:
                return False

            self.logger.info(f"User search query: '{query}'")
            return self._perform_search(query)

        except Exception as e:
            self.logger.error(f"Search dialog error: {e}")
            return False

    def show_search_results(self, params: Dict[str, Any]) -> bool:
        """Show search results with Phase 5 enhanced paging"""
        try:
            # Parse query from URL parameters
            query = self._parse_query_from_params(params)

            # Execute search
            result = self.search_engine.search(query)

            # Build directory listing
            self._build_search_results_directory(query, result)

            return True

        except Exception as e:
            self.logger.error(f"Error showing search results: {e}")
            self._show_search_error()
            return False

    def _parse_query_from_params(self, params: Dict[str, Any]) -> SearchQuery:
        """Parse search query from URL parameters"""
        try:
            # Extract search parameters
            query_text = params.get("q", "")
            scope_type = params.get("scope_type", "library")
            scope_id = params.get("scope_id")
            sort_method = params.get("sort", "title_asc")
            page_offset = int(params.get("offset", "0"))

            # Convert scope_id to int if present
            if scope_id:
                scope_id = int(scope_id)

            # Parse query with parameters
            query = self.query_interpreter.parse_query(
                query_text,
                scope_type=scope_type,
                scope_id=scope_id,
                sort_method=sort_method,
                page_offset=page_offset
            )

            return query

        except Exception as e:
            self.logger.error(f"Error parsing query from params: {e}")
            # Return empty query as fallback
            return SearchQuery()

    def _navigate_to_search_results(self, query: SearchQuery):
        """Navigate to search results page with query parameters"""
        try:
            # Build URL parameters
            params = {
                "action": "search_results",
                "q": query.original_text,
                "scope_type": query.scope_type,
                "sort": query.sort_method,
                "offset": str(query.page_offset)
            }

            if query.scope_id:
                params["scope_id"] = str(query.scope_id)

            # Build URL
            base_url = f"plugin://{self.config.addon_id}/"
            url = f"{base_url}?{urlencode(params)}"

            # Navigate
            xbmc.executebuiltin(f"Container.Update({url})")

        except Exception as e:
            self.logger.error(f"Error navigating to search results: {e}")

    def _build_search_results_directory(self, query: SearchQuery, result: SearchResult):
        """Build Kodi directory with search results and Phase 5 paging"""
        try:
            handle = int(self.config.addon_handle)

            # Add search summary header
            self._add_search_summary_item(query, result)

            # Add previous page navigation if needed
            if result.has_prev_page:
                self._add_prev_page_item(query)

            # Add movie results
            for movie in result.items:
                self._add_movie_result_item(movie, query)

            # Add next page navigation if needed
            if result.has_next_page:
                self._add_next_page_item(query)

            # Add empty state if no results
            if not result.items and not self.query_interpreter.is_empty_query(query):
                self._add_no_results_item(query)

            # Finalize directory
            xbmcplugin.setContent(handle, 'movies')
            xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=False)

        except Exception as e:
            self.logger.error(f"Error building search results directory: {e}")
            xbmcplugin.endOfDirectory(handle, succeeded=False)

    def _add_search_summary_item(self, query: SearchQuery, result: SearchResult):
        """Add search summary header item"""
        try:
            handle = int(self.config.addon_handle)

            # Build summary text
            summary_parts = [
                f"Results: {result.total_count}",
                f"Page {result.current_page}/{result.page_count}",
                f"Sorted by {result.sort_description}"
            ]

            if result.scope_description:
                summary_parts.append(f"Scope: {result.scope_description}")

            summary_text = " • ".join(summary_parts)

            # Create list item
            list_item = xbmcgui.ListItem(summary_text)
            list_item.setProperty('IsPlayable', 'false')
            list_item.setInfo('video', {'title': summary_text, 'plot': result.query_summary})

            # Add to directory (non-clickable)
            xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)

        except Exception as e:
            self.logger.debug(f"Error adding search summary: {e}")

    def _add_prev_page_item(self, query: SearchQuery):
        """Add previous page navigation item"""
        try:
            handle = int(self.config.addon_handle)

            # Calculate previous page offset
            prev_offset = max(0, query.page_offset - query.page_size)

            # Build URL for previous page
            params = {
                "action": "search_results",
                "q": query.original_text,
                "scope_type": query.scope_type,
                "sort": query.sort_method,
                "offset": str(prev_offset)
            }

            if query.scope_id:
                params["scope_id"] = str(query.scope_id)

            url = f"plugin://{self.config.addon_id}/?{urlencode(params)}"

            # Create list item
            list_item = xbmcgui.ListItem("◀ Previous page...")  # TODO: Localize
            list_item.setProperty('IsPlayable', 'false')
            list_item.setInfo('video', {'title': 'Previous page', 'plot': 'Go to previous page of results'})

            # Add to directory
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=True)

        except Exception as e:
            self.logger.debug(f"Error adding previous page item: {e}")

    def _add_next_page_item(self, query: SearchQuery):
        """Add next page navigation item"""
        try:
            handle = int(self.config.addon_handle)

            # Calculate next page offset
            next_offset = query.page_offset + query.page_size

            # Build URL for next page
            params = {
                "action": "search_results",
                "q": query.original_text,
                "scope_type": query.scope_type,
                "sort": query.sort_method,
                "offset": str(next_offset)
            }

            if query.scope_id:
                params["scope_id"] = str(query.scope_id)

            url = f"plugin://{self.config.addon_id}/?{urlencode(params)}"

            # Create list item
            list_item = xbmcgui.ListItem("Next page... ▶")  # TODO: Localize
            list_item.setProperty('IsPlayable', 'false')
            list_item.setInfo('video', {'title': 'Next page', 'plot': 'Go to next page of results'})

            # Add to directory
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=True)

        except Exception as e:
            self.logger.debug(f"Error adding next page item: {e}")

    def _add_movie_result_item(self, movie: Dict[str, Any], query: SearchQuery):
        """Add movie result item with Phase 11 rich metadata"""
        try:
            handle = int(self.config.addon_handle)

            # Use listitem renderer for consistent presentation
            list_item = self.movie_renderer.create_listitem(
                movie, 
                base_url=f"plugin://{self.config.addon_id}/",
                action="play_movie"
            )

            # Build playback URL
            kodi_id = movie.get('kodi_id')
            if kodi_id:
                play_url = f"plugin://{self.config.addon_id}/?action=play_movie&kodi_id={kodi_id}"
                xbmcplugin.addDirectoryItem(handle, play_url, list_item, isFolder=False)

        except Exception as e:
            self.logger.debug(f"Error adding movie result item: {e}")

    def _add_no_results_item(self, query: SearchQuery):
        """Add no results found item with helpful hints"""
        try:
            handle = int(self.config.addon_handle)

            # Get localized hint
            hint = self.query_interpreter.get_no_results_hint(query)

            # Create list item
            list_item = xbmcgui.ListItem("No matches found")  # TODO: Localize
            list_item.setProperty('IsPlayable', 'false')
            list_item.setInfo('video', {
                'title': 'No matches found',
                'plot': hint
            })

            # Add to directory (non-clickable)
            xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)

        except Exception as e:
            self.logger.debug(f"Error adding no results item: {e}")

    def _show_search_error(self):
        """Show search error message"""
        try:
            dialog = xbmcgui.Dialog()
            dialog.notification(
                "Search Error",  # TODO: Localize
                "Unable to perform search",  # TODO: Localize
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
        except Exception as e:
            self.logger.error(f"Error showing search error dialog: {e}")


# Global search handler instance
_search_handler_instance = None


def get_search_handler():
    """Get global search handler instance"""
    global _search_handler_instance
    if _search_handler_instance is None:
        _search_handler_instance = SearchHandler()
    return _search_handler_instance