""" /main.py """
import os
import sys

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

from resources.lib.addon_helper import run_addon
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib import utils

def main():
    """Main addon entry point"""
    # Ensure Search History folder exists
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        utils.log("Search History folder initialization complete", "DEBUG")
    except Exception as e:
        utils.log(f"Error initializing Search History folder: {str(e)}", "ERROR")

if __name__ == '__main__':
    run_addon()