import sys
import urllib.parse
import xbmcgui
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
            from resources.lib.data.query_manager import QueryManager
            config = get_config()
            query_manager = QueryManager(config.db_path)

            # Get Search History folder ID
            search_history_folder_id = query_manager.get_folder_id_by_name("Search History")

            # First, delete all lists in Search History folder
            if search_history_folder_id:
                search_history_lists = query_manager.fetch_lists(search_history_folder_id)
                for list_item in search_history_lists:
                    try:
                        # Use standardized QueryManager method to delete list and its items atomically
                        if query_manager.delete_list_and_contents(list_item['id']):
                            utils.log(f"Deleted Search History list ID: {list_item['id']} ('{list_item['name']}')", "DEBUG")
                        else:
                            utils.log(f"Failed to delete Search History list {list_item['id']}", "WARNING")
                    except Exception as e:
                        utils.log(f"Error deleting Search History list {list_item['id']}: {str(e)}", "WARNING")

            # Get all root-level folders and lists
            all_root_folders = query_manager.fetch_folders(None)  # Root level folders
            all_root_lists = query_manager.fetch_lists(None)      # Root level lists

            # Delete all root-level folders except 'Search History' (this will cascade to delete all subfolders and their lists)
            for folder in all_root_folders:
                if folder['name'] != "Search History":
                    try:
                        query_manager.delete_folder_and_contents(folder['id'])
                        utils.log(f"Deleted folder and all contents: {folder['name']} (ID: {folder['id']})", "DEBUG")
                    except Exception as e:
                        utils.log(f"Error deleting folder {folder['name']}: {str(e)}", "WARNING")

            # Delete all root-level lists (not in any folder)
            for list_item in all_root_lists:
                try:
                    # Use standardized QueryManager method to delete list and its items atomically
                    if query_manager.delete_list_and_contents(list_item['id']):
                        utils.log(f"Deleted root-level list: {list_item['name']} (ID: {list_item['id']})", "DEBUG")
                    else:
                        utils.log(f"Failed to delete root-level list {list_item['name']}", "WARNING")
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
        # Extract relevant information for routing decision
        url_part = sys.argv[0] if len(sys.argv) > 0 else ""
        handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
        paramstr = sys.argv[2] if len(sys.argv) > 2 else ""
        action = None

        # Check for script actions in sys.argv (RunScript calls from settings.xml)
        script_action = None
        if len(sys.argv) >= 2:
            potential_action = sys.argv[1]
            # Clean up potential action string (remove any quotes or extra characters)
            potential_action = potential_action.strip('\'"')
            
            # Complete list of script actions from settings.xml
            script_actions = [
                'setup_remote_api', 'manual_setup_remote_api', 'test_remote_api',
                'upload_library_full', 'upload_library_delta', 'upload_status',
                'clear_server_library', 'show_main_window', 'clear_all_local_data',
                'import_from_shortlist', 'addon_library_status'
            ]
            
            if potential_action in script_actions:
                script_action = potential_action
                utils.log(f"Detected script action: {script_action}", "INFO")
            else:
                utils.log(f"Unrecognized potential action: '{potential_action}' (not a script action)", "DEBUG")

        # Handle script actions directly without routing through main router
        if script_action == "upload_library_full":
            utils.log("Handling upload_library_full script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                utils.log("Starting full library upload...", "INFO")
                result = upload_manager.upload_library_full_sync()
                utils.log(f"Full library upload completed with result: {result}", "INFO")
            except Exception as e:
                utils.log(f"Error in upload_library_full script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Upload error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "upload_library_delta":
            utils.log("Handling upload_library_delta script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                utils.log("Starting delta library upload...", "INFO")
                result = upload_manager.upload_library_delta_sync()
                utils.log(f"Delta library upload completed with result: {result}", "INFO")
            except Exception as e:
                utils.log(f"Error in upload_library_delta script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Upload error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "clear_server_library":
            utils.log("Handling clear_server_library script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                utils.log("Starting server library clear...", "INFO")
                result = upload_manager.clear_server_library()
                utils.log(f"Server library clear completed with result: {result}", "INFO")
            except Exception as e:
                utils.log(f"Error in clear_server_library script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Clear error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "upload_status":
            utils.log("Handling upload_status script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                upload_manager = IMDbUploadManager()
                utils.log("Getting upload status...", "INFO")
                upload_manager.get_upload_status()
                utils.log("Upload status displayed successfully", "INFO")
            except Exception as e:
                utils.log(f"Error in upload_status script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Upload status error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "view_upload_status":
            utils.log("Handling view_upload_status script action", "INFO")
            try:
                settings_manager = SettingsManager()
                utils.log("Calling view_upload_status method...", "INFO")
                settings_manager.view_upload_status()
                utils.log("View upload status displayed successfully", "INFO")
            except Exception as e:
                utils.log(f"Error in view_upload_status script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"View upload status error traceback: {traceback.format_exc()}", "ERROR")
            return
                import traceback
                utils.log(f"Upload status error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "setup_remote_api":
            utils.log("Handling setup_remote_api script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.remote_api_setup import run_setup
                utils.log("Starting remote API setup...", "INFO")
                run_setup()
                utils.log("Remote API setup completed", "INFO")
            except Exception as e:
                utils.log(f"Error in setup_remote_api script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Setup error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "manual_setup_remote_api":
            utils.log("Handling manual_setup_remote_api script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.remote_api_setup import run_manual_setup
                utils.log("Starting manual remote API setup...", "INFO")
                run_manual_setup()
                utils.log("Manual remote API setup completed", "INFO")
            except Exception as e:
                utils.log(f"Error in manual_setup_remote_api script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Manual setup error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "test_remote_api":
            utils.log("Handling test_remote_api script action", "INFO")
            try:
                from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
                remote_client = RemoteAPIClient()
                utils.log("Testing remote API connection...", "INFO")
                result = remote_client.test_connection()
                utils.log(f"Remote API test completed with result: {result}", "INFO")
                if result:
                    import xbmcgui
                    xbmcgui.Dialog().ok("Test Successful", "Remote API connection is working correctly!")
                else:
                    import xbmcgui
                    xbmcgui.Dialog().ok("Test Failed", "Remote API connection failed. Check your settings.")
            except Exception as e:
                utils.log(f"Error in test_remote_api script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Test error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "import_from_shortlist":
            utils.log("Handling import_from_shortlist script action", "INFO")
            try:
                from resources.lib.config.settings_manager import SettingsManager
                settings_manager = SettingsManager()
                utils.log("Starting shortlist import...", "INFO")
                result = settings_manager.import_from_shortlist()
                utils.log(f"Shortlist import completed with result: {result}", "INFO")
            except Exception as e:
                utils.log(f"Error in import_from_shortlist script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Import error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "addon_library_status":
            utils.log("Handling addon_library_status script action", "INFO")
            try:
                from resources.lib.config.settings_manager import SettingsManager
                settings_manager = SettingsManager()
                utils.log("Showing addon library status...", "INFO")
                result = settings_manager.addon_library_status()
                utils.log("Addon library status displayed successfully", "INFO")
            except Exception as e:
                utils.log(f"Error in addon_library_status script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Status error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "clear_all_local_data":
            utils.log("Handling clear_all_local_data script action", "INFO")
            try:
                utils.log("Starting clear all local data...", "INFO")
                clear_all_local_data()
                utils.log("Clear all local data completed", "INFO")
            except Exception as e:
                utils.log(f"Error in clear_all_local_data script action: {str(e)}", "ERROR")
                import traceback
                utils.log(f"Clear data error traceback: {traceback.format_exc()}", "ERROR")
            return
        elif script_action == "show_main_window":
            utils.log("Handling show_main_window script action", "INFO")
            # For show_main_window, we want to proceed to normal plugin routing
            # so we don't return here - let it fall through to the router
            utils.log("Proceeding to normal plugin routing for main window", "INFO")
        else:
            # Parse params for other actions
            params = urllib.parse.parse_qs(paramstr)
            action = params.get('action', [None])[0]
            utils.log(f"Parsed URL params - paramstr: '{paramstr}', action: '{action}'", "DEBUG")

        # Check if launched from context menu only (exclude show_main_window which has its own handler)
        is_context_launch = (len(sys.argv) > 1 and sys.argv[1] == '-1') and action != 'show_main_window'
        utils.log(f"Launch context analysis - Args: {sys.argv}, Action: {action}, Is Context: {is_context_launch}", "DEBUG")

        # Initialize config and database
        utils.log("Initializing Config and QueryManager", "DEBUG")
        from resources.lib.config.config_manager import get_config
        from resources.lib.data.query_manager import QueryManager
        config = get_config()
        query_manager = QueryManager(config.db_path)

        # Ensure database is setup
        utils.log("Setting up database schema", "DEBUG")
        query_manager.setup_database()

        utils.log("Initializing Kodi helper", "DEBUG")
        kodi_helper = KodiHelper()

        # Use plugin-based routing instead of MainWindow
        utils.log(f"Using plugin-based routing instead of MainWindow with paramstr: {paramstr}", "DEBUG")
        from main import router
        router(handle, paramstr)
        return

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)