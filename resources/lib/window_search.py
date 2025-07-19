
import pyxbmct
import xbmcgui
from resources.lib.window_base import BaseWindow
from resources.lib.window_search_progress import SearchProgressWindow
from resources.lib import utils

class SearchWindow(BaseWindow):
    def __init__(self, title="Movie Search"):
        super().__init__(title)
        self.setGeometry(600, 300, 6, 4)
        self.search_results = None
        
        self.setup_ui()
        self.set_navigation()

    def setup_ui(self):
        # Title label
        self.title_label = pyxbmct.Label("Enter your movie search query:", alignment=0)
        self.placeControl(self.title_label, 0, 0, columnspan=4, pad_x=10, pad_y=10)
        
        # Search input field
        self.search_input = pyxbmct.Edit("", "Search for movies...")
        self.placeControl(self.search_input, 1, 0, columnspan=4, pad_x=10, pad_y=5)
        # Disable the default keyboard popup
        try:
            self.search_input.setType(xbmcgui.INPUT_TYPE_TEXT, "Search for movies...")
        except:
            pass
        
        # Example text
        self.example_label = pyxbmct.Label("Example: 'zombie movies from the 80s' or 'romantic comedies with happy endings'", alignment=0)
        self.placeControl(self.example_label, 2, 0, columnspan=4, pad_x=10, pad_y=5)
        
        # Buttons
        self.search_button = pyxbmct.Button("Search")
        self.placeControl(self.search_button, 4, 0, columnspan=2, pad_x=5, pad_y=10)
        
        self.cancel_button = pyxbmct.Button("Cancel")
        self.placeControl(self.cancel_button, 4, 2, columnspan=2, pad_x=5, pad_y=10)
        
        # Connect button actions
        self.connect(self.search_button, self.on_search_click)
        self.connect(self.cancel_button, self.close)

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
        query = self.search_input.getText().strip()
        
        if not query:
            self.show_notification("Please enter a search query", xbmcgui.NOTIFICATION_WARNING)
            return
        
        if len(query) < 3:
            self.show_notification("Search query must be at least 3 characters", xbmcgui.NOTIFICATION_WARNING)
            return
        
        # Close this window and start the progressive search
        self.close()
        self.start_progressive_search(query)

    def start_progressive_search(self, query):
        """Start the progressive search with the given query"""
        try:
            # Show progressive search modal
            progress_window = SearchProgressWindow(query)
            progress_window.doModal()
            
            # Get results from the modal
            self.search_results = progress_window.get_results()
            del progress_window
            
            # Show results summary
            if self.search_results and self.search_results.get('status') == 'success':
                matches = self.search_results.get('matches', [])
                total_time = self.search_results.get('timing', {}).get('total', 0)
                
                if matches:
                    message = f"Found {len(matches)} movies in {total_time:.1f}s"
                    self.show_notification(message, xbmcgui.NOTIFICATION_INFO)
                else:
                    self.show_notification("No movies found matching your search", xbmcgui.NOTIFICATION_INFO)
            else:
                self.show_notification("Search was cancelled or failed", xbmcgui.NOTIFICATION_WARNING)
                
        except Exception as e:
            utils.log(f"Search error: {str(e)}", "ERROR")
            self.show_notification("An error occurred during search", xbmcgui.NOTIFICATION_ERROR)

    def get_search_results(self):
        """Get the search results after the window closes"""
        return self.search_results

    def onAction(self, action):
        """Handle window actions"""
        import xbmcgui
        action_id = action.getId()
        
        # Handle back/escape key
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()
        # Handle enter/select key
        elif action_id in (xbmcgui.ACTION_SELECT_ITEM, xbmcgui.ACTION_MOUSE_LEFT_CLICK):
            # Only trigger search if focus is on search input or search button
            focused_control = self.getFocus()
            if focused_control == self.search_input or focused_control == self.search_button:
                self.on_search_click()
        else:
            super().onAction(action)
