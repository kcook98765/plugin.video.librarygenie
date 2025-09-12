#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Session State Manager
Tracks UI state to prevent notification spam and manage user experience
"""

import time
from typing import Dict, Any, List, Optional

from ..utils.logger import get_logger


class SessionState:
    """Manages session-specific UI state"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._notifications_shown = set()
        self._last_notification_times = {}
        self._session_start = time.time()
        self.last_search_results: Optional[Dict[str, Any]] = None
        self.last_search_query: Optional[str] = None
        
        # Cache-busting refresh token
        self._refresh_token = int(time.time() * 1000)  # Use milliseconds for uniqueness
        
        # Tools context tracking for better navigation
        self.tools_return_location: Optional[str] = None

    def should_show_notification(self, notification_key: str, cooldown_seconds: int = 300) -> bool:
        """Check if a notification should be shown based on session state"""
        current_time = time.time()

        # Check if we've shown this notification this session
        if notification_key in self._notifications_shown:
            # Check cooldown period
            last_time = self._last_notification_times.get(notification_key, 0)
            if current_time - last_time < cooldown_seconds:
                return False

        # Mark as shown and update timestamp
        self._notifications_shown.add(notification_key)
        self._last_notification_times[notification_key] = current_time
        return True

    def reset_notification(self, notification_key: str):
        """Reset a specific notification state"""
        self._notifications_shown.discard(notification_key)
        self._last_notification_times.pop(notification_key, None)

    def clear_all_notifications(self):
        """Clear all notification state"""
        self._notifications_shown.clear()
        self._last_notification_times.clear()
    
    def bump_refresh_token(self) -> int:
        """Increment refresh token for cache-busting after operations"""
        self._refresh_token += 1
        self.logger.debug("Refresh token bumped to: %s", self._refresh_token)
        return self._refresh_token
    
    def get_refresh_token(self) -> int:
        """Get current refresh token"""
        return self._refresh_token
    
    def set_tools_return_location(self, location: str):
        """Set location to return to after tools operations"""
        self.tools_return_location = location
        self.logger.debug("Tools return location set to: %s", location)
    
    def get_tools_return_location(self) -> Optional[str]:
        """Get location to return to after tools operations"""
        return self.tools_return_location
    
    def clear_tools_return_location(self):
        """Clear tools return location"""
        self.tools_return_location = None


# Global session state instance
_session_state = None


def get_session_state():
    """Get global session state instance"""
    global _session_state
    if _session_state is None:
        _session_state = SessionState()
    return _session_state