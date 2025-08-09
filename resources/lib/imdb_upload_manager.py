
import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.remote_api_client import RemoteAPIClient
from resources.lib.query_manager import QueryManager
from resources.lib.config_manager import Config
import uuid
import time

class IMDBUploadManager:
    def __init__(self):
        self.config = Config()
        self.jsonrpc = JSONRPC()
        self.remote_client = RemoteAPIClient()
        self.query_manager = QueryManager(self.config.db_path)
        
    def start_upload_process(self):
        """Main entry point for IMDB upload process"""
        if not self.remote_client.api_key:
            xbmcgui.Dialog().ok("Error", "Remote API not configured. Please set up the API connection first.")
            return False
            
        # Show confirmation dialog
        if not xbmcgui.Dialog().yesno(
            "Upload IMDB List", 
            "This will upload your Kodi movie library IMDB numbers to the remote server.\n\nProceed?"
        ):
            return False
            
        progress = xbmcgui.DialogProgress()
        progress.create("Uploading IMDB List")
        
        try:
            # Step 1: Clear and populate holding table
            progress.update(10, "Clearing previous data...")
            self._clear_holding_table()
            
            # Step 2: Fetch movies from Kodi
            progress.update(20, "Fetching movies from Kodi library...")
            movies = self._fetch_all_kodi_movies(progress)
            
            if not movies:
                xbmcgui.Dialog().ok("Info", "No movies found in Kodi library")
                return False
                
            # Step 3: Store to holding table
            progress.update(60, "Storing movie data...")
            self._store_to_holding_table(movies)
            
            # Step 4: Extract valid IMDB numbers
            progress.update(70, "Extracting IMDB numbers...")
            imdb_numbers = self._get_valid_imdb_numbers()
            
            if not imdb_numbers:
                xbmcgui.Dialog().ok("Info", "No valid IMDB numbers found in your library")
                return False
                
            # Step 5: Upload to server
            progress.update(80, f"Uploading {len(imdb_numbers)} IMDB numbers...")
            success = self._upload_to_server(imdb_numbers, progress)
            
            if success:
                progress.update(100, "Upload completed successfully!")
                time.sleep(1)
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Successfully uploaded {len(imdb_numbers)} IMDB numbers",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )
                return True
            else:
                xbmcgui.Dialog().ok("Error", "Upload failed. Check logs for details.")
                return False
                
        except Exception as e:
            utils.log(f"Upload process failed: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Upload failed: {str(e)}")
            return False
        finally:
            progress.close()
            
    def _clear_holding_table(self):
        """Clear the IMDB holding table"""
        self.query_manager.execute_query("DELETE FROM imdb_holding", fetch_all=False)
        utils.log("Cleared IMDB holding table", "DEBUG")
        
    def _fetch_all_kodi_movies(self, progress):
        """Fetch all movies from Kodi library with pagination"""
        all_movies = []
        start = 0
        limit = 100
        
        while True:
            if progress.iscanceled():
                return []
                
            response = self.jsonrpc.get_movies(start, limit, 
                properties=["title", "year", "imdbnumber", "uniqueid"])
            
            if 'result' not in response or 'movies' not in response['result']:
                break
                
            movies = response['result']['movies']
            if not movies:
                break
                
            all_movies.extend(movies)
            
            total = response['result'].get('limits', {}).get('total', 0)
            if total > 0:
                percent = min(50, 20 + (len(all_movies) / total) * 30)
                progress.update(int(percent), f"Fetched {len(all_movies)}/{total} movies...")
            
            start += limit
            
        utils.log(f"Fetched {len(all_movies)} movies from Kodi", "DEBUG")
        return all_movies
        
    def _store_to_holding_table(self, movies):
        """Store movie data to holding table"""
        for movie in movies:
            # Extract IMDB number from various sources
            imdb_id = self._extract_imdb_id(movie)
            
            data = {
                'kodi_id': movie.get('movieid', 0),
                'title': movie.get('title', ''),
                'year': movie.get('year', 0),
                'imdb_id': imdb_id,
                'raw_uniqueid': str(movie.get('uniqueid', {})),
                'raw_imdbnumber': movie.get('imdbnumber', '')
            }
            
            self.query_manager.execute_query("""
                INSERT INTO imdb_holding (kodi_id, title, year, imdb_id, raw_uniqueid, raw_imdbnumber)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data['kodi_id'], data['title'], data['year'], data['imdb_id'], 
                  data['raw_uniqueid'], data['raw_imdbnumber']), fetch_all=False)
                  
        utils.log(f"Stored {len(movies)} movies to holding table", "DEBUG")
        
    def _extract_imdb_id(self, movie):
        """Extract IMDB ID from movie data"""
        # Try imdbnumber field first
        imdb_number = movie.get('imdbnumber', '')
        if imdb_number and imdb_number.startswith('tt'):
            return imdb_number
            
        # Try uniqueid field
        unique_ids = movie.get('uniqueid', {})
        if isinstance(unique_ids, dict):
            # Try imdb key
            if 'imdb' in unique_ids and unique_ids['imdb'].startswith('tt'):
                return unique_ids['imdb']
            # Try tmdb or other sources that might have imdb format
            for key, value in unique_ids.items():
                if isinstance(value, str) and value.startswith('tt'):
                    return value
                    
        return ''
        
    def _get_valid_imdb_numbers(self):
        """Get valid IMDB numbers from holding table"""
        result = self.query_manager.execute_query("""
            SELECT DISTINCT imdb_id 
            FROM imdb_holding 
            WHERE imdb_id IS NOT NULL 
            AND imdb_id != '' 
            AND imdb_id LIKE 'tt%'
        """)
        
        imdb_numbers = [row['imdb_id'] for row in result]
        utils.log(f"Found {len(imdb_numbers)} valid IMDB numbers", "DEBUG")
        return imdb_numbers
        
    def _upload_to_server(self, imdb_numbers, progress):
        """Upload IMDB numbers to server using batch upload API"""
        try:
            # Step 1: Start batch session
            session_response = self.remote_client.start_batch_upload(
                mode='replace',  # Replace existing collection
                total_count=len(imdb_numbers),
                source='kodi'
            )
            
            if not session_response or not session_response.get('success'):
                utils.log(f"Failed to start batch session: {session_response}", "ERROR")
                return False
                
            upload_id = session_response['upload_id']
            max_chunk = session_response.get('max_chunk', 500)
            chunk_size = min(500, max_chunk)
            
            utils.log(f"Started batch upload session: {upload_id}", "DEBUG")
            
            # Step 2: Upload in chunks
            chunks = [imdb_numbers[i:i + chunk_size] 
                     for i in range(0, len(imdb_numbers), chunk_size)]
            
            for chunk_index, chunk in enumerate(chunks):
                if progress.iscanceled():
                    return False
                    
                percent = 80 + (chunk_index / len(chunks)) * 15
                progress.update(int(percent), f"Uploading chunk {chunk_index + 1}/{len(chunks)}...")
                
                # Format items for API
                items = [{'imdb_id': imdb_id} for imdb_id in chunk]
                
                # Upload chunk with retry
                success = False
                for attempt in range(3):
                    try:
                        idempotency_key = str(uuid.uuid4())
                        result = self.remote_client.upload_batch_chunk(
                            upload_id, chunk_index, items, idempotency_key
                        )
                        
                        if result and result.get('success'):
                            success = True
                            utils.log(f"Uploaded chunk {chunk_index}: {result.get('results', {})}", "DEBUG")
                            break
                        else:
                            utils.log(f"Chunk upload failed (attempt {attempt + 1}): {result}", "WARNING")
                            
                    except Exception as e:
                        utils.log(f"Chunk upload error (attempt {attempt + 1}): {str(e)}", "WARNING")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        
                if not success:
                    utils.log(f"Failed to upload chunk {chunk_index} after 3 attempts", "ERROR")
                    return False
                    
            # Step 3: Commit the batch
            progress.update(95, "Finalizing upload...")
            commit_response = self.remote_client.commit_batch_upload(upload_id)
            
            if commit_response and commit_response.get('success'):
                utils.log(f"Batch upload committed successfully: {commit_response.get('final_tallies', {})}", "INFO")
                return True
            else:
                utils.log(f"Failed to commit batch upload: {commit_response}", "ERROR")
                return False
                
        except Exception as e:
            utils.log(f"Upload to server failed: {str(e)}", "ERROR")
            return False
            
    def get_upload_stats(self):
        """Get statistics about the last upload"""
        stats = self.query_manager.execute_query("""
            SELECT 
                COUNT(*) as total_movies,
                COUNT(CASE WHEN imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%' THEN 1 END) as valid_imdb,
                COUNT(CASE WHEN imdb_id IS NULL OR imdb_id = '' OR imdb_id NOT LIKE 'tt%' THEN 1 END) as invalid_imdb
            FROM imdb_holding
        """, fetch_all=False)
        
        if stats:
            row = stats[0]
            return {
                'total_movies': row['total_movies'],
                'valid_imdb': row['valid_imdb'],
                'invalid_imdb': row['invalid_imdb'],
                'percentage': (row['valid_imdb'] / row['total_movies'] * 100) if row['total_movies'] > 0 else 0
            }
        return {'total_movies': 0, 'valid_imdb': 0, 'invalid_imdb': 0, 'percentage': 0}
