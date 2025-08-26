
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Device Code Authorization (Stub)
Placeholder for device code authorization flow
"""

import xbmcgui
from ..utils.logger import get_logger


def run_authorize_flow():
    """Run device authorization flow (stub implementation)"""
    logger = get_logger(__name__)
    logger.info("Running authorization flow (stub)")
    
    # Show stub notification
    xbmcgui.Dialog().notification(
        "Movie List Manager",
        "Authorization flow not implemented yet",
        xbmcgui.NOTIFICATION_INFO,
        3000
    )
    
    # TODO: Implement actual device code flow
