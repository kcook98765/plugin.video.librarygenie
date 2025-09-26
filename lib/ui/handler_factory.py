#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Handler Factory
Provides lazy instantiation of handlers to improve plugin startup performance
"""

import time
from typing import Dict, Optional, Any, Callable
from lib.utils.kodi_log import get_kodi_logger


class HandlerFactory:
    """Factory class for lazy handler instantiation"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.handler_factory')
        self._handler_cache: Dict[str, Any] = {}
        # Added context attribute, assuming it will be set elsewhere or passed during initialization
        self.context: Optional[Any] = None

    def get_main_menu_handler(self):
        """Get MainMenuHandler instance (lazy loaded)"""
        if 'main_menu' not in self._handler_cache:
            handler_start = time.time()
            from lib.ui.main_menu_handler import MainMenuHandler
            self._handler_cache['main_menu'] = MainMenuHandler()
            handler_time = (time.time() - handler_start) * 1000
            self.logger.debug("TIMING: MainMenuHandler instantiation took %.2f ms", handler_time)
        return self._handler_cache['main_menu']

    def get_search_handler(self):
        """Get SearchHandler instance (lazy loaded)"""
        if 'search' not in self._handler_cache:
            from lib.ui.search_handler import SearchHandler
            self._handler_cache['search'] = SearchHandler()
            self.logger.debug("Created SearchHandler instance")
        return self._handler_cache['search']

    def get_lists_handler(self):
        """Get lists handler instance"""
        if 'lists' not in self._handler_cache:
            handler_start = time.time()
            from lib.ui.lists_handler import ListsHandler
            self._handler_cache['lists'] = ListsHandler(self.context)
            handler_time = (time.time() - handler_start) * 1000
            self.logger.debug("TIMING: ListsHandler instantiation took %.2f ms", handler_time)
        return self._handler_cache['lists']

    def get_favorites_handler(self):
        """Get FavoritesHandler instance (lazy loaded)"""
        if 'favorites' not in self._handler_cache:
            from lib.ui.favorites_handler import FavoritesHandler
            self._handler_cache['favorites'] = FavoritesHandler()
            self.logger.debug("Created FavoritesHandler instance")
        return self._handler_cache['favorites']

    def get_tools_handler(self):
        """Get ToolsHandler instance (lazy loaded)"""
        if 'tools' not in self._handler_cache:
            from lib.ui.tools_handler import ToolsHandler
            self._handler_cache['tools'] = ToolsHandler()
            self.logger.debug("Created ToolsHandler instance")
        return self._handler_cache['tools']

    def get_bookmarks_handler(self):
        """Get BookmarksHandler instance (lazy loaded)"""
        if 'bookmarks' not in self._handler_cache:
            from lib.ui.bookmarks_handler import BookmarksHandler
            self._handler_cache['bookmarks'] = BookmarksHandler(self.context)
            self.logger.debug("Created BookmarksHandler instance")
        return self._handler_cache['bookmarks']

    def clear_cache(self):
        """Clear handler cache (useful for testing)"""
        self._handler_cache.clear()
        self.logger.debug("Cleared handler cache")


# Global factory instance
_handler_factory: Optional[HandlerFactory] = None


def get_handler_factory() -> HandlerFactory:
    """Get the global handler factory instance"""
    global _handler_factory
    if _handler_factory is None:
        _handler_factory = HandlerFactory()
    return _handler_factory