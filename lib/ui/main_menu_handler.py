

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Menu Handler
Handles the main menu display and navigation
"""

from typing import Optional
from .menu_builder import MenuBuilder
from .plugin_context import PluginContext
from ..utils.logger import get_logger
from ..utils.kodi_version import get_kodi_major_version
import xbmcplugin
import xbmcaddon


class MainMenuHandler:
    """Handles main menu display"""

    def __init__(self):
        pass

    def show_main_menu(self, context: PluginContext) -> bool:
        """Show main menu with top-level navigation items"""
        try:
            kodi_major = get_kodi_major_version()
            context.logger.info(f"MAIN MENU: Starting main menu display on Kodi v{kodi_major}")

            query_manager = context.query_manager
            if not query_manager:
                context.logger.error("Query manager not available")
                return False

            # Build root-level menu items
            context.logger.info("Building root-level main menu")
            menu_items = []

            # 1. Search
            menu_items.append({
                'label': f"🔍 Search",
                'action': 'prompt_and_search',
                'is_folder': True,
                'icon': 'DefaultAddonsSearch.png',
                'description': 'Search your library'
            })

            # 2. AI Search (conditional - only when activated)
            from ..remote.ai_search_client import get_ai_search_client
            ai_client = get_ai_search_client()
            if ai_client.is_activated():
                context.logger.info("AI Search is activated - adding to main menu")
                menu_items.append({
                    'label': f"🤖 AI Search",
                    'action': 'ai_search_prompt',
                    'is_folder': True,
                    'icon': 'DefaultAddonsSearch.png',
                    'description': 'AI-powered search'
                })
            else:
                context.logger.info("AI Search is not activated - not showing in main menu")

            # 3. Search History (always show - service.py handles folder creation)
            context.logger.info("Adding search history menu item")
            menu_items.append({
                'label': f"📊 Search History",
                'action': 'show_search_history',
                'is_folder': True,
                'icon': 'DefaultRecentlyAdded.png',
                'description': 'Recent searches'
            })

            # 4. Lists
            all_lists = query_manager.get_all_lists_with_folders()
            user_lists = [item for item in all_lists if item.get('name') != 'Kodi Favorites']
            context.logger.info(f"Found {len(user_lists)} user lists")
            
            menu_items.append({
                'label': f"📋 Lists",
                'action': 'show_lists_menu',
                'is_folder': True,
                'icon': 'DefaultPlaylist.png',
                'description': f'Manage your lists ({len(user_lists)} lists)'
            })

            # 5. Kodi Favorites (conditional - check if favorites integration is enabled)
            addon = xbmcaddon.Addon()
            favorites_enabled = addon.getSettingBool('favorites_integration_enabled')
            
            if favorites_enabled:
                context.logger.info("Kodi Favorites integration is enabled - adding to main menu")
                
                # Check if there are any favorites
                favorites_manager = context.favorites_manager
                if favorites_manager:
                    favorites = favorites_manager.get_mapped_favorites(show_unmapped=True)
                    favorites_count = len(favorites)
                    
                    menu_items.append({
                        'label': f"⭐ Kodi Favorites",
                        'action': 'kodi_favorites',
                        'is_folder': True,
                        'icon': 'DefaultShortcut.png',
                        'description': f'Your Kodi favorites ({favorites_count} items)'
                    })
                    context.logger.info(f"Added Kodi Favorites to main menu ({favorites_count} items)")
                else:
                    context.logger.warning("Favorites manager not available")
            else:
                context.logger.info("Kodi Favorites integration is disabled - not showing in main menu")

            # Use MenuBuilder to create the menu
            context.logger.info("MAIN MENU: Building menu with MenuBuilder")
            menu_builder = MenuBuilder()
            menu_builder.build_menu(
                menu_items, 
                context.addon_handle, 
                context.base_url, 
                breadcrumb_path=context.breadcrumb_path
            )

            context.logger.info("MAIN MENU: Successfully completed main menu display")
            return True

        except Exception as e:
            context.logger.error(f"MAIN MENU: Error showing main menu: {e}")
            import traceback
            context.logger.error(f"MAIN MENU: Traceback: {traceback.format_exc()}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

