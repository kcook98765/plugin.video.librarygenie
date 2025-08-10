
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
        
        # Fallback to file-based imports with source code modification
        try:
            import importlib.util
            
            # Import addon_ref first
            addon_ref_path = os.path.join(lib_dir, 'addon_ref.py')
            spec = importlib.util.spec_from_file_location("addon_ref", addon_ref_path)
            addon_ref_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(addon_ref_module)
            sys.modules['addon_ref'] = addon_ref_module
            
            # Import utils
            utils_path = os.path.join(lib_dir, 'utils.py')
            spec_utils = importlib.util.spec_from_file_location("utils", utils_path)
            utils_module = importlib.util.module_from_spec(spec_utils)
            spec_utils.loader.exec_module(utils_module)
            sys.modules['utils'] = utils_module
            
            # Import jsonrpc_manager
            jsonrpc_path = os.path.join(lib_dir, 'jsonrpc_manager.py')
            spec_jsonrpc = importlib.util.spec_from_file_location("jsonrpc_manager", jsonrpc_path)
            jsonrpc_module = importlib.util.module_from_spec(spec_jsonrpc)
            spec_jsonrpc.loader.exec_module(jsonrpc_module)
            sys.modules['jsonrpc_manager'] = jsonrpc_module
            
            # For kodi_helper, we need to modify the source to remove relative imports
            kodi_helper_path = os.path.join(lib_dir, 'kodi_helper.py')
            with open(kodi_helper_path, 'r', encoding='utf-8') as f:
                kodi_helper_source = f.read()
            
            # Replace relative imports with absolute imports
            modified_source = kodi_helper_source.replace(
                'from .addon_ref import get_addon',
                'from addon_ref import get_addon'
            ).replace(
                'from . import utils',
                'import utils'
            ).replace(
                'from .jsonrpc_manager import JSONRPCManager',
                'from jsonrpc_manager import JSONRPCManager'
            )
            
            # Compile and execute the modified source
            code = compile(modified_source, kodi_helper_path, 'exec')
            kodi_helper_module = importlib.util.module_from_spec(
                importlib.util.spec_from_loader('kodi_helper', loader=None)
            )
            kodi_helper_module.__file__ = kodi_helper_path
            sys.modules['kodi_helper'] = kodi_helper_module
            exec(code, kodi_helper_module.__dict__)
            
            # Import window_main with similar approach
            window_main_path = os.path.join(lib_dir, 'window_main.py')
            with open(window_main_path, 'r', encoding='utf-8') as f:
                window_main_source = f.read()
            
            # Replace relative imports in window_main
            modified_main_source = window_main_source
            relative_imports = [
                ('from .database_manager import DatabaseManager', 'from database_manager import DatabaseManager'),
                ('from .config_manager import Config', 'from config_manager import Config'),
                ('from . import utils', 'import utils'),
                ('from .kodi_helper import KodiHelper', 'from kodi_helper import KodiHelper'),
                ('from .window_base import BaseWindow', 'from window_base import BaseWindow'),
                ('from .window_search import SearchWindow', 'from window_search import SearchWindow'),
                ('from .window_list import ListWindow', 'from window_list import ListWindow'),
                ('from .window_genie import GenieWindow', 'from window_genie import GenieWindow')
            ]
            
            for old_import, new_import in relative_imports:
                modified_main_source = modified_main_source.replace(old_import, new_import)
            
            # Import dependencies for window_main
            deps_to_import = ['database_manager', 'config_manager', 'window_base', 'window_search', 'window_list', 'window_genie']
            for dep in deps_to_import:
                try:
                    dep_path = os.path.join(lib_dir, f'{dep}.py')
                    if os.path.exists(dep_path):
                        with open(dep_path, 'r', encoding='utf-8') as f:
                            dep_source = f.read()
                        
                        # Fix relative imports in dependencies
                        dep_source = dep_source.replace('from .', 'from ').replace('from . import', 'import')
                        
                        dep_code = compile(dep_source, dep_path, 'exec')
                        dep_module = importlib.util.module_from_spec(
                            importlib.util.spec_from_loader(dep, loader=None)
                        )
                        dep_module.__file__ = dep_path
                        sys.modules[dep] = dep_module
                        exec(dep_code, dep_module.__dict__)
                except Exception as dep_error:
                    xbmc.log(f"LibraryGenie: Warning loading dependency {dep}: {str(dep_error)}", xbmc.LOGWARNING)
            
            # Compile and execute window_main
            main_code = compile(modified_main_source, window_main_path, 'exec')
            window_main_module = importlib.util.module_from_spec(
                importlib.util.spec_from_loader('window_main', loader=None)
            )
            window_main_module.__file__ = window_main_path
            sys.modules['window_main'] = window_main_module
            exec(main_code, window_main_module.__dict__)
            
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
