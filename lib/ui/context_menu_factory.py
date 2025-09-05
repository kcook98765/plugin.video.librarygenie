#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Context Menu Factory
Centralized context menu generation for all list items and favorites
"""

from typing import List, Tuple, Dict, Any, Optional
from .plugin_context import PluginContext
from ..utils.logger import get_logger


class ContextMenuFactory:
    """Factory for creating context menus for different item types"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def _shorten_menu_text(self, text: str, max_length: int = 30) -> str:
        """Shorten text for context menu display"""
        if len(text) <= max_length:
            return text

        # For search history items, extract just the search terms
        if text.startswith("Search: '") and "' (" in text:
            search_part = text.split("' (")[0].replace("Search: '", "")
            if len(search_part) <= max_length - 3:
                return f"'{search_part}'"
            else:
                return f"'{search_part[:max_length-6]}...'"

        # For regular text, just truncate
        return f"{text[:max_length-3]}..."

    def create_list_item_context_menu(self, item: Dict[str, Any], context: PluginContext,
                                    list_id: Optional[str] = None) -> List[Tuple[str, str]]:
        """Create context menu for regular list items"""
        context_menu = []

        try:
            # Add to List option
            media_item_id = item.get('media_item_id') or item.get('id')
            item_title = item.get('title', '')
            if media_item_id:
                context_menu.append((
                    self._shorten_menu_text(f"Add to List: {item_title}"),
                    f"RunPlugin({context.build_url('add_to_list', media_item_id=media_item_id)})"
                ))

            # Remove from List option (if list_id provided)
            if list_id and media_item_id:
                context_menu.append((
                    self._shorten_menu_text(f"Remove from List: {item_title}"),
                    f"RunPlugin({context.build_url('remove_from_list', list_id=list_id, item_id=media_item_id)})"
                ))

            # Quick Add to Default List option
            if media_item_id:
                context_menu.append((
                    self._shorten_menu_text(f"Quick Add to Default: {item_title}"),
                    f"RunPlugin({context.build_url('quick_add', media_item_id=media_item_id)})"
                ))

        except Exception as e:
            self.logger.warning(f"Failed to create list item context menu: {e}")

        return context_menu

    def create_favorites_context_menu(self, item: Dict[str, Any], context: PluginContext) -> List[Tuple[str, str]]:
        """Create context menu for favorites items"""
        context_menu = []

        try:
            # Remove from Favorites option
            item_id = item.get('id') or item.get('media_item_id') or item.get('kodi_id', '')
            item_title = item.get('title', '')
            if item_id:
                context_menu.append((
                    self._shorten_menu_text(f"Remove from Favorites: {item_title}"),
                    f"RunPlugin({context.build_url('remove_from_favorites', item_id=item_id)})"
                ))

            # Add to List option (for mapped favorites)
            if item.get('imdb_id') or item.get('media_item_id'):
                media_item_id = item.get('media_item_id') or item.get('id')
                context_menu.append((
                    self._shorten_menu_text(f"Add to List: {item_title}"),
                    f"RunPlugin({context.build_url('add_to_list_menu', media_item_id=media_item_id)})"
                ))

        except Exception as e:
            self.logger.warning(f"Failed to create favorites context menu: {e}")

        return context_menu

    def create_search_result_context_menu(self, item: Dict[str, Any], context: PluginContext) -> List[Tuple[str, str]]:
        """Create context menu for search result items"""
        context_menu = []

        try:
            # Add to List option
            media_item_id = item.get('media_item_id') or item.get('id')
            item_title = item.get('title', '')
            if media_item_id:
                context_menu.append((
                    self._shorten_menu_text(f"Add to List: {item_title}"),
                    f"RunPlugin({context.build_url('add_to_list', media_item_id=media_item_id)})"
                ))

            # Quick Add to Default List option
            if media_item_id:
                context_menu.append((
                    self._shorten_menu_text(f"Quick Add to Default: {item_title}"),
                    f"RunPlugin({context.build_url('quick_add', media_item_id=media_item_id)})"
                ))

        except Exception as e:
            self.logger.warning(f"Failed to create search result context menu: {e}")

        return context_menu

    def create_folder_context_menu(self, folder: Dict[str, Any], context: PluginContext) -> List[Tuple[str, str]]:
        """Create context menu for folder items"""
        context_menu = []

        try:
            folder_id = folder.get('id')
            folder_name = folder.get('name', '')
            if folder_id:
                # Rename Folder option
                context_menu.append((
                    self._shorten_menu_text(f"Rename Folder: {folder_name}"),
                    f"RunPlugin({context.build_url('rename_folder', folder_id=folder_id)})"
                ))

                # Delete Folder option
                context_menu.append((
                    self._shorten_menu_text(f"Delete Folder: {folder_name}"),
                    f"RunPlugin({context.build_url('delete_folder', folder_id=folder_id)})"
                ))

        except Exception as e:
            self.logger.warning(f"Failed to create folder context menu: {e}")

        return context_menu

    def create_list_context_menu(self, list_item: Dict[str, Any], context: PluginContext) -> List[Tuple[str, str]]:
        """Create context menu for list items in lists view"""
        context_menu = []

        try:
            list_id = list_item.get('id')
            list_name = list_item.get('name', '')
            if list_id:
                # Rename List option
                context_menu.append((
                    self._shorten_menu_text(f"Rename List: {list_name}"),
                    f"RunPlugin({context.build_url('rename_list', list_id=list_id)})"
                ))

                # Delete List option
                context_menu.append((
                    self._shorten_menu_text(f"Delete List: {list_name}"),
                    f"RunPlugin({context.build_url('delete_list', list_id=list_id)})"
                ))

        except Exception as e:
            self.logger.warning(f"Failed to create list context menu: {e}")

        return context_menu

    def create_tools_context_menu(self, item_type: str, item_id: str, context: PluginContext) -> List[Tuple[str, str]]:
        """Create context menu for tools and options"""
        context_menu = []

        try:
            # Tools & Options entry
            context_menu.append((
                "Tools & Options",
                f"RunPlugin({context.build_url('show_list_tools', list_type=item_type, list_id=item_id)})"
            ))

        except Exception as e:
            self.logger.warning(f"Failed to create tools context menu: {e}")

        return context_menu


# Global factory instance
_context_menu_factory_instance = None


def get_context_menu_factory() -> ContextMenuFactory:
    """Get global context menu factory instance"""
    global _context_menu_factory_instance
    if _context_menu_factory_instance is None:
        _context_menu_factory_instance = ContextMenuFactory()
    return _context_menu_factory_instance