#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Background Service
Handles info hijacking and background tasks
"""

import xbmc
import xbmcaddon
from lib.utils.logger import get_logger
from lib.ui.info_hijack_manager import InfoHijackManager

# Global service instance
_service_instance = None

class LibraryGenieService:
    """Background service for LibraryGenie addon"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.addon = xbmcaddon.Addon()
        self.hijack_manager = InfoHijackManager(self.logger)
        self._monitor = xbmc.Monitor()
        self._running = False

        self.logger.info("LibraryGenie Service initialized")

    def start(self):
        """Start the background service"""
        self._running = True
        self.logger.info("🚀 LibraryGenie Service starting...")

        try:
            # Main service loop
            while self._running and not self._monitor.abortRequested():
                # Run hijack manager tick every 100ms for responsiveness
                try:
                    self.hijack_manager.tick()
                except Exception as e:
                    self.logger.error(f"Hijack manager tick failed: {e}")

                # Wait 100ms or until abort is requested
                if self._monitor.waitForAbort(0.1):
                    break

        except Exception as e:
            self.logger.error(f"Service main loop error: {e}")
        finally:
            self.logger.info("🛑 LibraryGenie Service stopped")

    def stop(self):
        """Stop the background service"""
        self._running = False
        self.logger.info("LibraryGenie Service stop requested")

def get_service_instance():
    """Get or create the global service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = LibraryGenieService()
    return _service_instance

if __name__ == "__main__":
    # This is the main service entry point
    logger = get_logger(__name__)
    logger.info("🔥 SERVICE.PY MAIN ENTRY POINT - Starting LibraryGenie background service")

    try:
        service = LibraryGenieService()
        service.start()
    except Exception as e:
        logger.error(f"Service startup failed: {e}")
        import traceback
        logger.error(f"Service startup traceback: {traceback.format_exc()}")