#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Remote Search Client
Handles remote search requests with authentication
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from ..auth.state import is_authorized
from ..config import get_config
from ..utils.logger import get_logger


class RemoteError(Exception):
    """Remote search error"""
    pass


def search_remote(query, page=1, page_size=100):
    """
    Search remote server for movies/shows

    Args:
        query: Search query string
        page: Page number (1-based)
        page_size: Items per page

    Returns:
        dict: Response with 'items' list

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

    # Create request with authorization
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "LibraryGenie Kodi Addon",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        logger.debug(f"Remote search: {query} (page {page}, size {page_size})")

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

            if response.getcode() == 200:
                logger.debug(f"Remote search successful: {len(data.get('items', []))} results")
                return data
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


def get_access_token():
    """
    Get access token from stored auth state

    Returns:
        str: Access token or None if not available
    """
    try:
        from ..auth.state import _PATH
        import os

        token_file = os.path.join(_PATH, 'tokens.json')

        with open(token_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data.get("access_token")

    except Exception:
        return None