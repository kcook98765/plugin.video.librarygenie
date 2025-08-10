
import sys
import os

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager

def main():
    """Launcher entry point for direct GUI access"""
    try:
        utils.log("=== LibraryGenie launcher starting ===", "INFO")
        
        # Initialize components
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        
        # Import and launch main window
        from resources.lib.window_main import MainWindow
        
        # Create item info for browser mode
        item_info = {
            'title': 'LibraryGenie Browser',
            'plot': 'Browse and manage your movie lists and folders',
            'is_playable': False,
            'kodi_id': 0
        }
        
        main_window = MainWindow(item_info, "LibraryGenie - Browse Lists")
        main_window.doModal()
        del main_window
        
        utils.log("=== LibraryGenie launcher complete ===", "INFO")
    except Exception as e:
        utils.log(f"CRITICAL ERROR in launcher: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

if __name__ == '__main__':
    main()
