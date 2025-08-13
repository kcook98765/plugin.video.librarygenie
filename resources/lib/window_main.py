import xbmc
import xbmcgui
from resources.lib import utils

utils.log("Initializing MainWindow module", "INFO")

# Legacy MainWindow functionality moved to plugin-based approach
# Use main.py router and context menus instead

def launch_movie_search():
    """Launches the proper SearchWindow for movie search"""
    try:
        from resources.lib.window_search import SearchWindow

        search_window = SearchWindow()
        search_window.doModal()
        results = search_window.get_search_results()
        del search_window
        return results
    except Exception as e:
        utils.log(f"Error in movie search: {str(e)}", "ERROR")
        return {'status': 'error', 'error': str(e)}

# The rest of the original file content that utilized pyxbmct has been removed.