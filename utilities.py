#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Settings Utilities Handler
Handles RunScript calls from settings.xml action buttons
"""

import sys
import os
import xbmcgui
import xbmcaddon

# Setup proper module paths for Kodi addon structure
addon = xbmcaddon.Addon()
addon_path = addon.getAddonInfo('path')
lib_path = os.path.join(addon_path, 'lib')

# Add lib directory to Python path for absolute imports
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Now import using absolute paths from lib/
from utils.kodi_log import log, log_info, log_error


def main():
    """Main entry point for RunScript calls from settings"""
    log_info("=== UTILITIES HANDLER CALLED ===")
    log_info(f"sys.argv: {sys.argv}")
    
    if len(sys.argv) < 2:
        log_error("No action parameter provided to utilities handler")
        return
    
    # Normalize action parameter (handle whitespace and key=value format)
    action = sys.argv[1].strip()
    if action.startswith("action="):
        action = action.split("=", 1)[1].strip()
    
    log_info(f"Handling settings action: '{action}'")
    
    try:
        if action == "set_default_list":
            handle_set_default_list()
        elif action == "manual_library_sync":
            handle_manual_library_sync()
        elif action == "import_shortlist":
            handle_import_shortlist()
        elif action == "manual_backup":
            handle_manual_backup()
        elif action == "restore_backup":
            handle_restore_backup()
        elif action == "authorize_ai_search":
            handle_authorize_ai_search()
        elif action == "ai_search_replace_sync":
            handle_ai_search_replace_sync()
        elif action == "ai_search_regular_sync":
            handle_ai_search_regular_sync()
        else:
            log_error(f"Unknown action: {action}")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Unknown action: {action}",
                xbmcgui.NOTIFICATION_ERROR
            )
    
    except Exception as e:
        log_error(f"Error in utilities handler for action '{action}': {e}")
        import traceback
        log_error(f"Utilities handler error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Error in {action}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_set_default_list():
    """Handle set default list action from settings"""
    log_info("Handling set_default_list action")
    
    try:
        # Simplified approach - directly create a list selection dialog
        # Get available lists from database
        from data.query_manager import get_query_manager
        
        query_manager = get_query_manager()
        if not query_manager or not query_manager.initialize():
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Database not available",
                xbmcgui.NOTIFICATION_ERROR
            )
            return
        
        # Get all lists
        lists = query_manager.get_all_lists()
        
        if not lists:
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "No lists found. Create some lists first.",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Create selection dialog
        dialog = xbmcgui.Dialog()
        list_names = [f"{lst['name']}" for lst in lists]
        list_names.insert(0, "None (disable quick-add)")
        
        selected = dialog.select("Select Default List for Quick-Add", list_names)
        
        if selected == -1:  # User cancelled
            return
        elif selected == 0:  # None selected
            # Clear default list
            from config.config_manager import get_config
            config = get_config()
            config.set("default_list_id", "")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Quick-add default list cleared",
                xbmcgui.NOTIFICATION_INFO
            )
        else:
            # Set selected list as default
            selected_list = lists[selected - 1]  # -1 because we inserted "None" at index 0
            
            from config.config_manager import get_config
            config = get_config()
            config.set("default_list_id", str(selected_list['id']))
            
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Default list set to: {selected_list['name']}",
                xbmcgui.NOTIFICATION_INFO
            )
            log_info(f"Default list set to: {selected_list['name']} (ID: {selected_list['id']})")
        
    except Exception as e:
        log_error(f"Error in handle_set_default_list: {e}")
        import traceback
        log_error(f"Set default list error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Error setting default list: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_manual_library_sync():
    """Handle manual library sync action from settings"""
    log_info("Handling manual_library_sync action")
    
    try:
        # Import the manual sync handler from plugin.py
        from plugin import _handle_manual_library_sync
        from ui.plugin_context import PluginContext
        
        # Create a mock context for settings operations
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Call the manual sync handler
        _handle_manual_library_sync(context)
        
    except Exception as e:
        log_error(f"Error in handle_manual_library_sync: {e}")
        import traceback
        log_error(f"Manual sync error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Manual sync error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_import_shortlist():
    """Handle import shortlist action from settings"""
    log_info("Handling import_shortlist action")
    
    try:
        # Import the shortlist handler from plugin.py
        from plugin import handle_shortlist_import
        
        # Call the shortlist import handler
        handle_shortlist_import()
        
    except Exception as e:
        log_error(f"Error in handle_import_shortlist: {e}")
        import traceback
        log_error(f"Import shortlist error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Import shortlist error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_manual_backup():
    """Handle manual backup action from settings"""
    log_info("Handling manual_backup action")
    
    try:
        # Direct backup approach avoiding complex UI imports
        from import_export.timestamp_backup_manager import get_timestamp_backup_manager
        
        backup_manager = get_timestamp_backup_manager()
        result = backup_manager.run_automatic_backup()
        
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
            log_info(f"Manual backup completed: {result.get('filename', 'Unknown')}")
        else:
            error_msg = result.get("error", "Unknown error")
            xbmcgui.Dialog().ok("Manual Backup Failed", f"Backup failed:\n{error_msg}")
            log_error(f"Manual backup failed: {error_msg}")
        
    except Exception as e:
        log_error(f"Error in handle_manual_backup: {e}")
        import traceback
        log_error(f"Manual backup error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Manual backup error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_restore_backup():
    """Handle restore backup action from settings"""
    log_info("Handling restore_backup action")
    
    try:
        # Direct restore approach avoiding complex UI imports
        from import_export.timestamp_backup_manager import get_timestamp_backup_manager
        
        backup_manager = get_timestamp_backup_manager()
        
        # Get available backup files
        available_backups = backup_manager.get_available_backups()
        
        if not available_backups:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "No backup files found",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Create selection dialog
        dialog = xbmcgui.Dialog()
        backup_names = []
        for backup in available_backups:
            # Format: filename (size, age)
            size_mb = round(backup.get('file_size', 0) / 1024 / 1024, 2)
            age_days = backup.get('age_days', 0)
            backup_names.append(f"{backup['filename']} ({size_mb}MB, {age_days} days old)")
        
        selected = dialog.select("Select Backup to Restore", backup_names)
        
        if selected == -1:  # User cancelled
            return
        
        selected_backup = available_backups[selected]
        
        # Confirm restore
        if not dialog.yesno(
            "Confirm Restore",
            f"This will restore from:\n{selected_backup['filename']}\n\nAll current data will be replaced. Continue?",
            "Cancel",
            "Restore"
        ):
            return
        
        # Perform restore
        result = backup_manager.restore_backup(selected_backup['file_path'], replace_mode=True)
        
        if result["success"]:
            message = f"Backup restored successfully!\n\nRestored {result.get('total_items', 0)} items"
            xbmcgui.Dialog().ok("Backup Restored", message)
            log_info(f"Backup restored: {selected_backup['filename']}")
        else:
            error_msg = result.get("error", "Unknown error")
            xbmcgui.Dialog().ok("Restore Failed", f"Restore failed:\n{error_msg}")
            log_error(f"Backup restore failed: {error_msg}")
        
    except Exception as e:
        log_error(f"Error in handle_restore_backup: {e}")
        import traceback
        log_error(f"Restore backup error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Restore backup error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_authorize_ai_search():
    """Handle authorize AI search action from settings"""
    log_info("Handling authorize_ai_search action")
    
    try:
        # Direct approach for AI search authorization
        from auth.otp_auth import run_otp_authorization_flow
        from config.config_manager import get_config
        
        config = get_config()
        server_url = config.get("remote_server_url", "")
        
        if not server_url:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "No AI search server URL configured",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Run authorization flow
        result = run_otp_authorization_flow(server_url)
        
        if result.get('success'):
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search authorization completed successfully",
                xbmcgui.NOTIFICATION_INFO
            )
            log_info("AI search authorization completed successfully")
        else:
            error_msg = result.get('error', 'Authorization failed')
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Authorization failed: {error_msg}",
                xbmcgui.NOTIFICATION_ERROR
            )
            log_error(f"AI search authorization failed: {error_msg}")
        
    except Exception as e:
        log_error(f"Error in handle_authorize_ai_search: {e}")
        import traceback
        log_error(f"AI search authorization error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"AI search authorization error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_ai_search_replace_sync():
    """Handle AI search replace sync action from settings"""
    log_info("Handling ai_search_replace_sync action")
    
    try:
        # Direct approach for AI search sync
        from remote.ai_search import get_ai_search_service
        from config.config_manager import get_config
        
        config = get_config()
        
        # Check if AI search is activated
        if not config.get_bool("ai_search_activated", False):
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search is not activated",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Show confirmation
        dialog = xbmcgui.Dialog()
        if not dialog.yesno(
            "AI Search Replace Sync",
            "This will replace all movie data with fresh AI search data.\n\nThis may take some time. Continue?",
            "Cancel",
            "Continue"
        ):
            return
        
        # Get AI search service and perform sync
        ai_service = get_ai_search_service()
        if ai_service:
            # Run replace sync in background
            success = ai_service.perform_replace_sync()
            
            if success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "AI search replace sync started",
                    xbmcgui.NOTIFICATION_INFO
                )
                log_info("AI search replace sync started successfully")
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Failed to start AI search replace sync",
                    xbmcgui.NOTIFICATION_ERROR
                )
        else:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search service not available",
                xbmcgui.NOTIFICATION_ERROR
            )
        
    except Exception as e:
        log_error(f"Error in handle_ai_search_replace_sync: {e}")
        import traceback
        log_error(f"AI search replace sync error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"AI search replace sync error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_ai_search_regular_sync():
    """Handle AI search regular sync action from settings"""
    log_info("Handling ai_search_regular_sync action")
    
    try:
        # Direct approach for AI search regular sync
        from remote.ai_search import get_ai_search_service
        from config.config_manager import get_config
        
        config = get_config()
        
        # Check if AI search is activated
        if not config.get_bool("ai_search_activated", False):
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search is not activated",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Show confirmation
        dialog = xbmcgui.Dialog()
        if not dialog.yesno(
            "AI Search Regular Sync",
            "This will sync new movies with AI search data.\n\nThis may take some time. Continue?",
            "Cancel",
            "Continue"
        ):
            return
        
        # Get AI search service and perform sync
        ai_service = get_ai_search_service()
        if ai_service:
            # Run regular sync in background
            success = ai_service.perform_regular_sync()
            
            if success:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "AI search regular sync started",
                    xbmcgui.NOTIFICATION_INFO
                )
                log_info("AI search regular sync started successfully")
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Failed to start AI search regular sync",
                    xbmcgui.NOTIFICATION_ERROR
                )
        else:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search service not available",
                xbmcgui.NOTIFICATION_ERROR
            )
        
    except Exception as e:
        log_error(f"Error in handle_ai_search_regular_sync: {e}")
        import traceback
        log_error(f"AI search regular sync error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"AI search regular sync error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


if __name__ == "__main__":
    main()