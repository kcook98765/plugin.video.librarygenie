
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Integration Helper
Helper functions for favorites integration settings
"""

from ..utils.logger import get_logger


def on_favorites_integration_enabled():
    """Called when favorites integration is enabled via settings"""
    logger = get_logger(__name__)
    logger.info("Favorites integration enabled - folder will be visible in menu")
    # No automatic scanning - only manual scan by user
    return True
