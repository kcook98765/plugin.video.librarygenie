#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Handler Factory
Provides lazy instantiation of handlers to improve plugin startup performance
"""

from typing import Dict, Optional, Any, Callable
import time
from ..utils.kodi_log import get_kodi_logger


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
            from .main_menu_handler import MainMenuHandler
            self._handler_cache['main_menu'] = MainMenuHandler()
            self.logger.debug("Created MainMenuHandler instance")
        return self._handler_cache['main_menu']

    def get_search_handler(self):
        """Get SearchHandler instance (lazy loaded)"""
        if 'search' not in self._handler_cache:
            from .search_handler import SearchHandler
            self._handler_cache['search'] = SearchHandler()
            self.logger.debug("Created SearchHandler instance")
        return self._handler_cache['search']

    def get_lists_handler(self):
        """Get lists handler instance"""
        if 'lists' not in self._handler_cache:
            # FACTORY TIMING: Lists handler import
            import_start_time = time.time()
            from .lists_handler import ListsHandler
            import_end_time = time.time()
            self.logger.info(f"FACTORY: ListsHandler import took {import_end_time - import_start_time:.3f} seconds")
            
            # FACTORY TIMING: Lists handler instantiation
            instantiation_start_time = time.time()
            self._handler_cache['lists'] = ListsHandler(self.context)
            instantiation_end_time = time.time()
            self.logger.info(f"FACTORY: ListsHandler instantiation took {instantiation_end_time - instantiation_start_time:.3f} seconds")
        return self._handler_cache['lists']

    def get_favorites_handler(self):
        """Get FavoritesHandler instance (lazy loaded)"""
        if 'favorites' not in self._handler_cache:
            from .favorites_handler import FavoritesHandler
            self._handler_cache['favorites'] = FavoritesHandler()
            self.logger.debug("Created FavoritesHandler instance")
        return self._handler_cache['favorites']

    def get_tools_handler(self):
        """Get ToolsHandler instance (lazy loaded)"""
        if 'tools' not in self._handler_cache:
            from .tools_handler import ToolsHandler
            self._handler_cache['tools'] = ToolsHandler()
            self.logger.debug("Created ToolsHandler instance")
        return self._handler_cache['tools']

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
        # FACTORY TIMING: HandlerFactory creation
        factory_creation_start_time = time.time()
        _handler_factory = HandlerFactory()
        factory_creation_end_time = time.time()
        # Use direct logger since factory logger might not be ready yet
        logger = get_kodi_logger('lib.ui.handler_factory.global')
        logger.info(f"FACTORY: HandlerFactory creation took {factory_creation_end_time - factory_creation_start_time:.3f} seconds")
    return _handler_factory