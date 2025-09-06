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
import urllib.parse
from typing import List, Union

# Import localization module
try:
    from resources.lib.ui.localization import L
except ImportError:
    # Fallback for simple string retrieval
    def L(string_id, fallback=""):
        return fallback or f"String_{string_id}"


def main():
    """Main context menu handler"""
    try:
        # Debug: Log that context menu was triggered
        xbmc.log("LibraryGenie: Context menu script triggered", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: Context script sys.argv: {sys.argv}", xbmc.LOGINFO)
        
        addon = xbmcaddon.Addon()

        # Debug: Log current item info
        dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
        file_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
        xbmc.log(f"LibraryGenie: Context - DBTYPE={dbtype}, FilePath={file_path}", xbmc.LOGINFO)
        
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
                        L(37007),  # "Quick Add to Default List"
                        L(30012)   # "Add to List..."
                    ]

                    dialog = xbmcgui.Dialog()
                    selected = dialog.select(L(30012), list(options))  # "Add to List"

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
                        L(37007),  # "Quick Add to Default List"
                        L(30012)   # "Add to List..."
                    ]

                    dialog = xbmcgui.Dialog()
                    selected = dialog.select(L(30012), list(options))  # "Add to List"

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
                        L(37007),  # "Quick Add to Default List"
                        L(30012)   # "Add to List..."
                    ]

                    dialog = xbmcgui.Dialog()
                    selected = dialog.select(L(30012), list(options))  # "Add to List"

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
                            L(37007),  # "Quick Add to Default List"
                            L(30012)   # "Add to List..."
                        ]

                        dialog = xbmcgui.Dialog()
                        selected = dialog.select(L(30012), list(options))  # "Add to List"

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
                # Check if this is a LibraryGenie item
                if file_path.startswith('plugin://plugin.video.librarygenie/'):
                    _handle_librarygenie_item(addon)
                    return
                else:
                    _handle_external_item(addon)
                    return

            # No supported item found
            xbmcgui.Dialog().notification(
                L(30001),  # "LibraryGenie"
                L(30002),  # "No supported media item found"
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            return

    except Exception as e:
        xbmc.log(f"LibraryGenie context menu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            L(30001),  # "LibraryGenie"
            L(30003),  # "Context menu error occurred"
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _handle_librarygenie_item(addon):
    """Handle LibraryGenie items with dynamic context options"""
    try:
        # Get item metadata from ListItem properties
        media_item_id = xbmc.getInfoLabel('ListItem.Property(media_item_id)')
        list_id = xbmc.getInfoLabel('ListItem.Property(list_id)')
        item_title = xbmc.getInfoLabel('ListItem.Title') or xbmc.getInfoLabel('ListItem.Label')

        if not media_item_id:
            xbmcgui.Dialog().notification(
                L(30001),  # "LibraryGenie"
                L(30004),  # "No item ID found"
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            return

        # Build dynamic options based on context and settings
        options = []
        actions = []

        # Check if quick-add is enabled and has a default list configured
        quick_add_enabled = addon.getSettingBool('quick_add_enabled')
        default_list_id = addon.getSetting('default_list_id')

        # Add to List option (always available)
        options.append(L(30012))  # "Add to List..."
        actions.append(f"plugin://plugin.video.librarygenie/?action=add_to_list&media_item_id={media_item_id}")

        # Quick Add option (if configured)
        if quick_add_enabled and default_list_id:
            options.append(L(37007))  # "Quick Add to Default List"
            actions.append(f"plugin://plugin.video.librarygenie/?action=quick_add&media_item_id={media_item_id}")

        # Remove from List option (if we're in a list context)
        if list_id:
            options.append(L(30013))  # "Remove from List"
            actions.append(f"plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={list_id}&item_id={media_item_id}")

        # Show context menu if we have options
        if options:
            dialog = xbmcgui.Dialog()
            selected = dialog.select(L(30001), options)  # "LibraryGenie"

            if selected >= 0:
                plugin_url = actions[selected]
                xbmc.executebuiltin(f"RunPlugin({plugin_url})")
        else:
            xbmcgui.Dialog().notification(
                L(30001),  # "LibraryGenie"
                L(30005),  # "No actions available for this item"
                xbmcgui.NOTIFICATION_INFO,
                3000
            )

    except Exception as e:
        xbmc.log(f"LibraryGenie item context error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            L(30001),  # "LibraryGenie"
            L(30006),  # "Failed to process LibraryGenie item"
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
                L(30001),  # "LibraryGenie"
                L(30007),  # "Unable to identify item title"
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
            L(30001),  # "LibraryGenie"
            L(30008),  # "Failed to process external item"
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


if __name__ == '__main__':
    main()