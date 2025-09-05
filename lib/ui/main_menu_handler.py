#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Menu Handler
Handles the main menu display and navigation
"""

from .plugin_context import PluginContext
from .response_types import DirectoryResponse
from .localization import L


class MainMenuHandler:
    """Handles main menu display"""

    def __init__(self):
        pass

    def show_main_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main menu with auth-aware options"""
        menu_items = []

        # 1. Lists (always visible)
        menu_items.append({
            'label': context.addon.getLocalizedString(35016),  # "Lists"
            'url': context.build_url('lists'),
            'is_folder': True
        })

        # 2. Search (always visible)
        menu_items.append({
            'label': context.addon.getLocalizedString(35014),  # "Search"
            'url': context.build_url('search'),
            'is_folder': True
        })

        # 3. Search History (if exists)
        try:
            from ..data.query_manager import get_query_manager
            query_manager = get_query_manager()
            if query_manager.initialize():
                search_folder_id = query_manager.get_or_create_search_history_folder()
                search_lists = query_manager.get_lists_in_folder(search_folder_id)
                if search_lists:
                    menu_items.append({
                        'label': L(32900),  # "Search History"
                        'url': context.build_url('show_folder', folder_id=search_folder_id),
                        'is_folder': True,
                        'icon': "DefaultAddonProgram.png",
                        'description': L(32901) % len(search_lists)  # "Browse %d saved searches"
                    })
        except Exception as e:
            context.logger.debug(f"Could not check search history: {e}")

        # 4. Kodi Favorites (if visibility is enabled in settings)
        if context.addon.getSettingBool("favorites_integration_enabled"):
            menu_items.append({
                'label': context.addon.getLocalizedString(32000),  # "Kodi Favorites (read-only)"
                'url': context.build_url('kodi_favorites'),
                'is_folder': True,
                'icon': "DefaultFavourites.png",
                'description': context.addon.getLocalizedString(32001)  # "Browse Kodi Favorites"
            })

        # Remote features (when authorized) - keeping this for functionality
        if context.is_authorized:
            menu_items.append({
                'label': context.addon.getLocalizedString(35017),  # "Remote Lists"
                'url': context.build_url('remote_lists'),
                'is_folder': True
            })

        # Use MenuBuilder (no breadcrumb for main menu)
        from .menu_builder import MenuBuilder
        menu_builder = MenuBuilder()
        menu_builder.build_menu(
            menu_items,
            context.addon_handle,
            context.base_url,
            breadcrumb_path=None  # No breadcrumb for root menu
        )

        return DirectoryResponse(
            items=menu_items,
            success=True,
            cache_to_disc=True,
            content_type="files"
        )