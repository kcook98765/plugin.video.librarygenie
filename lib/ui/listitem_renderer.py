#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 11 ListItem Renderer
Enhanced ListItem creation with artwork, metadata, and playback actions
"""

import xbmcgui
import xbmcplugin

import json
from typing import Dict, Any, Optional, List, Callable
from urllib.parse import urlencode

from ..config import get_config
from ..utils.logger import get_logger


class ListItemRenderer:
    """Renders ListItems with Phase 11 artwork, metadata, and playback actions"""
    
    def __init__(self, string_getter: Optional[Callable[[int], str]] = None):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self._get_string = string_getter or self._fallback_string_getter
        
        # Load UI preferences
        self._load_ui_preferences()
    
    def _load_ui_preferences(self):
        """Load UI preferences from database or config"""
        try:
            # Try to get from database first, fallback to config
            from ..data import get_connection_manager
            conn_manager = get_connection_manager()
            
            prefs = conn_manager.execute_single(
                "SELECT ui_density, artwork_preference, show_secondary_label, show_plot_in_detailed, fallback_icon FROM ui_preferences WHERE id = 1"
            )
            
            if prefs:
                self.ui_density = prefs['ui_density']
                self.artwork_preference = prefs['artwork_preference'] 
                self.show_secondary_label = bool(prefs['show_secondary_label'])
                self.show_plot_in_detailed = bool(prefs['show_plot_in_detailed'])
                self.fallback_icon = prefs['fallback_icon'] or 'DefaultVideo.png'
            else:
                self._load_default_preferences()
                
        except Exception as e:
            self.logger.debug(f"Failed to load UI preferences from database: {e}")
            self._load_default_preferences()
    
    def _load_default_preferences(self):
        """Load default UI preferences"""
        self.ui_density = self.config.get('ui_density', 'compact')
        self.artwork_preference = self.config.get('artwork_preference', 'poster')
        self.show_secondary_label = self.config.get('show_secondary_label', True)
        self.show_plot_in_detailed = self.config.get('show_plot_in_detailed', True)
        self.fallback_icon = 'DefaultVideo.png'
    
    def create_movie_listitem(self, movie_data: Dict[str, Any], base_url: str, action: str = "play_movie") -> 'xbmcgui.ListItem':
        """Create a rich ListItem for a movie with artwork and metadata"""
        
        # Extract basic info
        title = movie_data.get('title', 'Unknown Movie')
        year = movie_data.get('year')
        kodi_id = movie_data.get('kodi_id')
        
        # Build primary and secondary labels
        primary_label = title
        secondary_label = str(year) if year and self.show_secondary_label else ""
        
        # Create ListItem
        if KODI_AVAILABLE:
            list_item = xbmcgui.ListItem(label=primary_label, label2=secondary_label)
        else:
            # Stub mode
            list_item = type('MockListItem', (), {
                'setInfo': lambda *args: None,
                'setArt': lambda *args: None,
                'addContextMenuItems': lambda *args: None,
                'setProperty': lambda *args: None
            })()
        
        # Set Video InfoLabels based on UI density
        info_labels = self._build_info_labels(movie_data)
        if KODI_AVAILABLE:
            list_item.setInfo('video', info_labels)
        
        # Set artwork based on preferences
        art_dict = self._build_art_dict(movie_data)
        if KODI_AVAILABLE:
            list_item.setArt(art_dict)
        
        # Add playback context menu
        context_menu = self._build_playback_context_menu(movie_data, base_url)
        if context_menu and KODI_AVAILABLE:
            list_item.addContextMenuItems(context_menu)
        
        # Set additional properties for skin use
        self._set_additional_properties(list_item, movie_data)
        
        return list_item
    
    def _build_info_labels(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Video InfoLabels based on UI density and available metadata"""
        
        info = {}
        
        # Core fields (always included)
        info['title'] = movie_data.get('title', 'Unknown Movie')
        if movie_data.get('year'):
            info['year'] = movie_data['year']
        
        # Add extended metadata based on UI density
        if self.ui_density in ['detailed', 'art_heavy']:
            # Plot/description
            plot = movie_data.get('plot', '')
            plotoutline = movie_data.get('plotoutline', '')
            
            if self.show_plot_in_detailed and plot:
                info['plot'] = plot
            elif plotoutline:
                info['plotoutline'] = plotoutline
            
            # Runtime
            runtime = movie_data.get('runtime', 0)
            if runtime:
                info['duration'] = runtime * 60  # Kodi expects seconds
            
            # Rating
            rating = movie_data.get('rating', 0.0)
            if rating:
                info['rating'] = float(rating)
            
            # Genre
            genre = movie_data.get('genre', '')
            if genre:
                info['genre'] = genre.split(', ') if ',' in genre else [genre]
            
            # MPAA rating
            mpaa = movie_data.get('mpaa', '')
            if mpaa:
                info['mpaa'] = mpaa
            
            # Director
            director = movie_data.get('director', '')
            if director:
                info['director'] = director.split(', ') if ',' in director else [director]
            
            # Studio/country
            try:
                studio = movie_data.get('studio', [])
                if isinstance(studio, str):
                    studio = json.loads(studio) if studio.startswith('[') else [studio]
                if studio:
                    info['studio'] = studio
            except:
                pass
            
            try:
                country = movie_data.get('country', [])
                if isinstance(country, str):
                    country = json.loads(country) if country.startswith('[') else [country]
                if country:
                    info['country'] = country
            except:
                pass
        
        # Playback info
        playcount = movie_data.get('playcount', 0)
        if playcount:
            info['playcount'] = playcount
        
        # External IDs
        if movie_data.get('imdb_id'):
            info['imdbnumber'] = movie_data['imdb_id']
        
        # Unique IDs for better matching
        unique_ids = {}
        if movie_data.get('imdb_id'):
            unique_ids['imdb'] = movie_data['imdb_id']
        if movie_data.get('tmdb_id'):
            unique_ids['tmdb'] = movie_data['tmdb_id']
        if unique_ids:
            info['uniqueid'] = unique_ids
        
        return info
    
    def _build_art_dict(self, movie_data: Dict[str, Any]) -> Dict[str, str]:
        """Build artwork dictionary based on preferences and available art"""
        
        art = {}
        
        # Get artwork URLs
        poster = movie_data.get('poster', '')
        fanart = movie_data.get('fanart', '')
        thumb = movie_data.get('thumb', '')
        
        # Set primary artwork based on preference
        if self.artwork_preference == 'poster' and poster:
            art['thumb'] = poster
            art['poster'] = poster
        elif self.artwork_preference == 'fanart' and fanart:
            art['thumb'] = fanart
            art['fanart'] = fanart
        
        # Always try to set both if available
        if poster:
            art['poster'] = poster
            if not art.get('thumb'):
                art['thumb'] = poster
        
        if fanart:
            art['fanart'] = fanart
            if not art.get('thumb'):
                art['thumb'] = fanart
        
        # Fallback to default icon if no artwork
        if not art.get('thumb'):
            art['thumb'] = self.fallback_icon
        
        # Additional art types for high-density UI
        if self.ui_density == 'art_heavy':
            if poster:
                art['clearlogo'] = poster  # Some skins use clearlogo
            if fanart:
                art['landscape'] = fanart
        
        return art
    
    def _build_playback_context_menu(self, movie_data: Dict[str, Any], base_url: str) -> List[tuple]:
        """Build context menu with playback actions"""
        
        kodi_id = movie_data.get('kodi_id')
        if not kodi_id:
            return []
        
        context_menu = []
        
        # Play action
        play_url = f"{base_url}?{urlencode({'action': 'play_movie', 'kodi_id': kodi_id})}"
        context_menu.append((self._get_string(35001), f"RunPlugin({play_url})"))  # "Play"
        
        # Resume action (if resume point exists)
        resume_time = movie_data.get('resume_time', 0)
        if resume_time > 0:
            resume_url = f"{base_url}?{urlencode({'action': 'resume_movie', 'kodi_id': kodi_id})}"
            context_menu.append((self._get_string(35002), f"RunPlugin({resume_url})"))  # "Resume"
        
        # Queue action
        queue_url = f"{base_url}?{urlencode({'action': 'queue_movie', 'kodi_id': kodi_id})}"
        context_menu.append((self._get_string(35003), f"RunPlugin({queue_url})"))  # "Add to Queue"
        
        # Show Info action
        info_url = f"{base_url}?{urlencode({'action': 'show_info', 'kodi_id': kodi_id})}"
        context_menu.append((self._get_string(35004), f"RunPlugin({info_url})"))  # "Movie Information"
        
        return context_menu
    
    def _set_additional_properties(self, list_item: Any, movie_data: Dict[str, Any]):
        """Set additional properties for skin/plugin use"""
        
        if not KODI_AVAILABLE:
            return
        
        # Set resume time as property for skins that support it
        resume_time = movie_data.get('resume_time', 0)
        if resume_time > 0:
            list_item.setProperty('ResumeTime', str(resume_time))
            list_item.setProperty('TotalTime', str(movie_data.get('runtime', 0) * 60))
            
            # Calculate percentage for progress indicators
            total_time = movie_data.get('runtime', 0) * 60
            if total_time > 0:
                progress = (resume_time / total_time) * 100
                list_item.setProperty('PercentPlayed', str(int(progress)))
        
        # Set movie IDs as properties
        if movie_data.get('imdb_id'):
            list_item.setProperty('IMDbID', movie_data['imdb_id'])
        if movie_data.get('tmdb_id'):
            list_item.setProperty('TMDbID', movie_data['tmdb_id'])
        
        # Set UI density for skin adaptation
        list_item.setProperty('ListItemDensity', self.ui_density)
        list_item.setProperty('ArtworkPreference', self.artwork_preference)
    
    def create_simple_listitem(self, title: str, description: str = "", action: str = "", **kwargs) -> 'xbmcgui.ListItem':
        """Create a simple ListItem for non-movie items (menus, actions, etc.)"""
        
        if KODI_AVAILABLE:
            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo('video', {'plot': description})
        else:
            # Stub mode
            list_item = type('MockListItem', (), {
                'setInfo': lambda *args: None,
                'setArt': lambda *args: None,
                'addContextMenuItems': lambda *args: None
            })()
        
        # Set fallback artwork for consistency
        if KODI_AVAILABLE:
            icon = kwargs.get('icon', self.fallback_icon)
            list_item.setArt({'thumb': icon})
        
        return list_item
    
    def update_preferences(self, **preferences):
        """Update UI preferences and save to database"""
        
        if 'ui_density' in preferences:
            self.ui_density = preferences['ui_density']
        if 'artwork_preference' in preferences:
            self.artwork_preference = preferences['artwork_preference']
        if 'show_secondary_label' in preferences:
            self.show_secondary_label = preferences['show_secondary_label']
        if 'show_plot_in_detailed' in preferences:
            self.show_plot_in_detailed = preferences['show_plot_in_detailed']
        
        # Save to database
        try:
            from ..data import get_connection_manager
            conn_manager = get_connection_manager()
            
            with conn_manager.transaction() as conn:
                conn.execute("""
                    UPDATE ui_preferences 
                    SET ui_density = ?, artwork_preference = ?, show_secondary_label = ?, 
                        show_plot_in_detailed = ?, updated_at = datetime('now')
                    WHERE id = 1
                """, [
                    self.ui_density, self.artwork_preference, 
                    int(self.show_secondary_label), int(self.show_plot_in_detailed)
                ])
            
            self.logger.info(f"Updated UI preferences: density={self.ui_density}, artwork={self.artwork_preference}")
            
        except Exception as e:
            self.logger.error(f"Failed to save UI preferences: {e}")
    
    def _fallback_string_getter(self, string_id: int) -> str:
        """Fallback string getter for testing"""
        fallback_strings = {
            35001: "Play",
            35002: "Resume", 
            35003: "Add to Queue",
            35004: "Movie Information",
            35005: "Play from Beginning",
            35006: "Show Details"
        }
        return fallback_strings.get(string_id, f"String {string_id}")


# Global renderer instance
_renderer_instance = None


def get_listitem_renderer(string_getter: Optional[Callable[[int], str]] = None):
    """Get global ListItem renderer instance"""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = ListItemRenderer(string_getter)
    return _renderer_instance


def refresh_renderer_preferences():
    """Refresh renderer preferences from database"""
    global _renderer_instance
    if _renderer_instance:
        _renderer_instance._load_ui_preferences()