#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - NFO Parser
Parses Kodi NFO files for TV shows, episodes, and movies
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from lib.utils.kodi_log import get_kodi_logger
from lib import xmltodict


class NFOParser:
    """Parses Kodi NFO files and extracts metadata"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.nfo_parser')
    
    def parse_nfo_file(self, nfo_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse an NFO file and return its contents as a dict
        
        Args:
            nfo_path: Path to the NFO file
            
        Returns:
            Dict containing NFO data, or None if parsing fails
        """
        try:
            with open(nfo_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse with force_list for keys that can be 1..n items
            nfo_data = xmltodict.parse(
                content,
                force_list=('genre', 'actor', 'episodedetails', 'director', 'writer', 'studio', 'tag')
            )
            
            return nfo_data
            
        except Exception as e:
            self.logger.error("Failed to parse NFO file %s: %s", nfo_path, e)
            return None
    
    def parse_tvshow_nfo(self, nfo_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a tvshow.nfo file
        
        Returns:
            Dict with TV show metadata including title, plot, premiered, genres, etc.
        """
        nfo_data = self.parse_nfo_file(nfo_path)
        if not nfo_data or 'tvshow' not in nfo_data:
            return None
        
        tvshow = nfo_data['tvshow']
        
        # Extract standard fields
        metadata = {
            'title': self._get_text(tvshow, 'title'),
            'originaltitle': self._get_text(tvshow, 'originaltitle'),
            'plot': self._get_text(tvshow, 'plot'),
            'premiered': self._get_text(tvshow, 'premiered'),
            'year': self._get_int(tvshow, 'year'),
            'genre': self._get_list(tvshow, 'genre'),
            'studio': self._get_list(tvshow, 'studio'),
            'mpaa': self._get_text(tvshow, 'mpaa'),
            'rating': self._get_rating(tvshow),
            'votes': self._get_int(tvshow, 'votes'),
            'uniqueid': self._get_uniqueid(tvshow),
            'art': self._get_art(tvshow),
            'actor': self._get_actors(tvshow)
        }
        
        return metadata
    
    def parse_episode_nfo(self, nfo_path: Path) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
        """
        Parse an episode NFO file
        
        Returns:
            Dict with episode metadata, list of dicts for multi-episode NFOs, or None
        """
        nfo_data = self.parse_nfo_file(nfo_path)
        if not nfo_data:
            return None
        
        # Check for multi-episode NFO
        if 'multiepisodenfo' in nfo_data:
            return self._parse_multiepisode_nfo(nfo_data['multiepisodenfo'])
        elif 'episodedetails' in nfo_data:
            ep_data = nfo_data['episodedetails']
            # force_list wraps single episode in a list, unwrap if single item
            if isinstance(ep_data, list):
                if len(ep_data) == 1:
                    return self._parse_single_episode(ep_data[0])
                else:
                    # Multiple episodes without multiepisodenfo wrapper
                    return [self._parse_single_episode(ep) for ep in ep_data]
            else:
                return self._parse_single_episode(ep_data)
        
        return None
    
    def _parse_multiepisode_nfo(self, multi_data: Dict) -> List[Dict[str, Any]]:
        """Parse multi-episode NFO and return list of episodes"""
        episodes = []
        
        # episodedetails should be a list due to force_list
        episode_list = multi_data.get('episodedetails', [])
        if not isinstance(episode_list, list):
            episode_list = [episode_list]
        
        for ep_data in episode_list:
            episode = self._parse_single_episode(ep_data)
            if episode:
                episodes.append(episode)
        
        return episodes
    
    def _parse_single_episode(self, ep_data: Dict) -> Dict[str, Any]:
        """Parse single episode data"""
        metadata = {
            'title': self._get_text(ep_data, 'title'),
            'showtitle': self._get_text(ep_data, 'showtitle'),
            'season': self._get_int(ep_data, 'season'),
            'episode': self._get_int(ep_data, 'episode'),
            'plot': self._get_text(ep_data, 'plot'),
            'aired': self._get_text(ep_data, 'aired'),
            'year': self._get_int(ep_data, 'year'),
            'rating': self._get_rating(ep_data),
            'votes': self._get_int(ep_data, 'votes'),
            'director': self._get_list(ep_data, 'director'),
            'writer': self._get_list(ep_data, 'writer'),
            'uniqueid': self._get_uniqueid(ep_data),
            'art': self._get_art(ep_data),
            'actor': self._get_actors(ep_data)
        }
        
        return metadata
    
    def parse_movie_nfo(self, nfo_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a movie NFO file
        
        Returns:
            Dict with movie metadata
        """
        nfo_data = self.parse_nfo_file(nfo_path)
        if not nfo_data or 'movie' not in nfo_data:
            return None
        
        movie = nfo_data['movie']
        
        metadata = {
            'title': self._get_text(movie, 'title'),
            'originaltitle': self._get_text(movie, 'originaltitle'),
            'year': self._get_int(movie, 'year'),
            'plot': self._get_text(movie, 'plot'),
            'tagline': self._get_text(movie, 'tagline'),
            'genre': self._get_list(movie, 'genre'),
            'country': self._get_list(movie, 'country'),
            'studio': self._get_list(movie, 'studio'),
            'director': self._get_list(movie, 'director'),
            'writer': self._get_list(movie, 'writer'),
            'mpaa': self._get_text(movie, 'mpaa'),
            'runtime': self._get_int(movie, 'runtime'),
            'rating': self._get_rating(movie),
            'votes': self._get_int(movie, 'votes'),
            'uniqueid': self._get_uniqueid(movie),
            'set': self._get_text(movie, 'set'),
            'art': self._get_art(movie),
            'actor': self._get_actors(movie),
            'dateadded': self._get_text(movie, 'dateadded')
        }
        
        return metadata
    
    def _get_text(self, data: Dict, key: str) -> Optional[str]:
        """Safely get text value from NFO data"""
        value = data.get(key)
        if value is None:
            return None
        if isinstance(value, dict) and '#text' in value:
            return str(value['#text']).strip()
        return str(value).strip() if value else None
    
    def _get_int(self, data: Dict, key: str) -> Optional[int]:
        """Safely get integer value from NFO data"""
        value = self._get_text(data, key)
        if value:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        return None
    
    def _get_list(self, data: Dict, key: str) -> List[str]:
        """Get list of values, handling both single and multiple items"""
        value = data.get(key)
        if not value:
            return []
        
        # Already a list due to force_list
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict) and '#text' in item:
                    result.append(str(item['#text']).strip())
                elif isinstance(item, str):
                    result.append(item.strip())
            return result
        
        # Single value
        if isinstance(value, dict) and '#text' in value:
            return [str(value['#text']).strip()]
        return [str(value).strip()] if value else []
    
    def _get_rating(self, data: Dict) -> Optional[float]:
        """Extract rating value"""
        # Try rating/value structure first
        if 'rating' in data:
            rating_data = data['rating']
            if isinstance(rating_data, dict) and 'value' in rating_data:
                try:
                    return float(rating_data['value'])
                except (ValueError, TypeError):
                    pass
            # Direct rating value
            if isinstance(rating_data, (int, float, str)):
                try:
                    return float(rating_data)
                except (ValueError, TypeError):
                    pass
        
        # Try ratings/rating/value (newer format)
        if 'ratings' in data:
            ratings = data['ratings']
            if isinstance(ratings, dict) and 'rating' in ratings:
                rating_data = ratings['rating']
                if isinstance(rating_data, dict) and 'value' in rating_data:
                    try:
                        return float(rating_data['value'])
                    except (ValueError, TypeError):
                        pass
        
        return None
    
    def _get_uniqueid(self, data: Dict) -> Dict[str, str]:
        """Extract unique IDs (IMDb, TMDb, etc.)"""
        ids = {}
        
        if 'uniqueid' in data:
            uniqueid = data['uniqueid']
            
            # Handle single uniqueid
            if isinstance(uniqueid, dict):
                id_type = uniqueid.get('@type', 'unknown')
                id_value = uniqueid.get('#text') or uniqueid.get('@default')
                if id_value:
                    ids[id_type] = str(id_value).strip()
            
            # Handle list of uniqueids
            elif isinstance(uniqueid, list):
                for uid in uniqueid:
                    if isinstance(uid, dict):
                        id_type = uid.get('@type', 'unknown')
                        id_value = uid.get('#text')
                        if id_value:
                            ids[id_type] = str(id_value).strip()
        
        # Also check for direct imdb/tmdb fields
        if 'imdb' in data or 'id' in data:
            imdb = self._get_text(data, 'imdb') or self._get_text(data, 'id')
            if imdb:
                ids['imdb'] = imdb
        
        if 'tmdbid' in data:
            tmdb = self._get_text(data, 'tmdbid')
            if tmdb:
                ids['tmdb'] = tmdb
        
        return ids
    
    def _get_art(self, data: Dict) -> Dict[str, str]:
        """Extract art URLs from NFO"""
        art = {}
        
        # Direct art fields
        for art_type in ['thumb', 'poster', 'fanart', 'banner', 'clearlogo', 'clearart', 'landscape']:
            value = self._get_text(data, art_type)
            if value:
                art[art_type] = value
        
        return art
    
    def _get_actors(self, data: Dict) -> List[Dict[str, str]]:
        """Extract actor information"""
        actors = []
        
        actor_list = data.get('actor', [])
        if not isinstance(actor_list, list):
            actor_list = [actor_list]
        
        for actor_data in actor_list:
            if isinstance(actor_data, dict):
                actor = {
                    'name': self._get_text(actor_data, 'name'),
                    'role': self._get_text(actor_data, 'role'),
                    'thumb': self._get_text(actor_data, 'thumb')
                }
                if actor['name']:
                    actors.append(actor)
        
        return actors
    
    def parse_episode_from_filename(self, filename: str) -> Optional[Dict[str, int]]:
        """
        Parse season/episode numbers from filename
        
        Supports patterns: SxxEyy, SxEy, 1x02, Season 01/Episode 02
        """
        # Remove extension
        name = Path(filename).stem
        
        # Try SxxEyy or SxEy pattern
        match = re.search(r'[sS](\d+)[eE](\d+)', name)
        if match:
            return {
                'season': int(match.group(1)),
                'episode': int(match.group(2))
            }
        
        # Try 1x02 pattern
        match = re.search(r'(\d+)x(\d+)', name)
        if match:
            return {
                'season': int(match.group(1)),
                'episode': int(match.group(2))
            }
        
        # Try Season XX Episode YY pattern
        match = re.search(r'Season\s+(\d+).*Episode\s+(\d+)', name, re.IGNORECASE)
        if match:
            return {
                'season': int(match.group(1)),
                'episode': int(match.group(2))
            }
        
        return None


def get_nfo_parser() -> NFOParser:
    """Get NFO parser instance"""
    return NFOParser()
