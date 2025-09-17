
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Localization Utility
Provides cached localized string access
"""

from xbmcaddon import Addon
from functools import lru_cache

_addon = Addon()

# Centralized UI color map (msgid -> Kodi color name)
COLOR_MAP = {
    # Context Menu colors (37xxx)
    97100: "lightblue",   # LG Search
    97101: "lightgreen",  # LG Quick Add
    97102: "yellow",      # LG Add to List...
    97103: "red",         # LG Remove from List
    97104: "white",       # LG more...
    97105: "lightblue",   # LG Search/Favorites
    97200: "lightblue",   # Local Movie Search
    97201: "lightblue",   # Local TV Search
    97202: "cyan",        # AI Movie Search
    97203: "yellow",      # Search History
    97204: "green",       # Kodi Favorites
    
    # Tools Menu colors (36xxx)
    96001: "white",       # Scan Favorites
    96002: "lightgreen",  # Save As New List
    96004: "yellow",      # Merge Into %s
    96005: "yellow",      # Rename '%s'
    96008: "red",         # Delete '%s'
    96009: "lightgreen",  # Create New List in '%s'
    96010: "lightgreen",  # Create New Subfolder in '%s'
    96011: "yellow",      # Move '%s' to Folder
    96012: "white",       # Export All Lists in '%s'
    96051: "yellow",      # Rename %s
    96052: "yellow",      # Move %s to Folder
    96053: "white",       # Export %s
    96054: "red",         # Delete %s
    
    # Search colors (3xxxx)
    93000: "lightblue",   # Local Movie Search
    94100: "cyan",        # AI Movie Search
    
    # Error Messages (should be red for visibility)
    90507: "red",         # Failed to create list
    94306: "red",         # Database error
    97019: "red",         # List not found
    97020: "red",         # Folder not found
    97021: "red",         # Failed to create folder
    
    # Success Messages (should be green)
    94011: "green",       # Restore completed successfully
    
    # Action Labels (should be yellow for emphasis)
    97022: "yellow",      # Move to New List
    97023: "yellow",      # Clear All Search History
    
    # Navigation Labels (should be white/neutral)
    96032: "white",       # [Root Level]
}

def _is_colorization_enabled() -> bool:
    """Check if colorization is enabled in settings"""
    try:
        from lib.config.config_manager import get_config
        config = get_config()
        return config.get_bool('enable_colorized_labels', True)
    except Exception:
        return True  # Default to enabled if setting can't be read

@lru_cache(maxsize=None)
def L(msgid: int) -> str:
    """Get localized string with optional colorization"""
    localized_string = _addon.getLocalizedString(msgid)
    
    # If string is empty or not found, return fallback indicating missing localization
    if not localized_string or localized_string.strip() == "":
        return f"LocMiss_{msgid}"
    
    # Apply color if enabled and mapped
    if _is_colorization_enabled() and msgid in COLOR_MAP:
        return f"[COLOR {COLOR_MAP[msgid]}]{localized_string}[/COLOR]"
    
    return localized_string
