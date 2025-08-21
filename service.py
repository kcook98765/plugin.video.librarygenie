
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
