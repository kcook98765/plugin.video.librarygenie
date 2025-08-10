import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.remote_api_client import RemoteAPIClient
from resources.lib.query_manager import QueryManager
from resources.lib.config_manager import Config

class IMDbUploadManager:
    def __init__(self):
        self.config = Config()
        self.remote_client = RemoteAPIClient()
        self.jsonrpc = JSONRPC()

    def get_kodi_movie_collection(self):
        """Get all movies from Kodi library with IMDb IDs"""
        try:
            movies = self.jsonrpc.get_movies_with_imdb()

            # Filter movies with valid IMDb IDs
            valid_movies = []
            for movie in movies:
                imdb_id = movie.get('imdbnumber', '')
                if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
                    valid_movies.append({'imdb_id': imdb_id})

            utils.log(f"Found {len(valid_movies)} movies with valid IMDb IDs", "INFO")
            return valid_movies

        except Exception as e:
            utils.log(f"Error getting Kodi movie collection: {str(e)}", "ERROR")
            return []

    def upload_library_full_sync(self):
        """Upload entire Kodi library (authoritative replacement)"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        movies = self.get_kodi_movie_collection()
        if not movies:
            xbmcgui.Dialog().ok("Error", "No movies with valid IMDb IDs found in Kodi library")
            return False

        # Show confirmation dialog
        if not xbmcgui.Dialog().yesno(
            "Full Library Sync",
            f"This will upload {len(movies)} movies to the server and replace your existing collection.\n\nContinue?"
        ):
            return False

        progress = xbmcgui.DialogProgress()
        progress.create("Uploading Library", "Starting full library sync...")

        try:
            # Create progress callback function
            def progress_callback(current_chunk, total_chunks, chunk_size, current_item=None):
                if progress.iscanceled():
                    return False  # Signal to cancel the upload
                
                percent = int((current_chunk / total_chunks) * 100)
                message = f"Uploading chunk {current_chunk} of {total_chunks} ({chunk_size} movies)"
                if current_item:
                    message += f"\nProcessing: {current_item}"
                
                utils.log(f"Progress update: {percent}% - {message}", "DEBUG")
                progress.update(percent, message)
                return True  # Continue uploading

            result = self.remote_client._chunked_movie_upload(movies, mode='replace', progress_callback=progress_callback)

            progress.close()

            if result.get('success'):
                # Try multiple ways to get the uploaded count
                uploaded_count = (
                    result.get('user_movie_count') or 
                    result.get('final_tallies', {}).get('total_movies') or 
                    result.get('final_tallies', {}).get('successful_imports') or 
                    len(movies)
                )
                message = f"Successfully uploaded {uploaded_count} movies"
                utils.log(f"Upload result: {result}", "DEBUG")
                xbmcgui.Dialog().ok("Upload Complete", message)
                return True
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                xbmcgui.Dialog().ok("Upload Failed", f"Upload failed: {error_msg}")
                return False

        except Exception as e:
            progress.close()
            utils.log(f"Error during library upload: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Upload failed: {str(e)}")
            return False

    def upload_library_delta_sync(self):
        """Upload only new movies to server (delta sync)"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        movies = self.get_kodi_movie_collection()
        if not movies:
            xbmcgui.Dialog().ok("Error", "No movies with valid IMDb IDs found in Kodi library")
            return False

        progress = xbmcgui.DialogProgress()
        progress.create("Syncing Library", "Checking for new movies...")

        try:
            # Create progress callback function
            def progress_callback(current_chunk, total_chunks, chunk_size, current_item=None):
                if progress.iscanceled():
                    return False  # Signal to cancel the upload
                
                percent = int((current_chunk / total_chunks) * 100)
                message = f"Syncing chunk {current_chunk} of {total_chunks} ({chunk_size} movies)"
                if current_item:
                    message += f"\nProcessing: {current_item}"
                
                utils.log(f"Progress update: {percent}% - {message}", "DEBUG")
                progress.update(percent, message)
                return True  # Continue syncing

            result = self.remote_client._chunked_movie_upload(movies, mode='merge', progress_callback=progress_callback)

            progress.close()

            if result.get('success'):
                if result.get('message') == 'Collection already up to date':
                    xbmcgui.Dialog().ok("Sync Complete", "Your collection is already up to date")
                else:
                    # Try multiple ways to get the synced count
                    synced_count = (
                        result.get('user_movie_count') or 
                        result.get('final_tallies', {}).get('total_movies') or 
                        result.get('final_tallies', {}).get('successful_imports') or 
                        0
                    )
                    message = f"Successfully synced {synced_count} movies"
                    utils.log(f"Sync result: {result}", "DEBUG")
                    xbmcgui.Dialog().ok("Sync Complete", message)
                return True
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                xbmcgui.Dialog().ok("Sync Failed", f"Sync failed: {error_msg}")
                return False

        except Exception as e:
            progress.close()
            utils.log(f"Error during library sync: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Sync failed: {str(e)}")
            return False

    def get_upload_status(self):
        """Show current upload/sync status and history"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return

        try:
            # Get current movie count
            movie_list = self.remote_client.get_movie_list(per_page=1)
            if movie_list and movie_list.get('success'):
                total_movies = movie_list.get('user_movie_count', 0)

                # Get batch history
                batches = self.remote_client.get_batch_history()

                status_text = f"Current movies on server: {total_movies}\n\n"

                if batches:
                    status_text += "Recent uploads:\n"
                    for batch in batches[:3]:  # Show last 3 batches
                        status_text += f"• {batch.get('started_at', 'Unknown')}: {batch.get('successful_imports', 0)} movies ({batch.get('batch_type', 'unknown')})\n"
                else:
                    status_text += "No upload history found"

                xbmcgui.Dialog().ok("Upload Status", status_text)
            else:
                xbmcgui.Dialog().ok("Error", "Failed to get upload status")

        except Exception as e:
            utils.log(f"Error getting upload status: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Failed to get status: {str(e)}")

    def clear_server_library(self):
        """Clear all movies from server"""
        if not self.remote_client.test_connection():
            xbmcgui.Dialog().ok("Error", "Remote API is not configured or not accessible")
            return False

        # Double confirmation for destructive action
        if not xbmcgui.Dialog().yesno(
            "Clear Server Library",
            "This will permanently delete ALL movies from your server collection.\n\nAre you absolutely sure?"
        ):
            return False

        if not xbmcgui.Dialog().yesno(
            "Final Confirmation",
            "This action cannot be undone!\n\nProceed with clearing your entire movie collection?"
        ):
            return False

        try:
            result = self.remote_client.clear_movie_list()

            if result and result.get('success'):
                deleted_count = result.get('deleted_count', 0)
                xbmcgui.Dialog().ok("Library Cleared", f"Successfully deleted {deleted_count} movies from server")
                return True
            else:
                xbmcgui.Dialog().ok("Error", "Failed to clear library")
                return False

        except Exception as e:
            utils.log(f"Error clearing server library: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Error", f"Failed to clear library: {str(e)}")
            return False