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
from typing import List, Union

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
        elif action == "deactivate_ai_search":
            handle_deactivate_ai_search()
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
        from data.query_manager import get_query_manager
        from config.config_manager import get_config
        
        query_manager = get_query_manager()
        if not query_manager or not query_manager.initialize():
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Database not available",
                xbmcgui.NOTIFICATION_ERROR
            )
            return
        
        # Initialize display setting if needed - sync with existing default list
        config = get_config()
        current_default_id = config.get("default_list_id", "")
        if current_default_id:
            # Ensure display setting matches current default
            _update_default_list_display(config, current_default_id)
        else:
            # No default set, ensure display shows "None selected"
            _update_default_list_display(config, None)
        
        while True:  # Loop to allow retry after creating new list
            # Get all user lists and filter out Search History
            all_lists = query_manager.get_user_lists()
            lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History']
            
            # Create selection dialog options
            dialog = xbmcgui.Dialog()
            list_names: List[Union[str, xbmcgui.ListItem]] = ["Add New List..."]  # First option for creating new list
            
            # Add existing lists
            for lst in lists:
                folder_info = f" ({lst['folder_name']})" if lst.get('folder_name') else ""
                list_names.append(f"{lst['name']}{folder_info}")
            
            # If no lists available, still show the create option
            if not lists:
                list_names.append("(No existing lists found)")
            
            selected = dialog.select("Select Default List for Quick-Add", list_names)
            
            if selected == -1:  # User cancelled
                return
            elif selected == 0:  # "Add New List..." selected
                # Handle new list creation
                new_list_id = _create_new_list_with_folder_selection(query_manager)
                if new_list_id:
                    # Successfully created new list, set it as default
                    # Ensure we have just the ID, not a dictionary
                    list_id = new_list_id['id'] if isinstance(new_list_id, dict) else new_list_id
                    config.set("default_list_id", str(list_id))
                    
                    # Update the display setting
                    _update_default_list_display(config, list_id)
                    
                    # Get the new list info for confirmation  
                    new_list = query_manager.get_list_by_id(list_id)
                    list_name = new_list.get('name', 'New List') if new_list else 'New List'
                    
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Created and set default list: {list_name}",
                        xbmcgui.NOTIFICATION_INFO
                    )
                    log_info(f"Created new list and set as default: {list_name} (ID: {list_id})")
                    
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Default list updated. Click OK to save settings.",
                        xbmcgui.NOTIFICATION_INFO
                    )
                    return
                # If creation failed, continue the loop to show menu again
            else:
                # Existing list selected
                if not lists or selected > len(lists):
                    # Handle edge case where "No existing lists found" was shown
                    continue
                    
                selected_list = lists[selected - 1]  # -1 because "Add New List..." is at index 0
                
                config.set("default_list_id", str(selected_list['id']))
                
                # Update the display setting
                _update_default_list_display(config, selected_list['id'])
                
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Default list set to: {selected_list['name']}",
                    xbmcgui.NOTIFICATION_INFO
                )
                log_info(f"Default list set to: {selected_list['name']} (ID: {selected_list['id']})")
                
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Default list updated. Click OK to save settings.",
                    xbmcgui.NOTIFICATION_INFO
                )
                return
        
    except Exception as e:
        log_error(f"Error in handle_set_default_list: {e}")
        import traceback
        log_error(f"Set default list error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Error setting default list: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )



def _update_default_list_display(config, list_id=None):
    """Helper function to update the display setting with the current default list name"""
    try:
        if not list_id:
            # Clear the display
            config.set("default_list_display", "None selected")
            return True
            
        # Get the list name from the database
        from data.query_manager import get_query_manager
        query_manager = get_query_manager()
        if query_manager and query_manager.initialize():
            list_info = query_manager.get_list_by_id(list_id)
            if list_info:
                list_name = list_info.get('name', 'Unknown List')
                folder_name = list_info.get('folder_name')
                
                # Format display with folder info if available
                if folder_name:
                    display_text = f"{list_name} ({folder_name})"
                else:
                    display_text = list_name
                    
                config.set("default_list_display", display_text)
                return True
        
        # Fallback if we can't get list info
        config.set("default_list_display", f"List ID: {list_id}")
        return True
        
    except Exception as e:
        log_error(f"Error updating default list display: {e}")
        return False


def _create_new_list_with_folder_selection(query_manager):
    """Helper function to create a new list with folder selection"""
    try:
        # Get list name from user
        dialog = xbmcgui.Dialog()
        list_name = dialog.input("Enter List Name", type=xbmcgui.INPUT_ALPHANUM)
        
        if not list_name or not list_name.strip():
            return None  # User cancelled or entered empty name
        
        list_name = list_name.strip()
        
        # Get available folders for selection
        all_folders = query_manager.get_all_folders()
        
        # Filter out Search History folder from selection
        folders = [f for f in all_folders if f.get('name') != 'Search History']
        
        folder_options: List[Union[str, xbmcgui.ListItem]] = ["[Root Level]"]  # Option for root level
        folder_ids = [None]  # None represents root level
        
        for folder in folders:
            folder_options.append(folder['name'])
            folder_ids.append(folder['id'])
        
        # Show folder selection dialog
        selected_folder_index = dialog.select(f"Select Folder for '{list_name}'", folder_options)
        
        if selected_folder_index == -1:
            return None  # User cancelled folder selection
        
        selected_folder_id = folder_ids[selected_folder_index]
        
        # Create the list
        result = query_manager.create_list(list_name, description='', folder_id=selected_folder_id)
        
        if isinstance(result, dict) and result.get("error"):
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Failed to create list: {result['error']}",
                xbmcgui.NOTIFICATION_ERROR
            )
            return None
        elif result:
            # Successful creation - result might be a dict or just the ID
            if isinstance(result, dict) and 'id' in result:
                return result['id']  # Extract ID from dictionary
            else:
                return result  # Already just the ID
        else:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to create list",
                xbmcgui.NOTIFICATION_ERROR
            )
            return None
            
    except Exception as e:
        log_error(f"Error creating new list: {e}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"Error creating list: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )
        return None


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
        backup_names: List[Union[str, xbmcgui.ListItem]] = []
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
        addon = xbmcaddon.Addon()
        
        # Check if we already have a URL configured
        server_url = config.get("remote_server_url", "").strip()
        
        if not server_url:
            # Streamlined workflow: Ask for URL first
            dialog = xbmcgui.Dialog()
            entered_url = dialog.input(
                "Enter AI Search Server URL", 
                type=xbmcgui.INPUT_ALPHANUM
            )
            
            if not entered_url or not entered_url.strip():
                log_info("User cancelled URL entry")
                return
                
            server_url = entered_url.strip()
            
            # Save URL immediately to both addon settings and config
            addon.setSetting("remote_server_url", server_url)
            config.set("remote_server_url", server_url)
            
            log_info(f"User entered and saved server URL for authorization")
        else:
            log_info(f"Using existing server URL for authorization")
        
        # Run authorization flow
        success = run_otp_authorization_flow(server_url)
        
        if success:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search authorization completed successfully",
                xbmcgui.NOTIFICATION_INFO
            )
            log_info("AI search authorization completed successfully")
        else:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Authorization failed",
                xbmcgui.NOTIFICATION_ERROR
            )
            log_error("AI search authorization failed")
        
    except Exception as e:
        log_error(f"Error in handle_authorize_ai_search: {e}")
        import traceback
        log_error(f"AI search authorization error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"AI search authorization error: {str(e)}",
            xbmcgui.NOTIFICATION_ERROR
        )


def handle_deactivate_ai_search():
    """Handle deactivate AI search action from settings"""
    log_info("Handling deactivate_ai_search action")
    
    try:
        from auth.state import clear_auth_data, is_authorized
        from config.config_manager import get_config
        
        # Check if currently authorized
        if not is_authorized():
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "AI search is not currently activated",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Confirm deactivation
        dialog = xbmcgui.Dialog()
        if not dialog.yesno(
            "Deactivate AI Search",
            "This will deactivate AI search and clear all authorization data.\n\nContinue?",
            "Cancel",
            "Deactivate"
        ):
            return
        
        # Clear auth data and deactivate
        config = get_config()
        
        # Clear API key and auth data
        success = clear_auth_data()
        if success:
            # Set activated status to false
            config.set('ai_search_activated', False)
            
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search deactivated successfully", 
                xbmcgui.NOTIFICATION_INFO
            )
            log_info("AI search deactivated successfully")
        else:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to deactivate AI search",
                xbmcgui.NOTIFICATION_ERROR
            )
            log_error("Failed to clear auth data during deactivation")
        
    except Exception as e:
        log_error(f"Error in handle_deactivate_ai_search: {e}")
        import traceback
        log_error(f"AI search deactivation error traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"AI search deactivation error: {str(e)}",
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