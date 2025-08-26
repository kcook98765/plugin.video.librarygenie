#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Authorization Helper
Handles authorization prompts and user guidance
"""

try:
    from typing import Optional
except ImportError:
    # Python < 3.5 fallback
    Optional = object

import xbmcgui
import xbmcaddon


class AuthorizationHelper:
    """Helper for managing authorization UX"""

    def __init__(self, string_getter=None):
        self.logger = get_logger(__name__)
        self._get_string = string_getter or (lambda x: f"String {x}")

    def check_authorization_or_prompt(self, feature_name: str = "remote feature") -> bool:
        """
        Check if authorized, and if not, prompt user to authorize

        Args:
            feature_name: Name of the feature requiring authorization

        Returns:
            bool: True if authorized (or user completed auth), False otherwise
        """
        if is_authorized():
            return True

        # Show authorization prompt
        dialog = xbmcgui.Dialog()

        result = dialog.yesno(
            "Authorization Required",
            f"The {feature_name} requires authorization with the remote server.\n\n"
            "Would you like to authorize this device now?",
            nolabel="Cancel",
            yeslabel="Authorize"
        )

        if not result:
            self.logger.debug(f"User declined authorization for {feature_name}")
            return False

        # Start authorization flow
        try:
            success = run_authorize_flow()
            if success:
                self.logger.info(f"Authorization successful for {feature_name}")
                return True
            else:
                self.logger.info(f"Authorization failed for {feature_name}")
                return False

        except Exception as e:
            self.logger.error(f"Authorization flow error: {e}")
            dialog.ok(
                "Authorization Error",
                f"Failed to complete authorization:\n{str(e)[:100]}..."
            )
            return False

    def show_authorization_status(self):
        """Show current authorization status to user"""
        dialog = xbmcgui.Dialog()

        if is_authorized():
            dialog.ok(
                "Authorization Status",
                "Device is currently authorized for remote services."
            )
        else:
            result = dialog.yesno(
                "Authorization Status",
                "Device is not authorized for remote services.\n\n"
                "Would you like to authorize now?",
                nolabel="Cancel",
                yeslabel="Authorize"
            )

            if result:
                self.check_authorization_or_prompt("remote services")


# Global helper instance
_auth_helper = None


def get_auth_helper(string_getter=None):
    """Get global authorization helper instance"""
    global _auth_helper
    if _auth_helper is None:
        _auth_helper = AuthorizationHelper(string_getter)
    return _auth_helper