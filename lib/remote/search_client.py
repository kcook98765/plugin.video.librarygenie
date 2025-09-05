#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Remote Search Client
Handles remote search requests with authentication and proper HTTP handling
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
import urllib.error
from ..auth.state import is_authorized, get_access_token
from ..config import get_config
from ..utils.logger import get_logger


class RemoteError(Exception):
    """Remote search error"""
    pass


from ..ui.localization import L

def search_remote(query, page=1, page_size=100):
    """
    Search remote server for movies/shows

    Args:
        query: Search query string
        page: Page number (1-based)
        page_size: Items per page

    Returns:
        dict: Response with 'items' list and uniform format

    Raises:
        RemoteError: If not authorized or request fails
    """
    logger = get_logger(__name__)

    if not is_authorized():
        raise RemoteError("not authorized")

    cfg = get_config()
    base = cfg.get('remote_base_url')

    if not base:
        raise RemoteError("remote_base_url not configured")

    # Build search URL
    params = {
        "q": query,
        "page": page,
        "page_size": page_size
    }
    url = f"{base}/search?" + urllib.parse.urlencode(params)

    # Get access token
    access_token = get_access_token()
    if not access_token:
        raise RemoteError("no access token available")

    # Get version for User-Agent
    try:
        import xbmcaddon
        addon = xbmcaddon.Addon()
        version = addon.getAddonInfo('version')
    except:
        version = "1.0.0"

    # Create request with proper headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": f"LibraryGenie-Kodi/{version}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        logger.debug(f"Remote search: {query} (page {page}, size {page_size})")

        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))

            if response.getcode() == 200:
                # Map remote results to uniform format
                items = data.get('items', [])
                mapped_items = [_map_remote_item(item) for item in items]

                result = {
                    'items': mapped_items,
                    'total': data.get('total', len(mapped_items)),
                    'used_remote': True
                }

                logger.debug(f"Remote search successful: {len(mapped_items)} results")
                return result
            else:
                raise RemoteError(f"server returned {response.getcode()}")

    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RemoteError("unauthorized - token may be expired")
        elif e.code == 403:
            raise RemoteError("access denied")
        elif e.code == 429:
            raise RemoteError("rate limited - please try again later")
        elif e.code == 503:
            raise RemoteError("service temporarily unavailable")
        else:
            raise RemoteError(f"HTTP {e.code}")

    except urllib.error.URLError as e:
        if "timeout" in str(e).lower():
            raise RemoteError("request timed out")
        else:
            raise RemoteError(f"network error: {e}")

    except Exception as e:
        raise RemoteError(f"request failed: {e}")


def _map_remote_item(remote_item):
    """Map remote item to uniform format with local file preference"""
    # Try to map to local file if we have IMDB/TMDB IDs
    local_path = _find_local_path(remote_item)

    # Create uniform item dict
    mapped_item = {
        'label': remote_item.get('title', 'Unknown'),
        'path': local_path or remote_item.get('stream_url', ''),
        'art': remote_item.get('art', {}),
        'type': remote_item.get('type', 'movie'),
        'ids': {
            'imdb': remote_item.get('imdb_id', ''),
            'tmdb': remote_item.get('tmdb_id', ''),
            'remote_id': remote_item.get('id', '')
        },
        # Additional metadata
        'title': remote_item.get('title', ''),
        'year': remote_item.get('year', ''),
        'plot': remote_item.get('plot', ''),
        'rating': remote_item.get('rating', 0.0),
        'genre': remote_item.get('genre', []),
        'director': remote_item.get('director', []),
        'runtime': remote_item.get('runtime', 0),
        '_source': 'remote',
        '_local_mapped': bool(local_path)
    }

    # Add episode-specific fields if applicable
    if remote_item.get('type') == 'episode':
        mapped_item.update({
            'showtitle': remote_item.get('showtitle', ''),
            'season': remote_item.get('season', 0),
            'episode': remote_item.get('episode', 0)
        })

    return mapped_item


def _find_local_path(remote_item):
    """
    Try to find local file path by matching IMDB/TMDB IDs
    Returns local path if found, None otherwise
    """
    try:
        from ..data.connection_manager import get_connection_manager

        imdb_id = remote_item.get('imdb_id')
        tmdb_id = remote_item.get('tmdb_id')

        if not (imdb_id or tmdb_id):
            return None

        conn_manager = get_connection_manager()

        # Try IMDB ID first
        if imdb_id:
            query = """
                SELECT file_path FROM media_items 
                WHERE imdbnumber = ? AND source = 'lib'
                LIMIT 1
            """
            result = conn_manager.execute_single(query, (imdb_id,))
            if result:
                return result[0]

        # Try TMDB ID
        if tmdb_id:
            query = """
                SELECT file_path FROM media_items 
                WHERE tmdb_id = ? AND source = 'lib'
                LIMIT 1
            """
            result = conn_manager.execute_single(query, (tmdb_id,))
            if result:
                return result[0]

        return None

    except Exception as e:
        logger = get_logger(__name__)
        logger.debug(f"Could not map remote item to local: {e}")
        return None