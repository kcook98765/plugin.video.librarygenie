"""
Simple Navigation Helpers for LibraryGenie

Replaces complex control ID mapping with elegant view-orientation detection.
Uses Container.Viewmode to determine navigation direction instead of guessing control IDs.
"""

import xbmc
import xbmcgui
import time
from .view_orientation_detector import ViewOrientationDetector

def _log(message, level=xbmc.LOGDEBUG):
    """Simple logging helper"""
    xbmc.log(f"LibraryGenie: {message}", level)

def focus_list_simple(tries: int = 3) -> bool:
    """
    Simple list navigation using view orientation detection.
    
    Instead of guessing control IDs, determines if current view is vertical or horizontal
    and sends appropriate navigation action (Down vs Right).
    
    Args:
        tries: Number of navigation attempts (much fewer needed than old approach)
        
    Returns:
        True if navigation was attempted successfully
    """
    t_start = time.perf_counter()
    
    try:
        detector = ViewOrientationDetector()
        
        # Get current view orientation
        orientation = detector.get_current_view_orientation()
        _log(f"focus_list_simple: Detected view orientation = '{orientation}'")
        
        # Try navigation based on orientation
        for attempt in range(tries):
            if orientation == "vertical":
                _log(f"Attempt {attempt + 1}: Sending Down action for vertical view")
                xbmc.executebuiltin("Action(Down)")
                
            elif orientation == "horizontal":
                _log(f"Attempt {attempt + 1}: Sending Right action for horizontal view")
                xbmc.executebuiltin("Action(Right)")
                
            else:
                # Unknown orientation - try Down first (most common)
                _log(f"Attempt {attempt + 1}: Unknown orientation, trying Down")
                xbmc.executebuiltin("Action(Down)")
            
            # Brief pause to let action take effect
            xbmc.sleep(100)
            
            # Check if we've successfully moved in the list
            # (We don't need to check specific control focus - just that navigation worked)
            
        t_end = time.perf_counter()
        _log(f"focus_list_simple: Completed navigation attempts in {t_end - t_start:.3f}s")
        return True
        
    except Exception as e:
        t_end = time.perf_counter()
        _log(f"focus_list_simple: Error during navigation: {e} (took {t_end - t_start:.3f}s)", xbmc.LOGERROR)
        return False

def verify_list_focus_simple() -> bool:
    """
    Simple check if we're in a list view.
    
    Returns True if Container.Viewmode indicates we're in any kind of list/grid view.
    Much simpler than checking specific control IDs.
    """
    try:
        detector = ViewOrientationDetector()
        orientation = detector.get_current_view_orientation()
        
        # If we can detect orientation, we're probably in a list/grid view
        in_list_view = orientation in ["vertical", "horizontal"]
        _log(f"verify_list_focus_simple: In list view = {in_list_view} (orientation: {orientation})")
        
        return in_list_view
        
    except Exception as e:
        _log(f"verify_list_focus_simple: Error checking view: {e}", xbmc.LOGWARNING)
        return False

def navigate_to_next_item() -> bool:
    """Navigate to next item based on current view orientation"""
    try:
        detector = ViewOrientationDetector()
        return detector.navigate_to_next_item()
    except Exception as e:
        _log(f"navigate_to_next_item: Error: {e}", xbmc.LOGERROR)
        return False

def navigate_to_previous_item() -> bool:
    """Navigate to previous item based on current view orientation"""
    try:
        detector = ViewOrientationDetector()
        return detector.navigate_to_previous_item()
    except Exception as e:
        _log(f"navigate_to_previous_item: Error: {e}", xbmc.LOGERROR)
        return False

def get_navigation_debug_info() -> dict:
    """Get debug info about current navigation state"""
    try:
        detector = ViewOrientationDetector()
        info = detector.get_debug_info()
        
        # Add some additional context
        info.update({
            "current_window": xbmc.getInfoLabel("System.CurrentWindow"),
            "current_control": xbmc.getInfoLabel("System.CurrentControlId"),
            "container_position": xbmc.getInfoLabel("Container.CurrentItem"),
            "container_total": xbmc.getInfoLabel("Container.NumItems")
        })
        
        return info
    except Exception as e:
        return {"error": str(e)}

# Compatibility functions to replace old approach
def focus_list_manual(*args, **kwargs) -> bool:
    """Compatibility wrapper - redirects to simple approach"""
    _log("focus_list_manual: Using simple navigation approach instead of control ID mapping")
    return focus_list_simple()

def verify_list_focus() -> bool:
    """Compatibility wrapper - redirects to simple approach"""
    return verify_list_focus_simple()