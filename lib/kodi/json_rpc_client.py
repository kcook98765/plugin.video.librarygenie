#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Kodi JSON-RPC Client
Safe, paginated communication with Kodi's video library
"""

import json
from typing import Dict, Any, Optional, Union, List

import xbmc

from ..utils.logger import get_logger


class KodiJsonRpcClient:
    """Client for safely communicating with Kodi's JSON-RPC API"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.page_size = 100  # Safe page size for large libraries

    def get_movies(self, offset: int = 0, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get movies from Kodi library with pagination"""
        actual_limit = limit or self.page_size

        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {
                "properties": [
                    "title",
                    "year",
                    "imdbnumber",
                    "uniqueid",
                    "file",
                    "dateadded",
                    "art",
                    "plot",
                    "plotoutline",
                    "runtime",
                    "rating",
                    "genre",
                    "mpaa",
                    "director",
                    "country",
                    "studio",
                    "cast",
                    "playcount",
                    "resume"
                ],
                "limits": {
                    "start": offset,
                    "end": offset + actual_limit
                }
            },
            "id": 1
        }

        try:
            self.logger.debug(f"JSON-RPC request: VideoLibrary.GetMovies offset={offset} limit={actual_limit}")
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error(f"JSON-RPC error: {response['error']}")
                return {"movies": [], "limits": {"total": 0}}

            result = response.get("result", {})
            movies = result.get("movies", [])
            limits = result.get("limits", {"total": 0})

            self.logger.debug(f"Retrieved {len(movies)} movies, total: {limits.get('total', 0)}")

            # Normalize the movie data
            normalized_movies = []
            for movie in movies:
                normalized = self._normalize_movie_data(movie)
                if normalized:
                    normalized_movies.append(normalized)

            return {"movies": normalized_movies, "limits": limits}

        except Exception as e:
            self.logger.error(f"JSON-RPC request failed: {e}")
            return {"movies": [], "limits": {"total": 0}}

    def get_movie_count(self) -> int:
        """Get total count of movies in library"""

        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {
                "properties": ["title"],
                "limits": {"start": 0, "end": 1}
            },
            "id": 1
        }

        try:
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error(f"JSON-RPC count error: {response['error']}")
                return 0

            result = response.get("result", {})
            limits = result.get("limits", {"total": 0})

            return limits.get("total", 0)

        except Exception as e:
            self.logger.error(f"JSON-RPC count request failed: {e}")
            return 0

    def get_movies_quick_check(self) -> List[Dict[str, Any]]:
        """Quick check of library IDs and basic metadata for delta detection"""

        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {
                "properties": ["file", "dateadded"],
                "limits": {"start": 0, "end": 10000}  # Large limit for quick checks
            },
            "id": 1
        }

        try:
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error(f"JSON-RPC quick check error: {response['error']}")
                return []

            result = response.get("result", {})
            movies = result.get("movies", [])

            return movies

        except Exception as e:
            self.logger.error(f"JSON-RPC quick check failed: {e}")
            return []

    def _normalize_movie_data(self, movie: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize movie data from Kodi JSON-RPC response"""
        try:
            # Extract external IDs
            imdb_id = None
            tmdb_id = None

            # Try the old imdbnumber field
            if "imdbnumber" in movie and movie["imdbnumber"]:
                if movie["imdbnumber"].startswith("tt"):
                    imdb_id = movie["imdbnumber"]

            # Try the newer uniqueid structure
            if "uniqueid" in movie and isinstance(movie["uniqueid"], dict):
                if "imdb" in movie["uniqueid"]:
                    imdb_id = movie["uniqueid"]["imdb"]
                if "tmdb" in movie["uniqueid"]:
                    tmdb_id = str(movie["uniqueid"]["tmdb"])

            # Extract artwork URLs
            art = movie.get("art", {})
            poster = art.get("poster", "")
            fanart = art.get("fanart", "")
            thumb = art.get("thumb", poster)  # Fallback to poster

            # Extract and process metadata
            genres = movie.get("genre", [])
            genre_str = ", ".join(genres) if isinstance(genres, list) else str(genres) if genres else ""

            directors = movie.get("director", [])
            director_str = ", ".join(directors) if isinstance(directors, list) else str(directors) if directors else ""

            # Handle resume point
            resume_data = movie.get("resume", {})
            resume_time = resume_data.get("position", 0) if isinstance(resume_data, dict) else 0

            # Handle cast information
            cast_data = movie.get("cast", [])
            
            return {
                "kodi_id": movie.get("movieid"),
                "title": movie.get("title", "Unknown Title"),
                "year": movie.get("year"),
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                "file_path": movie.get("file", ""),
                "date_added": movie.get("dateadded", ""),
                # Phase 11: Artwork URLs
                "poster": poster,
                "fanart": fanart,
                "thumb": thumb,
                # Phase 11: Extended metadata
                "plot": movie.get("plot", ""),
                "plotoutline": movie.get("plotoutline", ""),
                "runtime": movie.get("runtime", 0),
                "rating": movie.get("rating", 0.0),
                "genre": genre_str,
                "mpaa": movie.get("mpaa", ""),
                "director": director_str,
                "country": movie.get("country", []),
                "studio": movie.get("studio", []),
                "cast": cast_data,
                "playcount": movie.get("playcount", 0),
                "resume_time": resume_time
            }

        except Exception as e:
            self.logger.warning(f"Failed to normalize movie data: {e}")
            return None



# Global client instance
_client_instance = None


def get_kodi_client():
    """Get global Kodi JSON-RPC client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = KodiJsonRpcClient()
    return _client_instance