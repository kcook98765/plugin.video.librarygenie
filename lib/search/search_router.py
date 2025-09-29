#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Router
Routes search requests through custom panel or legacy keyboard
"""

import xbmc
import xbmcaddon
from lib.gui.search_panel import (
    SearchPanel, CONTENT_MOVIES, CONTENT_SERIES, CONTENT_ALL,
    FIELDS_TITLE, FIELDS_PLOT, FIELDS_BOTH, MATCH_ANY, MATCH_ALL, MATCH_PHRASE
)

ADDON = xbmcaddon.Addon()
L = ADDON.getLocalizedString


def start_search_flow(initial_query=''):
    """Start search flow using custom panel or keyboard"""
    if ADDON.getSettingBool('use_custom_search_panel'):
        result = SearchPanel.prompt(initial_query)
        if not result:
            return None
        return build_query_from_result(result)
    else:
        # Legacy: straight keyboard - return unified structure
        kb = xbmc.Keyboard(initial_query, L(36200))
        kb.doModal()
        if not kb.isConfirmed():
            return None
        # Build legacy result in unified format
        legacy_result = {
            'content_type': CONTENT_ALL,
            'fields': FIELDS_BOTH,
            'match_mode': MATCH_ANY,
            'query': kb.getText()
        }
        return build_query_from_result(legacy_result)


def build_query_from_result(result):
    """Convert search panel result to query parameters"""
    # Map result into search engine parameters
    scope = []
    if result['fields'] in (FIELDS_TITLE, FIELDS_BOTH):
        scope.append('title')
    if result['fields'] in (FIELDS_PLOT, FIELDS_BOTH):
        scope.append('plot')

    # Map content type to media type
    media_type_map = {
        CONTENT_MOVIES: 'movie',
        CONTENT_SERIES: 'episode',
        CONTENT_ALL: 'all'
    }
    
    # Map match mode to match logic
    match_logic_map = {
        MATCH_ANY: 'any',
        MATCH_ALL: 'all',
        MATCH_PHRASE: 'phrase'
    }

    return {
        'type': media_type_map.get(result['content_type'], 'all'),
        'scope': scope,  # e.g., ['title','plot']
        'match': match_logic_map[result['match_mode']],
        'q': result['query'].strip()
    }
