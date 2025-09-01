#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Menu Handler
Handles the main menu display and navigation
"""

import xbmcplugin
import xbmcgui
from .plugin_context import PluginContext
from .response_types import DirectoryResponse
from ..auth.state import is_authorized


class MainMenuHandler:
    """Handles main menu display"""
    
    def __init__(self):
        pass
        
    def show_main_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main menu with auth-aware options"""
        menu_items = []
        
        # Search (always visible)
        menu_items.append({
            'label': context.addon.getLocalizedString(35014),  # "Search"
            'url': context.build_url('search'),
            'is_folder': True
        })

        # Lists (always visible)
        menu_items.append({
            'label': context.addon.getLocalizedString(35016),  # "Lists"
            'url': context.build_url('lists'),
            'is_folder': True
        })

        # Kodi Favorites (always visible)
        menu_items.append({
            'label': "Kodi Favorites",
            'url': context.build_url('kodi_favorites'),
            'is_folder': True
        })

        # Auth-dependent menu items
        if context.is_authorized:
            # Sign out (visible only when authorized)
            menu_items.append({
                'label': context.addon.getLocalizedString(35027),  # "Sign out"
                'url': context.build_url('signout'),
                'is_folder': False
            })

            # Remote features (when authorized)
            menu_items.append({
                'label': context.addon.getLocalizedString(35017),  # "Remote Lists"
                'url': context.build_url('remote_lists'),
                'is_folder': True
            })
        else:
            # Authorize device (visible only when not authorized)
            menu_items.append({
                'label': context.addon.getLocalizedString(35028),  # "Authorize device"
                'url': context.build_url('authorize'),
                'is_folder': False
            })

        # Build directory items
        for item in menu_items:
            list_item = xbmcgui.ListItem(label=item['label'])
            xbmcplugin.addDirectoryItem(
                context.addon_handle, 
                item['url'], 
                list_item, 
                item['is_folder']
            )

        # End directory
        xbmcplugin.endOfDirectory(
            context.addon_handle, 
            succeeded=True, 
            updateListing=False, 
            cacheToDisc=True
        )

        return DirectoryResponse(
            items=menu_items,
            success=True,
            cache_to_disc=True,
            content_type="files"
        )