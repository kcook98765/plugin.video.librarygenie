
"""
ListItem Factory for LibraryGenie
Single entry point for creating Kodi ListItems from MediaItem objects
"""
import xbmcgui
from typing import Union
from ...data.models import MediaItem
from ..adapters.infotag_adapter import apply_infotag
from ..adapters.art_mapper import apply_art
from ..menu.registry import for_item
from ...utils import utils


def build_listitem(item: MediaItem, view_hint: Union[str, None] = None) -> xbmcgui.ListItem:
    """
    Build a complete Kodi ListItem from MediaItem
    
    Args:
        item: MediaItem containing all media information
        view_hint: Optional hint about the viewing context ('folder', 'list', 'search_history', etc.)
    
    Returns:
        Configured xbmcgui.ListItem ready for display
    """
    try:
        # Create base ListItem
        li = xbmcgui.ListItem(item.title or "Unknown")
        
        # Set basic properties
        li.setIsFolder(item.is_folder)
        
        # Set label2 based on context
        label2 = _get_label2(item, view_hint)
        if label2:
            li.setLabel2(label2)
        
        # Apply InfoTag data (version-specific)
        apply_infotag(item, li)
        
        # Apply art mapping
        apply_art(item, li)
        
        # Set additional properties
        _set_properties(li, item, view_hint)
        
        # Set sort keys if available
        _set_sort_properties(li, item)
        
        # Add context menu items
        context_menu = for_item(item)
        if context_menu:
            li.addContextMenuItems(context_menu, replaceItems=False)
        
        utils.log(f"Built ListItem for '{item.title}' (type: {item.media_type})", "DEBUG")
        return li
        
    except Exception as e:
        utils.log(f"Failed to build ListItem for '{item.title}': {str(e)}", "ERROR")
        # Return minimal ListItem as fallback
        fallback_li = xbmcgui.ListItem(item.title or "Unknown")
        fallback_li.setIsFolder(item.is_folder)
        return fallback_li


def _get_label2(item: MediaItem, view_hint: Union[str, None]) -> str:
    """Generate label2 based on item and context"""
    try:
        if view_hint == 'search_history':
            # Show search score for search results
            if item.sort_keys.get('search_score'):
                score = item.sort_keys.get('search_score')
                return f"Score: {score:.1f}"
        
        # Default: show year if available
        if item.year and item.year > 0:
            return str(item.year)
        
        return ""
        
    except Exception:
        return ""


def _set_properties(li: xbmcgui.ListItem, item: MediaItem, view_hint: Union[str, None]) -> None:
    """Set additional ListItem properties"""
    try:
        # Set media ID for context menu operations
        if item.id:
            li.setProperty('media_id', str(item.id))
        
        # Set IMDb ID for external operations
        if item.imdb:
            li.setProperty('imdb_id', item.imdb)
        
        # Set TMDb ID if available
        if item.tmdb:
            li.setProperty('tmdb_id', item.tmdb)
        
        # Set type indicators for context menu detection
        if item.is_folder:
            if item.media_type == 'folder':
                li.setProperty('lg_type', 'folder')
            else:
                li.setProperty('lg_type', 'list')
        
        # Set viewing context for list operations
        if 'in_list' in item.context_tags and item.extras.get('_viewing_list_id'):
            li.setProperty('viewing_list_id', str(item.extras.get('_viewing_list_id')))
        
        # Set search score for search results
        if item.sort_keys.get('search_score'):
            li.setProperty('search_score', str(item.sort_keys.get('search_score')))
        
        # Set playable property for non-folder items
        if not item.is_folder:
            li.setProperty('IsPlayable', 'true')
        
    except Exception as e:
        utils.log(f"Error setting properties: {str(e)}", "DEBUG")


def _set_sort_properties(li: xbmcgui.ListItem, item: MediaItem) -> None:
    """Set sort-related properties"""
    try:
        # Set sort key for search results
        if item.sort_keys.get('search_score'):
            # Invert score for proper sorting (higher scores first)
            inverted_score = 1000 - item.sort_keys.get('search_score', 0)
            li.setProperty('sort_score', f"{inverted_score:06.1f}")
        
        # Set year for sorting
        if item.year:
            li.setProperty('sort_year', f"{item.year:04d}")
        
        # Set title for sorting (remove special characters)
        clean_title = _clean_title_for_sort(item.title)
        li.setProperty('sort_title', clean_title)
        
    except Exception as e:
        utils.log(f"Error setting sort properties: {str(e)}", "DEBUG")


def _clean_title_for_sort(title: str) -> str:
    """Clean title for sorting purposes"""
    if not title:
        return ""
    
    import re
    
    # Remove common articles and special characters
    clean = title.lower()
    clean = re.sub(r'^(the|a|an)\s+', '', clean)
    clean = re.sub(r'[^\w\s]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    return clean
