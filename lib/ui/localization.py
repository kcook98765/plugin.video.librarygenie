
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Localization Utility
Provides cached localized string access
"""

from xbmcaddon import Addon
from functools import lru_cache

_addon = Addon()

@lru_cache(maxsize=None)
def L(msgid: int) -> str:
    """Get localized string with caching and fallback for missing strings"""
    localized_string = _addon.getLocalizedString(msgid)
    
    # If string is empty or not found, return fallback indicating missing localization
    if not localized_string or localized_string.strip() == "":
        return f"LocMiss_{msgid}"
    
    return localized_string
