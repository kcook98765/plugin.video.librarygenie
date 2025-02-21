
import xbmc
import xbmcgui
import os

class ZoomPanDialog(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self.service = kwargs.get('service')
        self.image_path = kwargs.get('image_path')
        self.pointer_x = 960  # Center
        self.pointer_y = 540
        self.move_delta = 20
        self.zoom_level = 1.0
        self.zoom_step = 0.25
        self.calibration_mode = False
        self.calibration_points = []
        self.offset_x = 0
        self.offset_y = 0
        self.scale = 1.0
        super(ZoomPanDialog, self).__init__(*args, **kwargs)

    def onInit(self):
        self.pointer = self.getControl(102)
        self.background = self.getControl(101)
        self.coord_label = self.getControl(103)
        
        # Set the image path
        self.background.setImage(self.image_path)
        self.updatePointer()

    def onAction(self, action):
        if action in [xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT, 
                     xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN]:
            self.handleNavigation(action)
        elif action in [xbmcgui.ACTION_MOUSE_WHEEL_UP]:
            self.zoom_level = min(4.0, self.zoom_level + self.zoom_step)
            self.updateZoom()
        elif action in [xbmcgui.ACTION_MOUSE_WHEEL_DOWN]:
            self.zoom_level = max(1.0, self.zoom_level - self.zoom_step)
            self.updateZoom()
        elif action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()

    def handleNavigation(self, action):
        if action == xbmcgui.ACTION_MOVE_LEFT:
            self.pointer_x -= self.move_delta
        elif action == xbmcgui.ACTION_MOVE_RIGHT:
            self.pointer_x += self.move_delta
        elif action == xbmcgui.ACTION_MOVE_UP:
            self.pointer_y -= self.move_delta
        elif action == xbmcgui.ACTION_MOVE_DOWN:
            self.pointer_y += self.move_delta
        
        self.updatePointer()
        
    def updatePointer(self):
        # Bound checking
        self.pointer_x = max(20, min(1900, self.pointer_x))
        self.pointer_y = max(20, min(1060, self.pointer_y))
        
        bg_x, bg_y = self.background.getPosition()
        
        # Zoom adjustment
        adjusted_x = self.pointer_x
        adjusted_y = self.pointer_y
        if self.zoom_level != 1.0:
            adjusted_x = self.pointer_x - bg_x
            adjusted_y = self.pointer_y - bg_y
            
        # Update pointer position
        self.pointer.setPosition(self.pointer_x, self.pointer_y)
        
        # Update display
        self.coord_label.setLabel(f"Position: ({adjusted_x},{adjusted_y}) Zoom: {self.zoom_level:.1f}x")
        
        # Notify observers
        if self.service:
            self.service.notify_observers(adjusted_x, adjusted_y, not self.calibration_mode, 
                                        adjusted_x, adjusted_y)

    def updateZoom(self):
        base_width = 1920
        base_height = 1080
        zoomed_width = int(base_width * self.zoom_level)
        zoomed_height = int(base_height * self.zoom_level)
        
        bg_x, bg_y = self.background.getPosition()
        
        max_offset_x = zoomed_width - base_width
        max_offset_y = zoomed_height - base_height
        
        edge_margin = 100
        if self.pointer_x < edge_margin:
            bg_x = min(0, bg_x + self.move_delta)
        elif self.pointer_x > base_width - edge_margin:
            bg_x = max(-max_offset_x, bg_x - self.move_delta)
            
        if self.pointer_y < edge_margin:
            bg_y = min(0, bg_y + self.move_delta)
        elif self.pointer_y > base_height - edge_margin:
            bg_y = max(-max_offset_y, bg_y - self.move_delta)
        
        self.background.setPosition(bg_x, bg_y)
        self.background.setWidth(zoomed_width)
        self.background.setHeight(zoomed_height)
