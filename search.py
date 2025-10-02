#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Program Entry Point
Launches the LibraryGenie search directly when run from Kodi's Programs menu
"""

import xbmc

# Launch search menu action via plugin URL
# This provides a direct entry point for users to access search from Programs
xbmc.executebuiltin('RunPlugin(plugin://plugin.video.librarygenie/?action=search_menu)')
