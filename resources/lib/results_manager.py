
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib import utils

from resources.lib.singleton_base import Singleton

class ResultsManager(Singleton):
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.jsonrpc = JSONRPC()
            self._initialized = True

    def search_movie_by_criteria(self, title, year=None, director=None):
        # Case-insensitive title search with partial matching
        title_conditions = [
            {"field": "title", "operator": "contains", "value": title.lower()},
            {"field": "title", "operator": "contains", "value": title.upper()},
            {"field": "title", "operator": "contains", "value": title.title()}
        ]
        
        filter_conditions = {"or": title_conditions}
        
        and_conditions = []
        if year:
            and_conditions.append({"field": "year", "operator": "is", "value": str(year)})
            
        if director:
            director_parts = director.split()
            director_conditions = []
            for part in director_parts:
                director_conditions.append(
                    {"field": "director", "operator": "contains", "value": part}
                )
            and_conditions.append({"or": director_conditions})
            
        if and_conditions:
            filter_conditions = {
                "and": [filter_conditions] + and_conditions
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
