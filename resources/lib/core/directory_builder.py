"""Directory building utilities for LibraryGenie addon"""

import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.utils import utils
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.config.config_manager import Config
from resources.lib.kodi.url_builder import build_plugin_url, detect_context
from resources.lib.data.normalize import from_db
from resources.lib.kodi.listitem.factory import build_listitem
import sys
import urllib.parse
from typing import List, Dict, Any

def add_context_menu_for_item(li: xbmcgui.ListItem, item_type: str, **ids):
    """
    Legacy function - context menus now handled by factory pattern
    """
    # Context menus are now handled automatically by build_listitem factory
    return li

def add_options_header_item(ctx: dict, handle: int):
    """Add the options and tools header item using new factory pattern"""
    try:
        # Check if navigation is in progress - skip adding options header during navigation
        navigating = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.Navigating)")
        if navigating == "true":
            utils.log("Navigation in progress, skipping options header item", "DEBUG")
            return

        utils.log("Adding Options & Tools header item using factory pattern", "DEBUG")

        # Create MediaItem for options header
        from resources.lib.data.models import MediaItem
        options_item = MediaItem(
            id=0,
            media_type='system',
            title='[B]Options & Tools[/B]',
            plot='Access list management tools, search options, and addon settings.',
            is_folder=False
        )

        # Add context for menu generation
        options_item.context_tags.add('options_header')
        if ctx.get('list_id'):
            options_item.extras['list_id'] = ctx['list_id']
        if ctx.get('folder_id'):
            options_item.extras['folder_id'] = ctx['folder_id']

        # Set play path using centralized URL builder
        url_params = {
            'action': 'show_options',
            'view': ctx.get('view'),
        }

        if ctx.get('list_id'):
            url_params['list_id'] = ctx['list_id']
        if ctx.get('folder_id'):
            url_params['folder_id'] = ctx['folder_id']

        options_item.play_path = build_plugin_url(url_params)

        # Set art using addon path
        from resources.lib.config.addon_ref import get_addon
        addon = get_addon()
        addon_path = addon.getAddonInfo("path")
        icon_path = f"{addon_path}/resources/media/icon.jpg"

        options_item.art = {
            'icon': icon_path,
            'thumb': icon_path,
            'poster': icon_path
        }

        # Build ListItem using factory
        li = build_listitem(options_item, 'options_header')

        # Add as non-folder item for RunPlugin behavior
        xbmcplugin.addDirectoryItem(handle, options_item.play_path, li, isFolder=False)

    except Exception as e:
        utils.log(f"Error in Options & Tools ListItem build: {str(e)}", "ERROR")

def build_root_directory(handle: int):
    """Build the root directory using new factory pattern"""
    # Add options header
    ctx = detect_context({'view': 'root'})
    add_options_header_item(ctx, handle)

    # Add list and folder items using factory pattern
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get top-level folders
        top_level_folders = db_manager.fetch_folders(None) # None for root

        # Get top-level lists
        top_level_lists = db_manager.fetch_lists(None) # None for root

        # Add top-level folders using factory pattern
        for folder in top_level_folders:
            # Skip protected folders logic
            if folder['name'] in ["Search History", "Imported Lists"]:
                folder_count = db_manager.get_folder_media_count(folder['id'])
                subfolders = db_manager.fetch_folders(folder['id'])
                has_subfolders = len(subfolders) > 0

                if folder_count == 0 and not has_subfolders:
                    continue
                if folder['name'] == "Search History":
                    continue

            # Normalize folder data to MediaItem
            folder_data = {
                'id': folder['id'],
                'title': f"📁 {folder['name']}",
                'media_type': 'folder',
                'is_folder': True,
            }

            media_item = from_db(folder_data)
            media_item.play_path = build_plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            media_item.context_tags.add('folder')
            media_item.extras['folder_id'] = folder['id']

            # Build ListItem using factory
            li = build_listitem(media_item, 'folder_view')

            xbmcplugin.addDirectoryItem(handle, media_item.play_path, li, isFolder=True)

        # Add top-level lists using factory pattern
        for list_item in top_level_lists:
            list_count = db_manager.get_list_media_count(list_item['id'])

            # Handle count display logic
            import re
            has_count_in_name = re.search(r'\(\d+\)$', list_item['name'])

            if has_count_in_name:
                display_title = list_item['name']
            else:
                display_title = f"{list_item['name']} ({list_count})"

            # Normalize list data to MediaItem
            list_data = {
                'id': list_item['id'],
                'title': f"📋 {display_title}",
                'media_type': 'playlist',
                'is_folder': True,
            }

            media_item = from_db(list_data)
            media_item.play_path = build_plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
            media_item.context_tags.add('list')
            media_item.extras['list_id'] = list_item['id']

            # Build ListItem using factory
            li = build_listitem(media_item, 'folder_view')

            xbmcplugin.addDirectoryItem(handle, media_item.play_path, li, isFolder=True)

    except Exception as e:
        utils.log(f"Error populating root directory with lists/folders: {str(e)}", "ERROR")

    # Set content type to 'files' for menu navigation (not 'movies')
    xbmcplugin.setContent(handle, 'files')
    xbmcplugin.endOfDirectory(handle)

def show_empty_directory(handle: int, message="No items to display."):
    """Displays a directory with a single item indicating no content using factory pattern"""
    utils.log(f"Showing empty directory: {message}", "DEBUG")
    try:
        # Create MediaItem for empty message
        from resources.lib.data.models import MediaItem
        empty_item = MediaItem(
            title=message,
            media_type='system',
            is_folder=False,
            play_path=""
        )

        # Build ListItem using factory
        li = build_listitem(empty_item, 'empty_view')

        xbmcplugin.addDirectoryItem(handle, "", li, False)
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    except Exception as e:
        utils.log(f"Error showing empty directory: {str(e)}", "ERROR")
        # Fallback: just end directory to prevent hanging
        xbmcplugin.endOfDirectory(handle, succeeded=False)