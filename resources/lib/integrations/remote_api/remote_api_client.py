import json
import urllib.request
import urllib.parse
import urllib.error
import hashlib
import time
import uuid
from resources.lib import utils
from resources.lib.config.config_manager import get_config

class RemoteAPIClient:
    def __init__(self, config=None):
        self.config = config or get_config()
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

        utils.log(f"Attempting to exchange pairing code with server: {url}", "INFO")
        utils.log(f"Pairing code length: {len(pairing_code)}", "DEBUG")
        # Redact sensitive pairing code from logs
        redacted_data = json.loads(json.dumps(data)) # Create a mutable copy
        redacted_data['pairing_code'] = f"{redacted_data['pairing_code'][:2]}***{redacted_data['pairing_code'][-2:]}"
        utils.log(f"Sending pairing request data: {json.dumps(redacted_data)}", "DEBUG")

        try:
            json_data = json.dumps(data)
            

            req = urllib.request.Request(url, 
                                       data=json_data.encode('utf-8'),
                                       headers=headers, method='POST')

            utils.log("Making HTTP request to pairing endpoint...", "DEBUG")
            with urllib.request.urlopen(req, timeout=30) as response:
                utils.log(f"HTTP response code: {response.getcode()}", "DEBUG")
                response_text = response.read().decode('utf-8')
                utils.log(f"Raw response: {response_text}", "DEBUG")

                result = json.loads(response_text)

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

        except urllib.error.HTTPError as e:
            utils.log(f"HTTP error during pairing - Code: {e.code}, Reason: {e.reason}", "ERROR")
            try:
                error_body = e.read().decode('utf-8')
                utils.log(f"Error response body: {error_body}", "ERROR")
            except Exception as read_error:
                utils.log(f"Could not read error response body: {str(read_error)}", "WARNING")
            return False
        except urllib.error.URLError as e:
            utils.log(f"URL/Network error during pairing: {str(e)}", "ERROR")
            utils.log(f"Server URL being accessed: {url}", "ERROR")
            return False
        except json.JSONDecodeError as e:
            utils.log(f"JSON decode error during pairing: {str(e)}", "ERROR")
            return False
        except Exception as e:
            utils.log(f"Unexpected error during pairing: {str(e)}", "ERROR")
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
            batches = result.get('batches', [])
            # Ensure each batch has the expected format
            formatted_batches = []
            for batch in batches:
                if isinstance(batch, dict):
                    # Use the batch as-is if it's already a dict
                    formatted_batches.append(batch)
                else:
                    # Convert object to dict if needed, with safe attribute access
                    formatted_batch = {
                        'batch_id': getattr(batch, 'batch_id', getattr(batch, 'id', 'unknown')),
                        'batch_type': getattr(batch, 'batch_type', getattr(batch, 'mode', 'unknown')),
                        'status': getattr(batch, 'status', 'unknown'),
                        'total_movies': getattr(batch, 'total_movies', getattr(batch, 'total_count', 0)),
                        'successful_imports': getattr(batch, 'successful_imports', getattr(batch, 'processed_count', 0)),
                        'failed_imports': getattr(batch, 'failed_imports', 0),
                        'started_at': getattr(batch, 'started_at', getattr(batch, 'created_at', 'Unknown')),
                        'completed_at': getattr(batch, 'completed_at', getattr(batch, 'updated_at', 'Unknown'))
                    }
                    formatted_batches.append(formatted_batch)
            return formatted_batches
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

    def _chunked_movie_upload(self, movies, mode='merge', chunk_size=500, progress_callback=None):
        """Upload movies in chunks with retry logic and proper error handling"""

        # Step 1: Start batch session
        session = self.start_batch_upload(mode, len(movies), 'kodi')

        if not session or not session.get('success'):
            return {'success': False, 'error': 'Failed to start batch session'}

        upload_id = session['upload_id']

        # Step 2: Upload chunks
        failed_chunks = []
        total_chunks = (len(movies) + chunk_size - 1) // chunk_size  # Calculate total chunks

        for chunk_num, chunk_index in enumerate(range(0, len(movies), chunk_size)):
            chunk_movies = movies[chunk_index:chunk_index + chunk_size]
            idempotency_key = str(uuid.uuid4())

            # Update progress if callback provided
            if progress_callback:
                should_continue = progress_callback(
                    chunk_num + 1, 
                    total_chunks, 
                    len(chunk_movies),
                    f"Uploading movies {chunk_index + 1}-{min(chunk_index + chunk_size, len(movies))}"
                )
                if not should_continue:
                    utils.log("Upload cancelled by user", "INFO")
                    return {'success': False, 'error': 'Upload cancelled by user'}

            # Convert movies to the expected format
            items = []
            for movie in chunk_movies:
                if 'imdb_id' in movie:
                    # New format - direct IMDb ID
                    items.append({'imdb_id': movie['imdb_id']})
                elif 'imdbnumber' in movie and movie['imdbnumber']:
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

    def delta_sync_movies(self, local_movies, progress_callback=None):
        """Upload movies using delta sync mode (merge with existing)"""
        # Get current server fingerprints
        server_hash = self.get_library_hash()
        if not server_hash or not server_hash.get('success'):
            return self._chunked_movie_upload(local_movies, mode='replace')

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
        return self._chunked_movie_upload(movies_to_upload, mode='merge', progress_callback=progress_callback)

    def full_sync_movies(self, movies, progress_callback=None):
        """Upload movies using full sync mode (authoritative replacement)"""
        return self._chunked_movie_upload(movies, mode='replace', progress_callback=progress_callback)

    def find_similar_movies(self, reference_imdb_id, include_plot=False, include_mood=False, include_themes=False, include_genre=False, limit=50):
        """Find movies similar to a reference movie using the /similar_to endpoint"""
        try:
            # Validate at least one facet is selected
            if not any([include_plot, include_mood, include_themes, include_genre]):
                utils.log("No facets selected for similarity search", "ERROR")
                return []

            # Make request to public /similar_to endpoint (no auth required)
            url = f"{self.base_url.rstrip('/')}/similar_to"
            headers = {'Content-Type': 'application/json'}
            
            data = {
                'reference_imdb_id': reference_imdb_id,
                'include_plot': include_plot,
                'include_mood': include_mood,
                'include_themes': include_themes,
                'include_genre': include_genre
            }

            utils.log(f"Making similarity request for {reference_imdb_id} with facets: plot={include_plot}, mood={include_mood}, themes={include_themes}, genre={include_genre}", "DEBUG")

            # Create request without authentication (public endpoint)
            json_data = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(url, data=json_data, headers=headers)
            request.get_method = lambda: 'POST'

            # Make request with timeout
            response = urllib.request.urlopen(request, timeout=15)

            if response.getcode() == 200:
                response_data = response.read().decode('utf-8')
                result = json.loads(response_data)
                
                if result.get('success'):
                    similar_movies = result.get('results', [])
                    utils.log(f"Found {len(similar_movies)} similar movies", "INFO")
                    return similar_movies
                else:
                    utils.log(f"Similarity search failed: {result.get('error', 'Unknown error')}", "ERROR")
                    return []
            else:
                utils.log(f"Similarity API request failed: {response.getcode()}", "ERROR")
                return []

        except Exception as e:
            utils.log(f"Error in similarity search: {str(e)}", "ERROR")
            return []