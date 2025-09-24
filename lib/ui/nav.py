
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Navigator API
Centralizes all container mutations and endOfDirectory calls
"""

import xbmc
import xbmcplugin
from lib.utils.kodi_log import get_kodi_logger


class Navigator:
    """Centralized navigation API for container management"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.nav')

    def push(self, url: str) -> None:
        """Navigate to URL by pushing to navigation stack"""
        self.logger.debug("NAVIGATOR: Push to %s", url)
        xbmc.executebuiltin(f'Container.Update("{url}")')

    def replace(self, url: str) -> None:
        """Navigate to URL by replacing current location"""
        self.logger.debug("NAVIGATOR: Replace with %s", url)
        xbmc.executebuiltin(f'Container.Update("{url}", replace)')

    def refresh(self) -> None:
        """Refresh current container"""
        self.logger.debug("NAVIGATOR: Refresh container")
        xbmc.executebuiltin('Container.Refresh')

    def finish_directory(self, handle: int, succeeded: bool = True, update: bool = False) -> None:
        """End directory with consistent parameters"""
        self.logger.debug("NAVIGATOR: Finish directory - handle=%s, succeeded=%s, update=%s", handle, succeeded, update)
        xbmcplugin.endOfDirectory(handle, succeeded=succeeded, updateListing=update, cacheToDisc=False)

    def execute_intent(self, intent) -> None:
        """Execute a NavigationIntent"""
        if intent is None:
            self.logger.debug("NAVIGATOR: No intent to execute")
            return
            
        from lib.ui.response_types import NavigationIntent
        if not isinstance(intent, NavigationIntent):
            self.logger.warning("NAVIGATOR: Invalid intent type: %s", type(intent))
            return
            
        if intent.mode == 'push':
            self.push(intent.url)
        elif intent.mode == 'replace':
            self.replace(intent.url)
        elif intent.mode == 'refresh':
            self.refresh()
        elif intent.mode is None:
            self.logger.debug("NAVIGATOR: Intent mode is None, no action taken")
        else:
            self.logger.warning("NAVIGATOR: Unknown intent mode: %s", intent.mode)


# Global navigator instance
_navigator_instance = None


def get_navigator() -> Navigator:
    """Get global navigator instance"""
    global _navigator_instance
    if _navigator_instance is None:
        _navigator_instance = Navigator()
    return _navigator_instance


# Convenience functions for direct access
def push(url: str) -> None:
    """Navigate to URL by pushing to navigation stack"""
    get_navigator().push(url)


def replace(url: str) -> None:
    """Navigate to URL by replacing current location"""
    get_navigator().replace(url)


def refresh() -> None:
    """Refresh current container"""
    get_navigator().refresh()


def finish_directory(handle: int, succeeded: bool = True, update: bool = False) -> None:
    """End directory with consistent parameters"""
    get_navigator().finish_directory(handle, succeeded, update)


def execute_intent(intent) -> None:
    """Execute a NavigationIntent"""
    get_navigator().execute_intent(intent)
