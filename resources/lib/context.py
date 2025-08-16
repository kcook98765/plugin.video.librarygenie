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
        
        # Debug: Log all potentially useful InfoLabels for troubleshooting
        debug_labels = [
            'ListItem.DBID',
            'ListItem.IMDBNumber', 
            'ListItem.UniqueID(imdb)',
            'ListItem.Property(imdb_id)',
            'ListItem.Property(IMDbID)',
            'ListItem.Property(uniqueid.imdb)',
            'ListItem.Property(LibraryGenie.IMDbID)',
        ]
        
        xbmc.log("LibraryGenie: Available InfoLabels in context menu:", xbmc.LOGDEBUG)
        for label in debug_labels:
            value = xbmc.getInfoLabel(label)
            if value:
                xbmc.log(f"  {label}: {value}", xbmc.LOGDEBUG)

        # Show context menu options
        addon = get_addon()
        addon_id = addon.getAddonInfo("id")

        # Create menu options - check if we have IMDb ID for similarity
        # Get IMDb ID from available InfoLabels (context menu has limited access)
        # Enhanced detection for Kodi v19 compatibility
        imdb_candidates = [
            xbmc.getInfoLabel('ListItem.Property(LibraryGenie.IMDbID)'),
            xbmc.getInfoLabel('ListItem.UniqueID(imdb)'),
            xbmc.getInfoLabel('ListItem.IMDBNumber'),
            xbmc.getInfoLabel('ListItem.Property(imdb_id)'),
            xbmc.getInfoLabel('ListItem.Property(IMDbID)'),
            # Additional v19-specific locations
            xbmc.getInfoLabel('ListItem.Property(uniqueid.imdb)'),
            xbmc.getInfoLabel('ListItem.DBID'),  # For library items, we can try to resolve via JSONRPC
        ]
        
        imdb_id = None
        db_id = None
        
        # First pass: look for direct IMDb IDs
        for candidate in imdb_candidates[:-1]:  # Exclude DBID from this pass
            if candidate and str(candidate).startswith('tt'):
                imdb_id = candidate
                xbmc.log(f"LibraryGenie: Found direct IMDb ID: {imdb_id}", xbmc.LOGDEBUG)
                break
        
        # Second pass: if no direct IMDb ID, try resolving via DBID for library items
        if not imdb_id:
            db_id = xbmc.getInfoLabel('ListItem.DBID')
            if db_id and db_id.isdigit():
                try:
                    # Use JSONRPC to get more details for library items
                    import json
                    json_query = {
                        "jsonrpc": "2.0",
                        "method": "VideoLibrary.GetMovieDetails",
                        "params": {
                            "movieid": int(db_id),
                            "properties": ["imdbnumber", "uniqueid"]
                        },
                        "id": 1
                    }
                    response = xbmc.executeJSONRPC(json.dumps(json_query))
                    result = json.loads(response)
                    
                    if 'result' in result and 'moviedetails' in result['result']:
                        movie_details = result['result']['moviedetails']
                        
                        # Check uniqueid first (more reliable)
                        uniqueid = movie_details.get('uniqueid', {})
                        if isinstance(uniqueid, dict) and uniqueid.get('imdb', '').startswith('tt'):
                            imdb_id = uniqueid['imdb']
                            xbmc.log(f"LibraryGenie: Found IMDb ID via JSONRPC uniqueid: {imdb_id}", xbmc.LOGDEBUG)
                        elif movie_details.get('imdbnumber', '').startswith('tt'):
                            imdb_id = movie_details['imdbnumber']
                            xbmc.log(f"LibraryGenie: Found IMDb ID via JSONRPC imdbnumber: {imdb_id}", xbmc.LOGDEBUG)
                            
                except Exception as e:
                    xbmc.log(f"LibraryGenie: Error resolving IMDb ID via JSONRPC: {str(e)}", xbmc.LOGDEBUG)
        
        xbmc.log(f"LibraryGenie: Final IMDb ID detection result: {imdb_id} (from DBID: {db_id})", xbmc.LOGDEBUG)

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