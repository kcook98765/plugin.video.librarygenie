#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Breadcrumb Helper
Generates breadcrumb navigation paths for UI context
"""

from typing import Optional
from ..utils.logger import get_logger


class BreadcrumbHelper:
    """Helper class for generating breadcrumb navigation paths"""

    def __init__(self):
        self.logger = get_logger(__name__)


    def get_breadcrumb_for_action(self, action: str, context_params: dict, query_manager=None) -> Optional[str]:
        """Generate breadcrumb path based on current action and context"""
        try:
            if action == "show_list":
                return self._get_list_breadcrumb(context_params, query_manager)
            elif action == "show_folder":
                return self._get_folder_breadcrumb(context_params, query_manager)
            elif action == "favorites" or action == "kodi_favorites":
                return "Kodi Favorites"
            elif action == "search_results":
                query = context_params.get('query', '')
                return f"Search: \"{query}\""
            elif action == "search_history":
                return "Search History"
            elif action == "lists":
                return "Lists"
            elif action == "library_browse":
                return "Browse Movies"
            elif action == "show_list_tools":
                return self._get_tools_breadcrumb(context_params, query_manager)
            elif action == "show_favorites_tools":
                return "Favorites Tools"
            else:
                # Return None for main menu and unrecognized actions
                return None

        except Exception as e:
            self.logger.error(f"Error generating breadcrumb for action '{action}': {e}")
            return None

    def _get_list_breadcrumb(self, params: dict, query_manager) -> Optional[str]:
        """Generate breadcrumb for list view"""
        list_id = params.get('list_id')
        if not list_id or not query_manager:
            return "Lists > Unknown List"

        try:
            list_info = query_manager.get_list_info(list_id)
            if not list_info:
                return "Lists > Unknown List"

            list_name = list_info.get('name', 'Unknown List')
            folder_id = list_info.get('folder_id')

            if folder_id:
                folder_info = query_manager.get_folder_info(folder_id)
                if folder_info:
                    folder_name = folder_info.get('name', 'Unknown Folder')

                    # Special handling for search history lists
                    if folder_name == "Search History":
                        # Extract just the search terms from the list name
                        if list_name.startswith("Search: '") and "'" in list_name[9:]:
                            search_terms = list_name[9:].split("'")[0]
                            return f"Search History > {search_terms}"
                        else:
                            return f"Search History > {list_name}"

                    return f"{folder_name} > {list_name}"

            return list_name

        except Exception as e:
            self.logger.error(f"Error getting list breadcrumb: {e}")
            return "Lists > Unknown List"

    def _get_folder_breadcrumb(self, params: dict, query_manager) -> Optional[str]:
        """Generate breadcrumb for folder view"""
        folder_id = params.get('folder_id')
        if not folder_id or not query_manager:
            return "Lists > Unknown Folder"

        try:
            folder_info = query_manager.get_folder_info(folder_id)
            if not folder_info:
                return "Lists > Unknown Folder"

            folder_name = folder_info.get('name', 'Unknown Folder')
            parent_id = folder_info.get('parent_id')

            if parent_id:
                parent_info = query_manager.get_folder_info(parent_id)
                if parent_info:
                    parent_name = parent_info.get('name', 'Unknown Folder')
                    return f"Lists > {parent_name} > {folder_name}"

            return f"Lists > {folder_name}"

        except Exception as e:
            self.logger.error(f"Error getting folder breadcrumb: {e}")
            return "Lists > Unknown Folder"

    def _get_tools_breadcrumb(self, params: dict, query_manager) -> Optional[str]:
        """Generate breadcrumb for tools view"""
        list_type = params.get('list_type', 'unknown')
        list_id = params.get('list_id')

        if list_type == 'favorites':
            return "Favorites Tools"
        elif list_type == 'lists_main':
            return "Lists Tools"
        elif list_type == 'user_list' and list_id and query_manager:
            try:
                list_info = query_manager.get_list_info(list_id)
                if list_info:
                    list_name = list_info.get('name', 'Unknown List')
                    return f"{list_name} Tools"
            except Exception:
                pass
            return "List Tools"
        elif list_type == 'folder' and list_id and query_manager:
            try:
                folder_info = query_manager.get_folder_info(list_id)
                if folder_info:
                    folder_name = folder_info.get('name', 'Unknown Folder')
                    return f"{folder_name} Tools"
            except Exception:
                pass
            return "Folder Tools"
        else:
            return "Tools"

    


# Global instance
_breadcrumb_helper = None


def get_breadcrumb_helper():
    """Get global breadcrumb helper instance"""
    global _breadcrumb_helper
    if _breadcrumb_helper is None:
        _breadcrumb_helper = BreadcrumbHelper()
    return _breadcrumb_helper