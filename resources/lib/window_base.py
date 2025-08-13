import xbmcgui
from resources.lib import utils
from resources.lib.singleton_base import Singleton

class BaseWindow(Singleton):
    def __init__(self, title=""):
        if not hasattr(self, '_initialized'):
            # Only call super().__init__() if this is the first initialization
            if not hasattr(self.__class__, '_singleton_initialized'):
                super().__init__()
                self.__class__._singleton_initialized = True
            self.title = title
            self._initialized = True

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

    def doModal(self):
        """Compatibility method for modal display"""
        pass

    def close(self):
        """Compatibility method for close"""
        pass