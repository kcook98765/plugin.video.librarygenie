
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Authorization Helper
Handles authorization prompts and user guidance for OTP-based auth
"""

import xbmcgui
from lib.utils.kodi_log import get_kodi_logger
from lib.auth.state import is_authorized, get_api_key, clear_auth_data
from lib.auth.otp_auth import run_otp_authorization_flow, test_api_connection, is_api_key_valid
from lib.config import get_config
from lib.ui.dialog_service import get_dialog_service


class AuthorizationHelper:
    """Helper for managing OTP-based authorization UX"""

    def __init__(self, string_getter=None):
        self.logger = get_kodi_logger('lib.auth.auth_helper')
        self._get_string = string_getter or (lambda x: f"String {x}")

    def check_authorization_or_prompt(self, feature_name: str = "AI search") -> bool:
        """
        Check if authorized, and if not, prompt user to authorize

        Args:
            feature_name: Name of the feature requiring authorization

        Returns:
            bool: True if authorized (or user completed auth), False otherwise
        """
        if is_authorized():
            # Verify the API key is still valid
            if self.verify_api_key():
                return True
            else:
                self.logger.warning("Stored API key is invalid, clearing auth data")
                clear_auth_data()

        # Show authorization prompt
        dialog_service = get_dialog_service('lib.auth.auth_helper')
        
        result = dialog_service.yesno(
            "Authentication Required",
            f"The {feature_name} feature requires authorization with the remote server.\n\nWould you like to authorize this device now?",
            no_label="Cancel",
            yes_label="Authorize Device"
        )

        if not result:
            self.logger.debug("User declined authorization for %s", feature_name)
            return False

        # Start authorization flow
        return self.start_device_authorization()

    def verify_api_key(self) -> bool:
        """Verify that the stored API key is still valid"""
        try:
            cfg = get_config()
            server_url = cfg.get('ai_search_server_url', '')
            
            if not server_url:
                self.logger.debug("No server URL configured for API key verification")
                return False
            
            return is_api_key_valid(str(server_url))
            
        except Exception as e:
            self.logger.error("Error verifying API key: %s", e)
            return False

    def show_authorization_status(self):
        """Show current authorization status to user"""
        dialog_service = get_dialog_service('lib.auth.auth_helper')

        if is_authorized():
            # Test the connection
            cfg = get_config()
            server_url = cfg.get('ai_search_server_url', '')
            
            if server_url:
                test_result = test_api_connection(str(server_url))
                if test_result.get('success'):
                    dialog_service.ok(
                        "Authorization Status",
                        f"Device is authorized for AI search.\n\nUser: {test_result.get('user_email', 'Unknown')}\nRole: {test_result.get('user_role', 'Unknown')}"
                    )
                else:
                    dialog_service.ok(
                        "Authorization Status",
                        f"Device has an API key but connection test failed:\n\n{test_result.get('error', 'Unknown error')}"
                    )
            else:
                dialog_service.ok(
                    "Authorization Status",
                    "Device has an API key but no server URL is configured."
                )
        else:
            result = dialog_service.yesno(
                "Authorization Status",
                "Device is not authorized for AI search.\n\nWould you like to authorize now?",
                no_label="Cancel",
                yes_label="Authorize Device"
            )

            if result:
                self.start_device_authorization()

    def start_device_authorization(self) -> bool:
        """Start the OTP authorization flow"""
        try:
            cfg = get_config()
            server_url = cfg.get('ai_search_server_url', '')
            
            if not server_url:
                dialog_service = get_dialog_service('lib.auth.auth_helper')
                dialog_service.ok(
                    "Configuration Required",
                    "Please configure the AI Search Server URL in addon settings before authorizing."
                )
                return False
            
            self.logger.info("Starting OTP authorization flow")
            success = run_otp_authorization_flow(str(server_url))
            
            if success:
                self.logger.info("OTP authorization completed successfully")
                return True
            else:
                self.logger.info("OTP authorization failed or was cancelled")
                return False
                
        except Exception as e:
            self.logger.error("Error during OTP authorization: %s", e)
            dialog_service = get_dialog_service('lib.auth.auth_helper')
            dialog_service.show_error(
                f"Failed to authorize device: {str(e)[:50]}...",
                title="Authorization Error"
            )
            return False

    def clear_authorization(self) -> bool:
        """Clear stored authorization data"""
        try:
            result = clear_auth_data()
            if result:
                dialog_service = get_dialog_service('lib.auth.auth_helper')
                dialog_service.show_success(
                    "Device authorization has been cleared.",
                    title="Authorization Cleared"
                )
            return result
        except Exception as e:
            self.logger.error("Error clearing authorization: %s", e)
            return False


# Global helper instance
_auth_helper = None


def get_auth_helper(string_getter=None):
    """Get global authorization helper instance"""
    global _auth_helper
    if _auth_helper is None:
        _auth_helper = AuthorizationHelper(string_getter)
    return _auth_helper
