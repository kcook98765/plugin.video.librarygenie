import time
import json
import xbmc
import xbmcaddon
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.config.settings_manager import SettingsManager
from resources.lib.data.query_manager import QueryManager
from resources.lib.integrations.remote_api.favorites_sync_manager import FavoritesSyncManager

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

        # Check if library scanning is needed (this handles initial scan prompting)
        check_and_prompt_library_scan()

        # Only run favorites sync if we have library data (skip during initial scan)
        try:
            config = Config()
            query_manager = QueryManager(config.db_path)
            
            # Check if we have actual library data before running favorites sync
            imdb_result = query_manager.execute_query("SELECT COUNT(*) as count FROM imdb_exports", fetch_one=True)
            imdb_count = imdb_result['count'] if imdb_result else 0
            
            if imdb_count > 0:
                sync_manager = FavoritesSyncManager()
                sync_manager.sync_favorites()
                utils.log("Favorites sync completed during service startup", "DEBUG")
            else:
                utils.log("Skipping favorites sync during startup - no library data available yet", "DEBUG")
        except Exception as e:
            utils.log(f"Error syncing favorites during startup: {e}", "ERROR")

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

        # Check if this is a fresh database (no library data) - skip folder/list creation during initial scan
        imdb_result = query_manager.execute_query("SELECT COUNT(*) as count FROM imdb_exports", fetch_one=True)
        imdb_count = imdb_result['count'] if imdb_result else 0
        
        media_result = query_manager.execute_query("SELECT COUNT(*) as count FROM media_items", fetch_one=True) 
        media_count = media_result['count'] if media_result else 0

        if imdb_count == 0 and media_count == 0:
            utils.log("Fresh database detected - skipping folder/list creation until after initial library scan", "INFO")
            return True

        # Only create folders and lists if we have existing data (not during initial setup)
        utils.log("Existing data found - ensuring required folders and lists exist", "DEBUG")

        # Ensure required system folders exist
        search_history_folder_id = query_manager.get_folder_id_by_name("Search History")
        if not search_history_folder_id:
            search_history_result = query_manager.create_folder("Search History", None)
            if isinstance(search_history_result, dict):
                search_history_folder_id = search_history_result['id']
            else:
                search_history_folder_id = search_history_result
            utils.log(f"Search History folder ensured: {search_history_folder_id}", "DEBUG")

        imported_lists_folder_id = query_manager.get_folder_id_by_name("Imported Lists")
        if not imported_lists_folder_id:
            imported_lists_result = query_manager.create_folder("Imported Lists", None)
            if isinstance(imported_lists_result, dict):
                imported_lists_folder_id = imported_lists_result['id']
            else:
                imported_lists_folder_id = imported_lists_result
            utils.log(f"Created Imported Lists folder: {imported_lists_folder_id}", "DEBUG")

        # Ensure reserved lists exist - but only if QueryManager has the methods
        try:
            if hasattr(query_manager, 'ensure_kodi_favorites_list'):
                kodi_favorites_list = query_manager.ensure_kodi_favorites_list()
                if kodi_favorites_list:
                    list_id = kodi_favorites_list['id'] if isinstance(kodi_favorites_list, dict) else kodi_favorites_list
                    utils.log(f"Ensured Kodi Favorites list exists with ID: {list_id}", "DEBUG")
            else:
                utils.log("QueryManager missing ensure_kodi_favorites_list method - skipping", "DEBUG")
        except Exception as e:
            utils.log(f"Error ensuring Kodi Favorites list: {e}", "ERROR")

        try:
            if hasattr(query_manager, 'ensure_shortlist_imports_list'):
                shortlist_imports_list = query_manager.ensure_shortlist_imports_list()
                if shortlist_imports_list:
                    list_id = shortlist_imports_list['id'] if isinstance(shortlist_imports_list, dict) else shortlist_imports_list
                    utils.log(f"Ensured Shortlist Imports list exists with ID: {list_id}", "DEBUG")
            else:
                utils.log("QueryManager missing ensure_shortlist_imports_list method - skipping", "DEBUG")
        except Exception as e:
            utils.log(f"Error ensuring Shortlist Imports list: {e}", "ERROR")

        utils.log("Database setup completed successfully", "INFO")
        return True

    except Exception as e:
        utils.log(f"Error ensuring database ready: {e}", "ERROR")
        return False

def check_and_prompt_library_scan():
    """Check if library data exists and prompt user for initial scan if needed"""
    try:
        config = Config()
        query_manager = QueryManager(config.db_path)

        # Always check actual database content - don't rely solely on settings
        # Check if we have any library data in both tables
        imdb_result = query_manager.execute_query(
            "SELECT COUNT(*) as count FROM imdb_exports",
            fetch_one=True
        )

        media_result = query_manager.execute_query(
            "SELECT COUNT(*) as count FROM media_items WHERE source = 'lib'",
            fetch_one=True
        )

        imdb_count = imdb_result['count'] if imdb_result else 0
        media_count = media_result['count'] if media_result else 0

        utils.log(f"Library data check: found {imdb_count} items in imdb_exports, {media_count} items in media_items", "INFO")
        
        # Check current settings state
        scan_declined = _get_bool('library_scan_declined', False)
        library_scanned = _get_bool('library_scanned', False)
        utils.log(f"Current settings - library_scanned: {library_scanned}, library_scan_declined: {scan_declined}", "INFO")

        # If no actual data exists, reset settings and prompt for scan
        if imdb_count == 0 and media_count == 0:
            # Reset scan settings since database is empty
            _set_bool('library_scanned', False)
            _set_bool('library_scan_declined', False)

            utils.log("No library data found - prompting user for scan", "INFO")
            
            # Force prompt on completely empty database (fresh wipe scenario)
            prompt_user_for_library_scan()
        else:
            # Library data exists - mark as scanned and clear decline flag
            _set_bool('library_scanned', True)
            _set_bool('library_scan_declined', False)
            utils.log(f"Library data exists (imdb_exports: {imdb_count}, media_items: {media_count}) - marking as scanned", "INFO")

    except Exception as e:
        utils.log(f"Error checking library scan status: {e}", "ERROR")

def prompt_user_for_library_scan(force_prompt=False):
    """Show modal to user asking permission to scan library"""
    try:
        import xbmcgui
        import threading

        def show_dialog():
            try:
                # Give Kodi a moment to fully start up
                import time
                time.sleep(2)
                
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
                    # Pass True to show the modal on completion
                    start_library_scan(show_status_on_completion=True)
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

def start_library_scan(show_status_on_completion=False):
    """Start the library scan process"""
    try:
        from resources.lib.integrations.remote_api.imdb_upload_manager import IMDbUploadManager

        utils.log("Starting background library scan", "INFO")
        upload_manager = IMDbUploadManager()

        # Use the efficient incremental approach with notifications
        success = upload_manager.get_full_kodi_movie_collection_and_store_locally(
            use_notifications=True,
            show_modal_on_completion=show_status_on_completion  # Show modal only when requested
        )

        if success:
            utils.log("Background library scan completed successfully", "INFO")
        else:
            utils.log("Background library scan failed", "ERROR")

    except Exception as e:
        utils.log(f"Error in background library scan: {str(e)}", "ERROR")

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

class LibraryGenieService:
    def __init__(self):
        self.config = Config()
        self.settings = SettingsManager()
        self.monitor = xbmc.Monitor()

        utils.log("LibraryGenie service started", "INFO")

    def run(self):
        utils.log("LibraryGenie service started", "INFO")

        while not self.monitor.abortRequested():
            try:
                # Service loop for other background tasks if needed
                pass

            except Exception as e:
                utils.log(f"Error in service loop: {str(e)}", "ERROR")

            # Wait for next cycle or abort - use a shorter interval for responsiveness
            # but check sync timing internally
            if self.monitor.waitForAbort(5):
                break

        utils.log("LibraryGenie service stopped", "INFO")

def main():
    utils.log(f"{ID} service starting", "INFO")

    init_once()
    mon = ServiceMonitor()
    service = LibraryGenieService()

    # Start the service in a separate thread
    import threading
    service_thread = threading.Thread(target=service.run)
    service_thread.daemon = True
    service_thread.start()

    # Periodic loop for monitoring and other tasks
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