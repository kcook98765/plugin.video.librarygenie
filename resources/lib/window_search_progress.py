import pyxbmct
import xbmc
import xbmcgui
import threading
import time
from resources.lib.window_base import BaseWindow
from resources.lib.api_client import ApiClient
from resources.lib import utils

class SearchProgressWindow(BaseWindow):
    def __init__(self, query, title="Search Progress"):
        super().__init__(title)
        self.setGeometry(600, 400, 8, 6)
        self.query = query
        self.search_id = None
        self.final_results = None
        self.is_complete = False
        self.is_cancelled = False
        self.api_client = ApiClient()

        self.setup_ui()
        self.set_navigation()

        # Start the search in a separate thread
        self.search_thread = threading.Thread(target=self.run_progressive_search)
        self.search_thread.daemon = True
        self.search_thread.start()

    def setup_ui(self):
        # Title
        self.title_label = pyxbmct.Label(f"Searching: {self.query}", alignment=0)
        self.placeControl(self.title_label, 0, 0, columnspan=6, pad_x=10, pad_y=5)

        # Progress steps
        self.step1_label = pyxbmct.Label("1. Processing Query...", alignment=0)
        self.placeControl(self.step1_label, 1, 0, columnspan=6, pad_x=20, pad_y=2)

        self.step2_label = pyxbmct.Label("2. Generating Embeddings...", alignment=0) 
        self.placeControl(self.step2_label, 2, 0, columnspan=6, pad_x=20, pad_y=2)

        self.step3_label = pyxbmct.Label("3. Vector Search...", alignment=0)
        self.placeControl(self.step3_label, 3, 0, columnspan=6, pad_x=20, pad_y=2)

        self.step4_label = pyxbmct.Label("4. AI Quality Filter...", alignment=0)
        self.placeControl(self.step4_label, 4, 0, columnspan=6, pad_x=20, pad_y=2)

        # Progress info
        self.progress_label = pyxbmct.Label("Starting search...", alignment=0)
        self.placeControl(self.progress_label, 5, 0, columnspan=6, pad_x=10, pad_y=5)

        # Timing info
        self.timing_label = pyxbmct.Label("", alignment=0)
        self.placeControl(self.timing_label, 6, 0, columnspan=6, pad_x=10, pad_y=2)

        # Cancel button
        self.cancel_button = pyxbmct.Button("Cancel")
        self.placeControl(self.cancel_button, 7, 4, columnspan=2, pad_x=5, pad_y=5)
        self.connect(self.cancel_button, self.cancel_search)
        self.connect(pyxbmct.ACTION_NAV_BACK, self.cancel_search)

    def set_navigation(self):
        self.set_basic_navigation(self.cancel_button)

    def update_step_status(self, step, status="active", time_taken=None):
        """Update the visual status of a step"""
        step_labels = {
            'QUERY_PROCESSING': self.step1_label,
            'EMBEDDING_GENERATION': self.step2_label, 
            'VECTOR_SEARCH': self.step3_label,
            'AI_FILTERING': self.step4_label
        }

        if step in step_labels:
            label = step_labels[step]
            step_num = list(step_labels.keys()).index(step) + 1

            if status == "active":
                text = f"[COLOR yellow]{step_num}. {self.get_step_name(step)}... [ACTIVE][/COLOR]"
            elif status == "complete":
                time_str = f" ({time_taken:.1f}s)" if time_taken else ""
                text = f"[COLOR green]{step_num}. {self.get_step_name(step)}... ✓{time_str}[/COLOR]"
            else:
                text = f"{step_num}. {self.get_step_name(step)}..."

            label.setLabel(text)

    def get_step_name(self, step):
        """Get human-readable step name"""
        names = {
            'QUERY_PROCESSING': 'Processing Query',
            'EMBEDDING_GENERATION': 'Generating Embeddings',
            'VECTOR_SEARCH': 'Vector Search', 
            'AI_FILTERING': 'AI Quality Filter'
        }
        return names.get(step, step)

    def run_progressive_search(self):
        """Run the progressive search and update UI"""
        try:
            # Start the async search
            search_data = self.api_client.start_async_search(self.query)
            if not search_data:
                self.show_error("Failed to start search")
                return

            self.search_id = search_data.get('search_id')
            if not self.search_id:
                self.show_error("No search ID received")
                return

            xbmc.executebuiltin('Notification(LibraryGenie, Search started, 2000)')

            # Poll for progress
            last_step = None
            step_times = {}

            while not self.is_cancelled:
                time.sleep(0.5)  # Poll every 500ms

                progress = self.api_client.get_search_progress(self.search_id)
                if not progress:
                    self.show_error("Failed to get progress")
                    break

                status = progress.get('status')
                current_step = progress.get('current_step')
                progress_data = progress.get('progress_data', {})

                # Update step visualization
                if current_step != last_step and current_step:
                    if last_step:
                        # Mark previous step as complete
                        time_taken = self.get_step_time(progress_data, last_step)
                        self.update_step_status(last_step, "complete", time_taken)

                    # Mark current step as active
                    self.update_step_status(current_step, "active")
                    last_step = current_step

                # Update progress text
                self.update_progress_text(current_step, progress_data)

                # Check if completed
                if status == 'COMPLETED':
                    # Mark final step as complete
                    if current_step:
                        time_taken = self.get_step_time(progress_data, current_step)
                        self.update_step_status(current_step, "complete", time_taken)

                    # Show final results
                    results = progress_data.get('results', [])
                    total_time = progress_data.get('total_time', 0)

                    self.progress_label.setLabel(f"[COLOR green]Search completed! Found {len(results)} movies[/COLOR]")
                    self.timing_label.setLabel(f"Total time: {total_time:.1f}s")

                    # Store results and embedding
                    self.final_results = {
                        'matches': results,
                        'query_embedding': progress_data.get('query_embedding'),
                        'search_id': self.search_id,
                        'timing': step_times,
                        'status': 'success'
                    }

                    self.is_complete = True

                    # Auto-close after 2 seconds
                    xbmc.executebuiltin('Notification(LibraryGenie, Search complete! Closing..., 2000)')
                    time.sleep(2)
                    self.close_search()
                    break

                elif status == 'FAILED':
                    error_msg = progress.get('error_message', 'Unknown error')
                    self.show_error(f"Search failed: {error_msg}")
                    break

        except Exception as e:
            utils.log(f"Search progress error: {str(e)}", "ERROR")
            self.show_error(f"Search error: {str(e)}")

    def get_step_time(self, progress_data, step):
        """Extract timing for a specific step"""
        time_keys = {
            'QUERY_PROCESSING': 'query_parsing_time',
            'EMBEDDING_GENERATION': 'embedding_time', 
            'VECTOR_SEARCH': 'milvus_search_time',
            'AI_FILTERING': 'post_filter_time'
        }
        return progress_data.get(time_keys.get(step, ''), 0)

    def update_progress_text(self, current_step, progress_data):
        """Update the progress description"""
        if current_step == 'QUERY_PROCESSING':
            self.progress_label.setLabel("Processing and expanding search query...")
        elif current_step == 'EMBEDDING_GENERATION':
            query_time = progress_data.get('query_parsing_time', 0)
            if query_time > 0:
                expanded = progress_data.get('expanded_query', '')
                if expanded and expanded != self.query:
                    self.progress_label.setLabel(f"Query expanded. Converting to embeddings...")
                else:
                    self.progress_label.setLabel(f"Using original query. Converting to embeddings...")
        elif current_step == 'VECTOR_SEARCH':
            self.progress_label.setLabel("Searching vector database for similar movies...")
        elif current_step == 'AI_FILTERING':
            movie_count = progress_data.get('user_filtered_results', progress_data.get('results_found', 0))
            self.progress_label.setLabel(f"AI analyzing {movie_count} movies for relevance...")

    def show_error(self, message):
        """Show error and close"""
        self.progress_label.setLabel(f"[COLOR red]Error: {message}[/COLOR]")
        self.cancel_button.setLabel("Close")
        time.sleep(3)
        self.close_search()

    def cancel_search(self):
        """Cancel the search and close"""
        self.is_cancelled = True
        self.close_search()

    def close_search(self):
        """Close the search window"""
        try:
            self.close()
        except:
            pass

    def get_results(self):
        """Get the final search results"""
        return self.final_results if self.is_complete else None

    def onAction(self, action):
        """Handle window actions"""
        action_id = action.getId()

        # Handle back/escape key
        if action_id in (pyxbmct.ACTION_NAV_BACK, pyxbmct.ACTION_PREVIOUS_MENU):
            self.cancel_search()
        # Handle enter/select key (action IDs 7 and 100)
        elif action_id in (7, 100):
            # Close the search when Enter is pressed
            self.close_search()
        else:
            super().onAction(action)

    def start_search(self):
        """Start the progressive search"""
        utils.log(f"SearchProgressWindow: Starting search for query: '{self.query}'", "DEBUG")
        self.search_complete = False
        self.search_cancelled = False

        try:
            from resources.lib.api_client import ApiClient
            utils.log("SearchProgressWindow: Creating ApiClient instance", "DEBUG")
            self.api_client = ApiClient()

            # Start async search
            utils.log("SearchProgressWindow: Calling start_async_search", "DEBUG")
            result = self.api_client.start_async_search(self.query)
            utils.log(f"SearchProgressWindow: start_async_search result: {result}", "DEBUG")

            if not result:
                utils.log("SearchProgressWindow: start_async_search returned None, showing error", "ERROR")
                self.show_error("Failed to start search")
                return
        except Exception as e:
            utils.log(f"SearchProgressWindow: Error in start_search: {str(e)}", "ERROR")
            self.show_error(f"Search error: {str(e)}")