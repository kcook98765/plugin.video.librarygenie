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

    # Check debug logging setting for DEBUG and INFO messages
    if level in ['DEBUG', 'INFO']:
        try:
            from .addon_ref import get_addon
            addon = get_addon()
            debug_enabled = addon.getSetting('debug_logging') == 'true'
            if not debug_enabled:
                return
        except:
            # If we can't get the setting, default to logging for safety
            pass

    # Skip common spam logs
    if isinstance(message, str):
        spam_patterns = [
            "Executing SQL:",
            "DEBUG: JSONRPC request:",
            "DEBUG: JSONRPC response:",
            "JSONRPC VideoLibrary.GetMovies completed",
            "JSONRPC GetMovies success: Got",
            "Executing JSONRPC method:",
            "Inserted into media_items, got ID:"
        ]
        
        for pattern in spam_patterns:
            if message.startswith(pattern) and level == 'DEBUG':
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

def show_dialog_ok(heading, message):
    """Centralized OK dialog"""
    xbmcgui.Dialog().ok(heading, message)

def show_dialog_yesno(heading, message):
    """Centralized Yes/No dialog"""
    return xbmcgui.Dialog().yesno(heading, message)

def show_dialog_input(heading, default=""):
    """Centralized input dialog"""
    return xbmcgui.Dialog().input(heading, default).strip()

def is_debug_enabled():
    """Check if debug logging is enabled in addon settings"""
    try:
        from .addon_ref import get_addon
        return get_addon().getSetting('debug_logging') == 'true'
    except Exception:
        return True

def setup_remote_api():
    """Launch remote API setup wizard"""
    try:
        from resources.lib.remote_api_setup import setup_remote_api
        return setup_remote_api()
    except Exception as e:
        log(f"Error setting up remote API: {str(e)}", "ERROR")
        show_dialog_ok("Setup Error", f"Failed to setup remote API: {str(e)}")
        return False