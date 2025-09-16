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

# Add the main lib directory to Python path so we can import lib.utils.kodi_log
# utilities.py is in resources/lib/, so we need to go up two levels to get to the addon root,
# then down to lib/
addon_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_path = os.path.join(addon_root, 'lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

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
        # Import required modules
        from ui.plugin_context import PluginContext
        from ui.handler_factory import get_handler_factory
        from ui.response_handler import get_response_handler
        
        # Create a mock context for settings operations (no addon handle needed)
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Get the lists handler
        factory = get_handler_factory()
        factory.context = context
        lists_handler = factory.get_lists_handler()
        response_handler = get_response_handler()
        
        # Call the set default list method
        response = lists_handler.set_default_list(context)
        
        # Handle the response
        if hasattr(response, 'success'):
            if response.success:
                log_info("Set default list completed successfully")
            else:
                log_error(f"Set default list failed: {getattr(response, 'message', 'Unknown error')}")
        
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
        import sys
        import os
        # Add the addon root directory to the Python path
        addon_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        sys.path.insert(0, addon_root)
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
        import sys
        import os
        # Add the addon root directory to the Python path
        addon_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if addon_root not in sys.path:
            sys.path.insert(0, addon_root)
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
        # Import the manual backup handler from plugin.py
        import sys
        import os
        # Add the addon root directory to the Python path
        addon_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if addon_root not in sys.path:
            sys.path.insert(0, addon_root)
        from plugin import _handle_manual_backup
        from ui.plugin_context import PluginContext
        
        # Create a mock context for settings operations
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Call the manual backup handler
        _handle_manual_backup(context)
        
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
        # Import the restore backup handler from plugin.py
        import sys
        import os
        # Add the addon root directory to the Python path
        addon_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if addon_root not in sys.path:
            sys.path.insert(0, addon_root)
        from plugin import _handle_restore_backup
        from ui.plugin_context import PluginContext
        
        # Create a mock context for settings operations
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Call the restore backup handler
        _handle_restore_backup(context)
        
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
        # Check if AI search handler is available
        from ui.handler_factory import get_handler_factory
        factory = get_handler_factory()
        
        if not hasattr(factory, 'get_ai_search_handler'):
            log_error("AI search handler not available in factory")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search functionality not available",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Import required modules
        from ui.plugin_context import PluginContext
        
        # Create a mock context for settings operations
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Get the AI search handler
        factory.context = context
        ai_search_handler = factory.get_ai_search_handler()
        
        # Call the authorize method
        result = ai_search_handler.authorize_ai_search(context)
        
        if hasattr(result, 'success'):
            if result.success:
                log_info("AI search authorization completed successfully")
            else:
                log_error(f"AI search authorization failed: {getattr(result, 'message', 'Unknown error')}")
        
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
        # Check if AI search handler is available
        from ui.handler_factory import get_handler_factory
        factory = get_handler_factory()
        
        if not hasattr(factory, 'get_ai_search_handler'):
            log_error("AI search handler not available in factory")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search functionality not available",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Import required modules
        from ui.plugin_context import PluginContext
        
        # Create a mock context for settings operations
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Get the AI search handler
        factory.context = context
        ai_search_handler = factory.get_ai_search_handler()
        
        # Call the replace sync method
        result = ai_search_handler.trigger_replace_sync(context)
        
        if hasattr(result, 'success'):
            if result.success:
                log_info("AI search replace sync completed successfully")
            else:
                log_error(f"AI search replace sync failed: {getattr(result, 'message', 'Unknown error')}")
        
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
        # Check if AI search handler is available
        from ui.handler_factory import get_handler_factory
        factory = get_handler_factory()
        
        if not hasattr(factory, 'get_ai_search_handler'):
            log_error("AI search handler not available in factory")
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "AI search functionality not available",
                xbmcgui.NOTIFICATION_WARNING
            )
            return
        
        # Import required modules
        from ui.plugin_context import PluginContext
        
        # Create a mock context for settings operations
        context = PluginContext()
        context.addon_handle = -1  # No directory rendering for settings actions
        
        # Get the AI search handler
        factory.context = context
        ai_search_handler = factory.get_ai_search_handler()
        
        # Call the regular sync method
        result = ai_search_handler.trigger_regular_sync(context)
        
        if hasattr(result, 'success'):
            if result.success:
                log_info("AI search regular sync completed successfully")
            else:
                log_error(f"AI search regular sync failed: {getattr(result, 'message', 'Unknown error')}")
        
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