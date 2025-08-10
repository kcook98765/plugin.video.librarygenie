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
from resources.lib.window_main import MainWindow
from resources.lib.addon_ref import get_addon

def main():
    """Main entry point for context menu actions"""
    try:
        xbmc.log("LibraryGenie: Context menu script started", xbmc.LOGINFO)
        
        # Check if we have arguments from the context menu
        action = None
        if len(sys.argv) > 1:
            action = sys.argv[1]
            xbmc.log(f"LibraryGenie: Context menu action: {action}", xbmc.LOGINFO)

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

        # Handle different actions
        if action == "search":
            # Launch search window directly
            from resources.lib.window_search import SearchWindow
            search_window = SearchWindow("LibraryGenie - Movie Search")
            search_window.doModal()
            del search_window
        elif action == "add_to_list":
            # Launch main window in "add to list" mode
            from resources.lib.window_main import MainWindow
            window = MainWindow(item_info, f"LibraryGenie - Add {item_info.get('title', 'Item')} to List")
            window.doModal()
            del window
        else:
            # Default: Launch the main window with full options
            from resources.lib.window_main import MainWindow
            window = MainWindow(item_info, f"LibraryGenie - {item_info.get('title', 'Item')}")
            window.doModal()
            del window

    except Exception as e:
        xbmc.log(f"LibraryGenie: Context menu error: {str(e)}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"LibraryGenie: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("LibraryGenie", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

if __name__ == '__main__':
    main()