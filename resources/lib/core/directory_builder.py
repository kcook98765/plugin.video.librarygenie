"""Directory building utilities for LibraryGenie addon"""

import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.utils import utils
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.config.config_manager import Config
from resources.lib.kodi.url_builder import build_plugin_url, detect_context
from resources.lib.kodi.listitem_builder import ListItemBuilder

# Context menus now handled entirely by native system via addon.xml
# No programmatic context menu items needed

def add_options_header_item(ctx: dict, handle: int):
    """Add the options and tools header item as a non-folder RunPlugin item"""
    try:
        utils.log("=== ADD_OPTIONS_HEADER: Starting Options & Tools header creation ===", "INFO")
        utils.log(f"ADD_OPTIONS_HEADER: Context received: {ctx}", "INFO")
        utils.log(f"ADD_OPTIONS_HEADER: Handle received: {handle}", "INFO")

        # Create list item for options as non-folder - avoid any video-related configuration
        li = xbmcgui.ListItem(label="[B]Options & Tools[/B]")
        utils.log("=== ADD_OPTIONS_HEADER: Created ListItem with label '[B]Options & Tools[/B]' ===", "INFO")

        # Do NOT set any video info to prevent Kodi from treating this as media content
        # Do NOT call setInfo with 'video' type as this triggers media player behavior
        
        # Explicitly mark as non-playable to prevent Kodi from trying to play it
        li.setProperty('IsPlayable', 'false')
        
        # Set content type to indicate this is not media content
        li.setProperty('folder', 'false')
        
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
        utils.log(f"FOLDER_CONTEXT_DEBUG: Built plugin URL: {url}", "INFO")

        # Add as folder item to prevent Kodi from trying to play it
        # This will make it navigable but not playable
        li.setIsFolder(True)
        utils.log(f"=== ADD_OPTIONS_HEADER: About to add directory item with URL: {url} ===", "INFO")
        result = xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        utils.log(f"=== ADD_OPTIONS_HEADER: addDirectoryItem returned: {result} ===", "INFO")
        utils.log("=== ADD_OPTIONS_HEADER: Options & Tools header successfully added to directory ===", "INFO")

    except Exception as e:
        utils.log(f"=== ADD_OPTIONS_HEADER: ERROR in Options & Tools ListItem build: {str(e)} ===", "ERROR")
        import traceback
        utils.log(f"=== ADD_OPTIONS_HEADER: Traceback: {traceback.format_exc()} ===", "ERROR")

def build_root_directory(handle: int):
    """Build the root directory with search option"""
    utils.log("=== BUILD_ROOT_DIRECTORY: FUNCTION ENTRY - Starting root directory build ===", "DEBUG")
    utils.log(f"=== BUILD_ROOT_DIRECTORY: Handle received: {handle} ===", "DEBUG")
    
    # Add options header
    ctx = detect_context({'view': 'root'})
    utils.log(f"=== BUILD_ROOT_DIRECTORY: Detected context for root: {ctx} ===", "DEBUG")
    
    utils.log("=== BUILD_ROOT_DIRECTORY: About to add Options & Tools header ===", "DEBUG")
    try:
        add_options_header_item(ctx, handle)
        utils.log("=== BUILD_ROOT_DIRECTORY: Options & Tools header call completed successfully ===", "DEBUG")
    except Exception as e:
        utils.log(f"=== BUILD_ROOT_DIRECTORY: ERROR calling add_options_header_item: {str(e)} ===", "ERROR")
        import traceback
        utils.log(f"=== BUILD_ROOT_DIRECTORY: Traceback: {traceback.format_exc()} ===", "ERROR")

    # Add list and folder items here based on existing database content
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get top-level folders
        top_level_folders = db_manager.fetch_folders(None) # None for root

        # Get top-level lists
        top_level_lists = db_manager.fetch_lists(None) # None for root

        # Add top-level folders (excluding protected folders)
        for folder in top_level_folders:
            # Skip protected folders - they're accessed via Options & Tools menu only
            if folder['name'] in ["Search History", "Imported Lists"]:
                # Always skip Search History - it's only accessible via Options & Tools
                if folder['name'] == "Search History":
                    continue
                
                # For Imported Lists, only show if it has content
                folder_count = db_manager.get_folder_media_count(folder['id'])
                subfolders = db_manager.fetch_folders(folder['id'])
                has_subfolders = len(subfolders) > 0
                
                # Only show if it has content (lists or subfolders)
                if folder_count == 0 and not has_subfolders:
                    continue

            li = ListItemBuilder.build_folder_item(f"📁 {folder['name']}", is_folder=True)
            li.setProperty('lg_type', 'folder')
            # Context menus handled by native system via addon.xml
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
            # Context menus handled by native system via addon.xml
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
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    except Exception as e:
        utils.log(f"Error showing empty directory: {str(e)}", "ERROR")
        # Fallback: just end directory to prevent hanging
        xbmcplugin.endOfDirectory(handle, succeeded=False)


class DirectoryBuilder:
    """Handles building Kodi directory listings for folders and lists"""
    
    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)
    
    def build_folder_directory(self, folder_id: int, handle: int):
        """Build directory listing for a specific folder"""
        try:
            utils.log(f"Building folder directory for folder_id: {folder_id}", "DEBUG")
            
            # Get folder details
            folder = self.db_manager.fetch_folder_by_id(folder_id)
            if not folder:
                utils.log(f"Folder {folder_id} not found", "ERROR")
                show_empty_directory(handle, "Folder not found")
                return
            
            utils.log(f"Found folder: {folder['name']}", "DEBUG")
            
            # Add options header with folder context
            ctx = detect_context({'view': 'folder', 'folder_id': folder_id})
            add_options_header_item(ctx, handle)
            
            # Get subfolders
            subfolders = self.db_manager.fetch_folders(folder_id)
            utils.log(f"Found {len(subfolders)} subfolders", "DEBUG")
            
            # Get lists in this folder
            lists = self.db_manager.fetch_lists(folder_id)
            utils.log(f"Found {len(lists)} lists", "DEBUG")
            
            # Add subfolders
            for subfolder in subfolders:
                li = ListItemBuilder.build_folder_item(f"📁 {subfolder['name']}", is_folder=True)
                li.setProperty('lg_type', 'folder')
                url = build_plugin_url({'action': 'browse_folder', 'folder_id': subfolder['id'], 'view': 'folder'})
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
            
            # Add lists
            for list_item in lists:
                list_count = self.db_manager.get_list_media_count(list_item['id'])
                
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
                url = build_plugin_url({'action': 'browse_list', 'list_id': list_item['id'], 'view': 'list'})
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
            
            # Set content type and end directory
            xbmcplugin.setContent(handle, 'files')
            xbmcplugin.endOfDirectory(handle)
            utils.log(f"Successfully built folder directory for {folder['name']}", "DEBUG")
            
        except Exception as e:
            utils.log(f"Error building folder directory: {str(e)}", "ERROR")
            import traceback
            utils.log(f"build_folder_directory traceback: {traceback.format_exc()}", "ERROR")
            show_empty_directory(handle, "Error loading folder contents")
    
    def build_list_directory(self, list_id: int, handle: int):
        """Build directory listing for a specific list"""
        try:
            utils.log(f"Building list directory for list_id: {list_id}", "DEBUG")
            
            # Get list details
            list_info = self.db_manager.fetch_list_by_id(list_id)
            if not list_info:
                utils.log(f"List {list_id} not found", "ERROR")
                show_empty_directory(handle, "List not found")
                return
            
            utils.log(f"Found list: {list_info['name']}", "DEBUG")
            
            # Add options header with list context
            ctx = detect_context({'view': 'list', 'list_id': list_id})
            add_options_header_item(ctx, handle)
            
            # Get list items with details
            list_items = self.db_manager.fetch_list_items_with_details(list_id)
            utils.log(f"Found {len(list_items)} items in list", "DEBUG")
            
            if not list_items:
                show_empty_directory(handle, "This list is empty")
                return
            
            # Add each item in the list
            for item in list_items:
                try:
                    # Build list item using ListItemBuilder
                    li = ListItemBuilder.build_media_item(item)
                    
                    # Determine if item is playable based on kodi_id
                    kodi_id = item.get('kodi_id', 0)
                    if kodi_id and int(kodi_id) > 0:
                        # Item exists in Kodi library - make it playable
                        li.setProperty('IsPlayable', 'true')
                        url = build_plugin_url({
                            'action': 'play_movie',
                            'movieid': kodi_id
                        })
                        is_folder = False
                    else:
                        # Item not in library - show details only
                        li.setProperty('IsPlayable', 'false')
                        url = build_plugin_url({
                            'action': 'show_item_details',
                            'title': item.get('title', 'Unknown'),
                            'list_id': list_id,
                            'item_id': item.get('id')
                        })
                        is_folder = False
                    
                    xbmcplugin.addDirectoryItem(handle, url, li, is_folder)
                    
                except Exception as item_error:
                    utils.log(f"Error building list item: {str(item_error)}", "ERROR")
                    continue
            
            # Set content type and end directory
            xbmcplugin.setContent(handle, 'movies')
            xbmcplugin.endOfDirectory(handle)
            utils.log(f"Successfully built list directory for {list_info['name']}", "DEBUG")
            
        except Exception as e:
            utils.log(f"Error building list directory: {str(e)}", "ERROR")
            import traceback
            utils.log(f"build_list_directory traceback: {traceback.format_exc()}", "ERROR")
            show_empty_directory(handle, "Error loading list contents")