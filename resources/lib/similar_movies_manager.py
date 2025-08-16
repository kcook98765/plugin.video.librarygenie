
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
        import time
        start_time = time.time()
        utils.log(f"[SIMILARITY TIMING] Starting similarity search for '{movie_title}' (IMDb: {imdb_id})", "INFO")
        
        try:
            # Check if IMDb ID exists in uploaded collection
            validation_start = time.time()
            if not self._is_movie_uploaded(imdb_id):
                utils.log(f"[SIMILARITY TIMING] Validation failed after {time.time() - validation_start:.3f}s", "WARNING")
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    'Movie not found in uploaded collection',
                    xbmcgui.NOTIFICATION_WARNING
                )
                return
            utils.log(f"[SIMILARITY TIMING] Validation completed in {time.time() - validation_start:.3f}s", "DEBUG")

            # Show facet selection dialog
            dialog_start = time.time()
            facets = self._show_facet_selection_dialog(movie_title)
            dialog_time = time.time() - dialog_start
            utils.log(f"[SIMILARITY TIMING] User dialog completed in {dialog_time:.3f}s", "DEBUG")
            
            if not facets:
                utils.log(f"[SIMILARITY TIMING] User cancelled dialog after {dialog_time:.3f}s", "INFO")
                return  # User cancelled

            utils.log(f"[SIMILARITY TIMING] Selected facets: {facets}", "INFO")

            # Make API request
            api_start = time.time()
            utils.log(f"[SIMILARITY TIMING] Starting API request to /similar_to", "INFO")
            results = self._find_similar_movies(imdb_id, facets)
            api_time = time.time() - api_start
            utils.log(f"[SIMILARITY TIMING] API request completed in {api_time:.3f}s, found {len(results) if results else 0} results", "INFO")
            
            if not results:
                utils.log(f"[SIMILARITY TIMING] No results from API after {api_time:.3f}s", "WARNING")
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    'No similar movies found',
                    xbmcgui.NOTIFICATION_INFO
                )
                return

            # Save to Search History
            save_start = time.time()
            utils.log(f"[SIMILARITY TIMING] Starting save to search history with {len(results)} results", "INFO")
            list_id = self._save_to_search_history(movie_title, results)
            save_time = time.time() - save_start
            utils.log(f"[SIMILARITY TIMING] Save to search history completed in {save_time:.3f}s, list_id: {list_id}", "INFO")
            
            if list_id:
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    f'Found {len(results)} similar movies'
                )
                # Navigate to the search results list with proper state management
                nav_start = time.time()
                from resources.lib.url_builder import build_plugin_url
                from resources.lib.navigation_manager import get_navigation_manager
                import xbmc
                
                # Clear any stuck navigation states before proceeding
                nav_manager = get_navigation_manager()
                nav_manager.cleanup_stuck_navigation(5.0)  # Clean up any navigation stuck > 5 seconds
                
                list_url = build_plugin_url({
                    'action': 'browse_list',
                    'list_id': list_id,
                    'view': 'list'
                })
                utils.log(f"[SIMILARITY NAV] Built navigation URL: {list_url}", "INFO")
                utils.log(f"[SIMILARITY NAV] About to execute navigation with state management", "INFO")
                
                try:
                    # Clear any existing modal/dialog states
                    utils.log(f"[SIMILARITY NAV] Clearing modal states", "DEBUG")
                    nav_manager.set_search_modal_active(False)
                    
                    # Use navigation manager for proper state handling
                    utils.log(f"[SIMILARITY NAV] Executing managed navigation", "INFO")
                    nav_manager.navigate_to_url(list_url, replace=True)
                    
                    nav_time = time.time() - nav_start
                    utils.log(f"[SIMILARITY NAV] Navigation sequence completed in {nav_time:.3f}s", "INFO")
                except Exception as nav_error:
                    nav_time = time.time() - nav_start
                    utils.log(f"[SIMILARITY NAV] Navigation failed after {nav_time:.3f}s: {str(nav_error)}", "ERROR")
                    import traceback
                    utils.log(f"[SIMILARITY NAV] Navigation exception traceback: {traceback.format_exc()}", "ERROR")
                    
                    # Ensure navigation state is cleared on error
                    nav_manager.clear_navigation_flags()
                    raise nav_error
            else:
                utils.log(f"[SIMILARITY TIMING] Save failed after {save_time:.3f}s", "ERROR")
                xbmcgui.Dialog().notification(
                    'LibraryGenie', 
                    'Failed to save results',
                    xbmcgui.NOTIFICATION_ERROR
                )

            total_time = time.time() - start_time
            utils.log(f"[SIMILARITY TIMING] Total similarity search process completed in {total_time:.3f}s", "INFO")

        except Exception as e:
            total_time = time.time() - start_time
            utils.log(f"[SIMILARITY TIMING] Error after {total_time:.3f}s: {str(e)}", "ERROR")
            import traceback
            utils.log(f"[SIMILARITY TIMING] Full traceback: {traceback.format_exc()}", "ERROR")
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
            # Create custom dialog for facet selection
            dialog = xbmcgui.Dialog()
            
            # Show info about what we're doing - fix: dialog.ok() only takes 2 arguments
            dialog.ok(
                'Find Similar Movies',
                f'Finding movies similar to: {movie_title}\n\nSelect which aspects to compare:'
            )
            
            # Facet options
            facet_options = [
                'Plot similarity',
                'Mood/tone similarity', 
                'Themes/subtext similarity',
                'Genre/tropes similarity'
            ]
            
            # Let user select multiple facets
            selected_indices = dialog.multiselect(
                'Select similarity facets:',
                facet_options
            )
            
            # Ensure dialog is properly closed and UI settles
            del dialog
            import xbmc
            xbmc.sleep(100)  # Allow UI to settle after dialog closes
            
            if not selected_indices:
                utils.log("User cancelled facet selection", "DEBUG")
                return None  # User cancelled
            
            # Build facets dict
            facets = {
                'include_plot': 0 in selected_indices,
                'include_mood': 1 in selected_indices,
                'include_themes': 2 in selected_indices,
                'include_genre': 3 in selected_indices
            }
            
            utils.log(f"User selected facets: {facets}", "DEBUG")
            return facets
            
        except Exception as e:
            utils.log(f"Error showing facet selection dialog: {str(e)}", "ERROR")
            return None

    def _find_similar_movies(self, imdb_id, facets):
        """Call the similar movies API endpoint"""
        import time
        try:
            if not self.remote_client.api_key:
                utils.log("[SIMILARITY API] Remote API not configured", "WARNING")
                return []

            # Make request to /similar_to endpoint
            data = {
                'reference_imdb_id': imdb_id,
                **facets
            }
            
            utils.log(f"[SIMILARITY API] Making POST request to /similar_to with data: {data}", "DEBUG")
            request_start = time.time()
            response = self.remote_client._make_request('POST', '/similar_to', data)
            request_time = time.time() - request_start
            
            if response and response.get('success'):
                similar_imdb_ids = response.get('results', [])
                utils.log(f"[SIMILARITY API] Request successful in {request_time:.3f}s, found {len(similar_imdb_ids)} similar movies", "INFO")
                utils.log(f"[SIMILARITY API] First 5 results: {similar_imdb_ids[:5]}", "DEBUG")
                return similar_imdb_ids
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'No response'
                utils.log(f"[SIMILARITY API] Request failed after {request_time:.3f}s: {error_msg}", "ERROR")
                utils.log(f"[SIMILARITY API] Full response: {response}", "DEBUG")
                return []

        except Exception as e:
            utils.log(f"[SIMILARITY API] Exception in API request: {str(e)}", "ERROR")
            import traceback
            utils.log(f"[SIMILARITY API] API exception traceback: {traceback.format_exc()}", "ERROR")
            return []

    def _save_to_search_history(self, movie_title, similar_imdb_ids):
        """Save similar movies results to Search History folder"""
        import time
        try:
            # Convert IMDb IDs to the format expected by search history
            format_start = time.time()
            formatted_results = []
            for imdb_id in similar_imdb_ids:
                formatted_movie = {
                    'imdbnumber': imdb_id,
                    'imdb_id': imdb_id,
                    'score': 1.0,  # All similar movies get max score
                    'search_score': 1.0
                }
                formatted_results.append(formatted_movie)
            format_time = time.time() - format_start
            utils.log(f"[SIMILARITY SAVE] Formatted {len(similar_imdb_ids)} results in {format_time:.3f}s", "DEBUG")

            # Use the existing search history functionality
            query = f"Similar to {movie_title}"
            db_start = time.time()
            utils.log(f"[SIMILARITY SAVE] Adding to search history with query: '{query}'", "DEBUG")
            list_id = self.db_manager.add_search_history(query, formatted_results)
            db_time = time.time() - db_start
            utils.log(f"[SIMILARITY SAVE] Database save completed in {db_time:.3f}s, list_id: {list_id}", "INFO")
            
            return list_id

        except Exception as e:
            utils.log(f"[SIMILARITY SAVE] Error saving to search history: {str(e)}", "ERROR")
            import traceback
            utils.log(f"[SIMILARITY SAVE] Save exception traceback: {traceback.format_exc()}", "ERROR")
            return None
