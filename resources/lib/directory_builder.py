"""Directory building utilities for LibraryGenie addon"""

import sys
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib import utils
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib.url_builder import build_plugin_url, detect_context
from resources.lib.listitem_builder import ListItemBuilder

def add_context_menu_for_item(li: xbmcgui.ListItem, item_type: str, **ids):
    """
    Attach context actions per item type.
    item_type: 'list' | 'movie' | 'folder'
    ids may include: list_id, movie_id, folder
    """
    cm = []
    if item_type == 'list':
        list_id = ids.get('list_id', '')
        cm += [
            ('Rename list',
             f'RunPlugin({build_plugin_url({"action":"rename_list","list_id":list_id})})'),
            ('Move list',
             f'RunPlugin({build_plugin_url({"action":"move_list","list_id":list_id})})'),
            ('Delete list',
             f'RunPlugin({build_plugin_url({"action":"delete_list","list_id":list_id})})'),
        ]
    elif item_type == 'movie':
        list_id = ids.get('list_id', '')
        movie_id = ids.get('movie_id', '')
        cm += [
            ('Remove movie from list',
             f'RunPlugin({build_plugin_url({"action":"remove_from_list","list_id":list_id,"movie_id":movie_id})})'),
            ('Refresh metadata',
             f'RunPlugin({build_plugin_url({"action":"refresh_movie","movie_id":movie_id})})'),
        ]
    elif item_type == 'folder':
        folder = ids.get('folder', '')
        if folder:
            cm += [
                ('Rename folder',
                 f'RunPlugin({build_plugin_url({"action":"rename_folder","folder":folder})})'),
            ]
    if cm:
        li.addContextMenuItems(cm, replaceItems=False)
    return li

def add_options_header_item(ctx: dict, handle: int):
    """Add the options and tools header item as a non-folder RunPlugin item"""
    try:
        # Check if navigation is in progress - skip adding options header during navigation
        navigating = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.Navigating)")
        if navigating == "true":
            utils.log("Navigation in progress, skipping options header item", "DEBUG")
            return

        # Create list item for options as non-folder
        li = xbmcgui.ListItem(label="[B]Options & Tools[/B]")
        li.setInfo('video', {
            'title': 'Options & Tools',
            'plot': 'Access list management tools, search options, and addon settings.',
            'mediatype': 'video'
        })

        # Set custom icon for Options & Tools
        from resources.lib.addon_ref import get_addon
        addon = get_addon()
        addon_path = addon.getAddonInfo("path")
        icon_path = f"{addon_path}/resources/media/icon.jpg"

        li.setArt({
            'icon': icon_path,
            'thumb': icon_path,
            'poster': icon_path
        })

        # Build URL with current context using centralized URL builder
        url = build_plugin_url({
            'action': 'options',
            'view': ctx.get('view'),
            # Only include list_id/folder if they exist
            **({'list_id': ctx['list_id']} if ctx.get('list_id') else {}),
            **({'folder': ctx['folder']} if ctx.get('folder') else {}),
        })

        # Add as non-folder item so Kodi uses RunPlugin instead of trying to render directory
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    except Exception as e:
        utils.log(f"Error adding options header: {str(e)}", "ERROR")

def build_root_directory(handle: int):
    """Build the root directory with search option"""
    # Add options header
    ctx = detect_context({'view': 'root'})
    add_options_header_item(ctx, handle)

    # Add list and folder items here based on existing database content
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get top-level folders
        top_level_folders = db_manager.fetch_folders(None) # None for root

        # Get top-level lists
        top_level_lists = db_manager.fetch_lists(None) # None for root

        # Add top-level folders (excluding Search History folder)
        for folder in top_level_folders:
            # Skip the Search History folder - it's accessed via Options & Tools menu
            if folder['name'] == "Search History":
                continue

            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            add_context_menu_for_item(li, 'folder', folder_id=folder['id'])
            url = build_plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Add top-level lists
        for list_item in top_level_lists:
            list_count = db_manager.get_list_media_count(list_item['id'])

            # Check if this list contains a count pattern like "(number)" at the end
            # Search history lists already include count, regular lists need count added
            import re
            has_count_in_name = re.search(r'\(\d+\)$', list_item['name'])

            if has_count_in_name:
                # List already has count in name (likely search history), use as-is
                display_title = list_item['name']
            else:
                # Regular list, add count
                display_title = f"{list_item['name']} ({list_count})"
            li = ListItemBuilder.build_folder_item(f"📋 {display_title}", is_folder=True, item_type='playlist')
            li.setProperty('lg_type', 'list')
            add_context_menu_for_item(li, 'list', list_id=list_item['id'])
            url = build_plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    except Exception as e:
        utils.log(f"Error populating root directory with lists/folders: {str(e)}", "ERROR")

    xbmcplugin.endOfDirectory(handle)

def show_empty_directory(handle: int, message="No items to display."):
    """Displays a directory with a single item indicating no content."""
    utils.log(f"Showing empty directory: {message}", "DEBUG")
    try:
        li = ListItemBuilder.build_folder_item(message, is_folder=False)
        li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", li, False)
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    except Exception as e:
        utils.log(f"Error showing empty directory: {str(e)}", "ERROR")
        # Fallback: just end directory to prevent hanging
        xbmcplugin.endOfDirectory(handle, succeeded=False)