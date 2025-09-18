#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ListItem Utilities
Consolidated utilities for Kodi ListItem operations to eliminate code duplication
"""

import xbmcgui
from typing import Dict, Any, Optional, List, Tuple, Callable
from lib.utils.kodi_version import get_kodi_major_version
from lib.utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('lib.utils.listitem_utils')

class ListItemMetadataManager:
    """Unified metadata manager for Kodi ListItems with version-aware handling"""
    
    def __init__(self, addon_id: str):
        self.addon_id = addon_id
        self.logger = logger
        
    def set_basic_metadata(self, list_item: xbmcgui.ListItem, title: str, plot: Optional[str] = None, item_type: str = "video") -> bool:
        """
        Set basic metadata (title and plot) using version-appropriate method.
        
        Args:
            list_item: The ListItem to set metadata on
            title: The title to set
            plot: Optional plot/description text
            item_type: Used for logging context (e.g., "list", "folder", "movie")
            
        Returns:
            bool: True if metadata was set successfully, False otherwise
        """
        try:
            kodi_major = get_kodi_major_version()
            
            if kodi_major >= 21:
                # v21+: Use InfoTagVideo ONLY - avoid setInfo() to prevent deprecation warnings
                return self._set_metadata_infotag(list_item, title, plot, item_type, allow_fallback=False)
                
            elif kodi_major == 20:
                # v20: Try InfoTagVideo first, fallback to setInfo() if needed
                return self._set_metadata_infotag(list_item, title, plot, item_type, allow_fallback=True)
                
            else:
                # v19: Use setInfo() only
                return self._set_metadata_setinfo(list_item, title, plot, item_type)
                
        except Exception as e:
            self.logger.error("METADATA: Failed to set basic metadata for %s '%s': %s", item_type, title, e)
            return False
    
    def _set_metadata_infotag(self, list_item: xbmcgui.ListItem, title: str, plot: Optional[str] = None, item_type: str = "video", allow_fallback: bool = True) -> bool:
        """Set metadata using InfoTagVideo method"""
        try:
            video_info_tag = list_item.getVideoInfoTag()
            video_info_tag.setTitle(title)
            if plot:
                video_info_tag.setPlot(plot)
            
            kodi_major = get_kodi_major_version()
            self.logger.debug("METADATA v%d+: Set metadata via InfoTagVideo for %s '%s'", kodi_major, item_type, title)
            return True
            
        except Exception as e:
            kodi_major = get_kodi_major_version()
            if allow_fallback and kodi_major == 20:
                self.logger.warning("METADATA v20: InfoTagVideo failed for %s '%s': %s, falling back to setInfo()", item_type, title, e)
                return self._set_metadata_setinfo(list_item, title, plot, item_type)
            else:
                self.logger.error("METADATA v%d+: InfoTagVideo failed for %s '%s': %s", kodi_major, item_type, title, e)
                return False
    
    def _set_metadata_setinfo(self, list_item: xbmcgui.ListItem, title: str, plot: Optional[str] = None, item_type: str = "video") -> bool:
        """Set metadata using setInfo method"""
        try:
            info_dict = {'title': title}
            if plot:
                info_dict['plot'] = plot
                
            list_item.setInfo('video', info_dict)
            self.logger.debug("METADATA v19: Set metadata via setInfo for %s '%s'", item_type, title)
            return True
            
        except Exception as e:
            self.logger.error("METADATA v19: setInfo failed for %s '%s': %s", item_type, title, e)
            return False
    
    def set_comprehensive_metadata(self, list_item: xbmcgui.ListItem, item_data: Dict[str, Any], title_override: Optional[str] = None) -> bool:
        """
        Set comprehensive metadata for media items using version-appropriate method.
        
        Args:
            list_item: The ListItem to set metadata on
            item_data: Dictionary containing item metadata
            title_override: Optional title override (useful for formatted episode titles)
            
        Returns:
            bool: True if metadata was set successfully
        """
        try:
            kodi_major = get_kodi_major_version()
            title = title_override or item_data.get('title', 'Unknown')
            
            if kodi_major >= 20:
                # v20+: Use InfoTagVideo setters
                return self._set_comprehensive_infotag(list_item, item_data, title)
            else:
                # v19: Use setInfo() with lightweight info dict
                return self._set_comprehensive_setinfo(list_item, item_data, title)
                
        except Exception as e:
            self.logger.error("METADATA: Failed to set comprehensive metadata: %s", e)
            return False
    
    def _set_comprehensive_infotag(self, list_item: xbmcgui.ListItem, item_data: Dict[str, Any], title: str) -> bool:
        """Set comprehensive metadata using InfoTagVideo"""
        import json
        try:
            video_info_tag = list_item.getVideoInfoTag()
            
            # Core fields
            video_info_tag.setTitle(title)
            
            if item_data.get('originaltitle') and item_data['originaltitle'] != item_data.get('title'):
                video_info_tag.setOriginalTitle(item_data['originaltitle'])
            
            if item_data.get('plot'):
                video_info_tag.setPlot(item_data['plot'])
            
            if item_data.get('year'):
                try:
                    video_info_tag.setYear(int(item_data['year']))
                except (ValueError, TypeError):
                    pass
            
            if item_data.get('rating'):
                try:
                    video_info_tag.setRating(float(item_data['rating']))
                except (ValueError, TypeError):
                    pass
            
            if item_data.get('genre'):
                try:
                    # V20+ stores genre as JSON array, parse it back to list
                    if isinstance(item_data['genre'], str) and item_data['genre'].startswith('['):
                        genre_list = json.loads(item_data['genre'])
                        video_info_tag.setGenres(genre_list if isinstance(genre_list, list) else [item_data['genre']])
                    else:
                        # Handle as string or already parsed list
                        video_info_tag.setGenres([item_data['genre']] if isinstance(item_data['genre'], str) else item_data['genre'])
                except (json.JSONDecodeError, ValueError):
                    # Fallback for malformed JSON or non-JSON strings
                    video_info_tag.setGenres([item_data['genre']] if isinstance(item_data['genre'], str) else item_data['genre'])
            
            if item_data.get('votes'):
                try:
                    video_info_tag.setVotes(int(item_data['votes']))
                except (ValueError, TypeError):
                    pass
                    
            # Handle duration - prefer duration_seconds if available, else convert from minutes
            if item_data.get('duration_seconds'):
                try:
                    video_info_tag.setDuration(int(item_data['duration_seconds']))
                except (ValueError, TypeError):
                    pass
            elif item_data.get('duration'):
                try:
                    # Duration is stored in minutes, but InfoTagVideo.setDuration expects seconds
                    duration_minutes = int(item_data['duration'])
                    duration_seconds = duration_minutes * 60
                    video_info_tag.setDuration(duration_seconds)
                except (ValueError, TypeError):
                    pass
                    
            if item_data.get('mpaa'):
                video_info_tag.setMpaa(item_data['mpaa'])
                
            if item_data.get('director'):
                try:
                    # V20+ stores director as JSON array, parse it back to list
                    if isinstance(item_data['director'], str) and item_data['director'].startswith('['):
                        director_list = json.loads(item_data['director'])
                        video_info_tag.setDirectors(director_list if isinstance(director_list, list) else [item_data['director']])
                    else:
                        # Handle as string or already parsed list
                        video_info_tag.setDirectors([item_data['director']] if isinstance(item_data['director'], str) else item_data['director'])
                except (json.JSONDecodeError, ValueError):
                    # Fallback for malformed JSON or non-JSON strings
                    video_info_tag.setDirectors([item_data['director']] if isinstance(item_data['director'], str) else item_data['director'])
                
            if item_data.get('studio'):
                video_info_tag.setStudios([item_data['studio']] if isinstance(item_data['studio'], str) else item_data['studio'])
                
            if item_data.get('country'):
                video_info_tag.setCountries([item_data['country']] if isinstance(item_data['country'], str) else item_data['country'])
                
            if item_data.get('writer'):
                video_info_tag.setWriters([item_data['writer']] if isinstance(item_data['writer'], str) else item_data['writer'])
                
            if item_data.get('imdbnumber'):
                video_info_tag.setIMDbNumber(item_data['imdbnumber'])
                
            if item_data.get('tmdb_id'):
                video_info_tag.setUniqueId(str(item_data['tmdb_id']), 'tmdb')
            
            # Episode-specific fields
            if item_data.get('media_type') == 'episode':
                if item_data.get('tvshowtitle'):
                    video_info_tag.setTvShowTitle(item_data['tvshowtitle'])
                if item_data.get('season') is not None:
                    video_info_tag.setSeason(int(item_data['season']))
                if item_data.get('episode') is not None:
                    video_info_tag.setEpisode(int(item_data['episode']))
                if item_data.get('aired'):
                    video_info_tag.setFirstAired(item_data['aired'])
            
            self.logger.debug("METADATA: Set comprehensive InfoTagVideo metadata for '%s'", title)
            return True
            
        except Exception as e:
            self.logger.error("METADATA: InfoTagVideo comprehensive setup failed for '%s': %s", title, e)
            return False
    
    def _set_comprehensive_setinfo(self, list_item: xbmcgui.ListItem, item_data: Dict[str, Any], title: str) -> bool:
        """Set comprehensive metadata using setInfo"""
        import json
        try:
            info = {'title': title}
            
            # Add available fields
            if item_data.get('originaltitle') and item_data['originaltitle'] != item_data.get('title'):
                info['originaltitle'] = item_data['originaltitle']
            
            if item_data.get('plot'):
                info['plot'] = item_data['plot']
            
            if item_data.get('year'):
                try:
                    info['year'] = str(int(item_data['year']))
                except (ValueError, TypeError):
                    pass
            
            if item_data.get('rating'):
                try:
                    info['rating'] = str(float(item_data['rating']))
                except (ValueError, TypeError):
                    pass
            
            if item_data.get('genre'):
                try:
                    # Handle different genre formats for V19 setInfo compatibility
                    if isinstance(item_data['genre'], list):
                        # Already a Python list - join to comma-separated string
                        info['genre'] = ', '.join(item_data['genre'])
                    elif isinstance(item_data['genre'], str) and item_data['genre'].lstrip().startswith('['):
                        # V20+ JSON-formatted genre data - parse and join
                        genre_list = json.loads(item_data['genre'])
                        info['genre'] = ', '.join(genre_list) if isinstance(genre_list, list) else item_data['genre']
                    else:
                        # Handle as regular string
                        info['genre'] = str(item_data['genre'])
                except (json.JSONDecodeError, ValueError):
                    # Fallback for malformed JSON
                    info['genre'] = item_data['genre']
            
            if item_data.get('votes'):
                try:
                    info['votes'] = str(int(item_data['votes']))
                except (ValueError, TypeError):
                    pass
                    
            # Handle duration - prefer duration_seconds if available, else convert from minutes
            if item_data.get('duration_seconds'):
                try:
                    info['duration'] = str(int(item_data['duration_seconds']))
                except (ValueError, TypeError):
                    pass
            elif item_data.get('duration'):
                try:
                    # Duration is stored in minutes, but V19 needs seconds
                    duration_minutes = int(item_data['duration'])
                    duration_seconds = duration_minutes * 60
                    info['duration'] = str(duration_seconds)
                except (ValueError, TypeError):
                    pass
                    
            if item_data.get('mpaa'):
                info['mpaa'] = item_data['mpaa']
                
            if item_data.get('director'):
                try:
                    # Handle different director formats for V19 setInfo compatibility
                    if isinstance(item_data['director'], list):
                        # Already a Python list - join to comma-separated string
                        info['director'] = ', '.join(item_data['director'])
                    elif isinstance(item_data['director'], str) and item_data['director'].lstrip().startswith('['):
                        # V20+ JSON-formatted director data - parse and join
                        director_list = json.loads(item_data['director'])
                        info['director'] = ', '.join(director_list) if isinstance(director_list, list) else item_data['director']
                    else:
                        # Handle as regular string
                        info['director'] = str(item_data['director'])
                except (json.JSONDecodeError, ValueError):
                    # Fallback for malformed JSON
                    info['director'] = item_data['director']
                
            if item_data.get('studio'):
                info['studio'] = item_data['studio']
                
            if item_data.get('country'):
                info['country'] = item_data['country']
                
            if item_data.get('writer'):
                info['writer'] = item_data['writer']
                
            if item_data.get('imdbnumber'):
                info['imdbnumber'] = item_data['imdbnumber']
                
            if item_data.get('tmdb_id'):
                info['tmdb'] = str(item_data['tmdb_id'])
            
            # Episode-specific fields
            if item_data.get('media_type') == 'episode':
                if item_data.get('tvshowtitle'):
                    info['tvshowtitle'] = item_data['tvshowtitle']
                if item_data.get('season') is not None:
                    info['season'] = str(int(item_data['season']))
                if item_data.get('episode') is not None:
                    info['episode'] = str(int(item_data['episode']))
                if item_data.get('aired'):
                    info['aired'] = item_data['aired']
            
            info['mediatype'] = item_data.get('media_type', 'movie')
            
            list_item.setInfo('video', info)
            self.logger.debug("METADATA: Set comprehensive setInfo metadata for '%s'", title)
            return True
            
        except Exception as e:
            self.logger.error("METADATA: setInfo comprehensive setup failed for '%s': %s", title, e)
            return False

class ListItemPropertyManager:
    """Unified property manager for Kodi ListItems"""
    
    def __init__(self):
        self.logger = logger
    
    def set_standard_properties(self, list_item: xbmcgui.ListItem, 
                              is_playable: bool = False,
                              media_type: Optional[str] = None,
                              db_id: Optional[int] = None,
                              **extra_properties) -> bool:
        """
        Set standard properties that are commonly used across different ListItem types.
        
        Args:
            list_item: The ListItem to set properties on
            is_playable: Whether the item is playable
            media_type: Media type (movie, episode, etc.)
            db_id: Database ID for library items
            **extra_properties: Additional properties to set
            
        Returns:
            bool: True if properties were set successfully
        """
        try:
            # Set IsPlayable property
            list_item.setProperty('IsPlayable', 'true' if is_playable else 'false')
            
            # Set media type properties if provided
            if media_type:
                list_item.setProperty('mediatype', media_type)
                list_item.setProperty('dbtype', media_type)
            
            # Set database ID if provided
            if db_id is not None:
                list_item.setProperty('dbid', str(db_id))
            
            # Set any extra properties
            for key, value in extra_properties.items():
                if value is not None:
                    list_item.setProperty(key, str(value))
            
            self.logger.debug("PROPERTIES: Set standard properties (playable=%s, media_type=%s, db_id=%s)", 
                            is_playable, media_type, db_id)
            return True
            
        except Exception as e:
            self.logger.error("PROPERTIES: Failed to set standard properties: %s", e)
            return False

class ListItemArtManager:
    """Unified art manager for Kodi ListItems"""
    
    def __init__(self, addon_id: str):
        self.addon_id = addon_id
        self.logger = logger
    
    def apply_art(self, list_item: xbmcgui.ListItem, art_dict: Optional[Dict[str, str]] = None, 
                  fallback_icon: str = 'DefaultFolder.png') -> bool:
        """
        Apply artwork to a ListItem with fallback handling.
        
        Args:
            list_item: The ListItem to apply art to
            art_dict: Dictionary of art to apply
            fallback_icon: Fallback icon to use if art fails
            
        Returns:
            bool: True if art was applied successfully
        """
        try:
            if art_dict:
                list_item.setArt(art_dict)
                self.logger.debug("ART: Applied custom art with %d items", len(art_dict))
                return True
            else:
                # Apply fallback art
                return self._apply_fallback_art(list_item, fallback_icon)
                
        except Exception as e:
            self.logger.error("ART: Failed to apply custom art: %s", e)
            return self._apply_fallback_art(list_item, fallback_icon)
    
    def _apply_fallback_art(self, list_item: xbmcgui.ListItem, fallback_icon: str) -> bool:
        """Apply fallback art when custom art fails"""
        try:
            list_item.setArt({
                'icon': fallback_icon,
                'thumb': fallback_icon
            })
            self.logger.debug("ART: Applied fallback art: %s", fallback_icon)
            return True
        except Exception as e:
            self.logger.error("ART: Even fallback art failed: %s", e)
            return False

    def build_art_dict(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Build artwork dictionary from item data with version-specific handling"""
        import json
        import urllib.parse
        import re
        
        art = {}
        
        # Get art data from the art JSON field only
        item_art = item.get('art')
        if item_art:
            # Handle both dict and JSON string formats
            if isinstance(item_art, str):
                try:
                    item_art = json.loads(item_art)
                except (json.JSONDecodeError, ValueError):
                    item_art = {}

            if isinstance(item_art, dict):
                # Check Kodi version once for efficiency
                from lib.utils.kodi_version import get_kodi_major_version
                kodi_major = get_kodi_major_version()
                is_v19 = (kodi_major == 19)
                
                # Copy all art keys from the art dict
                for art_key in ['poster', 'fanart', 'thumb', 'banner', 'landscape',
                               'clearlogo', 'clearart', 'discart', 'icon']:
                    if art_key in item_art and item_art[art_key]:
                        art_value = item_art[art_key]
                        
                        # V19 Fix: Normalize to canonical format for image:// URLs
                        if is_v19 and art_value and art_value.startswith('image://'):
                            try:
                                # Extract inner URL and normalize encoding
                                if len(art_value) > 8:
                                    inner_url = art_value[8:]
                                    inner_content = inner_url.rstrip('/')
                                    
                                    if inner_content:
                                        # Check if already encoded
                                        has_percent = bool(re.search(r'%[0-9A-Fa-f]{2}', inner_content))
                                        has_unescaped = bool(re.search(r'[:/\?#\[\]@!$&\'()*+,;= ]', inner_content))
                                        
                                        if has_percent and not has_unescaped:
                                            normalized_url = f"image://{inner_content}/"
                                        else:
                                            encoded_inner = urllib.parse.quote(inner_content, safe='')
                                            normalized_url = f"image://{encoded_inner}/"
                                        
                                        art_value = normalized_url
                                        
                            except Exception as e:
                                self.logger.error("V19 ART: Failed to normalize %s URL: %s", art_key, e)
                        
                        art[art_key] = art_value

        # If we have poster but no thumb/icon, set them for list view compatibility
        if art.get('poster') and not art.get('thumb'):
            art['thumb'] = art['poster']
        if art.get('poster') and not art.get('icon'):
            art['icon'] = art['poster']

        return art
    
    def apply_type_specific_art(self, list_item: xbmcgui.ListItem, item_type: str, 
                               resource_path_func: Optional[Callable[[str], str]] = None) -> bool:
        """
        Apply type-specific artwork (list, folder, etc.) with resource path support.
        
        Args:
            list_item: The ListItem to apply art to
            item_type: Type of item ('list', 'folder', etc.)
            resource_path_func: Function to get resource paths
            
        Returns:
            bool: True if art was applied successfully
        """
        try:
            art_mapping = {
                'list': {
                    'icon_name': 'list_playlist_icon.png',
                    'thumb_name': 'list_playlist.jpg',
                    'fallback': 'DefaultPlaylist.png'
                },
                'folder': {
                    'icon_name': 'list_folder_icon.png', 
                    'thumb_name': 'list_folder.jpg',
                    'fallback': 'DefaultFolder.png'
                }
            }
            
            if item_type not in art_mapping:
                return self._apply_fallback_art(list_item, 'DefaultFolder.png')
            
            art_config = art_mapping[item_type]
            
            if resource_path_func:
                try:
                    icon = resource_path_func(art_config['icon_name'])
                    thumb = resource_path_func(art_config['thumb_name'])
                    
                    list_item.setArt({
                        'icon': icon,
                        'thumb': thumb
                    })
                    self.logger.debug("ART: Applied resource art for %s type", item_type)
                    return True
                    
                except Exception as e:
                    self.logger.warning("ART: Resource art failed for %s: %s", item_type, e)
                    # Fall through to fallback
            
            # Use fallback art
            return self._apply_fallback_art(list_item, art_config['fallback'])
            
        except Exception as e:
            self.logger.error("ART: Failed to apply type-specific art for %s: %s", item_type, e)
            return self._apply_fallback_art(list_item, 'DefaultFolder.png')

class ContextMenuBuilder:
    """Unified context menu builder for consistent menu creation"""
    
    def __init__(self, addon_id: str):
        self.addon_id = addon_id
        self.logger = logger
    
    def build_context_menu(self, item_id: str, item_type: str, item_name: str = "", 
                          is_protected: bool = False,
                          custom_actions: Optional[List[Tuple[str, str]]] = None) -> List[Tuple[str, str]]:
        """
        Build a context menu for an item.
        
        Args:
            item_id: ID of the item
            item_type: Type of item (list, folder, etc.)
            item_name: Name of the item (for logging/compatibility)
            is_protected: Whether the item is protected from rename/delete operations
            custom_actions: List of (label, action_url) tuples to add
            
        Returns:
            List of (label, action_url) tuples for the context menu
        """
        try:
            context_items = []
            
            # Standard actions based on type
            if item_type == 'list':
                try:
                    from lib.ui.localization import L
                    context_items.extend([
                        (L(31020), f"RunPlugin(plugin://{self.addon_id}/?action=rename_list&list_id={item_id})"),  # "Rename"
                        (L(31021), f"RunPlugin(plugin://{self.addon_id}/?action=delete_list&list_id={item_id})"),  # "Delete"
                        (L(31022), f"RunPlugin(plugin://{self.addon_id}/?action=export_list&list_id={item_id})")   # "Export"
                    ])
                except ImportError:
                    # Fallback if localization not available
                    context_items.extend([
                        ("Rename", f"RunPlugin(plugin://{self.addon_id}/?action=rename_list&list_id={item_id})"),
                        ("Delete", f"RunPlugin(plugin://{self.addon_id}/?action=delete_list&list_id={item_id})"),
                        ("Export", f"RunPlugin(plugin://{self.addon_id}/?action=export_list&list_id={item_id})")
                    ])
                
            elif item_type == 'folder':
                # Don't add rename/delete for protected folders
                if not is_protected:
                    try:
                        from lib.ui.localization import L
                        context_items.extend([
                            (L(31020), f"RunPlugin(plugin://{self.addon_id}/?action=rename_folder&folder_id={item_id})"),  # "Rename"
                            (L(31021), f"RunPlugin(plugin://{self.addon_id}/?action=delete_folder&folder_id={item_id})")   # "Delete"
                        ])
                    except ImportError:
                        # Fallback if localization not available
                        context_items.extend([
                            ("Rename", f"RunPlugin(plugin://{self.addon_id}/?action=rename_folder&folder_id={item_id})"),
                            ("Delete", f"RunPlugin(plugin://{self.addon_id}/?action=delete_folder&folder_id={item_id})")
                        ])
            
            # Add custom actions
            if custom_actions:
                context_items.extend(custom_actions)
            
            self.logger.debug("CONTEXT: Built context menu for %s '%s' with %d items", 
                            item_type, item_id, len(context_items))
            return context_items
            
        except Exception as e:
            self.logger.error("CONTEXT: Failed to build context menu for %s '%s': %s", item_type, item_id, e)
            return []

# Convenience functions for common operations
def create_simple_listitem(title: str, plot: Optional[str] = None, addon_id: str = "", 
                          is_playable: bool = False, icon: Optional[str] = None) -> xbmcgui.ListItem:
    """
    Create a simple ListItem with basic metadata and properties.
    
    Args:
        title: The title for the ListItem
        plot: Optional plot/description
        addon_id: Addon ID for metadata manager
        is_playable: Whether the item should be playable
        icon: Optional icon to set
        
    Returns:
        Configured ListItem
    """
    try:
        list_item = xbmcgui.ListItem(label=title)
        
        # Set metadata
        metadata_manager = ListItemMetadataManager(addon_id)
        metadata_manager.set_basic_metadata(list_item, title, plot, "simple")
        
        # Set properties
        property_manager = ListItemPropertyManager()
        property_manager.set_standard_properties(list_item, is_playable=is_playable)
        
        # Set art if provided
        if icon:
            art_manager = ListItemArtManager(addon_id)
            art_manager.apply_art(list_item, {'icon': icon, 'thumb': icon})
        
        return list_item
        
    except Exception as e:
        logger.error("SIMPLE: Failed to create simple listitem for '%s': %s", title, e)
        # Return basic listitem as fallback
        return xbmcgui.ListItem(label=title)