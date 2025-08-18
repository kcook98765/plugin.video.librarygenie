import sys
import urllib.parse
import xbmcgui
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.kodi.kodi_helper import KodiHelper
from resources.lib.utils import utils

_initialized = False

def clear_all_local_data():
    """Clears all lists and folders except 'Search History' folder (but clears its lists)."""
    utils.log("Attempting to clear all local data", "INFO")
    dialog = xbmcgui.Dialog()
    if dialog.yesno("Clear All Data", "Are you sure you want to delete ALL your lists and folders? This action cannot be undone. The 'Search History' folder will remain but all its lists will be cleared."):
        try:
            from resources.lib.config.config_manager import get_config
            config = get_config()
            db_manager = DatabaseManager(config.db_path)

            # Get Search History folder ID
            search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

            # First, delete all lists in Search History folder
            if search_history_folder_id:
                search_history_lists = db_manager.fetch_lists(search_history_folder_id)
                for list_item in search_history_lists:
                    try:
                        db_manager.delete_list(list_item['id'])
                        utils.log(f"Deleted Search History list ID: {list_item['id']} ('{list_item['name']}')", "DEBUG")
                    except Exception as e:
                        utils.log(f"Error deleting Search History list {list_item['id']}: {str(e)}", "WARNING")

            # Get all root-level folders and lists
            all_root_folders = db_manager.fetch_folders(None)  # Root level folders
            all_root_lists = db_manager.fetch_lists(None)      # Root level lists

            # Delete all root-level folders except 'Search History' (this will cascade to delete all subfolders and their lists)
            for folder in all_root_folders:
                if folder['name'] != "Search History":
                    try:
                        db_manager.delete_folder_and_contents(folder['id'])
                        utils.log(f"Deleted folder and all contents: {folder['name']} (ID: {folder['id']})", "DEBUG")
                    except Exception as e:
                        utils.log(f"Error deleting folder {folder['name']}: {str(e)}", "WARNING")

            # Delete all root-level lists (not in any folder)
            for list_item in all_root_lists:
                try:
                    db_manager.delete_list(list_item['id'])
                    utils.log(f"Deleted root-level list: {list_item['name']} (ID: {list_item['id']})", "DEBUG")
                except Exception as e:
                    utils.log(f"Error deleting root-level list {list_item['name']}: {str(e)}", "WARNING")
            
            dialog.notification("LibraryGenie", "All local data cleared successfully.", xbmcgui.NOTIFICATION_INFO, 3000)
            utils.log("Successfully cleared all local data.", "INFO")

        except Exception as e:
            utils.log(f"Error clearing local data: {str(e)}", "ERROR")
            dialog.notification("LibraryGenie", "Error clearing local data.", xbmcgui.NOTIFICATION_ERROR, 5000)
    else:
        utils.log("User cancelled clearing local data.", "INFO")


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

        # Handle direct script actions from settings
        script_actions = [
            'setup_remote_api', 'manual_setup_remote_api', 'test_remote_api',
            'upload_library_full', 'upload_library_delta', 'upload_status', 
            'clear_server_library', 'show_main_window', 'clear_all_local_data',
            'import_from_shortlist'
        ]

        if len(sys.argv) > 1 and sys.argv[1] in script_actions:
            action = sys.argv[1]
            utils.log(f"Detected script action: {action}", "INFO")

            # Handle special case for setup_remote_api
            if action == 'setup_remote_api':
                from resources.lib.integrations.remote_api.remote_api_setup import run_setup
                run_setup()
                return  # Early return to prevent normal startup
            elif action == 'import_from_shortlist':
                from resources.lib.integrations.remote_api.shortlist_importer import import_from_shortlist
                import_from_shortlist()
                return  # Early return to prevent normal startup
        else:
            args = sys.argv[2][1:] if len(sys.argv) > 2 else ""
            params = urllib.parse.parse_qs(args)
            action = params.get('action', [None])[0]
            utils.log(f"Parsed URL params - args: '{args}', action: '{action}'", "DEBUG")

        # Check if launched from context menu only (exclude show_main_window which has its own handler)
        listitem_context = (len(sys.argv) > 1 and sys.argv[1] == '-1') and action != 'show_main_window'
        utils.log(f"Launch context analysis - Args: {sys.argv}, Action: {action}, Is Context: {listitem_context}", "DEBUG")

        # Initialize config and database
        utils.log("Initializing Config and DatabaseManager", "DEBUG")
        from resources.lib.config.config_manager import get_config
        config = get_config()
        db_manager = DatabaseManager(config.db_path)

        # Ensure database is setup
        utils.log("Setting up database schema", "DEBUG")
        db_manager.setup_database()

        utils.log("Initializing Kodi helper", "DEBUG")
        kodi_helper = KodiHelper()

        # MainWindow functionality has been moved to plugin-based approach
        utils.log("Using plugin-based routing instead of MainWindow", "DEBUG")

        # Handle context menu vs direct launch
        if listitem_context:
            utils.log("Processing context menu click", "DEBUG")
            # Context menu functionality has been moved to plugin-based approach
            utils.log("Context menu handling deprecated - using plugin routing", "INFO")
            xbmcgui.Dialog().notification("LibraryGenie", "Use addon menu instead of context menu", xbmcgui.NOTIFICATION_INFO, 3000)
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
                utils.log("Main window functionality deprecated - using plugin routing", "INFO")
                xbmcgui.Dialog().notification("LibraryGenie", "Main window has been replaced with plugin interface", xbmcgui.NOTIFICATION_INFO, 3000)
            elif action == 'setup_remote_api':
                utils.log("Setting up remote API", "DEBUG")
                utils.setup_remote_api()
            elif action == 'manual_setup_remote_api':
                utils.log("Manual remote API setup", "DEBUG")
                from resources.lib.integrations.remote_api.remote_api_setup import manual_setup_remote_api
                manual_setup_remote_api()
            elif action == 'test_remote_api':
                utils.log("Testing remote API connection", "DEBUG")
                from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
                client = RemoteAPIClient()
                if client.test_connection():
                    utils.show_notification("Remote API", "Connection test successful!")
                else:
                    utils.show_notification("Remote API", "Connection test failed!", icon=xbmcgui.NOTIFICATION_ERROR)
            elif action == 'upload_library_full':
                utils.log("Starting full library upload", "DEBUG")
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.upload_library_full_sync()
            elif action == 'upload_library_delta':
                utils.log("Starting delta library sync", "DEBUG")
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.upload_library_delta_sync()
            elif action == 'upload_status':
                utils.log("Checking upload status", "DEBUG")
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.get_upload_status()
            elif action == 'clear_server_library':
                utils.log("Clearing server library", "DEBUG")
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                upload_manager.clear_server_library()
            elif action == 'clear_all_local_data':
                clear_all_local_data()
            else:
                # Always show root directory for direct launch or unknown action
                # Use the new function-based directory builder
                from resources.lib.core.directory_builder import build_root_directory
                import sys
                
                # Get the plugin handle for directory building
                handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
                if handle != -1:
                    build_root_directory(handle)
                return

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)