""" /resources/lib/addon_helper.py """
import xbmc
import xbmcgui
from resources.lib.window_main import MainWindow
from resources.lib import utils

def run_addon():
    """Main entry point for the addon"""
    utils.log("Running addon...", "DEBUG")

    try:
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

        # Create and show the main window
        window = MainWindow(item_info)
        window.doModal()
        del window

    except Exception as e:
        utils.log(f"Error running addon: {str(e)}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)