#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Tools Provider
Provides tools for Kodi Favorites context
"""

from typing import List, Any
from ..types import ToolAction, ToolsContext
from .base_provider import BaseToolsProvider
from lib.ui.localization import L
from lib.ui.response_types import DialogResponse


class FavoritesToolsProvider(BaseToolsProvider):
    """Provider for favorites tools"""
    
    def __init__(self):
        super().__init__()
    
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build favorites tools menu"""
        return [
            self._create_action(
                action_id="scan_favorites",
                label=L(96001),  # "Scan Favorites"
                handler=self._handle_scan_favorites
            ),
            self._create_action(
                action_id="save_as_list", 
                label=L(96002),  # "Save As New List"
                handler=self._handle_save_as_list
            )
        ]
    
    def _handle_scan_favorites(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle scanning favorites"""
        from lib.ui.favorites_handler import FavoritesHandler
        
        def scan_operation():
            favorites_handler = FavoritesHandler()
            return favorites_handler.scan_favorites(plugin_context)
            
        return self._handle_with_error_logging("scan_favorites", scan_operation)
    
    def _handle_save_as_list(self, plugin_context: Any, payload: dict) -> DialogResponse:
        """Handle saving favorites as new list"""
        from lib.ui.favorites_handler import FavoritesHandler
        
        def save_operation():
            favorites_handler = FavoritesHandler()
            return favorites_handler.save_favorites_as(plugin_context)
            
        return self._handle_with_error_logging("save_as_list", save_operation)