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
import json
import requests
import xbmc
from resources.lib import utils
from resources.lib.config_manager import Config

class ApiClient:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.get_setting('api_base_url')
        self.api_key = self.config.get_setting('api_key')
        
    def _make_request(self, method, endpoint, data=None, files=None, headers=None):
        """Make HTTP request to API with proper error handling"""
        if headers is None:
            headers = {}
        
        # Add API key to headers if available
        if self.api_key:
            headers['X-API-Key'] = self.api_key
            
        if data and not files:
            headers['Content-Type'] = 'application/json'
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=json.dumps(data) if data and not files else None,
                files=files
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            utils.log(f"API request failed: {str(e)}", "ERROR")
            return {'status': 'error', 'message': str(e)}
            
    def register_user(self, registration_code):
        """Register a new user with the provided registration code"""
        endpoint = '/api/v1/api_info/create-user'
        data = {'code': registration_code}
        return self._make_request('POST', endpoint, data=data)
        
    def upload_imdb_numbers(self, imdb_numbers=None, csv_file=None):
        """Upload IMDb numbers either as JSON list or CSV file"""
        endpoint = '/api/v1/movies/upload'
        
        if csv_file:
            files = {'file': ('imdb_numbers.csv', csv_file, 'text/csv')}
            return self._make_request('POST', endpoint, files=files)
        elif imdb_numbers:
            data = {'imdb_numbers': imdb_numbers}
            return self._make_request('POST', endpoint, data=data)
        else:
            return {'status': 'error', 'message': 'Either IMDb numbers or CSV file required'}
            
    def search_movies(self, query):
        """Search for movies using natural language query"""
        endpoint = '/api/v1/user_search/search'
        data = {'query': query}
        return self._make_request('POST', endpoint, data=data)
        
    def list_exports(self):
        """Get list of available data exports"""
        endpoint = '/api/v1/user_data/exports'
        return self._make_request('GET', endpoint)
        
    def download_export(self, export_path):
        """Download a specific export file"""
        endpoint = f'/api/v1/user_data/exports/{export_path}'
        return self._make_request('GET', endpoint)
        
    def get_api_versions(self):
        """Get API version information"""
        endpoint = '/api/v1/versions'
        return self._make_request('GET', endpoint)
