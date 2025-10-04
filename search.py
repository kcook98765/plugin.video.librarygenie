#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Program Entry Point
Launches the LibraryGenie search directly when run from Kodi's Programs menu
Also delegates to utilities.py when called with action parameters from settings.xml
"""

import sys
import xbmc

# Check if called with parameters (from settings.xml RunScript)
if len(sys.argv) > 1:
    # Delegate to utilities handler for settings actions
    import utilities
    utilities.main()
else:
    # Launch search by opening Videos window with plugin URL
    # ActivateWindow creates proper plugin context (unlike RunPlugin from Programs)
    xbmc.executebuiltin('ActivateWindow(videos,plugin://plugin.video.librarygenie/?action=prompt_and_search,return)')
