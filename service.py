
import time
import json
import xbmc
import xbmcaddon
from resources.lib.config.config_manager import Config
from resources.lib.data.query_manager import QueryManager
from resources.lib.utils import utils

ADDON = xbmcaddon.Addon()
MON = xbmc.Monitor()
ID = ADDON.getAddonInfo('id')

def _get_bool(k, d=False):
    return ADDON.getSettingBool(k) if ADDON.getSetting(k) != '' else d

def _get_int(k, d=0):
    return int(ADDON.getSettingInt(k)) if ADDON.getSetting(k) != '' else d

def _set_bool(k, v):
    ADDON.setSettingBool(k, v)

def _set_int(k, v):
    ADDON.setSettingInt(k, int(v))

def init_once():
    """Idempotent: create/upgrade schema + seed baseline data."""
    try:
        # Ensure database is properly set up
        if not ensure_database_ready():
            utils.log(f"{ID} database setup failed during init", "ERROR")
            return

        # Check if library scanning is needed
        check_and_prompt_library_scan()

        # Mark initialization as complete
        if not _get_bool('init_done', False):
            _set_bool('init_done', True)

        utils.log(f"{ID} service init complete", "INFO")
    except Exception as e:
        utils.log(f"{ID} init error: {e}", "ERROR")

def handle_periodic_tasks():
    """Do lightweight, repeatable work here."""
    try:
        # Example periodic tasks:
        # - Clean up old search results
        # - Refresh cached data
        # - Sync with remote services if configured
        
        # For now, just log that the service is running
        utils.log(f"{ID} periodic task executed", "DEBUG")
        
        # You can add more periodic tasks here later
        
    except Exception as e:
        utils.log(f"{ID} periodic task error: {e}", "ERROR")

def ensure_database_ready():
    """Ensure database and all required tables/folders are properly set up"""
    try:
        config = Config()
        query_manager = QueryManager(config.db_path)

        # Setup all database tables
        query_manager.setup_database()
        
        # Ensure required system folders exist
        search_history_folder = query_manager.ensure_search_history_folder()
        utils.log(f"Search History folder ensured: {search_history_folder}", "DEBUG")
        
        # Create Imported Lists folder if it doesn't exist
        imported_lists_folder_id = query_manager.get_folder_id_by_name("Imported Lists")
        if not imported_lists_folder_id:
            imported_lists_folder = query_manager.create_folder("Imported Lists", None)
            utils.log(f"Created Imported Lists folder: {imported_lists_folder}", "DEBUG")
        else:
            utils.log("Imported Lists folder already exists", "DEBUG")

        utils.log("Database setup completed successfully", "INFO")
        return True
        
    except Exception as e:
        utils.log(f"Error ensuring database ready: {e}", "ERROR")
        return False

def check_and_prompt_library_scan():
    """Check if library data exists and prompt user for initial scan if needed"""
    try:
        # Skip if already scanned or user previously declined
        if _get_bool('library_scanned', False) or _get_bool('library_scan_declined', False):
            return

        config = Config()
        query_manager = QueryManager(config.db_path)
        
        # Check if we have any library data
        result = query_manager.execute_query(
            "SELECT COUNT(*) as count FROM imdb_exports",
            fetch_one=True
        )
        
        library_count = result['count'] if result else 0
        
        if library_count == 0:
            # No library data exists - prompt user
            utils.log("No library data found - prompting user for initial scan", "INFO")
            prompt_user_for_library_scan()
        else:
            # Library data exists - mark as scanned
            _set_bool('library_scanned', True)
            utils.log(f"Library data exists ({library_count} items) - skipping scan prompt", "INFO")
            
    except Exception as e:
        utils.log(f"Error checking library scan status: {e}", "ERROR")

def prompt_user_for_library_scan():
    """Show modal to user asking permission to scan library"""
    try:
        import xbmcgui
        import threading
        
        def show_dialog():
            try:
                dialog = xbmcgui.Dialog()
                
                # Show informational dialog explaining the need
                response = dialog.yesno(
                    "LibraryGenie - Initial Setup",
                    "LibraryGenie needs to scan your Kodi movie library to enable its features.\n\n"
                    "This one-time scan will:\n"
                    "• Index your movies with IMDb information\n"
                    "• Enable search and list management\n"
                    "• Take a few minutes depending on library size\n\n"
                    "Would you like to start the scan now?",
                    nolabel="Not Now",
                    yeslabel="Start Scan"
                )
                
                if response:
                    # User agreed - start the scan
                    utils.log("User approved library scan - starting background scan", "INFO")
                    _set_bool('library_scan_declined', False)
                    start_library_scan()
                else:
                    # User declined - remember their choice
                    utils.log("User declined library scan", "INFO")
                    _set_bool('library_scan_declined', True)
                    
            except Exception as e:
                utils.log(f"Error in dialog thread: {e}", "ERROR")
        
        # Run dialog in separate thread to avoid blocking service
        dialog_thread = threading.Thread(target=show_dialog)
        dialog_thread.daemon = True
        dialog_thread.start()
        
    except Exception as e:
        utils.log(f"Error prompting user for library scan: {e}", "ERROR")

def start_library_scan():
    """Start the library scanning process in background"""
    try:
        import threading
        
        def scan_worker():
            try:
                utils.log("Starting background library scan", "INFO")
                
                # Import the upload manager and use its scanning method
                from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager
                config = Config()
                query_manager = QueryManager(config.db_path)
                
                upload_manager = IMDbUploadManager(query_manager)
                
                # Run only the collection and storage part (not upload)
                success = upload_manager.get_full_kodi_movie_collection_and_store_locally(use_notifications=True)
                
                if success:
                    _set_bool('library_scanned', True)
                    utils.log("Background library scan completed successfully", "INFO")
                    
                    # Show completion notification
                    import xbmcgui
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        "Library scan complete! Addon is ready to use.", 
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )
                else:
                    utils.log("Background library scan failed", "ERROR")
                    
            except Exception as e:
                utils.log(f"Error in library scan worker: {e}", "ERROR")
        
        # Start scan in background thread
        scan_thread = threading.Thread(target=scan_worker)
        scan_thread.daemon = True
        scan_thread.start()
        
    except Exception as e:
        utils.log(f"Error starting library scan: {e}", "ERROR")

def handle_command(topic, message):
    """
    Receive NotifyAll commands from your plugin/UI:
      xbmc.executebuiltin('NotifyAll(plugin.video.librarygenie,{"cmd":"refresh_lists"})')
    """
    try:
        if topic != ID:
            return
        data = json.loads(message or "{}")
        cmd = data.get("cmd")
        
        if cmd == "refresh_lists":
            utils.log(f"{ID} refresh_lists command received", "INFO")
            handle_periodic_tasks()
        elif cmd == "reinit":
            utils.log(f"{ID} reinit command received", "INFO")
            _set_bool('init_done', False)
            init_once()
        elif cmd == "cleanup":
            utils.log(f"{ID} cleanup command received", "INFO")
            # Add cleanup tasks here
        elif cmd == "rescan_library":
            utils.log(f"{ID} rescan_library command received", "INFO")
            _set_bool('library_scanned', False)
            _set_bool('library_scan_declined', False)
            check_and_prompt_library_scan()
        
    except Exception as e:
        utils.log(f"{ID} command error: {e}", "ERROR")

class ServiceMonitor(xbmc.Monitor):
    def onSettingsChanged(self):
        # Settings changed from UI—no restart needed
        utils.log(f"{ID} settings changed", "INFO")

    def onNotification(self, sender, method, data):
        # React to system/app notifications (JSON-RPC broadcasts)
        # e.g., method == "VideoLibrary.OnScanFinished"
        if method == "GUI.OnNotification":
            try:
                payload = json.loads(data)
                if payload.get("message") and payload.get("sender") == ID:
                    handle_command(payload.get("sender", ""), payload.get("message"))
            except Exception:
                pass

def main():
    utils.log(f"{ID} service starting", "INFO")
    
    init_once()
    mon = ServiceMonitor()

    # Periodic loop
    # Use waitForAbort(timeout) so Kodi can shut down the service instantly
    while not mon.abortRequested():
        if not _get_bool('service_enabled', True):
            # Sleep lightly while disabled
            if mon.waitForAbort(5):
                break
            continue

        # Run one tick
        try:
            handle_periodic_tasks()
        except Exception as e:
            utils.log(f"{ID} periodic error: {e}", "ERROR")

        # Wait respecting dynamic interval
        interval = max(10, _get_int('poll_interval_sec', 300))
        if mon.waitForAbort(interval):
            break

    utils.log(f"{ID} service stopping", "INFO")

if __name__ == "__main__":
    main()
