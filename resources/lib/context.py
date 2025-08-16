import sys
import xbmcgui
import xbmcaddon
import xbmcvfs
translatePath = xbmcvfs.translatePath

# Get addon and setup paths FIRST
ADDON = xbmcaddon.Addon()
ADDON_PATH = translatePath(ADDON.getAddonInfo("path"))

# Ensure the addon root directory is in the Python path for imports to work
if ADDON_PATH not in sys.path:
    sys.path.insert(0, ADDON_PATH)

# Import required modules AFTER setting up the path
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
            "Search History",
            "Settings"
        ]

        # Show dialog to select option
        selected = xbmcgui.Dialog().contextmenu(options)
        
        if selected == 0:  # Search Movies - use direct search instead of plugin URL
            # Import here to avoid circular imports
            from resources.lib.window_search import SearchWindow
            from resources.lib.navigation_manager import get_navigation_manager
            
            # Set context flag to indicate this is from context menu
            xbmc.executebuiltin("SetProperty(LibraryGenie.ContextSearch,true,Home)")
            
            try:
                # Perform search directly
                search_window = SearchWindow("LibraryGenie Search")
                search_window.doModal()
                
                # Check if we have a target URL to navigate to
                target_url = search_window.get_target_url()
                if target_url:
                    # Use navigation manager for proper flow control
                    nav_manager = get_navigation_manager()
                    xbmc.sleep(200)  # Brief delay to let modal close properly
                    nav_manager.navigate_to_url(target_url, replace=True)
                    
            except Exception as search_error:
                xbmc.log(f"LibraryGenie: Context search error: {str(search_error)}", xbmc.LOGERROR)
            finally:
                # Always clear the context flag
                xbmc.executebuiltin("ClearProperty(LibraryGenie.ContextSearch,Home)")
                
        elif selected == 1:  # Search History
            url = f"plugin://{addon_id}/?action=browse_folder&folder_name=Search History"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == 2:  # Settings
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