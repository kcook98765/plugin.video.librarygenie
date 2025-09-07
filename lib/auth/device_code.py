
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Device Code Authorization (DEPRECATED)
This module has been completely replaced by otp_auth.py for OTP-based authentication.
All OAuth2 device code functionality has been removed.
"""

import warnings
from ..utils.logger import get_logger

logger = get_logger(__name__)

def run_authorize_flow():
    """
    DEPRECATED: Use otp_auth.run_otp_authorization_flow() instead
    """
    warnings.warn(
        "run_authorize_flow() is deprecated. Use otp_auth.run_otp_authorization_flow() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.error("Deprecated OAuth2 device code flow called - use OTP auth instead")
    return False

def test_authorization():
    """
    DEPRECATED: Use otp_auth.test_api_connection() instead
    """
    warnings.warn(
        "test_authorization() is deprecated. Use otp_auth.test_api_connection() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.error("Deprecated authorization test called - use OTP auth instead")
    return False, "Deprecated function - use OTP auth"

# Clean up - remove all other functions
__all__ = []  # Export nothing
