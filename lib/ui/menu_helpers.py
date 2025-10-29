#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Menu Helpers
Consolidated context menu builders for folders and lists
"""

from typing import List, Tuple, Optional, Any


def get_tools_visibility_toggle_entry(context) -> Tuple[str, str]:
    """
    Get the Tools & Options visibility toggle context menu entry
    
    Args:
        context: PluginContext instance
        
    Returns:
        Tuple of (label, RunPlugin URL)
    """
    from lib.config.config_manager import get_config
    config = get_config()
    is_visible = config.get_bool('show_tools_menu_item', True)
    
    label = "Hide Tools & Options Menu Item" if is_visible else "Show Tools & Options Menu Item"
    url = context.build_url('toggle_tools_menu_item')
    
    return (label, f"RunPlugin({url})")


def build_folder_context_menu(context, folder_id: Any, folder_name: str) -> List[Tuple[str, str]]:
    """
    Build context menu for a folder
    
    Args:
        context: PluginContext instance
        folder_id: ID of the folder
        folder_name: Name of the folder
        
    Returns:
        List of context menu items as (label, action) tuples
    """
    from lib.config.config_manager import get_config
    config = get_config()
    current_startup_folder = config.get('startup_folder_id', None)
    
    menu = [
        ("Create Intersection List...", f"RunPlugin({context.build_url('create_intersection_list', folder_id=folder_id)})"),
        (f"Rename '{folder_name}'", f"RunPlugin({context.build_url('rename_folder', folder_id=folder_id)})"),
        (f"Move '{folder_name}'", f"RunPlugin({context.build_url('move_folder', folder_id=folder_id)})"),
        (f"Delete '{folder_name}'", f"RunPlugin({context.build_url('delete_folder', folder_id=folder_id)})"),
    ]
    
    # Add startup folder option
    if str(folder_id) == str(current_startup_folder):
        menu.append((f"Clear Startup Folder", f"RunPlugin({context.build_url('clear_startup_folder')})"))
    else:
        menu.append((f"Set as Startup Folder", f"RunPlugin({context.build_url('set_startup_folder', folder_id=folder_id)})"))
    
    menu.append(get_tools_visibility_toggle_entry(context))
    
    return menu


def build_list_context_menu(context, list_id: Any, list_name: str) -> List[Tuple[str, str]]:
    """
    Build context menu for a regular user list
    
    Args:
        context: PluginContext instance
        list_id: ID of the list
        list_name: Name of the list
        
    Returns:
        List of context menu items as (label, action) tuples
    """
    return [
        (f"Edit List Items...", f"RunPlugin({context.build_url('edit_list_items', list_id=list_id)})"),
        (f"Rename '{list_name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
        (f"Move '{list_name}' to Folder", f"RunPlugin({context.build_url('move_list_to_folder', list_id=list_id)})"),
        (f"Export '{list_name}'", f"RunPlugin({context.build_url('export_list', list_id=list_id)})"),
        (f"Delete '{list_name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})"),
        get_tools_visibility_toggle_entry(context)
    ]


def build_intersection_list_context_menu(context, list_id: Any, list_name: str) -> List[Tuple[str, str]]:
    """
    Build context menu for an intersection list
    
    Args:
        context: PluginContext instance
        list_id: ID of the intersection list
        list_name: Name of the intersection list
        
    Returns:
        List of context menu items as (label, action) tuples
    """
    return [
        (f"Edit Intersection Sources...", f"RunPlugin({context.build_url('edit_intersection_sources', list_id=list_id)})"),
        (f"View Source Lists", f"RunPlugin({context.build_url('view_intersection_sources', list_id=list_id)})"),
        (f"Convert to Regular List", f"RunPlugin({context.build_url('convert_intersection_to_regular', list_id=list_id)})"),
        (f"Rename '{list_name}'", f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"),
        (f"Move '{list_name}' to Folder", f"RunPlugin({context.build_url('move_list_to_folder', list_id=list_id)})"),
        (f"Export '{list_name}'", f"RunPlugin({context.build_url('export_list', list_id=list_id)})"),
        (f"Delete '{list_name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})"),
        get_tools_visibility_toggle_entry(context)
    ]


def build_kodi_favorites_context_menu(context, list_id: Any, list_name: str) -> List[Tuple[str, str]]:
    """
    Build context menu for Kodi Favorites list (limited operations)
    
    Args:
        context: PluginContext instance
        list_id: ID of the Kodi Favorites list
        list_name: Name of the list (should be "Kodi Favorites")
        
    Returns:
        List of context menu items as (label, action) tuples
    """
    return [
        (f"Tools & Options for '{list_name}'", f"RunPlugin({context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})"),
        get_tools_visibility_toggle_entry(context)
    ]


def build_search_history_list_context_menu(context, list_id: Any, list_name: str) -> List[Tuple[str, str]]:
    """
    Build context menu for search history list (delete only)
    
    Args:
        context: PluginContext instance
        list_id: ID of the search history list
        list_name: Name of the search
        
    Returns:
        List of context menu items as (label, action) tuples
    """
    return [
        (f"Delete '{list_name}'", f"RunPlugin({context.build_url('delete_list', list_id=list_id)})"),
        get_tools_visibility_toggle_entry(context)
    ]
