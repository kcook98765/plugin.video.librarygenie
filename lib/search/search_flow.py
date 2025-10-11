#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Flow Controller
Consolidates all search flow logic into a single coordinator
"""

import xbmc
import xbmcaddon
from typing import Optional
from lib.ui.plugin_context import PluginContext
from lib.utils.kodi_log import get_kodi_logger


class NavigationStrategy:
    """Handles navigation to search results based on context"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.search.search_flow.NavigationStrategy')
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')
    
    def navigate_to_results(self, list_id: int, context: PluginContext) -> bool:
        """
        Navigate to search results list using appropriate method
        
        Args:
            list_id: ID of the saved search results list
            context: Plugin context with addon_handle
            
        Returns:
            True if navigation successful
        """
        list_url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"
        
        if context.addon_handle >= 0:
            # Valid handle - direct rendering (Videos window context)
            self.logger.debug(f"Valid handle {context.addon_handle}, rendering directly")
            from lib.ui.handler_factory import get_handler_factory
            from lib.ui.response_handler import get_response_handler
            
            factory = get_handler_factory()
            factory.context = context
            lists_handler = factory.get_lists_handler()
            response_handler = get_response_handler()
            
            directory_response = lists_handler.view_list(context, str(list_id))
            return response_handler.handle_directory_response(directory_response, context)
        else:
            # Invalid handle (RunPlugin from Programs menu) - use ActivateWindow
            self.logger.debug(f"Invalid handle {context.addon_handle}, using ActivateWindow")
            xbmc.executebuiltin(f'ActivateWindow(videos,{list_url},return)')
            return True


class SearchFlowController:
    """Coordinates the complete search flow from dialog to results"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.search.search_flow.SearchFlowController')
        self.navigation_strategy = NavigationStrategy()
    
    def execute_search_flow(self, context: PluginContext, initial_mode: str = 'local') -> bool:
        """
        Execute complete search flow: dialog → search → save → navigate
        
        Args:
            context: Plugin context
            initial_mode: 'local' or 'ai' for initial search mode
            
        Returns:
            True if search completed (or cancelled cleanly), False on error
        """
        from lib.search.integrated_search import start_integrated_search_flow, execute_ai_search_and_save
        from lib.search.search_router import build_query_from_result
        from lib.search.simple_query_interpreter import get_simple_query_interpreter
        from lib.search.simple_search_engine import SimpleSearchEngine
        from lib.ui.handler_factory import get_handler_factory
        
        try:
            # Step 1: Show dialog and get search input
            search_result = start_integrated_search_flow(initial_mode)
            
            if not search_result:
                # User cancelled - clean exit
                self.logger.info("User cancelled search")
                return True
            
            # Step 2: Handle search history navigation (if selected from dialog)
            if isinstance(search_result, dict) and search_result.get('navigate_away'):
                target_url = search_result.get('target')
                if target_url:
                    xbmc.executebuiltin('Dialog.Close(all,true)')
                    xbmc.executebuiltin(f'ActivateWindow(Videos,{target_url},return)')
                return True
            
            # Step 3: Execute search based on mode
            if isinstance(search_result, dict) and search_result.get('mode') == 'ai':
                # AI search mode
                return self._handle_ai_search(search_result, context)
            elif isinstance(search_result, dict) and search_result.get('mode') == 'local':
                # Local search mode
                return self._handle_local_search(search_result, context)
            else:
                self.logger.error(f"Unknown search result type: {search_result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Search flow failed: {e}", exc_info=True)
            return False
    
    def _handle_ai_search(self, search_result: dict, context: PluginContext) -> bool:
        """Handle AI search execution and navigation"""
        from lib.search.integrated_search import execute_ai_search_and_save
        import xbmcgui
        
        ai_result = search_result.get('result', {})
        query = ai_result.get('query', '').strip()
        
        if not query:
            self.logger.warning("Empty AI search query")
            return True
        
        # Close all dialogs
        xbmc.executebuiltin('Dialog.Close(all,true)')
        
        # Use DialogProgressBG (addon-friendly busy indicator)
        progress = xbmcgui.DialogProgressBG()
        progress.create("LibraryGenie", "Searching...")
        
        try:
            # Execute AI search and save results
            list_id = execute_ai_search_and_save(
                query,
                max_results=ai_result.get('max_results', 20),
                mode=ai_result.get('mode', 'hybrid'),
                use_llm=ai_result.get('use_llm', False),
                debug_intent=ai_result.get('debug_intent', False)
            )
            
            if list_id:
                # Navigate to results
                self.logger.info(f"AI search successful, navigating to list {list_id}")
                return self.navigation_strategy.navigate_to_results(list_id, context)
            else:
                self.logger.warning("AI search returned no list ID")
                return True
        finally:
            # Always close progress dialog
            progress.close()

    
    def _handle_local_search(self, search_result: dict, context: PluginContext) -> bool:
        """Handle local search execution and navigation"""
        from lib.search.search_router import build_query_from_result
        from lib.search.simple_query_interpreter import get_simple_query_interpreter
        from lib.search.simple_search_engine import SimpleSearchEngine
        from lib.ui.handler_factory import get_handler_factory
        import xbmcgui
        
        local_result = search_result.get('result')
        query_params = build_query_from_result(local_result)
        
        # Close all dialogs
        xbmc.executebuiltin('Dialog.Close(all,true)')
        
        # Use DialogProgressBG (addon-friendly busy indicator)
        progress = xbmcgui.DialogProgressBG()
        progress.create("LibraryGenie", "Searching...")
        
        try:
            # Convert to SimpleSearchQuery
            interpreter = get_simple_query_interpreter()
            
            # Map media type string to list
            media_type_map = {
                'all': ['movie', 'episode', 'tvshow'],
                'movie': ['movie'],
                'episode': ['episode', 'tvshow']
            }
            media_types = media_type_map.get(query_params.get('type', 'all'), ['movie'])
            
            # Map scope list to search_scope string
            scope_list = query_params.get('scope', ['title', 'plot'])
            if set(scope_list) == {'title', 'plot'}:
                search_scope = 'both'
            elif 'title' in scope_list:
                search_scope = 'title'
            elif 'plot' in scope_list:
                search_scope = 'plot'
            else:
                search_scope = 'both'
            
            # Parse query
            search_query = interpreter.parse_query(
                query_params['q'],
                media_types=media_types,
                search_scope=search_scope,
                match_logic=query_params.get('match', 'all')
            )
            
            # Execute search
            engine = SimpleSearchEngine()
            results = engine.search(search_query)
            
            if results.total_count > 0:
                # Save to history and navigate to results
                factory = get_handler_factory()
                factory.context = context
                search_handler = factory.get_search_handler()
                
                list_id = search_handler._save_search_history(query_params['q'], {}, results)
                
                if list_id:
                    self.logger.info(f"Local search successful, navigating to list {list_id}")
                    return self.navigation_strategy.navigate_to_results(list_id, context)
            
            # No results - just return success
            self.logger.info("Local search completed with no results")
            return True
        finally:
            # Always close progress dialog
            progress.close()
