"""Folder and list management utilities for LibraryGenie addon"""

import xbmc
import xbmcgui
from resources.lib.utils import utils
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.config.config_manager import Config

class FolderListManager:
    """Manages folder and list operations"""

    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)

    def create_new_folder_at_root(self):
        """Create a new folder at root level"""
        self.create_new_folder(None)

    def create_new_folder(self, parent_folder_id):
        """Create a new folder in the specified parent folder (None for root)"""
        try:
            # Check folder depth limit BEFORE asking for folder name
            if parent_folder_id is not None:
                current_depth = self.db_manager.get_folder_depth(parent_folder_id)
                max_depth = self.config.max_folder_depth - 1  # -1 because we're adding a new level

                if current_depth >= max_depth:
                    # Show limit reached notification without override option
                    xbmcgui.Dialog().ok(
                        'Folder Depth Limit Reached',
                        f'Maximum folder depth of {self.config.max_folder_depth} has been reached.\n\n'
                        f'Current location depth: {current_depth + 1}\n'
                        f'Maximum allowed depth: {self.config.max_folder_depth}\n\n'
                        'Please adjust the "Maximum Folder Depth" setting to allow deeper nesting.'
                    )
                    return

            # Only ask for name if depth check passed
            name = xbmcgui.Dialog().input('New folder name', type=xbmcgui.INPUT_ALPHANUM)
            if not name:
                return

            # Create in specified parent folder
            self.db_manager.insert_folder(name, parent_folder_id)
            xbmcgui.Dialog().notification('LibraryGenie', f'Folder "{name}" created')
            xbmc.executebuiltin('Container.Refresh')
        except Exception as e:
            utils.log(f"Error creating folder: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create folder')

    def clear_all_local_data(self):
        """Clear all local database data"""
        utils.log("=== CLEAR_ALL_LOCAL_DATA: ABOUT TO SHOW CONFIRMATION MODAL ===", "DEBUG")
        if not xbmcgui.Dialog().yesno('Clear All Local Data', 'This will delete all lists, folders, and search history.\n\nAre you sure?'):
            utils.log("=== CLEAR_ALL_LOCAL_DATA: CONFIRMATION MODAL CLOSED - CANCELLED ===", "DEBUG")
            return
        utils.log("=== CLEAR_ALL_LOCAL_DATA: CONFIRMATION MODAL CLOSED - CONFIRMED ===", "DEBUG")

        try:
            # Clear user-created content and media cache
            self.db_manager.delete_data('list_items', '1=1')
            self.db_manager.delete_data('lists', '1=1')
            self.db_manager.delete_data('folders', '1=1')
            self.db_manager.delete_data('media_items', '1=1')
            # Preserve imdb_exports - they contain valuable library reference data

            # Recreate protected folders
            search_folder_id = self.db_manager.ensure_folder_exists("Search History", None)
            imported_lists_folder_id = self.db_manager.ensure_folder_exists("Imported Lists", None)

            utils.log("=== CLEAR_ALL_LOCAL_DATA: ABOUT TO SHOW SUCCESS NOTIFICATION ===", "DEBUG")
            xbmcgui.Dialog().notification('LibraryGenie', 'All local data cleared')
            utils.log("=== CLEAR_ALL_LOCAL_DATA: SUCCESS NOTIFICATION CLOSED ===", "DEBUG")
            xbmc.executebuiltin('Container.Refresh')
        except Exception as e:
            utils.log(f"Error clearing local data: {str(e)}", "ERROR")
            utils.log("=== CLEAR_ALL_LOCAL_DATA: ABOUT TO SHOW ERROR NOTIFICATION ===", "DEBUG")
            xbmcgui.Dialog().notification('LibraryGenie', 'Failed to clear data')
            utils.log("=== CLEAR_ALL_LOCAL_DATA: ERROR NOTIFICATION CLOSED ===", "DEBUG")

    def browse_search_history(self):
        """Browse the search history by navigating to the Search History folder"""
        utils.log("=== BROWSE_SEARCH_HISTORY FUNCTION CALLED ===", "INFO")
        try:
            # Get Search History folder ID
            search_history_folder_id = self.db_manager.get_folder_id_by_name("Search History")
            if not search_history_folder_id:
                utils.log("Error: Search History folder not found.", "ERROR")
                xbmcgui.Dialog().notification('LibraryGenie', 'Search History folder not found', xbmcgui.NOTIFICATION_ERROR)
                return

            utils.log(f"Found Search History folder with ID: {search_history_folder_id}", "DEBUG")

            # Navigate to the Search History folder using the existing browse_folder function
            from resources.lib.kodi.url_builder import build_plugin_url
            plugin_url = build_plugin_url({
                'action': 'browse_folder',
                'folder_id': search_history_folder_id,
                'view': 'folder'
            })

            utils.log(f"Navigating to Search History folder: {plugin_url}", "DEBUG")

            # Use Container.Update to navigate to the folder
            xbmc.executebuiltin(f'Container.Update({plugin_url})')

            utils.log("=== BROWSE_SEARCH_HISTORY FUNCTION COMPLETE ===", "INFO")

        except Exception as e:
            utils.log(f"Error in browse_search_history: {e}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', 'Error accessing search history', xbmcgui.NOTIFICATION_ERROR)

# Global instance
_folder_list_manager = None

def get_folder_list_manager():
    """Get the singleton folder list manager instance"""
    global _folder_list_manager
    if _folder_list_manager is None:
        _folder_list_manager = FolderListManager()
    return _folder_list_manager