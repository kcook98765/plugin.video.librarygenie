import pyxbmct
import xbmcgui
from resources.lib import utils

class BaseWindow(pyxbmct.AddonDialogWindow):
    def __init__(self, title=""):
        super().__init__(title)
        
    def show_notification(self, message, icon=xbmcgui.NOTIFICATION_INFO):
        utils.show_notification("LibraryGenie", message, icon)
        
    def handle_name_input(self, current_name="", entity_type="item"):
        new_name = utils.show_dialog_input(f"Enter new {entity_type} name", current_name)
        if not new_name:
            self.show_notification("Invalid name entered", xbmcgui.NOTIFICATION_WARNING)
            return None
        return new_name
        
    def confirm_delete(self, name, entity_type="item"):
        return utils.show_dialog_yesno("Confirm Delete", f"Are you sure you want to delete the {entity_type} '{name}'?")

    def set_basic_navigation(self, control):
        """Set up basic navigation for a single control"""
        try:
            # First check if control exists and is valid
            if control and hasattr(control, 'getId') and control.getId() > 0:
                control.controlUp(control)
                control.controlDown(control)
                control.controlLeft(control)
                control.controlRight(control)
                # Only set focus if control is focusable
                if hasattr(control, 'setEnabled'):
                    control.setEnabled(True)
                self.setFocus(control)
        except Exception as e:
            utils.log(f"Error setting navigation for control: {str(e)}", "ERROR")
