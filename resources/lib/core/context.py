import sys
import xbmcgui
import xbmcaddon
import xbmcvfs
import xbmc
import re
from urllib.parse import quote_plus

from resources.lib.kodi.kodi_helper import KodiHelper
from resources.lib.config.addon_ref import get_addon
from resources.lib.kodi.context_menu_builder import get_context_menu_builder
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.kodi.window_search import SearchWindow
from resources.lib.utils import utils

translatePath = xbmcvfs.translatePath

# Get addon and setup paths FIRST
ADDON = xbmcaddon.Addon()
ADDON_PATH = translatePath(ADDON.getAddonInfo("path"))

def main():
    """Main entry point for context menu actions"""
    try:
        xbmc.log("LibraryGenie: Context menu script started", xbmc.LOGINFO)

        addon = get_addon()
        if not addon:
            xbmc.log("LibraryGenie: Failed to get addon instance", xbmc.LOGERROR)
            return

        # Get basic item information that's available in context
        title = xbmc.getInfoLabel('ListItem.Title')
        year = xbmc.getInfoLabel('ListItem.Year')

        xbmc.log(f"LibraryGenie: Context menu for: {title} ({year})", xbmc.LOGINFO)

        # Show context menu options
        addon_id = addon.getAddonInfo("id")

        # Ensure database schema is up to date (including migrations)
        try:
            config = Config()
            db_manager = DatabaseManager(config.db_path)
            # This will run any pending migrations including the 'file' column
            db_manager.setup_database()
            xbmc.log("LibraryGenie: Database schema check completed for context menu", xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f"LibraryGenie: Error setting up database schema: {str(e)}", xbmc.LOGERROR)

        # Use existing KodiHelper to get IMDb ID (handles v19/v20+ compatibility)
        imdb_id = None
        try:
            kodi_helper = KodiHelper()
            imdb_id = kodi_helper.get_imdb_from_item()
            xbmc.log(f"LibraryGenie: IMDb ID from KodiHelper: {imdb_id}", xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f"LibraryGenie: Error getting IMDb ID via KodiHelper: {str(e)}", xbmc.LOGDEBUG)

        xbmc.log(f"LibraryGenie: Final IMDb ID detection result: {imdb_id}", xbmc.LOGDEBUG)

        options = []

        # Check authentication before adding API-dependent options
        context_builder = get_context_menu_builder()
        is_authenticated = context_builder._is_authenticated()

        # Check if we're currently viewing a LibraryGenie list (to offer Remove option)
        current_container_path = xbmc.getInfoLabel('Container.FolderPath')
        viewing_list_id = None
        is_librarygenie_list = False

        if 'browse_list' in current_container_path and 'list_id=' in current_container_path and 'plugin.video.librarygenie' in current_container_path:
            try:
                match = re.search(r'list_id=(\d+)', current_container_path)
                if match:
                    extracted_list_id = match.group(1)
                    xbmc.log(f"LibraryGenie: Detected potential list_id: {extracted_list_id}", xbmc.LOGDEBUG)

                    # Verify this list exists in our database
                    try:
                        config = Config()
                        db_manager = DatabaseManager(config.db_path)
                        list_data = db_manager.fetch_list_by_id(extracted_list_id)

                        if list_data:
                            viewing_list_id = extracted_list_id
                            is_librarygenie_list = True
                            xbmc.log(f"LibraryGenie: Confirmed viewing LibraryGenie list_id: {viewing_list_id}", xbmc.LOGDEBUG)
                        else:
                            xbmc.log(f"LibraryGenie: List {extracted_list_id} not found in database - not a LibraryGenie list", xbmc.LOGDEBUG)
                    except Exception as db_error:
                        xbmc.log(f"LibraryGenie: Error verifying list in database: {str(db_error)}", xbmc.LOGDEBUG)

            except Exception as e:
                xbmc.log(f"LibraryGenie: Error extracting list_id: {str(e)}", xbmc.LOGDEBUG)

        # Enhanced folder detection with comprehensive debugging
        current_item_path = xbmc.getInfoLabel('ListItem.FolderPath')
        item_path = xbmc.getInfoLabel('ListItem.Path')
        is_folder_item = xbmc.getInfoLabel('ListItem.IsFolder') == 'true'
        lg_type = xbmc.getInfoLabel('ListItem.Property(lg_type)')
        is_librarygenie_folder = False

        # Debug all relevant paths and properties
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - Title: '{title}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - IsFolder: {is_folder_item}", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - lg_type: '{lg_type}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - Container.FolderPath: '{current_container_path}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - ListItem.FolderPath: '{current_item_path}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - ListItem.Path: '{item_path}'", xbmc.LOGINFO)

        # Additional debugging info
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - ListItem.Label: '{xbmc.getInfoLabel('ListItem.Label')}'", xbmc.LOGINFO)

        # Check if this is a LibraryGenie folder based on lg_type property first
        # This handles cases where IsFolder might be False but it's still a folder/list item
        if lg_type == 'folder':
            # This is a LibraryGenie folder - check if we're in LibraryGenie context
            if 'plugin.video.librarygenie' in (current_container_path or item_path or ''):
                is_librarygenie_folder = True
                xbmc.log("LibraryGenie: FOLDER DEBUG - Detected LibraryGenie folder via lg_type=folder", xbmc.LOGINFO)

        # For regular folder items (when IsFolder is True), use the existing detection methods
        elif is_folder_item:
            try:
                # Method 1: Check if we're viewing a LibraryGenie folder structure
                if 'plugin.video.librarygenie' in current_container_path:
                    xbmc.log("LibraryGenie: FOLDER DEBUG - In LibraryGenie container path", xbmc.LOGINFO)

                    # Check for browse_folder action in container path
                    if 'action=browse_folder' in current_container_path:
                        is_librarygenie_folder = True
                        xbmc.log(f"LibraryGenie: FOLDER DEBUG - Detected browse_folder action in container: {current_container_path}", xbmc.LOGINFO)

                    # Check if at root of LibraryGenie (no specific action) - this is key for root folders
                    elif current_container_path.strip('/').endswith('plugin.video.librarygenie') or '/?action=' not in current_container_path:
                        is_librarygenie_folder = True
                        xbmc.log("LibraryGenie: FOLDER DEBUG - At LibraryGenie root or general context", xbmc.LOGINFO)

                # Method 2: Check the item's own path
                if not is_librarygenie_folder and item_path and 'plugin.video.librarygenie' in item_path:
                    xbmc.log(f"LibraryGenie: FOLDER DEBUG - LibraryGenie found in item path: {item_path}", xbmc.LOGINFO)
                    if 'action=browse_folder' in item_path or 'folder_id=' in item_path:
                        is_librarygenie_folder = True
                        xbmc.log("LibraryGenie: FOLDER DEBUG - Detected folder action in item path", xbmc.LOGINFO)

                # Method 3: Check if this is a folder with 📁 emoji (our folder marker)
                if not is_librarygenie_folder and title and title.startswith('📁'):
                    xbmc.log("LibraryGenie: FOLDER DEBUG - Detected folder emoji marker", xbmc.LOGINFO)
                    # Additional check: verify we're in LibraryGenie context
                    if 'plugin.video.librarygenie' in (current_container_path or item_path or ''):
                        is_librarygenie_folder = True
                        xbmc.log("LibraryGenie: FOLDER DEBUG - Confirmed LibraryGenie folder via emoji marker", xbmc.LOGINFO)

                # Method 4: Universal LibraryGenie folder detection - if we're in LibraryGenie and it's a folder, assume it's ours
                if not is_librarygenie_folder and 'plugin.video.librarygenie' in current_container_path:
                    is_librarygenie_folder = True
                    xbmc.log("LibraryGenie: FOLDER DEBUG - Universal detection - folder in LibraryGenie context", xbmc.LOGINFO)

            except Exception as e:
                xbmc.log(f"LibraryGenie: Error detecting LibraryGenie folder context: {str(e)}", xbmc.LOGERROR)
                import traceback
                xbmc.log(f"LibraryGenie: Folder detection traceback: {traceback.format_exc()}", xbmc.LOGERROR)

        # Check if this is a LibraryGenie folder/list item (either by IsFolder=true or lg_type=folder/list)
        is_lg_folder_item = (is_folder_item and is_librarygenie_folder) or (lg_type == 'folder' and is_librarygenie_folder)
        is_lg_list_item = (lg_type == 'list' and 'plugin.video.librarygenie' in (current_container_path or ''))

        xbmc.log(f"LibraryGenie: FOLDER DEBUG - Final detection result: is_librarygenie_folder = {is_librarygenie_folder}", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - is_folder_item = {is_folder_item}", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - lg_type = {lg_type}", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - is_lg_folder_item = {is_lg_folder_item}", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: FOLDER DEBUG - is_lg_list_item = {is_lg_list_item}", xbmc.LOGINFO)

        # If this is a LibraryGenie list item (lg_type=list), show list options
        if is_lg_list_item:
            xbmc.log("LibraryGenie: LIST OPTIONS - Detected LibraryGenie list item, showing list options", xbmc.LOGINFO)

            # List-specific options
            options.append("Rename List")
            options.append("Delete List")
            options.append("Move List")
            options.append("Add Movies to List")
            options.append("Clear List")
            options.append("Export List")
            options.append("Information")
            options.append("Settings")

            xbmc.log(f"LibraryGenie: LIST OPTIONS - Added {len(options)} list options: {options}", xbmc.LOGINFO)

        # If this is a LibraryGenie folder item (either actual folder or lg_type=folder), show folder options
        elif is_lg_folder_item:
            xbmc.log("LibraryGenie: FOLDER OPTIONS - Detected LibraryGenie folder item, showing folder options", xbmc.LOGINFO)

            # Folder-specific options
            options.append("Rename Folder")
            options.append("Delete Folder")
            options.append("Move Folder")
            options.append("Create New List Here")
            options.append("Create New Subfolder")
            options.append("Information")
            options.append("Settings")

            xbmc.log(f"LibraryGenie: FOLDER OPTIONS - Added {len(options)} folder options: {options}", xbmc.LOGINFO)
        else:
            xbmc.log("LibraryGenie: FOLDER OPTIONS - NOT showing folder options, showing regular item options instead", xbmc.LOGINFO)
            # Regular movie/item options
            # Show Details - always available
            options.append("Show Details")

            # Information - always available
            options.append("Information")

            # Add movie to a list - available for both library items (with IMDb) and plugin items (without IMDb)
            # For library items, we prefer IMDb ID, but for plugin items we'll use available metadata
            can_add_to_list = (imdb_id and str(imdb_id).startswith('tt')) or (title and title.strip())

            if can_add_to_list:
                if viewing_list_id and is_librarygenie_list:
                    # If viewing a LibraryGenie list, offer Remove option first
                    options.append("Remove from List...")
                    options.append("Add to Another List...")
                else:
                    # If not viewing a LibraryGenie list, offer Add option
                    options.append("Add to List...")

            # Find Similar Movies - only if authenticated AND has valid IMDb ID
            if imdb_id and str(imdb_id).startswith('tt'):
                if is_authenticated:
                    options.append("Find Similar Movies...")
                else:
                    options.append("Find Similar Movies... (Requires Authentication)")

        # Refresh Metadata - always available (unless it's a LibraryGenie folder, then it's handled by folder options)
        if not is_lg_folder_item:
            options.append("Refresh Metadata")

        # Search Movies - only if authenticated
        if not is_lg_folder_item:
            if is_authenticated:
                options.append("Search Movies...")
            else:
                options.append("Search Movies... (Requires Authentication)")

        if not is_lg_folder_item:
            options.extend([
                "Search History",
                "Settings"
            ])

        if len(options) == 0:
            xbmc.log("LibraryGenie: No options available, exiting context menu", xbmc.LOGINFO)
            return

        xbmc.log(f"LibraryGenie: CONTEXT MENU - Showing {len(options)} options: {options}", xbmc.LOGINFO)

        # Show list selection dialog
        from typing import List, Union
        typed_options: List[Union[str, xbmcgui.ListItem]] = options
        selected_index = xbmcgui.Dialog().select(
            f"LibraryGenie - {title}:",
            typed_options
        )

        if selected_index == -1:  # User cancelled
            xbmc.log("LibraryGenie: User cancelled context menu selection", xbmc.LOGINFO)
            return

        selected_option = options[selected_index]
        xbmc.log(f"LibraryGenie: User selected option {selected_index}: '{selected_option}'", xbmc.LOGINFO)

        # Handle list-specific actions
        if is_lg_list_item:
            xbmc.log(f"LibraryGenie: LIST ACTION - Handling list option: '{selected_option}'", xbmc.LOGINFO)

            if selected_option == "Rename List":
                xbmc.log("LibraryGenie: LIST ACTION - Executing Rename List", xbmc.LOGINFO)
                try:
                    # Extract list_id from item path for rename operation
                    list_id = None
                    match = re.search(r'list_id=(\d+)', current_item_path)
                    if match:
                        list_id = match.group(1)

                    if list_id:
                        xbmc.log(f"LibraryGenie: LIST ACTION - Extracted list_id: {list_id}", xbmc.LOGINFO)
                        # Call rename list function
                        rename_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})'
                        xbmc.executebuiltin(rename_url)
                    else:
                        xbmc.log("LibraryGenie: LIST ACTION - Could not extract list_id for rename", xbmc.LOGERROR)
                        xbmcgui.Dialog().notification("LibraryGenie", "Could not determine list to rename", xbmcgui.NOTIFICATION_ERROR, 3000)
                except Exception as e:
                    xbmc.log(f"LibraryGenie: LIST ACTION - Error in rename list: {str(e)}", xbmc.LOGERROR)

            elif selected_option == "Delete List":
                xbmc.log("LibraryGenie: LIST ACTION - Executing Delete List", xbmc.LOGINFO)
                # Implement Delete List logic
                xbmcgui.Dialog().notification("LibraryGenie", "Delete List - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Move List":
                xbmc.log("LibraryGenie: LIST ACTION - Executing Move List", xbmc.LOGINFO)
                # Implement Move List logic
                xbmcgui.Dialog().notification("LibraryGenie", "Move List - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Add Movies to List":
                xbmc.log("LibraryGenie: LIST ACTION - Executing Add Movies to List", xbmc.LOGINFO)
                # Implement Add Movies to List logic
                xbmcgui.Dialog().notification("LibraryGenie", "Add Movies to List - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Clear List":
                xbmc.log("LibraryGenie: LIST ACTION - Executing Clear List", xbmc.LOGINFO)
                # Implement Clear List logic
                xbmcgui.Dialog().notification("LibraryGenie", "Clear List - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Export List":
                xbmc.log("LibraryGenie: LIST ACTION - Executing Export List", xbmc.LOGINFO)
                # Implement Export List logic
                xbmcgui.Dialog().notification("LibraryGenie", "Export List - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Information":
                xbmc.log("LibraryGenie: LIST ACTION - Executing List Information", xbmc.LOGINFO)
                xbmc.executebuiltin('Action(Info)')

            elif selected_option == "Settings":
                xbmc.log("LibraryGenie: LIST ACTION - Executing List Settings", xbmc.LOGINFO)
                xbmc.executebuiltin(f'Addon.OpenSettings({addon_id})')
            else:
                xbmc.log(f"LibraryGenie: LIST ACTION - Unknown list option: '{selected_option}'", xbmc.LOGWARNING)

            xbmc.log("LibraryGenie: LIST ACTION - List action handling complete", xbmc.LOGINFO)
            return # Exit after handling list options

        # Handle folder-specific actions
        elif is_lg_folder_item:
            xbmc.log(f"LibraryGenie: FOLDER ACTION - Handling folder option: '{selected_option}'", xbmc.LOGINFO)

            if selected_option == "Rename Folder":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Rename Folder", xbmc.LOGINFO)
                try:
                    # Extract folder_id from current path for rename operation
                    folder_id = None
                    match = re.search(r'folder_id=(\d+)', current_container_path)
                    if match:
                        folder_id = match.group(1)

                    if folder_id:
                        xbmc.log(f"LibraryGenie: FOLDER ACTION - Extracted folder_id: {folder_id}", xbmc.LOGINFO)
                        # Call rename folder function
                        rename_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=rename_folder&folder_id={folder_id})'
                        xbmc.executebuiltin(rename_url)
                    else:
                        xbmc.log("LibraryGenie: FOLDER ACTION - Could not extract folder_id for rename", xbmc.LOGERROR)
                        xbmcgui.Dialog().notification("LibraryGenie", "Could not determine folder to rename", xbmcgui.NOTIFICATION_ERROR, 3000)
                except Exception as e:
                    xbmc.log(f"LibraryGenie: FOLDER ACTION - Error in rename folder: {str(e)}", xbmc.LOGERROR)

            elif selected_option == "Delete Folder":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Delete Folder", xbmc.LOGINFO)
                # Implement Delete Folder logic
                xbmcgui.Dialog().notification("LibraryGenie", "Delete Folder - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Move Folder":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Move Folder", xbmc.LOGINFO)
                # Implement Move Folder logic
                xbmcgui.Dialog().notification("LibraryGenie", "Move Folder - Not implemented yet", xbmcgui.NOTIFICATION_INFO, 3000)

            elif selected_option == "Create New List Here":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Create New List Here", xbmc.LOGINFO)
                try:
                    # Extract folder_id from current path
                    folder_id = None
                    match = re.search(r'folder_id=(\d+)', current_container_path)
                    if match:
                        folder_id = match.group(1)

                    if folder_id:
                        xbmc.log(f"LibraryGenie: FOLDER ACTION - Creating list in folder_id: {folder_id}", xbmc.LOGINFO)
                        create_list_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=create_list&folder_id={folder_id})'
                        xbmc.executebuiltin(create_list_url)
                    else:
                        # Create at root level
                        xbmc.log("LibraryGenie: FOLDER ACTION - Creating list at root level", xbmc.LOGINFO)
                        create_list_url = 'RunPlugin(plugin://plugin.video.librarygenie/?action=create_list)'
                        xbmc.executebuiltin(create_list_url)
                except Exception as e:
                    xbmc.log(f"LibraryGenie: FOLDER ACTION - Error creating list: {str(e)}", xbmc.LOGERROR)

            elif selected_option == "Create New Subfolder":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Create New Subfolder", xbmc.LOGINFO)
                try:
                    # Extract folder_id from current path
                    folder_id = None
                    match = re.search(r'folder_id=(\d+)', current_container_path)
                    if match:
                        folder_id = match.group(1)

                    if folder_id:
                        xbmc.log(f"LibraryGenie: FOLDER ACTION - Creating subfolder in folder_id: {folder_id}", xbmc.LOGINFO)
                        create_folder_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=create_folder&parent_folder_id={folder_id})'
                        xbmc.executebuiltin(create_folder_url)
                    else:
                        # Create at root level
                        xbmc.log("LibraryGenie: FOLDER ACTION - Creating folder at root level", xbmc.LOGINFO)
                        create_folder_url = 'RunPlugin(plugin://plugin.video.librarygenie/?action=create_folder)'
                        xbmc.executebuiltin(create_folder_url)
                except Exception as e:
                    xbmc.log(f"LibraryGenie: FOLDER ACTION - Error creating subfolder: {str(e)}", xbmc.LOGERROR)

            elif selected_option == "Information":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Folder Information", xbmc.LOGINFO)
                xbmc.executebuiltin('Action(Info)')

            elif selected_option == "Settings":
                xbmc.log("LibraryGenie: FOLDER ACTION - Executing Folder Settings", xbmc.LOGINFO)
                xbmc.executebuiltin(f'Addon.OpenSettings({addon_id})')
            else:
                xbmc.log(f"LibraryGenie: FOLDER ACTION - Unknown folder option: '{selected_option}'", xbmc.LOGWARNING)

            xbmc.log("LibraryGenie: FOLDER ACTION - Folder action handling complete", xbmc.LOGINFO)
            return # Exit after handling folder options

        # Handle regular item actions
        if selected_option == "Show Details":
            # Show item details
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF0DC8A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF4BC7B]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR ECECA9A7]', '').replace('[/COLOR]', '')

                # Get item ID from various sources
                item_id = (xbmc.getInfoLabel('ListItem.DBID') or
                          xbmc.getInfoLabel('ListItem.Property(movieid)') or
                          xbmc.getInfoLabel('ListItem.Property(id)') or "")

                encoded_title = quote_plus(clean_title)
                details_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=show_item_details&title={encoded_title}&item_id={item_id})'
                xbmc.executebuiltin(details_url)

            except Exception as details_error:
                xbmc.log(f"LibraryGenie: Error showing details: {str(details_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error showing details", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif selected_option == "Information":
            # Show Kodi information dialog
            xbmc.executebuiltin('Action(Info)')

        elif selected_option == "Remove from List...":
            # Handle removing movie from current list
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF0DC8A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF4BC7B]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

                # Get media_id from ListItem properties (set by listitem_builder)
                media_id = xbmc.getInfoLabel('ListItem.Property(media_id)')
                if not media_id:
                    # Fallback to other ID sources
                    media_id = (xbmc.getInfoLabel('ListItem.DBID') or
                              xbmc.getInfoLabel('ListItem.Property(movieid)') or
                              xbmc.getInfoLabel('ListItem.Property(id)') or "")

                xbmc.log(f"LibraryGenie: Remove from list - Title: {clean_title}, List ID: {viewing_list_id}, Media ID: {media_id}", xbmc.LOGDEBUG)

                if viewing_list_id and media_id:
                    # Use RunPlugin to trigger remove_from_list action
                    encoded_title = quote_plus(clean_title)
                    remove_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list&list_id={viewing_list_id}&media_id={media_id})'
                    xbmc.executebuiltin(remove_url)
                else:
                    xbmcgui.Dialog().notification("LibraryGenie", "Cannot determine list or media ID", xbmcgui.NOTIFICATION_WARNING, 3000)

            except Exception as remove_error:
                xbmc.log(f"LibraryGenie: Error removing movie from list: {str(remove_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error removing movie from list", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif selected_option in ["Add to List...", "Add to Another List..."]:
            # Handle adding movie to list (both library and plugin items)
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF0DC8A]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFF4BC7B]', '').replace('[/COLOR]', '')
                clean_title = clean_title.replace('[COLOR FFECA9A7]', '').replace('[/COLOR]', '')

                # Get item ID from various sources
                item_id = (xbmc.getInfoLabel('ListItem.DBID') or
                          xbmc.getInfoLabel('ListItem.Property(movieid)') or
                          xbmc.getInfoLabel('ListItem.Property(id)') or "")

                # Determine if this is a library item or plugin item
                is_library_item = item_id and item_id.isdigit() and int(item_id) > 0

                if is_library_item:
                    # Use the existing add_to_list action for library items
                    encoded_title = quote_plus(clean_title)
                    add_to_list_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=add_to_list&title={encoded_title}&item_id={item_id})'
                    xbmc.executebuiltin(add_to_list_url)
                else:
                    # For plugin items, use direct context menu handling
                    xbmc.log(f"LibraryGenie: Adding plugin item to list: {clean_title}", xbmc.LOGINFO)

                    try:
                        # Get media manager to extract current item info
                        from resources.lib.media.media_manager import MediaManager
                        media_manager = MediaManager()

                        xbmc.log("LibraryGenie: Extracting media info for plugin item...", xbmc.LOGDEBUG)
                        media_info = media_manager.get_media_info('movie')

                        if media_info:
                            xbmc.log(f"LibraryGenie: Successfully extracted media info for '{media_info.get('title', 'Unknown')}'", xbmc.LOGDEBUG)
                            # Add the plugin item directly
                            add_plugin_item_to_list(media_info)
                        else:
                            xbmc.log("LibraryGenie: Failed to extract media info - no data returned", xbmc.LOGERROR)
                            xbmcgui.Dialog().notification("LibraryGenie", "Failed to extract item information", xbmcgui.NOTIFICATION_ERROR, 3000)

                    except Exception as media_error:
                        xbmc.log(f"LibraryGenie: Error extracting media info: {str(media_error)}", xbmc.LOGERROR)
                        import traceback
                        xbmc.log(f"LibraryGenie: Media extraction traceback: {traceback.format_exc()}", xbmc.LOGERROR)
                        xbmcgui.Dialog().notification("LibraryGenie", "Error extracting item information", xbmcgui.NOTIFICATION_ERROR, 3000)

            except Exception as add_error:
                xbmc.log(f"LibraryGenie: Error adding item to list: {str(add_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error adding item to list", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif selected_option == "Refresh Metadata":
            # Refresh metadata
            try:
                # Get the clean title without color formatting
                clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

                # Get item ID from various sources
                item_id = (xbmc.getInfoLabel('ListItem.DBID') or
                          xbmc.getInfoLabel('ListItem.Property(movieid)') or
                          xbmc.getInfoLabel('ListItem.Property(id)') or "")

                encoded_title = quote_plus(clean_title)
                refresh_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=refresh_metadata&title={encoded_title}&item_id={item_id})'
                xbmc.executebuiltin(refresh_url)

            except Exception as refresh_error:
                xbmc.log(f"LibraryGenie: Error refreshing metadata: {str(refresh_error)}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("LibraryGenie", "Error refreshing metadata", xbmcgui.NOTIFICATION_ERROR, 3000)

        elif "Find Similar Movies..." in selected_option:
            if "(Requires Authentication)" in selected_option:
                xbmcgui.Dialog().notification("LibraryGenie", "Please configure API settings first", xbmcgui.NOTIFICATION_WARNING, 3000)
                return
            # Get the clean title without color formatting
            clean_title = title.replace('[COLOR FF7BC99A]', '').replace('[/COLOR]', '')

            xbmc.log(f"LibraryGenie [DEBUG]: Similarity search - Title: {clean_title}, Year: {year}, IMDb: {imdb_id}", xbmc.LOGDEBUG)

            if not imdb_id or not str(imdb_id).startswith('tt'):
                xbmc.log("LibraryGenie [WARNING]: Similarity search failed - no valid IMDb ID found", xbmc.LOGWARNING)
                xbmcgui.Dialog().notification("LibraryGenie", "No valid IMDb ID found for similarity search", xbmcgui.NOTIFICATION_WARNING, 3000)
                return

            # Use RunPlugin to trigger similarity search
            encoded_title = quote_plus(clean_title)
            similarity_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=find_similar&imdb_id={imdb_id}&title={encoded_title})'
            xbmc.executebuiltin(similarity_url)

        elif "Search Movies..." in selected_option:  # Search Movies - use direct search instead of plugin URL
            if "(Requires Authentication)" in selected_option:
                xbmcgui.Dialog().notification("LibraryGenie", "Please configure API settings first", xbmcgui.NOTIFICATION_WARNING, 3000)
                return
            try:
                # Perform search directly
                search_window = SearchWindow("LibraryGenie Search")
                search_window.doModal()

                # Check if we have a target URL to navigate to
                target_url = search_window.get_target_url()
                if target_url:
                    xbmc.log(f"LibraryGenie: Context menu navigation to: {target_url}", xbmc.LOGINFO)
                    # Give time for modal to fully close
                    xbmc.sleep(300)
                    # Use ActivateWindow for more reliable navigation from context menu
                    xbmc.executebuiltin(f'ActivateWindow(videos,"{target_url}",return)')

            except Exception as search_error:
                xbmc.log(f"LibraryGenie: Context search error: {str(search_error)}", xbmc.LOGERROR)

        elif selected_option == "Search History":  # Search History
            # Get the Search History folder ID
            try:
                config = Config()
                db_manager = DatabaseManager(config.db_path)
                search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

                if search_history_folder_id:
                    url = f"plugin://{addon_id}/?action=browse_folder&folder_id={search_history_folder_id}&view=folder"
                    xbmc.executebuiltin(f'ActivateWindow(videos,{url})')
                else:
                    xbmcgui.Dialog().notification("LibraryGenie", "Search History folder not found", xbmcgui.NOTIFICATION_WARNING, 3000)

            except Exception as e:
                utils.log(f"Error accessing Search History: {str(e)}", "ERROR")
                xbmcgui.Dialog().notification("LibraryGenie", "Error accessing Search History", xbmcgui.NOTIFICATION_ERROR, 3000)
        elif selected_option == "Settings":  # Settings
            xbmc.executebuiltin(f'Addon.OpenSettings({addon_id})')
        # If nothing selected (selected == -1), do nothing

    except Exception as e:
        utils.log(f"Context menu error: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification("LibraryGenie", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)


def add_plugin_item_to_list(media_info):
    """Add a plugin item (non-library) to a selected list with enhanced fallback data"""
    try:
        utils.log("=== ADD PLUGIN ITEM TO LIST: Starting process ===", "DEBUG")
        utils.log(f"ADD PLUGIN ITEM: Received media_info: {media_info}", "DEBUG")

        # Validate media_info
        if not media_info or not isinstance(media_info, dict):
            utils.log(f"ADD PLUGIN ITEM: Invalid media_info received: {media_info}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", "Invalid item information", xbmcgui.NOTIFICATION_ERROR, 3000)
            return

        # Enhance media_info for plugin items
        title = media_info.get('title', 'Unknown')
        utils.log(f"ADD PLUGIN ITEM: Working with title: '{title}'", "DEBUG")

        # For plugin items without IMDb ID, we can still add them with available metadata
        if not media_info.get('imdbnumber'):
            utils.log(f"ADD PLUGIN ITEM: No IMDb ID found for '{title}', will use available metadata", "DEBUG")

            # Create a pseudo-unique identifier for plugin items without IMDb
            import hashlib
            file_path = media_info.get('file', '')
            plugin_id = hashlib.md5(f"{title}_{file_path}".encode()).hexdigest()[:16]
            media_info['plugin_id'] = f"plugin_{plugin_id}"

            # Enhance the plot to indicate this is from a plugin
            current_plot = media_info.get('plot', '')
            if current_plot:
                media_info['plot'] = f"[Plugin Item] {current_plot}"
            else:
                media_info['plot'] = f"[Plugin Item] - Added from {media_info.get('source', 'external addon')}"

        # Use the database manager directly for plugin items
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get all available lists for user selection
        all_lists = db_manager.fetch_all_lists()

        # Get Search History folder ID to exclude its lists
        search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

        # Filter out Search History lists
        filtered_lists = []
        for list_item in all_lists:
            if list_item.get('folder_id') != search_history_folder_id:
                filtered_lists.append(list_item)

        if not filtered_lists:
            utils.log("ADD PLUGIN ITEM: No lists found", "WARNING")
            xbmcgui.Dialog().ok('LibraryGenie', "No lists found. Create a list first.")
            return

        # Create list selection options with "New List" at top
        list_options = ["📝 Create New List"]
        list_ids = [None]  # None indicates "create new list"

        for list_item in filtered_lists:
            # Get folder path for display
            folder_path = ""
            if list_item.get('folder_id'):
                folder = db_manager.fetch_folder_by_id(list_item['folder_id'])
                if folder:
                    folder_path = f"[{folder['name']}] "

            list_options.append(f"{folder_path}{list_item['name']}")
            list_ids.append(list_item['id'])

        # Show list selection dialog
        from typing import Sequence, Union
        typed_list_options: Sequence[Union[str, xbmcgui.ListItem]] = list_options
        selected_index = xbmcgui.Dialog().select(
            f"Add '{title}' to list:",
            typed_list_options
        )

        if selected_index == -1:  # User cancelled
            utils.log("ADD PLUGIN ITEM: User cancelled list selection", "DEBUG")
            return

        selected_list_id = list_ids[selected_index]

        # Handle "Create New List" option
        if selected_list_id is None:
            new_list_name = xbmcgui.Dialog().input('New list name', type=xbmcgui.INPUT_ALPHANUM)
            if not new_list_name:
                utils.log("ADD PLUGIN ITEM: User cancelled new list creation", "DEBUG")
                return

            # Create new list at root level (folder_id=None)
            new_list_result = db_manager.create_list(new_list_name, None)
            if not new_list_result:
                xbmcgui.Dialog().notification('LibraryGenie', 'Failed to create new list', xbmcgui.NOTIFICATION_ERROR)
                return

            selected_list_id = new_list_result['id'] if isinstance(new_list_result, dict) else new_list_result
            utils.log(f"ADD PLUGIN ITEM: Created new list '{new_list_name}' with ID: {selected_list_id}", "DEBUG")

        # For plugin items, create a unique media item entry
        import hashlib
        file_path = media_info.get('file', '')
        unique_id = hashlib.md5(f"{title}_{file_path}".encode()).hexdigest()[:16]

        # Create media item data for plugin item
        media_item_data = {
            'kodi_id': 0,  # No Kodi ID for plugin items
            'title': title,
            'year': int(media_info.get('year', 0)) if media_info.get('year', '').isdigit() else 0,
            'imdbnumber': media_info.get('imdbnumber', ''),  # May be empty for plugin items
            'source': 'plugin_addon',
            'plot': media_info.get('plot', f'[Plugin Item] - Added from external addon'),
            'rating': 0.0,
            'search_score': 0,
            'media_type': 'movie',
            'genre': media_info.get('genre', ''),
            'director': media_info.get('director', ''),
            'cast': media_info.get('cast', '[]'),
            'file': media_info.get('file', ''),
            'thumbnail': media_info.get('thumbnail', ''),
            'poster': media_info.get('poster', ''),
            'fanart': media_info.get('fanart', ''),
            'art': media_info.get('art', '{}'),
            'duration': media_info.get('duration', 0),
            'votes': 0,
            'play': f"plugin_item://{unique_id}"  # Unique identifier for plugin items
        }

        utils.log(f"ADD PLUGIN ITEM: Creating media item for '{title}' with data: {media_item_data}", "DEBUG")

        # Add the media item to the selected list
        success = db_manager.add_media_item(selected_list_id, media_item_data)

        if success:
            selected_list_name = next((lst['name'] for lst in filtered_lists if lst['id'] == selected_list_id), 'New List')
            utils.log(f"ADD PLUGIN ITEM: Successfully added '{title}' to list '{selected_list_name}'", "INFO")
            xbmcgui.Dialog().notification(
                'LibraryGenie',
                f"Added '{title}' to '{selected_list_name}'",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
        else:
            utils.log(f"ADD PLUGIN ITEM: Failed to add '{title}' to list", "ERROR")
            xbmcgui.Dialog().notification(
                'LibraryGenie',
                f"Failed to add '{title}' to list",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )

    except Exception as e:
        utils.log(f"ADD PLUGIN ITEM TO LIST: Error: {str(e)}", "ERROR")
        import traceback
        utils.log(f"ADD PLUGIN ITEM TO LIST: Traceback: {traceback.format_exc()}", "ERROR")
        xbmcgui.Dialog().notification(
            'LibraryGenie',
            'Error adding plugin item to list',
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


if __name__ == '__main__':
    main()