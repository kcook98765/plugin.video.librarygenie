import os
import sys
import xbmc
import xbmcgui
import xbmcaddon

try:
    import xbmcvfs
    translatePath = xbmcvfs.translatePath
except Exception:
    import xbmc
    translatePath = xbmc.translatePath

# Get addon and setup paths
ADDON = xbmcaddon.Addon()
ADDON_PATH = translatePath(ADDON.getAddonInfo("path"))

# Ensure the addon root directory is in the Python path for imports to work
if ADDON_PATH not in sys.path:
    sys.path.insert(0, ADDON_PATH)

# Import required modules using absolute imports
from resources.lib.kodi_helper import KodiHelper
from resources.lib.addon_ref import get_addon

def main():
    """Main entry point for context menu actions"""
    try:
        import xbmc
        xbmc.log("LibraryGenie: Context menu script started", xbmc.LOGINFO)

        addon = get_addon()
        if not addon:
            xbmc.log("LibraryGenie: Failed to get addon instance", xbmc.LOGERROR)
            return

        # Get the current item's information
        kodi_helper = KodiHelper()
        item_info = kodi_helper.get_focused_item_details()

        if not item_info:
            xbmc.log("LibraryGenie: No item information found", xbmc.LOGWARNING)
            xbmcgui.Dialog().notification("LibraryGenie", "No item selected", xbmcgui.NOTIFICATION_WARNING, 2000)
            return

        xbmc.log(f"LibraryGenie: Got item info for: {item_info.get('title', 'Unknown')}", xbmc.LOGINFO)

        # Show context menu options
        addon = get_addon()
        addon_id = addon.getAddonInfo("id")

        # Create menu options
        options = [
            "Search Movies...",
            "Browse Lists",
            "Search History",
            "Settings"
        ]

        # Show dialog to select option
        selected = xbmcgui.Dialog().contextmenu(options)
        
        if selected == 0:  # Search Movies
            url = f"plugin://{addon_id}/?action=search"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == 1:  # Browse Lists
            url = f"plugin://{addon_id}/"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == 2:  # Search History
            url = f"plugin://{addon_id}/?action=browse_folder&folder_name=Search History"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == 3:  # Settings
            xbmc.executebuiltin(f'Addon.OpenSettings({addon_id})')
        # If nothing selected (selected == -1), do nothing

    except Exception as e:
        xbmc.log(f"LibraryGenie: Context menu error: {str(e)}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"LibraryGenie: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("LibraryGenie", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

if __name__ == '__main__':
    main()