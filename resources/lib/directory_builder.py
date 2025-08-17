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
    Attach context actions per item type using centralized context menu builder.
    item_type: 'list' | 'movie' | 'folder'
    ids may include: list_id, movie_id, folder_id
    """
    from resources.lib.context_menu_builder import get_context_menu_builder
    context_builder = get_context_menu_builder()

    cm = []
    if item_type == 'list':
        list_info = {'list_id': ids.get('list_id', '')}
        cm = context_builder.build_list_context_menu(list_info, ids.get('context', {}))

    elif item_type == 'movie':
        media_info = ids.get('media_info', {})
        context_info = ids.get('context', {})
        cm = context_builder.build_video_context_menu(media_info, context_info)

    elif item_type == 'folder':
        folder_info = {'folder_id': ids.get('folder_id', '')}
        cm = context_builder.build_folder_context_menu(folder_info, ids.get('context', {}))
    if cm:
        li.addContextMenuItems(cm, replaceItems=False)
    return li

def add_options_header_item(ctx: dict, handle: int):
    """Add the options and tools header item as a non-folder RunPlugin item"""
    try:
        # Create list item for options as non-folder
        li = xbmcgui.ListItem(label="[B]Options & Tools[/B]")
        utils.log("Adding Options & Tools header item", "DEBUG")

        # For Kodi v19, avoid setting video info entirely to prevent video info dialog
        from resources.lib import utils as utils_module
        if utils_module.is_kodi_v19():
            utils.log("Kodi v19 detected - skipping video info to prevent dialog issues", "INFO")
        else:
            # Set info dictionary for v20+ - NO mediatype to avoid video info dialog
            info_dict = {
                'title': 'Options & Tools',
                'plot': 'Access list management tools, search options, and addon settings.'
            }
            utils.log(f"=== SETTING INFO WITH DICT: {info_dict} ===", "INFO")
            li.setInfo('video', info_dict)
            utils.log("Successfully called li.setInfo('video', info_dict)", "INFO")

        # Set custom icon for Options & Tools

        from resources.lib.addon_ref import get_addon
        addon = get_addon()
        addon_path = addon.getAddonInfo("path")
        icon_path = f"{addon_path}/resources/media/icon.jpg"

        art_dict = {
            'icon': icon_path,
            'thumb': icon_path,
            'poster': icon_path
        }
        li.setArt(art_dict)

        # Build URL with current context using centralized URL builder
        utils.log("=== BUILDING URL ===", "INFO")
        url_params = {
            'action': 'show_options',
            'view': ctx.get('view'),
        }

        # Only include list_id/folder_id if they exist
        if ctx.get('list_id'):
            url_params['list_id'] = ctx['list_id']
            utils.log(f"Added list_id to URL params: {ctx['list_id']}", "INFO")
        if ctx.get('folder_id'):
            url_params['folder_id'] = ctx['folder_id']
            utils.log(f"Added folder_id to URL params: {ctx['folder_id']}", "INFO")

        utils.log(f"FOLDER_CONTEXT_DEBUG: Building options URL with params: {url_params}", "INFO")
        url = build_plugin_url(url_params)
        utils.log(f"FOLDER_CONTEXT_DEBUG: Built options URL: {url}", "INFO")

        # Add as non-folder item for RunPlugin behavior
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    except Exception as e:
        utils.log(f"Error in Options & Tools ListItem build: {str(e)}", "ERROR")

def build_root_directory(ctx: dict, handle: int):
    """Build the root directory listing"""
    try:
        utils.log("Building root directory listing", "DEBUG")

        from resources.lib.config_manager import Config
        from resources.lib.database_manager import DatabaseManager

        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Add Options & Tools header first
        utils.log("Adding Options & Tools header item to root directory", "DEBUG")
        add_options_header_item(ctx, handle)

        # Get root folders and lists
        folders = db_manager.fetch_folders_by_parent(None)
        lists = db_manager.fetch_lists_by_folder(None)

        utils.log(f"Found {len(folders)} folders and {len(lists)} lists in root", "DEBUG")

        # Get Search History folder ID to exclude it from root display
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

        # Add folders (excluding Search History folder)
        for folder in folders:
            if folder['id'] != search_history_folder_id:
                add_folder_item(folder, ctx, handle)
            else:
                utils.log(f"Hiding Search History folder (ID: {folder['id']}) from root directory", "DEBUG")

        # Add lists
        for list_item in lists:
            add_list_item(list_item, ctx, handle)

        # Set content type and finish directory
        xbmcplugin.setContent(handle, 'movies')
        xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        utils.log(f"Error building root directory: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")

def build_directory_listing(ctx: dict, handle: int):
    """Build the directory listing based on context"""
    try:
        utils.log(f"Building directory listing with context: {ctx}", "DEBUG")

        # Handle different view types
        view = ctx.get('view', 'root')

        if view == 'root':
            build_root_directory(ctx, handle)
        elif view == 'folder':
            build_folder_directory(ctx, handle)
        elif view == 'list':
            build_list_directory(ctx, handle)
        else:
            utils.log(f"Unknown view type: {view}", "WARNING")
            build_root_directory(ctx, handle)

    except Exception as e:
        utils.log(f"Error building directory listing: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")

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

# Helper functions for adding items (assumed to be defined elsewhere or will be added)
def add_folder_item(folder: dict, ctx: dict, handle: int):
    """Helper to build and add a folder list item."""
    try:
        li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
        li.setProperty('lg_type', 'folder')
        add_context_menu_for_item(li, 'folder', folder_id=folder['id']) # Pass folder_id
        url = build_plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    except Exception as e:
        utils.log(f"Error adding folder item for {folder.get('name', 'N/A')}: {str(e)}", "ERROR")

def add_list_item(list_item: dict, ctx: dict, handle: int):
    """Helper to build and add a list list item."""
    try:
        from resources.lib.config_manager import Config
        from resources.lib.database_manager import DatabaseManager
        
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        
        list_count = db_manager.get_list_media_count(list_item['id'])

        # Check if this list contains a count pattern like "(number)" at the end
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
        utils.log(f"Error adding list item for {list_item.get('name', 'N/A')}: {str(e)}", "ERROR")