
"""Context Menu Utilities for LibraryGenie - minimal backward compatibility

Note: LibraryGenie uses the native Kodi context menu system exclusively (via addon.xml).
This module maintains minimal backward compatibility for any remaining imports.
"""

# Minimal backward compatibility - empty implementations
def get_context_menu_builder():
    """Backward compatibility: Returns None since context menu building is no longer used"""
    return None

def get_context_menu_utils():
    """Backward compatibility: Returns None since context menu utils are no longer used"""
    return None

# Legacy classes for import compatibility
class ContextMenuUtils:
    """Legacy class for backward compatibility - no longer used"""
    pass

class ContextMenuBuilder:
    """Legacy class for backward compatibility - no longer used"""
    pass
