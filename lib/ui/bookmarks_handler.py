#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Bookmarks Handler
Handles bookmark viewing and navigation functionality
"""

import json
from typing import List, Optional
import xbmcgui
import xbmcplugin
from lib.data.query_manager import QueryManager
from lib.ui.plugin_context import PluginContext
from lib.ui.directory_response import DirectoryResponse
from lib.ui.dialog_response import DialogResponse
from lib.ui.listitem_renderer import ListItemRenderer
from lib.ui.navigation_items import NavigationItems
from lib.utils.kodi_log import get_kodi_logger
from lib.ui.localization import L


class BookmarksHandler:
    """Handles bookmark-related operations and UI"""
    
    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_kodi_logger('lib.ui.bookmarks_handler')
        self.query_manager = context.query_manager
        self.renderer = ListItemRenderer(context)
        
    def show_bookmarks_menu(self, context: PluginContext) -> DirectoryResponse:
        """Show main bookmarks menu with folders and bookmarks"""
        try:
            # Get all bookmark folders (including root)
            folders = self._get_bookmark_folders()
            
            # Get root-level bookmarks
            root_bookmarks = self._get_bookmarks_in_folder(None)
            
            # Build directory listing
            list_items = []
            
            # Add folders first
            for folder in folders:
                folder_item = self._build_folder_listitem(folder)
                if folder_item:
                    list_items.append(folder_item)
            
            # Add root bookmarks
            for bookmark in root_bookmarks:
                bookmark_item = self._build_bookmark_listitem(bookmark)
                if bookmark_item:
                    list_items.append(bookmark_item)
            
            # If no bookmarks exist, show helpful message
            if not list_items:
                # Add informational item
                url = self.context.build_url(action='noop')
                info_item = xbmcgui.ListItem(label="No Bookmarks")
                info_item.setInfo('video', {'plot': "Right-click on any folder in Kodi and select LibraryGenie > Save Bookmark to get started"})
                info_item.setIsFolder(False)
                list_items.append((url, info_item, False))
            
            return DirectoryResponse(
                success=True,
                list_items=list_items,
                content_type='folders',
                cache_to_disc=False,
                update_listing=False
            )
            
        except Exception as e:
            self.logger.error("Error showing bookmarks menu: %s", e)
            return DirectoryResponse(
                success=False,
                message=f"Failed to load bookmarks: {str(e)}"
            )
    
    def show_bookmark_folder(self, context: PluginContext, folder_id: str) -> DirectoryResponse:
        """Show bookmarks within a specific folder"""
        try:
            folder_id_int = int(folder_id) if folder_id else None
            
            # Get folder info
            folder_info = None
            if folder_id_int:
                folder_info = self.query_manager.get_folder_by_id(folder_id_int)
                if not folder_info:
                    return DirectoryResponse(
                        success=False,
                        message="Bookmark folder not found"
                    )
            
            # Get bookmarks in this folder
            bookmarks = self._get_bookmarks_in_folder(folder_id_int)
            
            # Build directory listing
            list_items = []
            
            # Add parent navigation if we're in a subfolder
            if folder_id_int:
                parent_item = self._build_parent_navigation_item()
                if parent_item:
                    list_items.append(parent_item)
            
            # Add bookmarks
            for bookmark in bookmarks:
                bookmark_item = self._build_bookmark_listitem(bookmark)
                if bookmark_item:
                    list_items.append(bookmark_item)
            
            # If no bookmarks in folder, show helpful message
            if len(list_items) <= 1:  # Account for parent navigation
                folder_name = folder_info['name'] if folder_info else 'Root'
                url = self.context.build_url(action='noop')
                info_item = xbmcgui.ListItem(label=f"No Bookmarks in {folder_name}")
                info_item.setInfo('video', {'plot': "This folder is empty"})
                info_item.setIsFolder(False)
                list_items.append((url, info_item, False))
            
            return DirectoryResponse(
                success=True,
                list_items=list_items,
                content_type='files',
                cache_to_disc=False,
                update_listing=False
            )
            
        except Exception as e:
            self.logger.error("Error showing bookmark folder: %s", e)
            return DirectoryResponse(
                success=False,
                message=f"Failed to load bookmark folder: {str(e)}"
            )
    
    def navigate_to_bookmark(self, context: PluginContext, bookmark_id: str) -> DirectoryResponse:
        """Navigate to a saved bookmark location"""
        try:
            bookmark_id_int = int(bookmark_id)
            
            # Get bookmark from database
            from lib.data.bookmark_manager import get_bookmark_manager
            bookmark_manager = get_bookmark_manager()
            bookmark = bookmark_manager.get_bookmark_by_id(bookmark_id_int)
            
            if not bookmark:
                return DirectoryResponse(
                    success=False,
                    message="Bookmark not found",
                    notification_message="Bookmark not found"
                )
            
            # Navigate to the bookmark URL safely using navigation intent
            self.logger.info("Navigating to bookmark: %s -> %s", bookmark['display_name'], bookmark['url'][:50])
            
            # Use navigation intent instead of direct executebuiltin
            return DirectoryResponse(
                success=True,
                navigation_intent={
                    'type': 'container_update',
                    'url': bookmark['url'],
                    'replace': True
                },
                message=f"Navigating to: {bookmark['display_name']}",
                notification_message=f"Navigating to: {bookmark['display_name']}"
            )
            
        except Exception as e:
            self.logger.error("Error navigating to bookmark: %s", e)
            return DirectoryResponse(
                success=False,
                message="Failed to navigate to bookmark",
                notification_message="Failed to navigate to bookmark"
            )
    
    def _get_bookmark_folders(self) -> List[dict]:
        """Get all bookmark folders - for now return empty as we use flat structure"""
        try:
            # TODO: Implement proper bookmark folder hierarchy
            # For now, bookmarks use a flat structure with optional folder_id references
            # but no separate bookmark folder table exists
            self.logger.debug("Bookmark folders not yet implemented, using flat structure")
            return []
            
        except Exception as e:
            self.logger.error("Error getting bookmark folders: %s", e)
            return []
    
    def _get_bookmarks_in_folder(self, folder_id: Optional[int]) -> List[dict]:
        """Get bookmarks in a specific folder (None for root)"""
        try:
            from lib.data.bookmark_manager import get_bookmark_manager
            bookmark_manager = get_bookmark_manager()
            
            bookmarks = bookmark_manager.get_bookmarks(folder_id=folder_id)
            return bookmarks if bookmarks else []
            
        except Exception as e:
            self.logger.error("Error getting bookmarks in folder %s: %s", folder_id, e)
            return []
    
    def _build_folder_listitem(self, folder: dict) -> Optional[object]:
        """Build a ListItem for a bookmark folder"""
        try:
            folder_id = folder['id']
            folder_name = folder['name']
            
            # Build URL for showing folder contents
            url = self.context.build_url(
                action='show_bookmark_folder',
                folder_id=str(folder_id)
            )
            
            # Create ListItem
            listitem = xbmcgui.ListItem(label=folder_name)
            listitem.setIsFolder(True)
            
            # Set folder icon
            listitem.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            
            # Add context menu for folder management
            context_menu = [
                (L(37103) or "Rename Folder", f"RunPlugin({self.context.build_url(action='rename_bookmark_folder', folder_id=str(folder_id))})"),
                (L(37104) or "Delete Folder", f"RunPlugin({self.context.build_url(action='delete_bookmark_folder', folder_id=str(folder_id))})")
            ]
            listitem.addContextMenuItems(context_menu)
            
            return (url, listitem, True)
            
        except Exception as e:
            self.logger.error("Error building folder listitem: %s", e)
            return None
    
    def _build_bookmark_listitem(self, bookmark: dict) -> Optional[object]:
        """Build a ListItem for a bookmark"""
        try:
            bookmark_id = bookmark['id']
            display_name = bookmark['display_name']
            bookmark_type = bookmark['bookmark_type']
            description = bookmark.get('description', '')
            
            # Parse metadata and art
            metadata = {}
            art_data = {}
            
            if bookmark.get('metadata'):
                try:
                    metadata = json.loads(bookmark['metadata'])
                except (json.JSONDecodeError, Exception):
                    pass
                    
            if bookmark.get('art_data'):
                try:
                    art_data = json.loads(bookmark['art_data'])
                except (json.JSONDecodeError, Exception):
                    pass
            
            # Build URL for navigation
            url = self.context.build_url(
                action='navigate_to_bookmark',
                bookmark_id=str(bookmark_id)
            )
            
            # Create ListItem
            listitem = xbmcgui.ListItem(label=display_name)
            
            # Determine if this is a folder or playable item
            is_folder = True
            if bookmark_type in ('library',):
                # Library items might be playable
                url_lower = bookmark['url'].lower()
                if 'videodb://movies/titles/' in url_lower or 'videodb://tvshows/titles/' in url_lower:
                    is_folder = False
            elif bookmark_type == 'file':
                # File items might be playable
                url_lower = bookmark['url'].lower()
                video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v')
                if any(ext in url_lower for ext in video_extensions):
                    is_folder = False
            
            listitem.setIsFolder(is_folder)
            
            # Set description/plot
            if description:
                listitem.setInfo('video', {'plot': description})
            else:
                # Show bookmark type and URL info safely
                url_display = bookmark['url'][:50] + '...' if len(bookmark['url']) > 50 else bookmark['url']
                plot = f"Type: {bookmark_type.title()}\nLocation: {url_display}"
                listitem.setInfo('video', {'plot': plot})
            
            # Set artwork
            if art_data:
                listitem.setArt(art_data)
            else:
                # Default icons based on bookmark type
                if bookmark_type == 'network':
                    icon = 'DefaultNetwork.png'
                elif bookmark_type == 'file':
                    icon = 'DefaultFolder.png'
                elif bookmark_type == 'library':
                    icon = 'DefaultMovies.png'
                elif bookmark_type == 'special':
                    icon = 'DefaultAddonService.png'
                else:  # plugin
                    icon = 'DefaultAddon.png'
                
                listitem.setArt({'icon': icon, 'thumb': icon})
            
            # Add context menu for bookmark management
            context_menu = [
                (L(37105) or "Edit Bookmark", f"RunPlugin({self.context.build_url(action='edit_bookmark', bookmark_id=str(bookmark_id))})"),
                (L(37106) or "Delete Bookmark", f"RunPlugin({self.context.build_url(action='delete_bookmark', bookmark_id=str(bookmark_id))})")
            ]
            listitem.addContextMenuItems(context_menu)
            
            return (url, listitem, True)
            
        except Exception as e:
            self.logger.error("Error building bookmark listitem: %s", e)
            return None
    
    def _build_parent_navigation_item(self) -> Optional[object]:
        """Build parent navigation item for going back"""
        try:
            url = self.context.build_url(action='show_bookmarks')
            
            listitem = xbmcgui.ListItem(label="..")
            listitem.setIsFolder(True)
            listitem.setArt({'icon': 'DefaultFolderBack.png', 'thumb': 'DefaultFolderBack.png'})
            
            return (url, listitem, True)
            
        except Exception as e:
            self.logger.error("Error building parent navigation item: %s", e)
            return None