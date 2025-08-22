import xbmc
import xbmcgui
import time
from resources.lib.utils import utils

class SearchWindow:
    def __init__(self, title="Movie Search"):
        utils.log("SearchWindow: Initializing SearchWindow with standard dialogs", "DEBUG")
        self.search_results = None
        self.title = title
        self._target_url = None

    def doModal(self):
        """Show search dialog and handle the search process"""
        utils.log("=== SearchWindow: doModal() START ===", "DEBUG")
        utils.log("SearchWindow: Showing search input dialog", "DEBUG")

        try:
            import time
            dialog_start_time = time.time()
            
            utils.log("=== ABOUT TO SHOW SEARCH INPUT MODAL ===", "DEBUG")
            # Set property to track modal state
            xbmc.executebuiltin("SetProperty(LibraryGenie.SearchModalActive,true,Home)")
            
            # Show input dialog for search query
            query = xbmcgui.Dialog().input(
                f"{self.title}: Enter your movie search query", 
                type=xbmcgui.INPUT_ALPHANUM
            )
            
            # Clear modal state property
            xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
            
            dialog_duration = time.time() - dialog_start_time
            utils.log("=== SEARCH INPUT MODAL CLOSED ===", "DEBUG")
            utils.log(f"Input dialog duration: {dialog_duration:.1f}s", "DEBUG")

            if not query:
                utils.log("SearchWindow: No query entered, cancelling search", "DEBUG")
                return

            if len(query) < 3:
                utils.log("SearchWindow: Query too short, showing warning", "DEBUG")
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "Search query must be at least 3 characters", 
                    xbmcgui.NOTIFICATION_WARNING
                )
                return

            utils.log(f"SearchWindow: Starting search with query: '{query}'", "DEBUG")
            self.start_search(query)

        except Exception as e:
            utils.log(f"=== SearchWindow: ERROR IN doModal: {str(e)} ===", "ERROR")
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "An error occurred during search", 
                xbmcgui.NOTIFICATION_ERROR
            )
        finally:
            utils.log("=== SearchWindow: doModal() COMPLETE ===", "DEBUG")

    def start_search(self, query):
        """Perform the search directly without progress modal"""
        utils.log(f"SearchWindow: Starting search with query: '{query}'", "DEBUG")
        try:
            # Record start time
            start_time = time.time()

            # Perform search directly
            utils.log("SearchWindow: Initializing RemoteAPIClient", "DEBUG")
            from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
            api_client = RemoteAPIClient()

            utils.log("SearchWindow: Starting movie search", "DEBUG")
            self.search_results = api_client.search_movies(query)

            # Calculate search time
            search_time = time.time() - start_time

            # Process results
            utils.log(f"SearchWindow: Processing search results: {self.search_results}", "DEBUG")

            # Handle both list format (direct results) and dict format (wrapped results)
            if self.search_results:
                if isinstance(self.search_results, list):
                    # Direct list of results
                    matches = self.search_results
                elif isinstance(self.search_results, dict) and self.search_results.get('status') == 'success':
                    # Wrapped results format
                    matches = self.search_results.get('matches', [])
                else:
                    matches = []

                if matches:
                    message = f"Found {len(matches)} movies in {search_time:.1f}s"
                    utils.log(f"SearchWindow: Search successful: {message}", "DEBUG")

                    # Save to search history first
                    # Convert to expected format for save_to_search_history_and_navigate
                    results_dict = {'matches': matches} if isinstance(self.search_results, list) else self.search_results
                    created_list_id = self.save_to_search_history(query, results_dict)

                    # Show success notification and store target URL for delayed navigation
                    if created_list_id:
                        utils.log(f"SearchWindow: Search successful: {message}", "DEBUG")
                        xbmcgui.Dialog().notification(
                            "LibraryGenie", 
                            f"Found {len(matches)} movies in {search_time:.1f}s", 
                            xbmcgui.NOTIFICATION_INFO
                        )
                        # Store target URL for navigation after modal closes
                        self._target_url = self.build_plugin_url({
                            'action': 'browse_list',
                            'list_id': created_list_id,
                        })
                        utils.log(f"=== STORED TARGET URL FOR DELAYED NAVIGATION: {self._target_url} ===", "DEBUG")
                    else:
                        xbmcgui.Dialog().notification(
                            "LibraryGenie", 
                            "Search completed but failed to save results", 
                            xbmcgui.NOTIFICATION_WARNING
                        )
                else:
                    utils.log("SearchWindow: No matches found", "DEBUG")
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        f"No movies found matching your search ({search_time:.1f}s)", 
                        xbmcgui.NOTIFICATION_INFO
                    )
            else:
                utils.log("SearchWindow: Search failed", "DEBUG")
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    f"Search failed ({search_time:.1f}s)", 
                    xbmcgui.NOTIFICATION_WARNING
                )

        except Exception as e:
            utils.log(f"Search error: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Search error traceback: {traceback.format_exc()}", "ERROR")
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "An error occurred during search", 
                xbmcgui.NOTIFICATION_ERROR
            )

    def save_to_search_history(self, query, search_results):
        """Save search results to search history and return the created list ID"""
        try:
            from resources.lib.data.query_manager import QueryManager
            from resources.lib.config.config_manager import Config

            config = Config()
            query_manager = QueryManager(config.db_path)

            # Extract matches from search results
            matches = search_results.get('matches', [])

            if matches:
                utils.log(f"SearchWindow: Saving {len(matches)} search results to history", "DEBUG")

                # Ensure Search History folder exists
                search_folder = query_manager.ensure_search_history_folder()
                search_folder_id = search_folder['id'] if isinstance(search_folder, dict) else search_folder

                # Create unique list name for this search
                base_name = f"Search: {query}"
                list_name = query_manager.get_unique_list_name(base_name, search_folder_id)

                # Create the list
                new_list = query_manager.create_list(list_name, search_folder_id)
                created_list_id = new_list['id'] if isinstance(new_list, dict) else new_list

                # Add each match to the list
                for match in matches:
                    imdb_id = match.get('imdb_id', '')
                    search_score = match.get('score', 0)
                    
                    # Look up title and year from imdb_exports if available
                    title_lookup = 'Unknown'
                    year_lookup = 0
                    
                    if imdb_id:
                        try:
                            lookup_query = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                            lookup_result = query_manager.execute_query(lookup_query, (imdb_id,), fetch_one=True)
                            if lookup_result:
                                title_lookup = lookup_result.get('title', 'Unknown')
                                year_lookup = int(lookup_result.get('year', 0) or 0)
                                utils.log(f"SEARCH_SAVE: Found title/year for {imdb_id}: '{title_lookup}' ({year_lookup})", "DEBUG")
                            else:
                                utils.log(f"SEARCH_SAVE: No imdb_exports entry for {imdb_id}", "DEBUG")
                        except Exception as e:
                            utils.log(f"SEARCH_SAVE: Error looking up title/year for {imdb_id}: {str(e)}", "ERROR")

                    # Prepare media item data with looked up data if available
                    media_item_data = {
                        'title': title_lookup,
                        'year': year_lookup,
                        'imdbnumber': imdb_id,
                        'source': 'search',
                        'media_type': 'movie',
                        'search_score': search_score,
                        'plot': match.get('plot', ''),
                        'genre': match.get('genre', ''),
                        'director': match.get('director', ''),
                        'cast': match.get('cast', ''),
                        'rating': match.get('rating', 0.0),
                        'poster': match.get('poster', ''),
                        'thumbnail': match.get('thumbnail', ''),
                        'fanart': match.get('fanart', ''),
                        'kodi_id': 0
                    }

                    # Insert media item and add to list atomically
                    query_manager.insert_media_item_and_add_to_list(created_list_id, media_item_data)

                if created_list_id:
                    utils.log(f"SearchWindow: Successfully saved search results to list ID: {created_list_id}", "DEBUG")
                    return created_list_id
                else:
                    utils.log("SearchWindow: Failed to create search history list", "ERROR")
                    xbmcgui.Dialog().notification(
                        "LibraryGenie", 
                        "Error creating search history list", 
                        xbmcgui.NOTIFICATION_ERROR
                    )
                    return None
            else:
                utils.log("SearchWindow: No matches found to save", "DEBUG")
                return None

        except Exception as e:
            utils.log(f"SearchWindow: Error saving to search history: {str(e)}", "ERROR")
            import traceback
            utils.log(f"SearchWindow: Traceback: {traceback.format_exc()}", "ERROR")
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "Error saving search results", 
                xbmcgui.NOTIFICATION_ERROR
            )
            return None

    def build_plugin_url(self, params):
        """Build a clean plugin URL with proper encoding"""
        try:
            from urllib.parse import urlencode
            from resources.lib.config.addon_ref import get_addon

            addon = get_addon()
            addon_id = addon.getAddonInfo("id")
            base_url = f"plugin://{addon_id}/"

            # Clean params - only include non-empty values
            cleaned_params = {k: str(v) for k, v in params.items() if v not in (None, '', False)}

            if cleaned_params:
                query_string = urlencode(cleaned_params)
                return f"{base_url}?{query_string}"
            else:
                return base_url

        except Exception as e:
            utils.log(f"SearchWindow: Error building URL: {str(e)}", "ERROR")
            return None

    def navigate_to_list(self, list_id):
        """Navigate to the search results list with improved cleanup"""
        try:
            utils.log(f"SearchWindow: Navigating to list with ID: {list_id}", "DEBUG")

            plugin_url = self.build_plugin_url({
                'action': 'browse_list',
                'list_id': list_id,
                'view': 'list',
            })

            if not plugin_url:
                utils.log("SearchWindow: Failed to build plugin URL", "ERROR")
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "Error building navigation URL", 
                    xbmcgui.NOTIFICATION_ERROR
                )
                return

            utils.log(f"SearchWindow: Built plugin URL: {plugin_url}", "DEBUG")

            # Set navigation flag to prevent concurrent dialogs
            utils.log("SearchWindow: Setting navigation flag", "DEBUG")
            import time
            current_time = time.time()
            xbmc.executebuiltin("SetProperty(LibraryGenie.Navigating,true,Home)")
            xbmc.executebuiltin(f"SetProperty(LibraryGenie.LastNavigation,{current_time},Home)")
            
            # Simple dialog cleanup
            utils.log("SearchWindow: Dialog cleanup", "DEBUG")
            xbmc.executebuiltin("Dialog.Close(all,true)")
            xbmc.sleep(100)  # Brief wait for cleanup
            
            # Clear window states
            xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")

            # Use Container.Update WITHOUT replace for back button preservation
            utils.log(f"SearchWindow: Using Container.Update WITHOUT replace to navigate to: {plugin_url}", "DEBUG")
            xbmc.executebuiltin(f'Container.Update("{plugin_url}")')
            utils.log("SearchWindow: Container.Update command executed", "DEBUG")
            
            utils.log(f"SearchWindow: Navigation sequence completed for list ID: {list_id}", "DEBUG")

        except Exception as e:
            utils.log(f"SearchWindow: Error navigating to list: {str(e)}", "ERROR")
            import traceback
            utils.log(f"SearchWindow: Navigation error traceback: {traceback.format_exc()}", "ERROR")
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "Error opening list view", 
                xbmcgui.NOTIFICATION_ERROR
            )

    def get_search_results(self):
        """Get the search results after the window closes"""
        return self.search_results

    def get_target_url(self):
        """Get the target URL for navigation after the modal closes"""
        return self._target_url

    def close(self):
        """Compatibility method for close"""
        pass