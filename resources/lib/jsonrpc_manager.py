""" /resources/lib/jsonrpc_manager.py """
import json
import xbmc

class JSONRPC:

    def execute(self, method, params):
        query = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        query_json = json.dumps(query)

        # Log the query being sent
        utils.log(f"Executing JSONRPC method: {method}", "INFO")
        utils.log(f"Query: {query_json}", "DEBUG")

        response = xbmc.executeJSONRPC(query_json)
        response_json = json.loads(response)

        # Log the response received
        utils.log(f"Response: {response}", "DEBUG")

        return response_json

    def fetch_movies_from_rpc(self, rpc):
        try:
            result = self.execute("VideoLibrary.GetMovies", rpc)

            # Log the result of the fetch operation
            xbmc.log(f"ListGenius: Fetch result: {json.dumps(result, indent=2)}", xbmc.LOGDEBUG)

            if 'result' in result and 'movies' in result['result']:
                return result['result']['movies']
            else:
                utils.log("No movies found in response", "DEBUG")
                return []
        except Exception as e:
            utils.log(f"Error fetching movies: {str(e)}", "ERROR")
            raise

    def get_movie_details(self, movie_id):
        method = 'VideoLibrary.GetMovieDetails'
        params = {
            'movieid': movie_id,
            'properties': [
                'title', 'genre', 'year', 'director', 'cast', 'plot', 'rating',
                'file', 'thumbnail', 'fanart', 'runtime', 'tagline',
                'writer', 'imdbnumber', 'premiered', 'mpaa', 'trailer', "votes",
                "country", "dateadded", "studio"
            ]
        }

        response = self.execute(method, params)
        details = response.get('result', {}).get('moviedetails', {})

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

        return details

    def log_request(self, request):
        utils.log(f"Sending request to {request.full_url}", "INFO")
        utils.log(f"Headers: {request.headers}", "INFO")
        utils.log(f"Body: {request.data.decode('utf-8')}", "INFO")

    def log_response(self, response):
        utils.log(f"Response: {response}", "INFO")
