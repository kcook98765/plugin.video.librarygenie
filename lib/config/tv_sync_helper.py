#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - TV Episode Sync Helper
Helper functions for TV episode sync settings
"""

from ..utils.logger import get_logger


def on_tv_episode_sync_enabled():
    """Called when TV episode sync is enabled via settings"""
    logger = get_logger(__name__)
    logger.info("TV episode sync enabled - starting immediate library scan with TV episodes")
    
    try:
        from ..library.scanner import get_library_scanner
        
        # Get library scanner instance
        scanner = get_library_scanner()
        if not scanner:
            logger.error("Failed to get library scanner instance")
            return False
            
        logger.info("Starting full library scan with TV episodes...")
        
        # Perform full scan which will include TV episodes since sync is now enabled
        scan_result = scanner.perform_full_scan()
        
        if scan_result and scan_result.get("success", False):
            movies_added = scan_result.get("items_added", 0)
            episodes_added = scan_result.get("episodes_added", 0)
            logger.info("TV episode sync completed successfully")
            logger.info("Scan results: %s movies, %s episodes processed", movies_added, episodes_added)
            
            # Log helpful message about episodes
            if episodes_added > 0:
                logger.info("TV episodes are now available for list building")
            else:
                logger.info("No TV episodes found in library - check that TV shows are properly indexed in Kodi")
                
            return True
        else:
            logger.warning("TV episode sync completed with issues: %s", 
                          scan_result.get("error", "Unknown error"))
            return False
            
    except Exception as e:
        logger.error("Error during TV episode sync: %s", e)
        return False