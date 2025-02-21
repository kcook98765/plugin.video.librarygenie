import os
import sys
import xbmc
import xbmcgui
import xbmcaddon

# Add addon root to Python path
addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, addon_dir)

from resources.lib.kodi_helper import KodiHelper
from resources.lib.window_main import MainWindow


def build_context_menu():
    xbmc.executebuiltin('Dialog.Close(all, true)')
    addon = xbmcaddon.Addon()
    options = [
        xbmcgui.ListItem("Item Management"),
        xbmcgui.ListItem("Additional Feature")
    ]

    dialog = xbmcgui.Dialog()
    choice = dialog.select("LibraryGenie", options)

    if choice == 0:  # Item Management
        kodi_helper = KodiHelper()
        item_info = kodi_helper.get_focused_item_details()
        if item_info:
            window = MainWindow(item_info)
            window.doModal()
            del window
    elif choice == 1:  # Additional Feature
        # Placeholder for new feature
        dialog.notification("LibraryGenie", "Feature coming soon", xbmcgui.NOTIFICATION_INFO, 2000)

if __name__ == '__main__':
    build_context_menu()