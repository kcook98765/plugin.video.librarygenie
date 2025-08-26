#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Search UI Handler
Handles search user interface and result presentation
"""

from typing import Optional
from urllib.parse import urlencode

import xbmcgui
import xbmcplugin

from ..search.local_engine import search_local
from ..auth.state import is_authorized
from ..utils.logger import get_logger
from ..config import get_config


class SearchUI:
    """Handles search user interface operations"""

    def __init__(self, handle: int, base_url: str):
        self.handle = handle
        self.base_url = base_url
        self.logger = get_logger(__name__)
        self.config = get_config()

    def prompt_and_show(self):
        """Prompt user for search query and display results"""
        # Get search query from user
        query = xbmcgui.Dialog().input(
            "Search Movies & TV Shows",
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not query or not query.strip():
            # User cancelled or entered empty query
            self._show_empty_directory()
            return

        self.logger.info(f"User search query: '{query}'")

        # For Phase 3, always use local search
        # Phase 5 will add remote search when authorized
        self._show_local_results(query)

    def _show_local_results(self, query: str):
        """Show local search results"""
        try:
            # Get search limit from config
            limit = self.config.get_int("search_page_size", 50)

            # Perform local search
            results = search_local(query, limit=limit)

            if not results:
                self._show_no_results(query)
                return

            # Add results to directory
            for item in results:
                self._add_search_result_item(item)

            # Add search info
            info_label = f"Local search: {len(results)} result(s) for '{query}'"
            if len(results) >= limit:
                info_label += f" (limited to {limit})"

            li = xbmcgui.ListItem(f"[COLOR gray]{info_label}[/COLOR]")
            xbmcplugin.addDirectoryItem(self.handle, "", li, False)

            xbmcplugin.endOfDirectory(self.handle)

        except Exception as e:
            self.logger.error(f"Error showing local search results: {e}")
            self._show_error("Search failed. Please try again.")

    def _add_search_result_item(self, item: dict):
        """Add a single search result item to the directory"""
        try:
            label = item.get('label', 'Unknown Item')
            path = item.get('path', '')
            art = item.get('art', {})
            item_type = item.get('type', 'unknown')

            # Create list item
            li = xbmcgui.ListItem(label)

            # Set artwork
            if art:
                li.setArt(art)

            # Set info based on type
            if item_type == 'movie':
                self._set_movie_info(li, item)
            elif item_type == 'episode':
                self._set_episode_info(li, item)

            # Set as playable
            li.setProperty('IsPlayable', 'true')

            # Add to directory
            xbmcplugin.addDirectoryItem(
                self.handle,
                path,
                li,
                False  # Not a folder
            )

        except Exception as e:
            self.logger.error(f"Error adding search result item: {e}")

    def _set_movie_info(self, li: xbmcgui.ListItem, item: dict):
        """Set movie-specific info for list item"""
        info = {
            'mediatype': 'movie',
            'title': item.get('title', ''),
            'plot': item.get('plot', ''),
            'rating': item.get('rating', 0.0),
            'genre': item.get('genre', []),
            'director': item.get('director', []),
            'duration': item.get('runtime', 0),
            'mpaa': item.get('mpaa', ''),
            'imdbnumber': item.get('imdbnumber', '')
        }

        year = item.get('year')
        if year:
            info['year'] = year

        li.setInfo('video', info)

    def _set_episode_info(self, li: xbmcgui.ListItem, item: dict):
        """Set episode-specific info for list item"""
        info = {
            'mediatype': 'episode',
            'title': item.get('title', ''),
            'tvshowtitle': item.get('showtitle', ''),
            'season': item.get('season', 0),
            'episode': item.get('episode', 0),
            'plot': item.get('plot', ''),
            'rating': item.get('rating', 0.0),
            'duration': item.get('runtime', 0),
            'aired': item.get('firstaired', '')
        }

        li.setInfo('video', info)

    def _show_no_results(self, query: str):
        """Show message when no results found"""
        message = f"No results found for '{query}'"
        li = xbmcgui.ListItem(f"[COLOR orange]{message}[/COLOR]")
        xbmcplugin.addDirectoryItem(self.handle, "", li, False)
        xbmcplugin.endOfDirectory(self.handle)

    def _show_error(self, message: str):
        """Show error message"""
        li = xbmcgui.ListItem(f"[COLOR red]Error: {message}[/COLOR]")
        xbmcplugin.addDirectoryItem(self.handle, "", li, False)
        xbmcplugin.endOfDirectory(self.handle)

    def _show_empty_directory(self):
        """Show empty directory (for cancelled searches)"""
        xbmcplugin.endOfDirectory(self.handle)