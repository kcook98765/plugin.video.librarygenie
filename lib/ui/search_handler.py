#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Search Handler
Provides UI bridge for search functionality with remote/local engine selection
"""

import xbmcgui
import xbmcplugin
from ..auth.state import is_authorized
from ..remote.search_client import search_remote, RemoteError
from ..search.local_engine import search_local
from ..utils.logger import get_logger


class SearchHandler:
    """Handles search UI and result display"""

    def __init__(self, addon_handle):
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)

    def prompt_and_show(self):
        """Prompt user for search query and show results"""
        # Get search query from user
        query = xbmcgui.Dialog().input(
            "Search Movies",
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not query or not query.strip():
            return

        # Perform search with engine selection
        try:
            results = self._perform_search(query.strip())
            self._display_results(results, query)

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            xbmcgui.Dialog().notification(
                "Search Error",
                "Search failed. Check logs for details.",
                xbmcgui.NOTIFICATION_ERROR
            )

    def _perform_search(self, query):
        """
        Perform search using remote or local engine with fallback

        Args:
            query: Search query string

        Returns:
            list: Search results
        """
        results = []

        # Try remote search if authorized
        if is_authorized():
            try:
                self.logger.debug("Using remote search (authorized)")
                remote_response = search_remote(query, page=1, page_size=100)
                results = remote_response.get('items', [])
                self.logger.info(f"Remote search returned {len(results)} results")

            except RemoteError as e:
                self.logger.warning(f"Remote search failed, falling back to local: {e}")
                results = search_local(query, limit=200)

        else:
            # Use local search when not authorized
            self.logger.debug("Using local search (not authorized)")
            results = search_local(query, limit=200)

        return results

    def _display_results(self, results, query):
        """Display search results in Kodi"""
        if not results:
            xbmcgui.Dialog().notification(
                "No Results",
                f"No movies found for '{query}'",
                xbmcgui.NOTIFICATION_INFO
            )
            return

        # Add directory items for each result
        for item in results:
            list_item = xbmcgui.ListItem(
                label=item.get('label', 'Unknown'),
                label2=item.get('year', '')
            )

            # Set artwork if available
            art = item.get('art', {})
            if art:
                list_item.setArt(art)

            # Set info
            info = {
                'title': item.get('label', 'Unknown'),
                'mediatype': item.get('type', 'movie')
            }

            if item.get('year'):
                info['year'] = item['year']

            list_item.setInfo('video', info)

            # Set playable if we have a path
            is_playable = bool(item.get('path'))
            list_item.setProperty('IsPlayable', 'true' if is_playable else 'false')

            # Add to directory
            url = item.get('path', '')
            xbmcplugin.addDirectoryItem(
                self.addon_handle,
                url,
                list_item,
                isFolder=False
            )

        # Finish directory
        xbmcplugin.endOfDirectory(self.addon_handle)

        self.logger.info(f"Displayed {len(results)} search results for '{query}'")