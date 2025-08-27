#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Logging Utilities
Kodi-specific logging implementation
"""

import logging
import sys
try:
    from typing import Optional
except ImportError:
    # Python < 3.5 fallback
    Optional = object

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

        if debug_enabled:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    except Exception:
        # Fallback to DEBUG level for troubleshooting search issues
        logger.setLevel(logging.DEBUG)


def update_all_loggers():
    """Update all existing loggers with current debug setting"""
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and logger.handlers:
            _update_logger_level(logger)