
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
    37100: "lightblue",   # LG Search
    37101: "lightgreen",  # LG Quick Add
    37102: "yellow",      # LG Add to List...
    37103: "red",         # LG Remove from List
    37104: "white",       # LG more...
    37105: "lightblue",   # LG Search/Favorites
    37200: "lightblue",   # Local Movie Search
    37201: "lightblue",   # Local TV Search
    37202: "cyan",        # AI Movie Search
    37203: "yellow",      # Search History
    37204: "green",       # Kodi Favorites
    
    # Tools Menu colors (36xxx)
    36001: "white",       # Scan Favorites
    36002: "lightgreen",  # Save As New List
    36004: "yellow",      # Merge Into %s
    36005: "yellow",      # Rename '%s'
    36008: "red",         # Delete '%s'
    36009: "lightgreen",  # Create New List in '%s'
    36010: "lightgreen",  # Create New Subfolder in '%s'
    36011: "yellow",      # Move '%s' to Folder
    36012: "white",       # Export All Lists in '%s'
    36051: "yellow",      # Rename %s
    36052: "yellow",      # Move %s to Folder
    36053: "white",       # Export %s
    36054: "red",         # Delete %s
    
    # Search colors (3xxxx)
    34100: "cyan",        # AI Movie Search
    
    # Error Messages (should be red for visibility)
    30507: "red",         # Failed to create list
    34306: "red",         # Database error
    37019: "red",         # List not found
    37020: "red",         # Folder not found
    37021: "red",         # Failed to create folder
    
    # Success Messages (should be green)
    34011: "green",       # Restore completed successfully
    
    # Action Labels (should be yellow for emphasis)
    37022: "yellow",      # Move to New List
    37023: "yellow",      # Clear All Search History
    
    # Navigation Labels (should be white/neutral)
    36032: "white",       # [Root Level]
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
