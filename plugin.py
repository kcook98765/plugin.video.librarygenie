#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Entry Point
Handles plugin URL routing using new modular architecture
"""

import sys
from urllib.parse import parse_qsl

import xbmcaddon
import xbmcgui
import xbmc

# Import new modular components
from lib.ui.plugin_context import PluginContext
from lib.ui.router import Router
from lib.ui.main_menu_handler import MainMenuHandler
from lib.ui.search_handler import SearchHandler
from lib.ui.lists_handler import ListsHandler
from lib.utils.logger import get_logger

# Import required functions
from lib.auth.auth_helper import get_auth_helper
from lib.data.query_manager import get_query_manager

# Get logger instance
logger = get_logger(__name__)


# Legacy handlers removed - functionality now handled by modular handlers


def handle_authorize():
    """Handle device authorization"""
    auth_helper = get_auth_helper()
    auth_helper.start_device_authorization()


def handle_signout():
    """Handle user sign out"""
    from lib.auth.state import clear_tokens

    addon = xbmcaddon.Addon()

    # Confirm sign out
    if xbmcgui.Dialog().yesno(
        addon.getLocalizedString(35002),  # "LibraryGenie"
        addon.getLocalizedString(35029),  # "Sign out"
        addon.getLocalizedString(35030)   # "Are you sure you want to sign out?"
    ):
        if clear_tokens():
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35031),  # "Signed out successfully"
                xbmcgui.NOTIFICATION_INFO
            )
        else:
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35032),  # "Sign out failed"
                xbmcgui.NOTIFICATION_ERROR
            )


def _check_and_trigger_initial_scan():
    """Check if library needs initial scan and trigger if needed"""
    try:
        from lib.library.scanner import get_library_scanner
        from lib.data.migrations import get_migration_manager

        logger = get_logger(__name__)

        # Ensure database is initialized first
        migration_manager = get_migration_manager()
        migration_manager.ensure_initialized()

        # Check if library needs indexing
        scanner = get_library_scanner()
        if not scanner.is_library_indexed():
            logger.info("Library not indexed - triggering initial scan")

            # Run scan in background thread to avoid blocking UI
            import threading

            def run_initial_scan():
                try:
                    result = scanner.perform_full_scan()
                    if result.get("success"):
                        logger.info(f"Initial library scan completed: {result.get('items_added', 0)} movies indexed")
                    else:
                        logger.warning(f"Initial library scan failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Initial library scan thread failed: {e}")

            scan_thread = threading.Thread(target=run_initial_scan)
            scan_thread.daemon = True  # Don't block Kodi shutdown
            scan_thread.start()

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to check/trigger initial scan: {e}")


# Legacy handlers removed - functionality now handled by modular handlers




















def _videodb_path(dbtype: str, dbid: int, tvshowid=None, season=None) -> str:
    """Build videodb:// path for Kodi library items"""
    if dbtype == "movie":
        return f'videodb://movies/titles/{dbid}'
    if dbtype == "episode":
        if isinstance(tvshowid, int) and isinstance(season, int):
            return f'videodb://tvshows/titles/{tvshowid}/{season}/{dbid}'
        return f'videodb://episodes/{dbid}'
    return ""


def handle_on_select(params: dict, addon_handle: int):
    """Handle library item selection - play or show info based on user preference"""
    try:
        from lib.config.config_manager import get_select_pref
        import re

        logger.debug(f"=== ON_SELECT HANDLER CALLED ===")
        logger.debug(f"Handling on_select with params: {params}")
        logger.debug(f"Addon handle: {addon_handle}")

        dbtype = params.get("dbtype", "movie")
        dbid = int(params.get("dbid", "0"))
        tvshowid = params.get("tvshowid")
        season = params.get("season")
        tvshowid = int(tvshowid) if tvshowid and str(tvshowid).isdigit() else None
        season = int(season) if season and str(season).isdigit() else None

        vdb = _videodb_path(dbtype, dbid, tvshowid, season)  # must be a videodb:// path
        pref = get_select_pref()  # 'play' or 'info'

        # Parse major Kodi version (19, 20, 21, ...)
        ver_str = xbmc.getInfoLabel('System.BuildVersion')
        try:
            kodi_major = int(re.split(r'[^0-9]', ver_str, 1)[0])
        except Exception:
            kodi_major = 0

        logger.debug(f"on_select: dbtype={dbtype}, dbid={dbid}, videodb_path={vdb}, preference={pref}, kodi_major={kodi_major}")

        if pref == "play":
            logger.info(f"Playing media: {vdb}")
            xbmc.executebuiltin(f'PlayMedia("{vdb}")')
        else:
            if kodi_major <= 19:
                logger.info("Opening DialogVideoInfo for videodb item (Matrix)")
                xbmc.executebuiltin(f'ActivateWindow(DialogVideoInfo,"{vdb}",return)')
            else:
                logger.debug("Opening info dialog for focused item (Nexus+)")
                xbmc.executebuiltin('Action(Info)')
                # Optionally force DB context on v20+:
                # xbmc.executebuiltin(f'ActivateWindow(VideoInformation,"{vdb}",return)')

        # Don’t render a directory for this action
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error in handle_on_select: {e}")
        import traceback
        logger.error(f"on_select error traceback: {traceback.format_exc()}")
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass


# Legacy handle_lists and handle_kodi_favorites functions removed
# Functionality moved to ListsHandler class


# Legacy favorites handlers removed - functionality moved to FavoritesHandler class


def handle_settings():
    """Handle settings menu"""
    logger.info("Opening addon settings")
    xbmcaddon.Addon().openSettings()


def _format_time_ago(timestamp_str):
    """Format timestamp as human readable 'time ago' string"""
    if not timestamp_str:
        return "never"

    try:
        from datetime import datetime, timezone

        # Parse the timestamp - handle both Z suffix and +00:00 formats
        if timestamp_str.endswith('Z'):
            normalized_timestamp = timestamp_str.replace('Z', '+00:00')
        elif '+' not in timestamp_str and timestamp_str.count(':') >= 2:
            normalized_timestamp = timestamp_str + '+00:00'
        else:
            normalized_timestamp = timestamp_str

        scan_time = datetime.fromisoformat(normalized_timestamp)

        if scan_time.tzinfo is None:
            scan_time = scan_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        diff = now - scan_time
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            return "just now"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = total_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"

    except Exception as e:
        logger.debug(f"Error formatting timestamp '{timestamp_str}': {e}")
        return "unknown"


def handle_shortlist_import():
    """Handle ShortList import action from settings"""
    import xbmcgui
    from lib.import_export.shortlist_importer import get_shortlist_importer

    try:
        # Show confirmation dialog
        dialog = xbmcgui.Dialog()
        if not dialog.yesno(
            "ShortList Import",
            "This will import all items from ShortList addon into a 'ShortList Import' list.",
            "Only items that match movies in your Kodi library will be imported.",
            "Continue?"
        ):
            return

        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("ShortList Import", "Checking ShortList addon...")
        progress.update(10)

        importer = get_shortlist_importer()

        # Check if ShortList is available
        if not importer.is_shortlist_installed():
            progress.close()
            dialog.notification(
                "LibraryGenie",
                "ShortList addon not found or not enabled",
                xbmcgui.NOTIFICATION_WARNING,
                5000
            )
            return

        progress.update(30, "Scanning ShortList data...")

        # Perform the import
        result = importer.import_shortlist_items()

        progress.update(100, "Import complete!")
        progress.close()

        if result.get("success"):
            message = (
                f"Import completed!\n"
                f"Processed: {result.get('total_items', 0)} items\n"
                f"Added to list: {result.get('items_added', 0)} movies\n"
                f"Unmapped: {result.get('items_unmapped', 0)} items"
            )
            dialog.ok("ShortList Import", message)
        else:
            error_msg = result.get("error", "Unknown error occurred")
            dialog.ok("ShortList Import", f"Import failed: {error_msg}")

    except Exception as e:
        logger.error(f"ShortList import handler error: {e}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Import failed with error",
            xbmcgui.NOTIFICATION_ERROR,
            5000
        )


def handle_noop():
    """No-op handler that safely ends the directory without args mismatches"""
    try:
        addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        if addon_handle >= 0:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
    except Exception:
        pass


def main():
    """Main plugin entry point using new modular architecture"""

    logger.debug(f"=== PLUGIN INVOCATION (REFACTORED) ===")
    logger.debug(f"Full sys.argv: {sys.argv}")
    logger.debug(f"Using modular handler architecture")

    try:
        # Create plugin context from request
        context = PluginContext()

        # Log window state for debugging
        _log_window_state(context)

        # Check if this is first run and trigger library scan if needed
        _check_and_trigger_initial_scan()

        # Set up legacy global variables for backward compatibility
        global args, base_url
        args = context.params
        base_url = context.base_url

        # Create router and register handlers
        router = Router()
        _register_all_handlers(router)

        # Try to dispatch the request
        if not router.dispatch(context):
            # No handler found, show main menu
            main_menu_handler = MainMenuHandler()
            main_menu_handler.show_main_menu(context)

    except Exception as e:
        logger.error(f"Fatal error in plugin main: {e}")
        import traceback
        logger.error(f"Main error traceback: {traceback.format_exc()}")

        # Try to show error to user if possible
        try:
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35013),
                xbmcgui.NOTIFICATION_ERROR
            )
        except Exception:
            pass


def _log_window_state(context: PluginContext):
    """Log window state for debugging"""
    try:
        current_window = xbmc.getInfoLabel("System.CurrentWindow")
        current_control = xbmc.getInfoLabel("System.CurrentControl")
        container_path = xbmc.getInfoLabel("Container.FolderPath")
        container_label = xbmc.getInfoLabel("Container.FolderName")

        context.logger.debug(f"Window state at plugin entry:")
        context.logger.debug(f"  Current window: {current_window}")
        context.logger.debug(f"  Current control: {current_control}")
        context.logger.debug(f"  Container path: {container_path}")
        context.logger.debug(f"  Container label: {container_label}")

        # Check specific window visibility states
        myvideo_nav_visible = xbmc.getCondVisibility("Window.IsVisible(MyVideoNav.xml)")
        dialog_video_info_visible = xbmc.getCondVisibility("Window.IsVisible(DialogVideoInfo.xml)")
        dialog_video_info_active = xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)")
        keyboard_visible = xbmc.getCondVisibility("Window.IsVisible(DialogKeyboard.xml)")

        context.logger.debug(f"  MyVideoNav.xml visible: {myvideo_nav_visible}")
        context.logger.debug(f"  DialogVideoInfo.xml visible: {dialog_video_info_visible}")
        context.logger.debug(f"  DialogVideoInfo.xml active: {dialog_video_info_active}")
        context.logger.debug(f"  DialogKeyboard.xml visible: {keyboard_visible}")

    except Exception as e:
        context.logger.warning(f"Failed to log window state at plugin entry: {e}")


def _register_all_handlers(router: Router):
    """Register all action handlers with the router"""

    # Create handler instances
    main_menu_handler = MainMenuHandler()
    search_handler = SearchHandler()
    lists_handler = ListsHandler()

    # Register new modular handlers
    router.register_handler('search', search_handler.prompt_and_search)
    router.register_handler('lists', lists_handler.show_lists_menu)
    
    # Register ListsHandler methods that expect specific parameters
    router.register_handler('create_list_execute', lambda ctx: _handle_dialog_response(ctx, lists_handler.create_list(ctx)))
    router.register_handler('create_folder_execute', lambda ctx: _handle_dialog_response(ctx, lists_handler.create_folder(ctx)))
    
    # Register parameter-based handlers
    router.register_handler('delete_list', lambda ctx: _handle_dialog_response(ctx, lists_handler.delete_list(ctx, ctx.get_param('list_id'))))
    router.register_handler('rename_list', lambda ctx: _handle_dialog_response(ctx, lists_handler.rename_list(ctx, ctx.get_param('list_id'))))
    router.register_handler('remove_from_list', lambda ctx: _handle_dialog_response(ctx, lists_handler.remove_from_list(ctx, ctx.get_param('list_id'), ctx.get_param('item_id'))))
    
    router.register_handler('rename_folder', lambda ctx: _handle_dialog_response(ctx, lists_handler.rename_folder(ctx, ctx.get_param('folder_id'))))
    router.register_handler('delete_folder', lambda ctx: _handle_dialog_response(ctx, lists_handler.delete_folder(ctx, ctx.get_param('folder_id'))))

    # Register legacy handlers with context wrapper
    router.register_handlers({
        'authorize': _wrap_legacy_handler(handle_authorize),
        'signout': _wrap_legacy_handler(handle_signout),
        'on_select': _wrap_legacy_on_select_handler(handle_on_select),
        'import_shortlist': _wrap_legacy_handler(handle_shortlist_import),
        'noop': _wrap_legacy_handler(handle_noop),
    })


def _wrap_legacy_handler(handler_func):
    """Wrap legacy handler functions to work with PluginContext"""
    def wrapper(context: PluginContext):
        # Set legacy globals for compatibility
        global args, base_url
        args = context.params
        base_url = context.base_url

        # Call legacy handler
        return handler_func()
    return wrapper


def _wrap_legacy_on_select_handler(handler_func):
    """Special wrapper for on_select handler"""
    def wrapper(context: PluginContext):
        return handler_func(context.params, context.addon_handle)
    return wrapper


def _handle_dialog_response(context: PluginContext, response):
    """Handle DialogResponse objects from handler methods"""
    from lib.ui.response_types import DialogResponse
    
    if isinstance(response, DialogResponse):
        # Show notification if there's a message
        response.show_notification(context.addon)
        
        # Refresh if needed
        if response.refresh_needed:
            import xbmc
            xbmc.executebuiltin('Container.Refresh')
    
    return response


if __name__ == '__main__':
    main()