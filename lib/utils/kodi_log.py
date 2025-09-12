#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Pure Kodi Standard Logging
Minimal direct xbmc.log() wrapper functions for maximum efficiency and Kodi compliance
"""

import xbmc


def log(message, level=xbmc.LOGDEBUG):
    """Standard Kodi logging - direct to xbmc.log()
    
    Args:
        message: Log message (should be pre-formatted string)  
        level: xbmc log level (defaults to LOGDEBUG per Kodi standards)
    """
    xbmc.log(f"[LibraryGenie] {message}", level)


def log_error(message):
    """Error logging shorthand"""
    xbmc.log(f"[LibraryGenie] {message}", xbmc.LOGERROR)


def log_info(message):
    """Info logging shorthand - use sparingly per Kodi standards"""
    xbmc.log(f"[LibraryGenie] {message}", xbmc.LOGINFO)


def log_warning(message):
    """Warning logging shorthand"""
    xbmc.log(f"[LibraryGenie] {message}", xbmc.LOGWARNING)