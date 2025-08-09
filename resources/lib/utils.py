import sys
import xbmc
import xbmcgui

def get_addon_handle():
    try:
        return int(sys.argv[1]) if sys.argv[1].isdigit() else -1
    except (IndexError, ValueError):
        return -1  # Use a default value that indicates an invalid handle

def log(message, level=None):
    """Unified logging function for LibraryGenie addon.
    Args:
        message: String message to log
        level: 'DEBUG', 'INFO', 'WARNING', 'ERROR', or 'FATAL'
    """
    if level is None:
        level = 'DEBUG'

    # Skip SQL execution logs
    if isinstance(message, str) and message.startswith("Executing SQL:"):
        return

    # Truncate cast data in JSON responses
    if isinstance(message, str):
        import re
        # Handle standard JSON cast array
        message = re.sub(r'("cast":\s*\[)[^\]]*(\])', r'\1...\2', message)
        # Handle Python dict representation of cast
        message = re.sub(r"('cast':\s*\[)[^\]]*(\])", r'\1...\2', message)
        # Handle nested cast arrays
        message = re.sub(r'("cast":\s*\[[^\[\]]*\[)[^\]]*(\][^\[\]]*\])', r'\1...\2', message)

    # Always use INFO level but include original level in message
    xbmc.log(f"LibraryGenie [{level}]: {message}", xbmc.LOGINFO)


def show_notification(title, message, icon=xbmcgui.NOTIFICATION_INFO, time=5000):
    xbmcgui.Dialog().notification(title, message, icon, time)

def launch_movie_search():
    """Launch the movie search GUI and return results"""
    log("Utils: Starting launch_movie_search", "DEBUG")
    try:
        log("Utils: Importing SearchWindow", "DEBUG")
        from resources.lib.window_search import SearchWindow

        log("Utils: Creating SearchWindow instance", "DEBUG")
        search_window = SearchWindow()
        log("Utils: Showing SearchWindow modal", "DEBUG")
        search_window.doModal()

        # Get results if any
        log("Utils: Getting search results", "DEBUG")
        results = search_window.get_search_results()
        log(f"Utils: Search results obtained: {results}", "DEBUG")
        del search_window

        return results
    except Exception as e:
        log(f"Error launching search window: {str(e)}", "ERROR")
        import traceback
        log(f"Error traceback: {traceback.format_exc()}", "ERROR")
        return None

def show_dialog_ok(heading, message):
    """Centralized OK dialog"""
    xbmcgui.Dialog().ok(heading, message)

def show_dialog_yesno(heading, message):
    """Centralized Yes/No dialog"""
    return xbmcgui.Dialog().yesno(heading, message)

def show_dialog_input(heading, default=""):
    """Centralized input dialog"""
    return xbmcgui.Dialog().input(heading, defaultt=default).strip()

def setup_remote_api():
    """Launch remote API setup wizard"""
    try:
        from resources.lib.remote_api_setup import setup_remote_api
        return setup_remote_api()
    except Exception as e:
        log(f"Error setting up remote API: {str(e)}", "ERROR")
        show_dialog_ok("Setup Error", f"Failed to setup remote API: {str(e)}")
        return False