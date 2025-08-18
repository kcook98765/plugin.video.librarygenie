
"""
Context Menu Registry for LibraryGenie
Centralized context menu logic based on MediaItem properties
"""
from typing import List, Tuple, Optional, Union
from ...data.models import MediaItem
from ...utils import utils


def for_item(item: MediaItem) -> List[Tuple[str, str]]:
    """
    Generate context menu items for a MediaItem
    
    Args:
        item: MediaItem to generate menu for
    
    Returns:
        List of (label, action) tuples for context menu
    """
    try:
        menu_items = []
        
        # Check if this is a folder or list item
        if item.is_folder:
            if item.media_type == 'folder':
                menu_items.extend(_get_folder_menu(item))
            else:
                menu_items.extend(_get_list_menu(item))
        else:
            # Regular media item
            menu_items.extend(_get_media_menu(item))
            
            # Add list-specific items if viewing from a list
            if 'in_list' in item.context_tags:
                menu_items.extend(_get_list_item_menu(item))
        
        return menu_items
        
    except Exception as e:
        utils.log(f"Error generating context menu for '{item.title}': {str(e)}", "ERROR")
        return []


def _get_media_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for regular media items"""
    from ..url_builder import build_plugin_url
    
    menu_items = []
    
    # Add to list - always available if we have a title
    if item.title and item.title != "Unknown":
        menu_items.append(
            ("Add to List", f"RunPlugin({build_plugin_url({'action': 'add_to_list', 'title': item.title, 'item_id': item.id})})")
        )
    
    # Find similar movies - only if we have IMDb ID and authentication
    if item.imdb and item.imdb.startswith('tt'):
        if _is_authenticated():
            menu_items.append(
                ("Find Similar Movies", f"RunPlugin({build_plugin_url({'action': 'find_similar', 'imdb_id': item.imdb, 'title': item.title})})")
            )
        else:
            menu_items.append(
                ("Find Similar Movies (Auth Required)", "")
            )
    
    # Refresh metadata
    menu_items.append(
        ("Refresh Metadata", f"RunPlugin({build_plugin_url({'action': 'refresh_metadata', 'title': item.title, 'item_id': item.id})})")
    )
    
    return menu_items


def _get_folder_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for folders"""
    from ..url_builder import build_plugin_url
    
    folder_id = item.extras.get('folder_id') or item.id
    
    menu_items = [
        ("Rename Folder", f"RunPlugin({build_plugin_url({'action': 'rename_folder', 'folder_id': folder_id})})"),
        ("Move Folder", f"RunPlugin({build_plugin_url({'action': 'move_folder', 'folder_id': folder_id})})"),
        ("Create New List Here", f"RunPlugin({build_plugin_url({'action': 'create_list', 'folder_id': folder_id})})"),
        ("Create New Subfolder", f"RunPlugin({build_plugin_url({'action': 'create_folder', 'parent_folder_id': folder_id})})"),
        ("Delete Folder", f"RunPlugin({build_plugin_url({'action': 'delete_folder', 'folder_id': folder_id})})")
    ]
    
    return menu_items


def _get_list_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for lists"""
    from ..url_builder import build_plugin_url

    list_id = item.extras.get('list_id') or item.id
    
    menu_items = [
        ("Rename List", f"RunPlugin({build_plugin_url({'action': 'rename_list', 'list_id': list_id})})"),
        ("Move List", f"RunPlugin({build_plugin_url({'action': 'move_list', 'list_id': list_id})})"),
        ("Clear List", f"RunPlugin({build_plugin_url({'action': 'clear_list', 'list_id': list_id})})"),
        ("Export List", f"RunPlugin({build_plugin_url({'action': 'export_list', 'list_id': list_id})})"),
        ("Delete List", f"RunPlugin({build_plugin_url({'action': 'delete_list', 'list_id': list_id})})")
    ]

    return menu_items


def _get_list_item_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for items within lists"""
    from ..url_builder import build_plugin_url

    list_id = item.extras.get('_viewing_list_id')
    if not list_id:
        return []

    menu_items: List[Tuple[str, str]] = [
        ("Remove from List", f"RunPlugin({build_plugin_url({'action': 'remove_from_list', 'list_id': list_id, 'media_id': item.id})})")
    ]

    return menu_items


def _is_authenticated() -> bool:
    """Check if user is authenticated for API features"""
    try:
        from ...config.config_manager import Config
        config = Config()
        
        # Check if we have API credentials
        api_key = config.get_setting('remote_api_key')
        api_url = config.get_setting('remote_api_server_url')
        
        return bool(api_key and api_url)
        
    except Exception:
        return False


class ContextMenuRegistry:
    """Legacy wrapper for backwards compatibility"""
    
    def __init__(self):
        pass
        
    def _is_authenticated(self) -> bool:
        """Legacy method - delegates to module function"""
        return _is_authenticated()
