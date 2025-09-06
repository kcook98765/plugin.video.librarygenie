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
    from resources.lib.ui.localization import L as _L

    def L(string_id):
        """Get localized string with better error handling"""
        try:
            result = _L(string_id)
            # Return empty string if localization failed or returned a malformed string
            if not result or result.startswith('string_') or result.startswith('String_'):
                return ""
            return result
        except Exception:
            return ""

except ImportError:
    # Fallback for simple string retrieval
    def L(string_id):
        return ""


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

        # Always show LibraryGenie submenu with conditional options
        _show_librarygenie_menu(addon)

    except Exception as e:
        xbmc.log(f"LibraryGenie context menu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Context menu error occurred",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _show_librarygenie_menu(addon):
    """Show LibraryGenie submenu with conditional options"""
    try:
        # Build options list - Search is always available
        options = []
        actions = []

        # Always add Search option
        search_label = L(33000)
        if not search_label or search_label.startswith('string_'):
            search_label = "Search"
        options.append(search_label)
        actions.append("search")

        # Check what type of content we're dealing with
        dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
        dbid = xbmc.getInfoLabel('ListItem.DBID')
        file_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')

        # Add content-specific options based on context
        if xbmc.getCondVisibility('Container.Content(movies)') or dbtype == 'movie':
            if dbid and dbid != '0':
                # Library movie - add list management options
                _add_library_movie_options(options, actions, addon, dbtype, dbid)
            else:
                # External/plugin movie - add external item options
                _add_external_item_options(options, actions, addon)

        elif xbmc.getCondVisibility('Container.Content(episodes)') or dbtype == 'episode':
            if dbid and dbid != '0':
                # Library episode - add list management options
                _add_library_episode_options(options, actions, addon, dbtype, dbid)
            else:
                # External/plugin episode - add external item options
                _add_external_item_options(options, actions, addon)

        elif xbmc.getCondVisibility('Container.Content(musicvideos)') or dbtype == 'musicvideo':
            if dbid and dbid != '0':
                # Library music video - add list management options
                _add_library_musicvideo_options(options, actions, addon, dbtype, dbid)
            else:
                # External/plugin music video - add external item options
                _add_external_item_options(options, actions, addon)

        elif file_path and file_path.startswith('plugin://plugin.video.librarygenie/'):
            # LibraryGenie item - add LibraryGenie-specific options
            _add_librarygenie_item_options(options, actions, addon)

        elif file_path and file_path.startswith('plugin://'):
            # Other plugin item - add external item options
            _add_external_item_options(options, actions, addon)

        else:
            # Unknown/unsupported item - only show search
            pass

        # Show the menu
        if len(options) > 1:
            dialog = xbmcgui.Dialog()
            selected = dialog.select("LibraryGenie", options)

            if selected >= 0:
                _execute_action(actions[selected], addon)
        else:
            # Only search available, execute directly
            _execute_action("search", addon)

    except Exception as e:
        xbmc.log(f"LibraryGenie submenu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Menu error occurred",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _add_library_movie_options(options, actions, addon, dbtype, dbid):
    """Add options for library movies"""
    # Check if quick-add is enabled and has a default list configured
    quick_add_enabled = addon.getSettingBool('quick_add_enabled')
    default_list_id = addon.getSetting('default_list_id')

    if quick_add_enabled and default_list_id:
        quick_add_label = L(31001)  # "Quick Add to Default"
        options.append(quick_add_label)
        actions.append(f"quick_add&dbtype={dbtype}&dbid={dbid}")

    add_to_list_label = L(31000)  # "Add to List..."
    options.append(add_to_list_label)
    actions.append(f"add_to_list&dbtype={dbtype}&dbid={dbid}")


def _add_library_episode_options(options, actions, addon, dbtype, dbid):
    """Add options for library episodes"""
    # Same logic as movies but for episodes
    quick_add_enabled = addon.getSettingBool('quick_add_enabled')
    default_list_id = addon.getSetting('default_list_id')

    if quick_add_enabled and default_list_id:
        quick_add_label = L(31001)  # "Quick Add to Default"
        options.append(quick_add_label)
        actions.append(f"quick_add&dbtype={dbtype}&dbid={dbid}")

    add_to_list_label = L(31000)  # "Add to List..."
    options.append(add_to_list_label)
    actions.append(f"add_to_list&dbtype={dbtype}&dbid={dbid}")


def _add_library_musicvideo_options(options, actions, addon, dbtype, dbid):
    """Add options for library music videos"""
    # Same logic as movies but for music videos
    quick_add_enabled = addon.getSettingBool('quick_add_enabled')
    default_list_id = addon.getSetting('default_list_id')

    if quick_add_enabled and default_list_id:
        quick_add_label = L(31001)  # "Quick Add to Default"
        options.append(quick_add_label)
        actions.append(f"quick_add&dbtype={dbtype}&dbid={dbid}")

    add_to_list_label = L(31000)  # "Add to List..."
    options.append(add_to_list_label)
    actions.append(f"add_to_list&dbtype={dbtype}&dbid={dbid}")


def _add_external_item_options(options, actions, addon):
    """Add options for external/plugin items"""
    # For external items, we can only do add to list (no quick add since we need to gather metadata)
    add_to_list_label = L(31000)  # "Add to List..."
    options.append(add_to_list_label)
    actions.append("add_external_item")


def _add_librarygenie_item_options(options, actions, addon):
    """Add options for LibraryGenie items"""
    # Get item metadata from ListItem properties
    media_item_id = xbmc.getInfoLabel('ListItem.Property(media_item_id)')
    list_id = xbmc.getInfoLabel('ListItem.Property(list_id)')

    if media_item_id:
        # Check if quick-add is enabled and has a default list configured
        quick_add_enabled = addon.getSettingBool('quick_add_enabled')
        default_list_id = addon.getSetting('default_list_id')

        if quick_add_enabled and default_list_id:
            quick_add_label = L(31001)  # "Quick Add to Default"
            options.append(quick_add_label)
            actions.append(f"quick_add&media_item_id={media_item_id}")

        add_to_list_label = L(31000)  # "Add to List..."
        options.append(add_to_list_label)
        actions.append(f"add_to_list&media_item_id={media_item_id}")

        # If we're in a list context, add remove option
        if list_id:
            remove_label = L(31010)  # "Remove from List"
            options.append(remove_label)
            actions.append(f"remove_from_list&list_id={list_id}&item_id={media_item_id}")


def _execute_action(action_with_params, addon):
    """Execute the selected action"""
    try:
        if action_with_params == "search":
            # Launch LibraryGenie search
            plugin_url = "plugin://plugin.video.librarygenie/?action=search"
            xbmc.executebuiltin(f"ActivateWindow(Videos,{plugin_url})")

        elif action_with_params == "add_external_item":
            # Handle external item by gathering metadata
            _handle_external_item_add(addon)

        else:
            # Handle other actions by building plugin URL
            plugin_url = f"plugin://plugin.video.librarygenie/?action={action_with_params}"
            xbmc.executebuiltin(f"RunPlugin({plugin_url})")

    except Exception as e:
        xbmc.log(f"LibraryGenie action execution error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Action failed",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _handle_external_item_add(addon):
    """Handle adding external/plugin items by gathering available metadata"""
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

        # Try to determine media type from context
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
        xbmc.log(f"LibraryGenie external item add error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Failed to process external item",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


if __name__ == '__main__':
    main()