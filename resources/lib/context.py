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

        # Show Details - always available
        options.append("Show Details")

        # Information - always available  
        options.append("Information")

        # Debug IMDB - always available if an IMDB ID is detected
        if imdb_id and str(imdb_id).startswith('tt'):
            options.append("Debug IMDB")

        # Check if we're currently viewing a LibraryGenie list (to offer Remove option)
        current_container_path = xbmc.getInfoLabel('Container.FolderPath')
        viewing_list_id = None
        is_librarygenie_list = False

        if 'browse_list' in current_container_path and 'list_id=' in current_container_path and 'plugin.video.librarygenie' in current_container_path:
            try:
                import re
                match = re.search(r'list_id=(\d+)', current_container_path)
                if match:
                    extracted_list_id = match.group(1)
                    xbmc.log(f"LibraryGenie: Detected potential list_id: {extracted_list_id}", xbmc.LOGDEBUG)

                    # Verify this list exists in our database
                    try:
                        from resources.lib.config_manager import Config
                        from resources.lib.database_manager import DatabaseManager

                        config = Config()
                        db_manager = DatabaseManager(config.db_path)
                        list_data = db_manager.fetch_list_by_id(extracted_list_id)

                        if list_data:
                            viewing_list_id = extracted_list_id
                            is_librarygenie_list = True
                            xbmc.log(f"LibraryGenie: Confirmed viewing LibraryGenie list_id: {viewing_list_id}", xbmc.LOGDEBUG)
                        else:
                            xbmc.log(f"LibraryGenie: List {extracted_list_id} not found in database - not a LibraryGenie list", xbmc.LOGDEBUG)
                    except Exception as db_error:
                        xbmc.log(f"LibraryGenie: Error verifying list in database: {str(db_error)}", xbmc.LOGDEBUG)

            except Exception as e:
                xbmc.log(f"LibraryGenie: Error extracting list_id: {str(e)}", xbmc.LOGDEBUG)

        # Add movie to a list - available when IMDb ID is detected
        if imdb_id and str(imdb_id).startswith('tt'):
            if viewing_list_id and is_librarygenie_list:
                # If viewing a LibraryGenie list, offer Remove option first
                options.append("Remove from List...")
                options.append("Add to Another List...")
            else:
                # If not viewing a LibraryGenie list, offer Add option
                options.append("Add to List...")

        # Find Similar Movies - only if authenticated AND has valid IMDb ID
        if imdb_id and str(imdb_id).startswith('tt'):
            if is_authenticated:
                options.append("Find Similar Movies...")
            else:
                options.append("Find Similar Movies... (Requires Authentication)")

        # Refresh Metadata - always available
        options.append("Refresh Metadata")

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

        if selected_option == "Show Details":
            # Show item details
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

                # Get item ID from various sources
                item_id = (xbmc.getInfoLabel('ListItem.DBID') or 
                          xbmc.getInfoLabel('ListItem.Property(movieid)') or 
                          xbmc.getInfoLabel('ListItem.Property(id)') or "")

                from urllib.parse import quote_plus
                encoded_title = quote_plus(clean_title)
                details_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=show_item_details&title={encoded_title}&item_id={item_id})'
                xbmc.executebuiltin(details_url)

            except Exception as details_error:
                xbmc.log(f"LibraryGenie: Error showing details: {str(details_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error showing details", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif selected_option == "Information":
            xbmc.executebuiltin("Action(Info)")
        elif selected_option == "Debug IMDB":
            # Import here to avoid circular imports
            from resources.lib.route_handlers import debug_imdb_info

            try:
                debug_imdb_info({'imdb_id': [imdb_id] if imdb_id else []})
            except Exception as debug_error:
                xbmc.log(f"LibraryGenie: Debug IMDB error: {str(debug_error)}", xbmc.LOGERROR)

        elif selected_option == "Remove from List...":
            # Handle removing movie from current list
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF0DC8A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF4BC7B]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

                # Get media_id from ListItem properties (set by listitem_builder)
                media_id = xbmc.getInfoLabel('ListItem.Property(media_id)')
                if not media_id:
                    # Fallback to other ID sources
                    media_id = (xbmc.getInfoLabel('ListItem.DBID') or 
                              xbmc.getInfoLabel('ListItem.Property(movieid)') or 
                              xbmc.getInfoLabel('ListItem.Property(id)') or "")

                xbmc.log(f"LibraryGenie: Remove from list - Title: {clean_title}, List ID: {viewing_list_id}, Media ID: {media_id}", xbmc.LOGDEBUG)

                if viewing_list_id and media_id:
                    # Use RunPlugin to trigger remove_from_list action
                    from urllib.parse import quote_plus
                    encoded_title = quote_plus(clean_title)
                    remove_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={viewing_list_id}&media_id={media_id})'
                    xbmc.executebuiltin(remove_url)
                else:
                    xbmcgui.Dialog().notification("LibraryGenie", "Cannot determine list or media ID", xbmcgui.NOTIFICATION_WARNING, 3000)

            except Exception as remove_error:
                xbmc.log(f"LibraryGenie: Error removing movie from list: {str(remove_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error removing movie from list", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif selected_option in ["Add to List...", "Add to Another List..."]:
            # Handle adding movie to list
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF0DC8A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF4BC7B]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFECA9A7]', '').replace('[/COLOR]', '')

                # Get item ID from various sources
                item_id = (xbmc.getInfoLabel('ListItem.DBID') or 
                          xbmc.getInfoLabel('ListItem.Property(movieid)') or 
                          xbmc.getInfoLabel('ListItem.Property(id)') or "")

                # Use RunPlugin to trigger add_to_list action
                from urllib.parse import quote_plus
                encoded_title = quote_plus(clean_title)
                add_to_list_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=add_to_list&title={encoded_title}&item_id={item_id})'
                xbmc.executebuiltin(add_to_list_url)

            except Exception as add_error:
                xbmc.log(f"LibraryGenie: Error adding movie to list: {str(add_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error adding movie to list", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif selected_option == "Refresh Metadata":
            # Refresh metadata
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

                # Get item ID from various sources
                item_id = (xbmc.getInfoLabel('ListItem.DBID') or 
                          xbmc.getInfoLabel('ListItem.Property(movieid)') or 
                          xbmc.getInfoLabel('ListItem.Property(id)') or "")

                from urllib.parse import quote_plus
                encoded_title = quote_plus(clean_title)
                refresh_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=refresh_metadata&title={encoded_title}&item_id={item_id})'
                xbmc.executebuiltin(refresh_url)

            except Exception as refresh_error:
                xbmc.log(f"LibraryGenie: Error refreshing metadata: {str(refresh_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error refreshing metadata", xbmcgui.NOTIFICATION_ERROR, 3000)

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
                from resources.lib import utils
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