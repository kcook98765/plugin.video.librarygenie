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
from lib.ui.handler_factory import get_handler_factory
from lib.utils.kodi_log import log, log_info, log_error, log_warning

# Import required functions
from lib.auth.auth_helper import get_auth_helper

# Using direct Kodi logging via lib.utils.kodi_log


def handle_authorize():
    """Handle device authorization"""
    auth_helper = get_auth_helper()
    auth_helper.start_device_authorization()


def handle_signout():
    """Handle user sign out"""
    from lib.auth.state import clear_tokens

    addon = xbmcaddon.Addon()

    from lib.ui.localization import L

    # Confirm sign out
    dialog = xbmcgui.Dialog()
    if dialog.yesno(
        heading=L(35002),  # "LibraryGenie"
        line1=L(35029),    # "Sign out"
        line2=L(35030),    # "Are you sure you want to sign out?"
        line3="",
        nolabel=L(36003),  # "Cancel"
        yeslabel=L(35029)  # "Sign out"
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





def handle_on_select(params: dict, addon_handle: int):
    """Handle library item selection - play media directly"""
    try:
        import re

        log("=== ON_SELECT HANDLER CALLED ===")
        log(f"Handling on_select with params: {params}")
        log(f"Addon handle: {addon_handle}")

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
        log(f"on_select: dbtype={dbtype}, dbid={dbid}, videodb_path={vdb}")

        # Always play the media directly
        log_info(f"Playing media: {vdb}")
        xbmc.executebuiltin(f'PlayMedia("{vdb}")')

        # Don’t render a directory for this action
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass

    except Exception as e:
        log_error(f"Error in handle_on_select: {e}")
        import traceback
        log_error(f"on_select error traceback: {traceback.format_exc()}")
        try:
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)
        except Exception:
            pass


# Legacy handle_lists and handle_kodi_favorites functions removed
# Functionality moved to ListsHandler class


# Legacy favorites handlers removed - functionality moved to FavoritesHandler class


def handle_settings():
    """Handle settings menu"""
    log_info("Opening addon settings")
    xbmcaddon.Addon().openSettings()


def _handle_test_backup(context: PluginContext):
    """Handle backup configuration test from settings"""
    try:
        log_info("Testing backup configuration from settings")

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
        log_error(f"Error in test backup handler: {e}")
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
        log_info("Running manual backup from settings")

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
        log_error(f"Error in manual backup handler: {e}")
        xbmcgui.Dialog().ok("Manual Backup Error", f"Backup error: {str(e)}")

    # Don't render directory for settings actions
    try:
        if context.addon_handle >= 0:
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
    except Exception:
        pass


def _handle_restore_backup(context: PluginContext):
    """Handle restore backup from settings - delegated to tools handler"""
    try:
        from lib.ui.tools_handler import ToolsHandler
        tools_handler = ToolsHandler()

        # Call the restore backup method from tools handler
        response = tools_handler.restore_backup_from_settings()

        # Handle the response appropriately
        from lib.ui.response_types import DialogResponse
        from lib.ui.response_handler import get_response_handler

        if isinstance(response, DialogResponse):
            response_handler = get_response_handler()
            response_handler.handle_dialog_response(response, context)

    except Exception as e:
        log_error(f"Error in restore backup handler: {e}")
        xbmcgui.Dialog().ok("Restore Backup Error", f"An error occurred: {str(e)}")

    # Don't render directory for settings actions
    try:
        if context.addon_handle >= 0:
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
    except Exception:
        pass


def handle_shortlist_import():
    """Handle ShortList import action from settings"""
    import xbmcgui

    log_info("=== SHORTLIST IMPORT HANDLER CALLED ===")

    try:
        log_info("Starting ShortList import process")

        # Show confirmation dialog
        dialog = xbmcgui.Dialog()

        from lib.ui.localization import L

        log_info("Showing confirmation dialog")
        if not dialog.yesno(
            L(30071),  # "Import from ShortList addon"
            L(37000) + "\n" + L(37001),  # Combined message
            nolabel=L(36003),  # "Cancel"
            yeslabel=L(37002)  # "Continue"
        ):
            log_info("User cancelled ShortList import")
            return

        log_info("User confirmed import, proceeding...")

        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("ShortList Import", "Checking ShortList addon...")
        progress.update(10)

        log_info("Attempting to get ShortList importer instance...")
        try:
            from lib.import_export.shortlist_importer import get_shortlist_importer
            log_info("Successfully imported get_shortlist_importer function")

            importer = get_shortlist_importer()
            log_info(f"Successfully got importer instance: {type(importer)}")

        except Exception as import_e:
            log_error(f"Error importing or getting ShortList importer: {import_e}")
            import traceback
            log_error(f"Import error traceback: {traceback.format_exc()}")
            progress.close()
            dialog.notification(
                "LibraryGenie",
                "Failed to load ShortList importer",
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        # Check if ShortList is available
        log_info("Checking if ShortList addon is installed...")
        try:
            is_installed = importer.is_shortlist_installed()
            log_info(f"ShortList installed check result: {is_installed}")

            if not is_installed:
                progress.close()
                dialog.notification(
                    "LibraryGenie",
                    "ShortList addon not found or not enabled",
                    xbmcgui.NOTIFICATION_WARNING,
                    5000
                )
                return
        except Exception as check_e:
            log_error(f"Error checking ShortList installation: {check_e}")
            import traceback
            log_error(f"Check error traceback: {traceback.format_exc()}")
            progress.close()
            dialog.notification(
                "LibraryGenie",
                "Error checking ShortList addon",
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        progress.update(30, "Scanning ShortList data...")

        log_info("About to call importer.import_shortlist_items()")
        log_info(f"Importer type: {type(importer)}")
        log_info(f"Importer instance: {importer}")

        # Check if the method exists
        if hasattr(importer, 'import_shortlist_items'):
            log_info(f"import_shortlist_items method exists: {importer.import_shortlist_items}")
            log_info(f"import_shortlist_items callable: {callable(importer.import_shortlist_items)}")
        else:
            log_error("import_shortlist_items method does not exist on importer!")
            progress.close()
            dialog.notification(
                "LibraryGenie",
                "ShortList importer missing method",
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return

        # Perform the import
        log_info("=== CALLING IMPORT METHOD ===")
        try:
            log_info("Calling import_shortlist_items method...")
            result = importer.import_shortlist_items()
            log_info("=== IMPORT METHOD COMPLETED ===")
            log_info(f"Import result type: {type(result)}")
            log_info(f"Import result: {result}")
        except TypeError as te:
            log_error("=== IMPORT METHOD TYPEERROR ===")
            log_error(f"TypeError calling import_shortlist_items: {te}")
            import traceback
            log_error(f"TypeError traceback: {traceback.format_exc()}")

            # Try to get more info about the method signature
            import inspect
            try:
                sig = inspect.signature(importer.import_shortlist_items)
                log_error(f"Method signature: {sig}")
            except Exception as sig_e:
                log_error(f"Could not get method signature: {sig_e}")

            raise
        except Exception as e:
            log_error("=== IMPORT METHOD ERROR ===")
            log_error(f"Error calling import_shortlist_items: {e}")
            import traceback
            log_error(f"Import method traceback: {traceback.format_exc()}")
            raise

        progress.update(100, "Import complete!")
        progress.close()

        log_info("Processing import results...")
        if result.get("success"):
            message = (
                f"Import completed!\n"
                f"Processed: {result.get('total_items', 0)} items\n"
                f"Added to list: {result.get('items_added', 0)} movies\n"
                f"Unmapped: {result.get('items_unmapped', 0)} items"
            )
            dialog.ok("ShortList Import", message)
            log_info("ShortList import completed successfully")
        else:
            error_msg = result.get("error", "Unknown error occurred")
            dialog.ok("ShortList Import", f"Import failed: {error_msg}")
            log_error(f"ShortList import failed: {error_msg}")

    except Exception as e:
        log_error("=== SHORTLIST HANDLER EXCEPTION ===")
        log_error(f"ShortList import handler error: {e}")
        import traceback
        log_error(f"Handler exception traceback: {traceback.format_exc()}")

        try:
            progress.close()
        except:
            pass

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


def _ensure_startup_initialization(context: PluginContext):
    """Ensure critical startup initialization is completed"""
    try:
        log("=== STARTUP INITIALIZATION ===")
        
        # Check if favorites integration is enabled
        from lib.config.config_manager import get_config
        config = get_config()
        favorites_enabled = config.get_bool('favorites_integration_enabled', False)
        log(f"Favorites integration enabled: {favorites_enabled}")
        
        if favorites_enabled:
            log("Favorites integration is enabled - ensuring Kodi Favorites list exists")
            
            # Use context query manager for consistency
            query_manager = context.query_manager
            
            if query_manager.initialize():
                with query_manager.connection_manager.transaction() as conn:
                    # Check if Kodi Favorites list exists
                    kodi_list = conn.execute("""
                        SELECT id FROM lists WHERE name = 'Kodi Favorites'
                    """).fetchone()
                    
                    if not kodi_list:
                        # Create the Kodi Favorites list since it doesn't exist
                        log_info("STARTUP: Creating 'Kodi Favorites' list - setting is enabled but list doesn't exist")
                        
                        try:
                            from lib.config.favorites_helper import on_favorites_integration_enabled
                            on_favorites_integration_enabled()
                            log_info("STARTUP: Successfully ensured 'Kodi Favorites' list exists")
                        except Exception as e:
                            log_error(f"STARTUP: Failed to create 'Kodi Favorites' list: {e}")
                    else:
                        log(f"STARTUP: 'Kodi Favorites' list already exists with ID {kodi_list['id']}")
            else:
                log_warning("STARTUP: Could not initialize query manager for startup check")
        else:
            log("STARTUP: Favorites integration is disabled - skipping Kodi Favorites list check")
            
        log("=== STARTUP INITIALIZATION COMPLETE ===")
        
    except Exception as e:
        log_error(f"STARTUP: Error during startup initialization: {e}")
        import traceback
        log_error(f"STARTUP: Initialization error traceback: {traceback.format_exc()}")
        # Don't fail the plugin startup for initialization issues
        pass


def main():
    """Main plugin entry point using new modular architecture"""

    log("=== PLUGIN INVOCATION (REFACTORED) ===")
    log(f"Full sys.argv: {sys.argv}")
    log("Using modular handler architecture")

    try:
        # Create plugin context from request
        context = PluginContext()

        # Log window state for debugging
        _log_window_state(context)

        # Ensure critical startup initialization is completed
        _ensure_startup_initialization(context)
        
        # Check for fresh install and show setup modal if needed
        fresh_install_handled = _check_and_handle_fresh_install(context)
        # Continue to main menu even after fresh install setup

        # Create router and register handlers
        router = Router()
        _register_all_handlers(router)

        # Try to dispatch the request
        if not router.dispatch(context):
            # No handler found, show main menu using lazy factory
            factory = get_handler_factory()
            main_menu_handler = factory.get_main_menu_handler()
            main_menu_handler.show_main_menu(context)

    except Exception as e:
        log_error(f"Fatal error in plugin main: {e}")
        import traceback
        log_error(f"Main error traceback: {traceback.format_exc()}")

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

        log("Window state at plugin entry:")
        log(f"  Current window: {current_window}")
        log(f"  Current control: {current_control}")
        log(f"  Container path: {container_path}")
        log(f"  Container label: {container_label}")

        # Check specific window visibility states
        myvideo_nav_visible = xbmc.getCondVisibility("Window.IsVisible(MyVideoNav.xml)")
        dialog_video_info_visible = xbmc.getCondVisibility("Window.IsVisible(DialogVideoInfo.xml)")
        dialog_video_info_active = xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)")
        keyboard_visible = xbmc.getCondVisibility("Window.IsVisible(DialogKeyboard.xml)")

        log(f"  MyVideoNav.xml visible: {myvideo_nav_visible}")
        log(f"  DialogVideoInfo.xml visible: {dialog_video_info_visible}")
        log(f"  DialogVideoInfo.xml active: {dialog_video_info_active}")
        log(f"  DialogKeyboard.xml visible: {keyboard_visible}")

    except Exception as e:
        log_warning(f"Failed to log window state at plugin entry: {e}")


def _check_and_handle_fresh_install(context: PluginContext) -> bool:
    """Check for fresh install and show setup modal if needed. Returns True if handled."""
    try:
        from lib.library.sync_controller import SyncController
        from lib.ui.localization import L
        
        sync_controller = SyncController()
        
        # Skip if first run already completed
        if not sync_controller.is_first_run():
            return False
            
        log_info("First run detected - showing setup modal")
        
        # Show welcome dialog first with explanation
        dialog = xbmcgui.Dialog()
        
        # Show welcome/explanation dialog
        dialog.ok(L(35540), L(35541))  # Welcome title and detailed explanation
        
        # Show fresh install setup dialog with enhanced options
        # Create setup options with enhanced descriptions
        options = [
            L(35521),  # Enhanced "Movies and TV Episodes (Recommended)" with description
            L(35522),  # Enhanced "Movies Only" with description  
            L(35523),  # Enhanced "TV Episodes Only" with description
            L(35524)   # Enhanced "Skip Setup (Configure Later)" with description
        ]
        
        # Use compatible dialog.select parameters
        selected = dialog.select(L(35520), options)  # "LibraryGenie Setup"
        
        # Handle user selection
        if selected == -1:  # User canceled or pressed back
            log_info("Fresh install setup canceled by user")
            return True  # Handled cancellation, continue to main menu
            
        elif selected == 0:  # Both movies and TV episodes
            log_info("User selected: Movies and TV Episodes")
            _show_setup_progress(L(35525))  # "Setting up Movies and TV Episodes sync..."
            sync_controller.complete_first_run_setup(sync_movies=True, sync_tv_episodes=True)
            _show_setup_complete(L(35528))  # "Setup complete! Both movies and TV episodes will be synced."
            
        elif selected == 1:  # Movies only
            log_info("User selected: Movies Only")
            _show_setup_progress(L(35526))  # "Setting up Movies sync..."
            sync_controller.complete_first_run_setup(sync_movies=True, sync_tv_episodes=False)
            _show_setup_complete(L(35529))  # "Setup complete! Movies will be synced."
            
        elif selected == 2:  # TV Episodes only
            log_info("User selected: TV Episodes Only")
            _show_setup_progress(L(35527))  # "Setting up TV Episodes sync..."
            sync_controller.complete_first_run_setup(sync_movies=False, sync_tv_episodes=True)
            _show_setup_complete(L(35530))  # "Setup complete! TV episodes will be synced."
            
        elif selected == 3:  # Skip setup
            log_info("User selected: Skip Setup")
            # Mark first run complete but don't enable any syncing
            sync_controller.complete_first_run_setup(sync_movies=False, sync_tv_episodes=False)
            xbmcgui.Dialog().notification(
                L(35002),   # "LibraryGenie"
                L(35531),   # "Setup skipped. Configure sync options in Settings."
                xbmcgui.NOTIFICATION_INFO,
                4000
            )
        
        return True  # Handled fresh install, continue to main menu
        
    except Exception as e:
        log_error(f"Error during fresh install setup: {e}")
        # On error, mark first run complete to avoid infinite loops
        try:
            from lib.library.sync_controller import SyncController
            sync_controller = SyncController()
            sync_controller.complete_first_run_setup(sync_movies=True, sync_tv_episodes=False)
        except:
            pass
        
        from lib.ui.localization import L
        xbmcgui.Dialog().notification(
            L(35002),   # "LibraryGenie"
            L(35532),   # "Setup error - using default settings"
            xbmcgui.NOTIFICATION_WARNING,
            4000
        )
        return True


def _show_setup_progress(message: str):
    """Show setup progress notification"""
    from lib.ui.localization import L
    xbmcgui.Dialog().notification(
        L(35520),   # "LibraryGenie Setup"
        message,
        xbmcgui.NOTIFICATION_INFO,
        1000
    )


def _show_setup_complete(message: str):
    """Show setup completion notification"""
    from lib.ui.localization import L
    xbmcgui.Dialog().notification(
        L(35520),   # "LibraryGenie Setup"
        message,
        xbmcgui.NOTIFICATION_INFO,
        1000
    )




def _handle_manual_library_sync(context: PluginContext):
    """Handle manual library sync triggered from settings"""
    try:
        from lib.library.sync_controller import SyncController
        
        log_info("Manual library sync triggered from settings")
        
        # Show initial notification
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Starting library sync...",
            xbmcgui.NOTIFICATION_INFO,
            2000
        )
        
        # Perform sync
        sync_controller = SyncController()
        success, message = sync_controller.perform_manual_sync()
        
        # Show result notification
        if success:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                message,
                xbmcgui.NOTIFICATION_INFO,
                6000
            )
            log_info(f"Manual library sync completed successfully: {message}")
        else:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Sync failed: {message}",
                xbmcgui.NOTIFICATION_ERROR,
                8000
            )
            log_warning(f"Manual library sync failed: {message}")
            
    except Exception as e:
        error_msg = f"Manual sync error: {str(e)}"
        log_error(error_msg)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            error_msg,
            xbmcgui.NOTIFICATION_ERROR,
            6000
        )


def _register_all_handlers(router: Router):
    """Register all action handlers with the router using lazy factory"""

    # Get handler factory for lazy loading
    factory = get_handler_factory()

    # Register handlers with lazy instantiation - handlers only created when needed
    router.register_handler('search', lambda ctx: factory.get_search_handler().prompt_and_search(ctx))
    router.register_handler('ai_search_prompt', lambda ctx: factory.get_search_handler().ai_search_prompt(ctx))
    router.register_handler('lists', lambda ctx: factory.get_lists_handler().show_lists_menu(ctx))
    router.register_handler('kodi_favorites', lambda ctx: _handle_directory_response(ctx, factory.get_favorites_handler().show_favorites_menu(ctx)))

    # Register ListsHandler methods that expect specific parameters
    router.register_handler('create_list_execute', lambda ctx: _handle_dialog_response(ctx, factory.get_lists_handler().create_list(ctx)))
    router.register_handler('create_folder_execute', lambda ctx: _handle_dialog_response(ctx, factory.get_lists_handler().create_folder(ctx)))

    # Register list and folder view handlers
    router.register_handler('show_list', lambda ctx: factory.get_lists_handler().view_list(ctx, ctx.get_param('list_id')))
    router.register_handler('show_folder', lambda ctx: factory.get_lists_handler().show_folder(ctx, ctx.get_param('folder_id')))

    # Register parameter-based handlers with proper context setting
    def _handle_delete_list(ctx):
        factory.context = ctx
        return _handle_dialog_response(ctx, factory.get_lists_handler().delete_list(ctx, ctx.get_param('list_id')))
    
    def _handle_rename_list(ctx):
        factory.context = ctx
        return _handle_dialog_response(ctx, factory.get_lists_handler().rename_list(ctx, ctx.get_param('list_id')))
    
    def _handle_remove_from_list_handler(ctx):
        factory.context = ctx
        return _handle_dialog_response(ctx, factory.get_lists_handler().remove_from_list(ctx, ctx.get_param('list_id'), ctx.get_param('item_id')))
    
    def _handle_rename_folder(ctx):
        factory.context = ctx
        return _handle_dialog_response(ctx, factory.get_lists_handler().rename_folder(ctx, ctx.get_param('folder_id')))
    
    def _handle_delete_folder(ctx):
        factory.context = ctx
        return _handle_dialog_response(ctx, factory.get_lists_handler().delete_folder(ctx, ctx.get_param('folder_id')))

    router.register_handler('delete_list', _handle_delete_list)
    router.register_handler('rename_list', _handle_rename_list)
    router.register_handler('remove_from_list', _handle_remove_from_list_handler)
    router.register_handler('rename_folder', _handle_rename_folder)
    router.register_handler('delete_folder', _handle_delete_folder)

    # Register FavoritesHandler methods
    router.register_handler('scan_favorites_execute', lambda ctx: factory.get_favorites_handler().handle_scan_favorites(ctx))
    router.register_handler('save_favorites_as', lambda ctx: factory.get_favorites_handler().handle_save_favorites_as(ctx))
    router.register_handler('add_favorite_to_list', lambda ctx: _handle_dialog_response(ctx, factory.get_favorites_handler().add_favorite_to_list(ctx, ctx.get_param('imdb_id'))))

    # Register remaining handlers (these don't use handlers so no lazy loading needed)
    router.register_handlers({
        'authorize': lambda ctx: handle_authorize(),
        'signout': lambda ctx: handle_signout(),
        'on_select': lambda ctx: handle_on_select(ctx.params, ctx.addon_handle),
        'import_shortlist': lambda ctx: handle_shortlist_import(),
        'test_backup': lambda ctx: _handle_test_backup(ctx),
        'manual_backup': lambda ctx: _handle_manual_backup(ctx),
        'restore_backup': lambda ctx: _handle_restore_backup(ctx),
        'noop': lambda ctx: handle_noop(),
        'settings': lambda ctx: handle_settings(),
        'manual_library_sync': lambda ctx: _handle_manual_library_sync(ctx),
    })


def _handle_dialog_response(context: PluginContext, response):
    """Handle DialogResponse objects from handler methods"""
    from lib.ui.response_types import DialogResponse
    from lib.ui.response_handler import get_response_handler

    if isinstance(response, DialogResponse):
        response_handler = get_response_handler()
        return response_handler.handle_dialog_response(response, context)

    return response


def _handle_remove_from_list(context: PluginContext, lists_handler):
    """Handle remove_from_list with fallback logic"""
    list_id = context.get_param('list_id')
    item_id = context.get_param('item_id')
    
    if item_id:
        # Direct removal using item_id
        response = lists_handler.remove_from_list(context, list_id, item_id)
    else:
        # Fallback: find item by library identifiers
        dbtype = context.get_param('dbtype')
        dbid = context.get_param('dbid')
        title = context.get_param('title', '')
        
        if dbtype and dbid:
            # Try to find the media_item in the list by matching library identifiers
            try:
                query_manager = context.query_manager
                list_items = query_manager.get_list_items(list_id)
                
                # Find matching item
                matching_item = None
                for item in list_items:
                    if (item.get('kodi_id') == int(dbid) and 
                        item.get('media_type') == dbtype):
                        matching_item = item
                        break
                
                if matching_item and 'id' in matching_item:
                    response = lists_handler.remove_from_list(context, list_id, str(matching_item['id']))
                else:
                    from lib.ui.response_types import DialogResponse
                    response = DialogResponse(
                        success=False,
                        message="Could not find item in list"
                    )
            except Exception as e:
                log_error(f"Error finding item for removal: {e}")
                from lib.ui.response_types import DialogResponse
                response = DialogResponse(
                    success=False,
                    message="Error finding item"
                )
        else:
            from lib.ui.response_types import DialogResponse
            response = DialogResponse(
                success=False,
                message="Invalid remove request"
            )
    
    return _handle_dialog_response(context, response)


def _handle_directory_response(context: PluginContext, response):
    """Handle DirectoryResponse objects from handler methods"""
    from lib.ui.response_types import DirectoryResponse
    from lib.ui.response_handler import get_response_handler

    if isinstance(response, DirectoryResponse):
        response_handler = get_response_handler()
        return response_handler.handle_directory_response(response, context)

    return response


if __name__ == '__main__':
    main()