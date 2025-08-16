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
        # Enhanced IMDb ID detection for v19 compatibility
        imdb_id = None
        
        # Try multiple sources for IMDb ID
        imdb_candidates = [
            xbmc.getInfoLabel('ListItem.IMDBNumber'),
            xbmc.getInfoLabel('ListItem.UniqueID(imdb)'),
            item_info.get('imdbnumber', ''),
            item_info.get('uniqueid', {}).get('imdb', '') if isinstance(item_info.get('uniqueid'), dict) else ''
        ]
        
        # Also check if we have a valid DBID and can get the IMDb ID via JSON-RPC
        db_id = xbmc.getInfoLabel('ListItem.DBID')
        if db_id and not any(candidate and str(candidate).startswith('tt') for candidate in imdb_candidates):
            try:
                from resources.lib.jsonrpc_manager import JSONRPC
                jsonrpc = JSONRPC()
                response = jsonrpc.execute('VideoLibrary.GetMovieDetails', {
                    'movieid': int(db_id),
                    'properties': ['uniqueid']
                })
                movie_details = response.get('result', {}).get('moviedetails', {})
                uniqueid = movie_details.get('uniqueid', {})
                if isinstance(uniqueid, dict) and 'imdb' in uniqueid:
                    imdb_candidates.append(uniqueid['imdb'])
                xbmc.log(f"LibraryGenie: Context menu JSON-RPC lookup found IMDb: {uniqueid.get('imdb', 'None')}", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"LibraryGenie: Context menu JSON-RPC lookup failed: {str(e)}", xbmc.LOGWARNING)
        
        for candidate in imdb_candidates:
            if candidate and str(candidate).startswith('tt'):
                imdb_id = candidate
                xbmc.log(f"LibraryGenie: Context menu found IMDb ID: {imdb_id}", xbmc.LOGINFO)
                break
        
        options = []
        
        if imdb_id and str(imdb_id).startswith('tt'):
            options.append("Find Similar Movies...")
        
        options.extend([
            "Search Movies...",
            "Search History", 
            "Settings"
        ])

        # Show dialog to select option
        selected = xbmcgui.Dialog().contextmenu(options)
        
        # Adjust indices based on whether similarity option is present
        similarity_offset = 1 if imdb_id and imdb_id.startswith('tt') else 0
        
        if selected == 0 and similarity_offset:  # Find Similar Movies
            # Import and call similarity handler directly
            from resources.lib.route_handlers import find_similar_movies_from_context
            find_similar_movies_from_context({})
            
        elif selected == (0 + similarity_offset):  # Search Movies - use direct search instead of plugin URL
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
                
        elif selected == (1 + similarity_offset):  # Search History
            url = f"plugin://{addon_id}/?action=browse_folder&folder_name=Search History"
            xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
        elif selected == (2 + similarity_offset):  # Settings
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