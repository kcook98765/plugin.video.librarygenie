
import json
import urllib.request
import urllib.parse
import urllib.error
from resources.lib import utils
from resources.lib.config_manager import Config

class RemoteAPIClient:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.get_setting('remote_api_url') or 'https://your-server.com'
        self.api_key = self.config.get_setting('remote_api_key')
        
    def _make_request(self, endpoint, method='GET', data=None):
        """Make authenticated API request"""
        if not self.api_key:
            utils.log("No API key configured for remote API", "ERROR")
            return None
            
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                req = urllib.request.Request(url, headers=headers)
            else:
                json_data = json.dumps(data) if data else None
                req = urllib.request.Request(url, 
                                           data=json_data.encode('utf-8') if json_data else None,
                                           headers=headers, method=method)
            
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    utils.log(f"API request failed with status {response.status}", "ERROR")
                    return None
                    
        except urllib.error.HTTPError as e:
            if e.code == 401:
                utils.log("API key invalid or expired", "ERROR")
                return {'error': 'authentication_failed'}
            else:
                utils.log(f"HTTP Error {e.code}: {e.reason}", "ERROR")
                return None
        except Exception as e:
            utils.log(f"Error making API request: {str(e)}", "ERROR")
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
        result = self._make_request('kodi/test')
        if result and result.get('kodi_ready'):
            utils.log("Remote API connection test successful", "INFO")
            return True
        else:
            utils.log("Remote API connection test failed", "ERROR")
            return False
    
    def search_movies(self, query, limit=20, offset=0, filters=None):
        """Search for movies using the remote API"""
        data = {
            'query': query,
            'limit': limit,
            'offset': offset
        }
        
        if filters:
            data['filters'] = filters
            
        result = self._make_request('api/search/movies', 'POST', data)
        if result and result.get('success'):
            return result.get('results', [])
        else:
            utils.log(f"Movie search failed: {result.get('error') if result else 'Unknown error'}", "ERROR")
            return []
    
    def get_movie_details(self, imdb_id):
        """Get detailed movie information"""
        result = self._make_request(f'api/movies/{imdb_id}')
        if result and result.get('success'):
            return result.get('movie')
        else:
            utils.log(f"Failed to get movie details for {imdb_id}", "ERROR")
            return None
    
    def get_similar_movies(self, imdb_id):
        """Get movies similar to the specified movie"""
        result = self._make_request(f'api/movies/{imdb_id}/similar')
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
            
        result = self._make_request('api/activity/log', 'POST', data)
        return result is not None
