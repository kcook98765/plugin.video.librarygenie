
import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib.remote_api_client import RemoteAPIClient

class SimilarMoviesManager:
    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)
        self.remote_client = RemoteAPIClient()

    def show_similar_movies_dialog(self, imdb_id, movie_title):
        """Show facet selection dialog and execute similar movies search"""
        try:
            # Check if IMDb ID exists in uploaded collection
            if not self._is_movie_uploaded(imdb_id):
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    'Movie not found in uploaded collection',
                    xbmcgui.NOTIFICATION_WARNING
                )
                return

            # Show facet selection dialog
            facets = self._show_facet_selection_dialog(movie_title)
            if not facets:
                return  # User cancelled

            # Make API request
            results = self._find_similar_movies(imdb_id, facets)
            if not results:
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    'No similar movies found',
                    xbmcgui.NOTIFICATION_INFO
                )
                return

            # Save to Search History
            list_id = self._save_to_search_history(movie_title, results)
            if list_id:
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    f'Found {len(results)} similar movies'
                )
                # Refresh container to show new search results
                xbmc.executebuiltin('Container.Refresh')
            else:
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    'Failed to save results',
                    xbmcgui.NOTIFICATION_ERROR
                )

        except Exception as e:
            utils.log(f"Error in similar movies dialog: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification(
                'LibraryGenie', 
                'Error finding similar movies',
                xbmcgui.NOTIFICATION_ERROR
            )

    def _is_movie_uploaded(self, imdb_id):
        """Check if movie has valid IMDb ID (skip upload requirement)"""
        try:
            # Simply check if we have a valid IMDb ID format
            if imdb_id and imdb_id.startswith('tt') and len(imdb_id) > 2:
                utils.log(f"Movie {imdb_id} has valid IMDb ID format", "DEBUG")
                return True
            else:
                utils.log(f"Movie {imdb_id} has invalid IMDb ID format", "DEBUG")
                return False
            
        except Exception as e:
            utils.log(f"Error checking IMDb ID format: {str(e)}", "ERROR")
            return False

    def _show_facet_selection_dialog(self, movie_title):
        """Show dialog for user to select which facets to include"""
        try:
            dialog = xbmcgui.Dialog()
            
            # Use individual yes/no dialogs for each facet - more reliable in Kodi
            facet_questions = [
                ('include_plot', 'Include plot/story similarity?'),
                ('include_mood', 'Include mood/tone similarity?'),
                ('include_themes', 'Include themes/subtext similarity?'),
                ('include_genre', 'Include genre/tropes similarity?')
            ]
            
            facets = {}
            selected_count = 0
            
            # Ask about each facet individually
            for facet_key, question in facet_questions:
                response = dialog.yesno(
                    f'Similar to: {movie_title}',
                    question
                )
                facets[facet_key] = response
                if response:
                    selected_count += 1
            
            # Ensure at least one facet is selected
            if selected_count == 0:
                dialog.ok(
                    'Find Similar Movies',
                    'At least one similarity aspect must be selected.'
                )
                return None
            
            utils.log(f"User selected facets: {facets}", "DEBUG")
            return facets
            
        except Exception as e:
            utils.log(f"Error showing facet selection dialog: {str(e)}", "ERROR")
            return None

    def _find_similar_movies(self, imdb_id, facets):
        """Call the similar movies API endpoint"""
        try:
            if not self.remote_client.api_key:
                utils.log("Remote API not configured", "WARNING")
                return []

            # Make request to /similar_to endpoint
            data = {
                'reference_imdb_id': imdb_id,
                **facets
            }
            
            response = self.remote_client._make_request('POST', '/similar_to', data)
            
            if response and response.get('success'):
                similar_imdb_ids = response.get('results', [])
                utils.log(f"Found {len(similar_imdb_ids)} similar movies", "DEBUG")
                return similar_imdb_ids
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response'
                utils.log(f"Similar movies request failed: {error_msg}", "ERROR")
                return []

        except Exception as e:
            utils.log(f"Error finding similar movies: {str(e)}", "ERROR")
            return []

    def _save_to_search_history(self, movie_title, similar_imdb_ids):
        """Save similar movies results to Search History folder"""
        try:
            # Convert IMDb IDs to the format expected by search history
            formatted_results = []
            for imdb_id in similar_imdb_ids:
                formatted_movie = {
                    'imdbnumber': imdb_id,
                    'imdb_id': imdb_id,
                    'score': 1.0,  # All similar movies get max score
                    'search_score': 1.0
                }
                formatted_results.append(formatted_movie)

            # Use the existing search history functionality
            query = f"Similar to {movie_title}"
            list_id = self.db_manager.add_search_history(query, formatted_results)
            
            return list_id

        except Exception as e:
            utils.log(f"Error saving similar movies to search history: {str(e)}", "ERROR")
            return None
