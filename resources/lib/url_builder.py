"""URL building and parameter parsing utilities for LibraryGenie addon"""

import sys
import urllib.parse
from urllib.parse import urlencode, parse_qs, urlparse, quote_plus
import xbmcaddon
from resources.lib import utils

def build_plugin_url(params):
    """Build plugin URL from parameters"""
    # Ensure all values are strings for URL encoding
    string_params = {}
    for key, value in params.items():
        if value is not None:
            if isinstance(value, list):
                string_params[key] = [str(v) for v in value]
            else:
                string_params[key] = str(value)

    # Build query string
    query_params = []
    for key, value in string_params.items():
        if isinstance(value, list):
            for v in value:
                query_params.append(f"{key}={quote_plus(v)}")
        else:
            query_params.append(f"{key}={quote_plus(value)}")

    query_string = "&".join(query_params)
    url = f"plugin://plugin.video.librarygenie/?{query_string}"
    return url

def parse_params(params_string: str) -> dict:
    """Parse URL parameters from query string or full URL"""
    try:
        # Handle both full URLs and query strings
        if params_string.startswith('?'):
            query_string = params_string[1:]  # Remove leading '?'
        else:
            parsed_url = urlparse(params_string)
            query_string = parsed_url.query

        return parse_qs(query_string) if query_string else {}
    except Exception as e:
        utils.log(f"Error parsing params '{params_string}': {str(e)}", "ERROR")
        return {}

def detect_context(ctx_params: dict) -> dict:
    """
    Decide what screen we're on so we can tailor actions.
    view: root | lists | list | folder | search | other
    """
    view = ctx_params.get('view') or 'root'
    ctx = {'view': view}
    if 'list_id' in ctx_params:
        ctx['list_id'] = ctx_params.get('list_id')
    if 'folder_id' in ctx_params:  # Changed from 'folder' to 'folder_id'
        ctx['folder_id'] = ctx_params.get('folder_id')
    return ctx