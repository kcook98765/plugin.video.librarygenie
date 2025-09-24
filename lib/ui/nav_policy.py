
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Navigation Policy
Centralizes navigation semantics for PUSH vs REPLACE vs REFRESH decisions
"""

from typing import Literal, Optional, Dict, Any
from lib.utils.kodi_log import get_kodi_logger


class NavigationPolicy:
    """Determines navigation mode based on route transitions and context"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.nav_policy')

    def decide_mode(
        self, 
        current_route: Optional[str], 
        next_route: str, 
        reason: str = "navigation",
        current_params: Optional[Dict[str, Any]] = None,
        next_params: Optional[Dict[str, Any]] = None
    ) -> Literal['push', 'replace']:
        """
        Decide navigation mode based on route transition
        
        Rules:
        - Different logical page (route or id changes) → PUSH
        - Same page morph (sort/filter/pagination>1) → REPLACE
        """
        current_params = current_params or {}
        next_params = next_params or {}
        
        self.logger.debug("NAV POLICY: Deciding mode - current: %s, next: %s, reason: %s", 
                         current_route, next_route, reason)
        
        # If no current route, always push
        if not current_route:
            self.logger.debug("NAV POLICY: No current route → PUSH")
            return 'push'
        
        # Extract base action from routes (remove parameters)
        current_action = self._extract_base_action(current_route)
        next_action = self._extract_base_action(next_route)
        
        # Different actions always push
        if current_action != next_action:
            self.logger.debug("NAV POLICY: Different actions (%s → %s) → PUSH", current_action, next_action)
            return 'push'
        
        # Same action - check if it's a page morph or new page
        if self._is_page_morph(current_action, current_params, next_params):
            self.logger.debug("NAV POLICY: Page morph detected → REPLACE")
            return 'replace'
        else:
            self.logger.debug("NAV POLICY: Different page/content → PUSH")
            return 'push'

    def _extract_base_action(self, route: str) -> str:
        """Extract the base action from a route URL"""
        # Handle plugin URLs
        if 'action=' in route:
            parts = route.split('action=')
            if len(parts) > 1:
                action_part = parts[1].split('&')[0]
                return action_part
        
        # Handle direct action strings
        if not route.startswith('plugin://'):
            return route
        
        # Default fallback
        return route.split('?')[0] if '?' in route else route

    def _is_page_morph(
        self, 
        action: str, 
        current_params: Dict[str, Any], 
        next_params: Dict[str, Any]
    ) -> bool:
        """
        Determine if this is a page morph (same logical page, different view)
        vs a navigation to a different page
        """
        # Check for pagination beyond page 1 (page morphs)
        current_page = current_params.get('page', '1')
        next_page = next_params.get('page', '1')
        
        if current_page != '1' or next_page != '1':
            self.logger.debug("NAV POLICY: Pagination detected (current: %s, next: %s)", current_page, next_page)
            return True
        
        # Check for sort/filter changes (page morphs)
        morph_params = ['sort', 'filter', 'view_mode', 'search_query']
        for param in morph_params:
            if param in current_params or param in next_params:
                if current_params.get(param) != next_params.get(param):
                    self.logger.debug("NAV POLICY: %s change detected → page morph", param)
                    return True
        
        # Check for ID-based pages - different IDs = different pages
        id_params = ['list_id', 'folder_id', 'item_id']
        for param in id_params:
            current_id = current_params.get(param)
            next_id = next_params.get(param)
            if current_id != next_id:
                self.logger.debug("NAV POLICY: Different %s (%s → %s) → different page (PUSH)", param, current_id, next_id)
                return False
        
        # Special case for list views: same list_id = page morph (REPLACE)
        if action == 'show_list' and current_params.get('list_id') == next_params.get('list_id'):
            self.logger.debug("NAV POLICY: Same list_id (%s) → page morph (REPLACE)", current_params.get('list_id'))
            return True
        
        # If we're here, it's likely a page morph
        return True

    def should_refresh(self, reason: str) -> bool:
        """Determine if a refresh is needed instead of navigation"""
        refresh_reasons = [
            'content_updated',
            'item_added',
            'item_removed',
            'list_modified',
            'folder_modified',
            'cache_invalidation'
        ]
        
        should_refresh = reason in refresh_reasons
        self.logger.debug("NAV POLICY: Should refresh for reason '%s': %s", reason, should_refresh)
        return should_refresh


# Global policy instance
_nav_policy_instance = None


def get_nav_policy() -> NavigationPolicy:
    """Get global navigation policy instance"""
    global _nav_policy_instance
    if _nav_policy_instance is None:
        _nav_policy_instance = NavigationPolicy()
    return _nav_policy_instance


# Convenience functions for direct access
def decide_mode(
    current_route: Optional[str], 
    next_route: str, 
    reason: str = "navigation",
    current_params: Optional[Dict[str, Any]] = None,
    next_params: Optional[Dict[str, Any]] = None
) -> Literal['push', 'replace']:
    """Decide navigation mode based on route transition"""
    return get_nav_policy().decide_mode(current_route, next_route, reason, current_params, next_params)


def should_refresh(reason: str) -> bool:
    """Determine if a refresh is needed instead of navigation"""
    return get_nav_policy().should_refresh(reason)
