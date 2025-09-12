"""
View Orientation Detector for LibraryGenie

Simple, elegant solution that detects whether the current view is vertical (list-style) 
or horizontal (panel/grid-style) and sends appropriate navigation actions instead of 
trying to guess control IDs.
"""

import xbmc
import xbmcgui
from typing import Optional, Literal

class ViewOrientationDetector:
    """Detects view orientation and provides appropriate navigation actions"""
    
    # View modes that use vertical navigation (Down/Up arrows)
    VERTICAL_VIEWS = {
        "list", "widelist", "lowlist", "bannerlist", "biglist", 
        "infolist", "detaillist", "episodes", "songs"
    }
    
    # View modes that use horizontal navigation (Right/Left arrows)  
    HORIZONTAL_VIEWS = {
        "wall", "poster", "panel", "thumbs", "iconwall", "fanart",
        "shift", "showcase", "thumbnails", "icons", "grid", "wrap"
    }
    
    def __init__(self):
        self.logger = xbmc.log
    
    def get_current_view_orientation(self) -> Literal["vertical", "horizontal", "unknown"]:
        """
        Detect the orientation of the current view mode.
        
        Returns:
            "vertical" for list-style views (use Down/Up navigation)
            "horizontal" for panel/grid-style views (use Right/Left navigation)  
            "unknown" if view mode can't be determined
        """
        try:
            # Get current view mode from Kodi
            view_mode = xbmc.getInfoLabel("Container.Viewmode").lower().strip()
            
            if not view_mode:
                self.logger("ViewOrientationDetector: No viewmode detected", xbmc.LOGDEBUG)
                return "unknown"
                
            self.logger(f"ViewOrientationDetector: Current viewmode = '{view_mode}'", xbmc.LOGDEBUG)
            
            # Check against known vertical view types
            if view_mode in self.VERTICAL_VIEWS:
                return "vertical"
                
            # Check against known horizontal view types  
            if view_mode in self.HORIZONTAL_VIEWS:
                return "horizontal"
                
            # Try partial matching for custom view names
            for vertical_view in self.VERTICAL_VIEWS:
                if vertical_view in view_mode:
                    return "vertical"
                    
            for horizontal_view in self.HORIZONTAL_VIEWS:
                if horizontal_view in view_mode:
                    return "horizontal"
            
            self.logger(f"ViewOrientationDetector: Unknown viewmode '{view_mode}'", xbmc.LOGWARNING)
            return "unknown"
            
        except Exception as e:
            self.logger(f"ViewOrientationDetector: Error detecting viewmode: {e}", xbmc.LOGERROR)
            return "unknown"
    
    def navigate_to_next_item(self) -> bool:
        """
        Navigate to the next item based on current view orientation.
        
        Returns:
            True if navigation was attempted, False if orientation unknown
        """
        orientation = self.get_current_view_orientation()
        
        if orientation == "vertical":
            # Send Down action for list-style views
            xbmc.executebuiltin("Action(Down)")
            self.logger("ViewOrientationDetector: Sent Down action for vertical view", xbmc.LOGDEBUG)
            return True
            
        elif orientation == "horizontal":
            # Send Right action for panel/grid-style views
            xbmc.executebuiltin("Action(Right)")  
            self.logger("ViewOrientationDetector: Sent Right action for horizontal view", xbmc.LOGDEBUG)
            return True
            
        else:
            # Unknown orientation - try both as fallback
            self.logger("ViewOrientationDetector: Unknown orientation, trying Down first", xbmc.LOGWARNING)
            xbmc.executebuiltin("Action(Down)")
            return False
    
    def navigate_to_previous_item(self) -> bool:
        """
        Navigate to the previous item based on current view orientation.
        
        Returns:
            True if navigation was attempted, False if orientation unknown
        """
        orientation = self.get_current_view_orientation()
        
        if orientation == "vertical":
            # Send Up action for list-style views
            xbmc.executebuiltin("Action(Up)")
            self.logger("ViewOrientationDetector: Sent Up action for vertical view", xbmc.LOGDEBUG)
            return True
            
        elif orientation == "horizontal":
            # Send Left action for panel/grid-style views
            xbmc.executebuiltin("Action(Left)")
            self.logger("ViewOrientationDetector: Sent Left action for horizontal view", xbmc.LOGDEBUG)
            return True
            
        else:
            # Unknown orientation - try Up as fallback
            self.logger("ViewOrientationDetector: Unknown orientation, trying Up", xbmc.LOGWARNING)
            xbmc.executebuiltin("Action(Up)")
            return False
    
    def get_debug_info(self) -> dict:
        """Get debug information about current view state"""
        try:
            view_mode = xbmc.getInfoLabel("Container.Viewmode")
            orientation = self.get_current_view_orientation()
            container_id = xbmc.getInfoLabel("System.CurrentControlId")
            
            return {
                "view_mode": view_mode,
                "orientation": orientation,
                "container_id": container_id,
                "vertical_views": list(self.VERTICAL_VIEWS),
                "horizontal_views": list(self.HORIZONTAL_VIEWS)
            }
        except Exception as e:
            return {"error": str(e)}