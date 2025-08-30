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
        """Search movies in local SQLite database"""
        self.logger.debug(f"Searching movies in SQLite for query: '{query_lower}' with limit: {limit}")

        try:
            # Import the connection manager to access the database
            from ..data.connection_manager import get_connection_manager
            conn_manager = get_connection_manager()

            # Search in the library_movie table
            self.logger.debug("Searching library_movie table in SQLite database")

            # Split query into individual words
            words = [word.strip() for word in query_lower.split() if word.strip()]
            
            if not words:
                self.logger.info("No valid words in query, returning empty results")
                return []

            # Build SQL conditions for cross-field matching
            # Each word can match in title OR plot, and all words must be found somewhere
            where_conditions = []
            params = []
            title_conditions = []  # For prioritization
            
            for word in words:
                word_pattern = f"%{word.lower()}%"
                # Each word must exist in either title OR plot (both fields converted to lowercase)
                where_conditions.append("(LOWER(title) LIKE ? OR LOWER(COALESCE(plot, '')) LIKE ?)")
                params.extend([word_pattern, word_pattern])
                
                # Track title matches for prioritization
                title_conditions.append(f"LOWER(title) LIKE ?")
                params.append(word_pattern)

            # All words must match somewhere across title/plot fields (AND condition)
            where_clause = " AND ".join(where_conditions)
            
            # Build prioritization - count how many words match in title
            title_match_count = " + ".join([f"CASE WHEN {cond} THEN 1 ELSE 0 END" 
                                          for cond in title_conditions])

            sql = f"""
                SELECT 
                    kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                    poster, fanart, poster as thumb, plot, duration as runtime, rating, 
                    genre, mpaa, director, 0 as playcount
                FROM media_items 
                WHERE media_type = 'movie'
                AND {where_clause}
                ORDER BY 
                    ({title_match_count}) DESC,
                    title
                LIMIT ?
            """
            
            params.append(limit)
            
            # Debug logging - show the actual SQL and parameters
            self.logger.debug(f"Executing SQL query: {sql}")
            self.logger.debug(f"Query parameters: {params}")
            
            # Also check what's actually in the database
            count_sql = "SELECT COUNT(*) as count FROM media_items WHERE media_type = 'movie'"
            total_movies = conn_manager.execute_single(count_sql, [])
            if total_movies:
                total_count = total_movies.get('count', 0) if hasattr(total_movies, 'get') else total_movies[0]
                self.logger.debug(f"Total movies in database: {total_count}")
            
            movies = conn_manager.execute_query(sql, params)

            # Debug: Test individual word searches to understand what's in the database
            for word in words:
                test_sql = """
                    SELECT title, 
                           SUBSTR(COALESCE(plot, ''), 1, 100) as plot_preview,
                           CASE WHEN LOWER(title) LIKE ? THEN 'TITLE' ELSE '' END as title_match,
                           CASE WHEN LOWER(COALESCE(plot, '')) LIKE ? THEN 'PLOT' ELSE '' END as plot_match
                    FROM media_items 
                    WHERE media_type = 'movie' 
                    AND (LOWER(title) LIKE ? OR LOWER(COALESCE(plot, '')) LIKE ?)
                    LIMIT 5
                """
                test_pattern = f"%{word.lower()}%"
                test_results = conn_manager.execute_query(test_sql, [test_pattern, test_pattern, test_pattern, test_pattern])
                if test_results:
                    self.logger.debug(f"Test search for '{word}': found {len(test_results)} matches")
                    for result in test_results[:3]:  # Show first 3 matches
                        # IMPORTANT: Convert sqlite3.Row to dict for .get() method access
                        # sqlite3.Row objects don't have .get() method, only dict objects do
                        if hasattr(result, 'keys'):
                            result_dict = dict(result)
                        else:
                            result_dict = result
                        
                        title = result_dict.get('title', 'Unknown')
                        plot_preview = result_dict.get('plot_preview', '')
                        title_match = result_dict.get('title_match', '')
                        plot_match = result_dict.get('plot_match', '')
                        self.logger.debug(f"  - '{title}' | {title_match}{plot_match} | Plot: '{plot_preview}'")

            self.logger.info(f"SQLite search returned {len(movies)} movies from database")

            if not movies:
                self.logger.info("No movies found in SQLite database")
                return []

            # Debug logging
            self.logger.info("=== DEBUGGING SQLITE MOVIE RESULTS ===")
            print("=== DEBUGGING SQLITE MOVIE RESULTS ===")
            for i, movie in enumerate(movies[:10]):
                title = movie['title']
                log_msg = f"SQLite Movie {i+1}: '{title}'"
                self.logger.info(log_msg)
                print(log_msg)

            witch_count = len([m for m in movies if 'witch' in m['title'].lower()])
            debug_msg = f"FOUND {witch_count} movies with 'witch' in title from SQLite"
            self.logger.info(debug_msg)
            print(debug_msg)

            self.logger.info("=== END DEBUGGING ===")
            print("=== END DEBUGGING ===")

            results = []
            for movie in movies:
                result = self._format_sqlite_movie_result(movie)
                results.append(result)

            self.logger.info(f"SQLite movie search completed: {len(results)} results")
            return results

        except Exception as e:
            import traceback
            self.logger.error(f"Error searching movies in SQLite: {e}")
            self.logger.error(f"SQLite search traceback: {traceback.format_exc()}")

            # Return empty results instead of fallback
            self.logger.error("SQLite search failed, returning empty results (no JSON-RPC fallback)")
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

    def _format_sqlite_movie_result(self, movie: Dict[str, Any]) -> Dict[str, Any]:
        """Format movie data from SQLite database to uniform item dict"""
        # CRITICAL: Convert sqlite3.Row to dict for proper attribute access
        # sqlite3.Row objects can be converted to dict but don't have .get() method
        # Always convert Row objects to dict before using .get() method
        if hasattr(movie, 'keys'):
            movie = dict(movie)

        title = movie.get('title') or 'Unknown Movie'
        year = movie.get('year')
        kodi_id = movie.get('kodi_id')

        # Create display label
        if year:
            label = f"{title} ({year})"
        else:
            label = title

        # Extract artwork from SQLite columns
        art = {}
        if movie.get('poster'):
            art['poster'] = movie['poster']
        if movie.get('fanart'):
            art['fanart'] = movie['fanart']
        if movie.get('thumb'):
            art['thumb'] = movie['thumb']

        result = {
            'label': label,
            'path': movie.get('file_path') or '',
            'art': art,
            'type': 'movie',
            'ids': {
                'imdb': movie.get('imdb_id'),
                'tmdb': movie.get('tmdb_id'),
                'kodi_id': kodi_id
            },
            # Additional metadata
            'title': title,
            'year': year,
            'plot': movie.get('plot') or '',
            'rating': movie.get('rating') or 0.0,
            'genre': movie.get('genre') or '',
            'director': movie.get('director') or '',
            'runtime': movie.get('runtime') or 0,
            'mpaa': movie.get('mpaa') or '',
            'playcount': movie.get('playcount') or 0
        }

        # CRITICAL: Include kodi_id at top level for search result storage
        if kodi_id:
            result['kodi_id'] = kodi_id
            result['movieid'] = kodi_id  # Alternative field name used by JSON-RPC
            self.logger.info(f"LOCAL SEARCH: SQLite result for '{title}' includes kodi_id: {kodi_id}")
        else:
            self.logger.warning(f"LOCAL SEARCH: SQLite result for '{title}' missing kodi_id - movie data: {list(movie.keys())}")

        return result

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