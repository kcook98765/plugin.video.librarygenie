import xbmc
import xbmcgui
import threading
import time
from resources.lib.remote_api_client import RemoteAPIClient
from resources.lib import utils

class SearchProgressWindow:
    def __init__(self, query):
        self.query = query
        self.search_results = None
        self.progress_dialog = None
        self.cancelled = False

    def doModal(self):
        """Show progress dialog and perform search"""
        utils.log(f"SearchProgressWindow: Starting search for query: {self.query}", "DEBUG")

        # Create progress dialog
        self.progress_dialog = xbmcgui.DialogProgress()
        self.progress_dialog.create("Searching Movies", f"Searching for: {self.query}")

        try:
            # Start search in background thread
            search_thread = threading.Thread(target=self._perform_search)
            search_thread.daemon = True
            search_thread.start()

            # Monitor progress with more detailed updates
            step = 0
            while search_thread.is_alive():
                if self.progress_dialog.iscanceled():
                    self.cancelled = True
                    utils.log("SearchProgressWindow: Search cancelled by user", "DEBUG")
                    break

                # Update progress dialog with animated progress
                step = (step + 1) % 100
                self.progress_dialog.update(step, f"Contacting search server... Query: {self.query}")
                xbmc.sleep(100)  # Check every 100ms

            search_thread.join(timeout=2.0)  # Wait up to 2 seconds for thread to finish

            # Show completion message briefly
            if not self.cancelled and self.search_results:
                if isinstance(self.search_results, dict):
                    matches = self.search_results.get('matches', [])
                    if matches:
                        self.progress_dialog.update(100, f"Search completed! Found {len(matches)} movies")
                        xbmc.sleep(500)  # Show completion message for 500ms

        except Exception as e:
            utils.log(f"SearchProgressWindow: Error during search: {str(e)}", "ERROR")
            self.search_results = {'status': 'error', 'error': str(e)}
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()

    def _perform_search(self):
        """Perform the actual search"""
        try:
            utils.log("SearchProgressWindow: Initializing RemoteAPIClient", "DEBUG")
            api_client = RemoteAPIClient()

            utils.log("SearchProgressWindow: Starting movie search", "DEBUG")
            self.search_results = api_client.search_movies(self.query)

            if self.cancelled:
                utils.log("SearchProgressWindow: Search was cancelled", "DEBUG")
                self.search_results = {'status': 'cancelled'}
            elif self.search_results:
                utils.log(f"SearchProgressWindow: Search completed successfully", "DEBUG")
            else:
                utils.log("SearchProgressWindow: Search returned no results", "WARNING")
                self.search_results = {'status': 'error', 'error': 'No results returned'}

        except Exception as e:
            utils.log(f"SearchProgressWindow: Error in search thread: {str(e)}", "ERROR")
            import traceback
            utils.log(f"SearchProgressWindow: Traceback: {traceback.format_exc()}", "ERROR")
            self.search_results = {'status': 'error', 'error': str(e)}

    def get_results(self):
        """Get the search results"""
        return self.search_results