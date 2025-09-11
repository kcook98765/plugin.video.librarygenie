#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Kodi JSON-RPC Client
Safe, paginated communication with Kodi's video library
"""

import json
from typing import Dict, Any, Optional, List

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
                    "votes",
                    "genre",
                    "mpaa",
                    "director",
                    "country",
                    "studio",
                    "writer",
                    "premiered",
                    "originaltitle",
                    "sorttitle",
                    # NOTE: DO NOT REQUEST "cast" HERE - Cast data should not be requested
                    # when building ListItems as it can cause performance issues and
                    # is not needed for list display. Kodi will populate cast data
                    # automatically when dbid is set on the ListItem.
                    "playcount",
                    "lastplayed",
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
            self.logger.debug("JSON-RPC request: VideoLibrary.GetMovies offset=%s limit=%s", offset, actual_limit)
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error("JSON-RPC error: %s", response['error'])
                return {"movies": [], "limits": {"total": 0}}

            result = response.get("result", {})
            movies = result.get("movies", [])
            limits = result.get("limits", {"total": 0})

            self.logger.debug("Retrieved %s movies, total: %s", len(movies), limits.get('total', 0))

            # Normalize the movie data
            normalized_movies = []
            for movie in movies:
                normalized = self._normalize_movie_data(movie)
                if normalized:
                    normalized_movies.append(normalized)

            return {"movies": normalized_movies, "limits": limits}

        except Exception as e:
            self.logger.error("JSON-RPC request failed: %s", e)
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
                self.logger.error("JSON-RPC count error: %s", response['error'])
                return 0

            result = response.get("result", {})
            limits = result.get("limits", {"total": 0})

            return limits.get("total", 0)

        except Exception as e:
            self.logger.error("JSON-RPC count request failed: %s", e)
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
                self.logger.error("JSON-RPC quick check error: %s", response['error'])
                return []

            result = response.get("result", {})
            movies = result.get("movies", [])

            return movies

        except Exception as e:
            self.logger.error("JSON-RPC quick check failed: %s", e)
            return []

    def get_movie_details(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get details for a specific movie by ID"""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetMovieDetails",
                "params": {
                    "movieid": movie_id,
                    "properties": [
                        "title", "year", "uniqueid", "plot", "runtime", "rating",
                        "genre", "director", "studio", "country", "art"
                    ]
                },
                "id": 1
            }

            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error("JSON-RPC error getting movie %s: %s", movie_id, response['error'])
                return None

            movie_details = response.get("result", {}).get("moviedetails")
            if movie_details:
                return self._normalize_movie_data(movie_details)

            return None

        except Exception as e:
            self.logger.error("Error getting movie details for ID %s: %s", movie_id, e)
            return None

    def get_episode_details(self, episode_id: int) -> Optional[Dict[str, Any]]:
        """Get details for a specific episode by ID"""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodeDetails",
                "params": {
                    "episodeid": episode_id,
                    "properties": [
                        "title", "showtitle", "season", "episode", "plot", 
                        "runtime", "rating", "art", "uniqueid"
                    ]
                },
                "id": 1
            }

            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error("JSON-RPC error getting episode %s: %s", episode_id, response['error'])
                return None

            episode_details = response.get("result", {}).get("episodedetails")
            if episode_details:
                return self._normalize_episode_data(episode_details)

            return None

        except Exception as e:
            self.logger.error("Error getting episode details for ID %s: %s", episode_id, e)
            return None

    def get_tvshows(self, offset: int = 0, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get TV shows from Kodi library with pagination"""
        actual_limit = limit or self.page_size

        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetTVShows",
            "params": {
                "properties": [
                    "title",
                    "year", 
                    "imdbnumber",
                    "uniqueid",
                    "art",
                    "plot",
                    "rating",
                    "votes",
                    "genre",
                    "mpaa",
                    "studio",
                    "premiered",
                    "originaltitle",
                    "sorttitle",
                    "playcount",
                    "lastplayed"
                ],
                "limits": {
                    "start": offset,
                    "end": offset + actual_limit
                }
            },
            "id": 1
        }

        try:
            self.logger.debug("JSON-RPC request: VideoLibrary.GetTVShows offset=%s limit=%s", offset, actual_limit)
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error("JSON-RPC error: %s", response['error'])
                return {"tvshows": [], "limits": {"total": 0}}

            result = response.get("result", {})
            tvshows = result.get("tvshows", [])
            limits = result.get("limits", {"total": 0})

            self.logger.debug("Retrieved %s TV shows, total: %s", len(tvshows), limits.get('total', 0))

            # Normalize the TV show data
            normalized_tvshows = []
            for tvshow in tvshows:
                normalized = self._normalize_tvshow_data(tvshow)
                if normalized:
                    normalized_tvshows.append(normalized)

            return {"tvshows": normalized_tvshows, "limits": limits}

        except Exception as e:
            self.logger.error("JSON-RPC request failed: %s", e)
            return {"tvshows": [], "limits": {"total": 0}}

    def get_tvshow_count(self) -> int:
        """Get total count of TV shows in library"""

        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetTVShows",
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
                self.logger.error("JSON-RPC count error: %s", response['error'])
                return 0

            result = response.get("result", {})
            limits = result.get("limits", {"total": 0})

            return limits.get("total", 0)

        except Exception as e:
            self.logger.error("JSON-RPC count request failed: %s", e)
            return 0

    def get_episodes_for_tvshow(self, tvshow_id: int) -> List[Dict[str, Any]]:
        """Get all episodes for a specific TV show"""
        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetEpisodes",
            "params": {
                "tvshowid": tvshow_id,
                "properties": [
                    "title", "showtitle", "season", "episode", "plot",
                    "runtime", "rating", "votes", "firstaired", "file",
                    "art", "uniqueid", "playcount", "lastplayed", "dateadded"
                ]
            },
            "id": 1
        }

        try:
            self.logger.debug("JSON-RPC request: VideoLibrary.GetEpisodes for tvshow %s", tvshow_id)
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error("JSON-RPC error getting episodes for show %s: %s", tvshow_id, response['error'])
                return []

            result = response.get("result", {})
            episodes = result.get("episodes", [])

            self.logger.debug("Retrieved %s episodes for TV show %s", len(episodes), tvshow_id)

            # Normalize episode data
            normalized_episodes = []
            for episode in episodes:
                normalized = self._normalize_episode_data(episode)
                if normalized:
                    normalized_episodes.append(normalized)

            return normalized_episodes

        except Exception as e:
            self.logger.error("Error getting episodes for TV show %s: %s", tvshow_id, e)
            return []

    def get_tvshows_quick_check(self) -> List[Dict[str, Any]]:
        """Get minimal TV show data for quick scanning (used for delta scans)"""
        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetTVShows",
            "params": {
                "properties": ["title"],
            },
            "id": 1
        }

        try:
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)

            if "error" in response:
                self.logger.error("JSON-RPC quick check error: %s", response['error'])
                return []

            result = response.get("result", {})
            return result.get("tvshows", [])

        except Exception as e:
            self.logger.error("JSON-RPC quick check failed: %s", e)
            return []

    def _normalize_tvshow_data(self, tvshow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize TV show data from JSON-RPC response"""
        try:
            # Extract IMDb ID from uniqueid
            imdb_id = ""
            tmdb_id = ""
            uniqueid = tvshow.get("uniqueid", {})
            if uniqueid:
                imdb_id = uniqueid.get("imdb", "")
                tmdb_id = uniqueid.get("tmdb", "")

            # Extract art URLs
            art = tvshow.get("art", {})
            poster = art.get("poster", "")
            fanart = art.get("fanart", "")
            thumb = art.get("thumb", "")

            # Handle genres (can be list or string)
            genre = tvshow.get("genre", [])
            if isinstance(genre, list):
                genre_str = ", ".join(genre)
            else:
                genre_str = str(genre)

            # Handle studio (can be list or string)
            studio = tvshow.get("studio", [])
            if isinstance(studio, list):
                studio_str = ", ".join(studio)
            else:
                studio_str = str(studio)

            return {
                "kodi_id": tvshow.get("tvshowid"),
                "title": tvshow.get("title", "Unknown TV Show"),
                "year": tvshow.get("year"),
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                # Artwork URLs
                "poster": poster,
                "fanart": fanart,
                "thumb": thumb,
                "art": art,  # Full art dictionary
                # Extended metadata
                "plot": tvshow.get("plot", ""),
                "rating": tvshow.get("rating", 0.0),
                "votes": tvshow.get("votes", 0),
                "genre": genre_str,
                "mpaa": tvshow.get("mpaa", ""),
                "studio": studio_str,
                "premiered": tvshow.get("premiered", ""),
                "originaltitle": tvshow.get("originaltitle", ""),
                "sorttitle": tvshow.get("sorttitle", ""),
                "playcount": tvshow.get("playcount", 0),
                "lastplayed": tvshow.get("lastplayed", ""),
                "uniqueid": uniqueid  # Full uniqueid dictionary
            }

        except Exception as e:
            self.logger.warning("Failed to normalize TV show data: %s", e)
            return None

    def _normalize_movie_data(self, movie: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize movie data from JSON-RPC response"""
        try:
            # Extract IMDb ID from uniqueid
            imdb_id = ""
            tmdb_id = ""
            uniqueid = movie.get("uniqueid", {})
            if uniqueid:
                imdb_id = uniqueid.get("imdb", "")
                tmdb_id = uniqueid.get("tmdb", "")

            # Extract art URLs
            art = movie.get("art", {})
            poster = art.get("poster", "")
            fanart = art.get("fanart", "")
            thumb = art.get("thumb", "")

            # Handle genres (can be list or string)
            genre = movie.get("genre", [])
            if isinstance(genre, list):
                genre_str = ", ".join(genre)
            else:
                genre_str = str(genre)

            # Handle director (can be list or string)  
            director = movie.get("director", [])
            if isinstance(director, list):
                director_str = ", ".join(director)
            else:
                director_str = str(director)

            # Handle resume point
            resume_data = movie.get("resume", {})
            resume_time = resume_data.get("position", 0) if isinstance(resume_data, dict) else 0

            # NOTE: Cast data is intentionally not processed here.
            # Cast information should not be requested in JSON-RPC calls for ListItems
            # as it causes performance issues. Kodi will handle cast population automatically
            # when the ListItem has a proper dbid set.

            # Handle additional fields for comprehensive storage
            writer = movie.get("writer", [])
            if isinstance(writer, list):
                writer_str = ", ".join(writer)
            else:
                writer_str = str(writer)

            country = movie.get("country", [])
            if isinstance(country, list):
                country_str = ", ".join(country)
            else:
                country_str = str(country)

            studio = movie.get("studio", [])
            if isinstance(studio, list):
                studio_str = ", ".join(studio)
            else:
                studio_str = str(studio)

            return {
                "kodi_id": movie.get("movieid"),
                "title": movie.get("title", "Unknown Title"),
                "year": movie.get("year"),
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                "file_path": movie.get("file", ""),
                "date_added": movie.get("dateadded", ""),
                # Artwork URLs
                "poster": poster,
                "fanart": fanart,
                "thumb": thumb,
                "art": art,  # Full art dictionary
                # Extended metadata
                "plot": movie.get("plot", ""),
                "plotoutline": movie.get("plotoutline", ""),
                "runtime": movie.get("runtime", 0),
                "rating": movie.get("rating", 0.0),
                "votes": movie.get("votes", 0),
                "genre": genre_str,
                "mpaa": movie.get("mpaa", ""),
                "director": director_str,
                "country": country_str,
                "studio": studio_str,
                "writer": writer_str,
                "premiered": movie.get("premiered", ""),
                "originaltitle": movie.get("originaltitle", ""),
                "sorttitle": movie.get("sorttitle", ""),
                "playcount": movie.get("playcount", 0),
                "lastplayed": movie.get("lastplayed", ""),
                "resume_time": resume_time,
                "resume": resume_data,  # Full resume data
                "uniqueid": uniqueid  # Full uniqueid dictionary
            }

        except Exception as e:
            self.logger.warning("Failed to normalize movie data: %s", e)
            return None

    def _normalize_episode_data(self, episode: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize episode data from JSON-RPC response"""
        try:
            # Extract unique IDs
            uniqueid = episode.get("uniqueid", {})
            imdb_id = uniqueid.get("imdb", "") if uniqueid else ""
            tmdb_id = uniqueid.get("tmdb", "") if uniqueid else ""

            # Extract art URLs
            art = episode.get("art", {})
            thumb = art.get("thumb", "")
            poster = art.get("poster", "")
            fanart = art.get("fanart", "")

            # Calculate duration from runtime
            runtime = episode.get("runtime", 0)  # in seconds
            duration = runtime // 60 if runtime else 0  # convert to minutes

            return {
                "kodi_id": episode.get("episodeid"),
                "title": episode.get("title", "Unknown Episode"),
                "tvshowtitle": episode.get("showtitle", "Unknown Show"),
                "season": episode.get("season", 0),
                "episode": episode.get("episode", 0),
                "plot": episode.get("plot", ""),
                "runtime": runtime,
                "duration": duration,
                "rating": episode.get("rating", 0.0),
                "votes": episode.get("votes", 0),
                "firstaired": episode.get("firstaired", ""),
                "file_path": episode.get("file", ""),
                "date_added": episode.get("dateadded", ""),
                "playcount": episode.get("playcount", 0),
                "lastplayed": episode.get("lastplayed", ""),
                # Artwork URLs
                "thumb": thumb,
                "poster": poster,
                "fanart": fanart,
                "art": art,  # Full art dictionary
                # External IDs
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                "uniqueid": uniqueid  # Full uniqueid dictionary
            }

        except Exception as e:
            self.logger.warning("Failed to normalize episode data: %s", e)
            return None



# Global client instance
_client_instance = None


def get_kodi_client():
    """Get global Kodi JSON-RPC client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = KodiJsonRpcClient()
    return _client_instance