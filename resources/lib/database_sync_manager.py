
from typing import List, Dict, Any, Optional
import xbmc
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.query_manager import QueryManager

class DatabaseSyncManager:
    def __init__(self, query_manager: QueryManager):
        self.query_manager = query_manager
        self.jsonrpc = JSONRPC()

    def setup_tables(self):
        """Create necessary tables for movie reference and addon metadata"""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS movies_reference (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path   TEXT,
                file_name   TEXT,
                movieid     INTEGER,
                imdbnumber  TEXT,
                tmdbnumber  TEXT,
                tvdbnumber  TEXT,
                addon_file  TEXT,
                source      TEXT NOT NULL CHECK(source IN ('Lib','File'))
            )
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_lib_unique
                ON movies_reference(file_path, file_name)
                WHERE source = 'Lib'
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_file_unique
                ON movies_reference(addon_file)
                WHERE source = 'File'
            """,
            """
            CREATE TABLE IF NOT EXISTS addon_metadata (
                movie_id    INTEGER PRIMARY KEY,
                filename    TEXT,
                title       TEXT,
                duration    INTEGER,
                rating      REAL,
                year       INTEGER,
                date       TEXT,
                plot       TEXT,
                plotoutline TEXT,
                thumb      TEXT,
                poster     TEXT,
                fanart     TEXT,
                banner     TEXT,
                clearart   TEXT,
                clearlogo  TEXT,
                landscape  TEXT,
                icon       TEXT,
                FOREIGN KEY(movie_id) REFERENCES movies_reference(id) ON DELETE CASCADE
            )
            """
        ]
        
        for query in queries:
            self.query_manager.execute_query(query)

    def sync_library_movies(self):
        """Sync movies from Kodi library"""
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
            
            # Begin transaction
            self.query_manager.execute_query("BEGIN TRANSACTION")
            
            try:
                # Clear existing library entries
                self.query_manager.execute_query(
                    "DELETE FROM movies_reference WHERE source = 'Lib'"
                )

                # Insert new entries
                for movie in movies:
                    file_path = movie.get('file', '')
                    path_parts = file_path.rsplit('/', 1)
                    file_path = path_parts[0] + '/' if len(path_parts) > 1 else ''
                    file_name = path_parts[1] if len(path_parts) > 1 else file_path
                    
                    uniqueid = movie.get('uniqueid', {})
                    
                    self.query_manager.execute_query(
                        """
                        INSERT INTO movies_reference 
                        (file_path, file_name, movieid, imdbnumber, tmdbnumber, tvdbnumber, source)
                        VALUES (?, ?, ?, ?, ?, ?, 'Lib')
                        """,
                        (
                            file_path,
                            file_name,
                            movie.get('movieid'),
                            movie.get('imdbnumber') or uniqueid.get('imdb'),
                            uniqueid.get('tmdb'),
                            uniqueid.get('tvdb'),
                        )
                    )
                
                # Commit transaction
                self.query_manager.execute_query("COMMIT")
                return True
                
            except Exception as e:
                # Rollback on error
                self.query_manager.execute_query("ROLLBACK")
                xbmc.log(f"Error syncing library: {str(e)}", xbmc.LOGERROR)
                return False
                
        return False
