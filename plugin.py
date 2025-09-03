#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Entry Point
Handles plugin URL routing using new modular architecture
"""

import sys

import xbmcaddon
import xbmcgui
import xbmc
import xbmcplugin

# Import new modular components
from lib.ui.plugin_context import PluginContext
from lib.ui.router import Router
from lib.ui.main_menu_handler import MainMenuHandler
from lib.ui.search_handler import SearchHandler
from lib.ui.lists_handler import ListsHandler
from lib.ui.favorites_handler import FavoritesHandler
from lib.utils.logger import get_logger

# Import required functions
from lib.auth.auth_helper import get_auth_helper

# Get logger instance
logger = get_logger(__name__)


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

            # Show notification that initial scan is starting
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                "Initial library scan starting...",
                xbmcgui.NOTIFICATION_INFO,
                5000
            )

            # Run scan in background thread to avoid blocking UI
            import threading

            def run_initial_scan():
                try:
                    result = scanner.perform_full_scan()
                    if result.get("success"):
                        logger.info(f"Initial library scan completed: {result.get('items_added', 0)} movies indexed")
                        # Show completion notification
                        xbmcgui.Dialog().notification(
                            addon.getLocalizedString(35002),  # "LibraryGenie"
                            f"Initial scan complete: {result.get('items_added', 0)} movies indexed",
                            xbmcgui.NOTIFICATION_INFO,
                            5000
                        )
                    else:
                        logger.warning(f"Initial library scan failed: {result.get('error', 'Unknown error')}")
                        # Show error notification
                        xbmcgui.Dialog().notification(
                            addon.getLocalizedString(35002),  # "LibraryGenie"
                            "Initial library scan failed",
                            xbmcgui.NOTIFICATION_ERROR,
                            5000
                        )
                except Exception as e:
                    logger.error(f"Initial library scan thread failed: {e}")
                    # Show error notification
                    xbmcgui.Dialog().notification(
                        addon.getLocalizedString(35002),  # "LibraryGenie"
                        "Initial library scan failed",
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )

            scan_thread = threading.Thread(target=run_initial_scan)
            scan_thread.daemon = True  # Don't block Kodi shutdown
            scan_thread.start()

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to check/trigger initial scan: {e}")


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

        # Build videodb:// path for Kodi library items
        if dbtype == "movie":
            vdb = f'videodb://movies/titles/{dbid}'
        elif dbtype == "episode":
            if isinstance(tvshowid, int) and isinstance(season, int):
                vdb = f'videodb://tvshows/titles/{tvshowid}/{season}/{dbid}'
            else:
                vdb = f'videodb://episodes/{dbid}'
        else:
            vdb = ""
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


def _handle_test_backup(context: PluginContext):
    """Handle backup configuration test from settings"""
    try:
        logger.info("Testing backup configuration from settings")
        
        from lib.import_export import get_timestamp_backup_manager
        backup_manager = get_timestamp_backup_manager()
        
        result = backup_manager.test_backup_configuration()
        
        if result["success"]:
            message = f"Backup test successful:\n{result.get('message', '')}"
            if 'path' in result:
                message += f"\nStorage path: {result['path']}"
            xbmcgui.Dialog().ok("Backup Test", message)
        else:
            error_msg = result.get("error", "Unknown error")
            xbmcgui.Dialog().ok("Backup Test Failed", f"Test failed:\n{error_msg}")
            
    except Exception as e:
        logger.error(f"Error in test backup handler: {e}")
        xbmcgui.Dialog().ok("Backup Test Error", f"Test error: {str(e)}")
    
    # Don't render directory for settings actions
    try:
        if context.addon_handle >= 0:
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
    except Exception:
        pass


def _handle_manual_backup(context: PluginContext):
    """Handle manual backup from settings"""
    try:
        logger.info("Running manual backup from settings")
        
        from lib.import_export import get_timestamp_backup_manager
        backup_manager = get_timestamp_backup_manager()
        
        result = backup_manager.run_manual_backup()
        
        if result["success"]:
            size_mb = round(result.get('file_size', 0) / 1024 / 1024, 2) if result.get('file_size') else 0
            message = (
                f"Manual backup completed successfully!\n\n"
                f"Filename: {result.get('filename', 'Unknown')}\n"
                f"Size: {size_mb} MB\n"
                f"Items: {result.get('total_items', 0)}\n"
                f"Location: {result.get('storage_location', 'Unknown')}"
            )
            xbmcgui.Dialog().ok("Manual Backup", message)
        else:
            error_msg = result.get("error", "Unknown error")
            xbmcgui.Dialog().ok("Manual Backup Failed", f"Backup failed:\n{error_msg}")
            
    except Exception as e:
        logger.error(f"Error in manual backup handler: {e}")
        xbmcgui.Dialog().ok("Manual Backup Error", f"Backup error: {str(e)}")
    
    # Don't render directory for settings actions
    try:
        if context.addon_handle >= 0:
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
    except Exception:
        pass


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
    favorites_handler = FavoritesHandler()

    # Register new modular handlers
    router.register_handler('search', search_handler.prompt_and_search)
    router.register_handler('lists', lists_handler.show_lists_menu)
    router.register_handler('kodi_favorites', favorites_handler.show_favorites_menu)
    
    # Register ListsHandler methods that expect specific parameters
    router.register_handler('create_list_execute', lambda ctx: _handle_dialog_response(ctx, lists_handler.create_list(ctx)))
    router.register_handler('create_folder_execute', lambda ctx: _handle_dialog_response(ctx, lists_handler.create_folder(ctx)))
    
    # Register list and folder view handlers
    router.register_handler('show_list', lambda ctx: lists_handler.view_list(ctx, ctx.get_param('list_id')))
    router.register_handler('show_folder', lambda ctx: lists_handler.show_folder(ctx, ctx.get_param('folder_id')))
    
    # Register parameter-based handlers
    router.register_handler('delete_list', lambda ctx: _handle_dialog_response(ctx, lists_handler.delete_list(ctx, ctx.get_param('list_id'))))
    router.register_handler('rename_list', lambda ctx: _handle_dialog_response(ctx, lists_handler.rename_list(ctx, ctx.get_param('list_id'))))
    router.register_handler('remove_from_list', lambda ctx: _handle_dialog_response(ctx, lists_handler.remove_from_list(ctx, ctx.get_param('list_id'), ctx.get_param('item_id'))))
    
    router.register_handler('rename_folder', lambda ctx: _handle_dialog_response(ctx, lists_handler.rename_folder(ctx, ctx.get_param('folder_id'))))
    router.register_handler('delete_folder', lambda ctx: _handle_dialog_response(ctx, lists_handler.delete_folder(ctx, ctx.get_param('folder_id'))))

    # Register FavoritesHandler methods
    router.register_handler('scan_favorites_execute', lambda ctx: favorites_handler.handle_scan_favorites(ctx))
    router.register_handler('save_favorites_as', lambda ctx: favorites_handler.handle_save_favorites_as(ctx))
    router.register_handler('add_favorite_to_list', lambda ctx: _handle_dialog_response(ctx, favorites_handler.add_favorite_to_list(ctx, ctx.get_param('imdb_id'))))

    # Register remaining handlers
    router.register_handlers({
        'authorize': lambda ctx: handle_authorize(),
        'signout': lambda ctx: handle_signout(),
        'on_select': lambda ctx: handle_on_select(ctx.params, ctx.addon_handle),
        'import_shortlist': lambda ctx: handle_shortlist_import(),
        'test_backup': lambda ctx: _handle_test_backup(ctx),
        'manual_backup': lambda ctx: _handle_manual_backup(ctx),
        'noop': lambda ctx: handle_noop(),
        'settings': lambda ctx: handle_settings(),
    })


def _handle_dialog_response(context: PluginContext, response):
    """Handle DialogResponse objects from handler methods"""
    from lib.ui.response_types import DialogResponse
    from lib.ui.response_handler import get_response_handler
    
    if isinstance(response, DialogResponse):
        response_handler = get_response_handler()
        return response_handler.handle_dialog_response(response, context)
    
    return response


if __name__ == '__main__':
    main()