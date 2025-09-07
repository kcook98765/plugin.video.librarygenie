
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Device Code Authorization (DEPRECATED)
This module has been replaced by otp_auth.py for OTP-based authentication.
Kept as placeholder for backward compatibility during transition.
"""

import warnings
from ..utils.logger import get_logger

logger = get_logger(__name__)

def run_authorize_flow():
    """
    Deprecated function - use otp_auth.run_otp_authorization_flow() instead
    """
    warnings.warn(
        "run_authorize_flow() is deprecated. Use otp_auth.run_otp_authorization_flow() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.warning("Deprecated OAuth2 device code flow called - please update to use OTP auth")
    return False

def test_authorization():
    """
    Deprecated function - use otp_auth.test_api_connection() instead
    """
    warnings.warn(
        "test_authorization() is deprecated. Use otp_auth.test_api_connection() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    logger.warning("Deprecated authorization test called - please update to use OTP auth")
    return False, "Deprecated function"
