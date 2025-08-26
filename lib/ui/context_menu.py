#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Context Menu System
Handles context menus for library and list operations
"""

import xbmcgui
from typing import Dict, Any, Optional, Callable, List

from ..utils.logger import get_logger


class ContextMenuManager:
    """Manages context menus for addon operations"""

    def __init__(self, string_getter):
        self.logger = get_logger(__name__)
        self._get_string = string_getter

    def add_library_item_context_menu(self, list_item, library_movie_id):
        """Add context menu for library items"""
        try:
            context_menu = [
                (
                    self._get_string(31000),  # "Add to List..."
                    f"RunPlugin(plugin://plugin.video.library.genie?action=add_to_list&library_movie_id={library_movie_id})"
                ),
                (
                    self._get_string(31001),  # "Quick Add to Default"
                    f"RunPlugin(plugin://plugin.video.library.genie?action=quick_add&library_movie_id={library_movie_id})"
                )
            ]

            list_item.addContextMenuItems(context_menu)
            return list_item

        except Exception as e:
            self.logger.warning(f"Failed to add library context menu: {e}")
            return list_item

    def add_list_item_context_menu(self, list_item, list_id, list_item_id):
        """Add context menu for list items"""
        try:
            context_menu = [
                (
                    self._get_string(31010),  # "Remove from List"
                    f"RunPlugin(plugin://plugin.video.library.genie?action=remove_from_list&list_id={list_id}&list_item_id={list_item_id})"
                ),
                (
                    self._get_string(31011),  # "Move to Another List..."
                    f"RunPlugin(plugin://plugin.video.library.genie?action=move_to_list&list_id={list_id}&list_item_id={list_item_id})"
                )
            ]

            list_item.addContextMenuItems(context_menu)
            return list_item

        except Exception as e:
            self.logger.warning(f"Failed to add list item context menu: {e}")
            return list_item


# Global context menu manager instance
_context_menu_instance = None


def get_context_menu_manager(string_getter):
    """Get global context menu manager instance"""
    global _context_menu_instance
    if _context_menu_instance is None:
        _context_menu_instance = ContextMenuManager(string_getter)
    return _context_menu_instance