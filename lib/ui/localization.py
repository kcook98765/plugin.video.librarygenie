
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
    """Get localized string with caching"""
    return _addon.getLocalizedString(msgid)
