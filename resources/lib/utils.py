
""" /resources/lib/utils.py """
import sys
import xbmc

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
    
    # Truncate cast information in logs
    if isinstance(message, str):
        import re
        message = re.sub(r'"cast":\s*\[[^\]]+\]', '"cast": "[TRUNCATED]"', message)
    
    # Always use INFO level but include original level in message
    xbmc.log(f"LibraryGenie [{level}]: {message}", xbmc.LOGINFO)
import xbmcgui

def show_notification(heading, message, icon=xbmcgui.NOTIFICATION_INFO, time=5000):
    """Centralized notification display"""
    xbmcgui.Dialog().notification(heading, message, icon, time)

def show_dialog_ok(heading, message):
    """Centralized OK dialog"""
    xbmcgui.Dialog().ok(heading, message)

def show_dialog_yesno(heading, message):
    """Centralized Yes/No dialog"""
    return xbmcgui.Dialog().yesno(heading, message)

def show_dialog_input(heading, default=""):
    """Centralized input dialog"""
    return xbmcgui.Dialog().input(heading, defaultt=default).strip()
