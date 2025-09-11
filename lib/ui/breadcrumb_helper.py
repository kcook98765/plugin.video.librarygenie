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
            self.logger.error("Error generating breadcrumb for action '%s': %s", action, e)
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

                    # Build full folder hierarchy for regular folders
                    folder_path = self._build_folder_hierarchy(folder_id, query_manager)
                    self.logger.debug("List breadcrumb: folder_path='%s', list_name='%s'", folder_path, list_name)
                    return f"Lists > {folder_path} > {list_name}"

            # If no folder_id, this is a standalone list - still show under Lists
            return f"Lists > {list_name}"

        except Exception as e:
            self.logger.error("Error getting list breadcrumb: %s", e)
            return "Lists > Unknown List"

    def _get_folder_breadcrumb(self, params: dict, query_manager) -> Optional[str]:
        """Generate breadcrumb for folder view"""
        folder_id = params.get('folder_id')
        if not folder_id or not query_manager:
            return "Lists > Unknown Folder"

        try:
            # Build the full folder hierarchy path
            folder_path = self._build_folder_hierarchy(folder_id, query_manager)
            self.logger.debug("Built folder hierarchy for %s: '%s'", folder_id, folder_path)
            return f"Lists > {folder_path}"

        except Exception as e:
            self.logger.error("Error getting folder breadcrumb for folder_id %s: %s", folder_id, e)
            return "Lists > Unknown Folder"

    def _build_folder_hierarchy(self, folder_id: str, query_manager) -> str:
        """Recursively build the full folder hierarchy path"""
        try:
            folder_info = query_manager.get_folder_info(folder_id)
            if not folder_info:
                self.logger.error("No folder info found for folder_id: %s", folder_id)
                return "Unknown Folder"
            
            folder_name = folder_info.get('name', 'Unknown Folder')
            parent_id = folder_info.get('parent_id')
            
            self.logger.debug("Building hierarchy for folder '%s' (id=%s, parent_id=%s)", folder_name, folder_id, parent_id)
            
            if parent_id:
                # Recursively get parent path
                parent_path = self._build_folder_hierarchy(parent_id, query_manager)
                result = f"{parent_path} > {folder_name}"
                self.logger.debug("Hierarchy result for %s: '%s'", folder_id, result)
                return result
            else:
                # This is a root-level folder
                self.logger.debug("Root folder found: '%s'", folder_name)
                return folder_name
                
        except Exception as e:
            self.logger.error("Error building folder hierarchy for %s: %s", folder_id, e)
            import traceback
            self.logger.error("Hierarchy error traceback: %s", traceback.format_exc())
            return "Unknown Folder"

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

    def show_breadcrumb_notification(self, title: str):
        """Show breadcrumb as a notification to the user"""
        try:
            if title and title.strip():
                import xbmcgui
                self.logger.debug("BREADCRUMB: Showing notification for '%s'", title)
                xbmcgui.Dialog().notification("Navigation", title, xbmcgui.NOTIFICATION_INFO, 3000)
                self.logger.debug("BREADCRUMB: Successfully displayed breadcrumb notification")
        except Exception as e:
            self.logger.error("BREADCRUMB: Failed to display breadcrumb notification: %s", e)


# Global instance
_breadcrumb_helper = None


def get_breadcrumb_helper():
    """Get global breadcrumb helper instance"""
    global _breadcrumb_helper
    if _breadcrumb_helper is None:
        _breadcrumb_helper = BreadcrumbHelper()
    return _breadcrumb_helper