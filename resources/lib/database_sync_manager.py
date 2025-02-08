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
        progress = xbmcgui.DialogProgress()
        progress.create("Syncing Library")
        
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
                progress.close()
                
                # Calculate statistics
                total_movies = len(movies)
                movies_with_imdb = sum(1 for movie in movies if movie.get('imdbnumber'))
                percentage = (movies_with_imdb / total_movies * 100) if total_movies > 0 else 0
                
                stats_message = (
                    f"Sync Complete\n\n"
                    f"Total Movies: {total_movies}\n"
                    f"Movies with IMDB IDs: {movies_with_imdb}\n"
                    f"Percentage: {percentage:.1f}%"
                )
                xbmcgui.Dialog().ok("Library Sync Statistics", stats_message)
                return True

            progress.close()
            return False

        except Exception as e:
            progress.close()
            xbmc.log(f"Error syncing library: {str(e)}", xbmc.LOGERROR)
            return False