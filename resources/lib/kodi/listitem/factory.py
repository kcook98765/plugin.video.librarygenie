
"""
ListItem Factory for LibraryGenie
Single entry point for creating Kodi ListItems from MediaItem objects
"""
import xbmcgui
from typing import Optional, Union
from ...data.models import MediaItem
from ..adapters.infotag_adapter import apply_infotag
from ..adapters.art_mapper import apply_art
from ...utils import utils


def build_listitem(item: MediaItem, view_hint: Optional[Union[str, object]] = None) -> xbmcgui.ListItem:
    """
    Build a complete Kodi ListItem from a MediaItem
    
    Args:
        item: MediaItem with all normalized data
        view_hint: Optional hint about the view context (for future use)
    
    Returns:
        Fully configured xbmcgui.ListItem
    """
    try:
        # Create base ListItem
        li = xbmcgui.ListItem()
        
        # Set basic properties
        if item.title:
            li.setLabel(item.title)
        
        # Set label2 (could be year, duration, etc. based on view_hint)
        label2 = _get_label2(item, view_hint)
        if label2:
            li.setLabel2(label2)
        
        # Set folder/playable state
        li.setIsFolder(item.is_folder)
        if not item.is_folder and item.play_path:
            li.setProperty('IsPlayable', 'true')
        
        # Apply InfoTag data
        apply_infotag(item, li)
        
        # Apply art mapping
        apply_art(item, li)
        
        # Set additional properties
        _set_additional_properties(item, li, view_hint)
        
        # Attach context menu from registry
        from ..menu.registry import for_item
        context_menu = for_item(item, view_hint)
        if context_menu:
            # Handle Kodi version differences for context menus
            if utils.get_kodi_version() >= 19:
                li.addContextMenuItems(context_menu, replaceItems=True)
            else:
                li.addContextMenuItems(context_menu, replaceItems=False)
        
        utils.log(f"Built ListItem for '{item.title}' (type: {item.media_type})", "DEBUG")
        return li
        
    except Exception as e:
        utils.log(f"Failed to build ListItem for '{item.title}': {str(e)}", "ERROR")
        # Return minimal ListItem as fallback
        fallback_li = xbmcgui.ListItem(item.title or "Unknown")
        fallback_li.setIsFolder(item.is_folder)
        return fallback_li


def _get_label2(item: MediaItem, view_hint: Optional[Union[str, object]]) -> str:
    """Generate label2 based on item data and view context"""
    if item.year:
        return str(item.year)
    elif item.runtime and item.runtime > 0:
        # Convert seconds to readable format
        hours = item.runtime // 3600
        minutes = (item.runtime % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    return ""


def _set_additional_properties(item: MediaItem, li: xbmcgui.ListItem, view_hint: Optional[Union[str, object]]) -> None:
    """Set additional properties on the ListItem"""
    try:
        # Set sort keys if available
        if hasattr(item, 'sort_keys') and item.sort_keys:
            for key, value in item.sort_keys.items():
                if value is not None:
                    li.setProperty(f"sort_{key}", str(value))
        
        # Set any extra properties
        if hasattr(item, 'extras') and item.extras:
            for key, value in item.extras.items():
                if value is not None:
                    li.setProperty(key, str(value))
        
        # Set context tags as properties (for future filtering/menu logic)
        if hasattr(item, 'context_tags') and item.context_tags:
            li.setProperty('context_tags', ','.join(item.context_tags))
            
    except Exception as e:
        utils.log(f"Failed to set additional properties: {str(e)}", "WARNING")
