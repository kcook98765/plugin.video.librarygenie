""" /resources/lib/window_results.py """
import pyxbmct
import xbmc
from resources.lib import utils
import xbmcgui
import json
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.llm_api_manager import LLMApiManager

class ResultsWindow(pyxbmct.AddonDialogWindow):
    INDENTATION_MULTIPLIER = 3  # Set the indentation multiplier

    def __init__(self, rpc=None, name='', list_id=None, movies=None):
        super(ResultsWindow, self).__init__()
        self.rpc = rpc if rpc is not None else {}
        self.name = name
        self.list_id = list_id
        self.movies = movies or []
        self.ok_button = None
        self.cancel_button = None
        self.db_manager = DatabaseManager(Config().db_path)
        self.jsonrpc = JSONRPC()  # Initialize JSONRPC
        self.llm_api_manager = LLMApiManager()  # Initialize LLMApiManager

        self.setGeometry(1280, 720, 12, 4)
        self.set_info_controls()
        self.set_navigation()

        self.connect(self.ok_button, self.on_ok)
        self.connect(self.cancel_button, self.on_cancel)

        if not rpc:
            self.perform_initial_query()

    def perform_initial_query(self):
        try:
            description = "Description for the GenieList"  # Replace with actual description if available
            rpc, name, movies = self.llm_api_manager.generate_query(description)
            self.rpc = rpc
            self.name = name

            # Store the original request and response
            response_json = json.dumps({'rpc': rpc, 'name': name, 'movies': movies})
            request_id = self.db_manager.insert_original_request(description, response_json)

            # Store the parsed movie details and check for matches
            matched_movies = []
            for movie in movies:
                title = movie.get('title', 'Unknown Title')
                year = movie.get('year', 0)
                director = movie.get('director', 'Unknown Director')
                self.db_manager.insert_parsed_movie(request_id, title, year, director)

                # Check for matches via JSON-RPC lookup
                search_results = self.search_movie_by_criteria(title, year, director)
                matched = bool(search_results)
                matched_movies.append({'title': title, 'year': year, 'director': director, 'matched': matched})

            self.movies = matched_movies
            self.populate_movies_list()

        except Exception as e:
            utils.log(f"Error running LLM request: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification("ListGenius", "Error running LLM request", xbmcgui.NOTIFICATION_ERROR, 5000)


    def search_movies(self, movie_list):
        results = []
        for movie in movie_list:
            title = movie.get('title')
            year = movie.get('year')
            director = movie.get('director')

            search_results = self.search_movie_by_criteria(title, year, director)
            if search_results:
                results.extend(search_results)

        return results

     def search_movie_by_criteria(self, title, year, director):
        query = self.build_combined_query(title, year, director)
        result = self.jsonrpc.execute("VideoLibrary.GetMovies", query)
        movies = result.get('result', {}).get('movies', [])
        return movies

    def build_combined_query(self, title, year, director):
        return {
            "filter": {
                "or": [
                    {
                        "and": [
                            {"field": "title", "operator": "is", "value": title},
                            {
                                "or": [
                                    {"field": "year", "operator": "greaterthan", "value": year - 2},
                                    {"field": "year", "operator": "lessthan", "value": year + 2}
                                ]
                            }
                        ]
                    },
                    {
                        "and": [
                            {"field": "director", "operator": "is", "value": director},
                            {
                                "or": [
                                    {"field": "year", "operator": "greaterthan", "value": year - 2},
                                    {"field": "year", "operator": "lessthan", "value": year + 2}
                                ]
                            }
                        ]
                    }
                ]
            },
            "properties": [
                "title", "year", "director", "genre", "rating", "thumbnail", "fanart"
            ]
        }

    def on_ok(self):
        utils.log("OK button clicked", xbmc.LOGDEBUG)
        if self.list_id is not None:
            try:
                matched_movies = [movie for movie in self.movies if movie.get('matched', False)]
                db_manager = DatabaseManager(Config().db_path)

                for movie in matched_movies:
                    # Create data dictionary to match database schema
                    data = {
                        'title': movie.get('title', 'Unknown Title'),
                        'year': movie.get('year', 0),
                        'director': movie.get('director', 'Unknown Director'),
                        'list_id': self.list_id
                    }

                    # Insert matched movie into the list
                    db_manager.insert_data('list_items', data)

                xbmcgui.Dialog().notification("ListGenius", f"{len(matched_movies)} movies added to the list", xbmcgui.NOTIFICATION_INFO, 5000)
            except Exception as e:
                utils.log(f"Error adding matched movies to list: {str(e)}", "ERROR")
                xbmcgui.Dialog().notification("ListGenius", "Error adding matched movies to list", xbmcgui.NOTIFICATION_ERROR, 5000)
        else:
            utils.log("No list_id provided, cannot add matched movies", "ERROR")
        self.close()

    def set_info_controls(self):
        self.movies_list_control = pyxbmct.List('font13')
        self.placeControl(self.movies_list_control, 0, 0, 10, 4)

        self.ok_button = pyxbmct.Button('OK')
        self.placeControl(self.ok_button, 10, 1)
        self.cancel_button = pyxbmct.Button('Cancel')
        self.placeControl(self.cancel_button, 10, 2)

        self.populate_movies_list()

    def populate_movies_list(self):
        self.movies_list_control.reset()
        if self.movies:
            for movie in self.movies:
                title = movie.get('title', 'Unknown Title')
                year = movie.get('year', 'Unknown Year')
                director = movie.get('director', 'Unknown Director')
                matched = movie.get('matched', False)
                match_status = "Matched" if matched else "No Match"
                self.movies_list_control.addItem(f"{title} ({year}) - Directed by {director} [{match_status}]")
        else:
            self.movies_list_control.addItem("No matches found")

    def set_navigation(self):
        self.ok_button.controlRight(self.cancel_button)
        self.ok_button.controlUp(self.movies_list_control)
        self.cancel_button.controlLeft(self.ok_button)
        self.cancel_button.controlUp(self.movies_list_control)
        self.movies_list_control.controlDown(self.ok_button)
        self.movies_list_control.controlUp(self.cancel_button)
        self.setFocus(self.movies_list_control)

    def on_cancel(self):
        utils.log("Cancel button clicked")
        self.close()