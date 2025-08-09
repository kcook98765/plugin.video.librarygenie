
import os
import sys
import json
import urllib.request
import urllib.parse

# Add addon directory to Python path
addon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(addon_dir)

import xbmc
import xbmcgui
from .addon_ref import get_addon
from resources.lib.kodi_helper import KodiHelper
from resources.lib.window_main import MainWindow

def authenticate_user():
    """Authenticate user with one-time code"""
    from resources.lib.authenticate_code import authenticate_with_code
    return authenticate_with_code()

def register_beta_user(addon):
    """Register user for beta access using one-time code"""
    from resources.lib.authenticate_code import authenticate_with_code
    success = authenticate_with_code()
    if success:
        xbmcgui.Dialog().notification(
            "LibraryGenie", 
            "Beta registration successful!", 
            xbmcgui.NOTIFICATION_INFO, 
            3000
        )
    else:
        xbmcgui.Dialog().notification(
            "LibraryGenie", 
            "Beta registration failed", 
            xbmcgui.NOTIFICATION_ERROR, 
            3000
        )

def build_context_menu():
    xbmc.executebuiltin('Dialog.Close(all, true)')
    addon = get_addon()
    options = [
        xbmcgui.ListItem("Item Management"),
        xbmcgui.ListItem("Search Movies"),
        xbmcgui.ListItem("Beta Signup"),
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
    elif choice == 1:  # Search Movies
        from resources.lib.window_search import SearchWindow
        search_window = SearchWindow()
        search_window.doModal()
        # Get results if needed
        results = search_window.get_search_results()
        del search_window
    elif choice == 2:  # Beta Signup
        register_beta_user(addon)
    elif choice == 3:  # Additional Feature
        dialog.notification("LibraryGenie", "Feature coming soon", xbmcgui.NOTIFICATION_INFO, 2000)

if __name__ == '__main__':
    build_context_menu()
