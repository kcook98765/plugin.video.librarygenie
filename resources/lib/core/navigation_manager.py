
"""Navigation and state management for LibraryGenie addon"""

import time
import xbmc
from resources.lib.utils import utils

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
        """Perform navigation with proper state management and back button preservation"""
        utils.log(f"=== NAVIGATION START ===", "DEBUG")
        utils.log(f"Target URL: {url}", "DEBUG")
        utils.log(f"Replace mode: {replace}", "DEBUG")
        utils.log(f"Current window: {xbmc.getInfoLabel('System.CurrentWindow')}", "DEBUG")
        utils.log(f"Current control: {xbmc.getInfoLabel('System.CurrentControl')}", "DEBUG")
        
        self.set_navigation_in_progress(True)
        
        # Let GUI settle before navigation
        xbmc.sleep(100)
        
        # Log navigation method choice
        if replace:
            utils.log("=== Using Container.Update with REPLACE (breaks back button) ===", "DEBUG")
            xbmc.executebuiltin(f'Container.Update("{url}", replace)')
        else:
            utils.log("=== Using Container.Update WITHOUT replace (preserves back button) ===", "DEBUG")
            xbmc.executebuiltin(f'Container.Update("{url}")')
        
        xbmc.sleep(50)
        
        # Log post-navigation state
        utils.log(f"Post-nav window: {xbmc.getInfoLabel('System.CurrentWindow')}", "DEBUG")
        utils.log(f"Post-nav control: {xbmc.getInfoLabel('System.CurrentControl')}", "DEBUG")
        
        # Clear navigation flag
        self.set_navigation_in_progress(False)
        utils.log("=== NAVIGATION COMPLETED ===", "DEBUG")

    def navigate_to_list_delayed(self, list_id, delay_seconds=2.0):
        """Navigate to a list with delayed execution for modal cleanup"""
        try:
            from resources.lib.config.addon_ref import get_addon
            from urllib.parse import urlencode
            import threading
            import time

            def delayed_navigate():
                try:
                    # Wait for modal cleanup
                    time.sleep(delay_seconds)
                    
                    utils.log(f"=== DELAYED_LIST_NAVIGATION: Starting navigation to list {list_id} ===", "DEBUG")
                    utils.log(f"Pre-delay window: {xbmc.getInfoLabel('System.CurrentWindow')}", "DEBUG")
                    
                    # Build plugin URL
                    addon = get_addon()
                    addon_id = addon.getAddonInfo("id")
                    params = urlencode({'action': 'browse_list', 'list_id': str(list_id)})
                    target_url = f"plugin://{addon_id}/?{params}"
                    
                    utils.log(f"Constructed URL: {target_url}", "DEBUG")
                    
                    # Clear any lingering modal states
                    xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
                    xbmc.executebuiltin("Dialog.Close(all,true)")
                    
                    # Brief wait for cleanup
                    time.sleep(0.5)
                    
                    # Navigate using Container.Update WITHOUT replace to preserve back button
                    utils.log(f"=== DELAYED_LIST_NAVIGATION: Using Container.Update WITHOUT replace ===", "DEBUG")
                    xbmc.executebuiltin(f'Container.Update("{target_url}")')
                    
                    utils.log(f"=== DELAYED_LIST_NAVIGATION: Navigation completed for list {list_id} ===", "DEBUG")
                    
                except Exception as e:
                    utils.log(f"Error in delayed list navigation: {str(e)}", "ERROR")
                    import traceback
                    utils.log(f"Delayed list navigation traceback: {traceback.format_exc()}", "ERROR")
            
            # Start navigation in background thread
            nav_thread = threading.Thread(target=delayed_navigate)
            nav_thread.daemon = True
            nav_thread.start()
            
        except Exception as e:
            utils.log(f"Error scheduling delayed list navigation: {str(e)}", "ERROR")

    def navigate_with_back_support(self, url: str, operation_name: str = "Unknown"):
        """Navigate while preserving Kodi's back button functionality"""
        utils.log(f"=== BACK-FRIENDLY NAVIGATION START: {operation_name} ===", "DEBUG")
        utils.log(f"Source window: {xbmc.getInfoLabel('System.CurrentWindow')}", "DEBUG")
        utils.log(f"Source URL: {xbmc.getInfoLabel('Container.FolderPath')}", "DEBUG")
        utils.log(f"Target URL: {url}", "DEBUG")
        
        self.set_navigation_in_progress(True)
        
        # Use Container.Update WITHOUT replace to preserve navigation history
        utils.log("=== Using Container.Update WITHOUT replace (preserves back button) ===", "DEBUG")
        xbmc.executebuiltin(f'Container.Update("{url}")')
        
        # Brief wait for navigation to complete
        xbmc.sleep(100)
        
        utils.log(f"Target window: {xbmc.getInfoLabel('System.CurrentWindow')}", "DEBUG")
        utils.log(f"Target path: {xbmc.getInfoLabel('Container.FolderPath')}", "DEBUG")
        
        self.set_navigation_in_progress(False)
        utils.log(f"=== BACK-FRIENDLY NAVIGATION COMPLETED: {operation_name} ===", "DEBUG")

    def refresh_current_container(self, operation_name: str = "Unknown"):
        """Refresh current container while preserving navigation stack"""
        utils.log(f"=== CONTAINER REFRESH: {operation_name} ===", "DEBUG")
        utils.log(f"Current window: {xbmc.getInfoLabel('System.CurrentWindow')}", "DEBUG")
        utils.log(f"Current path: {xbmc.getInfoLabel('Container.FolderPath')}", "DEBUG")
        
        # Container.Refresh preserves the navigation stack
        xbmc.executebuiltin('Container.Refresh')
        
        utils.log(f"=== CONTAINER REFRESH COMPLETED: {operation_name} ===", "DEBUG")

# Global navigation manager instance
_nav_manager = None

def get_navigation_manager():
    """Get the singleton navigation manager instance"""
    global _nav_manager
    if _nav_manager is None:
        _nav_manager = NavigationManager()
    return _nav_manager
