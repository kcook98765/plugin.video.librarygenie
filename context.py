#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Context Menu Script
Handles context menu actions for adding media to lists
"""

import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import urllib.parse
from typing import List, Union

# Import localization module
from lib.ui.localization import L


def _is_folder_context(container_path, file_path):
    """Check if we're in a folder context within LibraryGenie"""
    try:
        # Check if we're within LibraryGenie plugin
        container_is_lg = container_path and container_path.startswith('plugin://plugin.video.librarygenie/')
        file_is_lg = file_path and file_path.startswith('plugin://plugin.video.librarygenie/')

        is_lg_plugin = container_is_lg or file_is_lg
        if not is_lg_plugin:
            return False

        # Check for folder-specific URL parameters
        container_has_folder = container_path and ('folder_id=' in container_path or 'list_type=folder' in container_path)
        file_has_folder = file_path and ('folder_id=' in file_path or 'list_type=folder' in file_path)

        is_folder = container_has_folder or file_has_folder

        return bool(is_folder)

    except Exception as e:
        xbmc.log(f"LibraryGenie: Error detecting folder context: {str(e)}", xbmc.LOGERROR)
        return False


def main():
    """Main context menu handler"""
    try:
        # Check if we're within LibraryGenie plugin - if so, skip global context menu
        container_path = xbmc.getInfoLabel('Container.FolderPath')
        if container_path and container_path.startswith('plugin://plugin.video.librarygenie/'):
            xbmc.log("LibraryGenie: Skipping global context menu within plugin", xbmc.LOGINFO)
            return

        addon = xbmcaddon.Addon()

        # Comprehensive context debugging - capture ALL available information
        context_info = {
            'container_path': xbmc.getInfoLabel('Container.FolderPath'),
            'container_content': xbmc.getInfoLabel('Container.Content'),
            'container_label': xbmc.getInfoLabel('Container.Label'),
            'listitem_path': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'listitem_label': xbmc.getInfoLabel('ListItem.Label'),
            'listitem_dbtype': xbmc.getInfoLabel('ListItem.DBTYPE'),
            'listitem_dbid': xbmc.getInfoLabel('ListItem.DBID'),
            'listitem_title': xbmc.getInfoLabel('ListItem.Title'),
            'listitem_plot': xbmc.getInfoLabel('ListItem.Plot'),
            'window_property': xbmc.getInfoLabel('Window.Property(xmlfile)'),
            'current_window': xbmc.getInfoLabel('System.CurrentWindow'),
            'current_control': xbmc.getInfoLabel('System.CurrentControl'),
        }


        # Test folder context detection with detailed logging
        container_path = context_info['container_path']
        file_path = context_info['listitem_path']

        # Skip context menu for folder contexts
        is_folder_context = _is_folder_context(container_path, file_path)
        if is_folder_context:
            return

        # Show LibraryGenie submenu with conditional options for non-folder contexts
        _show_librarygenie_menu(addon)

    except Exception as e:
        xbmc.log(f"LibraryGenie context menu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Context menu error occurred",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _get_imdb_id():
    """Get IMDb ID - first try InfoLabel, then query database if needed"""
    # Step 1: Try ListItem.IMDBNumber InfoLabel first
    imdb_from_infolabel = xbmc.getInfoLabel('ListItem.IMDBNumber').strip()
    xbmc.log(f"[LG SIMILAR] ListItem.IMDBNumber: '{imdb_from_infolabel}'", xbmc.LOGINFO)
    
    # Check if it's a valid IMDb ID (starts with 'tt')
    if imdb_from_infolabel and imdb_from_infolabel.startswith('tt'):
        xbmc.log(f"[LG SIMILAR] ✓ Valid IMDb ID from InfoLabel: {imdb_from_infolabel}", xbmc.LOGINFO)
        return imdb_from_infolabel
    
    # If it's just numeric, it's a Kodi DB ID, not an IMDb ID
    if imdb_from_infolabel and imdb_from_infolabel.isdigit():
        xbmc.log(f"[LG SIMILAR] InfoLabel is numeric (Kodi DB ID): '{imdb_from_infolabel}' - will lookup in database", xbmc.LOGINFO)
    
    # Step 2: Query database using DBID to get actual IMDb ID
    dbid = xbmc.getInfoLabel('ListItem.DBID').strip()
    xbmc.log(f"[LG SIMILAR] ListItem.DBID: '{dbid}'", xbmc.LOGINFO)
    
    if dbid and dbid.isdigit():
        try:
            # Use the same pattern as the rest of context.py
            from lib.data.query_manager import get_query_manager
            query_manager = get_query_manager()
            
            if not query_manager.initialize():
                xbmc.log("[LG SIMILAR] Failed to initialize query manager", xbmc.LOGERROR)
                return ''
            
            # Get dbtype if available, otherwise try to infer from container
            dbtype = xbmc.getInfoLabel('ListItem.DBTYPE').strip()
            xbmc.log(f"[LG SIMILAR] ListItem.DBTYPE: '{dbtype}'", xbmc.LOGINFO)
            
            if not dbtype:
                # Infer from container content
                if xbmc.getCondVisibility('Container.Content(movies)'):
                    dbtype = 'movie'
                    xbmc.log("[LG SIMILAR] Inferred dbtype='movie' from Container.Content", xbmc.LOGINFO)
                elif xbmc.getCondVisibility('Container.Content(episodes)'):
                    dbtype = 'episode'
                    xbmc.log("[LG SIMILAR] Inferred dbtype='episode' from Container.Content", xbmc.LOGINFO)
            
            # Direct SQL query through query_manager's connection
            with query_manager.connection_manager.get_connection() as conn:
                # Query with or without media_type filter
                if dbtype:
                    xbmc.log(f"[LG SIMILAR] Querying DB: kodi_id={dbid}, media_type={dbtype}", xbmc.LOGINFO)
                    result = conn.execute(
                        "SELECT imdbnumber FROM media_items WHERE kodi_id = ? AND media_type = ? AND is_removed = 0",
                        [dbid, dbtype]
                    ).fetchone()
                else:
                    xbmc.log(f"[LG SIMILAR] Querying DB: kodi_id={dbid} (no media_type filter)", xbmc.LOGINFO)
                    result = conn.execute(
                        "SELECT imdbnumber FROM media_items WHERE kodi_id = ? AND is_removed = 0",
                        [dbid]
                    ).fetchone()
                
                if result and result[0]:
                    imdb_id = result[0].strip()
                    xbmc.log(f"[LG SIMILAR] DB returned IMDb ID: '{imdb_id}'", xbmc.LOGINFO)
                    # Only return if it starts with 'tt'
                    if imdb_id.startswith('tt'):
                        xbmc.log(f"[LG SIMILAR] ✓ Using IMDb ID from DB: {imdb_id}", xbmc.LOGINFO)
                        return imdb_id
                    else:
                        xbmc.log(f"[LG SIMILAR] DB IMDb ID doesn't start with 'tt', rejecting: {imdb_id}", xbmc.LOGINFO)
                else:
                    xbmc.log("[LG SIMILAR] No IMDb ID found in DB", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[LG SIMILAR] DB query error: {str(e)}", xbmc.LOGERROR)
            import traceback
            xbmc.log(f"[LG SIMILAR] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
    else:
        xbmc.log("[LG SIMILAR] No valid DBID available for DB lookup", xbmc.LOGINFO)
    
    xbmc.log("[LG SIMILAR] No valid IMDb ID found", xbmc.LOGINFO)
    return ''


def _show_librarygenie_menu(addon):
    """Show LibraryGenie submenu with conditional options"""
    try:
        # IMPORTANT: Cache all item info BEFORE showing any dialogs
        # This prevents losing context when the dialog opens
        item_info = {
            'dbtype': xbmc.getInfoLabel('ListItem.DBTYPE'),
            'dbid': xbmc.getInfoLabel('ListItem.DBID'),
            'file_path': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'navigation_path': xbmc.getInfoLabel('ListItem.Path'),
            'title': xbmc.getInfoLabel('ListItem.Title'),
            'label': xbmc.getInfoLabel('ListItem.Label'),
            'media_item_id': xbmc.getInfoLabel('ListItem.Property(media_item_id)'),
            'list_id': xbmc.getInfoLabel('ListItem.Property(list_id)'),
            'container_content': xbmc.getInfoLabel('Container.Content'),
            'is_movies': xbmc.getCondVisibility('Container.Content(movies)'),
            'is_episodes': xbmc.getCondVisibility('Container.Content(episodes)'),
            'year': xbmc.getInfoLabel('ListItem.Year'),
        }
        
        # Get IMDb ID - only returns if it starts with 'tt'
        item_info['imdbnumber'] = _get_imdb_id()


        # Build options list
        options = []
        actions = []

        # Use cached values instead of fresh getInfoLabel calls
        dbtype = item_info['dbtype']
        dbid = item_info['dbid']
        file_path = item_info['file_path']


        # FIRST: Check if we're in a LibraryGenie context (prioritize this over regular library items)
        container_path = xbmc.getInfoLabel('Container.FolderPath')

        # Check for LibraryGenie context indicators
        is_librarygenie_context = (
            container_path.startswith('plugin://plugin.video.librarygenie/') or
            (file_path and file_path.startswith('plugin://plugin.video.librarygenie/'))
        )

        # Add common LibraryGenie actions in order of priority
        _add_common_lg_options(options, actions, addon, item_info, is_librarygenie_context)


        # Show the menu if options are available
        if len(options) > 0:
            dialog = xbmcgui.Dialog()
            selected = dialog.select("LibraryGenie", options)

            if selected >= 0:
                _execute_action(actions[selected], addon, item_info)

    except Exception as e:
        xbmc.log(f"LibraryGenie submenu error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Menu error occurred",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _add_common_lg_options(options, actions, addon, item_info, is_librarygenie_context):
    """Add common LibraryGenie options in priority order"""

    # Check settings for quick add and other configurations
    try:
        from lib.config.settings import SettingsManager
        settings = SettingsManager()
        quick_add_enabled = settings.get_enable_quick_add()
        default_list_id = settings.get_default_list_id()
    except Exception:
        quick_add_enabled = False
        default_list_id = ""
    
    # Check if AI search is available (config activated AND has API key)
    ai_search_available = False
    try:
        from lib.auth.state import is_authorized
        from lib.config.settings import SettingsManager
        settings = SettingsManager()
        ai_search_activated = settings.get_ai_search_activated()
        has_api_key = is_authorized()
        ai_search_available = ai_search_activated and has_api_key
    except Exception:
        pass

    # Determine if we're in a list context for remove option
    container_path = xbmc.getInfoLabel('Container.FolderPath')
    in_list_context = 'list_id=' in container_path or item_info.get('list_id')

    # Check if this is a playable media item (not a folder or navigation item)
    # Use Kodi's definitive flags for robust detection
    is_folder = xbmc.getCondVisibility('ListItem.IsFolder')
    is_playable = xbmc.getCondVisibility('ListItem.IsPlayable')
    
    # Add Import File Media option for folders (Files browser, network shares, etc.)
    if is_folder and not is_librarygenie_context and not is_playable:
        folder_path = item_info.get('file_path') or item_info.get('navigation_path')
        if folder_path:
            # Only exclude Kodi library paths - allow everything else
            # Import handler will validate if it can handle the path
            if not folder_path.startswith('library://'):
                options.append("LG Import File Structure and Media")
                actions.append(f"import_file_media&source_url={urllib.parse.quote(folder_path)}")
    
    is_playable_item = (
        # Has valid library metadata for movies/episodes (exclude dbid '0')
        (item_info.get('dbtype') in ('movie', 'episode') and 
         item_info.get('dbid') and item_info.get('dbid') not in ('', '0')) or
        # Has LibraryGenie media item ID  
        item_info.get('media_item_id') or
        # In a media container, is playable and not a folder
        ((item_info.get('is_movies') or item_info.get('is_episodes')) and 
         item_info.get('title') and is_playable and not is_folder)
    )

    # Only show "Add to List" options for playable media items 
    if is_playable_item:
        # 2. LG Quick Add (if enabled and configured)
        if quick_add_enabled and default_list_id:
            quick_add_label = L(30380)  # "LG Quick Add"
            options.append(quick_add_label)

            # Determine appropriate quick add action based on context
            if item_info.get('media_item_id'):
                actions.append(f"quick_add&media_item_id={item_info['media_item_id']}")
            elif item_info.get('dbtype') and item_info.get('dbid'):
                actions.append(f"quick_add_context&dbtype={item_info['dbtype']}&dbid={item_info['dbid']}&title={item_info.get('title', '')}")
            else:
                actions.append("quick_add_external")

        # 3. LG Add to List...
        add_list_label = L(30381)  # "LG Add to List..."
        options.append(add_list_label)

        # Determine appropriate add action based on context
        if item_info.get('media_item_id'):
            actions.append(f"add_to_list&media_item_id={item_info['media_item_id']}")
        elif item_info.get('dbtype') and item_info.get('dbid'):
            actions.append(f"add_to_list&dbtype={item_info['dbtype']}&dbid={item_info['dbid']}&title={item_info.get('title', '')}")
        else:
            actions.append("add_external_item")

    # 4. LG Remove from List (if in list context and is playable item)
    if in_list_context and is_playable_item:
        remove_label = L(30382)  # "LG Remove from List"
        options.append(remove_label)

        # Extract list_id for remove action
        list_id = item_info.get('list_id')
        if not list_id and 'list_id=' in container_path:
            import re
            list_id_match = re.search(r'list_id=(\d+)', container_path)
            if list_id_match:
                list_id = list_id_match.group(1)

        # Determine appropriate remove action
        if item_info.get('media_item_id') and list_id:
            actions.append(f"remove_from_list&list_id={list_id}&item_id={item_info['media_item_id']}")
        elif item_info.get('dbtype') and item_info.get('dbid') and list_id:
            actions.append(f"remove_library_item_from_list&list_id={list_id}&dbtype={item_info['dbtype']}&dbid={item_info['dbid']}&title={item_info.get('title', '')}")
        else:
            actions.append("remove_from_list_generic")

    # 5. LG Find Similar Movies (if AI search is available and item has valid IMDb ID)
    # Determine if this is a movie - use dbtype or infer from container
    is_movie = item_info.get('dbtype') == 'movie' or (
        not item_info.get('dbtype') and item_info.get('is_movies')
    )
    
    xbmc.log(f"[LG SIMILAR] Menu check: ai_search_available={ai_search_available}, is_playable_item={is_playable_item}, is_movie={is_movie}", xbmc.LOGINFO)
    xbmc.log(f"[LG SIMILAR] Menu check: dbtype='{item_info.get('dbtype')}', is_movies={item_info.get('is_movies')}, imdbnumber='{item_info.get('imdbnumber')}'", xbmc.LOGINFO)
    
    if ai_search_available and is_playable_item and is_movie:
        imdb_id = item_info.get('imdbnumber', '').strip()
        
        # Only show option if we have a valid IMDb ID (already validated to start with 'tt')
        if imdb_id:
            xbmc.log(f"[LG SIMILAR] ✓ Adding 'Find Similar Movies' option for: {item_info.get('title')} (IMDb: {imdb_id})", xbmc.LOGINFO)
            similar_label = "LG Find Similar Movies"
            options.append(similar_label)
            
            # Build action with required parameters
            title = item_info.get('title', 'Unknown')
            year = item_info.get('year', '')
            actions.append(f"find_similar_movies&imdb_id={imdb_id}&title={urllib.parse.quote(title)}&year={year}")
        else:
            xbmc.log(f"[LG SIMILAR] ✗ No valid IMDb ID, hiding option for: {item_info.get('title')}", xbmc.LOGINFO)
    else:
        reason = []
        if not ai_search_available:
            reason.append("AI search not available")
        if not is_playable_item:
            reason.append("not playable item")
        if not is_movie:
            reason.append("not a movie")
        xbmc.log(f"[LG SIMILAR] ✗ Hiding option: {', '.join(reason)}", xbmc.LOGINFO)

    # 6. Save Link to Bookmarks (if not in LibraryGenie folder context)
    # Only show for navigable folders/containers
    container_path = xbmc.getInfoLabel('Container.FolderPath')
    if not _is_folder_context(container_path, item_info.get('file_path')):
        bookmark_label = L(30394)  # "LG Save Bookmark"
        options.append(bookmark_label)
        
        # Use container path for bookmarking the current folder location
        if container_path:
            actions.append("confirm_save_bookmark")
        else:
            actions.append("save_bookmark_generic")


def _show_search_submenu(addon):
    """Show the search submenu with various search options"""
    try:
        # Check settings for conditional options
        from lib.config.settings import SettingsManager
        try:
            settings = SettingsManager()
            favorites_enabled = settings.get_enable_favorites_integration()
        except Exception:
            favorites_enabled = False

        # Check if AI search is available/authorized
        ai_search_available = False
        try:
            from lib.config.config_manager import get_config
            config = get_config()
            ai_search_activated = config.get_bool('ai_search_activated', False)
            ai_search_api_key = config.get('ai_search_api_key', '')
            ai_search_available = ai_search_activated and ai_search_api_key
        except Exception:
            pass

        # Build search submenu options
        options = []
        actions = []

        # Local Movie Search
        movie_search_label = L(30385)  # "Local Movie Search"
        options.append(movie_search_label)
        actions.append("search_movies")

        # Local TV Search
        tv_search_label = L(30386)  # "Local TV Search"
        options.append(tv_search_label)
        actions.append("search_tv")

        # AI Movie Search (if available)
        if ai_search_available:
            ai_search_label = L(30387)  # "AI Movie Search"
            options.append(ai_search_label)
            actions.append("search_ai")

        # Search History
        search_history_label = L(30388)  # "Search History"
        options.append(search_history_label)
        actions.append("show_search_history")

        # Kodi Favorites (if enabled)
        if favorites_enabled:
            favorites_label = L(30389)  # "Kodi Favorites"
            options.append(favorites_label)
            actions.append("show_favorites")

        # Show the submenu
        dialog = xbmcgui.Dialog()
        selected = dialog.select("LibraryGenie Search Options", options)

        if selected >= 0:
            _execute_action(actions[selected], addon)

    except Exception as e:
        xbmc.log(f"LibraryGenie search submenu error: {str(e)}", xbmc.LOGERROR)
        # Fallback to basic search
        _execute_action("search", addon)




def _add_library_movie_options(dbtype, dbid, options, actions, addon):
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
    quick_add_enabled = settings.get_enable_quick_add()
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
    actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=add_to_list&dbtype={dbtype}&dbid={dbid}&title={xbmc.getInfoLabel('ListItem.Title')})")


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
        from lib.config.settings import SettingsManager
        if SettingsManager:
            settings = SettingsManager()
            quick_add_enabled = settings.get_enable_quick_add()
            default_list_id = settings.get_default_list_id()
        else:
            # Fallback to ConfigManager if SettingsManager not available
            from lib.config.config_manager import get_config
            config = get_config()
            quick_add_enabled = config.get_bool('quick_add_enabled', False)
            default_list_id = config.get('default_list_id', "")
    except Exception:
        # Fallback to ConfigManager
        from lib.config.config_manager import get_config
        config = get_config()
        quick_add_enabled = config.get_bool('quick_add_enabled', False)
        default_list_id = config.get('default_list_id', "")

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
    actions.append(f"RunPlugin(plugin://{addon.getAddonInfo('id')}/?action=search_from_context&query={xbmc.getInfoLabel('ListItem.TVShowTitle')} {xbmc.getInfoLabel('ListItem.Title')})")




def _add_external_item_options(options, actions, addon):
    """Add options for external/plugin items"""
    # For external items, we can only do add to list (no quick add since we need to gather metadata)
    add_to_list_label = L(31000)  # "Add to List..."
    options.append(add_to_list_label)
    actions.append("add_external_item")


def _add_librarygenie_item_options(options, actions, addon, item_info):
    """Add options for LibraryGenie items"""
    xbmc.log(f"LibraryGenie: _add_librarygenie_item_options called with item_info: {item_info}", xbmc.LOGINFO)

    # Use cached item metadata
    media_item_id = item_info['media_item_id']
    list_id = item_info['list_id']
    dbtype = item_info['dbtype']
    dbid = item_info['dbid']
    container_path = xbmc.getInfoLabel('Container.FolderPath')

    xbmc.log(f"LibraryGenie: Current container path: {container_path}", xbmc.LOGINFO)


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
        from lib.config.config_manager import get_config
        config = get_config()
        quick_add_enabled = config.get_bool('quick_add_enabled', False)
        default_list_id = config.get('default_list_id', "")

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
    elif dbtype in ('movie', 'episode') and dbid and dbid not in ('0', ''):
        xbmc.log(f"LibraryGenie: Using library item path for {dbtype} {dbid}", xbmc.LOGINFO)

        # If we're in a list context, add remove option first
        if extracted_list_id and item_info.get('title'):
            remove_label = L(31010) if L(31010) else "Remove from List"
            options.append(remove_label)
            # For library items in lists without media_item_id, we need to identify by title/dbid
            title = item_info.get('title', '')
            actions.append(f"remove_library_item_from_list&list_id={extracted_list_id}&dbtype={dbtype}&dbid={dbid}&title={title}")
            xbmc.log(f"LibraryGenie: Added remove option for library item {dbtype} {dbid} in list {extracted_list_id}", xbmc.LOGINFO)

        # Add LibraryGenie-specific add options (not the full library options to avoid duplicates)
        # Check if quick-add is enabled and has a default list configured
        from lib.config.config_manager import get_config
        config = get_config()
        quick_add_enabled = config.get_bool('quick_add_enabled', False)
        default_list_id = config.get('default_list_id', "")

        if quick_add_enabled and default_list_id:
            quick_add_label = L(31001) if L(31001) else "Quick Add to Default"
            options.append(quick_add_label)
            actions.append(f"quick_add_context&dbtype={dbtype}&dbid={dbid}&title={item_info.get('title', '')}")

        add_to_list_label = L(31000) if L(31000) else "Add to List..."
        options.append(add_to_list_label)
        actions.append(f"add_to_list&dbtype={dbtype}&dbid={dbid}&title={item_info.get('title', '')}")

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


def _execute_action(action_with_params, addon, item_info=None):
    """Execute the selected action"""
    try:
        if action_with_params == "show_search_submenu":
            # Show the search submenu
            _show_search_submenu(addon)

        elif action_with_params == "search" or action_with_params == "search_movies":
            # Launch LibraryGenie search (default to movies) - PUSH semantics for navigation
            plugin_url = "plugin://plugin.video.librarygenie/?action=search"
            xbmc.executebuiltin(f"ActivateWindow(Videos,{plugin_url})")

        elif action_with_params == "search_tv":
            # Launch LibraryGenie TV search - PUSH semantics for navigation
            plugin_url = "plugin://plugin.video.librarygenie/?action=search&content_type=episodes"
            xbmc.executebuiltin(f"ActivateWindow(Videos,{plugin_url})")

        elif action_with_params == "search_ai":
            # Launch AI Movie Search - PUSH semantics for navigation
            plugin_url = "plugin://plugin.video.librarygenie/?action=ai_search"
            xbmc.executebuiltin(f"ActivateWindow(Videos,{plugin_url})")
        
        elif action_with_params.startswith("find_similar_movies&"):
            # Handle Find Similar Movies action
            plugin_url = f"plugin://plugin.video.librarygenie/?action={action_with_params}"
            xbmc.executebuiltin(f"RunPlugin({plugin_url})")
        
        elif action_with_params.startswith("import_file_media&"):
            # Handle Import File Media action
            params = {}
            for param in action_with_params.split('&')[1:]:
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = urllib.parse.unquote(value)
            
            source_url = params.get('source_url', '')
            if source_url:
                plugin_url = f"plugin://plugin.video.librarygenie/?action=import_file_media&source_url={urllib.parse.quote(source_url)}"
                xbmc.executebuiltin(f"RunPlugin({plugin_url})")

        elif action_with_params == "search_history":
            # Show search history - PUSH semantics for navigation
            plugin_url = "plugin://plugin.video.librarygenie/?action=show_search_history"
            xbmc.executebuiltin(f"ActivateWindow(Videos,{plugin_url})")

        elif action_with_params == "show_favorites":
            # Show Kodi Favorites - PUSH semantics for navigation
            plugin_url = "plugin://plugin.video.librarygenie/?action=show_favorites"
            xbmc.executebuiltin(f"ActivateWindow(Videos,{plugin_url})")

        elif action_with_params == "add_external_item":
            # Handle external item by gathering metadata
            _handle_external_item_add(addon)

        elif action_with_params == "confirm_save_bookmark":
            # Show confirmation dialog for bookmark saving
            _handle_bookmark_confirmation(addon)
            
        elif action_with_params.startswith("save_bookmark"):
            # Handle bookmark saving actions
            _handle_bookmark_save(action_with_params, addon)
            
        elif action_with_params.startswith("remove_from_list") or action_with_params.startswith("remove_library_item_from_list"):
            # Handle remove actions - pure context actions, no endOfDirectory
            plugin_url = f"plugin://plugin.video.librarygenie/?action={action_with_params}"
            xbmc.log(f"LibraryGenie: Executing remove action: {plugin_url}", xbmc.LOGINFO)
            xbmc.executebuiltin(f"RunPlugin({plugin_url})")
            xbmc.log(f"LibraryGenie: Remove action executed, waiting for result", xbmc.LOGINFO)

        else:
            # Handle other actions - pure context actions, no endOfDirectory
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
            'navigation_path': xbmc.getInfoLabel('ListItem.Path'),  # Try ListItem.Path for navigation URL
            'media_type': 'movie'  # Default, will be refined below
        }

        # Try to determine media type from context
        if xbmc.getCondVisibility('Container.Content(episodes)'):
            item_data['media_type'] = 'episode'
            item_data['tvshowtitle'] = xbmc.getInfoLabel('ListItem.TVShowTitle')
            item_data['season'] = xbmc.getInfoLabel('ListItem.Season')
            item_data['episode'] = xbmc.getInfoLabel('ListItem.Episode')
            item_data['aired'] = xbmc.getInfoLabel('ListItem.Aired')
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

        # Art data is handled through individual fields below for URL compatibility

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
            # Skip dictionary values like art_data
            if isinstance(value, dict):
                cleaned_data[key] = value
                continue

            if value and str(value).strip():
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
                    cleaned_data[key] = str(value).strip()

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

        # Handle bookmark save directly without plugin calls
        _save_bookmark_directly(cleaned_data, addon)

    except Exception as e:
        xbmc.log(f"LibraryGenie external item add error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Failed to process external item",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _save_bookmark_directly(item_data, addon):
    """Save bookmark directly to database without plugin calls"""
    try:
        # Initialize database connection directly
        from lib.data.query_manager import get_query_manager
        query_manager = get_query_manager()
        if not query_manager.initialize():
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Database initialization failed",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return
        
        # Check if list_id is pre-selected (e.g., from confirmation dialog)
        target_list_id = item_data.get('list_id')
        
        if target_list_id:
            # Direct addition to specified list
            try:
                selected_list_id = int(target_list_id)
                # Verify the list exists
                list_info = query_manager.get_list_by_id(selected_list_id)
                if not list_info:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Target list not found",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    return
                selected_list_name = list_info.get('name', 'Unknown List')
            except (ValueError, TypeError):
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Invalid list ID",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return
        else:
            # Get all available lists for selection
            all_lists = query_manager.get_all_lists_with_folders()
            if not all_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("LibraryGenie", "No lists found. Create a new list?"):
                    list_name = xbmcgui.Dialog().input("Enter list name:", type=xbmcgui.INPUT_ALPHANUM)
                    if list_name:
                        # Create new list
                        result = query_manager.create_list(list_name.strip())
                        if result and result.get('success'):
                            selected_list_id = result.get('list_id')
                            selected_list_name = list_name.strip()
                        else:
                            xbmcgui.Dialog().notification(
                                "LibraryGenie",
                                "Failed to create list",
                                xbmcgui.NOTIFICATION_ERROR,
                                3000
                            )
                            return
                    else:
                        return
                else:
                    return
            else:
                # Build list selection options
                list_options = []
                list_ids = []
                
                for item in all_lists:
                    if item.get('type') == 'list':
                        list_name = item['name']
                        list_options.append(list_name)
                        list_ids.append(item['id'])
                
                if not list_options:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "No lists available",
                        xbmcgui.NOTIFICATION_WARNING,
                        3000
                    )
                    return
                
                # Show list selection dialog
                selected_index = xbmcgui.Dialog().select(
                    f"Add '{item_data['title']}' to list:",
                    list_options
                )
                
                if selected_index < 0:
                    return  # User cancelled
                
                selected_list_id = int(list_ids[selected_index])
                selected_list_name = list_options[selected_index]
        
        # Determine the best URL for bookmark navigation
        # Use conditional logic based on item type and context
        navigation_path = item_data.get('navigation_path', '')
        file_path = item_data.get('file_path', '')
        container_path = xbmc.getInfoLabel('Container.FolderPath')
        is_folder = xbmc.getCondVisibility('ListItem.IsFolder')
        
        # Get additional context for special cases including database ID
        title = item_data.get('title', '')
        label = item_data.get('label', '')
        
        # Get the numeric database ID for videodb items - this is the key!
        dbid = xbmc.getInfoLabel('ListItem.DBID')
        
        # Debug logging for bookmark URL detection (can be removed after testing)
        xbmc.log(f"LibraryGenie: Bookmark context - Container: {container_path}, DBID: {dbid}, Label: {xbmc.getInfoLabel('ListItem.Label')}", xbmc.LOGDEBUG)
        
        # Special handling for different container types
        
        # Handle plugin content (addons)
        if container_path and container_path.startswith('plugin://') and is_folder:
            # For plugin content, use the actual plugin path not the container path
            plugin_path = xbmc.getInfoLabel('ListItem.FileNameAndPath') or xbmc.getInfoLabel('ListItem.Path')
            if plugin_path and plugin_path.startswith('plugin://'):
                bookmark_url = plugin_path
                xbmc.log(f"LibraryGenie: Plugin content bookmark - using plugin path: {plugin_path}", xbmc.LOGINFO)
            else:
                bookmark_url = file_path
                xbmc.log(f"LibraryGenie: Plugin content - no plugin path found, using file_path: {file_path}", xbmc.LOGINFO)
                
        # Handle music database content (musicdb://)
        elif container_path and 'musicdb://' in container_path and is_folder:
            # Handle musicdb URLs similar to videodb
            if dbid:
                bookmark_url = f"{container_path.rstrip('/')}/{dbid}/"
                xbmc.log(f"LibraryGenie: Constructed musicdb URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
            else:
                item_label = xbmc.getInfoLabel('ListItem.Label') or title or label
                if item_label:
                    import urllib.parse
                    encoded_label = urllib.parse.quote(item_label.replace(' ', '%20'))
                    bookmark_url = f"{container_path.rstrip('/')}/{encoded_label}/"
                    xbmc.log(f"LibraryGenie: Constructed musicdb URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                else:
                    bookmark_url = file_path
                    xbmc.log(f"LibraryGenie: Musicdb - no DBID or label, using file_path: {file_path}", xbmc.LOGINFO)
                    
        # Handle special protocol URLs (special://)
        elif container_path and container_path.startswith('special://') and is_folder:
            # For special paths, use the actual path
            special_path = xbmc.getInfoLabel('ListItem.FileNameAndPath') or xbmc.getInfoLabel('ListItem.Path')
            if special_path:
                bookmark_url = special_path
                xbmc.log(f"LibraryGenie: Special protocol bookmark - using path: {special_path}", xbmc.LOGINFO)
            else:
                bookmark_url = file_path
                xbmc.log(f"LibraryGenie: Special protocol - no path found, using file_path: {file_path}", xbmc.LOGINFO)
        
        # Handle file system sources (SMB, NFS, local paths, etc.)
        elif container_path and container_path.startswith('sources://') and is_folder:
            # For file system sources, use the actual file path not the container path
            actual_path = xbmc.getInfoLabel('ListItem.FileNameAndPath') or xbmc.getInfoLabel('ListItem.Path')
            if actual_path:
                bookmark_url = actual_path
                xbmc.log(f"LibraryGenie: File system source bookmark - using actual path: {actual_path}", xbmc.LOGINFO)
            else:
                bookmark_url = file_path
                xbmc.log(f"LibraryGenie: File system source - no actual path found, using file_path: {file_path}", xbmc.LOGINFO)
                
        # Handle videodb and musicdb navigation using actual database IDs or labels
        elif container_path and ('videodb://' in container_path or 'musicdb://' in container_path) and is_folder:
            # Primary: Try to use numeric database ID
            if dbid:
                # Construct proper videodb URL using the numeric database ID
                if 'movies/genres' in container_path:
                    bookmark_url = f"videodb://movies/genres/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed genre URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'tvshows/genres' in container_path:
                    bookmark_url = f"videodb://tvshows/genres/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed TV genre URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'movies/sets' in container_path:
                    bookmark_url = f"videodb://movies/sets/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed movie set URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'movies/years' in container_path:
                    bookmark_url = f"videodb://movies/years/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed year URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'movies/actors' in container_path:
                    bookmark_url = f"videodb://movies/actors/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed actor URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'movies/directors' in container_path:
                    bookmark_url = f"videodb://movies/directors/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed director URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'movies/studios' in container_path:
                    bookmark_url = f"videodb://movies/studios/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed studio URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'tvshows/actors' in container_path:
                    bookmark_url = f"videodb://tvshows/actors/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed TV actor URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'tvshows/years' in container_path:
                    bookmark_url = f"videodb://tvshows/years/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed TV year URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'tvshows/titles' in container_path:
                    bookmark_url = f"videodb://tvshows/titles/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed TV show URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                elif 'movies/titles' in container_path:
                    bookmark_url = f"videodb://movies/titles/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed movie URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                # Music database URL patterns
                elif 'musicdb://' in container_path:
                    # Special containers that don't use DBID (like recently added)
                    if 'recentlyaddedalbums' in container_path or 'recentlyaddedmusic' in container_path or 'recentlyplayedalbums' in container_path or 'recentlyplayedsongs' in container_path or 'compilations' in container_path:
                        # Keep the original container path without appending DBID
                        bookmark_url = container_path
                        xbmc.log(f"LibraryGenie: Using special music container path: {bookmark_url}", xbmc.LOGINFO)
                    elif 'artists' in container_path:
                        bookmark_url = f"musicdb://artists/{dbid}/"
                        xbmc.log(f"LibraryGenie: Constructed music artist URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                    elif 'albums' in container_path:
                        bookmark_url = f"musicdb://albums/{dbid}/"
                        xbmc.log(f"LibraryGenie: Constructed music album URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                    elif 'genres' in container_path:
                        bookmark_url = f"musicdb://genres/{dbid}/"
                        xbmc.log(f"LibraryGenie: Constructed music genre URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                    elif 'songs' in container_path:
                        bookmark_url = f"musicdb://songs/{dbid}/"
                        xbmc.log(f"LibraryGenie: Constructed music song URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                    elif 'years' in container_path:
                        bookmark_url = f"musicdb://years/{dbid}/"
                        xbmc.log(f"LibraryGenie: Constructed music year URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                    else:
                        # Generic musicdb URL construction with DBID
                        bookmark_url = f"{container_path.rstrip('/')}/{dbid}/"
                        xbmc.log(f"LibraryGenie: Constructed generic musicdb URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
                else:
                    # Generic videodb URL construction with DBID
                    bookmark_url = f"{container_path.rstrip('/')}/{dbid}/"
                    xbmc.log(f"LibraryGenie: Constructed generic videodb URL with DBID {dbid}: {bookmark_url}", xbmc.LOGINFO)
            else:
                # Fallback: Use label when no DBID is available (e.g., years, some collections)
                item_label = xbmc.getInfoLabel('ListItem.Label') or title or label
                if item_label:
                    # URL encode the label for safety - avoid double-encoding
                    import urllib.parse
                    encoded_label = urllib.parse.quote(item_label, safe='')
                    
                    if 'movies/years' in container_path:
                        bookmark_url = f"videodb://movies/years/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed year URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    elif 'tvshows/years' in container_path:
                        bookmark_url = f"videodb://tvshows/years/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed TV year URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    elif 'movies/genres' in container_path:
                        bookmark_url = f"videodb://movies/genres/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed genre URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    elif 'tvshows/genres' in container_path:
                        bookmark_url = f"videodb://tvshows/genres/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed TV genre URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    elif 'tvshows/titles' in container_path:
                        bookmark_url = f"videodb://tvshows/titles/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed TV show URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    elif 'movies/titles' in container_path:
                        bookmark_url = f"videodb://movies/titles/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed movie URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    # Music database URL patterns with labels
                    elif 'musicdb://' in container_path:
                        # Special containers that don't use labels (like recently added)
                        if 'recentlyaddedalbums' in container_path or 'recentlyaddedmusic' in container_path or 'recentlyplayedalbums' in container_path or 'recentlyplayedsongs' in container_path or 'compilations' in container_path:
                            # Keep the original container path without appending label
                            bookmark_url = container_path
                            xbmc.log(f"LibraryGenie: Using special music container path (no label): {bookmark_url}", xbmc.LOGINFO)
                        elif 'artists' in container_path:
                            bookmark_url = f"musicdb://artists/{encoded_label}/"
                            xbmc.log(f"LibraryGenie: Constructed music artist URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                        elif 'albums' in container_path:
                            bookmark_url = f"musicdb://albums/{encoded_label}/"
                            xbmc.log(f"LibraryGenie: Constructed music album URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                        elif 'genres' in container_path:
                            bookmark_url = f"musicdb://genres/{encoded_label}/"
                            xbmc.log(f"LibraryGenie: Constructed music genre URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                        elif 'songs' in container_path:
                            bookmark_url = f"musicdb://songs/{encoded_label}/"
                            xbmc.log(f"LibraryGenie: Constructed music song URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                        elif 'years' in container_path:
                            bookmark_url = f"musicdb://years/{encoded_label}/"
                            xbmc.log(f"LibraryGenie: Constructed music year URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                        else:
                            # Generic musicdb URL construction with label
                            bookmark_url = f"{container_path.rstrip('/')}/{encoded_label}/"
                            xbmc.log(f"LibraryGenie: Constructed generic musicdb URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                    else:
                        # Generic videodb URL construction with label
                        bookmark_url = f"{container_path.rstrip('/')}/{encoded_label}/"
                        xbmc.log(f"LibraryGenie: Constructed generic videodb URL with label '{item_label}': {bookmark_url}", xbmc.LOGINFO)
                else:
                    # Last resort: use file_path
                    bookmark_url = file_path
                    xbmc.log(f"LibraryGenie: No DBID or label available, using file_path: {file_path}", xbmc.LOGINFO)
        # For folders, prefer ListItem.Path if it's different from container path
        elif is_folder and navigation_path and navigation_path != container_path:
            bookmark_url = navigation_path
            xbmc.log(f"LibraryGenie: Using navigation_path for folder bookmark: {navigation_path}", xbmc.LOGINFO)
        else:
            bookmark_url = file_path
            xbmc.log(f"LibraryGenie: Using file_path for bookmark: {file_path} (is_folder={is_folder})", xbmc.LOGINFO)
        
        # Edge case validation - ensure we have a valid bookmark URL
        if not bookmark_url or bookmark_url.strip() == "":
            xbmc.log(f"LibraryGenie: ERROR - Empty bookmark URL generated for '{item_data['title']}'", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Unable to create bookmark for '{item_data['title']}' - no valid URL found",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return
            
        # Validate URL format - basic sanity check
        if len(bookmark_url) > 2000:  # URLs shouldn't be extremely long
            xbmc.log(f"LibraryGenie: WARNING - Very long bookmark URL ({len(bookmark_url)} chars): {bookmark_url[:100]}...", xbmc.LOGWARNING)
        
        # Create stable ID for bookmark with backward compatibility check
        import hashlib
        stable_id = hashlib.sha1(bookmark_url.encode('utf-8')).hexdigest()[:16]
        
        # Check for existing bookmark using old file_path hash for backward compatibility
        old_stable_id = hashlib.sha1(file_path.encode('utf-8')).hexdigest()[:16] if file_path != bookmark_url else None
        
        # Add the bookmark to the selected list
        try:
            with query_manager.connection_manager.transaction() as conn:
                # Use the standard add_item_to_list method
                result = query_manager.add_item_to_list(
                    list_id=selected_list_id,
                    title=item_data['title'],
                    year=item_data.get('year'),
                    imdb_id=item_data.get('imdbnumber'),
                    tmdb_id=item_data.get('tmdb_id'),
                    kodi_id=item_data.get('kodi_id'),
                    art_data={},  # Art will be handled separately
                    tvshowtitle=item_data.get('tvshowtitle'),
                    season=item_data.get('season'),
                    episode=item_data.get('episode'),
                    aired=item_data.get('aired')
                )
                
                # If successful, update the media item to store the bookmark URL
                if result and result.get('id'):
                    media_item_id = result['id']
                    
                    # Update the media item to include bookmark data and mark as folder
                    conn.execute("""
                        UPDATE media_items 
                        SET play = ?, file_path = ?, source = 'bookmark', plot = ?, media_type = 'folder'
                        WHERE id = ?
                    """, [bookmark_url, bookmark_url, f"Bookmark: {item_data['title']}", media_item_id])
                    
                    # Success notification
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Added '{item_data['title']}' to '{selected_list_name}'",
                        xbmcgui.NOTIFICATION_INFO,
                        3000
                    )
                    
                    # Refresh container to show changes if we're in the plugin
                    container_path = xbmc.getInfoLabel('Container.FolderPath')
                    if 'plugin.video.librarygenie' in container_path:
                        xbmc.executebuiltin('Container.Refresh')
                    
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Failed to add bookmark to list",
                        xbmcgui.NOTIFICATION_ERROR,
                        3000
                    )
                    
        except Exception as e:
            xbmc.log(f"LibraryGenie bookmark save error: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Failed to save bookmark",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
    
    except Exception as e:
        xbmc.log(f"LibraryGenie bookmark save error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Bookmark save failed",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _handle_bookmark_save(action_with_params, addon):
    """Handle saving current location as a bookmark"""
    try:
        # Parse action parameters
        params = {}
        if '&' in action_with_params:
            param_string = action_with_params.split('&', 1)[1]
            for param in param_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = urllib.parse.unquote(value)
        
        # Get URL and name from parameters
        bookmark_url = params.get('url')
        bookmark_name = params.get('name', 'Unnamed Bookmark')
        
        if not bookmark_url:
            # Fallback to current container path
            bookmark_url = xbmc.getInfoLabel('Container.FolderPath')
            if not bookmark_url:
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "Unable to determine location to bookmark",
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
                return
        
        # Decode URL
        bookmark_url = urllib.parse.unquote(bookmark_url)
        
        # Determine bookmark type based on URL with expanded scheme detection
        bookmark_type = 'plugin'  # Default
        url_lower = bookmark_url.lower()
        
        # Network protocols
        network_schemes = ('smb://', 'nfs://', 'ftp://', 'sftp://', 'ftps://', 'http://', 'https://', 'dav://', 'davs://', 'upnp://')
        if any(url_lower.startswith(scheme) for scheme in network_schemes):
            bookmark_type = 'network'
        # File paths
        elif url_lower.startswith('file://') or (len(url_lower) > 2 and url_lower[1:3] == ':\\'):
            bookmark_type = 'file'
        # Special Kodi paths
        elif url_lower.startswith('special://'):
            bookmark_type = 'special'
        # Library database URLs
        elif url_lower.startswith('videodb://') or url_lower.startswith('musicdb://'):
            bookmark_type = 'library'
        # Plugin URLs (includes unrecognized schemes as fallback)
        else:
            bookmark_type = 'plugin'
        
        # Gather additional metadata
        metadata = {
            'container_content': xbmc.getInfoLabel('Container.Content'),
            'container_label': xbmc.getInfoLabel('Container.Label'),
            'saved_from': 'context_menu',
            'created_date': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Gather artwork if available
        art_data = {}
        fanart = xbmc.getInfoLabel('Container.Art(fanart)')
        if fanart:
            art_data['fanart'] = fanart
        icon = xbmc.getInfoLabel('Container.Art(icon)')
        if icon:
            art_data['icon'] = icon
        thumb = xbmc.getInfoLabel('Container.Art(thumb)')
        if thumb:
            art_data['thumb'] = thumb
        
        # Save bookmark directly without plugin calls
        bookmark_data = {
            'title': bookmark_name,
            'file_path': bookmark_url,
            'media_type': 'movie',  # Bookmarks use movie type for database compatibility
            'metadata': metadata,
            'art_data': art_data
        }
        
        _save_bookmark_directly(bookmark_data, addon)
        
    except Exception as e:
        xbmc.log(f"LibraryGenie bookmark save error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Failed to save bookmark",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def _detect_media_type(container_path):
    """Detect media type from container path and return appropriate prefix"""
    if not container_path:
        return 'OTH'
    
    # Convert to lowercase for case-insensitive matching
    path_lower = container_path.lower()
    
    if 'musicdb://' in path_lower:
        return 'MUS'
    elif 'videodb://tvshows/' in path_lower:
        return 'TV'
    elif 'videodb://movies/' in path_lower:
        return 'MOV'
    else:
        return 'OTH'


def _generate_smart_bookmark_name():
    """Generate intelligent bookmark name based on Container.FolderName and item context"""
    try:
        # Get container and item information
        container_path = xbmc.getInfoLabel('Container.FolderPath')
        container_folder_name = xbmc.getInfoLabel('Container.FolderName')
        
        # Detect media type for prefix
        media_prefix = _detect_media_type(container_path)
        xbmc.log(f"LibraryGenie: Smart naming - Detected media type: '{media_prefix}' from path: '{container_path}'", xbmc.LOGINFO)
        
        # Get item name using fallback logic: Label → Title → FileNameAndPath
        item_label = xbmc.getInfoLabel('ListItem.Label')
        item_title = xbmc.getInfoLabel('ListItem.Title')
        item_filename_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
        
        # Debug logging to track what we're getting
        xbmc.log(f"LibraryGenie: Smart naming - Container.FolderName: '{container_folder_name}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: Smart naming - ListItem.Label: '{item_label}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: Smart naming - ListItem.Title: '{item_title}'", xbmc.LOGINFO)
        xbmc.log(f"LibraryGenie: Smart naming - ListItem.FileNameAndPath: '{item_filename_path}'", xbmc.LOGINFO)
        
        # Determine the item name with fallback logic
        item_name = ''
        if item_label and item_label not in ('ListItem.Label', ''):
            item_name = item_label
            xbmc.log(f"LibraryGenie: Smart naming - Using Label: '{item_name}'", xbmc.LOGINFO)
        elif item_title and item_title not in ('ListItem.Title', ''):
            item_name = item_title
            xbmc.log(f"LibraryGenie: Smart naming - Using Title: '{item_name}'", xbmc.LOGINFO)
        elif item_filename_path and item_filename_path not in ('ListItem.FileNameAndPath', ''):
            # Extract just the filename from the full path for display
            import os
            item_name = os.path.basename(item_filename_path.rstrip('/'))
            xbmc.log(f"LibraryGenie: Smart naming - Using FileNameAndPath: '{item_name}'", xbmc.LOGINFO)
        
        # Get container folder name for prefix - normalize music folders to friendlier names
        folder_name = ''
        if container_folder_name and container_folder_name not in ('Container.FolderName', ''):
            # Map technical music/video folder names to user-friendly names
            if container_folder_name == 'Artists':
                folder_name = 'Artists'
            elif container_folder_name == 'Albums':
                folder_name = 'Albums'
            elif container_folder_name == 'Genres':
                folder_name = 'Genres'
            elif container_folder_name == 'Songs':
                folder_name = 'Songs'
            elif container_folder_name == 'Years':
                folder_name = 'Years'
            elif 'Recently added' in container_folder_name or 'recently added' in container_folder_name:
                folder_name = 'Recently Added'
            elif 'Recently played' in container_folder_name or 'recently played' in container_folder_name:
                folder_name = 'Recently Played'
            else:
                folder_name = container_folder_name
            xbmc.log(f"LibraryGenie: Smart naming - Using FolderName: '{folder_name}'", xbmc.LOGINFO)
        
        # Create smart bookmark name with media type prefix
        if folder_name and item_name:
            # Format: MUS: (Container.FolderName) Item Name
            result = f"{media_prefix}: ({folder_name}) {item_name}"
            xbmc.log(f"LibraryGenie: Smart naming - Final result: '{result}'", xbmc.LOGINFO)
            return result
        elif item_name:
            # Just the item name with media prefix if no container context
            result = f"{media_prefix}: {item_name}"
            xbmc.log(f"LibraryGenie: Smart naming - Item only: '{result}'", xbmc.LOGINFO)
            return result
        elif folder_name:
            # Just the folder name with media prefix if no item context
            result = f"{media_prefix}: {folder_name}"
            xbmc.log(f"LibraryGenie: Smart naming - Folder only: '{result}'", xbmc.LOGINFO)
            return result
        else:
            # Final fallback with media prefix
            result = f"{media_prefix}: Current Location"
            xbmc.log(f"LibraryGenie: Smart naming - Using fallback: '{result}'", xbmc.LOGINFO)
            return result
            
    except Exception as e:
        xbmc.log(f"LibraryGenie: Error generating smart bookmark name: {e}", xbmc.LOGWARNING)
        return 'Current Location'


def _handle_bookmark_confirmation(addon):
    """Show confirmation dialog for bookmark saving with name editing and folder selection"""
    try:
        # Get current location information
        container_path = xbmc.getInfoLabel('Container.FolderPath')
        
        # Generate intelligent bookmark name
        container_label = _generate_smart_bookmark_name()
        
        xbmc.log(f"LibraryGenie: Generated smart bookmark name: '{container_label}'", xbmc.LOGINFO)
        
        if not container_path:
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                "Unable to determine location to bookmark",
                xbmcgui.NOTIFICATION_WARNING,
                3000
            )
            return
        
        # Show dialog to edit bookmark name
        dialog = xbmcgui.Dialog()
        
        # Step 1: Ask user to confirm and edit bookmark name
        bookmark_name = dialog.input(
            "Bookmark Name",
            container_label,
            xbmcgui.INPUT_ALPHANUM
        )
        
        if not bookmark_name:  # User cancelled
            return
            
        # Step 2: Ask user to choose which list to add bookmark to
        try:
            from lib.data.query_manager import get_query_manager
            query_manager = get_query_manager()
            
            if not query_manager.initialize():
                dialog.notification(
                    "LibraryGenie",
                    "Failed to load lists",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return
            
            # Get all lists and folders for selection
            all_lists = query_manager.get_all_lists_with_folders()
            
            if not all_lists:
                # No lists exist - offer to create one
                create_list = dialog.yesno(
                    "LibraryGenie",
                    "No lists found. Create a new list for your bookmark?"
                )
                if not create_list:
                    return
                    
                # Ask for list name
                new_list_name = dialog.input(
                    "Create New List",
                    "Bookmarks",
                    xbmcgui.INPUT_ALPHANUM
                )
                if not new_list_name:
                    return
                    
                # For simplicity, guide user to create list through main interface
                dialog.notification(
                    "LibraryGenie",
                    "Please create a list first through My Lists menu, then try bookmarking again",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )
                return
            else:
                # Show existing lists for selection
                list_options = []
                list_ids = []
                
                # Add "Create New List" option at the top
                list_options.append("+ Create New List")
                list_ids.append("new")
                
                # Add existing lists (all items from get_all_lists_with_folders are lists)
                for item in all_lists:
                    folder_path = item.get('folder_name', '')  # Use folder_name from query result
                    if folder_path:
                        label = f"{folder_path} > {item['name']}"
                    else:
                        label = f"{item['name']}"
                    list_options.append(label)
                    list_ids.append(str(item['id']))
                
                selected_list = dialog.select(
                    "Add Bookmark to List",
                    list_options
                )
                
                if selected_list == -1:  # User cancelled
                    return
                    
                if selected_list == 0:  # Create new list
                    # Guide user to create list through main interface
                    dialog.notification(
                        "LibraryGenie",
                        "Please create a list first through My Lists menu, then try bookmarking again",
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )
                    return
                else:
                    list_id = list_ids[selected_list]
                    
        except Exception as e:
            xbmc.log(f"LibraryGenie: Error loading lists: {str(e)}", xbmc.LOGERROR)
            dialog.notification(
                "LibraryGenie",
                "Failed to load lists",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return
        
        # Save bookmark directly without plugin calls
        bookmark_data = {
            'title': bookmark_name,
            'file_path': container_path,  # Don't URL encode for internal use
            'media_type': 'movie',  # Bookmarks use movie type for database compatibility
            'list_id': list_id  # Pre-selected list from dialog
        }
        
        _save_bookmark_directly(bookmark_data, addon)
        
    except Exception as e:
        xbmc.log(f"LibraryGenie bookmark confirmation error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Failed to save bookmark",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


if __name__ == '__main__':
    main()