#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Builder
Builds ListItems with proper metadata and resume information
"""

import json
from typing import List, Dict, Any, Optional
import xbmc
import xbmcgui
import xbmcplugin
from ..utils.logger import get_logger


def is_kodi_v20_plus():
    """
    Check if running Kodi version 20 or higher

    Returns:
        bool: True if Kodi major version >= 20, False otherwise
    """
    try:
        build_version = xbmc.getInfoLabel("System.BuildVersion")
        # Extract major version number from build string like "20.2 (20.2.0) Git:20231119-8b12c1c20e"
        major_version = int(build_version.split('.')[0])
        return major_version >= 20
    except (ValueError, IndexError, AttributeError):
        # If parsing fails, assume older version for safety
        return False


class ListItemBuilder:
    """Builds ListItems with proper separation between Kodi library and external items"""

    def __init__(self, addon_handle: int, addon_id: str):
        self.addon_handle = addon_handle
        self.addon_id = addon_id
        self.logger = get_logger(__name__)
        # Assuming base_url is needed for constructing plugin URLs,
        # it should be initialized or passed if used in methods.
        # For now, it's hardcoded in the plugin URL construction.
        # self.base_url = "" # If needed, initialize here or pass to relevant methods.

    def _is_kodi_v20_or_higher(self) -> bool:
        """Check if Kodi version is 20 (Nexus) or higher"""
        try:
            version_str = xbmc.getInfoLabel("System.BuildVersion")
            # Extract major version number (e.g., "20.0" -> 20)
            major_version = int(version_str.split('.')[0].split('-')[0])
            return major_version >= 20
        except (ValueError, IndexError):
            # Default to v19 behavior on parse error
            return False

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
                return self._create_library_listitem(item)
            else:
                self.logger.info(f"BUILDING EXTERNAL ITEM: '{title}' (no kodi_id or external source), has_kodi_id: {has_kodi_id}, source: {source}")
                return self._create_external_item(item)

        except Exception as e:
            self.logger.error(f"ITEM BUILD: Failed to build ListItem for {item.get('title', 'unknown')}: {e}")
            return None

    def _create_library_listitem(self, item: Dict[str, Any]) -> tuple:
        """Create ListItem for library-backed items with lightweight metadata and version-branched resume"""
        try:
            title = item.get('title', 'Unknown')
            kodi_id = item.get('kodi_id')
            media_type = item.get('media_type', 'movie')

            self.logger.debug(f"Creating library ListItem for '{title}' (kodi_id: {kodi_id}, type: {media_type})")

            # Create ListItem with title
            list_item = xbmcgui.ListItem(label=title)

            # Set URL for library items using videodb://
            if kodi_id and media_type == 'movie':
                url = f"videodb://movies/titles/{kodi_id}"
                list_item.setPath(url)
                list_item.setProperty('IsPlayable', 'true')
                self.logger.debug(f"Set videodb URL: {url}")
            elif kodi_id and media_type == 'episode':
                url = f"videodb://tvshows/titles/{item.get('tvshowid', 0)}/{item.get('season', 1)}/{kodi_id}"
                list_item.setPath(url)
                list_item.setProperty('IsPlayable', 'true')
                self.logger.logger.debug(f"Set episode videodb URL: {url}")
            else:
                # Fallback to plugin URL
                # Assuming self.base_url is defined or passed appropriately
                base_url = f"plugin://{self.addon_id}" # Example base_url
                url = f"{base_url}?action=play&kodi_id={kodi_id}&type={media_type}"
                list_item.setPath(url)
                list_item.setProperty('IsPlayable', 'true')

            # Set lightweight metadata only (no heavy fields like cast)
            info = self._build_lightweight_info(item)
            list_item.setInfo('video', info)

            # Set art (poster and fanart minimum, others only if valid)
            art = self._build_art_dict(item)
            if art:
                list_item.setArt(art)

            # Set resume information with version branching (always for library items)
            self._set_resume_info_versioned(list_item, item)

            self.logger.debug(f"Successfully created library ListItem for '{title}'")
            return url, list_item, False # isFolder is False for playable items

        except Exception as e:
            self.logger.error(f"Failed to create library ListItem: {e}")
            # Return a basic list item on failure, as per original structure
            return None

    def _build_lightweight_info(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Build lightweight info dictionary for list items (no heavy arrays)"""
        info = {}

        # Basic metadata (lightweight strings/numbers only)
        if item.get('title'):
            info['title'] = item['title']
        if item.get('originaltitle') and item['originaltitle'] != item.get('title'):
            info['originaltitle'] = item['originaltitle']
        if item.get('sorttitle'):
            info['sorttitle'] = item['sorttitle']
        if item.get('year'):
            info['year'] = int(item['year'])
        if item.get('genre'):
            info['genre'] = item['genre']
        if item.get('plot'):
            info['plot'] = item['plot']
        if item.get('rating'):
            info['rating'] = float(item['rating'])
        if item.get('votes'):
            info['votes'] = int(item['votes'])
        if item.get('mpaa'):
            info['mpaa'] = item['mpaa']
        if item.get('duration_minutes'):
            info['duration'] = int(item['duration_minutes'])
        if item.get('studio'):
            info['studio'] = item['studio']
        if item.get('country'):
            info['country'] = item['country']
        if item.get('premiered'):
            info['premiered'] = item['premiered']

        # Episode-specific fields
        if item.get('media_type') == 'episode':
            if item.get('tvshowtitle'):
                info['tvshowtitle'] = item['tvshowtitle']
            if item.get('season'):
                info['season'] = int(item['season'])
            if item.get('episode'):
                info['episode'] = int(item['episode'])
            if item.get('aired'):
                info['aired'] = item['aired']
            if item.get('playcount') is not None:
                info['playcount'] = int(item['playcount'])
            if item.get('lastplayed'):
                info['lastplayed'] = item['lastplayed']

        # Set media type
        info['mediatype'] = item.get('media_type', 'movie')

        # NOTE: Do not set heavy fields like cast, streamdetails arrays here
        # This keeps list scrolling snappy and matches Kodi's native approach

        return info

    def _build_art_dict(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Build art dictionary with poster/fanart minimum, others only if valid"""
        art = {}

        # Poster and fanart (minimum required)
        if item.get('poster'):
            art['poster'] = item['poster']
        elif item.get('thumbnail'):
            # Fallback to thumbnail if no poster
            art['poster'] = item['thumbnail']

        if item.get('fanart'):
            art['fanart'] = item['fanart']

        # Additional art only if valid (non-empty)
        if item.get('thumb'):
            art['thumb'] = item['thumb']
        if item.get('banner'):
            art['banner'] = item['banner']
        if item.get('landscape'):
            art['landscape'] = item['landscape']
        if item.get('clearlogo'):
            art['clearlogo'] = item['clearlogo']

        return art

    def _set_resume_info_versioned(self, list_item: xbmcgui.ListItem, item: Dict[str, Any]):
        """Set resume information with version branching (always for library items)"""
        try:
            resume_data = item.get('resume', {})
            position = resume_data.get('position_seconds', 0)
            total = resume_data.get('total_seconds', 0)

            if position > 0 and total > 0:
                if self._is_kodi_v20_or_higher():
                    # v20+ path: set resume point on video tag (seconds)
                    try:
                        video_tag = list_item.getVideoInfoTag()
                        video_tag.setResumePoint(position, total)
                        self.logger.debug(f"Set v20+ resume: {position}s / {total}s")
                    except Exception as e:
                        self.logger.warning(f"Failed to set v20+ resume, falling back to properties: {e}")
                        # Fallback to v19 method
                        list_item.setProperty('ResumeTime', str(position))
                        list_item.setProperty('TotalTime', str(total))
                else:
                    # v19 path (Matrix): set ListItem properties ResumeTime and TotalTime (seconds)
                    list_item.setProperty('ResumeTime', str(position))
                    list_item.setProperty('TotalTime', str(total))
                    self.logger.debug(f"Set v19 resume: {position}s / {total}s")

        except Exception as e:
            self.logger.error(f"Failed to set resume info: {e}")

    def _create_external_item(self, item: Dict[str, Any]) -> tuple:
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

        return url, list_item, not is_playable

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
        # Assuming self.base_url is defined or passed appropriately
        base_url = f"plugin://{self.addon_id}" # Example base_url
        return f"{base_url}?action=info&item_id={item_id}"

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
            result = self._build_library_item(item, f"plugin://{self.addon_id}", "play") # Pass necessary args
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
            result = self._build_external_item(item, f"plugin://{self.addon_id}", "play") # Pass necessary args
            if result:
                url, list_item, is_folder = result
                return list_item
            return None
        except Exception as e:
            self.logger.error(f"Failed to create external listitem: {e}")
            return None

    def _create_plugin_listitem(self, item: Dict[str, Any]) -> xbmcgui.ListItem:
        """Create ListItem for plugin/external items with lightweight metadata"""
        try:
            title = item.get('title', 'Unknown')
            self.logger.debug(f"Creating plugin ListItem for '{title}'")

            # Create ListItem
            list_item = xbmcgui.ListItem(label=title)

            # Set plugin URL (or route to play/details action)
            action = item.get('action', 'play')
            item_id = item.get('id', item.get('imdb_id', ''))
            # Assuming self.base_url is defined or passed appropriately
            base_url = f"plugin://{self.addon_id}" # Example base_url
            url = f"{base_url}?action={action}&id={item_id}"
            list_item.setPath(url)
            list_item.setProperty('IsPlayable', 'true')

            # Set lightweight metadata (same profile as library items)
            info = self._build_lightweight_info(item)
            list_item.setInfo('video', info)

            # Set art (poster/fanart minimum, others only if valid)
            art = self._build_art_dict(item)
            if art:
                list_item.setArt(art)

            # Resume for plugin-only: only set if we maintain our own resume store
            # (Your "always show resume" rule applies to library items; plugin-only at discretion)
            # For now, skip resume for external items unless explicitly provided

            self.logger.debug(f"Successfully created plugin ListItem for '{title}'")
            return list_item

        except Exception as e:
            self.logger.error(f"Failed to create plugin ListItem: {e}")
            return xbmcgui.ListItem(label=item.get('title', 'Unknown'))

    def _build_library_item(self, item: Dict[str, Any], base_url: str, action: str) -> Optional[tuple]:
        """Build ListItem for Kodi library items (movies/episodes)"""
        try:
            title = item.get("title", "Unknown Title")
            year = item.get("year")
            media_type = item.get("media_type", "movie")

            # Create basic ListItem
            if year:
                display_title = f"{title} ({year})"
            else:
                display_title = title

            list_item = xbmcgui.ListItem(label=display_title)

            # Set basic info
            info = {
                'title': title,
                'mediatype': media_type
            }
            if year:
                info['year'] = year

            # Add plot if available
            plot = item.get("plot") or item.get("description")
            if plot:
                info['plot'] = plot

            # Add rating if available
            rating = item.get("rating")
            if rating:
                try:
                    info['rating'] = float(rating)
                except (ValueError, TypeError):
                    pass

            # Add runtime if available
            runtime = item.get("runtime")
            if runtime:
                try:
                    info['duration'] = int(runtime) * 60  # Convert minutes to seconds
                except (ValueError, TypeError):
                    pass

            # Add genre if available
            genre = item.get("genre")
            if genre:
                if isinstance(genre, list):
                    info['genre'] = genre
                else:
                    info['genre'] = [genre] if genre else []

            # Add director if available
            director = item.get("director")
            if director:
                if isinstance(director, list):
                    info['director'] = director
                else:
                    info['director'] = [director] if director else []

            list_item.setInfo('video', info)

            # Set artwork
            art = {}
            poster = item.get("poster") or item.get("thumbnail")
            if poster:
                art["poster"] = poster
                art["thumb"] = poster

            fanart = item.get("fanart")
            if fanart:
                art["fanart"] = fanart

            if art:
                list_item.setArt(art)

            # Set as playable - library items should always be playable
            list_item.setProperty('IsPlayable', 'true')

            # Set appropriate URL
            kodi_id = item.get('kodi_id')
            if kodi_id and media_type == 'movie':
                url = f"videodb://movies/titles/{kodi_id}"
                list_item.setPath(url)
                self.logger.debug(f"Set videodb URL: {url}")
            elif kodi_id and media_type == 'episode':
                url = f"videodb://tvshows/titles/{item.get('tvshowid', 0)}/{item.get('season', 1)}/{kodi_id}"
                list_item.setPath(url)
                self.logger.debug(f"Set episode videodb URL: {url}")
            else:
                # Fallback to plugin URL
                url = f"{base_url}?action={action}&item_id={item.get('id', '')}"
                list_item.setPath(url)
                self.logger.debug(f"Set fallback plugin URL: {url}")

            # Set resume information with version branching
            self._set_resume_info_versioned(list_item, item)

            self.logger.debug(f"Successfully created library ListItem for '{title}'")
            return url, list_item, False # isFolder is False for playable items

        except Exception as e:
            self.logger.error(f"Failed to build library item: {e}")
            return None

    def _build_external_item(self, item: Dict[str, Any], base_url: str, action: str) -> Optional[tuple]:
        """Build ListItem for external/plugin items"""
        try:
            title = item.get("title", "Unknown Title")
            year = item.get("year")
            media_type = item.get('media_type', 'movie')

            # Create basic ListItem
            if year:
                display_title = f"{title} ({year})"
            else:
                display_title = title

            list_item = xbmcgui.ListItem(label=display_title)

            # Set basic info
            info = {
                'title': title,
                'mediatype': media_type
            }
            if year:
                info['year'] = year

            # Add plot if available
            plot = item.get("plot") or item.get("description")
            if plot:
                info['plot'] = plot

            list_item.setInfo('video', info)

            # Set artwork if available
            art = {}
            poster = item.get("poster") or item.get("thumbnail")
            if poster:
                art["poster"] = poster
                art["thumb"] = poster

            fanart = item.get("fanart")
            if fanart:
                art["fanart"] = fanart

            if art:
                list_item.setArt(art)

            # Set as playable if we have a play URL
            play_url = item.get("play")
            is_playable = bool(play_url)
            if is_playable:
                list_item.setProperty('IsPlayable', 'true')
            else:
                list_item.setProperty('IsPlayable', 'false')

            # Set context menu for external items
            self._set_external_context_menu(list_item, item)

            # Build playback URL
            url = self._build_playback_url(item)

            self.logger.debug(f"Built external item: {title} (type: {media_type}, playable: {is_playable})")

            return url, list_item, not is_playable

        except Exception as e:
            self.logger.error(f"Failed to build external item: {e}")
            return None

    def build_library_item(self, item: Dict[str, Any], base_url: str, action: str) -> Optional[xbmcgui.ListItem]:
        """Public method to build library item - delegates to private method"""
        result = self._build_library_item(item, base_url, action)
        if result:
            return result[1] # Return only the ListItem
        return None