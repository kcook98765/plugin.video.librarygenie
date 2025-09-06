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
        # IMPORTANT: Cache all item info BEFORE showing any dialogs
        # This prevents losing context when the dialog opens
        item_info = {
            'dbtype': xbmc.getInfoLabel('ListItem.DBTYPE'),
            'dbid': xbmc.getInfoLabel('ListItem.DBID'),
            'file_path': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'title': xbmc.getInfoLabel('ListItem.Title'),
            'label': xbmc.getInfoLabel('ListItem.Label'),
            'media_item_id': xbmc.getInfoLabel('ListItem.Property(media_item_id)'),
            'list_id': xbmc.getInfoLabel('ListItem.Property(list_id)'),
            'container_content': xbmc.getInfoLabel('Container.Content'),
            'is_movies': xbmc.getCondVisibility('Container.Content(movies)'),
            'is_episodes': xbmc.getCondVisibility('Container.Content(episodes)'),
            'is_musicvideos': xbmc.getCondVisibility('Container.Content(musicvideos)'),
            # Try InfoHijack properties as fallback
            'hijack_dbid': xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)'),
            'hijack_dbtype': xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)'),
            'hijack_armed': xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
        }

        # Debug log the cached info
        xbmc.log(f"LibraryGenie: Cached item info: {item_info}", xbmc.LOGINFO)

        # Build options list - Search is always available
        options = []
        actions = []

        # Always add Search option
        search_label = L(33000)
        if not search_label or search_label.startswith('string_'):
            search_label = "Search"
        options.append(search_label)
        actions.append("search")

        # Use cached values instead of fresh getInfoLabel calls
        dbtype = item_info['dbtype']
        dbid = item_info['dbid']
        file_path = item_info['file_path']

        # Use hijack properties as fallback if regular properties are empty
        if not dbid and item_info['hijack_dbid']:
            dbid = item_info['hijack_dbid']
            xbmc.log(f"LibraryGenie: Using hijack DBID fallback: {dbid}", xbmc.LOGINFO)

        if not dbtype and item_info['hijack_dbtype']:
            dbtype = item_info['hijack_dbtype']
            xbmc.log(f"LibraryGenie: Using hijack DBType fallback: {dbtype}", xbmc.LOGINFO)

        # Add content-specific options based on cached context
        # Prioritize dbtype over container context for better detection
        if dbtype == 'movie':
            if dbid and dbid != '0':
                # Library movie - add list management options
                _add_library_movie_options(dbtype, dbid, options, actions)
            else:
                # External/plugin movie - add external item options
                _add_external_item_options(options, actions, addon)

        elif dbtype == 'episode':
            if dbid and dbid != '0':
                # Library episode - add list management options
                _add_library_episode_options(options, actions, addon, dbtype, dbid)
            else:
                # External/plugin episode - add external item options
                _add_external_item_options(options, actions, addon)

        elif dbtype == 'musicvideo':
            if dbid and dbid != '0':
                # Library music video - add list management options
                _add_library_musicvideo_options(options, actions, addon, dbtype, dbid)
            else:
                # External/plugin music video - add external item options
                _add_external_item_options(options, actions, addon)

        # Fallback to container context checks for items without explicit dbtype
        elif item_info['is_movies'] and not dbtype:
            _add_external_item_options(options, actions, addon)

        elif item_info['is_episodes'] and not dbtype:
            _add_external_item_options(options, actions, addon)

        elif item_info['is_musicvideos'] and not dbtype:
            _add_external_item_options(options, actions, addon)

        # Check if we're in a LibraryGenie container first
        elif xbmc.getInfoLabel('Container.FolderPath').startswith('plugin://plugin.video.librarygenie/'):
            # We're in LibraryGenie container
            xbmc.log(f"LibraryGenie: In LibraryGenie container - dbtype={dbtype}, dbid={dbid}", xbmc.LOGINFO)
            _add_librarygenie_item_options(options, actions, addon, item_info)

        elif file_path and file_path.startswith('plugin://plugin.video.librarygenie/'):
            # LibraryGenie item with explicit plugin path
            _add_librarygenie_item_options(options, actions, addon, item_info)

        # Also check if we have hijack properties indicating we're in a LibraryGenie context
        elif item_info.get('hijack_armed') == '1' and item_info.get('hijack_dbid'):
            # We're likely in a LibraryGenie list view with InfoHijack active
            xbmc.log(f"LibraryGenie: Detected InfoHijack context - dbtype={dbtype}, dbid={dbid}", xbmc.LOGINFO)
            _add_librarygenie_item_options(options, actions, addon, item_info)

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


def _add_library_movie_options(dbtype, dbid, options, actions):
    """Add library-specific options for movies"""

    # Get container information to determine context
    container_path = xbmc.getInfoLabel('Container.FolderPath')

    list_id = None
    if 'plugin.video.librarygenie' in container_path and 'list_id=' in container_path:
        # Extract list_id from container path
        import re
        match = re.search(r'list_id=(\d+)', container_path)
        if match:
            list_id = match.group(1)

    # Check if quick-add is enabled and we have a default list
    from lib.config.settings import SettingsManager
    settings = SettingsManager()
    quick_add_enabled = settings.is_quick_add_enabled()
    default_list_id = settings.get_default_list_id()

    # Add remove from list option if we're in a list context
    if list_id:
        options.append("Remove from List")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=remove_library_item_from_list&list_id={list_id}&dbtype={dbtype}&dbid={dbid}&title={xbmc.getInfoLabel('ListItem.Title')})")

    # Add quick-add option if enabled and configured
    if quick_add_enabled and default_list_id:
        options.append("Quick Add to Default List")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=quick_add_context&dbtype={dbtype}&dbid={dbid}&title={xbmc.getInfoLabel('ListItem.Title')})")

    # Always add general "Add to List..." option
    options.append("Add to List...")
    actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=add_library_item_to_list_context&dbtype={dbtype}&dbid={dbid}&title={xbmc.getInfoLabel('ListItem.Title')})")


def _add_library_episode_options(options, actions, addon, dbtype, dbid):
    """Add context menu options for library episodes"""
    xbmc.log(f"_add_library_episode_options called with dbtype={dbtype}, dbid={dbid}", level=xbmc.LOGINFO)

    # Get current context information
    container_path = xbmc.getInfoLabel('Container.FolderPath') or ''
    list_id = xbmc.getInfoLabel('ListItem.Property(list_id)') or ''

    # Extract list_id from URL if not in property
    if not list_id and 'action=show_list' in container_path and 'list_id=' in container_path:
        import re
        match = re.search(r'list_id=(\d+)', container_path)
        if match:
            list_id = match.group(1)

    # Remove from list option (only when in a list context and not Search History)
    if list_id and 'action=show_list' in container_path:
        if 'Search History' not in container_path:
            media_item_id = xbmc.getInfoLabel('ListItem.Property(media_item_id)') or ''
            if not media_item_id:
                media_item_id = f"episode_{dbid}"

            options.append("Remove from List")
            actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=remove_from_list&list_id={list_id}&item_id={media_item_id})")

    # Quick add functionality
    try:
        if SettingsManager:
            settings = SettingsManager()
            quick_add_enabled = settings.get_quick_add_enabled()
            default_list_id = settings.get_default_list_id()
        else:
            # Fallback to addon settings if SettingsManager not available
            quick_add_enabled = addon.getSettingBool('quick_add_enabled')
            default_list_id = addon.getSetting('default_list_id')
    except Exception:
        # Fallback to addon settings
        quick_add_enabled = addon.getSettingBool('quick_add_enabled')
        default_list_id = addon.getSetting('default_list_id')

    if quick_add_enabled and default_list_id:
        # Quick add option
        options.append("Quick Add to Default List")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=quick_add_library_item&dbtype={dbtype}&dbid={dbid})")

        # Regular add to list option
        options.append("Add to List...")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=add_library_item_to_list&dbtype={dbtype}&dbid={dbid})")
    else:
        # Only regular add to list option
        options.append("Add to List...")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=add_library_item_to_list&dbtype={dbtype}&dbid={dbid})")

    # Search option
    options.append("Search")
    actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=search_from_context&query={xbmc.getInfoLabel('ListItem.TVShowTitle')} {xbmc.getInfoLabel('ListItem.Title')}")


def _add_library_musicvideo_options(options, actions, addon, dbtype, dbid):
    """Add context menu options for library music videos"""
    xbmc.log(f"_add_library_musicvideo_options called with dbtype={dbtype}, dbid={dbid}", level=xbmc.LOGINFO)

    # Get current context information
    container_path = xbmc.getInfoLabel('Container.FolderPath') or ''
    list_id = xbmc.getInfoLabel('ListItem.Property(list_id)') or ''

    # Extract list_id from URL if not in property
    if not list_id and 'action=show_list' in container_path and 'list_id=' in container_path:
        import re
        match = re.search(r'list_id=(\d+)', container_path)
        if match:
            list_id = match.group(1)

    # Remove from list option (only when in a list context and not Search History)
    if list_id and 'action=show_list' in container_path:
        if 'Search History' not in container_path:
            media_item_id = xbmc.getInfoLabel('ListItem.Property(media_item_id)') or ''
            if not media_item_id:
                media_item_id = f"musicvideo_{dbid}"

            options.append("Remove from List")
            actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=remove_from_list&list_id={list_id}&item_id={media_item_id})")

    # Quick add functionality
    try:
        if SettingsManager:
            settings = SettingsManager()
            quick_add_enabled = settings.get_quick_add_enabled()
            default_list_id = settings.get_default_list_id()
        else:
            # Fallback to addon settings if SettingsManager not available
            quick_add_enabled = addon.getSettingBool('quick_add_enabled')
            default_list_id = addon.getSetting('default_list_id')
    except Exception:
        # Fallback to addon settings
        quick_add_enabled = addon.getSettingBool('quick_add_enabled')
        default_list_id = addon.getSetting('default_list_id')

    if quick_add_enabled and default_list_id:
        # Quick add option
        options.append("Quick Add to Default List")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=quick_add_library_item&dbtype={dbtype}&dbid={dbid})")

        # Regular add to list option
        options.append("Add to List...")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=add_library_item_to_list&dbtype={dbtype}&dbid={dbid})")
    else:
        # Only regular add to list option
        options.append("Add to List...")
        actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=add_library_item_to_list&dbtype={dbtype}&dbid={dbid})")

    # Search option
    options.append("Search")
    actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=search_from_context&query={xbmc.getInfoLabel('ListItem.Artist')} {xbmc.getInfoLabel('ListItem.Title')}")


def _add_external_item_options(options, actions, addon):
    """Add options for external/plugin items"""
    # For external items, we can only do add to list (no quick add since we need to gather metadata)
    add_to_list_label = L(31000)  # "Add to List..."
    options.append(add_to_list_label)
    actions.append("add_external_item")


def _add_librarygenie_item_options(options, actions, addon, item_info):
    """Add options for LibraryGenie items"""
    # Use cached item metadata
    media_item_id = item_info['media_item_id']
    list_id = item_info['list_id']
    dbtype = item_info['dbtype']
    dbid = item_info['dbid']
    container_path = xbmc.getInfoLabel('Container.FolderPath')

    # Use hijack properties as fallback
    if not dbid and item_info.get('hijack_dbid'):
        dbid = item_info['hijack_dbid']
    if not dbtype and item_info.get('hijack_dbtype'):
        dbtype = item_info['hijack_dbtype']

    xbmc.log(f"LibraryGenie: _add_librarygenie_item_options - dbtype={dbtype}, dbid={dbid}, media_item_id={media_item_id}", xbmc.LOGINFO)
    xbmc.log(f"LibraryGenie: Container path: {container_path}", xbmc.LOGINFO)

    # Extract list_id from container path if we're viewing a list
    extracted_list_id = None
    if 'list_id=' in container_path:
        try:
            import re
            list_id_match = re.search(r'list_id=(\d+)', container_path)
            if list_id_match:
                extracted_list_id = list_id_match.group(1)
                xbmc.log(f"LibraryGenie: Extracted list_id from container: {extracted_list_id}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"LibraryGenie: Failed to extract list_id: {e}", xbmc.LOGINFO)

    # First priority: items with media_item_id (existing LibraryGenie items)
    if media_item_id and media_item_id != '':
        xbmc.log(f"LibraryGenie: Using media_item_id path for {media_item_id}", xbmc.LOGINFO)
        # Check if quick-add is enabled and has a default list configured
        quick_add_enabled = addon.getSettingBool('quick_add_enabled')
        default_list_id = addon.getSetting('default_list_id')

        if quick_add_enabled and default_list_id:
            quick_add_label = L(31001) if L(31001) else "Quick Add to Default"
            options.append(quick_add_label)
            actions.append(f"quick_add&media_item_id={media_item_id}")

        add_to_list_label = L(31000) if L(31000) else "Add to List..."
        options.append(add_to_list_label)
        actions.append(f"add_to_list&media_item_id={media_item_id}")

        # If we're in a list context, add remove option
        target_list_id = list_id if list_id and list_id != '' else extracted_list_id
        if target_list_id:
            remove_label = L(31010) if L(31010) else "Remove from List"
            options.append(remove_label)
            actions.append(f"remove_from_list&list_id={target_list_id}&item_id={media_item_id}")
            xbmc.log(f"LibraryGenie: Added remove option for list {target_list_id}", xbmc.LOGINFO)

    # Second priority: library items with valid dbtype and dbid in LibraryGenie context
    elif dbtype in ('movie', 'episode', 'musicvideo') and dbid and dbid not in ('0', ''):
        xbmc.log(f"LibraryGenie: Using library item path for {dbtype} {dbid}", xbmc.LOGINFO)

        # If we're in a LibraryGenie list view, offer remove option first
        if extracted_list_id and item_info.get('title'):
            remove_label = L(31010) if L(31010) else "Remove from List"
            options.append(remove_label)
            # For library items in lists without media_item_id, we need to identify by title/dbid
            title = item_info.get('title', '')
            actions.append(f"remove_library_item_from_list&list_id={extracted_list_id}&dbtype={dbtype}&dbid={dbid}&title={title}")
            xbmc.log(f"LibraryGenie: Added remove option for library item {dbtype} {dbid} in list {extracted_list_id}", xbmc.LOGINFO)

        # Add standard library item options
        if dbtype == 'movie':
            _add_library_movie_options(dbtype, dbid, options, actions)
        elif dbtype == 'episode':
            _add_library_episode_options(options, actions, addon, dbtype, dbid)
        elif dbtype == 'musicvideo':
            _add_library_musicvideo_options(options, actions, addon, dbtype, dbid)

    # Third priority: items in movie container (but without library metadata)
    elif item_info.get('is_movies') and item_info.get('title'):
        xbmc.log(f"LibraryGenie: Using external item path for movie container item", xbmc.LOGINFO)

        # If we're in a list context, add remove option first
        if extracted_list_id:
            remove_label = L(31010) if L(31010) else "Remove from List"
            options.append(remove_label)
            title = item_info.get('title', '')
            actions.append(f"remove_from_list&list_id={extracted_list_id}&item_title={title}")
            xbmc.log(f"LibraryGenie: Added remove option for external item in list {extracted_list_id}", xbmc.LOGINFO)

        _add_external_item_options(options, actions, addon)

    # Fallback: any item with a title in LibraryGenie context
    elif item_info.get('title'):
        xbmc.log(f"LibraryGenie: Using fallback path for titled item", xbmc.LOGINFO)

        # If we're in a list context, add remove option first
        if extracted_list_id:
            remove_label = L(31010) if L(31010) else "Remove from List"
            options.append(remove_label)
            title = item_info.get('title', '')
            actions.append(f"remove_from_list&list_id={extracted_list_id}&item_title={title}")
            xbmc.log(f"LibraryGenie: Added remove option for fallback item in list {extracted_list_id}", xbmc.LOGINFO)

        _add_external_item_options(options, actions, addon)


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

        elif action_with_params.startswith("remove_from_list") or action_with_params.startswith("remove_library_item_from_list"):
            # Handle remove actions by building plugin URL
            plugin_url = f"plugin://plugin.video.librarygenie/?action={action_with_params}"
            xbmc.log(f"LibraryGenie: Executing remove action: {plugin_url}", xbmc.LOGINFO)
            xbmc.executebuiltin(f"RunPlugin({plugin_url})")

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

        # Gather comprehensive artwork for version-aware storage
        art_data = {}
        art_fields = {
            'poster': 'ListItem.Art(poster)',
            'fanart': 'ListItem.Art(fanart)',
            'thumb': 'ListItem.Art(thumb)',
            'banner': 'ListItem.Art(banner)',
            'landscape': 'ListItem.Art(landscape)',
            'clearlogo': 'ListItem.Art(clearlogo)',
            'clearart': 'ListItem.Art(clearart)',
            'discart': 'ListItem.Art(discart)',
            'icon': 'ListItem.Art(icon)'
        }

        for art_key, info_label in art_fields.items():
            art_value = xbmc.getInfoLabel(info_label)
            if art_value:
                art_data[art_key] = art_value

        # Fallback to ListItem.Thumb for poster if not available
        if not art_data.get('poster'):
            thumb_fallback = xbmc.getInfoLabel('ListItem.Thumb')
            if thumb_fallback:
                art_data['poster'] = thumb_fallback
                if not art_data.get('thumb'):
                    art_data['thumb'] = thumb_fallback

        # Store collected art data
        item_data['art_data'] = art_data

        # Also set individual fields for backward compatibility
        item_data['poster'] = art_data.get('poster', '')
        item_data['fanart'] = art_data.get('fanart', '')
        item_data['thumb'] = art_data.get('thumb', '')
        item_data['banner'] = art_data.get('banner', '')
        item_data['clearlogo'] = art_data.get('clearlogo', '')

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