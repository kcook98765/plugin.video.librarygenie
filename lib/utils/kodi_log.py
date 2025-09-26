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
    xbmc.log(f"[LG-LibraryGenie] {message}", level)


def log_error(message):
    """Error logging shorthand"""
    xbmc.log(f"[LG-LibraryGenie] {message}", xbmc.LOGERROR)


def log_info(message):
    """Info logging shorthand - use sparingly per Kodi standards"""
    xbmc.log(f"[LG-LibraryGenie] {message}", xbmc.LOGINFO)


def log_warning(message):
    """Warning logging shorthand"""
    xbmc.log(f"[LG-LibraryGenie] {message}", xbmc.LOGWARNING)


class KodiLogger:
    """Compatibility adapter that mimics Python logging API but routes to direct Kodi logging"""
    
    def __init__(self, name=None):
        base_name = name or "LibraryGenie"
        # Avoid double-prefixing if name already starts with LG-
        if base_name.startswith("LG-"):
            self.name = base_name
        else:
            self.name = f"LG-{base_name}"
    
    def debug(self, message, *args, **kwargs):
        """Debug-level logging with %-style formatting support"""
        if args:
            message = message % args
        xbmc.log(f"[{self.name}] {message}", xbmc.LOGDEBUG)
    
    def info(self, message, *args, **kwargs):
        """Info-level logging with %-style formatting support"""
        if args:
            message = message % args
        xbmc.log(f"[{self.name}] {message}", xbmc.LOGINFO)
    
    def warning(self, message, *args, **kwargs):
        """Warning-level logging with %-style formatting support"""
        if args:
            message = message % args
        # Handle exc_info for traceback inclusion
        if kwargs.get('exc_info'):
            import traceback
            message += f"\nTraceback: {traceback.format_exc()}"
        xbmc.log(f"[{self.name}] {message}", xbmc.LOGWARNING)
    
    def error(self, message, *args, **kwargs):
        """Error-level logging with %-style formatting support"""
        if args:
            message = message % args
        # Handle exc_info for traceback inclusion
        if kwargs.get('exc_info'):
            import traceback
            message += f"\nTraceback: {traceback.format_exc()}"
        xbmc.log(f"[{self.name}] {message}", xbmc.LOGERROR)
    
    def exception(self, message, *args, **kwargs):
        """Exception logging - always includes traceback"""
        if args:
            message = message % args
        import traceback
        message += f"\nTraceback: {traceback.format_exc()}"
        xbmc.log(f"[{self.name}] {message}", xbmc.LOGERROR)
    
    # Backward compatibility alias
    warn = warning


def get_kodi_logger(name=None):
    """Factory function to create KodiLogger instances"""
    return KodiLogger(name)