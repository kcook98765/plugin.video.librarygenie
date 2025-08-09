import sys
import urllib.parse
import xbmcgui
from .config_manager import Config
from .database_manager import DatabaseManager
from .kodi_helper import KodiHelper
from . import utils

_initialized = False

def run_addon():
    global _initialized
    if _initialized:
        utils.log("Addon already initialized, skipping", "DEBUG")
        return

    utils.log("=== Starting run_addon() ===", "DEBUG")
    _initialized = True
    try:
        # Initialize args and action
        args = ""
        action = None
        utils.log(f"Processing command line arguments: {sys.argv}", "DEBUG")

        # Handle special case for setup_remote_api script execution
        if len(sys.argv) > 1 and sys.argv[1] == 'setup_remote_api':
            utils.log("Detected setup_remote_api script execution", "INFO")
            from .remote_api_setup import run_setup
            run_setup()
            return

        # Handle direct action from context menu
        if len(sys.argv) > 1 and sys.argv[1] == 'show_main_window':
            action = 'show_main_window'
            utils.log("Direct main window action detected", "DEBUG")
        else:
            args = sys.argv[2][1:] if len(sys.argv) > 2 else ""
            params = urllib.parse.parse_qs(args)
            action = params.get('action', [None])[0]
            utils.log(f"Parsed URL params - args: '{args}', action: '{action}'", "DEBUG")

        # Check if launched from context menu or directly
        listitem_context = (len(sys.argv) > 1 and sys.argv[1] == '-1') or action == 'show_main_window'
        utils.log(f"Launch context analysis - Args: {sys.argv}, Action: {action}, Is Context: {listitem_context}", "DEBUG")

        # Initialize config and database
        utils.log("Initializing Config and DatabaseManager", "DEBUG")
        from resources.lib.config_manager import get_config
        config = get_config()
        db_manager = DatabaseManager(config.db_path)

        # Ensure database is setup
        utils.log("Setting up database schema", "DEBUG")
        db_manager.setup_database()

        utils.log("Initializing Kodi helper", "DEBUG")
        kodi_helper = KodiHelper()

        # Import MainWindow locally to avoid circular imports
        utils.log("Importing MainWindow class", "DEBUG")
        from .window_main import MainWindow

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
            # Handle different actions
            if action == 'show_main_window':
                utils.log("Showing main window", "DEBUG")
                from resources.lib.window_main import MainWindow
                main_window = MainWindow()
                main_window.doModal()
                del main_window
            elif action == 'setup_remote_api':
                utils.log("Setting up remote API", "DEBUG")
                utils.setup_remote_api()
            elif action == 'manual_setup_remote_api':
                utils.log("Manual remote API setup", "DEBUG")
                from resources.lib.remote_api_setup import manual_setup_remote_api
                manual_setup_remote_api()
            elif action == 'test_remote_api':
                utils.log("Testing remote API connection", "DEBUG")
                from resources.lib.remote_api_client import RemoteAPIClient
                client = RemoteAPIClient()
                if client.test_connection():
                    utils.show_notification("Remote API", "Connection test successful!")
                else:
                    utils.show_notification("Remote API", "Connection test failed!", icon=xbmcgui.NOTIFICATION_ERROR)
            elif action == 'upload_library_full':
                utils.log("Starting full library upload", "DEBUG")
                from resources.lib.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.upload_library_full_sync()
            elif action == 'upload_library_delta':
                utils.log("Starting delta library sync", "DEBUG")
                from resources.lib.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.upload_library_delta_sync()
            elif action == 'upload_status':
                utils.log("Checking upload status", "DEBUG")
                from resources.lib.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.get_upload_status()
            elif action == 'clear_server_library':
                utils.log("Clearing server library", "DEBUG")
                from resources.lib.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.clear_server_library()
            else:
                # Always show root directory for direct launch or unknown action
                root_folders = db_manager.fetch_folders(None)  # Get root folders
                root_lists = db_manager.fetch_lists(None)  # Get root lists
                kodi_helper.list_folders_and_lists(root_folders, root_lists)
                return

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)