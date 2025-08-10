import sys
import os

# Add the resources/lib directory to the Python path
addon_path = os.path.dirname(os.path.dirname(__file__))
lib_path = os.path.join(addon_path, 'lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

import xbmc
import xbmcgui
from addon_ref import get_addon
from kodi_helper import KodiHelper
from window_main import MainWindow

def main():
    """Main entry point for context menu actions"""
    try:
        addon = get_addon()
        if not addon:
            xbmc.log("LibraryGenie: Failed to get addon instance", xbmc.LOGERROR)
            return

        # Get the selected item's database ID
        info_tag = xbmcgui.Window(10000).getProperty('selected_item')
        if not info_tag:
            xbmc.log("LibraryGenie: No selected item found", xbmc.LOGWARNING)
            return

        # Launch the main window
        window = MainWindow()
        window.doModal()
        del window

    except Exception as e:
        xbmc.log(f"LibraryGenie: Context menu error: {str(e)}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"LibraryGenie: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)

if __name__ == '__main__':
    main()