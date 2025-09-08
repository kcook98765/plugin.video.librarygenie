#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Hot Routes
Performance-optimized consolidation of the most frequently accessed route handlers
This module minimizes imports and consolidates hot-path operations for low-power devices
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Union
import xbmcplugin
import xbmcgui

# Minimal essential imports only
from .plugin_context import PluginContext
from .response_types import DirectoryResponse
from .localization import L
from ..utils.logger import get_logger
from ..core.use_cases_hot import get_hot_use_cases


class HotRoutes:
    """Consolidated hot route handlers with minimal import overhead"""
    
    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_logger(__name__)
        self.hot_use_cases = get_hot_use_cases()
        
    # --- PRIMARY HOT ROUTES ---
    
    def show_main_menu(self) -> bool:
        """
        Main menu entry point - consolidated from MainMenuHandler + ListsHandler
        Most frequently accessed route - show lists as primary interface
        """
        try:
            self.logger.info("HOT ROUTE: Main menu - redirecting to Lists")
            return self.show_lists_menu()
            
        except Exception as e:
            self.logger.error(f"HOT ROUTE: Main menu error: {e}")
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
            return False
    
    def show_lists_menu(self) -> bool:
        """
        Lists menu display - consolidated from ListsHandler.show_lists_menu
        Hot path for browsing user lists and folders
        """
        try:
            self.logger.info("HOT ROUTE: Displaying lists menu")
            
            # Get lists and folders using hot use cases (with caching)
            browse_data = self.hot_use_cases.list_browse_basic()
            user_lists = browse_data.get('lists', [])
            folders = browse_data.get('folders', [])
            
            if not user_lists and not folders:
                return self._show_empty_lists_state()
            
            # Build menu items with inline logic
            self._add_lists_menu_header()
            
            # Add folders first
            for folder_info in folders:
                if folder_info.get('name') == 'Search History':
                    continue  # Skip search history in main view
                self._add_folder_item(folder_info)
            
            # Add standalone lists
            standalone_lists = [item for item in user_lists 
                              if not item.get('folder_name') or item.get('folder_name') == 'Root']
            
            for list_item in standalone_lists:
                self._add_list_item(list_item)
            
            # End directory
            xbmcplugin.endOfDirectory(
                self.context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"HOT ROUTE: Lists menu error: {e}")
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
            return False
    
    def prompt_and_search(self) -> bool:
        """
        Search prompt and execution - consolidated from SearchHandler
        Hot path for basic search functionality
        """
        try:
            self.logger.info("HOT ROUTE: Prompt and search")
            
            # Get search terms with inline logic
            search_terms = self._prompt_for_search_terms()
            if not search_terms:
                self.logger.info("No search terms entered")
                xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False, updateListing=False)
                return False
            
            # Execute search using hot use cases
            results = self.hot_use_cases.search_basic(
                search_terms=search_terms,
                search_scope="both",
                match_logic="all"
            )
            
            # Handle results
            if results['total_count'] > 0:
                self._save_search_and_redirect(search_terms, results)
                return True
            else:
                self._show_no_results_message(search_terms)
                xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True, updateListing=False)
                return True
                
        except Exception as e:
            self.logger.error(f"HOT ROUTE: Search error: {e}")
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
            return False
    
    def view_list(self, list_id: str) -> bool:
        """
        View specific list contents - consolidated from ListsHandler.view_list
        Hot path for browsing list items
        """
        try:
            if not list_id:
                self.logger.error("HOT ROUTE: Missing list_id for view_list")
                xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
                return False
            
            self.logger.info(f"HOT ROUTE: Viewing list {list_id}")
            
            # Get list items using hot use cases
            browse_data = self.hot_use_cases.list_browse_basic(list_id=list_id)
            items = browse_data.get('items', [])
            
            if not items:
                self._show_empty_list_state(list_id)
                return True
            
            # Build list items with inline rendering
            for item in items:
                self._add_media_item(item)
            
            # Set content type and end directory
            xbmcplugin.setContent(self.context.addon_handle, 'movies')
            xbmcplugin.endOfDirectory(
                self.context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"HOT ROUTE: View list error: {e}")
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
            return False
    
    def show_folder(self, folder_id: str) -> bool:
        """
        Show folder contents - consolidated from ListsHandler.show_folder
        Hot path for folder navigation
        """
        try:
            if not folder_id:
                self.logger.error("HOT ROUTE: Missing folder_id for show_folder")
                xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
                return False
            
            self.logger.info(f"HOT ROUTE: Showing folder {folder_id}")
            
            # Get folder contents using hot use cases  
            browse_data = self.hot_use_cases.list_browse_basic(folder_id=folder_id)
            lists_in_folder = browse_data.get('lists', [])
            
            # Add tools & options for folder
            self._add_folder_tools_item(folder_id)
            
            if not lists_in_folder:
                self._show_empty_folder_state(folder_id)
                return True
            
            # Add lists in this folder
            for list_item in lists_in_folder:
                self._add_list_item(list_item)
            
            # End directory
            xbmcplugin.endOfDirectory(
                self.context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"HOT ROUTE: Show folder error: {e}")
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
            return False
    
    def show_favorites_basic(self) -> bool:
        """
        Basic Kodi favorites display - consolidated from FavoritesHandler  
        Hot path for favorites without heavy scanning
        """
        try:
            self.logger.info("HOT ROUTE: Displaying Kodi favorites")
            
            # Get favorites using hot use cases (cached)
            favorites = self.hot_use_cases.get_favorites_minimal(show_unmapped=True)
            
            # Add tools & options
            self._add_favorites_tools_item()
            
            if not favorites:
                self._show_empty_favorites_state()
                return True
            
            # Add favorites items with inline rendering
            for favorite in favorites:
                self._add_media_item(favorite)
            
            # Set content type and end directory
            xbmcplugin.setContent(self.context.addon_handle, 'movies')
            xbmcplugin.endOfDirectory(
                self.context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=True
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"HOT ROUTE: Favorites error: {e}")
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=False)
            return False
    
    # --- INLINE HELPER METHODS (MINIMAL IMPORTS) ---
    
    def _prompt_for_search_terms(self) -> Optional[str]:
        """Prompt user for search keywords - inline logic"""
        try:
            terms = xbmcgui.Dialog().input(
                "Enter search terms",  # Inline instead of L(33002) to avoid import
                type=xbmcgui.INPUT_ALPHANUM
            )
            return terms.strip() if terms and terms.strip() else None
        except Exception as e:
            self.logger.warning(f"Search terms input failed: {e}")
            return None
    
    def _show_empty_lists_state(self) -> bool:
        """Show empty lists state with minimal UI"""
        # Add Tools & Options
        tools_item = xbmcgui.ListItem(label="[COLOR yellow]⚙️ Tools & Options[/COLOR]")
        tools_item.setInfo('video', {'plot': 'Search, Favorites, Import/Export & Settings'})
        tools_item.setArt({'icon': "DefaultAddonProgram.png"})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('show_list_tools', list_type='lists_main'),
            tools_item,
            True
        )
        
        # Add Create First List option
        create_item = xbmcgui.ListItem(label="[COLOR lightgreen]+ Create Your First List[/COLOR]")
        create_item.setInfo('video', {'plot': 'Create your first list to get started'})
        create_item.setArt({'icon': "DefaultAddSource.png"})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('create_list_execute'),
            create_item,
            True
        )
        
        xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True, cacheToDisc=True)
        return True
    
    def _add_lists_menu_header(self):
        """Add Tools & Options header to lists menu"""
        tools_item = xbmcgui.ListItem(label="[COLOR yellow]⚙️ Tools & Options[/COLOR]")
        tools_item.setInfo('video', {'plot': 'Search, Favorites, Import/Export & Settings'})
        tools_item.setArt({'icon': "DefaultAddonProgram.png"})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('show_list_tools', list_type='lists_main'),
            tools_item,
            True
        )
    
    def _add_folder_item(self, folder_info: Dict[str, Any]):
        """Add folder item to directory listing"""
        folder_id = folder_info.get('id')
        folder_name = folder_info.get('name')
        list_count = folder_info.get('list_count', 0)
        
        list_item = xbmcgui.ListItem(label=f"[COLOR cyan]{folder_name}[/COLOR]")
        list_item.setInfo('video', {'plot': f"Folder with {list_count} lists"})
        
        context_menu = [
            (f"Tools & Options for '{folder_name}'",
             f"RunPlugin({self.context.build_url('show_list_tools', list_type='folder', list_id=folder_id)})")
        ]
        list_item.addContextMenuItems(context_menu)
        
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('show_folder', folder_id=folder_id),
            list_item,
            True
        )
    
    def _add_list_item(self, list_info: Dict[str, Any]):
        """Add list item to directory listing"""
        list_id = list_info.get('id')
        name = list_info.get('name', 'Unnamed List')
        description = list_info.get('description', '')
        item_count = list_info.get('item_count', 0)
        
        display_name = f"{name}"
        if item_count > 0:
            display_name += f" ({item_count})"
        
        list_item = xbmcgui.ListItem(label=display_name)
        if description:
            list_item.setInfo('video', {'plot': description})
        
        context_menu = [
            (f"Tools & Options for '{name}'",
             f"RunPlugin({self.context.build_url('show_list_tools', list_type='user_list', list_id=list_id)})")
        ]
        list_item.addContextMenuItems(context_menu)
        
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('show_list', list_id=list_id),
            list_item,
            True
        )
    
    def _add_media_item(self, item: Dict[str, Any]):
        """Add media item to directory listing using proper ListItemBuilder for info hijack"""
        try:
            # Lazy import ListItemBuilder only when rendering media items
            from .listitem_builder import ListItemBuilder
            
            # Create builder instance for this context - pass context for full functionality
            builder = ListItemBuilder(
                addon_handle=self.context.addon_handle,
                addon_id=self.context.addon.getAddonInfo('id'),
                context=self.context  # Pass full context for rich metadata
            )
            
            # Use the proper builder to create the item with info hijack support
            result = builder._build_single_item(item)
            if result:
                url, list_item, is_folder = result
                
                # Add the properly built item to directory
                xbmcplugin.addDirectoryItem(
                    self.context.addon_handle,
                    url,
                    list_item,
                    is_folder
                )
            else:
                self.logger.warning(f"Failed to build media item: {item.get('title', 'Unknown')}")
                
        except Exception as e:
            self.logger.error(f"Error adding media item {item.get('title', 'Unknown')}: {e}")
            # Fallback to simple rendering if builder fails
            self._add_simple_media_item_fallback(item)
    
    def _add_simple_media_item_fallback(self, item: Dict[str, Any]):
        """Fallback simple media item rendering if builder fails"""
        title = item.get('title', 'Unknown Title')
        year = item.get('year', '')
        
        # Build display label
        label = title
        if year:
            label += f" ({year})"
        
        list_item = xbmcgui.ListItem(label=label)
        list_item.setInfo('video', {'title': title, 'plot': item.get('plot', '')})
        
        # Use noop URL as fallback
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('noop'),
            list_item,
            False
        )
    
    def _add_folder_tools_item(self, folder_id: str):
        """Add tools item for folder"""
        tools_item = xbmcgui.ListItem(label="[COLOR yellow]Tools & Options[/COLOR]")
        tools_item.setInfo('video', {'plot': 'Access folder tools and options'})
        tools_item.setArt({'icon': "DefaultAddonProgram.png"})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('show_list_tools', list_type='folder', list_id=folder_id),
            tools_item,
            True
        )
    
    def _add_favorites_tools_item(self):
        """Add tools item for favorites"""
        tools_item = xbmcgui.ListItem(label="[COLOR yellow]Tools & Options[/COLOR]")
        tools_item.setInfo('video', {'plot': 'Access favorites tools and options'})
        tools_item.setArt({'icon': "DefaultAddonProgram.png"})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('show_list_tools', list_type='favorites'),
            tools_item,
            True
        )
    
    def _show_empty_list_state(self, list_id: str):
        """Show empty list state"""
        empty_item = xbmcgui.ListItem(label="[COLOR gray]This list is empty[/COLOR]")
        empty_item.setInfo('video', {'plot': 'No items in this list yet. Use context menu to add items.'})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('noop'),
            empty_item,
            False
        )
        xbmcplugin.setContent(self.context.addon_handle, 'movies')
        xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True, cacheToDisc=True)
    
    def _show_empty_folder_state(self, folder_id: str):
        """Show empty folder state"""
        empty_item = xbmcgui.ListItem(label="[COLOR gray]This folder is empty[/COLOR]")
        empty_item.setInfo('video', {'plot': 'No lists in this folder yet. Use Tools & Options to create lists.'})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('noop'),
            empty_item,
            False
        )
        xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True, cacheToDisc=True)
    
    def _show_empty_favorites_state(self):
        """Show empty favorites state"""
        empty_item = xbmcgui.ListItem(label="[COLOR gray]No favorites found[/COLOR]")
        empty_item.setInfo('video', {'plot': 'No Kodi favorites found or none mapped to library. Use "Tools & Options" to scan favorites.xml'})
        xbmcplugin.addDirectoryItem(
            self.context.addon_handle,
            self.context.build_url('noop'),
            empty_item,
            False
        )
        xbmcplugin.setContent(self.context.addon_handle, 'movies')
        xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True, cacheToDisc=True)
    
    def _show_no_results_message(self, search_terms: str):
        """Show no search results message"""
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            f"No results found for: {search_terms}",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
    
    def _save_search_and_redirect(self, search_terms: str, results: Dict[str, Any]):
        """Save search results and redirect - simplified version"""
        try:
            # Lazy import only when needed for search history  
            from ..data.query_manager import get_query_manager
            
            query_manager = get_query_manager()
            if query_manager and query_manager.initialize():
                # Create search history list
                search_folder_id = query_manager.get_or_create_search_history_folder()
                if search_folder_id:
                    list_name = f"Search: {search_terms}"
                    description = f"Search results for '{search_terms}' - {results['total_count']} items"
                    
                    # Create list and add items
                    list_id = query_manager.create_list(list_name, description, folder_id=search_folder_id)
                    if list_id:
                        # Add search results to the list
                        for item in results.get('items', []):
                            query_manager.add_item_to_list(list_id, item)
                        
                        # Redirect to the saved search list
                        xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True)
                        return True
            
            # Fallback: just show notification
            xbmcgui.Dialog().notification(
                "LibraryGenie",
                f"Found {results['total_count']} results for: {search_terms}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Save search error: {e}")
            # Show results count notification as fallback
            xbmcgui.Dialog().notification(
                "LibraryGenie", 
                f"Found {results['total_count']} results",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            xbmcplugin.endOfDirectory(self.context.addon_handle, succeeded=True)
            return True


# Global instance factory
_hot_routes_instance = None


def get_hot_routes(context: PluginContext):
    """Get hot routes instance for context"""
    # Create fresh instance per context to avoid state issues
    return HotRoutes(context)