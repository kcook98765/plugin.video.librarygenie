
import os
import sys
import json
import requests

# Add addon directory to Python path
addon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(addon_dir)

import xbmc
import xbmcgui
import xbmcaddon
from resources.lib.kodi_helper import KodiHelper
from resources.lib.window_main import MainWindow

def register_beta_user(addon):
    dialog = xbmcgui.Dialog()
    code = dialog.input("Enter 6-digit Beta Code", type=xbmcgui.INPUT_NUMERIC)
    
    if not code or len(code) != 6:
        dialog.notification("LibraryGenie", "Invalid code format", xbmcgui.NOTIFICATION_ERROR, 2000)
        return

    api_url = addon.getSetting('lgs_upload_url').rstrip('/') + '/api/v1/api_info/create-user'
    
    try:
        response = requests.post(
            api_url,
            headers={'Content-Type': 'application/json'},
            json={'code': code}
        )
        
        data = response.json()
        
        if data.get('status') == 'success' and 'user' in data:
            user = data['user']
            addon.setSetting('lgs_upload_key', user['api_token'])
            addon.setSetting('lgs_username', user['username'])
            addon.setSetting('lgs_password', user['password'])
            
            dialog.ok("Success", f"Registration successful!\nUsername: {user['username']}\nPassword: {user['password']}\n\nPlease save these credentials securely.")
        else:
            dialog.ok("Error", "Registration failed: " + data.get('message', 'Unknown error'))
            
    except Exception as e:
        dialog.ok("Error", f"Failed to register: {str(e)}")

def build_context_menu():
    xbmc.executebuiltin('Dialog.Close(all, true)')
    addon = xbmcaddon.Addon()
    options = [
        xbmcgui.ListItem("Item Management"),
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
    elif choice == 1:  # Beta Signup
        register_beta_user(addon)
    elif choice == 2:  # Additional Feature
        dialog.notification("LibraryGenie", "Feature coming soon", xbmcgui.NOTIFICATION_INFO, 2000)

if __name__ == '__main__':
    build_context_menu()
