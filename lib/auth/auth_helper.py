#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Authorization Helper
Handles authorization prompts and user guidance
"""

import xbmcgui
from ..utils.logger import get_logger
from .state import is_authorized
from .device_code import run_authorize_flow


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

        from ..ui.localization import L
        
        result = dialog.yesno(
            heading=L(34106),  # "Authentication required"
            line1=L(37003) % feature_name,  # "The %s requires authorization with the remote server."
            line2=L(37004),    # "Would you like to authorize this device now?"
            line3="",
            nolabel=L(36003),  # "Cancel"
            yeslabel=L(35028)  # "Authorize device"
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
            from ..ui.localization import L
            
            result = dialog.yesno(
                heading=L(34100),  # "Sync Status" 
                line1=L(37005),    # "Device is not authorized for remote services."
                line2=L(37006),    # "Would you like to authorize now?"
                line3="",
                nolabel=L(36003),  # "Cancel"
                yeslabel=L(35028)  # "Authorize device"
            )

            if result:
                self.check_authorization_or_prompt("remote services")

    def start_device_authorization(self):
        """Start the device authorization flow"""
        try:
            self.logger.info("Starting device authorization flow")
            success = run_authorize_flow()
            
            if success:
                self.logger.info("Device authorization completed successfully")
                return True
            else:
                self.logger.info("Device authorization failed or was cancelled")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during device authorization: {e}")
            xbmcgui.Dialog().notification(
                "Authorization Error",
                f"Failed to authorize device: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR
            )
            return False


# Global helper instance
_auth_helper = None


def get_auth_helper(string_getter=None):
    """Get global authorization helper instance"""
    global _auth_helper
    if _auth_helper is None:
        _auth_helper = AuthorizationHelper(string_getter)
    return _auth_helper