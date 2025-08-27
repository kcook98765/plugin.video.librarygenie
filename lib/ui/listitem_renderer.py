#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 11 ListItem Renderer
Enhanced ListItem creation with artwork, metadata, and playback actions
"""

import xbmcgui
import xbmcplugin

import json
from typing import Dict, Any, Optional, List, List, Callable
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
        list_item = xbmcgui.ListItem(label=primary_label, label2=secondary_label)
        
        # Set Video InfoLabels based on UI density
        info_labels = self._build_info_labels(movie_data)
        list_item.setInfo('video', info_labels)
        
        # Set artwork based on preferences
        art_dict = self._build_art_dict(movie_data)
        list_item.setArt(art_dict)
        
        # Add playback context menu
        context_menu = self._build_playback_context_menu(movie_data, base_url)
        if context_menu:
            list_item.addContextMenuItems(context_menu)
        
        # Set additional properties for skin use
        self._set_additional_properties(list_item, movie_data)
        
        return list_item
    
    def _build_info_labels(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Video InfoLabels based on UI density and available metadata"""
        
        info = {}
        
        # Core fields (always included) - ensure proper types
        info['title'] = str(movie_data.get('title', 'Unknown Movie'))
        year = movie_data.get('year')
        if year:
            try:
                info['year'] = int(year)
            except (ValueError, TypeError):
                self.logger.debug(f"Invalid year value: {year}")
                pass
        
        # Add extended metadata based on UI density
        if self.ui_density in ['detailed', 'art_heavy']:
            # Plot/description - ensure they're strings
            plot = movie_data.get('plot', '')
            plotoutline = movie_data.get('plotoutline', '')
            
            if self.show_plot_in_detailed and plot and isinstance(plot, str):
                info['plot'] = str(plot).strip()
            elif plotoutline and isinstance(plotoutline, str):
                info['plotoutline'] = str(plotoutline).strip()
            
            # Runtime - ensure it's an integer
            runtime = movie_data.get('runtime', 0)
            if runtime:
                try:
                    info['duration'] = int(float(runtime)) * 60  # Kodi expects seconds
                except (ValueError, TypeError):
                    self.logger.debug(f"Invalid runtime value: {runtime}")
                    pass
            
            # Rating - ensure it's a float
            rating = movie_data.get('rating', 0.0)
            if rating:
                try:
                    rating_float = float(rating)
                    if 0.0 <= rating_float <= 10.0:  # Valid rating range
                        info['rating'] = rating_float
                except (ValueError, TypeError):
                    self.logger.debug(f"Invalid rating value: {rating}")
                    pass
            
            # Genre - ensure it's a list of strings
            genre = movie_data.get('genre', '')
            if genre and isinstance(genre, str):
                genre_list = genre.split(', ') if ', ' in genre else [genre]
                # Filter out empty strings
                genre_list = [g.strip() for g in genre_list if g.strip()]
                if genre_list:
                    info['genre'] = genre_list
            
            # MPAA rating - ensure it's a string
            mpaa = movie_data.get('mpaa', '')
            if mpaa and isinstance(mpaa, str):
                info['mpaa'] = str(mpaa).strip()
            
            # Director - ensure it's a list of strings
            director = movie_data.get('director', '')
            if director and isinstance(director, str):
                director_list = director.split(', ') if ', ' in director else [director]
                # Filter out empty strings
                director_list = [d.strip() for d in director_list if d.strip()]
                if director_list:
                    info['director'] = director_list
            
            # Studio/country - ensure these are simple strings or string lists
            try:
                studio = movie_data.get('studio', '')
                if isinstance(studio, str) and studio:
                    if studio.startswith('['):
                        # Try to parse JSON array
                        studio_list = json.loads(studio)
                        if isinstance(studio_list, list) and all(isinstance(s, str) for s in studio_list):
                            info['studio'] = studio_list
                        else:
                            info['studio'] = [str(studio)]
                    else:
                        # Simple string, split on comma if needed
                        info['studio'] = studio.split(', ') if ', ' in studio else [studio]
                elif isinstance(studio, list) and all(isinstance(s, str) for s in studio):
                    info['studio'] = studio
            except Exception as e:
                self.logger.debug(f"Error parsing studio: {e}")
                pass
            
            try:
                country = movie_data.get('country', '')
                if isinstance(country, str) and country:
                    if country.startswith('['):
                        # Try to parse JSON array
                        country_list = json.loads(country)
                        if isinstance(country_list, list) and all(isinstance(c, str) for c in country_list):
                            info['country'] = country_list
                        else:
                            info['country'] = [str(country)]
                    else:
                        # Simple string, split on comma if needed
                        info['country'] = country.split(', ') if ', ' in country else [country]
                elif isinstance(country, list) and all(isinstance(c, str) for c in country):
                    info['country'] = country
            except Exception as e:
                self.logger.debug(f"Error parsing country: {e}")
                pass
        
        # Playback info - ensure it's an integer
        playcount = movie_data.get('playcount', 0)
        if playcount:
            try:
                info['playcount'] = int(playcount)
            except (ValueError, TypeError):
                self.logger.debug(f"Invalid playcount value: {playcount}")
                pass
        
        # External IDs - ensure they're strings
        imdb_id = movie_data.get('imdb_id')
        if imdb_id and isinstance(imdb_id, str):
            info['imdbnumber'] = str(imdb_id).strip()
        
        # Unique IDs for better matching - ensure they're strings
        unique_ids = {}
        if imdb_id and isinstance(imdb_id, str):
            unique_ids['imdb'] = str(imdb_id).strip()
        
        tmdb_id = movie_data.get('tmdb_id')
        if tmdb_id and str(tmdb_id).strip():
            unique_ids['tmdb'] = str(tmdb_id).strip()
            
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
        
        list_item = xbmcgui.ListItem(label=title)
        list_item.setInfo('video', {'plot': description})
        
        # Set fallback artwork for consistency
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