import json
import xbmc
from resources.lib import utils

class JSONRPC:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JSONRPC, cls).__new__(cls)
            utils.log("JSONRPC Manager module initialized", "INFO")
        return cls._instance

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
        return json.loads(response)

    def get_movies(self, start=0, limit=50, properties=None):
        if properties is None:
            properties = ["title", "year", "file", "imdbnumber", "uniqueid"]

        return self.execute("VideoLibrary.GetMovies", {
            "properties": properties,
            "limits": {"start": start, "end": start + limit}
        })

    def get_movie_details(self, movie_id, properties=None):
        if properties is None:
            properties = [
                'title', 'genre', 'year', 'director', 'cast', 'plot', 'rating',
                'file', 'thumbnail', 'fanart', 'runtime', 'tagline', 'art',
                'writer', 'imdbnumber', 'premiered', 'mpaa', 'trailer', 'votes',
                'country', 'dateadded', 'studio'
            ]

        return self.execute("VideoLibrary.GetMovieDetails", {
            'movieid': movie_id,
            'properties': properties
        })

    def get_movies_for_export(self, start=0, limit=50):
        response = self.get_movies(start, limit)
        if 'result' in response and 'movies' in response['result']:
            return response['result']['movies'], response['result'].get('limits', {}).get('total', 0)
        return [], 0