#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Local Search Engine
Database-backed search for the local library index
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional

import xbmc

from ..utils.logger import get_logger
from ..config import get_config


class LocalSearchEngine:
    """Search engine for local Kodi library content"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()

    def search(self, query: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Search local library for movies and episodes

        Returns:
            dict: {'items': [...], 'total': int, 'used_remote': False}
        """
        self.logger.info(f"LocalSearchEngine.search() called with query='{query}', limit={limit}, offset={offset}")
        
        if not query or not query.strip():
            self.logger.info("Empty query provided, returning empty results")
            return {'items': [], 'total': 0, 'used_remote': False}

        query_lower = query.strip().lower()
        self.logger.debug(f"Normalized query: '{query_lower}'")
        results = []

        try:
            # Search movies first
            self.logger.debug("Starting movie search")
            movie_results = self._search_movies(query_lower, limit)
            self.logger.info(f"Movie search returned {len(movie_results)} results")
            results.extend(movie_results)

            # If we haven't hit the limit, search episodes
            remaining_limit = limit - len(results)
            if remaining_limit > 0:
                self.logger.debug(f"Starting episode search with remaining limit: {remaining_limit}")
                episode_results = self._search_episodes(query_lower, remaining_limit)
                self.logger.info(f"Episode search returned {len(episode_results)} results")
                results.extend(episode_results)
            else:
                self.logger.debug("Skipping episode search - movie results filled the limit")

            # Apply offset and limit
            self.logger.debug(f"Applying pagination: offset={offset}, limit={limit}")
            paginated_results = results[offset:offset + limit] if offset > 0 else results[:limit]

            final_result = {
                'items': paginated_results,
                'total': len(results),
                'used_remote': False
            }

            self.logger.info(f"Local search for '{query}' completed: {len(paginated_results)} paginated results, {len(results)} total matches")
            return final_result

        except Exception as e:
            import traceback
            self.logger.error(f"Error in local search: {e}")
            self.logger.error(f"Local search traceback: {traceback.format_exc()}")
            return {'items': [], 'total': 0, 'used_remote': False}

    def _search_movies(self, query_lower: str, limit: int) -> List[Dict[str, Any]]:
        """Search movies in local library using JSON-RPC"""
        self.logger.debug(f"Searching movies for query: '{query_lower}' with limit: {limit}")
        
        try:
            # Use JSON-RPC filter for basic search, fallback to client-side if needed
            self.logger.debug("Making JSON-RPC call to VideoLibrary.GetMovies")
            movies_data = self._json_rpc("VideoLibrary.GetMovies", {
                "properties": [
                    "title", "year", "file", "art", "plot", "rating",
                    "genre", "director", "runtime", "mpaa", "imdbnumber",
                    "uniqueid", "dateadded"
                ],
                "limits": {"start": 0, "end": limit * 2}  # Get more for client-side filtering
            })

            if not movies_data:
                self.logger.warning("JSON-RPC call returned empty/None data")
                return []

            movies = movies_data.get('movies', [])
            self.logger.info(f"JSON-RPC returned {len(movies)} movies from library")

            if not movies:
                self.logger.info("No movies found in library")
                return []
            
            # Log a few sample movie titles for debugging
            self.logger.debug("Sample movie titles from library:")
            for i, movie in enumerate(movies[:10]):
                title = movie.get('title', 'Unknown')
                self.logger.debug(f"  {i+1}: '{title}'")

            results = []
            matches_found = 0

            self.logger.info(f"Starting title matching for query: '{query_lower}'")
            
            for i, movie in enumerate(movies):
                title = movie.get('title', '').lower()
                original_title = movie.get('title', 'Unknown')
                
                # Log first few movies for debugging
                if i < 5:
                    self.logger.debug(f"Checking movie {i+1}: '{original_title}' -> normalized: '{title}'")
                
                # Client-side fallback filter
                if query_lower in title:
                    matches_found += 1
                    result = self._format_movie_result(movie)
                    results.append(result)
                    self.logger.info(f"Match {matches_found}: '{original_title}' contains '{query_lower}'")

                    if len(results) >= limit:
                        self.logger.debug(f"Reached limit of {limit} results")
                        break
                else:
                    # Log first few non-matches for debugging
                    if i < 10 and ('witch' in title or 'blair' in title):
                        self.logger.debug(f"Non-match: '{original_title}' ('{title}') does not contain '{query_lower}'")

            self.logger.info(f"Title matching completed: {matches_found} matches found out of {len(movies)} movies checked")

            self.logger.info(f"Movie search completed: {len(results)} matches out of {len(movies)} total movies")
            return results

        except Exception as e:
            import traceback
            self.logger.error(f"Error searching movies: {e}")
            self.logger.error(f"Movie search traceback: {traceback.format_exc()}")
            return []

    def _search_episodes(self, query_lower: str, limit: int) -> List[Dict[str, Any]]:
        """Search episodes in local library using JSON-RPC"""
        try:
            episodes_data = self._json_rpc("VideoLibrary.GetEpisodes", {
                "properties": [
                    "title", "showtitle", "season", "episode", "file", "art",
                    "plot", "rating", "runtime", "firstaired", "tvshowid"
                ],
                "limits": {"start": 0, "end": limit * 2}  # Get more for client-side filtering
            })

            results = []
            episodes = episodes_data.get('episodes', [])

            for episode in episodes:
                title = episode.get('title', '').lower()
                show_title = episode.get('showtitle', '').lower()

                # Client-side fallback filter - match either episode title or show title
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
        """Format movie data to uniform item dict"""
        title = movie.get('title', 'Unknown Movie')
        year = movie.get('year', '')

        # Create display label
        if year:
            label = f"{title} ({year})"
        else:
            label = title

        # Extract IDs
        imdb_id = movie.get('imdbnumber', '')
        tmdb_id = ''
        if 'uniqueid' in movie and isinstance(movie['uniqueid'], dict):
            imdb_id = movie['uniqueid'].get('imdb', imdb_id)
            tmdb_id = movie['uniqueid'].get('tmdb', '')

        return {
            'label': label,
            'path': movie.get('file', ''),
            'art': movie.get('art', {}),
            'type': 'movie',
            'ids': {
                'imdb': imdb_id,
                'tmdb': tmdb_id,
                'kodi_id': movie.get('movieid')
            },
            # Additional metadata for compatibility
            'title': title,
            'year': year,
            'plot': movie.get('plot', ''),
            'rating': movie.get('rating', 0.0),
            'genre': movie.get('genre', []),
            'director': movie.get('director', []),
            'runtime': movie.get('runtime', 0),
            'mpaa': movie.get('mpaa', '')
        }

    def _format_episode_result(self, episode: Dict[str, Any]) -> Dict[str, Any]:
        """Format episode data to uniform item dict"""
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
            'ids': {
                'tvshow_id': episode.get('tvshowid'),
                'kodi_id': episode.get('episodeid')
            },
            # Additional metadata for compatibility
            'title': title,
            'showtitle': show_title,
            'season': season,
            'episode': episode_num,
            'plot': episode.get('plot', ''),
            'rating': episode.get('rating', 0.0),
            'runtime': episode.get('runtime', 0),
            'firstaired': episode.get('firstaired', '')
        }

    def _json_rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute JSON-RPC call to Kodi"""
        self.logger.debug(f"Executing JSON-RPC call: {method}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        try:
            self.logger.debug(f"JSON-RPC payload: {json.dumps(payload, indent=2)}")
            raw_response = xbmc.executeJSONRPC(json.dumps(payload))
            self.logger.debug(f"JSON-RPC raw response length: {len(raw_response)} chars")
            
            response = json.loads(raw_response)
            self.logger.debug(f"JSON-RPC parsed response keys: {list(response.keys())}")

            if 'error' in response:
                error = response['error']
                self.logger.error(f"JSON-RPC error in {method}: {error}")
                return {}

            result = response.get('result', {})
            if result and method == "VideoLibrary.GetMovies":
                movie_count = len(result.get('movies', []))
                self.logger.info(f"JSON-RPC {method} returned {movie_count} movies")
            elif result and method == "VideoLibrary.GetEpisodes":
                episode_count = len(result.get('episodes', []))
                self.logger.info(f"JSON-RPC {method} returned {episode_count} episodes")
            
            return result

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON-RPC response for {method}: {e}")
            self.logger.error(f"Raw response (first 500 chars): {raw_response[:500]}...")
            return {}
        except Exception as e:
            import traceback
            self.logger.error(f"JSON-RPC call failed for {method}: {e}")
            self.logger.error(f"JSON-RPC traceback: {traceback.format_exc()}")
            return {}


# Convenience function for simple searches
def search_local(query: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Simple search function for backward compatibility"""
    engine = LocalSearchEngine()
    result = engine.search(query, limit)
    return result.get('items', [])