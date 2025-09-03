#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Context
Encapsulates request data and shared resources for handlers
"""

import sys
from urllib.parse import parse_qsl
from typing import Dict, Any, Optional

import xbmcaddon
from ..utils.logger import get_logger
from ..auth.state import is_authorized


class PluginContext:
    """Encapsulates all request context and shared resources"""

    def __init__(self):
        # Parse plugin arguments
        self.addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        self.base_url = sys.argv[0] if len(sys.argv) > 0 else ""
        query_string = sys.argv[2][1:] if len(sys.argv) > 2 and len(sys.argv[2]) > 1 else ""

        # Parse query parameters
        self.params = dict(parse_qsl(query_string))

        # Shared resources
        self.addon = xbmcaddon.Addon()
        self.logger = get_logger(__name__)

        # Cache auth state
        self._auth_state = None

        # Service singletons (lazy loaded)
        self._query_manager = None
        self._favorites_manager = None

        # Navigation context - generate breadcrumb automatically
        self.breadcrumb_path = self._generate_breadcrumb()

        self.logger.debug(f"PluginContext created: handle={self.addon_handle}, base_url={self.base_url}, params={self.params}")
        if self.breadcrumb_path:
            self.logger.debug(f"Generated breadcrumb: {self.breadcrumb_path}")

    @property
    def is_authorized(self) -> bool:
        """Get cached authorization state"""
        if self._auth_state is None:
            self._auth_state = is_authorized()
        return self._auth_state

    @property
    def query_manager(self):
        """Get query manager singleton"""
        if self._query_manager is None:
            from ..data.query_manager import get_query_manager
            self._query_manager = get_query_manager()
            if not self._query_manager.initialize():
                self.logger.error("Failed to initialize query manager")
                return None
        return self._query_manager

    @property
    def favorites_manager(self):
        """Get favorites manager singleton"""
        if self._favorites_manager is None:
            from ..kodi.favorites_manager import get_phase4_favorites_manager
            self._favorites_manager = get_phase4_favorites_manager()
        return self._favorites_manager

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get parameter value with optional default"""
        return self.params.get(key, default)

    def get_params(self) -> Dict[str, Any]:
        """Get all parameters"""
        return self.params

    def require_param(self, key: str) -> Any:
        """Get required parameter, raises ValueError if missing"""
        value = self.params.get(key)
        if value is None:
            raise ValueError(f"Required parameter '{key}' is missing")
        return value

    def build_url(self, action: str, **kwargs) -> str:
        """Build plugin URL with action and parameters"""
        params = [f"action={action}"]
        for key, value in kwargs.items():
            if value is not None:
                params.append(f"{key}={value}")

        query = "&".join(params)
        return f"{self.base_url}?{query}"

    def _generate_breadcrumb(self) -> Optional[str]:
        """Generate breadcrumb path for current context"""
        try:
            action = self.params.get('action', '')
            if not action:
                return None
            
            # Import here to avoid circular imports
            from .breadcrumb_helper import get_breadcrumb_helper
            breadcrumb_helper = get_breadcrumb_helper()
            return breadcrumb_helper.get_breadcrumb_for_action(action, self.params, self.query_manager)
        except Exception as e:
            self.logger.error(f"Error generating breadcrumb: {e}")
            return None