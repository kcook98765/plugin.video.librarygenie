""" /main.py """
import os
import sys
import urllib.parse # Import urllib.parse

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

from resources.lib.addon_helper import run_addon
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib import utils

# Global variable to track initialization
_initialized = False

def main():
    """Main addon entry point"""
    utils.log("=== LibraryGenie addon starting ===", "INFO")
    utils.log(f"Command line args: {sys.argv}", "DEBUG")

    try:
        utils.log("Initializing addon components", "DEBUG")

        # Check if this is a program addon launch (direct launch without context)
        if len(sys.argv) == 1 or (len(sys.argv) >= 2 and 'action=program' in str(sys.argv)):
            utils.log("Program addon launch detected - showing main window", "DEBUG")
            from resources.lib.window_main import MainWindow
            
            # Create empty item info for program launch
            item_info = {
                'title': 'LibraryGenie Browser',
                'is_playable': False,
                'kodi_id': 0
            }
            
            main_window = MainWindow(item_info, "LibraryGenie - Browse Lists")
            main_window.doModal()
            del main_window
            return

        # Run the addon
        utils.log("Calling run_addon()", "DEBUG")
        run_addon()

        # Ensure Search History folder exists
        utils.log("Setting up configuration and database", "DEBUG")
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        utils.log("Search History folder initialization complete", "DEBUG")

        utils.log("=== LibraryGenie addon startup complete ===", "INFO")
    except Exception as e:
        utils.log(f"CRITICAL ERROR in main(): {str(e)}", "ERROR")
        import traceback
        utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

if __name__ == '__main__':
    main()