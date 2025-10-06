#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Integrated Search Flow
Handles toggling between local and AI search panels
"""

import xbmc
import xbmcaddon
import xbmcgui
from typing import Optional, Dict, Any
from lib.gui.search_panel import SearchPanel
from lib.gui.ai_search_panel import AISearchPanel
from lib.remote.ai_search_client import AISearchClient
from lib.data.query_manager import get_query_manager
from lib.utils.kodi_log import get_kodi_logger

ADDON = xbmcaddon.Addon()
L = ADDON.getLocalizedString


def start_integrated_search_flow(initial_mode='local'):
    """
    Start integrated search flow with toggle support
    
    Args:
        initial_mode: 'local' or 'ai' to determine starting panel
        
    Returns:
        Dict with search results and metadata, or None if cancelled
    """
    logger = get_kodi_logger('lib.search.integrated_search')
    current_mode = initial_mode
    
    while True:
        if current_mode == 'local':
            # Show local search panel
            result = SearchPanel.prompt()
            
            if not result:
                # User cancelled
                return None
            
            # Check for mode switch
            if isinstance(result, dict) and result.get('switch_to_ai'):
                logger.info("User switched from local to AI search")
                current_mode = 'ai'
                continue
            
            # Check for navigate_away (search history selection)
            if isinstance(result, dict) and result.get('navigate_away'):
                return result
            
            # Regular local search result
            return {
                'mode': 'local',
                'result': result
            }
            
        elif current_mode == 'ai':
            # Show AI search panel
            result = AISearchPanel.prompt()
            
            if not result:
                # User cancelled
                return None
            
            # Check for mode switch
            if isinstance(result, dict) and result.get('switch_to_local'):
                logger.info("User switched from AI to local search")
                current_mode = 'local'
                continue
            
            # Regular AI search result
            return {
                'mode': 'ai',
                'result': result
            }


def execute_ai_search_and_save(query: str, max_results: int = 20) -> Optional[int]:
    """
    Execute AI search and save results as a list
    
    Args:
        query: Natural language search query
        max_results: Maximum number of results
        
    Returns:
        List ID if successful, None otherwise
    """
    logger = get_kodi_logger('lib.search.integrated_search')
    
    try:
        # Call AI search API
        ai_client = AISearchClient()
        response = ai_client.search_movies(query, limit=max_results)
        
        if not response or not response.get('success'):
            error_msg = response.get('error', 'Unknown error') if response else 'No response'
            logger.error(f"AI search failed: {error_msg}")
            xbmcgui.Dialog().notification(
                'LibraryGenie',
                f'AI search failed: {error_msg}',
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return None
        
        results = response.get('results', [])
        if not results:
            xbmcgui.Dialog().notification(
                'LibraryGenie',
                'No results found for your query',
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            return None
        
        logger.info(f"AI search returned {len(results)} results")
        
        # Save as a list in AI Search Results folder
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return None
        
        # Get or create AI Search Results folder
        folder_id = query_manager.get_or_create_folder("AI Search Results", create_if_missing=True)
        if not folder_id:
            logger.error("Failed to create AI Search Results folder")
            return None
        
        # Create list name with query
        list_name = f"AI: {query[:50]}"  # Limit to 50 chars
        
        # Create the list
        list_id = query_manager.create_list(list_name, folder_id=folder_id)
        if not list_id:
            logger.error("Failed to create AI search results list")
            return None
        
        # Add results to list
        # Convert AI results to media items format
        media_items = []
        for result in results:
            # AI search returns IMDb IDs - we need to match them to our library
            imdb_id = result.get('imdb_id', '').strip()
            if not imdb_id or not imdb_id.startswith('tt'):
                continue
            
            # Find matching media item in our database
            from lib.data.connection_manager import get_connection_manager
            conn_manager = get_connection_manager()
            db_result = conn_manager.execute_query(
                "SELECT id FROM media_items WHERE imdbnumber = ? LIMIT 1",
                (imdb_id,)
            )
            
            if db_result and len(db_result) > 0:
                media_id = db_result[0]['id']
                media_items.append({'media_id': media_id})
        
        if not media_items:
            logger.warning("No AI search results matched items in library")
            xbmcgui.Dialog().notification(
                'LibraryGenie',
                f'Found {len(results)} AI results, but none are in your library',
                xbmcgui.NOTIFICATION_WARNING,
                5000
            )
            # Still return the list ID so user can see it's created
            return list_id
        
        # Add items to list
        for item in media_items:
            query_manager.add_media_to_list(list_id, item['media_id'])
        
        logger.info(f"Added {len(media_items)} items to AI search list {list_id}")
        xbmcgui.Dialog().notification(
            'LibraryGenie',
            f'Found {len(media_items)} matching movies',
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return list_id
        
    except Exception as e:
        logger.error(f"Error executing AI search: {e}")
        import traceback
        logger.error(traceback.format_exc())
        xbmcgui.Dialog().notification(
            'LibraryGenie',
            f'AI search error: {str(e)}',
            xbmcgui.NOTIFICATION_ERROR,
            5000
        )
        return None
