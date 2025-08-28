#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Builder
Builds ListItems in two modes: Kodi Library Items vs Non-Library Items
"""

import json
from typing import List, Dict, Any, Optional
import xbmc
import xbmcgui
import xbmcplugin
from ..utils.logger import get_logger


class ListItemBuilder:
    """Builds ListItems with proper separation between Kodi library and external items"""

    def __init__(self, addon_handle: int, addon_id: str):
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_logger(__name__)

    def build_directory(self, items: List[Dict[str, Any]], content_type: str = "movies") -> bool:
        """
        Build a directory with proper content type and ListItems

        Args:
            items: List of media items with metadata
            content_type: "movies", "tvshows", or "episodes"

        Returns:
            bool: Success status
        """
        try:
            # Set container content once for the entire listing
            xbmcplugin.setContent(self.addon_handle, content_type)

            list_items = []

            for item in items:
                list_item = self._build_single_item(item)
                if list_item:
                    list_items.append(list_item)

            # Add all items to directory
            for url, list_item, is_folder in list_items:
                xbmcplugin.addDirectoryItem(
                    handle=self.addon_handle,
                    url=url,
                    listitem=list_item,
                    isFolder=is_folder
                )

            xbmcplugin.endOfDirectory(self.addon_handle)
            return True

        except Exception as e:
            self.logger.error(f"Failed to build directory: {e}")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
            return False

    def _build_single_item(self, item: Dict[str, Any]) -> Optional[tuple]:
        """
        Build a single ListItem based on whether it's in Kodi's library or not

        Args:
            item: Media item dictionary with metadata

        Returns:
            tuple: (url, listitem, is_folder) or None if failed
        """
        try:
            # Determine if this is a Kodi library item
            # Check for kodi_id from multiple possible fields
            kodi_id = item.get('kodi_id') or item.get('movieid') or item.get('id')
            has_kodi_id = kodi_id is not None
            media_type = item.get('media_type', 'movie')
            source = item.get('source', 'ext')
            
            # For search results, if we have a kodi_id and no explicit external source, treat as library
            if has_kodi_id and (source == 'lib' or source != 'remote'):
                self.logger.debug(f"Building library item for '{item.get('title')}' with kodi_id: {kodi_id}")
                return self._build_library_item(item)
            else:
                self.logger.debug(f"Building external item for '{item.get('title')}' (no kodi_id or external source)")
                return self._build_external_item(item)

        except Exception as e:
            self.logger.error(f"Failed to build ListItem for {item.get('title', 'unknown')}: {e}")
            return None

    def _build_library_item(self, item: Dict[str, Any]) -> tuple:
        """
        Build ListItem for Kodi library item (minimal metadata, let Kodi handle heavy data)

        Args:
            item: Media item with kodi_id

        Returns:
            tuple: (url, listitem, is_folder)
        """
        media_type = item.get('media_type', 'movie')
        # Get kodi_id from multiple possible fields
        kodi_id = item.get('kodi_id') or item.get('movieid') or item.get('id')
        title = item.get('title', 'Unknown Title')
        
        if not kodi_id:
            self.logger.error(f"No kodi_id found for library item: {title}")
            return self._build_external_item(item)

        # Create ListItem
        list_item = xbmcgui.ListItem(label=title)

        # Build videodb:// path for native Kodi behavior
        if media_type == 'movie':
            # videodb://movies/titles/{movieid}
            videodb_path = f"videodb://movies/titles/{kodi_id}"
            db_type = "movie"
        elif media_type == 'tvshow':
            # videodb://tvshows/titles/{tvshowid}
            videodb_path = f"videodb://tvshows/titles/{kodi_id}"
            db_type = "tvshow"
        elif media_type == 'episode':
            # For episodes, we need tvshowid, season, episode
            tvshow_id = item.get('tvshow_id', kodi_id)
            season = item.get('season', 1)
            episode = item.get('episode', 1)
            videodb_path = f"videodb://tvshows/titles/{tvshow_id}/{season}/{episode}"
            db_type = "episode"
        else:
            # Fallback to movie
            videodb_path = f"videodb://movies/titles/{kodi_id}"
            db_type = "movie"
            
        self.logger.debug(f"Built videodb path for {title}: {videodb_path}")

        # Set minimal video info labels - only lightweight display data
        info_labels = {
            'mediatype': media_type,
            'title': title
        }

        # Add basic lightweight metadata only
        if media_type == 'movie' and item.get('year'):
            info_labels['year'] = item['year']

        # Only set lightweight metadata that's needed for list display
        if item.get('plot') and len(item['plot']) < 500:  # Short plot only
            info_labels['plotoutline'] = item['plot'][:200]  # Brief outline
        if item.get('rating'):
            info_labels['rating'] = float(item['rating'])
        if item.get('genre'):
            info_labels['genre'] = item['genre']

        list_item.setInfo('video', info_labels)

        # DO NOT set cast, crew, or other heavy metadata here!
        # Kodi will automatically populate this when the user navigates to video info
        # based on the dbtype/dbid properties we set below.

        # Set properties for native Kodi behavior - CRITICAL for cast/crew/heavy data
        list_item.setProperty('dbtype', db_type)
        list_item.setProperty('dbid', str(kodi_id))
        
        # Also set the mediatype property to help Kodi identify the content
        list_item.setProperty('mediatype', media_type)

        # Set unique IDs if available (helps with cross-linking)
        if item.get('imdbnumber'):
            list_item.setProperty('uniqueid.imdb', item['imdbnumber'])
        if item.get('tmdb_id'):
            list_item.setProperty('uniqueid.tmdb', str(item['tmdb_id']))

        # Set basic artwork only
        self._set_library_artwork(list_item, item)

        # Use videodb path for native behavior
        url = videodb_path

        # Set context menu for library items
        self._set_library_context_menu(list_item, item)

        self.logger.debug(f"Built library item: {title} (kodi_id: {kodi_id}, type: {media_type}) - Kodi will handle heavy metadata")

        return (url, list_item, False)

    def _build_external_item(self, item: Dict[str, Any]) -> tuple:
        """
        Build ListItem for external/non-library item (full metadata control)

        Args:
            item: Media item without kodi_id

        Returns:
            tuple: (url, listitem, is_folder)
        """
        media_type = item.get('media_type', 'movie')
        title = item.get('title', 'Unknown Title')

        # Create ListItem
        list_item = xbmcgui.ListItem(label=title)

        # Build comprehensive info labels
        info_labels = {
            'mediatype': media_type,
            'title': title
        }

        # Add all available metadata
        if item.get('year'):
            info_labels['year'] = item['year']
        if item.get('plot'):
            info_labels['plot'] = item['plot']
        if item.get('genre'):
            info_labels['genre'] = item['genre']
        if item.get('director'):
            info_labels['director'] = item['director']
        if item.get('writer'):
            info_labels['writer'] = item['writer']
        if item.get('studio'):
            info_labels['studio'] = item['studio']
        if item.get('country'):
            info_labels['country'] = item['country']
        if item.get('duration'):
            info_labels['duration'] = int(item['duration'])
        if item.get('rating'):
            info_labels['rating'] = float(item['rating'])
        if item.get('votes'):
            info_labels['votes'] = int(item['votes'])
        if item.get('mpaa'):
            info_labels['mpaa'] = item['mpaa']

        # Handle TV show specific fields
        if media_type == 'episode':
            if item.get('season'):
                info_labels['season'] = int(item['season'])
            if item.get('episode'):
                info_labels['episode'] = int(item['episode'])
            if item.get('showtitle'):
                info_labels['tvshowtitle'] = item['showtitle']

        list_item.setInfo('video', info_labels)

        # Set cast if available (external items need manual cast)
        self._set_cast(list_item, item)

        # Set unique IDs for external items (for our own use)
        if item.get('imdbnumber'):
            list_item.setProperty('uniqueid.imdb', item['imdbnumber'])
        if item.get('tmdb_id'):
            list_item.setProperty('uniqueid.tmdb', str(item['tmdb_id']))

        # Set artwork
        self._set_artwork(list_item, item)

        # Build playback URL
        url = self._build_playback_url(item)

        # Set playable if we have a direct play URL
        is_playable = bool(item.get('play'))
        if is_playable:
            list_item.setProperty('IsPlayable', 'true')

        # Set context menu for external items
        self._set_external_context_menu(list_item, item)

        self.logger.debug(f"Built external item: {title} (type: {media_type}, playable: {is_playable})")

        return (url, list_item, not is_playable)

    def _set_cast(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set cast information for external items"""
        try:
            cast_data = item.get('cast')
            if not cast_data:
                return

            # Handle both JSON string and dict
            if isinstance(cast_data, str):
                cast_list = json.loads(cast_data)
            elif isinstance(cast_data, list):
                cast_list = cast_data
            else:
                return

            # Convert to Kodi cast format
            kodi_cast = []
            for cast_member in cast_list:
                if isinstance(cast_member, dict):
                    cast_info = {
                        'name': cast_member.get('name', ''),
                        'role': cast_member.get('role', ''),
                        'thumbnail': cast_member.get('thumbnail', '')
                    }
                    kodi_cast.append(cast_info)

            if kodi_cast:
                list_item.setCast(kodi_cast)

        except Exception as e:
            self.logger.warning(f"Failed to set cast: {e}")

    def _set_artwork(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set artwork for ListItem"""
        art_dict = {}

        if item.get('poster'):
            art_dict['poster'] = item['poster']
            art_dict['thumb'] = item['poster']  # Fallback

        if item.get('fanart'):
            art_dict['fanart'] = item['fanart']

        # Handle JSON art data for external items
        if item.get('art'):
            try:
                if isinstance(item['art'], str):
                    art_data = json.loads(item['art'])
                else:
                    art_data = item['art']

                if isinstance(art_data, dict):
                    art_dict.update(art_data)

            except Exception as e:
                self.logger.warning(f"Failed to parse art data: {e}")

        if art_dict:
            list_item.setArt(art_dict)

    def _set_library_artwork(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set basic artwork for Kodi library ListItem (minimal for list display)"""
        art_dict = {}
        
        # Set only basic artwork needed for list display
        if item.get('poster'):
            art_dict['poster'] = item['poster']
            art_dict['thumb'] = item['poster']  # Use poster as thumb
        elif item.get('thumb'):
            art_dict['thumb'] = item['thumb']
        
        if item.get('fanart'):
            art_dict['fanart'] = item['fanart']

        # Don't fetch heavy artwork - Kodi will handle this when user views details
        if art_dict:
            list_item.setArt(art_dict)
            self.logger.debug(f"Set basic artwork for library item {item.get('title', 'Unknown')}: {list(art_dict.keys())}")
        else:
            self.logger.debug(f"No basic artwork for library item: {item.get('title', 'Unknown')} - Kodi will use defaults")

    def _build_playback_url(self, item: Dict[str, Any]) -> str:
        """Build playback URL for external items"""
        # If we have a direct play URL, use it
        play_url = item.get('play')
        if play_url:
            return play_url

        # Otherwise, build a plugin URL for info/search
        item_id = item.get('id', '')
        return f"plugin://{self.addon_id}/?action=info&item_id={item_id}"

    def _set_library_context_menu(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set context menu for library items"""
        context_items = []

        # Add to list options
        context_items.append((
            "Add to List",
            f"RunPlugin(plugin://{self.addon_id}/?action=add_to_list&item_id={item.get('id', '')})"
        ))

        # Remove from list (if in a list context)
        if item.get('list_id'):
            context_items.append((
                "Remove from List",
                f"RunPlugin(plugin://{self.addon_id}/?action=remove_from_list&list_id={item['list_id']}&item_id={item.get('id', '')})"
            ))

        list_item.addContextMenuItems(context_items)

    def _set_external_context_menu(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set context menu for external items"""
        context_items = []

        # Search for item in library
        context_items.append((
            "Search in Library",
            f"RunPlugin(plugin://{self.addon_id}/?action=search_library&title={item.get('title', '')})"
        ))

        # Add to list options
        context_items.append((
            "Add to List",
            f"RunPlugin(plugin://{self.addon_id}/?action=add_to_list&item_id={item.get('id', '')})"
        ))

        list_item.addContextMenuItems(context_items)

    def _create_library_listitem(self, item: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Create ListItem for library items (compatibility method)"""
        try:
            # Determine if this is a library item or external item
            if item.get('kodi_id') or item.get('movieid'):
                return self._create_kodi_library_listitem(item)
            else:
                return self._create_external_listitem(item)
        except Exception as e:
            self.logger.error(f"Failed to create library listitem: {e}")
            return None

    def _create_kodi_library_listitem(self, item: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Create ListItem for Kodi library items (compatibility method)"""
        try:
            # Use the existing _build_library_item method but return just the ListItem
            result = self._build_library_item(item)
            if result:
                url, list_item, is_folder = result
                return list_item
            return None
        except Exception as e:
            self.logger.error(f"Failed to create Kodi library listitem: {e}")
            return None

    def _create_external_listitem(self, item: Dict[str, Any]) -> Optional[xbmcgui.ListItem]:
        """Create ListItem for external items (compatibility method)"""
        try:
            # Use the existing _build_external_item method but return just the ListItem
            result = self._build_external_item(item)
            if result:
                url, list_item, is_folder = result
                return list_item
            return None
        except Exception as e:
            self.logger.error(f"Failed to create external listitem: {e}")
            return None