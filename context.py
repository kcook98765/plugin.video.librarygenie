#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Context Menu Script
Handles context menu actions for adding media to lists
"""

import xbmc
import xbmcaddon
import xbmcgui
import urllib.parse
from typing import List, Union


def main():
    """Main context menu handler"""
    try:
        addon = xbmcaddon.Addon()

        # Get the currently playing/selected item info
        if xbmc.getCondVisibility('Container.Content(movies)'):
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            dbtype = 'movie'
            # Handle library items
            if dbid and dbid != '0':
                # Check if quick-add is enabled and has a default list configured
                quick_add_enabled = addon.getSettingBool('quick_add_enabled')
                default_list_id = addon.getSetting('default_list_id')

                if quick_add_enabled and default_list_id:
                    # Show context menu with both quick-add and regular add options
                    options = [
                        xbmcgui.ListItem(label="Quick Add to Default List"),
                        xbmcgui.ListItem(label="Add to List...")
                    ]

                    dialog = xbmcgui.Dialog()
                    selected = dialog.select("Add to List", options)

                    if selected == 0:  # Quick add
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=quick_add&dbtype={dbtype}&dbid={dbid}"
                    elif selected == 1:  # Regular add
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"
                    else:
                        return  # User cancelled
                else:
                    # Standard add to list dialog
                    plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"

                xbmc.executebuiltin(f"RunPlugin({plugin_url})")
                return
            else:
                # Handle plugin/external movie items
                _handle_external_item(addon)
                return

        elif xbmc.getCondVisibility('Container.Content(episodes)'):
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            dbtype = 'episode'
            # Handle library episodes
            if dbid and dbid != '0':
                # Check if quick-add is enabled and has a default list configured
                quick_add_enabled = addon.getSettingBool('quick_add_enabled')
                default_list_id = addon.getSetting('default_list_id')

                if quick_add_enabled and default_list_id:
                    # Show context menu with both quick-add and regular add options
                    options = [
                        xbmcgui.ListItem(label="Quick Add to Default List"),
                        xbmcgui.ListItem(label="Add to List...")
                    ]

                    dialog = xbmcgui.Dialog()
                    selected = dialog.select("Add to List", options)

                    if selected == 0:  # Quick add
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=quick_add&dbtype={dbtype}&dbid={dbid}"
                    elif selected == 1:  # Regular add
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"
                    else:
                        return  # User cancelled
                else:
                    # Standard add to list dialog
                    plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"

                xbmc.executebuiltin(f"RunPlugin({plugin_url})")
                return
            else:
                # Handle plugin/external episode items
                _handle_external_item(addon)
                return

        elif xbmc.getCondVisibility('Container.Content(musicvideos)'):
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            dbtype = 'musicvideo'
            # Handle library music videos
            if dbid and dbid != '0':
                # Check if quick-add is enabled and has a default list configured
                quick_add_enabled = addon.getSettingBool('quick_add_enabled')
                default_list_id = addon.getSetting('default_list_id')

                if quick_add_enabled and default_list_id:
                    # Show context menu with both quick-add and regular add options
                    options = [
                        xbmcgui.ListItem(label="Quick Add to Default List"),
                        xbmcgui.ListItem(label="Add to List...")
                    ]

                    dialog = xbmcgui.Dialog()
                    selected = dialog.select("Add to List", options)

                    if selected == 0:  # Quick add
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=quick_add&dbtype={dbtype}&dbid={dbid}"
                    elif selected == 1:  # Regular add
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"
                    else:
                        return  # User cancelled
                else:
                    # Standard add to list dialog
                    plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"

                xbmc.executebuiltin(f"RunPlugin({plugin_url})")
                return
            else:
                # Handle plugin/external music video items
                _handle_external_item(addon)
                return

        else:
            # Try to get from player if something is playing
            if xbmc.getCondVisibility('Player.HasMedia'):
                dbid = xbmc.getInfoLabel('Player.Art(dbid)')
                dbtype = xbmc.getInfoLabel('Player.Art(type)')
                if dbid and dbid != '0':
                    # Check if quick-add is enabled and has a default list configured
                    quick_add_enabled = addon.getSettingBool('quick_add_enabled')
                    default_list_id = addon.getSetting('default_list_id')

                    if quick_add_enabled and default_list_id:
                        # Show context menu with both quick-add and regular add options
                        options = [
                            xbmcgui.ListItem(label="Quick Add to Default List"),
                            xbmcgui.ListItem(label="Add to List...")
                        ]

                        dialog = xbmcgui.Dialog()
                        selected = dialog.select("Add to List", options)

                        if selected == 0:  # Quick add
                            plugin_url = f"plugin://plugin.video.librarygenie/?action=quick_add&dbtype={dbtype}&dbid={dbid}"
                        elif selected == 1:  # Regular add
                            plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"
                        else:
                            return  # User cancelled
                    else:
                        # Standard add to list dialog
                        plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&dbtype={dbtype}&dbid={dbid}"

                    xbmc.executebuiltin(f"RunPlugin({plugin_url})")
                    return

            # Check if current item is a plugin item
            file_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
            if file_path and file_path.startswith('plugin://'):
                _handle_external_item(addon)
                return

            # No supported item found
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "No supported media item found",
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            return

    except Exception as e:
        xbmc.log(f"LibraryGenie context menu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Context menu error occurred",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _handle_external_item(addon):
    """Handle plugin/external items by gathering available metadata"""
    try:
        # Gather all available metadata from the focused item
        item_data = {
            'title': xbmc.getInfoLabel('ListItem.Title') or xbmc.getInfoLabel('ListItem.Label'),
            'originaltitle': xbmc.getInfoLabel('ListItem.OriginalTitle'),
            'year': xbmc.getInfoLabel('ListItem.Year'),
            'plot': xbmc.getInfoLabel('ListItem.Plot') or xbmc.getInfoLabel('ListItem.PlotOutline'),
            'rating': xbmc.getInfoLabel('ListItem.Rating'),
            'votes': xbmc.getInfoLabel('ListItem.Votes'),
            'genre': xbmc.getInfoLabel('ListItem.Genre'),
            'director': xbmc.getInfoLabel('ListItem.Director'),
            'studio': xbmc.getInfoLabel('ListItem.Studio'),
            'country': xbmc.getInfoLabel('ListItem.Country'),
            'mpaa': xbmc.getInfoLabel('ListItem.MPAA'),
            'runtime': xbmc.getInfoLabel('ListItem.Duration'),
            'premiered': xbmc.getInfoLabel('ListItem.Premiered'),
            'playcount': xbmc.getInfoLabel('ListItem.PlayCount'),
            'lastplayed': xbmc.getInfoLabel('ListItem.LastPlayed'),
            'file_path': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'media_type': 'movie'  # Default, will be refined below
        }

        # Try to determine media type from context or file path
        if xbmc.getCondVisibility('Container.Content(episodes)'):
            item_data['media_type'] = 'episode'
            item_data['tvshowtitle'] = xbmc.getInfoLabel('ListItem.TVShowTitle')
            item_data['season'] = xbmc.getInfoLabel('ListItem.Season')
            item_data['episode'] = xbmc.getInfoLabel('ListItem.Episode')
            item_data['aired'] = xbmc.getInfoLabel('ListItem.Aired')
        elif xbmc.getCondVisibility('Container.Content(musicvideos)'):
            item_data['media_type'] = 'musicvideo'
            item_data['artist'] = xbmc.getInfoLabel('ListItem.Artist')
            item_data['album'] = xbmc.getInfoLabel('ListItem.Album')

        # Gather artwork
        item_data['poster'] = xbmc.getInfoLabel('ListItem.Art(poster)') or xbmc.getInfoLabel('ListItem.Thumb')
        item_data['fanart'] = xbmc.getInfoLabel('ListItem.Art(fanart)')
        item_data['thumb'] = xbmc.getInfoLabel('ListItem.Art(thumb)')
        item_data['banner'] = xbmc.getInfoLabel('ListItem.Art(banner)')
        item_data['clearlogo'] = xbmc.getInfoLabel('ListItem.Art(clearlogo)')

        # Try to get IMDb ID or other unique identifiers
        item_data['imdbnumber'] = xbmc.getInfoLabel('ListItem.IMDBNumber')

        # Clean up empty values and convert numeric fields
        cleaned_data = {}
        for key, value in item_data.items():
            if value and value.strip():
                if key in ('year', 'season', 'episode', 'playcount'):
                    try:
                        cleaned_data[key] = int(value)
                    except (ValueError, TypeError):
                        pass
                elif key in ('rating',):
                    try:
                        cleaned_data[key] = float(value)
                    except (ValueError, TypeError):
                        pass
                else:
                    cleaned_data[key] = value.strip()

        # Validate we have minimum required data
        if not cleaned_data.get('title'):
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Unable to identify item title",
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            return

        # Build URL-encoded data string for external item
        url_params = []
        for key, value in cleaned_data.items():
            if value is not None:
                url_params.append(f"{key}={urllib.parse.quote_plus(str(value))}")

        external_data = "&".join(url_params)

        # Launch add to list for external item
        plugin_url = f"plugin://plugin.video.librarygenie/?action=add_to_list&external_item=true&{external_data}"
        xbmc.executebuiltin(f"RunPlugin({plugin_url})")

    except Exception as e:
        xbmc.log(f"LibraryGenie external item context error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Failed to process external item",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


if __name__ == '__main__':
    main()