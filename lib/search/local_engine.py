
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Local Search Engine
JSON-RPC based search for local Kodi library content
"""

import json
from typing import List, Dict, Any, Optional

import xbmc

from ..utils.logger import get_logger
from ..config import get_config


class LocalSearchEngine:
    """Search engine for local Kodi library content"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()
    
    def search(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search local library for movies and episodes"""
        if not query or not query.strip():
            return []
        
        query_lower = query.strip().lower()
        results = []
        
        try:
            # Search movies first
            movie_results = self._search_movies(query_lower, limit)
            results.extend(movie_results)
            
            # If we haven't hit the limit, search episodes
            remaining_limit = limit - len(results)
            if remaining_limit > 0:
                episode_results = self._search_episodes(query_lower, remaining_limit)
                results.extend(episode_results)
            
            self.logger.debug(f"Local search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            self.logger.error(f"Error in local search: {e}")
            return []
    
    def _search_movies(self, query_lower: str, limit: int) -> List[Dict[str, Any]]:
        """Search movies in local library"""
        try:
            movies_data = self._json_rpc("VideoLibrary.GetMovies", {
                "properties": [
                    "title", "year", "file", "art", "plot", "rating",
                    "genre", "director", "runtime", "mpaa", "imdbnumber"
                ]
            })
            
            results = []
            movies = movies_data.get('movies', [])
            
            for movie in movies:
                title = movie.get('title', '').lower()
                if query_lower in title:
                    result = self._format_movie_result(movie)
                    results.append(result)
                    
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching movies: {e}")
            return []
    
    def _search_episodes(self, query_lower: str, limit: int) -> List[Dict[str, Any]]:
        """Search episodes in local library"""
        try:
            episodes_data = self._json_rpc("VideoLibrary.GetEpisodes", {
                "properties": [
                    "title", "showtitle", "season", "episode", "file", "art",
                    "plot", "rating", "runtime", "firstaired"
                ]
            })
            
            results = []
            episodes = episodes_data.get('episodes', [])
            
            for episode in episodes:
                title = episode.get('title', '').lower()
                show_title = episode.get('showtitle', '').lower()
                
                # Match either episode title or show title
                if query_lower in title or query_lower in show_title:
                    result = self._format_episode_result(episode)
                    results.append(result)
                    
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching episodes: {e}")
            return []
    
    def _format_movie_result(self, movie: Dict[str, Any]) -> Dict[str, Any]:
        """Format movie data for search results"""
        title = movie.get('title', 'Unknown Movie')
        year = movie.get('year', '')
        
        # Create display label
        if year:
            label = f"{title} ({year})"
        else:
            label = title
        
        return {
            'label': label,
            'path': movie.get('file', ''),
            'art': movie.get('art', {}),
            'type': 'movie',
            'title': title,
            'year': year,
            'plot': movie.get('plot', ''),
            'rating': movie.get('rating', 0.0),
            'genre': movie.get('genre', []),
            'director': movie.get('director', []),
            'runtime': movie.get('runtime', 0),
            'mpaa': movie.get('mpaa', ''),
            'imdbnumber': movie.get('imdbnumber', ''),
            'movieid': movie.get('movieid')
        }
    
    def _format_episode_result(self, episode: Dict[str, Any]) -> Dict[str, Any]:
        """Format episode data for search results"""
        title = episode.get('title', 'Unknown Episode')
        show_title = episode.get('showtitle', 'Unknown Show')
        season = episode.get('season', 0)
        episode_num = episode.get('episode', 0)
        
        # Create display label
        label = f"{show_title} - S{season:02d}E{episode_num:02d} - {title}"
        
        return {
            'label': label,
            'path': episode.get('file', ''),
            'art': episode.get('art', {}),
            'type': 'episode',
            'title': title,
            'showtitle': show_title,
            'season': season,
            'episode': episode_num,
            'plot': episode.get('plot', ''),
            'rating': episode.get('rating', 0.0),
            'runtime': episode.get('runtime', 0),
            'firstaired': episode.get('firstaired', ''),
            'episodeid': episode.get('episodeid')
        }
    
    def _json_rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute JSON-RPC call to Kodi"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        try:
            raw_response = xbmc.executeJSONRPC(json.dumps(payload))
            response = json.loads(raw_response)
            
            if 'error' in response:
                error = response['error']
                self.logger.error(f"JSON-RPC error in {method}: {error}")
                return {}
            
            return response.get('result', {})
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON-RPC response for {method}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"JSON-RPC call failed for {method}: {e}")
            return {}


# Convenience function for simple searches
def search_local(query: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Simple search function for backward compatibility"""
    engine = LocalSearchEngine()
    return engine.search(query, limit)
