
"""
Legacy InfoTag functions - now delegates to infotag_adapter
Maintained for backward compatibility during migration
"""
from typing import Dict, Any
import xbmcgui
from .adapters.infotag_adapter import set_info_tag, set_art

# Re-export the legacy functions for backward compatibility
__all__ = ['set_info_tag', 'set_art']

# These functions are now implemented in infotag_adapter.py
# This file exists only for backward compatibility during the migration
