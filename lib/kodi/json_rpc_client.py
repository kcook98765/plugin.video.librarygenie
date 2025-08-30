
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - JSON-RPC Client
Handles communication with Kodi's JSON-RPC API
"""

import json
from typing import Dict, Any, List, Optional

import xbmc

from ..utils.logger import get_logger


class JsonRpcClient:
    """Client for Kodi JSON-RPC API calls"""

    def __init__(self, config_manager=None):
        self.logger = get_logger(__name__)
        self.config_manager = config_manager

    def execute(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a JSON-RPC method call"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params or {}
            }

            raw_response = xbmc.executeJSONRPC(json.dumps(payload))
            response = json.loads(raw_response)

            if 'error' in response:
                self.logger.error(f"JSON-RPC error in {method}: {response['error']}")
                return {}

            return response.get('result', {})

        except Exception as e:
            self.logger.error(f"Error executing JSON-RPC method {method}: {e}")
            return {}

    def get_movies_batch(self, movie_ids: List[int]) -> List[Dict[str, Any]]:
        """Get movie details for a batch of movie IDs"""
        try:
            if not movie_ids:
                return []

            # Get details for each movie
            movies = []
            for movie_id in movie_ids:
                result = self.execute("VideoLibrary.GetMovieDetails", {
                    "movieid": movie_id,
                    "properties": [
                        "title", "originaltitle", "sorttitle", "year", "genre", 
                        "plot", "rating", "votes", "mpaa", "runtime", "studio", 
                        "country", "premiered", "art", "resume", "file"
                    ]
                })

                movie_details = result.get("moviedetails")
                if movie_details:
                    movies.append(movie_details)

            return movies

        except Exception as e:
            self.logger.error(f"Error in get_movies_batch: {e}")
            return []

    def get_episodes_batch(self, episode_ids: List[int]) -> List[Dict[str, Any]]:
        """Get episode details for a batch of episode IDs"""
        try:
            if not episode_ids:
                return []

            # Get details for each episode
            episodes = []
            for episode_id in episode_ids:
                result = self.execute("VideoLibrary.GetEpisodeDetails", {
                    "episodeid": episode_id,
                    "properties": [
                        "title", "showtitle", "season", "episode", "plot", 
                        "rating", "runtime", "art", "resume", "file", "aired",
                        "playcount", "lastplayed", "tvshowid"
                    ]
                })

                episode_details = result.get("episodedetails")
                if episode_details:
                    episodes.append(episode_details)

            return episodes

        except Exception as e:
            self.logger.error(f"Error in get_episodes_batch: {e}")
            return []


# Global instance
_json_rpc_client = None

def get_json_rpc_client(config_manager=None):
    """Get or create the global JSON-RPC client instance"""
    global _json_rpc_client
    if _json_rpc_client is None:
        _json_rpc_client = JsonRpcClient(config_manager)
    return _json_rpc_client
