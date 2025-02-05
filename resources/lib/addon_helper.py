
""" /resources/lib/addon_helper.py """
import sys
import urllib.parse
import xbmc
import xbmcgui
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib.kodi_helper import KodiHelper
from resources.lib.window_main import MainWindow
from resources.lib import utils

def run_addon():
    """Main entry point for the addon"""
    utils.log("Running addon...", "DEBUG")

    try:
        args = sys.argv[2][1:] if len(sys.argv) > 2 else ""
        params = urllib.parse.parse_qs(args)
        action = params.get('action', [None])[0]
        listitem_context = xbmc.getCondVisibility('Container.Content(movies)') or xbmc.getCondVisibility('Container.Content(episodes)')

        # Initialize helpers
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        kodi_helper = KodiHelper()

        # Handle context menu vs direct launch
        if listitem_context and not action:
            # Context menu on media item - show options window
            item_info = {
                'title': xbmc.getInfoLabel('ListItem.Title'),
                'kodi_id': xbmc.getInfoLabel('ListItem.DBID'),
                'is_playable': xbmc.getCondVisibility('ListItem.IsPlayable') == 1,
                'art': {
                    'thumb': xbmc.getInfoLabel('ListItem.Art(thumb)'),
                    'poster': xbmc.getInfoLabel('ListItem.Art(poster)'),
                    'banner': xbmc.getInfoLabel('ListItem.Art(banner)'),
                    'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)')
                }
            }
            window = MainWindow(item_info)
            window.doModal()
            del window
            return
        elif not action:
            # Direct addon launch - show root directory
            root_folders = db_manager.fetch_folders(None)  # Get root folders
            root_lists = db_manager.fetch_lists(None)  # Get root lists 
            kodi_helper.list_folders_and_lists(root_folders, root_lists)
            return

        # Handle context menu or other actions
        if action == "show_main_window":
            # Get basic info about currently selected item
            item_info = {
                'title': xbmc.getInfoLabel('ListItem.Title'),
                'kodi_id': xbmc.getInfoLabel('ListItem.DBID'),
                'is_playable': xbmc.getCondVisibility('ListItem.IsPlayable') == 1,
                'art': {
                    'thumb': xbmc.getInfoLabel('ListItem.Art(thumb)'),
                    'poster': xbmc.getInfoLabel('ListItem.Art(poster)'),
                    'banner': xbmc.getInfoLabel('ListItem.Art(banner)'),
                    'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)')
                }
            }
            window = MainWindow(item_info)
            window.doModal()
            del window
        elif action == "show_folder":
            folder_id = int(params.get('folder_id', [0])[0])
            folders = db_manager.fetch_folders(folder_id)
            lists = db_manager.fetch_lists(folder_id)
            kodi_helper.list_folders_and_lists(folders, lists)
        elif action == "show_list":
            list_id = int(params.get('list_id', [0])[0])
            items = db_manager.fetch_list_items(list_id)
            kodi_helper.list_items(items)

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)
