
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Integration Helper
Helper functions for favorites integration settings
"""

from ..utils.logger import get_logger


def trigger_immediate_favorites_scan():
    """Trigger immediate favorites scan when integration is enabled"""
    logger = get_logger(__name__)
    
    try:
        from ..kodi.favorites_manager import get_phase4_favorites_manager
        
        favorites_manager = get_phase4_favorites_manager()
        result = favorites_manager.scan_favorites(force_refresh=True)
        
        if result.get("success"):
            mapped = result.get("items_mapped", 0)
            total = result.get("items_found", 0)
            logger.info(f"Immediate favorites scan completed: {mapped}/{total} mapped")
            return True
        else:
            logger.warning(f"Immediate favorites scan failed: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to trigger immediate favorites scan: {e}")
        return False


def on_favorites_integration_enabled():
    """Called when favorites integration is enabled via settings"""
    logger = get_logger(__name__)
    logger.info("Favorites integration enabled - triggering immediate scan")
    return trigger_immediate_favorites_scan()
