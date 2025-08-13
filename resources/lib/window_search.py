import xbmc
import xbmcgui
import time
from resources.lib import utils

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
        """Perform the search with progress dialog"""
        utils.log(f"SearchWindow: Starting search with progress dialog for query: '{query}'", "DEBUG")
        try:
            # Use the progress window for the search
            from resources.lib.window_search_progress import SearchProgressWindow
            progress_window = SearchProgressWindow(query)
            
            utils.log("SearchWindow: Showing progress dialog", "DEBUG")
            progress_window.doModal()
            
            # Get the search results
            self.search_results = progress_window.get_results()
            utils.log(f"SearchWindow: Retrieved search results: {self.search_results}", "DEBUG")

            # Process results
            if self.search_results and not progress_window.cancelled:
                if isinstance(self.search_results, dict):
                    if self.search_results.get('status') == 'error':
                        error_msg = self.search_results.get('error', 'Unknown error')
                        utils.log(f"SearchWindow: Search error: {error_msg}", "ERROR")
                        xbmcgui.Dialog().notification(
                            "LibraryGenie", 
                            f"Search error: {error_msg}", 
                            xbmcgui.NOTIFICATION_ERROR
                        )
                        return
                    elif self.search_results.get('status') == 'cancelled':
                        utils.log("SearchWindow: Search was cancelled", "DEBUG")
                        return

                    matches = self.search_results.get('matches', [])
                elif isinstance(self.search_results, list):
                    matches = self.search_results
                else:
                    matches = []

                if matches:
                    utils.log(f"SearchWindow: Search successful with {len(matches)} matches", "DEBUG")

                    # Save to search history
                    results_dict = {'matches': matches} if isinstance(self.search_results, list) else self.search_results
                    created_list_id = self.save_to_search_history(query, results_dict)

                    if created_list_id:
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
                        "No movies found matching your search", 
                        xbmcgui.NOTIFICATION_INFO
                    )
            elif progress_window.cancelled:
                utils.log("SearchWindow: Search was cancelled by user", "DEBUG")
            else:
                utils.log("SearchWindow: Search failed or returned no results", "DEBUG")
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "Search failed", 
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
            from resources.lib.database_manager import DatabaseManager
            from resources.lib.config_manager import Config

            config = Config()
            db_manager = DatabaseManager(config.db_path)

            # Extract matches from search results
            matches = search_results.get('matches', [])

            if matches:
                utils.log(f"SearchWindow: Saving {len(matches)} search results to history", "DEBUG")

                # Convert matches to the format expected by add_search_history
                formatted_results = []
                for match in matches:
                    formatted_result = {
                        'imdbnumber': match.get('imdb_id', ''),
                        'score': match.get('score', 0),
                        'search_score': match.get('score', 0)
                    }
                    formatted_results.append(formatted_result)

                # Use the existing add_search_history method - it creates only ONE list
                created_list_id = db_manager.add_search_history(query, formatted_results)

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
            from resources.lib.addon_ref import get_addon

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

            # Use Container.Update for more reliable plugin navigation
            utils.log(f"SearchWindow: Using Container.Update to navigate to: {plugin_url}", "DEBUG")
            xbmc.executebuiltin(f'Container.Update({plugin_url})')
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