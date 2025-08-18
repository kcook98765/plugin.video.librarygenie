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


def handle_script_action(action):
    """Handle script actions that are called directly (not via plugin routing)"""
    utils.log(f"Handling script action: {action}", "INFO")

    if action == 'setup_remote_api':
        from resources.lib.integrations.remote_api.remote_api_setup import run_setup
        run_setup()
        return True
    elif action == 'import_from_shortlist':
        from resources.lib.integrations.remote_api.shortlist_importer import import_from_shortlist
        import_from_shortlist()
        return True
    elif action == 'manual_setup_remote_api':
        from resources.lib.integrations.remote_api.remote_api_setup import manual_setup_remote_api
        manual_setup_remote_api()
        return True
    elif action == 'test_remote_api':
        from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
        client = RemoteAPIClient()
        if client.test_connection():
            utils.show_notification("Remote API", "Connection test successful!")
        else:
            utils.show_notification("Remote API", "Connection test failed!", icon=xbmcgui.NOTIFICATION_ERROR)
        return True
    elif action == 'upload_library_full':
        from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
        upload_manager = IMDbUploadManager()
        upload_manager.upload_library_full_sync()
        return True
    elif action == 'upload_library_delta':
        from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
        upload_manager = IMDbUploadManager()
        upload_manager.upload_library_delta_sync()
        return True
    elif action == 'upload_status':
        from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
        upload_manager = IMDbUploadManager()
        upload_manager.get_upload_status()
        return True
    elif action == 'clear_server_library':
        from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
        upload_manager = IMDbUploadManager()
        upload_manager.clear_server_library()
        return True
    elif action == 'clear_all_local_data':
        clear_all_local_data()
        return True
    elif action == 'show_main_window':
        utils.log("Main window functionality deprecated - using plugin routing", "INFO")
        xbmcgui.Dialog().notification("LibraryGenie", "Main window has been replaced with plugin interface", xbmcgui.NOTIFICATION_INFO, 3000)
        return True

    return False


def run_addon():
    """Legacy function maintained for compatibility - now delegates to proper plugin routing"""
    global _initialized
    if _initialized:
        utils.log("Addon already initialized, skipping", "DEBUG")
        return

    utils.log("=== Starting run_addon() ===", "DEBUG")
    _initialized = True

    try:
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

        # Show notification that addon is initialized
        xbmcgui.Dialog().notification("LibraryGenie", "Addon initialized", xbmcgui.NOTIFICATION_INFO, 2000)

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)