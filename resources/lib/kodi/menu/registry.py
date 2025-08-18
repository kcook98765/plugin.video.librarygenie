
"""
Context Menu Registry for LibraryGenie
Centralized context menu logic based on MediaItem properties
"""
from typing import List, Tuple, Optional
from ...data.models import MediaItem
from ...utils import utils


def for_item(item: MediaItem, view_hint: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    Generate context menu entries for a MediaItem
    
    Args:
        item: MediaItem to generate menu for
        view_hint: Optional context about the current view
    
    Returns:
        List of (label, action_url) tuples for context menu
    """
    try:
        menu_items = []
        
        # Always available: Add to List
        if not item.is_folder:
            menu_items.append(_build_add_to_list_entry(item))
        
        # Authentication-dependent items
        if _is_authenticated():
            # Find Similar Movies (only for movies with IMDb ID)
            if (item.media_type == 'movie' and 
                item.imdb and 
                str(item.imdb).startswith('tt')):
                menu_items.append(_build_find_similar_entry(item))
        
        # List-specific actions (when viewing a list)
        if hasattr(item, 'context_tags') and item.context_tags:
            if 'in_list' in item.context_tags:
                menu_items.append(_build_remove_from_list_entry(item))
        
        # Folder/List management actions
        if item.is_folder:
            folder_type = _get_folder_type(item)
            if folder_type == 'list':
                menu_items.extend(_build_list_management_entries(item))
            elif folder_type == 'folder':
                menu_items.extend(_build_folder_management_entries(item))
        
        utils.log(f"Generated {len(menu_items)} context menu items for '{item.title}'", "DEBUG")
        return menu_items
        
    except Exception as e:
        utils.log(f"Error generating context menu for '{item.title}': {str(e)}", "ERROR")
        return []


def _is_authenticated() -> bool:
    """Check if user has API authentication for advanced features"""
    try:
        from ...config.addon_ref import get_addon
        addon = get_addon()
        
        # Check remote API credentials
        api_url = addon.getSetting('remote_api_url')
        api_key = addon.getSetting('remote_api_key')
        
        # Check LGS credentials as backup
        lgs_url = addon.getSetting('lgs_upload_url')
        lgs_key = addon.getSetting('lgs_upload_key')
        
        return bool((api_url and api_key) or (lgs_url and lgs_key))
        
    except Exception as e:
        utils.log(f"Error checking authentication: {str(e)}", "WARNING")
        return False


def _build_add_to_list_entry(item: MediaItem) -> Tuple[str, str]:
    """Build 'Add to List' context menu entry"""
    from urllib.parse import quote_plus
    
    # Clean title for URL encoding
    clean_title = _clean_title(item.title) if item.title else "Unknown"
    encoded_title = quote_plus(clean_title)
    
    # Use different parameters based on item source
    if hasattr(item, 'extras') and item.extras.get('movieid'):
        # Kodi library item
        item_id = item.extras['movieid']
        action_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=add_to_list&title={encoded_title}&item_id={item_id})'
    else:
        # Plugin or external item
        action_url = f'RunPlugin(plugin://plugin.video.librarygenie/?action=add_plugin_item_to_list&title={encoded_title})'
    
    return ("Add to List", action_url)


def _build_find_similar_entry(item: MediaItem) -> Tuple[str, str]:
    """Build 'Find Similar Movies' context menu entry"""
    from urllib.parse import quote_plus
    
    clean_title = _clean_title(item.title) if item.title else "Unknown"
    encoded_title = quote_plus(clean_title)
    
    action_url = (f'RunPlugin(plugin://plugin.video.librarygenie/?action=find_similar_movies'
                 f'&title={encoded_title}&imdb_id={item.imdb})')
    
    return ("Find Similar Movies", action_url)


def _build_remove_from_list_entry(item: MediaItem) -> Tuple[str, str]:
    """Build 'Remove from List' context menu entry"""
    # Extract list context from item
    list_id = None
    media_id = None
    
    if hasattr(item, 'extras') and item.extras:
        list_id = item.extras.get('_viewing_list_id')
        media_id = item.extras.get('media_id') or item.extras.get('list_item_id')
    
    if list_id and media_id:
        action_url = (f'RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list'
                     f'&list_id={list_id}&media_id={media_id})')
        return ("Remove from List", action_url)
    
    # Fallback if context not available
    return ("Remove from List", 'RunPlugin(plugin://plugin.video.librarygenie/?action=remove_from_list)')


def _build_list_management_entries(item: MediaItem) -> List[Tuple[str, str]]:
    """Build management entries for list items"""
    entries = []
    
    # Extract list_id from item context
    list_id = None
    if hasattr(item, 'extras') and item.extras:
        list_id = item.extras.get('list_id')
    
    if list_id:
        entries.append(("Rename List", f'RunPlugin(plugin://plugin.video.librarygenie/?action=rename_list&list_id={list_id})'))
        entries.append(("Delete List", f'RunPlugin(plugin://plugin.video.librarygenie/?action=delete_list&list_id={list_id})'))
        entries.append(("Move List", f'RunPlugin(plugin://plugin.video.librarygenie/?action=move_list&list_id={list_id})'))
        entries.append(("Clear List", f'RunPlugin(plugin://plugin.video.librarygenie/?action=clear_list&list_id={list_id})'))
        entries.append(("Export List", f'RunPlugin(plugin://plugin.video.librarygenie/?action=export_list&list_id={list_id})'))
    
    return entries


def _build_folder_management_entries(item: MediaItem) -> List[Tuple[str, str]]:
    """Build management entries for folder items"""
    entries = []
    
    # Extract folder_id from item context
    folder_id = None
    if hasattr(item, 'extras') and item.extras:
        folder_id = item.extras.get('folder_id')
    
    if folder_id:
        # Check for protected folders
        protected_folders = {"Search History", "Imported Lists"}
        if item.title not in protected_folders:
            entries.append(("Rename Folder", f'RunPlugin(plugin://plugin.video.librarygenie/?action=rename_folder&folder_id={folder_id})'))
            entries.append(("Delete Folder", f'RunPlugin(plugin://plugin.video.librarygenie/?action=delete_folder&folder_id={folder_id})'))
            entries.append(("Move Folder", f'RunPlugin(plugin://plugin.video.librarygenie/?action=move_folder&folder_id={folder_id})'))
    
    return entries


def _get_folder_type(item: MediaItem) -> str:
    """Determine if folder item is a 'list' or 'folder'"""
    # Check lg_type property first
    if hasattr(item, 'extras') and item.extras:
        lg_type = item.extras.get('lg_type')
        if lg_type in ['list', 'folder']:
            return lg_type
    
    # Fallback to context tags
    if hasattr(item, 'context_tags') and item.context_tags:
        if 'list' in item.context_tags:
            return 'list'
        elif 'folder' in item.context_tags:
            return 'folder'
    
    # Default assumption
    return 'folder'


def _clean_title(title: str) -> str:
    """Clean title for URL encoding"""
    import re
    
    if not title:
        return title
    
    # Remove emoji characters
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+",
        flags=re.UNICODE
    )
    
    cleaned = emoji_pattern.sub('', title).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned
