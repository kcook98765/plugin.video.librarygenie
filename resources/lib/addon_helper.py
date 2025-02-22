import sys
import urllib.parse
import xbmcgui
from .config_manager import Config
from .database_manager import DatabaseManager
from .kodi_helper import KodiHelper
from .window_main import MainWindow
from . import utils

_initialized = False

def run_addon():
    global _initialized
    if _initialized:
        return

    utils.log("Running addon...", "DEBUG")
    _initialized = True
    try:
        # Initialize args and action
        args = ""
        action = None
        
        # Handle direct action from context menu
        if len(sys.argv) > 1 and sys.argv[1] == 'show_main_window':
            action = 'show_main_window'
        else:
            args = sys.argv[2][1:] if len(sys.argv) > 2 else ""
            params = urllib.parse.parse_qs(args)
            action = params.get('action', [None])[0]

        # Check if launched from context menu or directly
        listitem_context = (len(sys.argv) > 1 and sys.argv[1] == '-1') or action == 'show_main_window'
        utils.log(f"Context menu check - Args: {sys.argv}, Action: {action}, Is Context: {listitem_context}", "DEBUG")

        # Initialize helpers
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Ensure database is setup
        db_manager.setup_database()

        kodi_helper = KodiHelper()

        # Handle context menu vs direct launch
        if listitem_context:
            utils.log("Processing context menu click", "DEBUG")
            # Context menu on media item - show options window
            kodi_helper = KodiHelper()
            item_info = kodi_helper.get_focused_item_details()
            if item_info:
                window = MainWindow(item_info)
                utils.log("MainWindow instance created", "DEBUG")
                window.doModal()
                utils.log("MainWindow closed", "DEBUG")
                del window
                return
            else:
                utils.log("No item info found for context menu", "WARNING")
                xbmcgui.Dialog().notification("LibraryGenie", "Could not get item details", xbmcgui.NOTIFICATION_WARNING, 3000)
                return
        elif action == 'show_list':
            # Handle specific list display
            params = urllib.parse.parse_qs(args)
            list_id = params.get('list_id', [None])[0]
            if list_id:
                kodi_helper.show_list(int(list_id))
            return
        else:
            # Always show root directory for direct launch or unknown action
            root_folders = db_manager.fetch_folders(None)  # Get root folders
            root_lists = db_manager.fetch_lists(None)  # Get root lists 
            kodi_helper.list_folders_and_lists(root_folders, root_lists)
            return

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)