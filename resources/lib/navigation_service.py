
import xbmc
import xbmcaddon
import xbmcgui
from .navigation_dialog import ZoomPanDialog

class NavigationService:
    def __init__(self):
        self._addon = xbmcaddon.Addon()
        self.current_image = None
        self.dialog = None
        self._observers = []
        
    def register_observer(self, callback):
        self._observers.append(callback)
        
    def unregister_observer(self, callback):
        if callback in self._observers:
            self._observers.remove(callback)
            
    def notify_observers(self, x, y, is_calibrated, raw_x, raw_y):
        for callback in self._observers:
            try:
                callback(x, y, is_calibrated, raw_x, raw_y)
            except Exception as e:
                xbmc.log(f"Error in observer callback: {str(e)}", xbmc.LOGERROR)
                
    def start_navigation(self, image_path):
        self.current_image = image_path
        if not self.dialog:
            addon_path = self._addon.getAddonInfo('path')
            self.dialog = ZoomPanDialog("navigation_dialog.xml", addon_path, "Default", "1080i", 
                                      service=self,
                                      image_path=image_path)
        self.dialog.show()
