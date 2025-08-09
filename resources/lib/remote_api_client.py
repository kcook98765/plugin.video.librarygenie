import json
import urllib.request
import urllib.parse
import urllib.error
from resources.lib import utils
from resources.lib.config_manager import Config
import requests # Added import for requests library

class RemoteAPIClient:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.get_setting('remote_api_url') or 'https://your-server.com'
        self.api_key = self.config.get_setting('remote_api_key')

    def _make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request to the API"""
        if not self.base_url or not self.api_key:
            return None

        url = f"{self.base_url.rstrip('/')}{endpoint}"
        request_headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Content-Type': 'application/json'
        }

        if headers:
            request_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=request_headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=request_headers, json=data, timeout=30)
            else:
                return None

            if response.status_code == 200:
                return response.json()
            else:
                utils.log(f"API request failed: {response.status_code} - {response.text}", "ERROR")
                return None

        except Exception as e:
            utils.log(f"API request error: {str(e)}", "ERROR")
            return None

    def exchange_pairing_code(self, pairing_code):
        """Exchange pairing code for API key"""
        data = {'pairing_code': pairing_code}

        # Use base URL without authentication for pairing
        url = f"{self.base_url.rstrip('/')}/pairing-code/exchange"
        headers = {'Content-Type': 'application/json'}

        try:
            json_data = json.dumps(data)
            req = urllib.request.Request(url, 
                                       data=json_data.encode('utf-8'),
                                       headers=headers, method='POST')

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))

                if result.get('success'):
                    # Store the API key and server URL
                    self.api_key = result.get('api_key')
                    self.config.set_setting('remote_api_key', self.api_key)
                    self.config.set_setting('remote_api_url', result.get('server_url', self.base_url))
                    self.base_url = result.get('server_url', self.base_url)

                    utils.log(f"Pairing successful for user: {result.get('user_email')}", "INFO")
                    return True
                else:
                    utils.log(f"Pairing failed: {result.get('error')}", "ERROR")
                    return False

        except Exception as e:
            utils.log(f"Error during pairing: {str(e)}", "ERROR")
            return False

    def test_connection(self):
        """Test API connection and authentication"""
        result = self._make_request('GET', '/kodi/test') # Changed endpoint call to use GET method
        if result and result.get('kodi_ready'):
            utils.log("Remote API connection test successful", "INFO")
            return True
        else:
            utils.log("Remote API connection test failed", "ERROR")
            return False

    def search_movies(self, query, limit=20):
        """Search for movies using the remote API"""
        if not self.api_key:
            utils.log("Remote API not configured", "WARNING")
            return []

        try:
            response = self._make_request('POST', '/kodi/search/movies', {
                'query': query,
                'limit': limit
            })

            if response and response.get('success'):
                return response.get('results', [])
            else:
                utils.log(f"Search request failed: {response}", "ERROR")
                return []

        except Exception as e:
            utils.log(f"Error searching movies: {str(e)}", "ERROR")
            return []

    def get_movie_details(self, imdb_id):
        """Get detailed movie information"""
        result = self._make_request('GET', f'/api/movies/{imdb_id}') # Changed endpoint call to use GET method
        if result and result.get('success'):
            return result.get('movie')
        else:
            utils.log(f"Failed to get movie details for {imdb_id}", "ERROR")
            return None

    def get_similar_movies(self, imdb_id):
        """Get movies similar to the specified movie"""
        result = self._make_request('GET', f'/api/movies/{imdb_id}/similar') # Changed endpoint call to use GET method
        if result and result.get('success'):
            return result.get('similar_movies', [])
        else:
            utils.log(f"Failed to get similar movies for {imdb_id}", "ERROR")
            return []

    def log_activity(self, action, movie_id=None, duration_seconds=None):
        """Log user activity for analytics"""
        data = {
            'action': action,
            'kodi_version': '20.0',  # Could get this dynamically
            'addon_version': '1.0.0'  # Could get from addon.xml
        }

        if movie_id:
            data['movie_id'] = movie_id
        if duration_seconds:
            data['duration_seconds'] = duration_seconds

        result = self._make_request('POST', '/api/activity/log', data) # Changed endpoint call to use POST method
        return result is not None

    def start_batch_upload(self, mode='merge', total_count=0, source='kodi'):
        """Start a batch upload session"""
        if not self.api_key:
            return None

        try:
            response = self._make_request('POST', '/library/batch/start', {
                'mode': mode,
                'total_count': total_count,
                'source': source
            })
            return response
        except Exception as e:
            utils.log(f"Error starting batch upload: {str(e)}", "ERROR")
            return None

    def upload_batch_chunk(self, upload_id, chunk_index, items, idempotency_key):
        """Upload a chunk of items to the batch session"""
        if not self.api_key:
            return None

        try:
            headers = {'Idempotency-Key': idempotency_key}
            response = self._make_request('PUT', f'/library/batch/{upload_id}/chunk', {
                'chunk_index': chunk_index,
                'items': items
            }, headers=headers)
            return response
        except Exception as e:
            utils.log(f"Error uploading batch chunk: {str(e)}", "ERROR")
            return None

    def commit_batch_upload(self, upload_id):
        """Commit the batch upload session"""
        if not self.api_key:
            return None

        try:
            response = self._make_request('POST', f'/library/batch/{upload_id}/commit', {})
            return response
        except Exception as e:
            utils.log(f"Error committing batch upload: {str(e)}", "ERROR")
            return None

    def get_batch_status(self, upload_id):
        """Get the status of a batch upload session"""
        if not self.api_key:
            return None

        try:
            response = self._make_request('GET', f'/library/batch/{upload_id}/status', {})
            return response
        except Exception as e:
            utils.log(f"Error getting batch status: {str(e)}", "ERROR")
            return None