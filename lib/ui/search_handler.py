#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Handler
Provides UI bridge for search functionality with remote/local engine selection
"""

import xbmcgui
import xbmcaddon

from ..search.enhanced_search_engine import get_enhanced_search_engine
from ..remote.search_client import search_remote, RemoteError
from ..auth.state import is_authorized
from ..auth.auth_helper import get_auth_helper
from ..ui.session_state import get_session_state
from ..utils.logger import get_logger

import xbmcplugin


class SearchHandler:
    """Handles search UI and result display"""

    def __init__(self, addon_handle):
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)

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
                results = self._search_local(query, limit=200)

        else:
            # Use local search when not authorized
            self.logger.debug("Using local search (not authorized)")
            results = self._search_local(query, limit=200)

        return results

    def _search_local(self, query, limit=200):
        """Perform local search using enhanced search engine"""
        try:
            search_engine = get_enhanced_search_engine()
            local_results = search_engine.search(query, limit=limit)
            return local_results.get('items', [])
        except Exception as e:
            self.logger.error(f"Local search failed: {e}")
            return []

    def _display_results(self, results, query):
        """Display search results in Kodi"""
        if not results:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35019),
                addon.getLocalizedString(35020) % query,
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

    def search_with_fallback(self, query, page=1, page_size=100):
        """Search with remote first, fallback to local"""
        results = []
        used_remote = False
        session_state = get_session_state()

        # Try remote search if authorized
        if is_authorized():
            try:
                remote_results = search_remote(query, page, page_size)
                if remote_results.get('items'):
                    results = remote_results['items']
                    used_remote = True
                    self.logger.info(f"Remote search successful: {len(results)} results")

            except RemoteError as e:
                self.logger.warning(f"Remote search failed: {e}")
                # Show fallback notification (once per session)
                if session_state.should_show_notification("remote_search_fallback", 600):
                    addon = xbmcaddon.Addon()
                    xbmcgui.Dialog().notification(
                        addon.getLocalizedString(35002),
                        addon.getLocalizedString(35023),
                        xbmcgui.NOTIFICATION_WARNING,
                        4000
                    )

            except Exception as e:
                self.logger.error(f"Remote search error: {e}")
                # Show fallback notification (once per session)
                if session_state.should_show_notification("remote_search_error", 600):
                    addon = xbmcaddon.Addon()
                    xbmcgui.Dialog().notification(
                        addon.getLocalizedString(35002),
                        addon.getLocalizedString(35024),
                        xbmcgui.NOTIFICATION_WARNING,
                        4000
                    )

        # Use local search if remote failed or not authorized
        if not results:
            try:
                search_engine = get_enhanced_search_engine()
                local_results = search_engine.search(query, limit=page_size, offset=(page-1)*page_size)
                results = local_results.get('items', [])
                self.logger.info(f"Local search: {len(results)} results")

            except Exception as e:
                self.logger.error(f"Local search failed: {e}")
                results = []
                # Show error notification
                addon = xbmcaddon.Addon()
                xbmcgui.Dialog().notification(
                    addon.getLocalizedString(35002),
                    addon.getLocalizedString(35025),
                    xbmcgui.NOTIFICATION_ERROR,
                    4000
                )

        return {
            'items': results,
            'used_remote': used_remote,
            'total': len(results)
        }

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
                addon.getLocalizedString(35026),
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return []