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

        # Navigate to plugin interface instead of custom window
        addon = get_addon()
        addon_id = addon.getAddonInfo("id")

        # Launch plugin browser
        import xbmc
        url = f"plugin://{addon_id}/?action=browse&title={item_info.get('title', 'Item')}"
        xbmc.executebuiltin(f'ActivateWindow(videos,{url})')

        xbmcgui.Dialog().notification("LibraryGenie", f"Browse lists for: {item_info.get('title', 'Unknown')}", xbmcgui.NOTIFICATION_INFO, 3000)

    except Exception as e:
        xbmc.log(f"LibraryGenie: Context menu error: {str(e)}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"LibraryGenie: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("LibraryGenie", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

if __name__ == '__main__':
    main()