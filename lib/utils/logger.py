#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Logging Utilities
Kodi-specific logging implementation
"""

import logging
import sys
from typing import Optional

import xbmc


class KodiLogHandler(logging.Handler):
    """Custom log handler for Kodi"""

    def emit(self, record):
        # Map Python log levels to Kodi log levels
        if record.levelno >= logging.ERROR:
            level = xbmc.LOGERROR
        elif record.levelno >= logging.WARNING:
            level = xbmc.LOGWARNING
        elif record.levelno >= logging.INFO:
            level = xbmc.LOGINFO
        else:
            level = xbmc.LOGDEBUG

        message = self.format(record)
        xbmc.log(f"[LibraryGenie] {message}", level)


def get_logger(name):
    """Get a logger instance configured for the addon"""
    logger = logging.getLogger(name)

    # Only configure once
    if not logger.handlers:
        handler = KodiLogHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Set level based on debug setting
        _update_logger_level(logger)

    return logger


def _update_logger_level(logger):
    """Update logger level based on config setting"""
    try:
        # Use safe import to avoid circular dependencies during early initialization
        from ..config import get_config

        config = get_config()
        debug_enabled = config.get_bool("debug_logging", False)

        old_level = logger.level
        if debug_enabled:
            logger.setLevel(logging.DEBUG)
            new_level = "DEBUG"
        else:
            logger.setLevel(logging.INFO)
            new_level = "INFO"
            
        # Only log level changes when there's an actual change from a configured level (not NOTSET)
        if old_level != logger.level and old_level != logging.NOTSET:
            logger.info(f"LOGGING: Logger level changed from {logging.getLevelName(old_level)} to {new_level} (debug_enabled: {debug_enabled})")
            
    except Exception as e:
        # Fallback to DEBUG level for troubleshooting search issues
        logger.setLevel(logging.DEBUG)
        logger.info(f"LOGGING: Fallback to DEBUG level due to error: {e}")


def update_all_loggers():
    """Update all existing loggers with current debug setting"""
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and logger.handlers:
            _update_logger_level(logger)


def force_debug_mode():
    """Force all LibraryGenie loggers to DEBUG level for troubleshooting"""
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and 'librarygenie' in name.lower():
            logger.setLevel(logging.DEBUG)
            # Log confirmation at INFO level so it's always visible
            logger.info(f"LOGGING: Forced DEBUG mode for logger: {name}")