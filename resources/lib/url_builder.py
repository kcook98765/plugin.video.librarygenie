
"""URL building and parameter parsing utilities for LibraryGenie addon"""

import sys
import urllib.parse
from urllib.parse import urlencode, parse_qs, urlparse
import xbmcaddon
from resources.lib import utils

def build_plugin_url(params: dict) -> str:
    """Build plugin URL with clean parameters (no empty values)"""
    # Drop None / '' / False and only encode the rest
    cleaned = {k: str(v) for k, v in params.items() if v not in (None, '', False)}
    addon_id = xbmcaddon.Addon().getAddonInfo('id')
    base_url = f"plugin://{addon_id}/"
    return base_url + ('?' + urlencode(cleaned, doseq=True) if cleaned else '')

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
    if 'folder' in ctx_params:
        ctx['folder'] = ctx_params.get('folder')
    return ctx
