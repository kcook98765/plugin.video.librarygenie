""" /resources/lib/utils.py """
import sys

def get_addon_handle():
    try:
        return int(sys.argv[1]) if sys.argv[1].isdigit() else -1
    except (IndexError, ValueError):
        return -1  # Use a default value that indicates an invalid handle

def log(message, level=None):
    """Unified logging function for LibraryGenie addon.
    Args:
        message: String message to log
        level: LOGDEBUG, LOGINFO, LOGWARNING, LOGERROR, or LOGFATAL
    """
    if level is None:
        level = xbmc.LOGDEBUG
    elif isinstance(level, str):
        level_map = {
            'DEBUG': xbmc.LOGDEBUG,
            'INFO': xbmc.LOGINFO,
            'WARNING': xbmc.LOGWARNING,
            'ERROR': xbmc.LOGERROR,
            'FATAL': xbmc.LOGFATAL
        }
        level = level_map.get(level.upper(), xbmc.LOGDEBUG)
    xbmc.log(f"LibraryGenie: {message}", level)
