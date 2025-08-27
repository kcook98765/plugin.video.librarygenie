#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Handler UI
Provides UI bridge for search functionality with remote/local engine selection
"""

from __future__ import annotations

from typing import Dict, Any, List

import xbmcgui
import xbmcaddon
import xbmcplugin

from ..search.local_engine import LocalSearchEngine
from ..remote.search_client import search_remote, RemoteError
from ..auth.state import is_authorized
from ..auth.auth_helper import get_auth_helper
from ..ui.session_state import get_session_state
from ..utils.logger import get_logger


class SearchHandler:
    """Handles search UI and result display with engine switching"""

    def __init__(self, addon_handle):
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)
        self.local_engine = LocalSearchEngine()
        self._remote_fallback_notified = False

    def prompt_and_show(self):
        """Prompt user for search query and show results"""
        # Get search query from user
        addon = xbmcaddon.Addon()
        query = xbmcgui.Dialog().input(
            addon.getLocalizedString(35018),
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
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35021),
                addon.getLocalizedString(35022),
                xbmcgui.NOTIFICATION_ERROR
            )

    def _perform_search(self, query):
        """
        Perform search using remote or local engine with fallback

        Args:
            query: Search query string

        Returns:
            dict: Search results with metadata
        """
        # Engine switch: authorized users try remote first
        if is_authorized():
            try:
                self.logger.debug("Using remote search (authorized)")
                results = search_remote(query, page=1, page_size=100)
                self.logger.info(f"Remote search returned {len(results.get('items', []))} results")
                return results

            except RemoteError as e:
                self.logger.warning(f"Remote search failed, falling back to local: {e}")
                self._show_fallback_notification()
                return self._search_local(query, limit=200)

            except Exception as e:
                self.logger.error(f"Remote search error, falling back to local: {e}")
                self._show_fallback_notification()
                return self._search_local(query, limit=200)

        else:
            # Non-authorized users use local search
            self.logger.debug("Using local search (not authorized)")
            return self._search_local(query, limit=200)

    def _search_local(self, query, limit=200):
        """Perform local search using local engine"""
        try:
            return self.local_engine.search(query, limit=limit)
        except Exception as e:
            self.logger.error(f"Local search failed: {e}")
            return {'items': [], 'total': 0, 'used_remote': False}

    def _show_fallback_notification(self):
        """Show one-shot notification about remote fallback (don't spam)"""
        session_state = get_session_state()

        if session_state.should_show_notification("remote_search_fallback", 600):
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35023),  # "Remote unavailable, using local"
                xbmcgui.NOTIFICATION_WARNING,
                4000
            )

    def _display_results(self, results, query):
        """Display search results in Kodi"""
        items = results.get('items', [])

        if not items:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35019),
                addon.getLocalizedString(35020) % query,
                xbmcgui.NOTIFICATION_INFO
            )
            return

        # Add directory items for each result
        for item in items:
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
                'title': item.get('title', item.get('label', 'Unknown')),
                'mediatype': item.get('type', 'movie')
            }

            if item.get('year'):
                info['year'] = item['year']
            if item.get('plot'):
                info['plot'] = item['plot']
            if item.get('rating'):
                info['rating'] = item['rating']

            list_item.setInfo('video', info)

            # Set playable if we have a path
            is_playable = bool(item.get('path'))
            list_item.setProperty('IsPlayable', 'true' if is_playable else 'false')

            # Add source indicator for remote items
            if item.get('_source') == 'remote':
                if item.get('_local_mapped'):
                    list_item.setProperty('IsLocal', 'true')
                else:
                    list_item.setProperty('IsRemote', 'true')

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

        # Log result summary
        used_remote = results.get('used_remote', False)
        source = "remote" if used_remote else "local"
        self.logger.info(f"Displayed {len(items)} {source} search results for '{query}'")

    def search_with_fallback(self, query, page=1, page_size=100):
        """Search with remote first, fallback to local"""
        if not query or not query.strip():
            return {'items': [], 'total': 0, 'used_remote': False}

        query = query.strip()

        # Engine switch logic
        if is_authorized():
            try:
                remote_results = search_remote(query, page, page_size)
                if remote_results.get('items'):
                    self.logger.info(f"Remote search successful: {len(remote_results['items'])} results")
                    return remote_results

            except RemoteError as e:
                self.logger.warning(f"Remote search failed: {e}")
                self._show_fallback_notification()

            except Exception as e:
                self.logger.error(f"Remote search error: {e}")
                self._show_fallback_notification()

        # Use local search
        try:
            local_results = self.local_engine.search(query, limit=page_size, offset=(page-1)*page_size)
            self.logger.info(f"Local search: {len(local_results.get('items', []))} results")
            return local_results

        except Exception as e:
            self.logger.error(f"Local search failed: {e}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35025),  # "Search failed"
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return {'items': [], 'total': 0, 'used_remote': False}

    def handle_search_request(self, query):
        """Handle search request from UI"""
        if not query or not query.strip():
            return []

        query = query.strip()
        self.logger.info(f"Search request: '{query}'")

        try:
            results = self.search_with_fallback(query)
            return results.get('items', [])

        except Exception as e:
            self.logger.error(f"Search request failed: {e}")
            return []

    def handle_remote_search_request(self, query):
        """Handle remote-only search request with authorization check"""
        if not query or not query.strip():
            return []

        # Check authorization and prompt if needed
        auth_helper = get_auth_helper()
        if not auth_helper.check_authorization_or_prompt("remote search"):
            return []

        query = query.strip()
        self.logger.info(f"Remote search request: '{query}'")

        try:
            remote_results = search_remote(query)
            return remote_results.get('items', [])

        except Exception as e:
            self.logger.error(f"Remote search failed: {e}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35026),  # "Remote search failed"
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return []