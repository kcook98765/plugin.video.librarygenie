import sys
import xbmcgui
import xbmcaddon
import xbmcvfs
translatePath = xbmcvfs.translatePath

# Get addon and setup paths
ADDON = xbmcaddon.Addon()
ADDON_PATH = translatePath(ADDON.getAddonInfo("path"))

# Ensure the addon root directory is in the Python path for imports to work
if ADDON_PATH not in sys.path:
    sys.path.insert(0, ADDON_PATH)

# Import required modules after path setup
try:
    from resources.lib.kodi_helper import KodiHelper
    from resources.lib.addon_ref import get_addon
except ImportError as e:
    import xbmc
    xbmc.log(f"LibraryGenie Context: Import error - {str(e)}", xbmc.LOGERROR)
    # Try alternative import method
    import os
    lib_path = os.path.join(ADDON_PATH, 'resources', 'lib')
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
    from kodi_helper import KodiHelper
    from addon_ref import get_addon

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
            "Search History",
            "Settings"
        ]
        
        # Add "Find Similar Movies" option if item has IMDb ID
        imdb_id = item_info.get('imdbnumber', '')
        if imdb_id and imdb_id.startswith('tt'):
            options.insert(0, "Find Similar Movies")

        # Show dialog to select option
        selected = xbmcgui.Dialog().contextmenu(options)
        
        # Check if "Find Similar Movies" is available
        has_similar_option = (imdb_id and imdb_id.startswith('tt'))
        
        if selected == 0 and has_similar_option:  # Find Similar Movies
            import urllib.parse
            title = item_info.get('title', 'Unknown Movie')
            encoded_title = urllib.parse.quote_plus(title)
            url = f"plugin://{addon_id}/?action=find_similar_movies&imdb_id={imdb_id}&title={encoded_title}"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == (1 if has_similar_option else 0):  # Search Movies
            url = f"plugin://{addon_id}/?action=search"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == (2 if has_similar_option else 1):  # Search History
            url = f"plugin://{addon_id}/?action=browse_folder&folder_name=Search History"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == (3 if has_similar_option else 2):  # Settings
            xbmc.executebuiltin(f'Addon.OpenSettings({addon_id})')
        # If nothing selected (selected == -1), do nothing

    except Exception as e:
        from resources.lib import utils
        utils.log(f"Context menu error: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

if __name__ == '__main__':
    main()