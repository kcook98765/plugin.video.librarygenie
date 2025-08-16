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
            "DEBUG: JSONRPC response:",
            "JSONRPC VideoLibrary.GetMovies completed",
            "JSONRPC GetMovies success: Got",
            "Executing JSONRPC method:",
            "Inserted into media_items, got ID:"
        ]

        # Allow JSON-RPC request logging to always show through
        if message.startswith("JSONRPC Request"):
            pass  # Don't filter these out
        else:
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
    """Check if debug logging is enabled for the addon"""
    try:
        from .addon_ref import get_addon
        settings_manager = SettingsManager()
        return settings_manager.get_bool_setting('debug_mode', default=False)
    except Exception:
        return False

# Global cache for Kodi version to avoid repeated detection
_KODI_VERSION_CACHE = None

def get_kodi_version():
    """Get the major version number of the current Kodi installation with caching"""
    global _KODI_VERSION_CACHE

    if _KODI_VERSION_CACHE is not None:
        return _KODI_VERSION_CACHE

    try:
        import xbmc
        version_info = xbmc.getInfoLabel("System.BuildVersion")
        _KODI_VERSION_CACHE = int(version_info.split('.')[0])
        log(f"Detected and cached Kodi version: {_KODI_VERSION_CACHE}", "INFO")
        return _KODI_VERSION_CACHE
    except Exception as e:
        _KODI_VERSION_CACHE = 21  # Default to latest if detection fails
        log(f"Could not detect Kodi version, defaulting to v{_KODI_VERSION_CACHE}: {str(e)}", "WARNING")
        return _KODI_VERSION_CACHE

def is_kodi_v19():
    """Check if running on Kodi v19 (Matrix)"""
    return get_kodi_version() == 19

def is_kodi_v20_plus():
    """Check if running on Kodi v20 or higher (Nexus+)"""
    return get_kodi_version() >= 20

def setup_remote_api():
    """Launch remote API setup wizard"""
    try:
        from resources.lib.remote_api_setup import setup_remote_api
        return setup_remote_api()
    except Exception as e:
        log(f"Error setting up remote API: {str(e)}", "ERROR")
        show_dialog_ok("Setup Error", f"Failed to setup remote API: {str(e)}")
        return False