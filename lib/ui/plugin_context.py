#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Plugin Context
Encapsulates request data and shared resources for handlers
"""

import sys
import time
from urllib.parse import parse_qsl
from typing import Dict, Any, Optional

import xbmcaddon
from lib.utils.kodi_log import get_kodi_logger
from lib.auth.state import is_authorized
from lib.ui.localization import L


class PluginContext:
    """Encapsulates all request context and shared resources"""

    def __init__(self):
        # Parse plugin arguments
        # Handle cases where sys.argv[1] might not be a valid integer (e.g., when called from settings)
        try:
            self.addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        except (ValueError, IndexError):
            # Fallback for non-integer handles (e.g., utilities.py calls)
            self.addon_handle = -1
        self.base_url = sys.argv[0] if len(sys.argv) > 0 else ""
        query_string = sys.argv[2][1:] if len(sys.argv) > 2 and len(sys.argv[2]) > 1 else ""

        # Parse query parameters
        self.params = dict(parse_qsl(query_string))

        # Shared resources
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')
        self.logger = get_kodi_logger('lib.ui.plugin_context')

        # Cache auth state
        self._auth_state = None

        # Service singletons (lazy loaded)
        self._query_manager = None
        self._favorites_manager = None
        self._storage_manager = None

        # Navigation context - generate breadcrumb automatically
        breadcrumb_start = time.time()
        self.breadcrumb_path = self._generate_breadcrumb()
        breadcrumb_time = (time.time() - breadcrumb_start) * 1000
        self.logger.debug("TIMING: Breadcrumb generation took %.2f ms", breadcrumb_time)

        self.logger.debug("PluginContext created: handle=%s, base_url=%s, params=%s", self.addon_handle, self.base_url, self.params)
        if self.breadcrumb_path:
            self.logger.debug("Generated breadcrumb: %s", self.breadcrumb_path)

    @property
    def is_authorized(self) -> bool:
        """Get cached authorization state"""
        if self._auth_state is None:
            self._auth_state = is_authorized()
        return self._auth_state

    @property
    def query_manager(self):
        """Get query manager singleton (lazy loaded)"""
        if self._query_manager is None:
            from lib.data.query_manager import get_query_manager
            self._query_manager = get_query_manager()
            if not self._query_manager.initialize():
                self.logger.error("Failed to initialize query manager")
                return None
        return self._query_manager

    @property
    def favorites_manager(self):
        """Get cached favorites manager instance"""
        if self._favorites_manager is None:
            from lib.kodi.favorites_manager import get_phase4_favorites_manager
            self._favorites_manager = get_phase4_favorites_manager()
        return self._favorites_manager

    @property
    def storage_manager(self):
        """Get cached storage manager instance"""
        if self._storage_manager is None:
            from lib.data.storage_manager import get_storage_manager
            self._storage_manager = get_storage_manager()
        return self._storage_manager

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get parameter value with optional default"""
        return self.params.get(key, default)

    def get_params(self) -> Dict[str, Any]:
        """Get all parameters"""
        return self.params
    
    def is_from_outside_plugin(self) -> bool:
        """Check if request is from outside the plugin (e.g., context menu)"""
        # Check if called from context menu or external source
        # This can be determined by looking at the addon handle or other markers
        external_param = self.params.get('external', False)
        is_external = isinstance(external_param, bool) and external_param
        return self.addon_handle == -1 or is_external
    
    def set_content_type(self, content_type: str = 'files'):
        """Set content type for directory listing"""
        if self.addon_handle >= 0:
            import xbmcplugin
            xbmcplugin.setContent(self.addon_handle, content_type)
    
    def add_item(self, url: str, listitem, isFolder: bool = False):
        """Add item to directory listing"""
        if self.addon_handle >= 0:  # Valid handle
            import xbmcplugin
            xbmcplugin.addDirectoryItem(self.addon_handle, url, listitem, isFolder)

    def require_param(self, key: str) -> Any:
        """Get required parameter, raises ValueError if missing"""
        value = self.params.get(key)
        if value is None:
            raise ValueError(f"Required parameter '{key}' is missing")
        return value

    def build_url(self, action: str, **kwargs) -> str:
        """Build plugin URL with action and parameters"""
        params = [f"action={action}"]
        for key, value in kwargs.items():
            if value is not None:
                params.append(f"{key}={value}")

        query = "&".join(params)
        return f"{self.base_url}?{query}"
    
    def build_cache_busted_url(self, action: str, **kwargs) -> str:
        """Build plugin URL with cache-busting refresh token"""
        from lib.ui.session_state import get_session_state
        session_state = get_session_state()
        
        # Add refresh token for cache busting
        kwargs['rt'] = session_state.get_refresh_token()
        
        return self.build_url(action, **kwargs)
    
    def add_cache_buster_to_url(self, url: str) -> str:
        """Add cache-busting parameter to existing URL"""
        from lib.ui.session_state import get_session_state
        session_state = get_session_state()
        
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}rt={session_state.get_refresh_token()}"

    def _generate_breadcrumb(self) -> Optional[str]:
        """Generate breadcrumb path for current context"""
        try:
            action = self.params.get('action', '')
            if not action:
                self.logger.debug("TIMING: No action parameter, skipping breadcrumb generation")
                return None

            # Import here to avoid circular imports
            import_start = time.time()
            from lib.ui.breadcrumb_helper import get_breadcrumb_helper
            breadcrumb_helper = get_breadcrumb_helper()
            import_time = (time.time() - import_start) * 1000
            self.logger.debug("TIMING: Breadcrumb helper import/instantiation took %.2f ms", import_time)
            
            breadcrumb_exec_start = time.time()
            result = breadcrumb_helper.get_breadcrumb_for_action(action, self.params, self.query_manager)
            breadcrumb_exec_time = (time.time() - breadcrumb_exec_start) * 1000
            self.logger.debug("TIMING: Breadcrumb execution for action '%s' took %.2f ms", action, breadcrumb_exec_time)
            
            return result
        except Exception as e:
            self.logger.error("Error generating breadcrumb: %s", e)
            return None

    def display_folder(self, folder_id: str):
        """Display folder contents with proper breadcrumb"""
        try:
            self.logger.debug("Displaying folder %s", folder_id)

            query_manager = get_query_manager()
            folder_info = query_manager.get_folder_info(folder_id)

            if not folder_info:
                self.logger.error("Folder %s not found", folder_id)
                self._show_error("Folder not found")
                return

            folder_name = folder_info.get('name', 'Unknown Folder')

            # Generate breadcrumb for folder
            from lib.ui.breadcrumb_helper import get_breadcrumb_helper
            breadcrumb_helper = get_breadcrumb_helper()
            breadcrumb_path = breadcrumb_helper.get_breadcrumb_for_action(
                'show_folder', 
                {'folder_id': folder_id}, 
                query_manager
            )
            self.logger.debug("Generated folder breadcrumb: '%s'", breadcrumb_path)

            # Get subfolders
            subfolders = query_manager.get_all_folders(parent_id=folder_id)
            self.logger.debug("Folder '%s' has %s subfolders", folder_name, len(subfolders))

            # Get lists in this folder
            lists_in_folder = query_manager.get_lists_in_folder(folder_id)
            self.logger.debug("Folder '%s' has %s lists", folder_name, len(lists_in_folder))

            # Build menu items
            menu_items = []

            # Add subfolders
            for subfolder in subfolders:
                subfolder_id = subfolder['id']
                subfolder_name = subfolder['name']

                context_menu = [
                    (f"Tools & Options for '{subfolder_name}'", f"RunPlugin({self.build_url('show_tools', list_type='folder', list_id=subfolder_id)})")
                ]

                menu_items.append({
                    'label': subfolder_name,
                    'url': self.build_url('show_folder', folder_id=subfolder_id),
                    'is_folder': True,
                    'description': f"Folder",
                    'context_menu': context_menu
                })

            # Add lists
            for list_item in lists_in_folder:
                list_id = list_item['id']
                name = list_item['name']
                description = list_item.get('description', '')

                context_menu = [
                    (f"Tools & Options for '{name}'", f"RunPlugin({self.build_url('show_tools', list_type='user_list', list_id=list_id)})")
                ]

                menu_items.append({
                    'label': name,
                    'url': self.build_url('show_list', list_id=list_id),
                    'is_folder': True,
                    'description': description,
                    'context_menu': context_menu
                })

            # Add Tools & Options for folder
            menu_items.append({
                'label': f"{L(36000)} for '{folder_name}'",
                'url': self.build_url('show_tools', list_type='folder', list_id=folder_id),
                'is_folder': True,
                'description': "Manage this folder"
            })

            # Use menu builder to display with breadcrumb
            menu_builder = MenuBuilder()
            menu_builder.build_directory_listing(menu_items, self.addon_handle, self.base_url, breadcrumb_path=breadcrumb_path)

        except Exception as e:
            self.logger.error("Error displaying folder %s: %s", folder_id, e)
            self._show_error("Error displaying folder")