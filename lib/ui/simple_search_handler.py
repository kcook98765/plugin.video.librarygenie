#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Search Handler
Simplified search interface with dialog-based options for keyword search across title and plot fields
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin_context import PluginContext
    from .response_types import DirectoryResponse

import xbmcgui
import xbmcaddon
import xbmc
import xbmcplugin

from ..search.simple_search_engine import get_simple_search_engine
from ..search.simple_query_interpreter import get_simple_query_interpreter
from ..data.query_manager import get_query_manager
from ..utils.logger import get_logger

try:
    from .response_types import DirectoryResponse
except Exception:
    DirectoryResponse = None


class SimpleSearchHandler:
    """Simple search handler with dialog-based keyword search"""

    def __init__(self, addon_handle: Optional[int] = None):
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)
        self.search_engine = get_simple_search_engine()
        self.query_interpreter = get_simple_query_interpreter()
        self.query_manager = get_query_manager()
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')

    def prompt_and_search(self, context=None) -> Optional[Any]:
        """Main entry point for simple search with dialog prompts"""
        self._ensure_handle_from_context(context)
        
        # Step 1: Get search keywords
        search_terms = self._prompt_for_search_terms()
        if not search_terms:
            self._info("No search terms entered")
            return self._maybe_dir_response([], False, "No search terms provided", content_type="movies")

        # Step 2: Get search options
        search_options = self._prompt_for_search_options()
        if search_options is None:
            self._info("User cancelled search options")
            return self._maybe_dir_response([], False, "Search cancelled", content_type="movies")

        # Step 3: Execute search
        results = self._execute_simple_search(search_terms, search_options, context)
        
        # Step 4: Save results and redirect
        if results.total_count > 0:
            self._save_search_history(search_terms, search_options, results)
            if not self._try_redirect_to_saved_search_list():
                self._error("Failed to redirect to saved search list")
                return self._maybe_dir_response([], False, "Search display failed", content_type="movies")
        else:
            self._show_no_results_message(search_terms)

        return self._maybe_dir_response(results.items, results.total_count > 0, 
                                      results.query_summary, content_type="movies")

    def _prompt_for_search_terms(self) -> Optional[str]:
        """Prompt user for search keywords"""
        try:
            terms = xbmcgui.Dialog().input(
                "Enter keywords to search for:",
                type=xbmcgui.INPUT_ALPHANUM
            )
            return terms.strip() if terms and terms.strip() else None
        except Exception as e:
            self._warn(f"Search terms input failed: {e}")
            return None

    def _prompt_for_search_options(self) -> Optional[Dict[str, str]]:
        """Prompt user for search scope and match logic"""
        try:
            # Search scope options
            scope_options = [
                "Search movie titles and plots (recommended)",
                "Search movie titles only", 
                "Search plot descriptions only",
                "Advanced: Find ANY keywords (more results)",
                "Advanced: Find ALL keywords (precise results)"
            ]
            
            selected = xbmcgui.Dialog().select("Search Options", list(scope_options))
            if selected < 0:  # User cancelled
                return None
            
            # Map selection to options
            if selected == 0:  # titles and plots, all keywords
                return {"search_scope": "both", "match_logic": "all"}
            elif selected == 1:  # titles only, all keywords
                return {"search_scope": "title", "match_logic": "all"}
            elif selected == 2:  # plots only, all keywords
                return {"search_scope": "plot", "match_logic": "all"}
            elif selected == 3:  # any keywords, both fields
                return {"search_scope": "both", "match_logic": "any"}
            elif selected == 4:  # all keywords, both fields
                return {"search_scope": "both", "match_logic": "all"}
            
            # Default fallback
            return {"search_scope": "both", "match_logic": "all"}
            
        except Exception as e:
            self._warn(f"Search options input failed: {e}")
            return {"search_scope": "both", "match_logic": "all"}

    def _execute_simple_search(self, search_terms: str, options: Dict[str, str], context=None):
        """Execute the simplified search"""
        try:
            # Parse query
            query_params = {
                "search_scope": options["search_scope"],
                "match_logic": options["match_logic"]
            }
            
            # Add scope info if searching within a list
            if context and hasattr(context, 'scope_type'):
                query_params["scope_type"] = context.scope_type
                query_params["scope_id"] = context.scope_id
            
            query = self.query_interpreter.parse_query(search_terms, **query_params)
            
            # Execute search
            results = self.search_engine.search(query)
            
            self._info(f"Simple search completed: {results.total_count} results for '{search_terms}'")
            return results
            
        except Exception as e:
            self._error(f"Simple search execution failed: {e}")
            from ..search.simple_search_engine import SimpleSearchResult
            result = SimpleSearchResult()
            result.query_summary = "Search error"
            return result

    def _save_search_history(self, search_terms: str, options: Dict[str, str], results):
        """Save search results to search history"""
        try:
            if results.total_count == 0:
                return
                
            # Create search history list
            scope_desc = {
                "title": "titles", 
                "plot": "plots", 
                "both": "titles+plots"
            }.get(options["search_scope"], "both")
            
            logic_desc = options["match_logic"].upper()
            query_desc = f"{search_terms} ({logic_desc} in {scope_desc})"
            
            list_id = self.query_manager.create_search_history_list(
                query=query_desc, 
                search_type="simple", 
                result_count=results.total_count
            )
            
            if list_id:
                # Convert results to format expected by query manager
                search_results = {"items": results.items}
                added = self.query_manager.add_search_results_to_list(list_id, search_results)
                if added > 0:
                    self._notify_info(f"Search saved: {added} items", ms=3000)
                    
        except Exception as e:
            self._warn(f"Failed to save search history: {e}")

    def _try_redirect_to_saved_search_list(self) -> bool:
        """Redirect to the most recent search history list"""
        try:
            search_folder_id = self.query_manager.get_or_create_search_history_folder()
            lists = self.query_manager.get_lists_in_folder(search_folder_id)
            if not lists:
                return False

            latest = lists[0]
            list_id = latest.get('id')
            if not list_id:
                return False

            list_url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"
            xbmc.executebuiltin(f'Container.Update("{list_url}",replace)')
            self._end_directory(succeeded=True, update=True)
            return True
            
        except Exception as e:
            self._warn(f"Redirect to saved search list failed: {e}")
            return False

    def _show_no_results_message(self, search_terms: str):
        """Show message when no results found"""
        self._notify_info(f"No results found for '{search_terms}'")

    # Helper methods
    def _ensure_handle_from_context(self, context):
        """Extract addon handle from context if provided"""
        if context and hasattr(context, 'addon_handle'):
            self.addon_handle = context.addon_handle

    def _end_directory(self, succeeded: bool, update: bool):
        """End directory listing"""
        if xbmcplugin and self.addon_handle is not None:
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=succeeded, updateListing=update)

    def _maybe_dir_response(self, items: List[Dict[str, Any]], success: bool, 
                           message: str, content_type: str = "movies") -> Optional[Any]:
        """Return DirectoryResponse if available"""
        if DirectoryResponse is None:
            return None
        return DirectoryResponse(items=items, success=success, content_type=content_type)

    # Logging methods
    def _info(self, msg: str):
        self.logger.info(msg)

    def _warn(self, msg: str):
        self.logger.warning(msg)

    def _error(self, msg: str):
        self.logger.error(msg)

    def _notify_info(self, msg: str, ms: int = 4000):
        xbmcgui.Dialog().notification("LibraryGenie", msg, xbmcgui.NOTIFICATION_INFO, ms)

    def _notify_error(self, msg: str, ms: int = 4000):
        xbmcgui.Dialog().notification("LibraryGenie", msg, xbmcgui.NOTIFICATION_ERROR, ms)