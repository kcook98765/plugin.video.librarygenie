
"""Navigation and state management for LibraryGenie addon"""

import time
import xbmc
from resources.lib import utils

class NavigationManager:
    """Manages navigation state and flow control for the addon"""
    
    def __init__(self):
        self._navigation_in_progress = False
        self._last_navigation_time = 0

    def set_navigation_in_progress(self, in_progress: bool):
        """Set navigation state with property synchronization"""
        self._navigation_in_progress = in_progress
        if in_progress:
            xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
            xbmc.executebuiltin(f"SetProperty(LibraryGenie.LastNavigation,{time.time()},Home)")
            self._last_navigation_time = time.time()
        else:
            xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")

    def is_navigation_in_progress(self) -> bool:
        """Check if navigation is currently in progress"""
        return self._navigation_in_progress

    def clear_navigation_flags(self):
        """Clear all navigation-related flags and properties"""
        self._navigation_in_progress = False
        xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
        xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
        utils.log("Cleared all navigation flags", "DEBUG")

    def cleanup_stuck_navigation(self, timeout_seconds: float = 15.0):
        """Clean up navigation flags if stuck for too long"""
        try:
            current_time = time.time()
            last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
            time_since_nav = current_time - last_navigation

            if time_since_nav > timeout_seconds:
                utils.log(f"=== CLEARING STUCK NAVIGATION FLAGS (stuck for {time_since_nav:.1f}s) ===", "DEBUG")
                self.clear_navigation_flags()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def set_search_modal_active(self, active: bool):
        """Set search modal state"""
        if active:
            xbmc.executebuiltin("SetProperty(LibraryGenie.SearchModalActive,true,Home)")
        else:
            xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")

    def navigate_to_url(self, url: str, replace: bool = True):
        """Perform navigation with proper state management"""
        utils.log(f"=== PERFORMING NAVIGATION TO: {url} ===", "DEBUG")
        self.set_navigation_in_progress(True)
        
        # Let GUI settle before navigation
        xbmc.sleep(100)
        
        # Navigate with proper quoting and replace parameter
        if replace:
            xbmc.executebuiltin(f'Container.Update("{url}", replace)')
        else:
            xbmc.executebuiltin(f'Container.Update("{url}")')
        
        xbmc.sleep(50)
        
        # Clear navigation flag
        self.set_navigation_in_progress(False)
        utils.log("=== NAVIGATION COMPLETED ===", "DEBUG")

# Global navigation manager instance
_nav_manager = None

def get_navigation_manager():
    """Get the singleton navigation manager instance"""
    global _nav_manager
    if _nav_manager is None:
        _nav_manager = NavigationManager()
    return _nav_manager
