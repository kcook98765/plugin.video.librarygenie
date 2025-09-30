
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
    30379: "lightblue",   # LG Search
    30380: "lightgreen",  # LG Quick Add
    30381: "yellow",      # LG Add to List...
    30382: "red",         # LG Remove from List
    30383: "white",       # LG more...
    30384: "lightblue",   # LG Search/Favorites
    30385: "lightblue",   # Local Movie Search
    30386: "lightblue",   # Local TV Search
    30387: "cyan",        # AI Movie Search
    30388: "yellow",      # Search History
    30389: "green",       # Kodi Favorites
    
    # Tools Menu colors (36xxx)
    30213: "white",       # Scan Favorites
    30214: "lightgreen",  # Save As New List
    30216: "yellow",      # Merge Into %s
    30217: "yellow",      # Rename '%s'
    30220: "red",         # Delete '%s'
    30221: "lightgreen",  # Create New List in '%s'
    30222: "lightgreen",  # Create New Subfolder in '%s'
    30223: "yellow",      # Move '%s' to Folder
    30219: "white",       # Export All Lists in '%s'
    30224: "yellow",      # Rename %s
    30225: "yellow",      # Move %s to Folder
    30226: "white",       # Export %s
    30227: "red",         # Delete %s
    
    # Search colors (3xxxx)
    30079: "cyan",        # AI Movie Search
    
    # Error Messages (should be red for visibility)
    30507: "red",         # Failed to create list
    30104: "red",         # Database error
    30368: "red",         # List not found
    30369: "red",         # Folder not found
    30370: "red",         # Failed to create folder
    
    # Success Messages (should be green)
    30066: "green",       # Restore completed successfully
    
    # Action Labels (should be yellow for emphasis)
    30371: "yellow",      # Move to New List
    30228: "yellow",      # Clear All Search History
    
    # Navigation Labels (should be white/neutral)
    30303: "white",       # [Root Level]
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
