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
    """
    Manages ephemeral session state that doesn't need to persist between Kodi restarts.
    Used for UI notifications, temporary flags, and other transient data.
    """
    def __init__(self):
        self._notification_timestamps: Dict[str, float] = {}
        self._session_data: Dict[str, Any] = {}
        self._hijack_suppression_end_time = 0

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

    def clear_session_data(self):
        """Clear all session data"""
        self._session_data.clear()
        self._notification_timestamps.clear()
        self._hijack_suppression_end_time = 0

    def activate_hijack_suppression(self, duration_seconds=2.0):
        """
        Activate search prompt suppression for specified duration.
        Used to prevent unwanted keyboard overlay after info hijack operations.
        """
        self._hijack_suppression_end_time = time.time() + duration_seconds

    def is_hijack_suppression_active(self):
        """
        Returns True if search prompts should be suppressed due to recent hijack.
        """
        if self._hijack_suppression_end_time == 0:
            return False

        current_time = time.time()
        if current_time < self._hijack_suppression_end_time:
            return True

        # Clean up expired suppression
        self._hijack_suppression_end_time = 0
        return False


# Global session state instance
_session_state = None


def get_session_state():
    """Get global session state instance"""
    global _session_state
    if _session_state is None:
        _session_state = SessionState()
    return _session_state