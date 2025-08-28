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
            self.logger.info(f"DIRECTORY BUILD: Starting build_directory with {len(items)} items, content_type='{content_type}'")
            self.logger.debug(f"DIRECTORY BUILD: addon_handle={self.addon_handle}, addon_id='{self.addon_id}'")
            
            # Set container content once for the entire listing
            xbmcplugin.setContent(self.addon_handle, content_type)
            self.logger.debug(f"DIRECTORY BUILD: Set content type to '{content_type}'")
            
            # Add sort methods for better UX
            sort_methods = [
                ('SORT_METHOD_TITLE_IGNORE_THE', xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE),
                ('SORT_METHOD_DATE', xbmcplugin.SORT_METHOD_DATE),
                ('SORT_METHOD_VIDEO_YEAR', xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            ]
            
            for method_name, method_const in sort_methods:
                xbmcplugin.addSortMethod(self.addon_handle, method_const)
                self.logger.debug(f"DIRECTORY BUILD: Added sort method {method_name}")

            list_items = []
            successful_items = 0
            failed_items = 0

            for idx, item in enumerate(items):
                self.logger.debug(f"DIRECTORY BUILD: Processing item {idx+1}/{len(items)}: '{item.get('title', 'Unknown')}'")
                list_item = self._build_single_item(item)
                if list_item:
                    list_items.append(list_item)
                    successful_items += 1
                else:
                    failed_items += 1
                    self.logger.warning(f"DIRECTORY BUILD: Failed to build item {idx+1}: '{item.get('title', 'Unknown')}'")

            self.logger.info(f"DIRECTORY BUILD: Built {successful_items} items successfully, {failed_items} failed")

            # Add all items to directory
            for idx, (url, list_item, is_folder) in enumerate(list_items):
                self.logger.debug(f"DIRECTORY BUILD: Adding item {idx+1} to directory - URL: '{url}', isFolder: {is_folder}")
                xbmcplugin.addDirectoryItem(
                    handle=self.addon_handle,
                    url=url,
                    listitem=list_item,
                    isFolder=is_folder
                )

            xbmcplugin.endOfDirectory(self.addon_handle)
            self.logger.info(f"DIRECTORY BUILD: Successfully completed directory with {len(list_items)} items")
            return True

        except Exception as e:
            self.logger.error(f"DIRECTORY BUILD: Failed to build directory: {e}")
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
            title = item.get('title', 'Unknown')
            self.logger.debug(f"ITEM BUILD: Starting build for '{title}'")
            
            # Log all available item fields for debugging
            item_fields = list(item.keys())
            self.logger.debug(f"ITEM BUILD: Available fields for '{title}': {item_fields}")
            
            # Determine if this is a Kodi library item
            # Check for kodi_id from multiple possible fields
            kodi_id = item.get('kodi_id') or item.get('movieid') or item.get('id')
            has_kodi_id = kodi_id is not None
            media_type = item.get('media_type', 'movie')
            source = item.get('source', 'ext')
            
            self.logger.debug(f"ITEM BUILD: Item analysis for '{title}' - kodi_id: {kodi_id}, has_kodi_id: {has_kodi_id}, media_type: {media_type}, source: {source}")
            
            # For search results, if we have a kodi_id and no explicit external source, treat as library
            if has_kodi_id and (source == 'lib' or source != 'remote'):
                self.logger.info(f"BUILDING LIBRARY ITEM: '{title}' with kodi_id: {kodi_id}, source: {source}")
                return self._build_library_item(item)
            else:
                self.logger.info(f"BUILDING EXTERNAL ITEM: '{title}' (no kodi_id or external source), has_kodi_id: {has_kodi_id}, source: {source}")
                return self._build_external_item(item)

        except Exception as e:
            self.logger.error(f"ITEM BUILD: Failed to build ListItem for {item.get('title', 'unknown')}: {e}")
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

        # Build videodb:// path for native Kodi behavior - NO trailing slash for proper cast display
        if media_type == 'movie':
            # videodb://movies/titles/{movieid} - NO trailing slash for cast to work
            videodb_path = f"videodb://movies/titles/{kodi_id}"
            db_type = "movie"
        elif media_type == 'tvshow':
            # videodb://tvshows/titles/{tvshowid} - NO trailing slash
            videodb_path = f"videodb://tvshows/titles/{kodi_id}"
            db_type = "tvshow"
        elif media_type == 'episode':
            # For episodes, we need tvshowid, season, episode - NO trailing slash
            tvshow_id = item.get('tvshow_id', kodi_id)
            season = item.get('season', 1)
            episode = item.get('episode', 1)
            videodb_path = f"videodb://tvshows/titles/{tvshow_id}/{season}/{episode}"
            db_type = "episode"
        elif media_type == 'musicvideo':
            # videodb://musicvideos/titles/{musicvideoid} - NO trailing slash
            videodb_path = f"videodb://musicvideos/titles/{kodi_id}"
            db_type = "musicvideo"
        else:
            # Fallback to movie for unknown types - NO trailing slash
            videodb_path = f"videodb://movies/titles/{kodi_id}"
            db_type = "movie"
            
        self.logger.info(f"VIDEODB PATH: Built videodb path for '{title}' (kodi_id: {kodi_id}, type: {media_type}): {videodb_path}")
        self.logger.info(f"LIBRARY ITEM: Setting dbtype='{db_type}', dbid='{kodi_id}' for native Kodi integration")

        # Set complete lightweight metadata for display
        info_labels = {
            'mediatype': media_type,
            'title': title
        }
        self.logger.debug(f"LIBRARY ITEM: Base info_labels for '{title}': mediatype={media_type}")

        # Add all lightweight metadata that's useful for display
        metadata_fields = []
        if item.get('year'):
            info_labels['year'] = item['year']
            metadata_fields.append(f"year={item['year']}")
        if item.get('plot'):
            info_labels['plot'] = item['plot']  # Full plot is fine
            metadata_fields.append(f"plot={len(item['plot'])} chars")
        if item.get('genre'):
            info_labels['genre'] = item['genre']
            metadata_fields.append(f"genre='{item['genre']}'")
        if item.get('rating'):
            info_labels['rating'] = float(item['rating'])
            metadata_fields.append(f"rating={item['rating']}")
        if item.get('votes'):
            info_labels['votes'] = int(item['votes'])
            metadata_fields.append(f"votes={item['votes']}")
        if item.get('mpaa'):
            info_labels['mpaa'] = item['mpaa']
            metadata_fields.append(f"mpaa='{item['mpaa']}'")
        if item.get('duration'):
            info_labels['duration'] = int(item['duration'])
            metadata_fields.append(f"duration={item['duration']}s")
        if item.get('director'):
            info_labels['director'] = item['director']
            metadata_fields.append(f"director='{item['director']}'")
        if item.get('writer'):
            info_labels['writer'] = item['writer']
            metadata_fields.append(f"writer='{item['writer']}'")
        if item.get('studio'):
            info_labels['studio'] = item['studio']
            metadata_fields.append(f"studio='{item['studio']}'")
        if item.get('country'):
            info_labels['country'] = item['country']
            metadata_fields.append(f"country='{item['country']}'")

        # Handle TV show specific fields
        if media_type == 'episode':
            if item.get('season'):
                info_labels['season'] = int(item['season'])
                metadata_fields.append(f"season={item['season']}")
            if item.get('episode'):
                info_labels['episode'] = int(item['episode'])
                metadata_fields.append(f"episode={item['episode']}")
            if item.get('showtitle'):
                info_labels['tvshowtitle'] = item['showtitle']
                metadata_fields.append(f"showtitle='{item['showtitle']}'")

        self.logger.debug(f"LIBRARY ITEM: Set metadata fields for '{title}': {', '.join(metadata_fields)}")
        list_item.setInfo('video', info_labels)

        # DO NOT set cast, crew, or streamdetails here!
        # Kodi will automatically populate heavyweight data when the user navigates to video info
        # based on the dbtype/dbid properties we set below.

        # Set properties for native Kodi behavior - CRITICAL for cast/crew/heavy data
        list_item.setProperty('dbtype', db_type)
        list_item.setProperty('dbid', str(kodi_id))
        list_item.setProperty('mediatype', media_type)
        
        self.logger.debug(f"LIBRARY ITEM: Set critical properties for '{title}' - dbtype='{db_type}', dbid='{kodi_id}', mediatype='{media_type}'")
        
        # CRITICAL: Set DB ID on the InfoTagVideo for proper cast display
        try:
            video_info_tag = list_item.getVideoInfoTag()
            if video_info_tag:
                video_info_tag.setMediaType(media_type)
                video_info_tag.setDbId(kodi_id)
                self.logger.debug(f"LIBRARY ITEM: Set InfoTagVideo properties for '{title}' - mediatype='{media_type}', dbid='{kodi_id}'")
            else:
                self.logger.warning(f"LIBRARY ITEM: Could not get VideoInfoTag for '{title}'")
        except Exception as e:
            self.logger.warning(f"LIBRARY ITEM: Failed to set InfoTagVideo properties for '{title}': {e}")
        
        # Set unique IDs if available (helps with cross-linking)
        unique_ids = []
        if item.get('imdbnumber'):
            list_item.setProperty('uniqueid.imdb', item['imdbnumber'])
            unique_ids.append(f"imdb={item['imdbnumber']}")
        if item.get('tmdb_id'):
            list_item.setProperty('uniqueid.tmdb', str(item['tmdb_id']))
            unique_ids.append(f"tmdb={item['tmdb_id']}")
        
        if unique_ids:
            self.logger.debug(f"LIBRARY ITEM: Set unique IDs for '{title}': {', '.join(unique_ids)}")
        else:
            self.logger.debug(f"LIBRARY ITEM: No unique IDs available for '{title}'")

        # Set basic artwork only
        self._set_library_artwork(list_item, item)

        # CRITICAL: Use videodb path as the URL for addDirectoryItem - this is what Kodi uses for the item's path
        # setPath() would be overridden by the URL passed to addDirectoryItem, so we don't call it
        url = videodb_path
        
        self.logger.info(f"LIBRARY ITEM: Built for '{title}' - dbtype={db_type}, dbid={kodi_id}, mediatype={media_type}")
        self.logger.info(f"VIDEODB URL: Using '{url}' as addDirectoryItem URL for native Kodi integration")

        # Set context menu for library items
        self._set_library_context_menu(list_item, item)

        # For library items using videodb URLs, mark as playable files (NOT folders) for proper cast display
        # This is CRITICAL for Kodi to show cast information in the Video Information dialog
        is_folder = False
        list_item.setProperty('IsPlayable', 'true')
        
        self.logger.debug(f"Built library item: {title} (kodi_id: {kodi_id}, type: {media_type}, playable: True) - videodb URL will show proper cast in Video Information")

        return (url, list_item, is_folder)

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
        self.logger.debug(f"EXTERNAL ITEM: Base info_labels for '{title}': mediatype={media_type}")

        # Add all available metadata
        metadata_fields = []
        if item.get('year'):
            info_labels['year'] = item['year']
            metadata_fields.append(f"year={item['year']}")
        if item.get('plot'):
            info_labels['plot'] = item['plot']
            metadata_fields.append(f"plot={len(item['plot'])} chars")
        if item.get('genre'):
            info_labels['genre'] = item['genre']
            metadata_fields.append(f"genre='{item['genre']}'")
        if item.get('director'):
            info_labels['director'] = item['director']
            metadata_fields.append(f"director='{item['director']}'")
        if item.get('writer'):
            info_labels['writer'] = item['writer']
            metadata_fields.append(f"writer='{item['writer']}'")
        if item.get('studio'):
            info_labels['studio'] = item['studio']
            metadata_fields.append(f"studio='{item['studio']}'")
        if item.get('country'):
            info_labels['country'] = item['country']
            metadata_fields.append(f"country='{item['country']}'")
        if item.get('duration'):
            info_labels['duration'] = int(item['duration'])
            metadata_fields.append(f"duration={item['duration']}s")
        if item.get('rating'):
            info_labels['rating'] = float(item['rating'])
            metadata_fields.append(f"rating={item['rating']}")
        if item.get('votes'):
            info_labels['votes'] = int(item['votes'])
            metadata_fields.append(f"votes={item['votes']}")
        if item.get('mpaa'):
            info_labels['mpaa'] = item['mpaa']
            metadata_fields.append(f"mpaa='{item['mpaa']}'")

        # Handle TV show specific fields
        if media_type == 'episode':
            if item.get('season'):
                info_labels['season'] = int(item['season'])
                metadata_fields.append(f"season={item['season']}")
            if item.get('episode'):
                info_labels['episode'] = int(item['episode'])
                metadata_fields.append(f"episode={item['episode']}")
            if item.get('showtitle'):
                info_labels['tvshowtitle'] = item['showtitle']
                metadata_fields.append(f"showtitle='{item['showtitle']}'")

        self.logger.debug(f"EXTERNAL ITEM: Set metadata fields for '{title}': {', '.join(metadata_fields)}")
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

        # Set playable if we have a direct play URL and should play immediately
        is_playable = bool(item.get('play'))
        if is_playable:
            list_item.setProperty('IsPlayable', 'true')
        # Don't set IsPlayable='false' - let Kodi handle default behavior

        # Set context menu for external items
        self._set_external_context_menu(list_item, item)

        self.logger.debug(f"Built external item: {title} (type: {media_type}, playable: {is_playable})")

        return (url, list_item, not is_playable)

    def _set_cast(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set cast information for external items"""
        try:
            cast_data = item.get('cast')
            title = item.get('title', 'Unknown')
            
            if not cast_data:
                self.logger.debug(f"EXTERNAL CAST: No cast data available for '{title}'")
                return

            self.logger.debug(f"EXTERNAL CAST: Processing cast data for '{title}', type: {type(cast_data)}")

            # Handle both JSON string and dict
            if isinstance(cast_data, str):
                cast_list = json.loads(cast_data)
                self.logger.debug(f"EXTERNAL CAST: Parsed JSON cast data for '{title}', count: {len(cast_list) if isinstance(cast_list, list) else 'not a list'}")
            elif isinstance(cast_data, list):
                cast_list = cast_data
                self.logger.debug(f"EXTERNAL CAST: Using list cast data for '{title}', count: {len(cast_list)}")
            else:
                self.logger.warning(f"EXTERNAL CAST: Unsupported cast data type for '{title}': {type(cast_data)}")
                return

            # Convert to Kodi cast format
            kodi_cast = []
            for idx, cast_member in enumerate(cast_list):
                if isinstance(cast_member, dict):
                    cast_info = {
                        'name': cast_member.get('name', ''),
                        'role': cast_member.get('role', ''),
                        'thumbnail': cast_member.get('thumbnail', '')
                    }
                    kodi_cast.append(cast_info)
                    self.logger.debug(f"EXTERNAL CAST: Added cast member {idx+1} for '{title}': {cast_member.get('name', 'Unknown')} as {cast_member.get('role', 'Unknown role')}")
                else:
                    self.logger.warning(f"EXTERNAL CAST: Invalid cast member {idx+1} for '{title}': {type(cast_member)}")

            if kodi_cast:
                list_item.setCast(kodi_cast)
                self.logger.info(f"EXTERNAL CAST: Set {len(kodi_cast)} cast members for '{title}'")
            else:
                self.logger.warning(f"EXTERNAL CAST: No valid cast members found for '{title}'")

        except Exception as e:
            self.logger.warning(f"EXTERNAL CAST: Failed to set cast for '{item.get('title', 'Unknown')}': {e}")

    def _set_artwork(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set artwork for ListItem"""
        art_dict = {}
        title = item.get('title', 'Unknown')
        
        self.logger.debug(f"EXTERNAL ART: Processing artwork for '{title}'")

        if item.get('poster'):
            art_dict['poster'] = item['poster']
            art_dict['thumb'] = item['poster']  # Fallback
            self.logger.debug(f"EXTERNAL ART: Set poster/thumb for '{title}': {item['poster']}")

        if item.get('fanart'):
            art_dict['fanart'] = item['fanart']
            self.logger.debug(f"EXTERNAL ART: Set fanart for '{title}': {item['fanart']}")

        # Handle JSON art data for external items
        if item.get('art'):
            try:
                if isinstance(item['art'], str):
                    art_data = json.loads(item['art'])
                    self.logger.debug(f"EXTERNAL ART: Parsed JSON art data for '{title}', keys: {list(art_data.keys()) if isinstance(art_data, dict) else 'not a dict'}")
                else:
                    art_data = item['art']
                    self.logger.debug(f"EXTERNAL ART: Using dict art data for '{title}', keys: {list(art_data.keys()) if isinstance(art_data, dict) else 'not a dict'}")

                if isinstance(art_data, dict):
                    art_dict.update(art_data)
                    self.logger.debug(f"EXTERNAL ART: Updated art dict for '{title}' with keys: {list(art_data.keys())}")

            except Exception as e:
                self.logger.warning(f"EXTERNAL ART: Failed to parse art data for '{title}': {e}")

        if art_dict:
            list_item.setArt(art_dict)
            self.logger.info(f"EXTERNAL ART: Set artwork for '{title}' with keys: {list(art_dict.keys())}")
        else:
            self.logger.debug(f"EXTERNAL ART: No artwork available for '{title}'")

    def _set_library_artwork(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set all available artwork for Kodi library ListItem"""
        art_dict = {}
        
        # Set all available artwork - whatever we have available
        if item.get('poster'):
            art_dict['poster'] = item['poster']
            art_dict['thumb'] = item['poster']  # Use poster as thumb
        elif item.get('thumb'):
            art_dict['thumb'] = item['thumb']
        
        if item.get('fanart'):
            art_dict['fanart'] = item['fanart']
        if item.get('clearlogo'):
            art_dict['clearlogo'] = item['clearlogo']
        if item.get('discart'):
            art_dict['discart'] = item['discart']
        if item.get('clearart'):
            art_dict['clearart'] = item['clearart']
        if item.get('landscape'):
            art_dict['landscape'] = item['landscape']
        if item.get('banner'):
            art_dict['banner'] = item['banner']

        # Handle JSON art data if available
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
            self.logger.debug(f"Set artwork for library item {item.get('title', 'Unknown')}: {list(art_dict.keys())}")
        else:
            self.logger.debug(f"No artwork for library item: {item.get('title', 'Unknown')} - Kodi will use defaults")

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