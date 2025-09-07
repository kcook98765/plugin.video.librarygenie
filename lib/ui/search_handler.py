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

from ..search import get_simple_search_engine, get_simple_query_interpreter
from ..data.query_manager import get_query_manager
from ..data.connection_manager import get_connection_manager
from ..search.simple_search_engine import SimpleSearchEngine
from ..utils.logger import get_logger
from .localization import L
from .search_history_manager import SearchHistoryManager
from .menu_builder import MenuBuilder

try:
    from .response_types import DirectoryResponse
except Exception:
    DirectoryResponse = None


class SearchHandler:
    """Simple search handler with dialog-based keyword search"""

    def __init__(self, addon_handle: Optional[int] = None):
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)
        self.query_manager = get_query_manager()
        self.conn_manager = get_connection_manager()
        self.search_engine = SimpleSearchEngine()
        self.query_interpreter = get_simple_query_interpreter()
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')

    def prompt_and_search(self, context: PluginContext) -> bool:
        """Main entry point for simple search"""
        self._ensure_handle_from_context(context)

        # Step 1: Get search keywords
        search_terms = self._prompt_for_search_terms()
        if not search_terms:
            self._info("No search terms entered")
            return self._maybe_dir_response([], False, "No search terms provided", content_type="movies")

        # Step 2: Use default search options (always search both title and plot)
        search_options = {"search_scope": "both", "match_logic": "all"}

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
                L(33002),  # "Enter search terms"
                type=xbmcgui.INPUT_ALPHANUM
            )
            return terms.strip() if terms and terms.strip() else None
        except Exception as e:
            self._warn(f"Search terms input failed: {e}")
            return None



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
                self._info("No results to save to search history")
                return

            self._info(f"Saving search history for '{search_terms}' with {results.total_count} results")

            # Create search history list with simplified description
            query_desc = f"{search_terms}"

            list_id = self.query_manager.create_search_history_list(
                query=query_desc,
                search_type="simple",
                result_count=results.total_count
            )

            if list_id:
                self._info(f"Created search history list with ID: {list_id}")
                # Convert results to format expected by query manager
                search_results = {"items": results.items}
                added = self.query_manager.add_search_results_to_list(list_id, search_results)
                if added > 0:
                    self._info(f"Successfully added {added} items to search history list {list_id}")
                    # Use f-string formatting to avoid string formatting errors
                    base_message = L(32102)  # Should be "Search saved: %d items" or similar
                    if '%d' in base_message:
                        formatted_message = base_message % added
                    elif '{' in base_message:
                        formatted_message = base_message.format(added)
                    else:
                        # Fallback message
                        formatted_message = f"Search saved: {added} items"
                    self._notify_info(formatted_message, ms=3000)
                else:
                    self._warn(f"Failed to add items to search history list {list_id}")
            else:
                self._warn("Failed to create search history list")

        except Exception as e:
            self._error(f"Failed to save search history: {e}")
            import traceback
            self._error(f"Search history save traceback: {traceback.format_exc()}")

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
        self._notify_info(L(32101) % search_terms)  # "No results found for '%s'"

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

    def ai_search_prompt(self, context: PluginContext) -> bool:
        """Prompt user for AI search query and perform AI search"""
        try:
            context.logger.info("AI SEARCH: Starting AI search prompt")

            # Get search query from user
            dialog = xbmcgui.Dialog()
            query = dialog.input(L(33001), type=xbmcgui.INPUT_ALPHANUM)  # "Enter search query"

            if not query or not query.strip():
                context.logger.info("AI SEARCH: User cancelled or entered empty query")
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False

            query = query.strip()
            context.logger.info(f"AI SEARCH: User entered query: '{query}'")

            # Perform AI search
            return self._perform_ai_search(query, context)

        except Exception as e:
            context.logger.error(f"AI SEARCH: Error in ai_search_prompt: {e}")
            import traceback
            context.logger.error(f"AI SEARCH: Traceback: {traceback.format_exc()}")
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False

    def _perform_ai_search(self, query: str, context: PluginContext) -> bool:
        """Perform AI search and display results"""
        try:
            from ..remote.ai_search_client import get_ai_search_client

            context.logger.info(f"AI SEARCH: Performing AI search for: '{query}'")

            # Get AI search client
            ai_client = get_ai_search_client()

            # Check if activated
            if not ai_client.is_activated():
                context.logger.warning("AI SEARCH: AI search not activated")
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "AI Search not activated",
                    xbmcgui.NOTIFICATION_WARNING,
                    5000
                )
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search", f"Searching for: {query}")
            progress.update(50)

            # Perform search
            results = ai_client.search_movies(query, limit=50)
            progress.close()

            if not results or not results.get('success'):
                error_msg = results.get('error', 'Unknown error') if results else 'No response from server'
                context.logger.error(f"AI SEARCH: Search failed: {error_msg}")
                xbmcgui.Dialog().notification(
                    "AI Search",
                    f"Search failed: {error_msg}",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False

            search_results = results.get('results', [])
            context.logger.info(f"AI SEARCH: Found {len(search_results)} results")

            if not search_results:
                xbmcgui.Dialog().notification(
                    "AI Search",
                    "No results found",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
                return False

            # Display results using movie menu
            menu_builder = MenuBuilder()
            menu_builder.build_movie_menu(
                search_results,
                context.addon_handle,
                context.base_url,
                breadcrumb_path=f"AI Search > {query}",
                category=f"AI Search Results"
            )

            context.logger.info("AI SEARCH: Successfully displayed AI search results")
            return True

        except Exception as e:
            context.logger.error(f"AI SEARCH: Error performing AI search: {e}")
            import traceback
            context.logger.error(f"AI SEARCH: Traceback: {traceback.format_exc()}")
            xbmcgui.Dialog().notification(
                "AI Search",
                "Search error occurred",
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False