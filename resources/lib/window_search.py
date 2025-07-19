import pyxbmct
import xbmcgui
from resources.lib.window_base import BaseWindow
from resources.lib.window_search_progress import SearchProgressWindow
from resources.lib import utils

class SearchWindow(BaseWindow):
    def __init__(self, title="Movie Search"):
        utils.log("SearchWindow: Initializing SearchWindow", "DEBUG")
        super().__init__(title)
        self.setGeometry(600, 300, 6, 4)
        self.search_results = None

        utils.log("SearchWindow: Setting up UI", "DEBUG")
        self.setup_ui()
        utils.log("SearchWindow: Setting navigation", "DEBUG")
        self.set_navigation()
        utils.log("SearchWindow: SearchWindow initialization complete", "DEBUG")

    def setup_ui(self):
        utils.log("SearchWindow: Creating UI controls", "DEBUG")
        # Title label
        self.title_label = pyxbmct.Label("Enter your movie search query:", alignment=0)
        self.placeControl(self.title_label, 0, 0, columnspan=4, pad_x=10, pad_y=10)

        # Search input field
        self.search_input = pyxbmct.Edit("", "Search for movies...")
        self.placeControl(self.search_input, 1, 0, columnspan=4, pad_x=10, pad_y=5)

        # Example text
        self.example_label = pyxbmct.Label("Example: 'zombie movies from the 80s' or 'romantic comedies with happy endings'", alignment=0)
        self.placeControl(self.example_label, 2, 0, columnspan=4, pad_x=10, pad_y=5)

        # Buttons
        self.search_button = pyxbmct.Button("Search")
        self.placeControl(self.search_button, 4, 0, columnspan=2, pad_x=5, pad_y=10)

        self.cancel_button = pyxbmct.Button("Cancel")
        self.placeControl(self.cancel_button, 4, 2, columnspan=2, pad_x=5, pad_y=10)

        # Connect button actions
        utils.log("SearchWindow: Connecting button actions", "DEBUG")
        self.connect(self.search_button, self.on_search_click)
        self.connect(self.cancel_button, self.close)
        utils.log("SearchWindow: UI setup complete", "DEBUG")

    def set_navigation(self):
        # Set up navigation between controls
        self.search_input.controlDown(self.search_button)
        self.search_input.controlUp(self.cancel_button)

        self.search_button.controlUp(self.search_input)
        self.search_button.controlDown(self.search_input)
        self.search_button.controlRight(self.cancel_button)

        self.cancel_button.controlUp(self.search_input)
        self.cancel_button.controlDown(self.search_input)
        self.cancel_button.controlLeft(self.search_button)

        # Set initial focus on the search input
        self.setFocus(self.search_input)

    def on_search_click(self):
        """Handle search button click or Enter key"""
        utils.log("SearchWindow: on_search_click called", "DEBUG")
        
        try:
            query = self.search_input.getText().strip()
            utils.log(f"SearchWindow: Retrieved query text: '{query}'", "DEBUG")

            if not query:
                utils.log("SearchWindow: Empty query, showing warning", "DEBUG")
                self.show_notification("Please enter a search query", xbmcgui.NOTIFICATION_WARNING)
                return

            if len(query) < 3:
                utils.log("SearchWindow: Query too short, showing warning", "DEBUG")
                self.show_notification("Search query must be at least 3 characters", xbmcgui.NOTIFICATION_WARNING)
                return

            # Close this window and start the progressive search
            utils.log("SearchWindow: Closing window and starting progressive search", "DEBUG")
            self.close()
            self.start_progressive_search(query)
        except Exception as e:
            utils.log(f"SearchWindow: Error in on_search_click: {str(e)}", "ERROR")
            self.show_notification("An error occurred during search", xbmcgui.NOTIFICATION_ERROR)

    def start_progressive_search(self, query):
        """Start the progressive search with the given query"""
        utils.log(f"SearchWindow: Starting progressive search with query: '{query}'", "DEBUG")
        try:
            # Show progressive search modal
            utils.log("SearchWindow: Creating SearchProgressWindow", "DEBUG")
            progress_window = SearchProgressWindow(query)
            utils.log("SearchWindow: Showing progress window modal", "DEBUG")
            progress_window.doModal()

            # Get results from the modal
            utils.log("SearchWindow: Getting results from progress window", "DEBUG")
            self.search_results = progress_window.get_results()
            del progress_window

            # Show results summary
            utils.log(f"SearchWindow: Processing search results: {self.search_results}", "DEBUG")
            if self.search_results and self.search_results.get('status') == 'success':
                matches = self.search_results.get('matches', [])
                total_time = self.search_results.get('timing', {}).get('total', 0)

                if matches:
                    message = f"Found {len(matches)} movies in {total_time:.1f}s"
                    utils.log(f"SearchWindow: Search successful: {message}", "DEBUG")
                    self.show_notification(message, xbmcgui.NOTIFICATION_INFO)
                else:
                    utils.log("SearchWindow: No matches found", "DEBUG")
                    self.show_notification("No movies found matching your search", xbmcgui.NOTIFICATION_INFO)
            else:
                utils.log("SearchWindow: Search cancelled or failed", "DEBUG")
                self.show_notification("Search was cancelled or failed", xbmcgui.NOTIFICATION_WARNING)

        except Exception as e:
            utils.log(f"Search error: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Search error traceback: {traceback.format_exc()}", "ERROR")
            self.show_notification("An error occurred during search", xbmcgui.NOTIFICATION_ERROR)

    def get_search_results(self):
        """Get the search results after the window closes"""
        return self.search_results

    def onAction(self, action):
        """Handle window actions"""
        action_id = action.getId()
        utils.log(f"SearchWindow: onAction called with action_id: {action_id}", "DEBUG")

        # Debug pyxbmct available attributes
        utils.log(f"SearchWindow: Available pyxbmct actions: {[attr for attr in dir(pyxbmct) if 'ACTION' in attr]}", "DEBUG")

        # Handle back/escape key
        if action_id in (pyxbmct.ACTION_NAV_BACK, pyxbmct.ACTION_PREVIOUS_MENU):
            utils.log("SearchWindow: Navigation back/previous detected, closing window", "DEBUG")
            self.close()
        # Handle enter/select key
        elif action_id in (7, 100):
            utils.log("SearchWindow: Select/click action detected", "DEBUG")
            # Only trigger search if focus is on search input or search button
            focused_control = self.getFocus()
            if focused_control == self.search_input or focused_control == self.search_button:
                utils.log("SearchWindow: Focus on search control, triggering search", "DEBUG")
                self.on_search_click()
            else:
                utils.log("SearchWindow: Focus not on search controls, ignoring action", "DEBUG")
        else:
            utils.log(f"SearchWindow: Passing action {action_id} to parent", "DEBUG")
            super().onAction(action)