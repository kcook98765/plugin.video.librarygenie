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

        # Get basic item information that's available in context
        title = xbmc.getInfoLabel('ListItem.Title')
        year = xbmc.getInfoLabel('ListItem.Year')

        xbmc.log(f"LibraryGenie: Context menu for: {title} ({year})", xbmc.LOGINFO)

        # Show context menu options
        addon = get_addon()
        addon_id = addon.getAddonInfo("id")

        # Use existing KodiHelper to get IMDb ID (handles v19/v20+ compatibility)
        imdb_id = None
        try:
            from resources.lib.kodi_helper import KodiHelper
            kodi_helper = KodiHelper()
            imdb_id = kodi_helper.get_imdb_from_item()
            xbmc.log(f"LibraryGenie: IMDb ID from KodiHelper: {imdb_id}", xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f"LibraryGenie: Error getting IMDb ID via KodiHelper: {str(e)}", xbmc.LOGDEBUG)

        xbmc.log(f"LibraryGenie: Final IMDb ID detection result: {imdb_id}", xbmc.LOGDEBUG)

        options = []

        # Check authentication before adding API-dependent options
        from resources.lib.context_menu_builder import get_context_menu_builder
        context_builder = get_context_menu_builder()
        is_authenticated = context_builder._is_authenticated()

        # Add movie to a list - available when IMDb ID is detected
        if imdb_id and str(imdb_id).startswith('tt'):
            options.append("Add movie to a list...")

        # Find Similar Movies - only if authenticated AND has valid IMDb ID
        if imdb_id and str(imdb_id).startswith('tt'):
            if is_authenticated:
                options.append("Find Similar Movies...")
            else:
                options.append("Find Similar Movies... (Requires Authentication)")

        # Search Movies - only if authenticated
        if is_authenticated:
            options.append("Search Movies...")
        else:
            options.append("Search Movies... (Requires Authentication)")

        options.extend([
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

        if selected_option == "Add movie to a list...":
            # Handle adding movie to list
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
                
                # Use RunPlugin to trigger add_to_list action
                from urllib.parse import quote_plus
                encoded_title = quote_plus(clean_title)
                add_to_list_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=add_to_list_from_context&title={encoded_title}&imdb_id={imdb_id}&year={year})'
                xbmc.executebuiltin(add_to_list_url)
                
            except Exception as add_error:
                xbmc.log(f"LibraryGenie: Error adding movie to list: {str(add_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error adding movie to list", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif "Find Similar Movies..." in selected_option:
            if "(Requires Authentication)" in selected_option:
                dialog.notification("LibraryGenie", "Please configure API settings first", xbmcgui.NOTIFICATION_WARNING, 3000)
                return
                
            # Get the clean title without color formatting
            clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

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

        elif "Search Movies..." in selected_option:  # Search Movies - use direct search instead of plugin URL
            if "(Requires Authentication)" in selected_option:
                dialog.notification("LibraryGenie", "Please configure API settings first", xbmcgui.NOTIFICATION_WARNING, 3000)
                return
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
            # Get the Search History folder ID
            try:
                from resources.lib.config_manager import Config
                from resources.lib.database_manager import DatabaseManager
                
                config = Config()
                db_manager = DatabaseManager(config.db_path)
                search_history_folder_id = db_manager.get_folder_id_by_name("Search History")
                
                if search_history_folder_id:
                    url = f"plugin://{addon_id}/?action=browse_folder&folder_id={search_history_folder_id}&view=folder"
                    xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
                else:
                    xbmcgui.Dialog().notification("LibraryGenie", "Search History folder not found", xbmcgui.NOTIFICATION_WARNING, 3000)
                    
            except Exception as e:
                utils.log(f"Error accessing Search History: {str(e)}", "ERROR")
                xbmcgui.Dialog().notification("LibraryGenie", "Error accessing Search History", xbmcgui.NOTIFICATION_ERROR, 3000)
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