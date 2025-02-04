
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
        
    level_map = {
        'DEBUG': xbmc.LOGDEBUG,
        'INFO': xbmc.LOGINFO, 
        'WARNING': xbmc.LOGWARNING,
        'ERROR': xbmc.LOGERROR,
        'FATAL': xbmc.LOGFATAL
    }
    xbmc_level = level_map.get(level.upper(), xbmc.LOGDEBUG)
    xbmc.log(f"LibraryGenie: {message}", xbmc_level)
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
