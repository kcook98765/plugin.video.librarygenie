"""Directory building utilities for LibraryGenie addon"""

import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.data.query_manager import QueryManager
from resources.lib.kodi.url_builder import build_plugin_url, detect_context
from resources.lib.kodi.listitem_builder import ListItemBuilder

def add_context_menu_for_item(li: xbmcgui.ListItem, item_type: str, **ids):
    """
    Attach context actions per item type using centralized context menu builder.
    item_type: 'list' | 'movie' | 'folder'
    ids may include: list_id, movie_id, folder_id
    """
    from resources.lib.kodi.context_menu_builder import get_context_menu_builder
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
        # Check if navigation is in progress - skip adding options header during navigation
        navigating = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.Navigating)")
        if navigating == "true":
            utils.log("Navigation in progress, skipping options header item", "DEBUG")
            return

        # Create list item for options as non-folder
        li = xbmcgui.ListItem(label="[B]Options & Tools[/B]")
        utils.log("Adding Options & Tools header item", "DEBUG")

        # For Kodi v19, avoid setting video info entirely to prevent video info dialog
        if utils.is_kodi_v19():
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

        from resources.lib.config.addon_ref import get_addon
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

def build_root_directory(handle: int):
    """Build the root directory with search option"""
    # Add options header
    ctx = detect_context({'view': 'root'})
    add_options_header_item(ctx, handle)

    # Add list and folder items here based on existing database content
    try:
        config = Config()
        # Initialize query manager and setup database
        query_manager = QueryManager(config.db_path)
        query_manager.setup_database()

        # Get top-level folders
        top_level_folders = query_manager.fetch_folders(None) # None for root

        # Get top-level lists
        top_level_lists = query_manager.fetch_lists(None) # None for root

        # Add top-level folders (excluding protected folders that are empty or accessed via Options & Tools)
        for folder in top_level_folders:
            # Skip protected folders - they're accessed via Options & Tools menu or hidden when empty
            if folder['name'] in ["Search History", "Imported Lists"]:
                # Check if the folder has any content (lists or subfolders)
                folder_count = query_manager.get_folder_media_count(folder['id'])
                subfolders = query_manager.fetch_folders(folder['id'])
                has_subfolders = len(subfolders) > 0

                # Only show if it has content (lists or subfolders)
                if folder_count == 0 and not has_subfolders:
                    continue
                # For Search History, still skip even if it has content (accessed via Options & Tools)
                if folder['name'] == "Search History":
                    continue

            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            add_context_menu_for_item(li, 'folder', folder_id=folder['id']) # Pass folder_id
            url = build_plugin_url({'action': 'browse_folder', 'folder_id': folder['id'], 'view': 'folder'})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Add top-level lists
        for list_item in top_level_lists:
            list_count = query_manager.get_list_media_count(list_item['id'])

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

    # Set content type to 'files' for menu navigation (not 'movies')
    xbmcplugin.setContent(handle, 'files')
    xbmcplugin.endOfDirectory(handle)

def show_empty_directory(handle: int, message="No items to display."):
    """Displays a directory with a single item indicating no content."""
    utils.log(f"Showing empty directory: {message}", "DEBUG")
    try:
        li = ListItemBuilder.build_folder_item(message, is_folder=False)
        li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", li, False)
        xbmcbmcplugin.endOfDirectory(handle, succeeded=True)
    except Exception as e:
        utils.log(f"Error showing empty directory: {str(e)}", "ERROR")
        # Fallback: just end directory to prevent hanging
        xbmcplugin.endOfDirectory(handle, succeeded=False)