#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - TV Episode Sync Helper
Compatibility layer for TV episode sync with new SyncController architecture
"""

from ..utils.kodi_log import get_kodi_logger


def on_tv_episode_sync_enabled():
    """
    Compatibility function for TV episode sync activation.
    Now redirects to SyncController for unified sync management.
    """
    logger = get_kodi_logger('lib.config.tv_sync_helper')
    logger.info("TV episode sync requested - using new SyncController")
    
    try:
        from ..library.sync_controller import SyncController
        
        # Use new SyncController for TV episode sync
        sync_controller = SyncController()
        
        # Check if TV episodes sync is enabled in settings
        from ..config.settings import SettingsManager
        settings = SettingsManager()
        if not settings.get_sync_tv_episodes():
            logger.warning("TV episode sync called but setting is disabled")
            return False
            
        logger.info("Starting TV episodes sync via SyncController...")
        
        # Perform manual sync (will sync both movies and TV if both enabled)
        success, message = sync_controller.perform_manual_sync()
        
        if success:
            logger.info("TV episode sync completed successfully: %s", message)
            logger.info("TV episodes are now available for list building")
            return True
        else:
            logger.warning("TV episode sync completed with issues: %s", message)
            return False
            
    except Exception as e:
        logger.error("Error during TV episode sync via SyncController: %s", e)
        return False


def trigger_tv_sync():
    """
    Trigger TV episodes sync using the new SyncController.
    Note: This respects current user settings - may sync both movies and TV if both are enabled.
    Renamed from trigger_episodes_only_sync to accurately reflect behavior.
    """
    logger = get_kodi_logger('lib.config.tv_sync_helper')
    logger.info("TV sync requested - delegating to SyncController")
    
    try:
        from ..library.sync_controller import SyncController
        from ..config.settings import SettingsManager
        
        settings = SettingsManager()
        
        # Check if TV episodes sync is enabled
        if not settings.get_sync_tv_episodes():
            logger.warning("TV episodes sync is disabled in settings")
            return False
        
        sync_controller = SyncController()
        
        # Use manual sync which respects current settings
        success, message = sync_controller.perform_manual_sync()
        
        logger.info("TV sync via SyncController: %s", message)
        return success
        
    except Exception as e:
        logger.error("Error during TV sync: %s", e)
        return False


# Legacy compatibility function
def trigger_episodes_only_sync():
    """
    Legacy compatibility function - now delegates to trigger_tv_sync.
    DEPRECATED: Use trigger_tv_sync() which more accurately describes the behavior.
    """
    logger = get_kodi_logger('lib.config.tv_sync_helper')
    logger.warning("trigger_episodes_only_sync is deprecated - use trigger_tv_sync instead")
    return trigger_tv_sync()