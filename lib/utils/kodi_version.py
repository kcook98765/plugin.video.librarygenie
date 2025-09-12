
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Kodi Version Detection
Centralized utility for determining Kodi version with caching
"""

import xbmc
from typing import Optional
from .logger import get_logger

logger = get_logger(__name__)

# Global cache to avoid repeated System.BuildVersion calls
_cached_major_version: Optional[int] = None

def get_kodi_major_version() -> int:
    """
    Get the major version number of Kodi with caching.
    
    Returns:
        int: The major version number (e.g., 19, 20, 21).
             Returns 19 as safe fallback for Matrix compatibility.
    """
    global _cached_major_version
    
    if _cached_major_version is not None:
        return _cached_major_version
    
    try:
        build_version = xbmc.getInfoLabel("System.BuildVersion")
        logger.debug("Kodi build version string: %s", build_version)
        
        # Examples: "20.2 (20.2.0) Git:...", "19.5-Matrix", "21.0-Omega"
        # Extract first numeric component before any dots or hyphens
        major_str = build_version.split('.')[0].split('-')[0]
        _cached_major_version = int(major_str)
        
        logger.debug("Detected Kodi major version: %s", _cached_major_version)
        return _cached_major_version
        
    except Exception as e:
        logger.warning("Failed to parse Kodi version from '%s': %s", build_version, e)
        # Safe fallback to Matrix (19) for maximum compatibility
        _cached_major_version = 19
        return _cached_major_version

def is_kodi_v20_plus() -> bool:
    """
    Check if running Kodi version 20 (Nexus) or higher.
    
    Returns:
        bool: True if Kodi major version >= 20, False otherwise
    """
    return get_kodi_major_version() >= 20

def is_kodi_v21_plus() -> bool:
    """
    Check if running Kodi version 21 (Omega) or higher.
    
    Returns:
        bool: True if Kodi major version >= 21, False otherwise
    """
    return get_kodi_major_version() >= 21

def get_version_specific_control_id() -> int:
    """
    Get the correct list control ID based on Kodi version.
    
    Returns:
        int: Control ID for main list view (55 for v20+, 50 for v19)
    """
    if is_kodi_v20_plus():
        # Kodi v20/v21 Estuary uses control ID 55 as default main list
        return 55
    else:
        # Kodi v19 uses control ID 50
        return 50

def reset_version_cache():
    """
    Reset the cached version detection (useful for testing).
    """
    global _cached_major_version
    _cached_major_version = None
    logger.debug("Kodi version cache reset")
