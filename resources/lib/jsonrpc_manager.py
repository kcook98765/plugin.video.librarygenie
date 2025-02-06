""" /resources/lib/jsonrpc_manager.py """
import json
import xbmc
from resources.lib import utils

# Initialize logging
utils.log("JSONRPC Manager module initialized", "INFO")

class JSONRPC:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JSONRPC, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            utils.log("JSONRPC Manager module initialized", "INFO")
            self._initialized = True

    def execute(self, method, params):
        query = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        query_json = json.dumps(query)
        utils.log(f"Executing JSONRPC method: {method} with params: {query_json}", "DEBUG")

        response = xbmc.executeJSONRPC(query_json)
        response_json = json.loads(response)
        utils.log(f"JSONRPC response: {response}", "DEBUG")

        return response_json

    def fetch_movies_from_rpc(self, rpc):
        try:
            result = self.execute("VideoLibrary.GetMovies", rpc)
            utils.log(f"Fetch result: {json.dumps(result, indent=2)}", "DEBUG")

            if 'error' in result:
                error_msg = result['error'].get('message', 'Unknown error')
                utils.log(f"JSONRPC error: {error_msg}", "ERROR")
                return []

            if 'result' in result and 'movies' in result['result']:
                return result['result']['movies']

            utils.log("No movies found in RPC response", "WARNING")
            return []

        except json.JSONDecodeError as e:
            utils.log(f"Invalid JSON in RPC response: {str(e)}", "ERROR")
            return []
        except KeyError as e:
            utils.log(f"Missing key in RPC response: {str(e)}", "ERROR")
            return []
        except Exception as e:
            utils.log(f"Unexpected error in RPC call: {str(e)}", "ERROR")
            return []

    def get_movie_details(self, movie_id):
        utils.log(f"Fetching details for movie ID: {movie_id}", "DEBUG")
        method = 'VideoLibrary.GetMovieDetails'
        params = {
            'movieid': movie_id,
            'properties': [
                'title', 'genre', 'year', 'director', 'cast', 'plot', 'rating',
                'file', 'thumbnail', 'fanart', 'runtime', 'tagline', 'art',
                'writer', 'imdbnumber', 'premiered', 'mpaa', 'trailer', 'votes',
                'country', 'dateadded', 'studio', 'art'
            ]
        }

        response = self.execute(method, params)
        details = response.get('result', {}).get('moviedetails', {})

        # Get poster from art dictionary with detailed logging
        art = details.get('art', {})
        utils.log(f"POSTER TRACE - JSONRPC raw response art dict: {art}", "DEBUG")
        utils.log(f"POSTER TRACE - JSONRPC raw response details: {details}", "DEBUG")
        
        poster = art.get('poster', '')
        utils.log(f"POSTER TRACE - JSONRPC initial poster from art: {poster}", "DEBUG")
        
        if not poster:
            poster = details.get('thumbnail', '')
            utils.log(f"POSTER TRACE - JSONRPC fallback to thumbnail: {poster}", "DEBUG")
            
        utils.log(f"POSTER TRACE - JSONRPC available art types: {list(art.keys())}", "DEBUG")
        utils.log(f"POSTER TRACE - JSONRPC final selected poster: {poster}", "DEBUG")
        utils.log(f"POSTER TRACE - JSONRPC thumbnail path: {details.get('thumbnail')}", "DEBUG")
        details['poster'] = poster
        details['art'] = {
            'poster': poster,
            'thumb': poster,
            'icon': poster
        }

        # Ensure we have art dictionary with all image types
        details['art'] = {
            'poster': details['thumbnail'],
            'thumb': details['thumbnail'],
            'icon': details.get('art', {}).get('icon', details['thumbnail']),
            'fanart': details.get('art', {}).get('fanart', '')
        }

        # Parse cast details
        cast_list = details.get('cast', [])
        cast = [{'name': actor.get('name'), 'role': actor.get('role'), 'order': actor.get('order'), 'thumbnail': actor.get('thumbnail')} for actor in cast_list]
        details['cast'] = cast

        # Convert list fields to comma-separated strings
        if 'genre' in details:
            details['genre'] = ' / '.join(details['genre'])
        if 'director' in details:
            details['director'] = ' / '.join(details['director'])
        if 'writer' in details:
            details['writer'] = ' / '.join(details['writer'])
        if 'country' in details:
            details['country'] = ' / '.join(details['country'])
        if 'studio' in details:
            details['studio'] = ' / '.join(details['studio'])

        details['file'] = details.get('file', '')
        details['kodi_id'] = int(movie_id)  # Ensure movie ID is included
        details['play'] = details['file']  # Set the play field to a valid value

        # Add resume data
        if 'resume' in details:
            details['resumetime'] = details['resume'].get('position', 0)
            details['totaltime'] = details['resume'].get('total', 0)

        return details

    def log_request(self, request):
        utils.log(f"Sending request to {request.full_url}", "INFO")
        utils.log(f"Headers: {request.headers}", "INFO")
        utils.log(f"Body: {request.data.decode('utf-8')}", "INFO")

    def log_response(self, response):
        utils.log(f"Response: {response}", "INFO")

    def get_movies_for_export(self, start=0, limit=50):
        """Get a batch of movies for IMDB export"""
        query = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {
                "properties": [
                    "imdbnumber", "title", "year", "file"
                ],
                "limits": {
                    "start": start,
                    "end": start + limit
                }
            },
            "id": 1
        }
        response = self.execute(query)
        if 'result' in response and 'movies' in response['result']:
            return response['result']['movies'], response['result'].get('limits', {}).get('total', 0)
        return [], 0