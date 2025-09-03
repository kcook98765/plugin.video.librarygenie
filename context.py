
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Context Menu Script
Handles context menu actions for adding media to lists
"""

import sys
import xbmc
import xbmcaddon
import xbmcgui


def main():
    """Main context menu handler"""
    try:
        addon = xbmcaddon.Addon()
        
        # Get the currently playing/selected item info
        if xbmc.getCondVisibility('Container.Content(movies)'):
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            dbtype = 'movie'
        elif xbmc.getCondVisibility('Container.Content(episodes)'):
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            dbtype = 'episode'
        elif xbmc.getCondVisibility('Container.Content(musicvideos)'):
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            dbtype = 'musicvideo'
        else:
            # Try to get from player if something is playing
            if xbmc.getCondVisibility('Player.HasMedia'):
                dbid = xbmc.getInfoLabel('Player.Art(dbid)')
                dbtype = xbmc.getInfoLabel('Player.Art(type)')
            else:
                xbmcgui.Dialog().notification(
                    "LibraryGenie", 
                    "No supported media item found", 
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return
        
        if not dbid or dbid == '0':
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                "Unable to identify media item", 
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            return
        
        # Launch the add to list dialog
        plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"
        xbmc.executebuiltin(f"RunPlugin({plugin_url})")
        
    except Exception as e:
        xbmc.log(f"LibraryGenie context menu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie", 
            "Context menu error occurred", 
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


if __name__ == '__main__':
    main()
