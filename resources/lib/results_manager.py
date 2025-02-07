from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib import utils

from resources.lib.singleton_base import Singleton

class ResultsManager(Singleton):
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.jsonrpc = JSONRPC()
            self._initialized = True

    def search_movie_by_criteria(self, title, year=None, director=None):
        try:
            from resources.lib.query_manager import QueryManager
            query_manager = QueryManager(Config().db_path)
            return query_manager.get_matched_movies(title, year, director)
        except Exception as e:
            utils.log(f"Error searching movies: {e}", "ERROR")
            return []