#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Integrated Search Flow
Handles toggling between local and AI search panels
"""

import xbmc
import xbmcaddon
import xbmcgui
from datetime import datetime
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
            
            # Check for navigate_away (search history selection)
            if isinstance(result, dict) and result.get('navigate_away'):
                return result
            
            # Regular AI search result
            return {
                'mode': 'ai',
                'result': result
            }


def execute_ai_search_and_save(query: str, max_results: Optional[int] = None, mode: str = 'hybrid', 
                                use_llm: bool = False, debug_intent: bool = False) -> Optional[int]:
    """
    Execute AI search and save results as a list
    
    Args:
        query: Natural language search query
        max_results: Maximum number of results (None = use setting, default)
        mode: Search mode - "bm25" or "hybrid" (default: hybrid)
        use_llm: Enable GPT-4 intent extraction (default: False)
        debug_intent: Include detailed diagnostics in response (default: False)
        
    Returns:
        List ID if successful, None otherwise
    """
    logger = get_kodi_logger('lib.search.integrated_search')
    
    try:
        # Get result limit from settings if not provided
        if max_results is None:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            max_results = addon.getSettingInt('ai_search_result_limit')
            if max_results <= 0:
                max_results = 20  # Fallback default
        
        # Call AI search API with new parameters
        ai_client = AISearchClient()
        response = ai_client.search_movies(query, limit=max_results, mode=mode, 
                                          use_llm=use_llm, debug_intent=debug_intent)
        
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
        
        # Save as a list in Search History folder (same as local searches)
        query_manager = get_query_manager()
        if not query_manager.initialize():
            logger.error("Failed to initialize query manager")
            return None
        
        # Get or create Search History folder
        folder_id = query_manager.get_or_create_search_history_folder()
        if not folder_id:
            logger.error("Failed to get Search History folder")
            return None
        
        # Create list name with AI prefix and timestamp (same format as local search)
        timestamp = datetime.now().strftime("%m/%d %H:%M")
        display_query = query if len(query) <= 20 else f"{query[:17]}..."
        base_list_name = f"AI: '{display_query}' ({timestamp})"
        
        # Truncate if too long
        if len(base_list_name) > 60:
            base_list_name = base_list_name[:57] + "..."
        
        # Try to create the list with fallback for duplicate names
        list_id = None
        for attempt in range(11):  # Try base name + 10 numbered attempts
            if attempt == 0:
                list_name = base_list_name
            else:
                list_name = f"{base_list_name} ({attempt})"
                # Truncate if adding number made it too long
                if len(list_name) > 60:
                    # Make room for the number suffix
                    truncated_base = base_list_name[:54 - len(str(attempt))] + "..."
                    list_name = f"{truncated_base} ({attempt})"
            
            result = query_manager.create_list(list_name, folder_id=folder_id)
            
            # Check if creation succeeded
            if isinstance(result, dict):
                if result.get('error') == 'duplicate_name':
                    logger.debug(f"List name '{list_name}' already exists, trying next variation")
                    continue
                elif result.get('id'):
                    # Success - extract ID from dict
                    list_id = int(result['id'])
                    logger.info(f"Created AI search list: '{list_name}'" + (f" (attempt {attempt + 1})" if attempt > 0 else ""))
                    break
                else:
                    logger.error(f"Failed to create list '{list_name}': {result}")
                    break
            elif isinstance(result, int):
                # Also handle if it returns an int directly
                list_id = result
                logger.info(f"Created AI search list: '{list_name}'" + (f" (attempt {attempt + 1})" if attempt > 0 else ""))
                break
            else:
                logger.error(f"Failed to create list '{list_name}': {result}")
                break
        
        if not list_id:
            logger.error("Failed to create AI search results list after 11 attempts")
            return None
        
        # Add results to list
        # Fetch full media item details from database
        from lib.data.connection_manager import get_connection_manager
        conn_manager = get_connection_manager()
        
        matched_items = []
        for result in results:
            # AI search returns IMDb IDs - we need to match them to our library
            imdb_id = result.get('imdb_id', '').strip()
            if not imdb_id or not imdb_id.startswith('tt'):
                continue
            
            # Fetch full media item details
            db_result = conn_manager.execute_query(
                """SELECT * FROM media_items 
                   WHERE imdbnumber = ? AND is_removed = 0 
                   LIMIT 1""",
                (imdb_id,)
            )
            
            if db_result and len(db_result) > 0:
                # Convert database row to dict with all fields
                item_dict = dict(db_result[0])
                
                # Add search score from AI result (for score display in search history)
                score = result.get('score')
                if score is not None:
                    item_dict['search_score'] = score
                    logger.debug(f"Added score {score} to item {item_dict.get('title', 'Unknown')}")
                
                matched_items.append(item_dict)
        
        if not matched_items:
            logger.warning("No AI search results matched items in library")
            xbmcgui.Dialog().notification(
                'LibraryGenie',
                f'Found {len(results)} AI results, but none are in your library',
                xbmcgui.NOTIFICATION_WARNING,
                5000
            )
            # Still return the list ID so user can see it's created
            return list_id
        
        # Add items to list using the same method as local search
        search_results = {"items": matched_items}
        added_count = query_manager.add_search_results_to_list(list_id, search_results)
        
        logger.info(f"Added {added_count} items to AI search list {list_id}")
        xbmcgui.Dialog().notification(
            'LibraryGenie',
            f'Found {added_count} matching movies',
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
