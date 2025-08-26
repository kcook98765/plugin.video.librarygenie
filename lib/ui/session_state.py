#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Session State Manager
Tracks UI state to prevent notification spam and manage user experience
"""

import time
try:
    from typing import Dict, Optional
except ImportError:
    # Python < 3.5 fallback
    Dict = dict
    Optional = object

from ..utils.logger import get_logger


class SessionState:
    """Manages session-specific UI state"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._notifications_shown = set()
        self._last_notification_times = {}
        self._session_start = time.time()

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


# Global session state instance
_session_state = None


def get_session_state():
    """Get global session state instance"""
    global _session_state
    if _session_state is None:
        _session_state = SessionState()
    return _session_state