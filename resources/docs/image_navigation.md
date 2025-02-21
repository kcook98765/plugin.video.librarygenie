Image Navigation System Implementation Guide
Overview

This system provides image navigation capabilities with:

    Zoom in/out (1.0x to 4.0x)
    Real-time coordinate tracking
    Pan support when zoomed
    Calibration system for coordinate mapping
    Support for high-resolution images

Core Components
1. Navigation Service

The navigation service manages state and coordinates observers:

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
            self.dialog = ZoomPanDialog("MyDialog.xml", addon_path, "Default", "1080i", 
                                      service=self,
                                      image_path=image_path)
        self.dialog.show()

2. Navigation Dialog Implementation

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
        self.updatePointer()

    def updatePointer(self):
        # Bound checking
        self.pointer_x = max(20, min(1900, self.pointer_x))
        self.pointer_y = max(20, min(1060, self.pointer_y))
        
        background = self.getControl(101)
        bg_x, bg_y = background.getPosition()
        
        # Zoom adjustment
        adjusted_x = self.pointer_x
        adjusted_y = self.pointer_y
        if self.zoom_level != 1.0:
            adjusted_x = self.pointer_x - bg_x
            adjusted_y = self.pointer_y - bg_y
            
        # Calibration transform
        img_x, img_y = self.screenToRaw(adjusted_x, adjusted_y)
        
        self.pointer.setPosition(self.pointer_x, self.pointer_y)
        
        # Update display
        coord_label = self.getControl(103)
        coord_label.setLabel(f"Screen: ({img_x},{img_y}) Raw: ({raw_x:.1f},{raw_y:.1f}) Zoom: {self.zoom_level:.1f}x")
        
        # Notify observers
        if self.service:
            self.service.notify_observers(img_x, img_y, not self.calibration_mode, raw_x, raw_y)

3. Calibration System

def startCalibration(self):
    self.calibration_mode = True
    self.calibration_points = []
    calibration_steps = [
        (0, 0, "Move pointer to TOP-LEFT of image and press SELECT"),
        (1920, 1080, "Move pointer to BOTTOM-RIGHT of image and press SELECT")
    ]
    self.current_calibration_step = 0
    self.calibration_steps = calibration_steps
    dialog = xbmcgui.Dialog()
    dialog.ok("Calibration", "Starting calibration.\n" + calibration_steps[0][2])

def finishCalibration(self):
    p1 = self.calibration_points[0]
    p2 = self.calibration_points[1]
    
    self.offset_x = p1['screen'][0]
    self.offset_y = p1['screen'][1]
    
    scale_x = (p2['screen'][0] - p1['screen'][0]) / (p2['raw'][0] - p1['raw'][0])
    scale_y = (p2['screen'][1] - p1['screen'][1]) / (p2['raw'][1] - p1['raw'][1])
    self.scale = (scale_x + scale_y) / 2
    
    self.calibration_mode = False

4. Zoom and Pan Management

def updateZoom(self):
    background = self.getControl(101)
    
    base_width = 1920
    base_height = 1080
    zoomed_width = int(base_width * self.zoom_level)
    zoomed_height = int(base_height * self.zoom_level)
    
    bg_x, bg_y = background.getPosition()
    
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
    
    background.setPosition(bg_x, bg_y)
    background.setWidth(zoomed_width)
    background.setHeight(zoomed_height)

Integration Steps

    Create the navigation service singleton in your addon:

_navigation_service = NavigationService()

def get_navigation_service():
    return _navigation_service

    Create the XML window definition (MyDialog.xml):

<?xml version="1.0" encoding="UTF-8"?>
<window>
    <controls>
        <control type="image" id="101">
            <description>Background Image</description>
            <left>0</left>
            <top>0</top>
            <width>1920</width>
            <height>1080</height>
            <texture>$INFO[Window.Property(ImagePath)]</texture>
        </control>
        <control type="image" id="102">
            <description>Pointer</description>
            <left>960</left>
            <top>540</top>
            <width>40</width>
            <height>40</height>
            <texture>pointer.png</texture>
        </control>
        <control type="label" id="103">
            <description>Coordinates</description>
            <left>20</left>
            <top>20</top>
            <width>500</width>
            <height>30</height>
            <font>font12</font>
            <textcolor>FFFFFFFF</textcolor>
        </control>
    </controls>
</window>

    Usage in your addon:

from navigation_service import get_navigation_service

def my_callback(x, y, is_calibrated, raw_x, raw_y):
    # Handle coordinate updates
    pass

nav_service = get_navigation_service()
nav_service.register_observer(my_callback)
nav_service.start_navigation("path/to/image.jpg")