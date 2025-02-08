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
                
                # First ensure table exists
                self.query_manager.setup_movies_reference_table()
                
                # Clear existing library entries
                self.query_manager.execute_query("DELETE FROM movies_reference WHERE source = 'Lib'")
                
                # Process each movie
                for movie in movies:
                    file_path = movie.get('file', '')
                    file_name = file_path.split('/')[-1] if file_path else ''
                    path = '/'.join(file_path.split('/')[:-1]) if file_path else ''
                    
                    # Get IMDB number either directly or from uniqueid
                    imdb_id = movie.get('imdbnumber') or movie.get('uniqueid', {}).get('imdb')
                    tmdb_id = movie.get('uniqueid', {}).get('tmdb')
                    tvdb_id = movie.get('uniqueid', {}).get('tvdb')
                    
                    self.query_manager.execute_query(
                        """INSERT INTO movies_reference 
                           (file_path, file_name, movieid, imdbnumber, tmdbnumber, tvdbnumber, source)
                           VALUES (?, ?, ?, ?, ?, ?, 'Lib')""",
                        (path, file_name, movie.get('movieid'), imdb_id, tmdb_id, tvdb_id)
                    )
                
                progress.close()
                
                # Calculate detailed statistics
                total_movies = len(movies)
                total_added = len(processed_movie_ids - existing_movie_ids)
                total_updated = len(processed_movie_ids & existing_movie_ids)
                total_removed = len(existing_movie_ids - processed_movie_ids)
                movies_with_imdb = sum(1 for movie in movies if movie.get('imdbnumber') or movie.get('uniqueid', {}).get('imdb'))
                percentage = (movies_with_imdb / total_movies * 100) if total_movies > 0 else 0
                
                stats_message = (
                    f"Sync Complete\n\n"
                    f"Total Movies: {total_movies}\n"
                    f"New Movies Added: {total_added}\n"
                    f"Movies Updated: {total_updated}\n"
                    f"Movies Removed: {total_removed}\n"
                    f"Movies with IMDB IDs: {movies_with_imdb}\n"
                    f"IMDB Coverage: {percentage:.1f}%"
                )
                xbmcgui.Dialog().ok("Library Sync Statistics", stats_message)
                return True

            progress.close()
            return False

        except Exception as e:
            progress.close()
            xbmc.log(f"Error syncing library: {str(e)}", xbmc.LOGERROR)
            return False