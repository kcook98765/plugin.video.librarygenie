""" /main.py """
import os
import sys
import urllib.parse # Import urllib.parse

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

from resources.lib.addon_helper import run_addon
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib import utils

# Global variable to track initialization
_initialized = False

def run_search():
    """Launch the search window directly"""
    utils.log("Direct search action triggered", "DEBUG")
    try:
        from resources.lib.window_search import SearchWindow
        search_window = SearchWindow("LibraryGenie - Movie Search")
        search_window.doModal()
        del search_window
    except Exception as e:
        utils.log(f"Error launching search window: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")

def build_root():
    """Build the root directory with search option"""
    import xbmcplugin
    import xbmcgui
    from resources.lib.addon_ref import get_addon
    
    addon = get_addon()
    addon_id = addon.getAddonInfo("id")
    handle = int(sys.argv[1])
    
    # Add a top-level "Search..." item
    li = xbmcgui.ListItem(label="Search Movies...")
    li.setInfo('video', {'title': 'Search Movies...', 'plot': 'Search for movies using natural language queries'})
    url = f"plugin://{addon_id}/?action=search"
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
    
    # Add Browse Lists item
    li = xbmcgui.ListItem(label="Browse Lists")
    li.setInfo('video', {'title': 'Browse Lists', 'plot': 'Browse your movie lists and folders'})
    url = f"plugin://{addon_id}/?action=browse"
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(handle)

def router(paramstr):
    """Route plugin calls to appropriate handlers"""
    from urllib.parse import parse_qs, urlparse
    
    utils.log(f"Router called with params: {paramstr}", "DEBUG")
    
    q = parse_qs(urlparse(paramstr).query) if paramstr else {}
    action = q.get("action", [""])[0]
    
    utils.log(f"Action determined: {action}", "DEBUG")
    
    if action == "search":
        utils.log("Routing to search action", "DEBUG")
        run_search()
        return
    elif action == "browse":
        utils.log("Routing to browse action", "DEBUG")
        from resources.lib.window_main import MainWindow
        
        # Create empty item info for browse launch
        item_info = {
            'title': 'LibraryGenie Browser',
            'is_playable': False,
            'kodi_id': 0
        }
        
        main_window = MainWindow(item_info, "LibraryGenie - Browse Lists")
        main_window.doModal()
        del main_window
        return
    
    # Default: build root directory
    utils.log("Building root directory", "DEBUG")
    build_root()

def main():
    """Main addon entry point"""
    utils.log("=== LibraryGenie addon starting ===", "INFO")
    utils.log(f"Command line args: {sys.argv}", "DEBUG")

    try:
        utils.log("Initializing addon components", "DEBUG")

        # Check if this is a program addon launch (direct launch without context)
        if len(sys.argv) == 1 or (len(sys.argv) >= 2 and 'action=program' in str(sys.argv)):
            utils.log("Program addon launch detected - showing main window", "DEBUG")
            from resources.lib.window_main import MainWindow
            
            # Create empty item info for program launch
            item_info = {
                'title': 'LibraryGenie Browser',
                'is_playable': False,
                'kodi_id': 0
            }
            
            main_window = MainWindow(item_info, "LibraryGenie - Browse Lists")
            main_window.doModal()
            del main_window
            return

        # Handle plugin routing
        if len(sys.argv) >= 3:
            utils.log("Plugin routing detected", "DEBUG")
            router(sys.argv[2])
            return

        # Fallback: Run the addon helper
        utils.log("Calling run_addon()", "DEBUG")
        run_addon()

        # Ensure Search History folder exists
        utils.log("Setting up configuration and database", "DEBUG")
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        utils.log("Search History folder initialization complete", "DEBUG")

        utils.log("=== LibraryGenie addon startup complete ===", "INFO")
    except Exception as e:
        utils.log(f"CRITICAL ERROR in main(): {str(e)}", "ERROR")
        import traceback
        utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

if __name__ == '__main__':
    main()