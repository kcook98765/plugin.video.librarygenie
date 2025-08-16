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

        # Create menu options - check if we have IMDb ID for similarity
        # Get IMDb ID from our custom ListItem property (set by listitem_builder.py)
        imdb_id = xbmc.getInfoLabel('ListItem.Property(LibraryGenie.IMDbID)')
        
        # Simple fallback for non-LibraryGenie items
        if not imdb_id:
            fallback_candidates = [
                xbmc.getInfoLabel('ListItem.IMDBNumber'),
                xbmc.getInfoLabel('ListItem.UniqueID(imdb)')
            ]
            for candidate in fallback_candidates:
                if candidate and str(candidate).startswith('tt'):
                    imdb_id = candidate
                    break
        
        if imdb_id:
            xbmc.log(f"LibraryGenie: Context menu found IMDb ID: {imdb_id}", xbmc.LOGINFO)

        options = []

        if imdb_id and str(imdb_id).startswith('tt'):
            options.append("Find Similar Movies...")

        options.extend([
            "Search Movies...",
            "Search History", 
            "Settings"
        ])

        if len(options) == 0:
            return

        # Show selection dialog
        dialog = xbmcgui.Dialog()
        selected = dialog.select("LibraryGenie Options", options)

        if selected == -1:  # User cancelled
            return

        selected_option = options[selected]

        if selected_option == "Find Similar Movies...":
            # Get the clean title without color formatting
            clean_title = item_info.get('title', 'Unknown').replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
            year = item_info.get('year', '')

            xbmc.log(f"LibraryGenie [DEBUG]: Similarity search - Title: {clean_title}, Year: {year}, IMDb: {imdb_id}", xbmc.LOGDEBUG)

            if not imdb_id or not str(imdb_id).startswith('tt'):
                xbmc.log("LibraryGenie [WARNING]: Similarity search failed - no valid IMDb ID found", xbmc.LOGWARNING)
                dialog.notification("LibraryGenie", "No valid IMDb ID found for similarity search", xbmcgui.NOTIFICATION_WARNING, 3000)
                return

            # Use RunPlugin to trigger similarity search
            from urllib.parse import quote_plus
            encoded_title = quote_plus(clean_title)
            similarity_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=find_similar&imdb_id={imdb_id}&title={encoded_title})'
            xbmc.executebuiltin(similarity_url)

        elif selected_option == "Search Movies...":  # Search Movies - use direct search instead of plugin URL
            # Import here to avoid circular imports
            from resources.lib.window_search import SearchWindow

            try:
                # Perform search directly
                search_window = SearchWindow("LibraryGenie Search")
                search_window.doModal()

                # Check if we have a target URL to navigate to
                target_url = search_window.get_target_url()
                if target_url:
                    xbmc.log(f"LibraryGenie: Context menu navigation to: {target_url}", xbmc.LOGINFO)
                    # Give time for modal to fully close
                    xbmc.sleep(300)
                    # Use ActivateWindow for more reliable navigation from context menu
                    xbmc.executebuiltin(f'ActivateWindow(videos,"{target_url}",return)')

            except Exception as search_error:
                xbmc.log(f"LibraryGenie: Context search error: {str(search_error)}", xbmc.LOGERROR)

        elif selected_option == "Search History":  # Search History
            url = f"plugin://{addon_id}/?action=browse_folder&folder_name=Search History"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected_option == "Settings":  # Settings
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