#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 12 Remote Mapper  
Maps remote search results to local library items
"""

from typing import Dict, Any, Optional, List
import re

from ..utils.kodi_log import get_kodi_logger
from ..data.connection_manager import get_connection_manager


class RemoteMapper:
    """Maps remote items to local library using various strategies"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.remote.mapper')
        self.conn_manager = get_connection_manager()
    
    def map_to_local(self, remote_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a remote item to local library entry using this priority:
        1. Unique ID match (IMDb/TMDb)
        2. Title + year exact match
        3. Title + file path heuristic (if paths stored consistently)
        
        Returns local item data if found, None if not mapped
        """
        
        # Strategy 1: Unique ID matching (highest confidence)
        local_item = self._map_by_unique_id(remote_item)
        if local_item:
            self.logger.debug("Mapped '%s' by unique ID", remote_item.get('title'))
            return local_item
        
        # Strategy 2: Title + year exact match  
        local_item = self._map_by_title_year(remote_item)
        if local_item:
            self.logger.debug("Mapped '%s' by title+year", remote_item.get('title'))
            return local_item
        
        # Strategy 3: Title + file path heuristic (if available)
        local_item = self._map_by_title_path(remote_item)
        if local_item:
            self.logger.debug("Mapped '%s' by title+path", remote_item.get('title'))
            return local_item
        
        # No mapping found
        self.logger.debug("No local mapping found for '%s'", remote_item.get('title'))
        return None
    
    def _map_by_unique_id(self, remote_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map using IMDb/TMDb unique IDs"""
        try:
            # Check for IMDb ID
            imdb_id = self._extract_imdb_id(remote_item)
            if imdb_id:
                result = self.conn_manager.execute_single("""
                    SELECT kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                           poster, fanart, plot, rating, genre, director, duration as runtime
                    FROM media_items 
                    WHERE imdbnumber = ? AND media_type = 'movie' AND is_removed = 0
                """, [imdb_id])
                
                if result:
                    return dict(result)
            
            # Check for TMDb ID
            tmdb_id = self._extract_tmdb_id(remote_item)
            if tmdb_id:
                result = self.conn_manager.execute_single("""
                    SELECT kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                           poster, fanart, plot, rating, genre, director, duration as runtime
                    FROM media_items 
                    WHERE tmdb_id = ? AND media_type = 'movie' AND is_removed = 0
                """, [tmdb_id])
                
                if result:
                    return dict(result)
            
            return None
            
        except Exception as e:
            self.logger.error("Error in unique ID mapping: %s", e)
            return None
    
    def _map_by_title_year(self, remote_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map using exact title and year match"""
        try:
            title = remote_item.get('title', '').strip()
            year = remote_item.get('year')
            
            if not title:
                return None
            
            # Try exact match with year
            if year:
                result = self.conn_manager.execute_single("""
                    SELECT kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                           poster, fanart, plot, rating, genre, director, duration as runtime
                    FROM media_items 
                    WHERE LOWER(title) = LOWER(?) AND year = ? AND media_type = 'movie' AND is_removed = 0
                """, [title, year])
                
                if result:
                    return dict(result)
            
            # Try exact match without year
            result = self.conn_manager.execute_single("""
                SELECT kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                       poster, fanart, plot, rating, genre, director, duration as runtime
                FROM media_items 
                WHERE LOWER(title) = LOWER(?) AND media_type = 'movie' AND is_removed = 0
                ORDER BY year DESC
                LIMIT 1
            """, [title])
            
            if result:
                return dict(result)
            
            return None
            
        except Exception as e:
            self.logger.error("Error in title+year mapping: %s", e)
            return None
    
    def _map_by_title_path(self, remote_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map using title and file path heuristics"""
        try:
            title = remote_item.get('title', '').strip()
            
            if not title:
                return None
            
            # Clean title for path matching
            clean_title = self._clean_title_for_path(title)
            
            # Search for files that might contain this title
            result = self.conn_manager.execute_single("""
                SELECT kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                       poster, fanart, plot, rating, genre, director, duration as runtime
                FROM media_items 
                WHERE LOWER(play) LIKE LOWER(?) AND media_type = 'movie' AND is_removed = 0
                ORDER BY LENGTH(play) ASC
                LIMIT 1
            """, [f'%{clean_title}%'])
            
            if result:
                return dict(result)
            
            return None
            
        except Exception as e:
            self.logger.error("Error in title+path mapping: %s", e)
            return None
    
    def _extract_imdb_id(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract IMDb ID from various possible fields"""
        # Check direct fields
        imdb_id = item.get('imdb_id') or item.get('imdb') or item.get('imdbid')
        if imdb_id and isinstance(imdb_id, str):
            # Ensure proper format
            if imdb_id.startswith('tt'):
                return imdb_id
            elif imdb_id.isdigit():
                return f'tt{imdb_id}'
        
        # Check in unique IDs object
        unique_ids = item.get('unique_ids', {}) or item.get('uniqueid', {})
        if isinstance(unique_ids, dict):
            imdb_id = unique_ids.get('imdb') or unique_ids.get('imdbid')
            if imdb_id:
                return imdb_id if imdb_id.startswith('tt') else f'tt{imdb_id}'
        
        # Check external IDs
        external_ids = item.get('external_ids', {})
        if isinstance(external_ids, dict):
            imdb_id = external_ids.get('imdb_id')
            if imdb_id:
                return imdb_id if imdb_id.startswith('tt') else f'tt{imdb_id}'
        
        return None
    
    def _extract_tmdb_id(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract TMDb ID from various possible fields"""
        # Check direct fields
        tmdb_id = item.get('tmdb_id') or item.get('tmdb') or item.get('tmdbid')
        if tmdb_id:
            return str(tmdb_id)
        
        # Check in unique IDs object
        unique_ids = item.get('unique_ids', {}) or item.get('uniqueid', {})
        if isinstance(unique_ids, dict):
            tmdb_id = unique_ids.get('tmdb') or unique_ids.get('tmdbid')
            if tmdb_id:
                return str(tmdb_id)
        
        # Check external IDs
        external_ids = item.get('external_ids', {})
        if isinstance(external_ids, dict):
            tmdb_id = external_ids.get('tmdb_id')
            if tmdb_id:
                return str(tmdb_id)
        
        return None
    
    def _clean_title_for_path(self, title: str) -> str:
        """Clean title for file path matching"""
        # Remove common punctuation and special characters
        clean = re.sub(r'[^\w\s]', '', title)
        
        # Remove common words that might not be in filenames
        remove_words = ['the', 'a', 'an', 'and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for', 'with']
        words = clean.lower().split()
        words = [w for w in words if w not in remove_words]
        
        # Take first few significant words
        significant_words = words[:3] if len(words) > 3 else words
        
        return ' '.join(significant_words) if significant_words else title
    
    def bulk_map_results(self, remote_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map multiple remote items efficiently"""
        mapped_results = []
        
        for item in remote_items:
            mapped = self.map_to_local(item)
            if mapped:
                # Combine remote and local data
                enhanced_item = {**item}
                enhanced_item.update(mapped)
                enhanced_item['_mapped'] = True
                mapped_results.append(enhanced_item)
            else:
                # Mark as unmapped
                item['_mapped'] = False
                mapped_results.append(item)
        
        return mapped_results


def get_remote_mapper():
    """Get global remote mapper instance"""
    return RemoteMapper()