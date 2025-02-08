
import xbmc
import xbmcgui
import xbmcaddon
import requests
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib import utils

class ApiClient:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.base_url = self.addon.getSetting('imdb_upload_url')
        self.api_key = self.addon.getSetting('imdb_upload_key')
        self.db_manager = DatabaseManager(Config().db_path)

    def upload_imdb_list(self):
        """Upload IMDB numbers to configured API endpoint"""
        if not self.base_url or not self.api_key:
            xbmcgui.Dialog().ok("Error", "Please configure IMDB Upload API URL and Key in settings")
            return False

        imdb_numbers = self.db_manager.get_valid_imdb_numbers()
        if not imdb_numbers:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "No valid IMDB numbers found to upload",
                xbmcgui.NOTIFICATION_INFO,
                5000
            )
            return False

        progress = xbmcgui.DialogProgress()
        progress.create("Uploading IMDB List")

        try:
            response = requests.post(
                self.base_url,
                json={'imdb_numbers': imdb_numbers},
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=30
            )
            response.raise_for_status()

            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Successfully uploaded {len(imdb_numbers)} IMDB numbers",
                xbmcgui.NOTIFICATION_INFO,
                5000
            )
            return True

        except Exception as e:
            utils.log(f"Error uploading IMDB list: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Failed to upload IMDB list: {str(e)}")
            return False
        finally:
            progress.close()

    def export_imdb_list(self, list_id):
        """Export list items to IMDB format"""
        from resources.lib.database_sync_manager import DatabaseSyncManager
        from resources.lib.query_manager import QueryManager

        query_manager = QueryManager(Config().db_path)
        sync_manager = DatabaseSyncManager(query_manager)

        sync_manager.setup_tables()
        return sync_manager.sync_library_movies()
