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

        try:
            self.logger.info(f"=== CREATING LISTITEM FOR: {movie_data.get('title', 'Unknown')} ===")
            self.logger.info(f"Movie data keys available: {sorted(movie_data.keys())}")
            self.logger.info(f"Basic data: title='{movie_data.get('title')}', year={movie_data.get('year')}, kodi_id={movie_data.get('kodi_id')}")
            self.logger.info(f"Artwork data: poster='{movie_data.get('poster', 'MISSING')}', fanart='{movie_data.get('fanart', 'MISSING')}', thumb='{movie_data.get('thumb', 'MISSING')}'")
            
            # Enhanced metadata logging
            plot = movie_data.get('plot', '')
            plotoutline = movie_data.get('plotoutline', '')
            self.logger.info(f"Plot data: plot length={len(plot) if plot else 0}, plotoutline length={len(plotoutline) if plotoutline else 0}")
            self.logger.info(f"Metadata: genre='{movie_data.get('genre', 'MISSING')}', director='{movie_data.get('director', 'MISSING')}'")
            self.logger.info(f"Additional: rating={movie_data.get('rating', 'MISSING')}, runtime={movie_data.get('runtime', 'MISSING')}, mpaa='{movie_data.get('mpaa', 'MISSING')}'")
            self.logger.info(f"Cast/Crew: writer='{movie_data.get('writer', 'MISSING')}', studio='{movie_data.get('studio', 'MISSING')}'")
            
            # UI preferences logging
            self.logger.info(f"UI Settings: density='{self.ui_density}', artwork_pref='{self.artwork_preference}', show_plot={self.show_plot_in_detailed}")

            # Extract basic info
            title = movie_data.get('title', 'Unknown Movie')
            year = movie_data.get('year')
            kodi_id = movie_data.get('kodi_id')

            # Build primary and secondary labels
            primary_label = str(title).strip() if title else 'Unknown Movie'
            secondary_label = str(year) if year and self.show_secondary_label else ""

            # Create ListItem
            list_item = xbmcgui.ListItem(label=primary_label, label2=secondary_label)

            # Set Video InfoLabels based on UI density
            info_labels = self._build_info_labels(movie_data)
            self.logger.info(f"Built info labels: {list(info_labels.keys())}")
            
            # Log the actual plot data being set
            if 'plot' in info_labels:
                plot_preview = info_labels['plot'][:100] + "..." if len(info_labels['plot']) > 100 else info_labels['plot']
                self.logger.info(f"Setting plot: '{plot_preview}'")
            else:
                self.logger.warning("No plot data in info labels!")
                
            list_item.setInfo('video', info_labels)

            # Set artwork based on preferences
            art_dict = self._build_art_dict(movie_data)
            self.logger.debug(f"Setting artwork: {list(art_dict.keys())}")
            list_item.setArt(art_dict)

            # Add playback context menu
            context_menu = self._build_playback_context_menu(movie_data, base_url)
            if context_menu:
                list_item.addContextMenuItems(context_menu)

            # Set additional properties for skin use
            self._set_additional_properties(list_item, movie_data)

            return list_item

        except Exception as e:
            self.logger.error(f"Error creating ListItem for {movie_data.get('title', 'Unknown')}: {e}")
            # Create a minimal fallback ListItem
            fallback_title = movie_data.get('title', 'Unknown Movie')
            fallback_item = xbmcgui.ListItem(label=str(fallback_title))
            fallback_item.setInfo('video', {'title': str(fallback_title)})
            fallback_item.setArt({'thumb': self.fallback_icon})
            return fallback_item

    def _build_info_labels(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Video InfoLabels based on UI density and available metadata"""

        info = {}

        # Core fields (always included) - ensure proper types
        title = movie_data.get('title', 'Unknown Movie')
        if title and str(title).strip():
            info['title'] = str(title).strip()
        else:
            info['title'] = 'Unknown Movie'

        year = movie_data.get('year')
        if year:
            try:
                year_int = int(year)
                if 1800 <= year_int <= 2100:  # Reasonable year range
                    info['year'] = year_int
            except (ValueError, TypeError):
                self.logger.debug(f"Invalid year value: {year}")
                pass

        # Handle plot information - prioritize actual plot data
        plot = movie_data.get('plot', '').strip()
        plotoutline = movie_data.get('plotoutline', '').strip()
        
        # Log what we're working with
        self.logger.debug(f"Plot processing for '{title}': plot='{plot[:50]}...' ({len(plot)} chars), plotoutline='{plotoutline[:50]}...' ({len(plotoutline)} chars)")
        
        if plot and len(plot) > 0:
            # Use full plot if available and non-empty
            info['plot'] = plot
            self.logger.debug(f"Using full plot for '{title}': {len(plot)} characters")
        elif plotoutline and len(plotoutline) > 0:
            # Use plot outline as fallback
            info['plot'] = plotoutline
            self.logger.debug(f"Using plotoutline for '{title}': {len(plotoutline)} characters")
        else:
            # Only create fallback description if NO plot data exists
            self.logger.debug(f"No plot data found for '{title}', creating fallback description")
            description_parts = []
            if year:
                description_parts.append(f"Released: {year}")
            
            # Add genre information if available
            genre = movie_data.get('genre', '').strip()
            if genre:
                # Take first few genres to keep it short
                genres = genre.split(',')[:3] if ',' in genre else [genre]
                description_parts.append(f"Genre: {', '.join([g.strip() for g in genres])}")
            
            # Add director if available
            director = movie_data.get('director', '').strip()
            if director:
                directors = director.split(',')[:2] if ',' in director else [director]
                description_parts.append(f"Director: {', '.join([d.strip() for d in directors])}")
            
            # Add rating if available
            rating = movie_data.get('rating')
            if rating and float(rating) > 0:
                description_parts.append(f"Rating: {float(rating):.1f}/10")
            
            if description_parts:
                info['plot'] = " • ".join(description_parts)
            else:
                info['plot'] = f"Movie from {year}" if year else "No description available"

        # Add extended metadata based on UI density (always include for Kodi items with rich data)
        include_extended_metadata = (
            self.ui_density in ['detailed', 'art_heavy'] or 
            movie_data.get('kodi_id')  # Always include for Kodi library items
        )
        
        if include_extended_metadata:
            # Plot is already handled above, so we can focus on other metadata here
            
            # Additional plot outline for detailed view (if different from main plot)
            plotoutline = movie_data.get('plotoutline', '').strip()
            if plotoutline and plotoutline != info.get('plot', '') and len(plotoutline) < len(info.get('plot', '')):
                info['plotoutline'] = plotoutline

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

            # Genre - ensure it's a valid string or list
            genre = movie_data.get('genre', '')
            if genre:
                try:
                    if isinstance(genre, str) and genre.strip():
                        # Split comma-separated genres
                        genre_list = [g.strip() for g in genre.split(',') if g.strip()]
                        if genre_list:
                            info['genre'] = genre_list
                    elif isinstance(genre, list):
                        # Validate list elements are strings
                        genre_list = [str(g).strip() for g in genre if str(g).strip()]
                        if genre_list:
                            info['genre'] = genre_list
                except Exception as e:
                    self.logger.debug(f"Error processing genre: {e}")
                    pass

            # MPAA rating - ensure it's a valid string
            mpaa = movie_data.get('mpaa', '')
            if mpaa:
                try:
                    mpaa_str = str(mpaa).strip()
                    if mpaa_str:
                        info['mpaa'] = mpaa_str
                except Exception as e:
                    self.logger.debug(f"Error processing MPAA: {e}")
                    pass

            # Director - ensure it's a valid string or list
            director = movie_data.get('director', '')
            if director:
                try:
                    if isinstance(director, str) and director.strip():
                        # Split comma-separated directors
                        director_list = [d.strip() for d in director.split(',') if d.strip()]
                        if director_list:
                            info['director'] = director_list
                    elif isinstance(director, list):
                        # Validate list elements are strings
                        director_list = [str(d).strip() for d in director if str(d).strip()]
                        if director_list:
                            info['director'] = director_list
                except Exception as e:
                    self.logger.debug(f"Error processing director: {e}")
                    pass

            # Studio - keep it simple, just use string
            studio = movie_data.get('studio', '')
            if studio:
                try:
                    studio_str = str(studio).strip()
                    if studio_str and not studio_str.startswith('['):
                        info['studio'] = studio_str
                except Exception as e:
                    self.logger.debug(f"Error processing studio: {e}")
                    pass

            # Country - keep it simple, just use string
            country = movie_data.get('country', '')
            if country:
                try:
                    country_str = str(country).strip()
                    if country_str and not country_str.startswith('['):
                        info['country'] = country_str
                except Exception as e:
                    self.logger.debug(f"Error processing country: {e}")
                    pass

            # Cast - add cast information to help Kodi display cast properly
            cast_list = movie_data.get('cast_list', [])
            cast_string = movie_data.get('cast', '')
            
            if cast_list and isinstance(cast_list, list):
                # Use the full cast structure if available
                try:
                    info['cast'] = cast_list
                    self.logger.debug(f"Set cast list with {len(cast_list)} members for '{title}'")
                except Exception as e:
                    self.logger.debug(f"Error setting cast list: {e}")
                    # Fallback to cast string
                    if cast_string:
                        info['cast'] = cast_string
            elif cast_string:
                # Use cast string as fallback
                try:
                    info['cast'] = cast_string
                    self.logger.debug(f"Set cast string for '{title}': {cast_string[:50]}...")
                except Exception as e:
                    self.logger.debug(f"Error setting cast string: {e}")
                    pass

        # Playback info - ensure it's an integer
        playcount = movie_data.get('playcount', 0)
        if playcount:
            try:
                info['playcount'] = int(playcount)
            except (ValueError, TypeError):
                self.logger.debug(f"Invalid playcount value: {playcount}")
                pass

        # External IDs - ensure they're valid strings
        imdb_id = movie_data.get('imdb_id')
        if imdb_id:
            try:
                imdb_str = str(imdb_id).strip()
                if imdb_str and imdb_str != 'None':
                    info['imdbnumber'] = imdb_str
            except Exception as e:
                self.logger.debug(f"Error processing IMDb ID: {e}")
                pass

        # UniqueID - helps Kodi link to its database
        uniqueid_dict = {}
        if imdb_id:
            try:
                imdb_str = str(imdb_id).strip()
                if imdb_str and imdb_str != 'None':
                    uniqueid_dict['imdb'] = imdb_str
            except Exception as e:
                self.logger.debug(f"Error processing IMDb ID for uniqueid: {e}")
                pass
        
        tmdb_id = movie_data.get('tmdb_id')
        if tmdb_id:
            try:
                tmdb_str = str(tmdb_id).strip()
                if tmdb_str and tmdb_str != 'None':
                    uniqueid_dict['tmdb'] = tmdb_str
            except Exception as e:
                self.logger.debug(f"Error processing TMDb ID for uniqueid: {e}")
                pass
        
        if uniqueid_dict:
            try:
                info['uniqueid'] = uniqueid_dict
                self.logger.debug(f"Set uniqueid for '{title}': {uniqueid_dict}")
            except Exception as e:
                self.logger.debug(f"Error setting uniqueid: {e}")
                pass

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
            
        # Ensure we have at least some artwork for better display
        if not art.get('poster') and art.get('thumb'):
            art['poster'] = art['thumb']
        if not art.get('fanart') and art.get('poster'):
            art['fanart'] = art['poster']

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

        # Set database ID for Kodi auto-population of cast and detailed metadata
        kodi_id = movie_data.get('kodi_id')
        if kodi_id:
            list_item.setProperty('dbid', str(kodi_id))
            # Also set the media type to help Kodi identify this as a movie
            list_item.setProperty('dbtype', 'movie')
            self.logger.info(f"SET DBID PROPERTY: Set dbid={kodi_id} and dbtype='movie' for '{movie_data.get('title', 'Unknown')}'")
        else:
            self.logger.warning(f"NO DBID SET: No kodi_id found for '{movie_data.get('title', 'Unknown')}' - available data keys: {list(movie_data.keys())}")

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