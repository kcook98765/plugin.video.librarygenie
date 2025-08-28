
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Builder
V19+ compatible ListItem creation following best practices
"""

import xbmcgui
import xbmcplugin
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlencode
from ..utils.logger import get_logger


class ListItemBuilder:
    """Build v19+ compatible ListItems for directories and playable content"""
    
    def __init__(self, addon_id: str, base_url: str):
        self.logger = get_logger(__name__)
        self.addon_id = addon_id
        self.base_url = base_url
        
    def build_directory_item(self, 
                           label: str,
                           action: str,
                           params: Dict[str, Any] = None,
                           label2: str = "",
                           art: Dict[str, str] = None,
                           context_menu: List[Tuple[str, str]] = None,
                           info: Dict[str, Any] = None) -> Tuple[str, xbmcgui.ListItem, bool]:
        """
        Build a directory (folder) item following v19+ guidelines
        
        Returns:
            Tuple of (url, listitem, is_folder)
        """
        # Build plugin URL - never empty for directories
        url_params = params or {}
        url_params['action'] = action
        url = f"{self.base_url}?{urlencode(url_params)}"
        
        # Create ListItem
        listitem = xbmcgui.ListItem(label=label, label2=label2)
        
        # Set as folder (not playable)
        listitem.setProperty('IsPlayable', 'false')
        
        # Set art with v19-safe keys, ensure icon is always set
        art_dict = art or {}
        if 'icon' not in art_dict:
            art_dict['icon'] = 'DefaultFolder.png'
        
        # Only set art keys that have valid values
        safe_art = {}
        for key in ['thumb', 'poster', 'fanart', 'banner', 'icon', 'landscape', 'clearlogo', 'clearart']:
            if key in art_dict and art_dict[key]:
                safe_art[key] = art_dict[key]
        
        if safe_art:
            listitem.setArt(safe_art)
        
        # Set info if provided
        if info:
            listitem.setInfo('video', info)
        
        # Add context menu if provided
        if context_menu:
            # Ensure all context menu commands are valid plugin URLs
            valid_menu = []
            for menu_label, command in context_menu:
                if command and (command.startswith('RunPlugin(') or 
                              command.startswith('Container.') or
                              command.startswith('plugin://')):
                    valid_menu.append((menu_label, command))
            
            if valid_menu:
                listitem.addContextMenuItems(valid_menu)
        
        return url, listitem, True  # is_folder = True
    
    def build_playable_item(self,
                           title: str,
                           play_url: str,
                           media_type: str = "video",
                           info: Dict[str, Any] = None,
                           art: Dict[str, str] = None,
                           context_menu: List[Tuple[str, str]] = None,
                           stream_info: Dict[str, Any] = None) -> Tuple[str, xbmcgui.ListItem, bool]:
        """
        Build a playable item following v19+ guidelines
        
        Args:
            title: Display title
            play_url: Either direct file path or plugin URL for resolution
            media_type: 'movie', 'episode', 'musicvideo', etc.
            info: Video info dictionary
            art: Art dictionary
            context_menu: Context menu items
            stream_info: Stream details if known
            
        Returns:
            Tuple of (url, listitem, is_folder)
        """
        # Create ListItem
        listitem = xbmcgui.ListItem(label=title)
        
        # Mark as playable - critical for v19+
        listitem.setProperty('IsPlayable', 'true')
        
        # Set video info with v19-safe keys
        video_info = info or {}
        
        # Ensure mediatype is set for proper skin rendering
        if 'mediatype' not in video_info:
            video_info['mediatype'] = media_type
        
        # Set title if not in info
        if 'title' not in video_info:
            video_info['title'] = title
        
        # Only include info we actually have
        safe_info = {}
        safe_keys = [
            'title', 'originaltitle', 'year', 'plot', 'genre', 'duration',
            'rating', 'votes', 'director', 'writer', 'studio', 'mpaa',
            'mediatype', 'aired', 'premiered', 'tagline', 'outline'
        ]
        
        for key in safe_keys:
            if key in video_info and video_info[key] is not None:
                safe_info[key] = video_info[key]
        
        if safe_info:
            listitem.setInfo('video', safe_info)
        
        # Set art with fallback to thumb if poster/fanart missing
        art_dict = art or {}
        if 'icon' not in art_dict:
            art_dict['icon'] = 'DefaultVideo.png'
        
        safe_art = {}
        for key in ['thumb', 'poster', 'fanart', 'banner', 'icon', 'landscape', 'clearlogo', 'clearart']:
            if key in art_dict and art_dict[key]:
                safe_art[key] = art_dict[key]
        
        if safe_art:
            listitem.setArt(safe_art)
        
        # Add stream info if available (don't fake it)
        if stream_info:
            if 'video' in stream_info:
                for stream in stream_info['video']:
                    listitem.addStreamInfo('video', stream)
            if 'audio' in stream_info:
                for stream in stream_info['audio']:
                    listitem.addStreamInfo('audio', stream)
        
        # Add context menu
        if context_menu:
            valid_menu = []
            for menu_label, command in context_menu:
                if command and (command.startswith('RunPlugin(') or 
                              command.startswith('Container.') or
                              command.startswith('plugin://')):
                    valid_menu.append((menu_label, command))
            
            if valid_menu:
                listitem.addContextMenuItems(valid_menu)
        
        return play_url, listitem, False  # is_folder = False
    
    def build_search_result_item(self,
                               item_data: Dict[str, Any],
                               is_authorized: bool = False) -> Tuple[str, xbmcgui.ListItem, bool]:
        """
        Build search result item with auth-aware routing
        
        Args:
            item_data: Media item data from search
            is_authorized: Whether user is authorized for remote features
        """
        title = item_data.get('title', 'Unknown')
        year = item_data.get('year')
        media_type = item_data.get('media_type', 'video')
        
        # Build display title
        display_title = title
        if year:
            display_title = f"{title} ({year})"
        
        # Determine play URL based on authorization and availability
        play_url = None
        
        # Check if we have a local file path
        local_file = item_data.get('file') or item_data.get('play')
        if local_file and (local_file.startswith('/') or local_file.startswith('smb://') or local_file.startswith('nfs://')):
            # Direct local file - best option
            play_url = local_file
        elif item_data.get('kodi_id'):
            # Can play via Kodi JSON-RPC
            play_url = f"{self.base_url}?action=play_kodi_item&kodi_id={item_data['kodi_id']}&media_type={media_type}"
        elif is_authorized and item_data.get('imdb_id'):
            # Authorized user - can try remote resolution
            play_url = f"{self.base_url}?action=play_remote_item&imdb_id={item_data['imdb_id']}"
        else:
            # Can't play - make it a details folder instead
            return self.build_directory_item(
                label=display_title,
                action='show_item_details',
                params={'item_id': item_data.get('id')},
                art=self._extract_art(item_data),
                info=self._extract_info(item_data, media_type)
            )
        
        # Build playable item
        return self.build_playable_item(
            title=display_title,
            play_url=play_url,
            media_type=media_type,
            info=self._extract_info(item_data, media_type),
            art=self._extract_art(item_data),
            context_menu=self._build_item_context_menu(item_data, is_authorized)
        )
    
    def _extract_info(self, item_data: Dict[str, Any], media_type: str) -> Dict[str, Any]:
        """Extract video info from item data"""
        info = {'mediatype': media_type}
        
        # Map common fields
        field_mapping = {
            'title': 'title',
            'year': 'year',
            'plot': 'plot',
            'rating': 'rating',
            'votes': 'votes',
            'duration': 'duration',
            'mpaa': 'mpaa',
            'genre': 'genre',
            'director': 'director',
            'writer': 'writer',
            'studio': 'studio'
        }
        
        for source_key, info_key in field_mapping.items():
            if source_key in item_data and item_data[source_key] is not None:
                info[info_key] = item_data[source_key]
        
        return info
    
    def _extract_art(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract art from item data"""
        art = {}
        
        # Map art fields
        art_mapping = {
            'poster': 'poster',
            'fanart': 'fanart',
            'thumb': 'thumb',
            'banner': 'banner',
            'clearlogo': 'clearlogo',
            'clearart': 'clearart',
            'landscape': 'landscape'
        }
        
        for source_key, art_key in art_mapping.items():
            if source_key in item_data and item_data[source_key]:
                art[art_key] = item_data[source_key]
        
        return art
    
    def _build_item_context_menu(self, item_data: Dict[str, Any], is_authorized: bool) -> List[Tuple[str, str]]:
        """Build context menu for media items"""
        menu = []
        
        # Add to list option
        menu.append((
            "Add to List",
            f"RunPlugin({self.base_url}?action=add_to_list&item_id={item_data.get('id')})"
        ))
        
        # Show details
        menu.append((
            "Show Details",
            f"RunPlugin({self.base_url}?action=show_item_details&item_id={item_data.get('id')})"
        ))
        
        # Remote search if authorized
        if is_authorized and item_data.get('title'):
            menu.append((
                "Search Online",
                f"RunPlugin({self.base_url}?action=remote_search&query={item_data['title']})"
            ))
        
        return menu
    
    def finish_directory(self, handle: int, content_type: str = "videos", sort_methods: List[int] = None):
        """
        Finish directory with proper v19+ settings
        
        Args:
            handle: Plugin handle
            content_type: Content type for skin rendering
            sort_methods: List of sort method constants
        """
        # Set content type so skins know how to render
        xbmcplugin.setContent(handle, content_type)
        
        # Add sort methods if specified
        if sort_methods:
            for method in sort_methods:
                xbmcplugin.addSortMethod(handle, method)
        else:
            # Default sort methods for v19
            xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED)
            xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_TITLE)
        
        # End directory
        xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True)
