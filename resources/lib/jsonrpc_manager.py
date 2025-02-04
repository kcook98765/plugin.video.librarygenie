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
        xbmc.log(f"ListGenius: Executing JSONRPC method: {method}", xbmc.LOGINFO)
        xbmc.log(f"ListGenius: Query: {query_json}", xbmc.LOGDEBUG)

        response = xbmc.executeJSONRPC(query_json)
        response_json = json.loads(response)

        # Log the response received
        xbmc.log(f"ListGenius: Response: {response}", xbmc.LOGDEBUG)

        return response_json

    def fetch_movies_from_rpc(self, rpc):
        try:
            result = self.execute("VideoLibrary.GetMovies", rpc)

            # Log the result of the fetch operation
            xbmc.log(f"ListGenius: Fetch result: {json.dumps(result, indent=2)}", xbmc.LOGDEBUG)

            if 'result' in result and 'movies' in result['result']:
                return result['result']['movies']
            else:
                xbmc.log("ListGenius: No movies found in response", xbmc.LOGDEBUG)
                return []
        except Exception as e:
            xbmc.log(f"ListGenius: Error fetching movies: {str(e)}", xbmc.LOGERROR)
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
        xbmc.log(f"ListGenius: Sending request to {request.full_url}", level=xbmc.LOGINFO)
        xbmc.log(f"ListGenius: Headers: {request.headers}", level=xbmc.LOGINFO)
        xbmc.log(f"ListGenius: Body: {request.data.decode('utf-8')}", level=xbmc.LOGINFO)

    def log_response(self, response):
        xbmc.log(f"ListGenius: Response: {response}", level=xbmc.LOGINFO)
