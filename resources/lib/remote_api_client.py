
import json
import urllib.request
import urllib.parse
import urllib.error
from resources.lib import utils
from resources.lib.config_manager import Config
import hashlib
import time
import random

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
            # Create request object
            if data:
                json_data = json.dumps(data).encode('utf-8')
                request = urllib.request.Request(url, data=json_data)
            else:
                request = urllib.request.Request(url)
            
            # Add headers
            for key, value in request_headers.items():
                request.add_header(key, value)
            
            # Set method for non-GET requests
            if method in ['PUT', 'POST', 'DELETE']:
                request.get_method = lambda: method
            
            # Make request
            response = urllib.request.urlopen(request, timeout=30)
            
            if response.getcode() == 200:
                response_data = response.read().decode('utf-8')
                return json.loads(response_data)
            else:
                utils.log(f"API request failed: {response.getcode()}", "ERROR")
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
        result = self._make_request('GET', '/kodi/test')
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

    def get_library_hash(self):
        """Get collection fingerprints for delta sync"""
        result = self._make_request('GET', '/library/hash')
        if result and result.get('success'):
            return result
        else:
            utils.log("Failed to get library hash", "ERROR")
            return None

    def get_movie_list(self, page=1, per_page=100):
        """Get user's current movie list with pagination"""
        result = self._make_request('GET', f'/kodi/movies/list?page={page}&per_page={per_page}')
        if result and result.get('success'):
            return result
        else:
            utils.log("Failed to get movie list", "ERROR")
            return None

    def clear_movie_list(self):
        """Clear user's entire movie list"""
        result = self._make_request('DELETE', '/kodi/movies/clear')
        if result and result.get('success'):
            return result
        else:
            utils.log("Failed to clear movie list", "ERROR")
            return None

    def get_batch_history(self):
        """Get user's movie upload batch history"""
        result = self._make_request('GET', '/kodi/movies/batches')
        if result and result.get('success'):
            return result.get('batches', [])
        else:
            utils.log("Failed to get batch history", "ERROR")
            return []

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
            response = self._make_request('GET', f'/library/batch/{upload_id}/status')
            return response
        except Exception as e:
            utils.log(f"Error getting batch status: {str(e)}", "ERROR")
            return None

    def chunked_movie_upload(self, movie_list, mode='merge', chunk_size=500):
        """Upload user's movie collection using chunked batch upload"""
        
        # Step 1: Start batch session
        session = self.start_batch_upload(mode, len(movie_list), 'kodi')
        
        if not session or not session.get('success'):
            return {'success': False, 'error': 'Failed to start batch session'}
        
        upload_id = session['upload_id']
        max_chunk = session['max_chunk']
        effective_chunk_size = min(chunk_size, max_chunk)
        
        # Step 2: Split into chunks and upload
        chunks = [movie_list[i:i + effective_chunk_size] 
                  for i in range(0, len(movie_list), effective_chunk_size)]
        
        failed_chunks = []
        
        for chunk_index, chunk in enumerate(chunks):
            # Generate unique idempotency key
            idempotency_key = f"{int(time.time())}-{random.randint(10000, 99999)}-{chunk_index}"
            
            # Format items for API - only IMDb IDs accepted
            items = []
            for movie in chunk:
                if isinstance(movie, str):
                    # Just IMDb ID
                    items.append({'imdb_id': movie})
                elif isinstance(movie, dict) and 'imdb_id' in movie:
                    # Movie object - extract only the IMDb ID  
                    items.append({'imdb_id': movie['imdb_id']})
                elif isinstance(movie, dict) and 'imdbnumber' in movie:
                    # Legacy format - extract from imdbnumber
                    items.append({'imdb_id': movie['imdbnumber']})
                else:
                    # Skip invalid items - only valid IMDb IDs accepted
                    continue
            
            # Upload chunk with retry logic
            success = False
            for attempt in range(3):  # 3 retry attempts
                try:
                    result = self.upload_batch_chunk(upload_id, chunk_index, items, idempotency_key)
                    
                    if result and result.get('success'):
                        success = True
                        break
                        
                except Exception as e:
                    utils.log(f"Chunk upload attempt {attempt + 1} failed: {str(e)}", "WARNING")
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            if not success:
                failed_chunks.append(chunk_index)
        
        # Step 3: Commit the batch
        if not failed_chunks:
            commit_result = self.commit_batch_upload(upload_id)
            
            if commit_result and commit_result.get('success'):
                return {
                    'success': True,
                    'upload_id': upload_id,
                    'final_tallies': commit_result['final_tallies'],
                    'user_movie_count': commit_result['user_movie_count']
                }
        
        return {
            'success': False,
            'upload_id': upload_id,
            'failed_chunks': failed_chunks,
            'error': 'Some chunks failed to upload'
        }

    def delta_sync_movies(self, local_movies):
        """Efficient delta sync using library fingerprints"""
        # Get current server fingerprints
        server_hash = self.get_library_hash()
        if not server_hash or not server_hash.get('success'):
            return self.chunked_movie_upload(local_movies, mode='replace')
        
        server_fingerprints = set(server_hash['fingerprints'])
        
        # Create local fingerprints using simple hash
        local_fingerprints = set()
        movies_to_upload = []
        
        for movie in local_movies:
            imdb_id = movie['imdb_id'] if isinstance(movie, dict) and 'imdb_id' in movie else movie.get('imdbnumber', movie) if isinstance(movie, dict) else movie
            
            # Create simple hash using available libraries
            hash_obj = hashlib.sha1(imdb_id.encode('utf-8'))
            fingerprint = hash_obj.hexdigest()[:8]
            local_fingerprints.add(fingerprint)
            
            # If not on server, add to upload list
            if fingerprint not in server_fingerprints:
                movies_to_upload.append(movie)
        
        if not movies_to_upload:
            return {'success': True, 'message': 'Collection already up to date'}
        
        # Upload only new movies
        return self.chunked_movie_upload(movies_to_upload, mode='merge')

    def full_sync_movies(self, local_movies):
        """Full collection sync (authoritative replacement)"""
        return self.chunked_movie_upload(local_movies, mode='replace')
