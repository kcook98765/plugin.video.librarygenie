#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Menu Builder
Builds Kodi directory listings and menus using the comprehensive ListItemRenderer
"""

from urllib.parse import urlencode
from typing import List, Dict, Any, Optional, Callable

import xbmcgui
import xbmcplugin

from ..utils.logger import get_logger
from .listitem_renderer import get_listitem_renderer


class MenuBuilder:
    """Builds menus and directory listings for Kodi using the comprehensive renderer"""

    def __init__(self, addon_id: str = None, base_url: str = None):
        self.logger = get_logger(__name__)
        self.addon_id = addon_id or 'plugin.video.librarygenie'
        self.base_url = base_url or f'plugin://{self.addon_id}'
        self.renderer = get_listitem_renderer()

    def build_menu(self, items: List[Dict[str, Any]], addon_handle: int):
        """Build a directory menu from items using the comprehensive renderer"""
        self.logger.debug(f"Building menu with {len(items)} items")

        try:
            # Use renderer's directory building capability
            processed_items = []

            for item in items:
                # Transform menu item format to renderer format if needed
                processed_item = self._transform_menu_item(item)
                processed_items.append(processed_item)

            # Use the renderer's comprehensive media items rendering
            success = self.renderer.render_media_items(addon_handle, processed_items, "files")

            if not success:
                self.logger.warning("Menu building failed, using fallback")
                self._build_fallback_menu(items, addon_handle)

        except Exception as e:
            self.logger.error(f"Error building menu: {e}")
            self._build_fallback_menu(items, addon_handle)

    def _transform_menu_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a menu item to renderer format"""
        # If already in proper format, return as-is
        if 'title' in item and ('kodi_id' in item or 'file' in item or 'play' in item):
            return item

        # Transform from menu format to media item format
        transformed = {
            'title': item.get('title', 'Unknown'),
            'plot': item.get('description', ''),
            'id': item.get('id'),
        }

        # If it has an action but no playback info, it's a directory
        if item.get('action') and not any(k in item for k in ['kodi_id', 'file', 'play']):
            # Make it browsable by adding a plugin URL
            action = item.get('action', '')
            params = {k: v for k, v in item.items() if k not in ['title', 'description', 'action', 'is_folder', 'context_menu']}
            params['action'] = action
            transformed['play'] = f"{self.base_url}?{urlencode(params)}"
            transformed['is_folder'] = item.get('is_folder', True)

        return transformed

    def _build_fallback_menu(self, items: List[Dict[str, Any]], addon_handle: int):
        """Fallback menu building using basic directory items"""
        try:
            xbmcplugin.setContent(addon_handle, "files")

            for item in items:
                title = item.get("title", "Unknown")
                action = item.get("action", "")
                description = item.get("description", "")
                is_folder = item.get("is_folder", True)

                # Build URL with parameters
                params = {"action": action}
                for key, value in item.items():
                    if key not in ["title", "description", "action", "is_folder", "context_menu"]:
                        params[key] = value

                url = f"{self.base_url}?{urlencode(params)}" if action else ""

                # Create basic listitem
                list_item = xbmcgui.ListItem(label=title)
                list_item.setInfo('video', {'title': title, 'plot': description})
                list_item.setArt({'icon': 'DefaultFolder.png'})
                list_item.setProperty('IsPlayable', 'false' if is_folder else 'true')

                xbmcplugin.addDirectoryItem(addon_handle, url, list_item, is_folder)

            xbmcplugin.endOfDirectory(addon_handle)

        except Exception as e:
            self.logger.error(f"Fallback menu building failed: {e}")
            xbmcplugin.endOfDirectory(addon_handle, succeeded=False)