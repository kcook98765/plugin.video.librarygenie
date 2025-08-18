"""
Context Menu Registry for LibraryGenie
Centralized context menu logic based on MediaItem properties
"""
from typing import List, Tuple, Optional, Union
from ...data.models import MediaItem
from ...utils import utils


def for_item(item: MediaItem, view_hint: Optional[Union[str, object]] = None) -> List[Tuple[str, str]]:
    """
    Generate context menu entries for a MediaItem

    Args:
        item: MediaItem to generate menus for
        view_hint: Optional hint about the view context

    Returns:
        List of (label, action_url) tuples for context menu
    """
    menu_items = []

    try:
        # Import URL builder
        from ..url_builder import build_plugin_url

        # Handle different item types based on context tags and media type
        if 'folder' in item.context_tags:
            menu_items.extend(_get_folder_menu(item))

        elif 'list' in item.context_tags:
            menu_items.extend(_get_list_menu(item))

        elif 'in_list' in item.context_tags:
            menu_items.extend(_get_list_item_menu(item))

        elif item.media_type == 'movie' and item.imdb and item.imdb.startswith('tt'):
            menu_items.extend(_get_movie_menu(item))

        # Add similarity search if IMDb ID available
        if item.imdb and item.imdb.startswith('tt'):
            menu_items.append((
                "Find Similar Movies",
                f"RunPlugin({build_plugin_url({'action': 'find_similar_movies', 'imdb_id': item.imdb, 'title': item.title})})"
            ))

        utils.log(f"Generated {len(menu_items)} context menu items for '{item.title}'", "DEBUG")
        return menu_items

    except Exception as e:
        utils.log(f"Error generating context menu for '{item.title}': {str(e)}", "ERROR")
        return []


def _get_folder_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for folders"""
    from ..url_builder import build_plugin_url

    folder_id = item.extras.get('folder_id')
    if not folder_id:
        return []

    menu_items = [
        ("Create New List", f"RunPlugin({build_plugin_url({'action': 'create_list', 'folder_id': folder_id})})"),
        ("Create Subfolder", f"RunPlugin({build_plugin_url({'action': 'create_subfolder', 'parent_folder_id': folder_id})})"),
        ("Rename Folder", f"RunPlugin({build_plugin_url({'action': 'rename_folder', 'folder_id': folder_id})})"),
        ("Move Folder", f"RunPlugin({build_plugin_url({'action': 'move_folder', 'folder_id': folder_id})})"),
        ("Delete Folder", f"RunPlugin({build_plugin_url({'action': 'delete_folder', 'folder_id': folder_id})})")
    ]

    return menu_items


def _get_list_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for lists"""
    from ..url_builder import build_plugin_url

    list_id = item.extras.get('list_id')
    if not list_id:
        return []

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

    list_id = item.extras.get('list_id')
    if not list_id:
        return []

    menu_items = [
        ("Remove from List", f"RunPlugin({build_plugin_url({'action': 'remove_from_list', 'list_id': list_id, 'media_id': item.id})})")
    ]

    return menu_items


def _get_movie_menu(item: MediaItem) -> List[Tuple[str, str]]:
    """Generate menu items for movies"""
    from ..url_builder import build_plugin_url
    import urllib.parse

    menu_items = []

    # Add to list option
    if item.imdb:
        encoded_title = urllib.parse.quote_plus(item.title)
        menu_items.append((
            "Add to List",
            f"RunPlugin({build_plugin_url({'action': 'add_to_list', 'title': encoded_title, 'imdb_id': item.imdb, 'year': str(item.year)})})"
        ))

    return menu_items