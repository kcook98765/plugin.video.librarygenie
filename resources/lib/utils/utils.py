import sys
import xbmc
import xbmcgui

def get_addon_handle():
    try:
        return int(sys.argv[1]) if sys.argv[1].isdigit() else -1
    except (IndexError, ValueError):
        return -1  # Use a default value that indicates an invalid handle

def should_log_debug():
    """Check if we should log detailed debug information"""
    try:
        from resources.lib.config.addon_ref import get_addon
        addon = get_addon()
        return addon.getSettingBool('debug_logging') if addon else False
    except:
        return False

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
        addon = None
        try:
            from resources.lib.config.addon_ref import get_addon
            addon = get_addon()
        except (ImportError, AttributeError, Exception):
            pass # If we can't get the setting, default to logging for safety

        if addon:
            debug_enabled = addon.getSetting('debug_logging') == 'true'
            if not debug_enabled:
                return

    # Skip common spam logs
    if isinstance(message, str):
        spam_patterns = [
            "Executing SQL:",
            "DEBUG: JSONRPC response:",
            "JSONRPC VideoLibrary.GetMovies completed",
            "JSONRPC GetMovies success: Got",
            "Executing JSONRPC method:",
            "Inserted into media_items, got ID:",
            "Gathering cast information",
            "Cast member",
            "=== BUILD_DISPLAY_ITEMS: Item",
            "Set imdbnumber for v19 compatibility:",
            "Found matching processed_ref",
            "Lookup keys - exact:",
            "Found 1 candidates, meta exists:",
            "Found Kodi match - title:",
            "=== SIMILARITY_SEARCH: Processing result",
            "=== SIMILARITY_SEARCH: Found title/year for",
            "=== SIMILARITY_SEARCH: Creating media item:",
            "=== SIMILARITY_SEARCH: Successfully added",
            "=== INSERT_MEDIA_ITEM_AND_ADD_TO_LIST:",
            "=== TITLE_YEAR_LOOKUP: Looking up IMDB",
            "=== TITLE_YEAR_LOOKUP: Found in imdb_exports:",
            "=== BUILD_DISPLAY_ITEMS: First returned movie keys:",
            "First movie sample keys:",
            "=== JSONRPC REQUEST: VideoLibrary.GetMovies ===",
            "Request params:",
            "Full request JSON:",
            "=== JSONRPC RESPONSE RAW: VideoLibrary.GetMovies ===",
            "Raw response length:",
            "=== JSONRPC RESPONSE PARSED: VideoLibrary.GetMovies ===",
            "Response result keys:",
            "Set ListItem path for",
            "Setting context for list viewing:",
            "=== BUILD_DISPLAY_ITEMS: Created",
            "display items ===",
            # Batch operation spam patterns
            "=== BATCH RETRIEVAL LOOP ITERATION:",
            "Fetching movies batch:",
            "Making JSON-RPC call to VideoLibrary.GetMovies with params:",
            "Movies returned:",
            "First movie title:",
            "=== JSONRPC SUCCESS: VideoLibrary.GetMovies ===",
            "JSON-RPC response received, checking for movies...",
            "Retrieved",
            "Movie retrieval progress:",
            "Total movies collected so far:",
            "Moving to next batch, new start position:",
            "Processing batch",
            "Beginning database transaction for batch",
            "Processing movie",
            "Inserting",
            "Successfully inserted",
            "Transaction committed for batch",
            "Batch",
            "Released database connection for batch",
            "Progress update:",
            "Processing: Uploading movies",
            # JSON-RPC response analysis spam patterns
            "=== JSON-RPC RESPONSE ANALYSIS",
            "Response keys:",
            "Result keys:",
            "Number of movies in first batch:",
            "=== MOVIE",
            "DETAILED DATA ===",
            "MOVIE_1:",
            "MOVIE_2:",
            "MOVIE_3:",
            "=== END MOVIE",
            "=== END JSON-RPC RESPONSE ANALYSIS ===",
            # Progress and transaction spam patterns
            "Progress tracking:",
            "updating every",
            "items",
            "Processing JSON-RPC batch",
            "=== SIMULTANEOUS STORAGE TRANSACTION:",
            "=== STORING LIGHT METADATA BATCH:",
            "Successfully stored light metadata for",
            "=== STORING HEAVY METADATA BATCH:",
            "Committed heavy metadata transaction:",
            "=== STORING EXPORT DATA BATCH:",
            "Successfully stored export data for",
            "=== TRANSACTION COMPLETED:",
            "records committed atomically",
            "=== JSONRPC TIMING:",
            "executed in",
            "ms ===",
            # Kodi match data spam patterns
            "=== KODI_MATCH_DATA: Item",
            "KODI_MATCH_DATA:",
            "=== END KODI_MATCH_DATA ===",
            "=== LISTITEM_INPUT_DATA: Item",
            "LISTITEM_INPUT_DATA:",
            "=== END LISTITEM_INPUT_DATA ===",
            "=== LISTITEM_BUILDER_INPUT:",
            "LISTITEM_BUILDER_INPUT:",
            "=== END LISTITEM_BUILDER_INPUT ===",
            "Set library file path for search result",
            "Set valid ListItem path for search result",
            # Movie matching spam patterns
            "=== MOVIE_MATCHING: Item",
            "MOVIE_MATCHING:",
            "=== BUILD_DISPLAY_ITEMS: Starting movie matching",
            "=== BUILD_DISPLAY_ITEMS: Indexed",
            "=== MERGED_DATA:",
            "MERGED_DATA:",
            "=== END MERGED_DATA ===",
            "=== HEAVY_CACHE_DATA:",
            "HEAVY_CACHE_DATA:",
            "=== END HEAVY_CACHE_DATA ===",
            "=== SAMPLE FINAL HEAVY METADATA RESULT ===",
            "FINAL_HEAVY:",
            "=== END SAMPLE FINAL HEAVY METADATA ===",
            "=== IMDB_TRACE: Setting ListItem properties",
            "IMDB_TRACE:",
            "=== END IMDB_TRACE:",
            "Successfully added",
            "items (", 
            "playable,",
            "non-playable)"
        ]

        # Allow JSON-RPC request logging to always show through
        if message.startswith("JSONRPC Request"):
            pass  # Don't filter these out
        else:
            for pattern in spam_patterns:
                if message.startswith(pattern) and level in ['DEBUG', 'INFO']:
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
        from resources.lib.config.settings_manager import SettingsManager
        settings_manager = SettingsManager()
        return settings_manager.get_setting('debug_mode', default='false') == 'true'
    except Exception:
        return False

# Global cache for Kodi version to avoid repeated detection
_KODI_VERSION_CACHE = None

# Global cache for initialization logging to prevent spam
_INIT_LOGGED = set()

def get_kodi_version():
    """Get the major version number of the current Kodi installation with caching"""
    global _KODI_VERSION_CACHE

    if _KODI_VERSION_CACHE is not None:
        return _KODI_VERSION_CACHE

    # First run detection - log when version detection is happening for the first time
    log("=== FIRST RUN: Detecting Kodi version for the first time ===", "INFO")
    
    try:
        import xbmc
        version_info = xbmc.getInfoLabel("System.BuildVersion")
        _KODI_VERSION_CACHE = int(version_info.split('.')[0])
        log(f"=== FIRST RUN: Successfully detected and cached Kodi version: {_KODI_VERSION_CACHE} ===", "INFO")
        log(f"Full build version info: {version_info}", "DEBUG")
        return _KODI_VERSION_CACHE
    except Exception as e:
        _KODI_VERSION_CACHE = 21  # Default to latest if detection fails
        log(f"=== FIRST RUN: Could not detect Kodi version, defaulting to v{_KODI_VERSION_CACHE}: {str(e)} ===", "WARNING")
        return _KODI_VERSION_CACHE

def log_once(key, message, level="DEBUG"):
    """Log a message only once per session to prevent spam"""
    global _INIT_LOGGED
    if key not in _INIT_LOGGED:
        log(message, level)
        _INIT_LOGGED.add(key)

def is_kodi_v19():
    """Check if running on Kodi v19 (Matrix)"""
    return get_kodi_version() == 19

def is_kodi_v20_plus():
    """Check if running on Kodi v20 or higher (Nexus+)"""
    return get_kodi_version() >= 20

def is_shield_tv():
    """Check if running on NVIDIA Shield TV"""
    try:
        import xbmc
        # Shield TV typically reports as Android with specific build info
        platform = xbmc.getInfoLabel("System.Platform.Android")
        if platform:
            build_version = xbmc.getInfoLabel("System.BuildVersion")
            return "tegra" in build_version.lower() or "shield" in build_version.lower()
    except:
        pass
    return False

def needs_modal_optimization():
    """Check if device needs modal dialog optimization (slow devices, older Kodi versions)"""
    try:
        import xbmc
        
        # Always optimize for Kodi v19 due to known modal animation issues
        if is_kodi_v19():
            return True
            
        # Optimize for Shield TV (known performance issues)
        if is_shield_tv():
            return True
            
        # Optimize for Android devices in general (often resource-constrained)
        if xbmc.getInfoLabel("System.Platform.Android"):
            return True
            
        # Optimize for ARM-based devices (typically slower)
        cpu_info = xbmc.getInfoLabel("System.CpuUsage")
        platform_arch = xbmc.getInfoLabel("System.BuildVersion")
        if any(arch in platform_arch.lower() for arch in ['arm', 'aarch64']):
            return True
            
        # Default to no optimization for powerful devices
        return False
    except:
        # If detection fails, err on the side of optimization
        return True

def should_log_debug():
    """Check if debug logging should be enabled (reduces overhead on slow devices)"""
    if needs_modal_optimization():
        # Reduce debug logging on devices that need optimization for performance
        return False
    return True

def setup_remote_api():
    """Launch remote API setup wizard"""
    try:
        from resources.lib.integrations.remote_api.remote_api_setup import setup_remote_api
        return setup_remote_api()
    except Exception as e:
        log(f"Error setting up remote API: {str(e)}", "ERROR")
        show_dialog_ok("Setup Error", f"Failed to setup remote API: {str(e)}")
        return False