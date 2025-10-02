#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Program Entry Point
Launches the LibraryGenie search directly when run from Kodi's Programs menu
"""

import xbmc

# Launch search by opening Videos window with plugin URL
# ActivateWindow creates proper plugin context (unlike RunPlugin from Programs)
xbmc.executebuiltin('ActivateWindow(videos,plugin://plugin.video.librarygenie/?action=prompt_and_search,return)')
