from typing import List, Dict, Any
import xbmc
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.query_manager import QueryManager
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config

class DatabaseSyncManager:
    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager
        self.db_manager = DatabaseManager(Config().db_path)
        self.jsonrpc = JSONRPC()

    def setup_tables(self):
        """Create necessary tables for movie reference and addon metadata"""
        self.db_manager.setup_database()

    def sync_library_movies(self) -> bool:
        """Sync movies from Kodi library"""
        try:
            # Get all movies from Kodi
            response = self.jsonrpc.execute('VideoLibrary.GetMovies', {
                'properties': [
                    'title',
                    'year',
                    'file',
                    'imdbnumber',
                    'uniqueid'
                ]
            })

            if 'result' in response and 'movies' in response['result']:
                movies = response['result']['movies']
                self.db_manager.sync_movies(movies)
                return True

            return False

        except Exception as e:
            xbmc.log(f"Error syncing library: {str(e)}", xbmc.LOGERROR)
            return False