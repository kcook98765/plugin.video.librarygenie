
import sys
import os

# Get the addon directory and add it to Python path
addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
lib_dir = os.path.join(addon_dir, 'resources', 'lib')

# Ensure the lib directory is in the Python path
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

# Also add the addon directory itself
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import xbmc
import xbmcgui

def safe_import_modules():
    """Safely import required modules with fallback"""
    try:
        # Try direct imports first
        import addon_ref
        import kodi_helper
        import window_main
        
        return (
            addon_ref.get_addon,
            kodi_helper.KodiHelper,
            window_main.MainWindow
        )
        
    except ImportError as e:
        xbmc.log(f"LibraryGenie: Direct import failed: {str(e)}", xbmc.LOGWARNING)
        
        # Fallback to file-based imports
        try:
            import importlib.util
            
            # Import addon_ref
            addon_ref_path = os.path.join(lib_dir, 'addon_ref.py')
            spec = importlib.util.spec_from_file_location("addon_ref", addon_ref_path)
            addon_ref_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(addon_ref_module)
            
            # Import kodi_helper - we need to handle its dependencies
            kodi_helper_path = os.path.join(lib_dir, 'kodi_helper.py')
            spec = importlib.util.spec_from_file_location("kodi_helper", kodi_helper_path)
            kodi_helper_module = importlib.util.module_from_spec(spec)
            
            # Pre-import dependencies for kodi_helper
            utils_path = os.path.join(lib_dir, 'utils.py')
            spec_utils = importlib.util.spec_from_file_location("utils", utils_path)
            utils_module = importlib.util.module_from_spec(spec_utils)
            spec_utils.loader.exec_module(utils_module)
            sys.modules['utils'] = utils_module
            
            jsonrpc_path = os.path.join(lib_dir, 'jsonrpc_manager.py')
            spec_jsonrpc = importlib.util.spec_from_file_location("jsonrpc_manager", jsonrpc_path)
            jsonrpc_module = importlib.util.module_from_spec(spec_jsonrpc)
            spec_jsonrpc.loader.exec_module(jsonrpc_module)
            sys.modules['jsonrpc_manager'] = jsonrpc_module
            
            # Now load kodi_helper
            spec.loader.exec_module(kodi_helper_module)
            
            # Import window_main
            window_main_path = os.path.join(lib_dir, 'window_main.py')
            spec = importlib.util.spec_from_file_location("window_main", window_main_path)
            window_main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(window_main_module)
            
            return (
                addon_ref_module.get_addon,
                kodi_helper_module.KodiHelper,
                window_main_module.MainWindow
            )
            
        except Exception as fallback_error:
            xbmc.log(f"LibraryGenie: All import methods failed: {str(fallback_error)}", xbmc.LOGERROR)
            raise fallback_error

def main():
    """Main entry point for context menu actions"""
    try:
        xbmc.log("LibraryGenie: Context menu script started", xbmc.LOGINFO)
        
        # Import required modules
        get_addon, KodiHelper, MainWindow = safe_import_modules()
        
        addon = get_addon()
        if not addon:
            xbmc.log("LibraryGenie: Failed to get addon instance", xbmc.LOGERROR)
            return

        # Get the current item's information
        kodi_helper = KodiHelper()
        item_info = kodi_helper.get_focused_item_details()
        
        if not item_info:
            xbmc.log("LibraryGenie: No item information found", xbmc.LOGWARNING)
            xbmcgui.Dialog().notification("LibraryGenie", "No item selected", xbmcgui.NOTIFICATION_WARNING, 2000)
            return

        xbmc.log(f"LibraryGenie: Got item info for: {item_info.get('title', 'Unknown')}", xbmc.LOGINFO)

        # Launch the main window with the item information
        window = MainWindow(item_info, f"LibraryGenie - {item_info.get('title', 'Item')}")
        window.doModal()
        del window

    except Exception as e:
        xbmc.log(f"LibraryGenie: Context menu error: {str(e)}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"LibraryGenie: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("LibraryGenie", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

if __name__ == '__main__':
    main()
