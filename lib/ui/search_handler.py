#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Handler
Handles search operations and result display
"""

import xbmcgui
import xbmcplugin
from .plugin_context import PluginContext
from .response_types import DirectoryResponse
from ..search.local_engine import LocalSearchEngine
from ..auth.state import is_authorized


class SearchHandler:
    """Handles search operations"""

    def __init__(self):
        self.local_engine = LocalSearchEngine()

    def prompt_and_search(self, context: PluginContext) -> DirectoryResponse:
        """Prompt user for search query and display results"""
        # Get search query from user
        query = xbmcgui.Dialog().input(
            context.addon.getLocalizedString(35018),  # "Search"
            type=xbmcgui.INPUT_ALPHANUM
        )

        if not query or not query.strip():
            context.logger.info("Empty query - returning to menu")
            return DirectoryResponse(
                items=[],
                success=False,
                message="No search query provided"
            )

        query = query.strip()
        context.logger.debug(f"Processing search query: '{query}'")

        # Determine search type based on authorization
        if context.is_authorized:
            # For authorized users, could offer remote search
            # For now, use local search
            results = self._search_local(query, context)
        else:
            # Non-authorized users use local search
            results = self._search_local(query, context)

        # Display results
        return self._display_results(results, query, context)

    def _search_local(self, query: str, context: PluginContext) -> dict:
        """Perform local search"""
        try:
            context.logger.debug(f"Starting local search for: '{query}'")
            results = self.local_engine.search(query, limit=200)

            if results:
                result_count = len(results.get('items', []))
                context.logger.info(f"Local search completed: {result_count} items found")
                results['used_remote'] = False
                return results
            else:
                context.logger.warning("Local search returned empty results")
                return {'items': [], 'total': 0, 'used_remote': False}

        except Exception as e:
            context.logger.error(f"Local search failed: {e}")
            return {'items': [], 'total': 0, 'used_remote': False, 'error': str(e)}

    def _display_results(self, results: dict, query: str, context: PluginContext) -> DirectoryResponse:
        """Display search results"""
        items = results.get('items', [])

        if not items:
            # Show no results notification
            xbmcgui.Dialog().notification(
                context.addon.getLocalizedString(35002),  # "LibraryGenie"
                context.addon.getLocalizedString(35020) % query,  # "No results for '%s'"
                xbmcgui.NOTIFICATION_INFO
            )

            # End directory
            xbmcplugin.endOfDirectory(
                context.addon_handle,
                succeeded=True,
                updateListing=False,
                cacheToDisc=False
            )

            return DirectoryResponse(
                items=[],
                success=True,
                message=f"No results found for '{query}'"
            )

        # Build directory items for search results
        menu_items = []
        for item in items:
            # Build display title
            title = item.get('title', 'Unknown')
            year = item.get('year')
            display_title = f"{title} ({year})" if year else title

            # Create context menu
            context_menu = []
            if item.get('kodi_id'):
                add_url = f"RunPlugin({context.base_url}?action=add_to_list&kodi_id={item['kodi_id']})"
                context_menu.append(("Add to List", add_url))

            list_item = xbmcgui.ListItem(label=display_title)
            list_item.setInfo('video', {
                'title': title,
                'year': year,
                'plot': item.get('plot', ''),
                'rating': item.get('rating', 0.0)
            })

            # Set art if available
            if item.get('art'):
                list_item.setArt(item['art'])

            # Add context menu
            if context_menu:
                list_item.addContextMenuItems(context_menu)

            # Determine URL for playback
            if item.get('kodi_id'):
                # Library item
                url = f"videodb://movies/titles/{item['kodi_id']}"
                is_folder = False
            else:
                # External item - create plugin URL
                url = context.build_url('play_external', item_id=item.get('id', ''))
                is_folder = False

            xbmcplugin.addDirectoryItem(
                context.addon_handle,
                url,
                list_item,
                is_folder
            )

            menu_items.append({
                'title': display_title,
                'url': url,
                'is_folder': is_folder,
                'item_data': item
            })

        # Set content type
        xbmcplugin.setContent(context.addon_handle, "movies")

        # End directory
        xbmcplugin.endOfDirectory(
            context.addon_handle,
            succeeded=True,
            updateListing=False,
            cacheToDisc=False
        )

        context.logger.info(f"Displayed {len(menu_items)} search results for '{query}'")

        return DirectoryResponse(
            items=menu_items,
            success=True,
            content_type="movies",
            message=f"Found {len(items)} results for '{query}'"
        )


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Handler UI
Provides UI bridge for search functionality with remote/local engine selection
"""

from __future__ import annotations

from typing import Dict, Any, List

import xbmcgui
import xbmcaddon
import xbmcplugin

from ..search.local_engine import LocalSearchEngine
from ..remote.search_client import search_remote, RemoteError
from ..auth.state import is_authorized
from ..auth.auth_helper import get_auth_helper
from ..ui.session_state import get_session_state
from ..data.query_manager import get_query_manager
from ..ui.listitem_builder import ListItemBuilder
from ..utils.logger import get_logger


class SearchHandler:
    """Handles search UI and result display with engine switching"""

    def __init__(self, addon_handle):
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)
        self.local_engine = LocalSearchEngine()
        self._remote_fallback_notified = False
        self.query_manager = get_query_manager()
        self.addon_id = xbmcaddon.Addon().getAddonInfo('id')

    def prompt_and_show(self):
        """Prompt user for search query and show results"""
        self.logger.debug("Starting search prompt flow")

        # Log call stack (filtered to addon paths)
        import traceback
        import os

        stack = traceback.extract_stack()
        addon_stack = []
        for frame in stack:
            if any(path in frame.filename for path in ['lib/', 'plugin.py', 'service.py']):
                # Show relative path for readability
                rel_path = os.path.basename(frame.filename)
                addon_stack.append(f"{rel_path}:{frame.lineno} in {frame.name}")

        if addon_stack:
            self.logger.debug(f"Call stack (addon only): {' -> '.join(addon_stack[-5:])}")  # Last 5 frames

        # Log current window state
        try:
            import xbmc
            dialog_video_info_active = xbmc.getCondVisibility("Window.IsActive(DialogVideoInfo.xml)")
            keyboard_active = xbmc.getCondVisibility("Window.IsActive(DialogKeyboard.xml)")
            current_window = xbmc.getInfoLabel("System.CurrentWindow")
            container_path = xbmc.getInfoLabel("Container.FolderPath")
            container_label = xbmc.getInfoLabel("Container.FolderName")

            self.logger.debug(f"Window state at search entry:")
            self.logger.debug(f"  Current window: {current_window}")
            self.logger.debug(f"  Container path: {container_path}")
            self.logger.debug(f"  Container label: {container_label}")
            self.logger.debug(f"  DialogVideoInfo active: {dialog_video_info_active}")
            self.logger.debug(f"  Keyboard dialog active: {keyboard_active}")

            # PROTECTION: Don't open search dialog if DialogVideoInfo is active
            # EXCEPT when we're restoring from a hijacked info dialog (detect by XSP path)
            if dialog_video_info_active:
                # Check if we're in a hijack restoration scenario
                is_hijack_restoration = container_path and container_path.endswith("lg_hijack_debug.xsp")

                if is_hijack_restoration:
                    self.logger.info("🔄 HIJACK RESTORATION: Restoring previous search results instead of prompting")

                    # Try to restore cached search results from session state
                    try:
                        from .session_state import get_session_state
                        session = get_session_state()

                        if hasattr(session, 'last_search_results') and session.last_search_results:
                            self.logger.info(f"Restoring cached search results for query: '{getattr(session, 'last_search_query', 'unknown')}'")
                            self._display_results(session.last_search_results, getattr(session, 'last_search_query', ''))
                            return
                        else:
                            self.logger.warning("No cached search results found, will show empty directory")
                            # Show empty directory to maintain navigation flow
                            import xbmcplugin
                            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)
                            return

                    except Exception as e:
                        self.logger.error(f"Failed to restore search results: {e}")
                        # Fall back to empty directory
                        import xbmcplugin
                        xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)
                        return
                else:
                    # Normal blocking for non-hijack scenarios
                    self.logger.warning("🚫 SEARCH BLOCKED: DialogVideoInfo is active, preventing search dialog overlay")
                    self.logger.warning(f"🚫 Container path during block: {container_path}")
                    # Properly end directory to prevent Kodi errors
                    import xbmcplugin
                    xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False)
                    return

        except Exception as e:
            self.logger.warning(f"Failed to log window state: {e}")

        try:
            # Get search query from user
            addon = xbmcaddon.Addon()
            self.logger.debug("Getting search input from user")

            query = xbmcgui.Dialog().input(
                addon.getLocalizedString(35018),
                type=xbmcgui.INPUT_ALPHANUM
            )

            self.logger.debug(f"User entered query: '{query}'")

            if not query or not query.strip():
                self.logger.info("Empty query - returning to menu")
                return

            query = query.strip()
            self.logger.debug(f"Processing search query: '{query}'")

            # For authorized users, offer search type selection
            search_type = self._get_search_type_preference()
            self.logger.debug(f"Selected search type: {search_type}")

            # Perform search with selected engine
            self.logger.debug(f"Starting search execution for query: '{query}' with type: {search_type}")
            results = self._perform_search_with_type(query, search_type)
            self.logger.info(f"Search completed, got {len(results.get('items', []))} results")

            # Cache search results in session state for potential restoration
            from .session_state import get_session_state
            session = get_session_state()
            session.last_search_results = results
            session.last_search_query = query
            self.logger.debug(f"Cached search results in session state: {len(results.get('items', []))} items")

            # Create search history list if we have results
            if results.get('items'):
                self._create_search_history_list(query, search_type, results)

            self.logger.debug("Displaying search results")
            self._display_results(results, query)
            self.logger.info("Search flow completed successfully")

        except Exception as e:
            import traceback
            self.logger.error(f"Search failed: {e}")
            self.logger.error(f"Search error traceback: {traceback.format_exc()}")

            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35021),
                addon.getLocalizedString(35022),
                xbmcgui.NOTIFICATION_ERROR
            )

    def _get_search_type_preference(self):
        """
        Get user preference for search type (local vs remote)
        Returns 'local', 'remote', or 'auto' for fallback behavior
        """
        # Non-authorized users always get local search
        if not is_authorized():
            return 'local'

        # For authorized users, show selection dialog
        dialog = xbmcgui.Dialog()

        options = [
            "Local Library Search",
            "Remote Search",
            "Remote with Local Fallback"
        ]

        selection = dialog.select(
            "Choose Search Type",
            options
        )

        if selection == -1:  # User cancelled
            return 'local'  # Default to local
        elif selection == 0:
            return 'local'
        elif selection == 1:
            return 'remote'
        else:  # selection == 2
            return 'auto'  # Remote with fallback

    def _perform_search_with_type(self, query, search_type):
        """
        Perform search with specified type

        Args:
            query: Search query string
            search_type: 'local', 'remote', or 'auto'

        Returns:
            dict: Search results with metadata
        """
        self.logger.debug(f"Starting search execution for query: '{query}' with type: {search_type}")

        if search_type == 'local':
            # Force local search only
            self.logger.debug("Using local search (user selected)")
            return self._search_local(query, limit=200)

        elif search_type == 'remote':
            # Force remote search only (no fallback)
            self.logger.info("Using remote search only (user selected)")
            return self._search_remote_only(query)

        else:  # search_type == 'auto'
            # Original behavior: remote with local fallback
            self.logger.info("Using remote search with local fallback (user selected)")
            return self._perform_search(query)

    def _perform_search(self, query):
        """
        Perform search using remote or local engine with fallback

        Args:
            query: Search query string

        Returns:
            dict: Search results with metadata
        """
        self.logger.info(f"Starting search execution for query: '{query}'")

        # Check authorization status
        auth_status = is_authorized()
        self.logger.info(f"Authorization status: {auth_status}")

        # Engine switch: authorized users try remote first
        if auth_status:
            try:
                self.logger.info("Attempting remote search (user is authorized)")

                # Import here to avoid circular dependencies
                from ..remote.search_client import search_remote
                self.logger.debug("Remote search client imported")

                results = search_remote(query, page=1, page_size=100)
                result_count = len(results.get('items', []))
                self.logger.info(f"Remote search succeeded: {result_count} results")
                results['used_remote'] = True
                return results

            except RemoteError as e:
                self.logger.warning(f"Remote search failed with RemoteError, falling back to local: {e}")
                self._show_fallback_notification()
                return self._search_local(query, limit=200)

            except Exception as e:
                import traceback
                self.logger.error(f"Remote search error, falling back to local: {e}")
                self.logger.error(f"Remote search traceback: {traceback.format_exc()}")
                self._show_fallback_notification()
                return self._search_local(query, limit=200)

        else:
            # Non-authorized users use local search
            self.logger.info("Using local search (user not authorized)")
            return self._search_local(query, limit=200)

    def _search_remote_only(self, query):
        """Perform remote-only search without fallback"""
        self.logger.info(f"Starting remote-only search for query: '{query}'")

        if not is_authorized():
            self.logger.warning("Remote-only search requested but user not authorized")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                "Remote search requires authorization",
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return {'items': [], 'total': 0, 'used_remote': False}

        try:
            self.logger.info("Attempting remote-only search")

            # Import here to avoid circular dependencies
            from ..remote.search_client import search_remote
            self.logger.debug("Remote search client imported")

            results = search_remote(query, page=1, page_size=100)
            result_count = len(results.get('items', []))
            self.logger.info(f"Remote-only search succeeded: {result_count} results")
            results['used_remote'] = True
            return results

        except RemoteError as e:
            self.logger.error(f"Remote-only search failed with RemoteError: {e}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                f"Remote search failed: {str(e)[:50]}",
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return {'items': [], 'total': 0, 'used_remote': False}

        except Exception as e:
            import traceback
            self.logger.error(f"Remote-only search error: {e}")
            self.logger.error(f"Remote-only search traceback: {traceback.format_exc()}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                "Remote search failed",
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return {'items': [], 'total': 0, 'used_remote': False}

    def _search_local(self, query, limit=200):
        """Perform local search using local engine"""
        self.logger.debug(f"Starting local search for query: '{query}' with limit: {limit}")

        try:
            # Check if local engine is properly initialized
            if not self.local_engine:
                self.logger.error("Local search engine is None")
                return {'items': [], 'total': 0, 'used_remote': False}

            self.logger.debug("Calling local_engine.search()")
            results = self.local_engine.search(query, limit=limit)

            if results:
                result_count = len(results.get('items', []))
                total_count = results.get('total', 0)
                self.logger.info(f"Local search completed: {result_count} items returned, {total_count} total matches")
                results['used_remote'] = False
                return results
            else:
                self.logger.warning("Local search returned None/empty results")
                return {'items': [], 'total': 0, 'used_remote': False}

        except Exception as e:
            import traceback
            self.logger.error(f"Local search failed: {e}")
            self.logger.error(f"Local search traceback: {traceback.format_exc()}")
            return {'items': [], 'total': 0, 'used_remote': False}

    def _show_fallback_notification(self):
        """Show one-shot notification about remote fallback (don't spam)"""
        session_state = get_session_state()

        if session_state.should_show_notification("remote_search_fallback", 600):
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35023),  # "Remote unavailable, using local"
                xbmcgui.NOTIFICATION_WARNING,
                4000
            )

    def _display_results(self, results, query):
        """Display search results by navigating to the saved list (V20+ behavior)"""
        try:
            items = results.get('items', [])

            if not items:
                self._show_no_results_message(query)
                return

            # Get the most recent search history list for this query
            search_lists = self.query_manager.get_lists_in_folder(self.query_manager.get_or_create_search_history_folder())

            if search_lists:
                # Use the most recent search list (first in the list)
                latest_list = search_lists[0]
                list_id = latest_list['id']

                self.logger.debug(f"Navigating to saved search list {list_id} instead of showing inline results")

                # Navigate to the saved list using Container.Update (V20+ behavior)
                import xbmc
                list_url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"

                self.logger.info(f"Using Container.Update to navigate to: {list_url}")
                xbmc.executebuiltin(f'Container.Update("{list_url}")')

                # Also end the directory to complete the navigation
                import xbmcplugin
                xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True)

                used_remote = results.get('used_remote', False)
                source = "remote" if used_remote else "local"
                self.logger.info(f"Redirected to saved list containing {len(items)} {source} search results for '{query}'")

            else:
                # Fallback: display inline if no saved list found
                self.logger.warning("No saved search list found, falling back to inline display")
                self._display_results_inline(results, query)

        except Exception as e:
            import traceback
            self.logger.error(f"Failed to navigate to search results: {e}")
            self.logger.error(f"Display results traceback: {traceback.format_exc()}")

            # Fallback to inline display on error
            self.logger.info("Falling back to inline display due to navigation error")
            self._display_results_inline(results, query)

    def _display_results_inline(self, results, query):
        """Display search results inline (fallback method)"""
        try:
            items = results.get('items', [])

            if not items:
                self._show_no_results_message(query)
                return

            # Normalize items for rendering using QueryManager
            from ..data.query_manager import get_query_manager
            query_manager = get_query_manager()

            normalized_items = []
            for item in items:
                # Set source for context menus
                item['source'] = 'search'

                # Ensure basic fields exist
                if 'media_type' not in item:
                    item['media_type'] = item.get('type', 'movie')

                if 'kodi_id' not in item and item.get('movieid'):
                    item['kodi_id'] = item['movieid']

                # Normalize to canonical format
                canonical_item = query_manager._normalize_to_canonical(item)
                normalized_items.append(canonical_item)

            # Display search results using proper ListItemBuilder
            content_type = self.query_manager.detect_content_type(normalized_items)

            list_builder = ListItemBuilder(self.addon_handle, self.addon_id)
            success = list_builder.build_directory(normalized_items, content_type)

            # Log result summary
            used_remote = results.get('used_remote', False)
            source = "remote" if used_remote else "local"
            self.logger.info(f"Displayed {len(normalized_items)} {source} search results inline for '{query}'")

        except Exception as e:
            import traceback
            self.logger.error(f"Failed to display search results inline: {e}")
            self.logger.error(f"Inline display traceback: {traceback.format_exc()}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35027),  # "Error displaying results"
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )

    def _show_no_results_message(self, query):
        """Show notification when no results are found"""
        addon = xbmcaddon.Addon()
        xbmcgui.Dialog().notification(
            addon.getLocalizedString(35019),
            addon.getLocalizedString(35020) % query,
            xbmcgui.NOTIFICATION_INFO
        )


    def _create_search_history_list(self, query, search_type, results):
        """Create a search history list with the results"""
        try:
            if not results.get('items'):
                return

            # Create the search history list
            list_id = self.query_manager.create_search_history_list(
                query=query,
                search_type=search_type,
                result_count=len(results['items'])
            )

            if not list_id:
                self.logger.error("Failed to create search history list")
                return

            # Add search results to the list
            added_count = self.query_manager.add_search_results_to_list(list_id, results)

            if added_count > 0:
                self.logger.info(f"Created search history list with {added_count} items")

                # Show brief notification
                addon = xbmcaddon.Addon()
                xbmcgui.Dialog().notification(
                    addon.getLocalizedString(35002),  # "LibraryGenie"
                    f"Search saved: {added_count} items in Search History",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            else:
                self.logger.warning("No items were added to search history list")

        except Exception as e:
            import traceback
            self.logger.error(f"Failed to create search history list: {e}")
            self.logger.error(f"Search history error traceback: {traceback.format_exc()}")

    def search_with_fallback(self, query, page=1, page_size=100):
        """Search with remote first, fallback to local"""
        if not query or not query.strip():
            return {'items': [], 'total': 0, 'used_remote': False}

        query = query.strip()

        # Engine switch logic
        if is_authorized():
            try:
                remote_results = search_remote(query, page, page_size)
                if remote_results.get('items'):
                    self.logger.info(f"Remote search successful: {len(remote_results['items'])} results")
                    # Create search history list
                    self._create_search_history_list(query, "remote", remote_results)
                    return remote_results

            except RemoteError as e:
                self.logger.warning(f"Remote search failed: {e}")
                self._show_fallback_notification()

            except Exception as e:
                self.logger.error(f"Remote search error: {e}")
                self._show_fallback_notification()

        # Use local search
        try:
            local_results = self.local_engine.search(query, limit=page_size, offset=(page-1)*page_size)
            self.logger.info(f"Local search: {len(local_results.get('items', []))} results")

            # Create search history list for non-empty results
            if local_results.get('items'):
                self._create_search_history_list(query, "local", local_results)

            return local_results

        except Exception as e:
            self.logger.error(f"Local search failed: {e}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35025),  # "Search failed"
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return {'items': [], 'total': 0, 'used_remote': False}

    def handle_search_request(self, query):
        """Handle search request from UI"""
        if not query or not query.strip():
            return []

        query = query.strip()
        self.logger.info(f"Search request: '{query}'")

        try:
            results = self.search_with_fallback(query)
            # Cache search results in session state for potential restoration
            from .session_state import get_session_state
            session = get_session_state()
            session.last_search_results = results
            session.last_search_query = query

            # Build and display the results
            self._display_results(results, query)
            return results.get('items', [])

        except Exception as e:
            self.logger.error(f"Search request failed: {e}")
            return []

    def handle_remote_search_request(self, query):
        """Handle remote-only search request with authorization check"""
        if not query or not query.strip():
            return []

        # Check authorization and prompt if needed
        auth_helper = get_auth_helper()
        if not auth_helper.check_authorization_or_prompt("remote search"):
            return []

        query = query.strip()
        self.logger.info(f"Remote search request: '{query}'")

        try:
            remote_results = search_remote(query)
            return remote_results.get('items', [])

        except Exception as e:
            self.logger.error(f"Remote search failed: {e}")
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35026),  # "Remote search failed"
                xbmcgui.NOTIFICATION_ERROR,
                4000
            )
            return []