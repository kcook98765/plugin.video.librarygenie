
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
    30674: "lightblue",   # LG Search
    30675: "lightgreen",  # LG Quick Add
    30676: "yellow",      # LG Add to List...
    30677: "red",         # LG Remove from List
    30678: "white",       # LG more...
    30679: "lightblue",   # LG Search/Favorites
    30680: "lightblue",   # Local Movie Search
    30681: "lightblue",   # Local TV Search
    30682: "cyan",        # AI Movie Search
    30683: "yellow",      # Search History
    30684: "green",       # Kodi Favorites
    
    # Tools Menu colors (36xxx)
    30516: "white",       # Scan Favorites
    30517: "lightgreen",  # Save As New List
    30519: "yellow",      # Merge Into %s
    30524: "yellow",      # Rename '%s'
    30527: "red",         # Delete '%s'
    30528: "lightgreen",  # Create New List in '%s'
    30529: "lightgreen",  # Create New Subfolder in '%s'
    30536: "yellow",      # Move '%s' to Folder
    30537: "white",       # Export All Lists in '%s'
    30588: "yellow",      # Rename %s
    30589: "yellow",      # Move %s to Folder
    30591: "white",       # Export %s
    30592: "red",         # Delete %s
    
    # Search colors (3xxxx)
    30327: "cyan",        # AI Movie Search
    
    # Error Messages (should be red for visibility)
    30107: "red",         # Failed to create list
    30359: "red",         # Database error
    30663: "red",         # List not found
    30664: "red",         # Folder not found
    30665: "red",         # Failed to create folder
    
    # Success Messages (should be green)
    30314: "green",       # Restore completed successfully
    
    # Action Labels (should be yellow for emphasis)
    30666: "yellow",      # Move to New List
    30593: "yellow",      # Clear All Search History
    
    # Navigation Labels (should be white/neutral)
    30561: "white",       # [Root Level]
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
