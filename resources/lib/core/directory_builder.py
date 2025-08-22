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
        utils.log("=== STARTING OPTIONS & TOOLS HEADER CREATION ===", "INFO")
        
        # Create list item for options as non-folder
        li = xbmcgui.ListItem(label="[B]Options & Tools[/B]")
        utils.log("Created Options & Tools ListItem", "DEBUG")

        # Set basic properties without complex info to avoid issues
        li.setProperty('IsPlayable', 'false')
        utils.log("Set IsPlayable to false", "DEBUG")

        # Set simple art using addon icon
        try:
            from resources.lib.config.addon_ref import get_addon
            addon = get_addon()
            addon_path = addon.getAddonInfo("path")
            icon_path = f"{addon_path}/resources/media/icon.jpg"

            art_dict = {
                'icon': icon_path,
                'thumb': icon_path
            }
            li.setArt(art_dict)
            utils.log("Set Options & Tools art", "DEBUG")
        except Exception as art_error:
            utils.log(f"Error setting art (continuing anyway): {str(art_error)}", "WARNING")

        # Build URL with current context using centralized URL builder
        url_params = {
            'action': 'show_options',
            'view': ctx.get('view', 'root'),
        }

        # Only include list_id/folder_id if they exist
        if ctx.get('list_id'):
            url_params['list_id'] = ctx['list_id']
        if ctx.get('folder_id'):
            url_params['folder_id'] = ctx['folder_id']

        utils.log(f"Building options URL with params: {url_params}", "DEBUG")
        try:
            url = build_plugin_url(url_params)
            utils.log(f"Built options URL: {url}", "DEBUG")
        except Exception as url_error:
            utils.log(f"Error building options URL: {str(url_error)}", "ERROR")
            # Fallback to simple URL
            url = build_plugin_url({'action': 'show_options'})
            utils.log(f"Using fallback options URL: {url}", "DEBUG")

        # Add as non-folder item for RunPlugin behavior
        utils.log("Adding Options & Tools to directory", "INFO")
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
        utils.log("=== OPTIONS & TOOLS HEADER ADDED SUCCESSFULLY ===", "INFO")

    except Exception as e:
        utils.log(f"Error in Options & Tools ListItem build: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Options & Tools creation traceback: {traceback.format_exc()}", "ERROR")
        
        # Try to add a basic fallback item
        try:
            fallback_li = xbmcgui.ListItem(label="[B]Options & Tools[/B]")
            fallback_url = build_plugin_url({'action': 'show_options'})
            xbmcplugin.addDirectoryItem(handle, fallback_url, fallback_li, isFolder=False)
            utils.log("Added fallback Options & Tools item", "INFO")
        except Exception as fallback_error:
            utils.log(f"Even fallback Options & Tools creation failed: {str(fallback_error)}", "ERROR")

def build_root_directory(handle: int):
    """Build the root directory with search option"""
    try:
        # Add options header - always add it at root level first
        utils.log("=== BUILDING ROOT DIRECTORY: Adding Options & Tools header ===", "INFO")
        ctx = detect_context({'view': 'root'})
        add_options_header_item(ctx, handle)
        utils.log("=== ROOT DIRECTORY: Options & Tools header added successfully ===", "INFO")
    except Exception as e:
        utils.log(f"Error adding Options & Tools header: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Options header error traceback: {traceback.format_exc()}", "ERROR")

    # Add list and folder items here based on existing database content
    try:
        config = Config()
        # Get query manager - database setup is handled by service
        query_manager = QueryManager(config.db_path)

        # Add Kodi Favorites list right after Options & Tools (if sync is enabled)
        from resources.lib.config.settings_manager import SettingsManager
        settings = SettingsManager()

        if settings.is_favorites_sync_enabled():
            # Use reserved list ID 1 for Kodi Favorites
            kodi_favorites_list = query_manager.fetch_list_by_id(1)

            if kodi_favorites_list and kodi_favorites_list['name'] == "Kodi Favorites":
                list_count = query_manager.get_list_media_count(1)
                display_title = f"Kodi Favorites ({list_count})"
                li = ListItemBuilder.build_folder_item(f"⭐ {display_title}", is_folder=True, item_type='playlist')
                li.setProperty('lg_type', 'list')
                add_context_menu_for_item(li, 'list', list_id=1)
                url = build_plugin_url({'action': 'browse_list', 'list_id': 1, 'view': 'list'})
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Add Shortlist Imports list (only if it has content)
        # Use reserved list ID 2 for Shortlist Imports
        shortlist_imports_list = query_manager.fetch_list_by_id(2)

        if shortlist_imports_list and shortlist_imports_list['name'] == "Shortlist Imports":
            list_count = query_manager.get_list_media_count(2)
            utils.log(f"Shortlist Imports list found with {list_count} items", "DEBUG")
            # Only show Shortlist Imports if it has content
            if list_count > 0:
                display_title = f"Shortlist Imports ({list_count})"
                li = ListItemBuilder.build_folder_item(f"📥 {display_title}", is_folder=True, item_type='playlist')
                li.setProperty('lg_type', 'list')
                add_context_menu_for_item(li, 'list', list_id=2)
                url = build_plugin_url({'action': 'browse_list', 'list_id': 2, 'view': 'list'})
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        # Get top-level folders
        top_level_folders = query_manager.fetch_folders(None) # None for root

        # Get top-level lists (excluding system lists which we handle separately)
        top_level_lists = [list_item for list_item in query_manager.fetch_lists(None) 
                          if list_item['name'] not in ["Kodi Favorites", "Shortlist Imports"]]

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
            list_id = list_item['id']
            list_name = list_item['name']

            # Get media count for the list
            media_count = query_manager.get_list_media_count(list_id)

            # Always show system lists (ID 1-10), skip other empty lists
            is_system_list = 1 <= list_id <= 10
            if media_count == 0 and not is_system_list:
                continue

            display_name = f"{list_name} ({media_count})"
            li = ListItemBuilder.build_folder_item(f"📋 {display_name}", is_folder=True, item_type='playlist')
            li.setProperty('lg_type', 'list')
            add_context_menu_for_item(li, 'list', list_id=list_id)
            url = build_plugin_url({'action': 'browse_list', 'list_id': list_id, 'view': 'list'})
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
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    except Exception as e:
        utils.log(f"Error showing empty directory: {str(e)}", "ERROR")
        # Fallback: just end directory to prevent hanging
        xbmcplugin.endOfDirectory(handle, succeeded=False)