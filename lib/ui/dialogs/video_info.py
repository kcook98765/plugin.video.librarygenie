# -*- coding: utf-8 -*-
"""
Video Info Dialog Management Utility

Centralized management of video info dialog operations to eliminate redundancy
and provide clear separation of concerns.
"""
from __future__ import annotations
import time
from typing import Optional

import xbmc
import xbmcgui

from lib.ui.navigation_cache import navigation_action


def is_video_info_active() -> bool:
    """
    Check if video info dialog is currently active.
    
    Returns:
        bool: True if DialogVideoInfo is active, False otherwise
    """
    current_dialog_id = xbmcgui.getCurrentWindowDialogId()
    return current_dialog_id in (12003, 10147)  # DialogVideoInfo / Fallback


def wait_for_dialog_close(context: str, initial_dialog_id: int, logger, max_wait: float = 1.0) -> bool:
    """
    Monitor for dialog actually closing instead of using fixed sleep.
    Moved from info_hijack_helpers to centralize dialog management.
    
    Args:
        context: Description of what operation is waiting for close
        initial_dialog_id: The dialog ID that should close
        logger: Logger instance for debug output
        max_wait: Maximum time to wait in seconds
        
    Returns:
        bool: True if dialog closed within timeout, False otherwise
    """
    start_time = time.time()
    check_interval = 0.1  # 100ms checks for responsive detection
    
    while (time.time() - start_time) < max_wait:
        current_dialog_id = xbmcgui.getCurrentWindowDialogId()
        
        # Dialog closed when ID changes from the initial dialog
        if current_dialog_id != initial_dialog_id:
            elapsed = time.time() - start_time
            logger.debug("HIJACK: Dialog close detected %s after %.3fs (%d→%d)", context, elapsed, initial_dialog_id, current_dialog_id)
            return True
        
        xbmc.sleep(int(check_interval * 1000))
    
    elapsed = time.time() - start_time
    current_dialog_id = xbmcgui.getCurrentWindowDialogId()
    logger.warning("HIJACK: Dialog close timeout %s after %.1fs (still %d)", context, elapsed, current_dialog_id)
    return False


def close_video_info_dialog(logger, timeout: float = 1.0) -> bool:
    """
    Close video info dialog and verify it closed.
    This is the single source of truth for dialog closing in the hijack process.
    
    Args:
        logger: Logger instance for debug output
        timeout: Maximum time to wait for close in seconds
        
    Returns:
        bool: True if dialog was closed successfully, False otherwise
    """
    logger.debug("HIJACK: Checking for open dialogs to close")
    
    # Check if video info dialog is currently open
    if not is_video_info_active():
        logger.debug("HIJACK: No video info dialog to close")
        return True
    
    initial_dialog_id = xbmcgui.getCurrentWindowDialogId()
    logger.debug("HIJACK: Found open dialog ID %d, closing it", initial_dialog_id)
    
    # Send back action to close the dialog
    with navigation_action():
        xbmc.executebuiltin('Action(Back)')
    
    # Monitor for dialog actually closing
    if wait_for_dialog_close("dialog close verification", initial_dialog_id, logger, max_wait=timeout):
        after_close_id = xbmcgui.getCurrentWindowDialogId()
        logger.debug("HIJACK: Dialog closed successfully (was %d, now %d)", initial_dialog_id, after_close_id)
        return True
    else:
        logger.warning("HIJACK: ⚠️ Dialog close timeout, could not close dialog")
        return False