
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib import utils

class ResultsManager:
    def __init__(self):
        self.jsonrpc = JSONRPC()

    def search_movie_by_criteria(self, title, year=None, director=None):
        filter_conditions = {"field": "title", "operator": "contains", "value": title}
        
        if year:
            filter_conditions = {
                "and": [
                    filter_conditions,
                    {"field": "year", "operator": "is", "value": str(year)}
                ]
            }
            
        if director:
            filter_conditions = {
                "and": [
                    filter_conditions,
                    {"field": "director", "operator": "contains", "value": director}
                ]
            }

        params = {
            "filter": filter_conditions,
            "properties": ["title", "year", "director", "file"]
        }
        
        try:
            results = self.jsonrpc.execute("VideoLibrary.GetMovies", params)
            return results.get('result', {}).get('movies', [])
        except Exception as e:
            utils.log(f"Error searching movies: {e}", "ERROR")
            return []
