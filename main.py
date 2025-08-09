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