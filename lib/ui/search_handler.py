#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Simple Search Handler
Simplified search interface with dialog-based options for keyword search across title and plot fields
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.ui.plugin_context import PluginContext
    from lib.ui.response_types import DirectoryResponse

import xbmcgui
import xbmcaddon
import xbmc
import xbmcplugin

from lib.search import get_simple_search_engine, get_simple_query_interpreter
from lib.data.query_manager import get_query_manager
from lib.data.connection_manager import get_connection_manager
from lib.search.simple_search_engine import SimpleSearchEngine
from lib.utils.kodi_log import get_kodi_logger
from lib.ui.localization import L
from lib.ui.menu_builder import MenuBuilder

try:
    from lib.ui.response_types import DirectoryResponse
except Exception:
    DirectoryResponse = None


class SearchHandler:
    """Simple search handler with dialog-based keyword search"""

    def __init__(self, addon_handle: Optional[int] = None):
        self.addon_handle = addon_handle
        self.logger = get_kodi_logger('lib.ui.search_handler')
        self.query_manager = get_query_manager()
        self.conn_manager = get_connection_manager()
        self.search_engine = SimpleSearchEngine()
        self.query_interpreter = get_simple_query_interpreter()
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')

    def prompt_and_search(self, context: PluginContext, media_scope: str = "movie") -> bool:
        """Main entry point for simple search"""
        self._ensure_handle_from_context(context)

        # Step 1: Get search keywords
        search_terms = self._prompt_for_search_terms()
        if not search_terms:
            self._info("No search terms entered")
            self._end_directory(succeeded=False, update=False)
            return False

        # Step 2: Use default search options (always search both title and plot)
        search_options = {"search_scope": "both", "match_logic": "all", "media_scope": media_scope}

        # Step 3: Execute search
        results = self._execute_simple_search(search_terms, search_options, context)

        # Step 4: Save results and render directly (no plugin restart)
        if results.total_count > 0:
            # Save search history and get the created list ID
            list_id = self._save_search_history(search_terms, search_options, results)
            
            if list_id:
                # Directly render the saved search list without Container.Update
                if self._render_saved_search_list_directly(str(list_id), context):
                    self._debug(f"Successfully displayed search results via direct rendering")
                    return True
                else:
                    # Fallback to redirect method if direct rendering fails
                    self._warn("Direct rendering failed, falling back to redirect method")
                    if not self._try_redirect_to_saved_search_list():
                        self._error("Failed to redirect to saved search list")
                        self._end_directory(succeeded=False, update=False)
                        return False
                    return True
            else:
                # Failed to save search history, fallback to redirect method
                self._warn("Failed to save search history, attempting fallback redirect")
                if not self._try_redirect_to_saved_search_list():
                    self._error("Failed to redirect to saved search list")
                    self._end_directory(succeeded=False, update=False)
                    return False
                return True
        else:
            self._show_no_results_message(search_terms)
            self._end_directory(succeeded=True, update=False)
            return True

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
            # Map media scope to media types
            media_scope = options.get("media_scope", "movie")
            if media_scope == "episode":
                media_types = ["episode", "tvshow"]
            else:  # default to movie
                media_types = ["movie"]

            # Parse query
            query_params = {
                "search_scope": options["search_scope"],
                "match_logic": options["match_logic"],
                "media_types": media_types
            }

            # Add scope info if searching within a list
            if context and hasattr(context, 'scope_type'):
                query_params["scope_type"] = context.scope_type
                query_params["scope_id"] = context.scope_id

            query = self.query_interpreter.parse_query(search_terms, **query_params)

            # Execute search
            results = self.search_engine.search(query)

            self._debug(f"Simple search completed: {results.total_count} results for '{search_terms}'")
            return results

        except Exception as e:
            self._error(f"Simple search execution failed: {e}")
            from lib.search.simple_search_engine import SimpleSearchResult
            result = SimpleSearchResult()
            result.query_summary = "Search error"
            return result

    def _save_search_history(self, search_terms: str, options: Dict[str, str], results):
        """Save search results to search history and return the created list ID"""
        try:
            if results.total_count == 0:
                self._debug("No results to save to search history")
                return None

            self._debug(f"Saving search history for '{search_terms}' with {results.total_count} results")

            # Create search history list with simplified description and media scope prefix
            media_scope = options.get("media_scope", "movie")
            if media_scope == "episode":
                query_desc = f"Episodes: {search_terms}"
                search_type = "episode_simple"
            else:
                query_desc = f"{search_terms}"
                search_type = "simple"

            list_id = self.query_manager.create_search_history_list(
                query=query_desc,
                search_type=search_type,
                result_count=results.total_count
            )

            if list_id:
                self._debug(f"Created search history list with ID: {list_id}")
                # Convert results to format expected by query manager
                search_results = {"items": results.items}
                added = self.query_manager.add_search_results_to_list(list_id, search_results)
                if added > 0:
                    self._debug(f"Successfully added {added} items to search history list {list_id}")
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
                    return list_id  # Return the list ID on success
                else:
                    self._warn(f"Failed to add items to search history list {list_id}")
                    return None
            else:
                self._warn("Failed to create search history list")
                return None

        except Exception as e:
            self._error(f"Failed to save search history: {e}")
            import traceback
            self._error(f"Search history save traceback: {traceback.format_exc()}")
            return None

    def _render_saved_search_list_directly(self, list_id: str, context: PluginContext) -> bool:
        """Directly render saved search list without Container.Update redirect"""
        try:
            self._debug(f"Directly rendering saved search list ID: {list_id}")
            
            # Import and instantiate ListsHandler
            from lib.ui.handler_factory import get_handler_factory
            from lib.ui.response_handler import get_response_handler
            
            factory = get_handler_factory()
            factory.context = context
            lists_handler = factory.get_lists_handler()
            response_handler = get_response_handler()
            
            # Directly call view_list with the saved list ID
            directory_response = lists_handler.view_list(context, list_id)
            
            # Handle the DirectoryResponse
            success = response_handler.handle_directory_response(directory_response, context)
            
            if success:
                self._debug(f"Successfully rendered saved search list {list_id} directly")
                return True
            else:
                self._warn(f"Failed to handle directory response for list {list_id}")
                return False
            
        except Exception as e:
            self._error(f"Error rendering saved search list directly: {e}")
            import traceback
            self._error(f"Direct rendering traceback: {traceback.format_exc()}")
            return False

    def _try_redirect_to_saved_search_list(self) -> bool:
        """Redirect to the most recent search history list"""
        try:
            search_folder_id = self.query_manager.get_or_create_search_history_folder()
            # Ensure folder_id is string type for API compatibility
            folder_id_str = str(search_folder_id) if search_folder_id is not None else None
            lists = self.query_manager.get_lists_in_folder(folder_id_str)
            if not lists:
                return False

            # Find the most recently created list by highest ID (since lists are ordered by name, not creation time)
            # Convert ID to int for proper numeric comparison
            latest = max(lists, key=lambda x: int(x.get('id', 0)))
            list_id = latest.get('id')
            if not list_id:
                return False

            self._debug(f"Redirecting to most recent search history list ID: {list_id}")
            list_url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"
            xbmc.executebuiltin(f'Container.Update("{list_url}",replace)')
            self._end_directory(succeeded=True, update=True)
            return True

        except Exception as e:
            self._warn(f"Redirect to saved search list failed: {e}")
            return False

    def _show_no_results_message(self, search_terms: str):
        """Show message when no results found"""
        self._notify_info(L(32101).format(search_terms))  # "No results found for '{0}'"

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

    def _debug(self, msg: str):
        self.logger.debug(msg)

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
            from lib.ui.ai_search_handler import get_ai_search_handler
            
            context.logger.debug("AI SEARCH: Starting AI search prompt")
            
            # Use the new AI search handler
            ai_search_handler = get_ai_search_handler()
            success = ai_search_handler.prompt_and_search()
            
            # End directory based on success
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=success)
            return success

        except Exception as e:
            context.logger.error("AI SEARCH: Error in ai_search_prompt: %s", e)
            import traceback
            context.logger.error("AI SEARCH: Traceback: %s", traceback.format_exc())
            xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)
            return False