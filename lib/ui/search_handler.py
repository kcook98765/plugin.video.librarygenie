#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Unified Search Handler (drop-in)
- Backward compatible with both previous implementations
- Supports PluginContext or bare addon_handle
- Consolidates remote/local/auto logic, history saving, and display paths
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Union

import xbmcgui
import xbmcaddon

# Optional imports guarded for drop-in flexibility
try:
    import xbmc
    import xbmcplugin
except Exception:  # pragma: no cover (Kodi runtime)
    xbmc = None
    xbmcplugin = None

# Shared libs
from ..search.local_engine import LocalSearchEngine
from ..remote.search_client import search_remote, RemoteError
from ..auth.state import is_authorized
from ..auth.auth_helper import get_auth_helper
from ..ui.session_state import get_session_state
from ..data.query_manager import get_query_manager
from ..utils.logger import get_logger

try:
    from ..ui.listitem_builder import ListItemBuilder
except ImportError:
    ListItemBuilder = None

# Newer arch types (kept optional so this file still imports without them)
try:
    from .plugin_context import PluginContext
    from .response_types import DirectoryResponse
except Exception:  # pragma: no cover
    PluginContext = Any = object  # type: ignore
    DirectoryResponse = None       # type: ignore


class SearchHandler:
    """
    Unified Search Handler
    - Works with either PluginContext (preferred) or addon_handle
    - Exposes both prompt entrypoints to remain drop-in compatible
    """

    def __init__(self, addon_handle: Optional[int] = None):
        # If called the "old" way, addon_handle comes in here; if using PluginContext,
        # we'll extract addon_handle from the context later.
        self.addon_handle = addon_handle
        self.logger = get_logger(__name__)
        self.local_engine = LocalSearchEngine()
        self.query_manager = get_query_manager()
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')

    # ---------- PUBLIC ENTRYPOINTS (both preserved) ----------

    def prompt_and_search(self, context: PluginContext) -> Optional["DirectoryResponse"]:
        """
        Newer entrypoint (kept): uses PluginContext and returns DirectoryResponse when inline-rendered.
        If the V20+ redirect path is used, returns a success DirectoryResponse with zero items.
        """
        self._ensure_handle_from_context(context)
        query = self._prompt_for_query()
        if not query:
            self._info("Empty query - returning")
            return self._maybe_dir_response([], False, "No search query provided", content_type="movies")

        # Choose search mode (authorized users may choose; others are local)
        search_type = self._get_search_type_preference()
        results = self._perform_search_with_type(query, search_type)

        # Cache results for hijack restoration / backstack UX
        self._cache_session_results(query, results)

        # Persist a Search History list if there are items
        self._maybe_persist_search_history(query, search_type, results)

        # Display: inline only to avoid parent navigation issues
        # Redirect to saved search list disabled due to parent navigation problems

        # Inline display (build directory now)
        self._display_results_inline(results, query)
        return self._maybe_dir_response(results.get('items', []), True, f"Found {len(results.get('items', []))} results for '{query}'", content_type="movies")

    def prompt_and_show(self):
        """
        Older entrypoint (kept): prompts, performs search, shows results.
        Uses addon_handle given at __init__ time.
        """
        query = self._prompt_for_query()
        if not query:
            self._info("Empty query - returning")
            return

        search_type = self._get_search_type_preference()
        results = self._perform_search_with_type(query, search_type)

        self._cache_session_results(query, results)
        self._maybe_persist_search_history(query, search_type, results)

        # Display inline only to avoid parent navigation issues
        self._display_results_inline(results, query)

    # ---------- EXTERNAL CALLERS (kept for compatibility) ----------

    def handle_search_request(self, query: str) -> List[Dict[str, Any]]:
        """Legacy compatibility: perform search with fallback, display results, return items list."""
        if not query or not query.strip():
            return []
        query = query.strip()

        results = self.search_with_fallback(query)
        self._cache_session_results(query, results)
        # Display inline only to avoid parent navigation issues
        self._display_results_inline(results, query)
        return results.get('items', [])

    def handle_remote_search_request(self, query: str) -> List[Dict[str, Any]]:
        """Legacy compatibility: remote-only with authorization prompt."""
        if not query or not query.strip():
            return []

        auth_helper = get_auth_helper()
        if not auth_helper.check_authorization_or_prompt("remote search"):
            return []

        try:
            remote_results = search_remote(query.strip())
            return remote_results.get('items', [])
        except Exception as e:
            self._error(f"Remote search failed: {e}")
            self._notify_error(self.addon.getLocalizedString(35026))  # "Remote search failed"
            return []

    def search_with_fallback(self, query: str, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Legacy compatibility helper used by some callers."""
        if not query or not query.strip():
            return {'items': [], 'total': 0, 'used_remote': False}
        query = query.strip()

        if is_authorized():
            try:
                remote_results = search_remote(query, page, page_size)
                if remote_results.get('items'):
                    self._info(f"Remote search successful: {len(remote_results['items'])} results")
                    self._maybe_persist_search_history(query, "remote", remote_results)
                    return self._mark_used_remote(remote_results, True)
            except Exception as e:
                self._warn(f"Remote search error: {e}")
                self._show_fallback_notification()

        try:
            local_results = self.local_engine.search(query, limit=page_size, offset=(page - 1) * page_size)
            if local_results.get('items'):
                self._maybe_persist_search_history(query, "local", local_results)
            return self._mark_used_remote(local_results, False)
        except Exception as e:
            self._error(f"Local search failed: {e}")
            self._notify_error(self.addon.getLocalizedString(35025))  # "Search failed"
            return {'items': [], 'total': 0, 'used_remote': False}

    # ---------- CORE EXECUTION ----------

    def _perform_search_with_type(self, query: str, search_type: str) -> Dict[str, Any]:
        if search_type == 'local':
            return self._search_local(query, limit=200)
        if search_type == 'remote':
            return self._search_remote_only(query)
        # 'auto' fallback
        return self._perform_search(query)

    def _perform_search(self, query: str) -> Dict[str, Any]:
        """Remote first (if authorized), else local, with notifications on fallback."""
        if is_authorized():
            try:
                results = search_remote(query, page=1, page_size=100)
                self._info(f"Remote search succeeded: {len(results.get('items', []))} results")
                return self._mark_used_remote(results, True)
            except RemoteError as e:
                self._warn(f"Remote search RemoteError: {e}")
                self._show_fallback_notification()
            except Exception as e:
                self._error(f"Remote search error: {e}")
                self._show_fallback_notification()
        # Fallback or not authorized
        return self._search_local(query, limit=200)

    def _search_remote_only(self, query: str) -> Dict[str, Any]:
        """Remote-only without local fallback (but with user feedback)."""
        if not is_authorized():
            self._notify_error("Remote search requires authorization")
            return {'items': [], 'total': 0, 'used_remote': False}
        try:
            results = search_remote(query, page=1, page_size=100)
            self._info(f"Remote-only search succeeded: {len(results.get('items', []))} results")
            return self._mark_used_remote(results, True)
        except RemoteError as e:
            self._error(f"Remote-only search failed: {e}")
            self._notify_error(f"Remote search failed: {str(e)[:50]}")
            return {'items': [], 'total': 0, 'used_remote': False}
        except Exception as e:
            self._error(f"Remote-only search error: {e}")
            self._notify_error(self.addon.getLocalizedString(35026))  # "Remote search failed"
            return {'items': [], 'total': 0, 'used_remote': False}

    def _search_local(self, query: str, limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        try:
            results = self.local_engine.search(query, limit=limit, offset=offset)
            items = results.get('items', []) if results else []
            total = results.get('total', 0) if results else 0
            self._info(f"Local search completed: {len(items)} items returned, {total} total")
            return self._mark_used_remote(results or {'items': [], 'total': 0}, False)
        except Exception as e:
            self._error(f"Local search failed: {e}")
            return {'items': [], 'total': 0, 'used_remote': False}

    # ---------- DISPLAY ----------

    def _display_results_inline(self, results: Dict[str, Any], query: str) -> None:
        items = results.get('items', [])
        if not items:
            self._show_no_results_message(query)
            self._end_directory(succeeded=True, update=False)
            return

        # Normalize items using QueryManager (ensures consistent fields for builder)
        normalized = []
        for item in items:
            item = dict(item)  # shallow copy
            item.setdefault('source', 'search')
            item.setdefault('media_type', item.get('type', 'movie'))
            if 'kodi_id' not in item and item.get('movieid'):
                item['kodi_id'] = item['movieid']
            canonical = self.query_manager._normalize_to_canonical(item)
            normalized.append(canonical)

        # Detect content and build
        content_type = self.query_manager.detect_content_type(normalized)
        if ListItemBuilder is None:
            self._error("ListItemBuilder not available")
            self._end_directory(succeeded=False, update=False)
            return
            
        builder = ListItemBuilder(self._require_handle(), self.addon_id)
        _ok = builder.build_directory(normalized, content_type)

        used_remote = results.get('used_remote', False)
        self._info(f"Displayed {len(normalized)} {'remote' if used_remote else 'local'} results inline for '{query}'")

    def _try_redirect_to_saved_search_list(self) -> bool:
        """
        On Kodi v20+, redirect to the most recent search-history list using Container.Update,
        if such a list exists. Returns True if redirected.
        """
        try:
            search_folder_id = self.query_manager.get_or_create_search_history_folder()
            lists = self.query_manager.get_lists_in_folder(search_folder_id)
            if not lists:
                return False

            latest = lists[0]
            list_id = latest.get('id')
            if not list_id or not xbmc:
                return False

            # Set proper parent path to the search history folder instead of search action
            search_folder_url = f"plugin://{self.addon_id}/?action=show_folder&folder_id={search_folder_id}"
            list_url = f"plugin://{self.addon_id}/?action=show_list&list_id={list_id}"
            xbmc.executebuiltin(f'Container.Update("{list_url}",replace)')
            self._end_directory(succeeded=True, update=True)
            return True
        except Exception as e:
            self._warn(f"Redirect to saved search list failed: {e}")
            return False

    # ---------- UX helpers ----------

    def _prompt_for_query(self) -> Optional[str]:
        try:
            q = xbmcgui.Dialog().input(self.addon.getLocalizedString(35018), type=xbmcgui.INPUT_ALPHANUM)
            return q.strip() if q and q.strip() else None
        except Exception as e:
            self._warn(f"Search input failed: {e}")
            return None

    def _get_search_type_preference(self) -> str:
        """Returns 'local' for non-authorized users, or user selection among local/remote/auto."""
        if not is_authorized():
            return 'local'

        options = ["Local Library Search", "Remote Search", "Remote with Local Fallback"]
        idx = xbmcgui.Dialog().select("Choose Search Type", options)
        if idx == 0:
            return 'local'
        if idx == 1:
            return 'remote'
        if idx == 2:
            return 'auto'
        # cancel → default to local
        return 'local'

    def _show_fallback_notification(self) -> None:
        session = get_session_state()
        if session.should_show_notification("remote_search_fallback", 600):
            self._notify_warn(self.addon.getLocalizedString(35023))  # "Remote unavailable, using local"

    def _show_no_results_message(self, query: str) -> None:
        self._notify_info(self.addon.getLocalizedString(35020) % query)  # "No results for '%s'"

    def _maybe_persist_search_history(self, query: str, search_type: str, results: Dict[str, Any]) -> None:
        try:
            if not results.get('items'):
                return
            list_id = self.query_manager.create_search_history_list(
                query=query, search_type=search_type, result_count=len(results['items'])
            )
            if not list_id:
                self._warn("Failed to create search history list")
                return
            added = self.query_manager.add_search_results_to_list(list_id, results)
            if added > 0:
                self._notify_info(f"Search saved: {added} items in Search History", ms=3000)
        except Exception as e:
            self._warn(f"Persisting search history failed: {e}")

    def _cache_session_results(self, query: str, results: Dict[str, Any]) -> None:
        try:
            session = get_session_state()
            session.last_search_results = results
            session.last_search_query = query
        except Exception as e:
            self._warn(f"Session cache failed: {e}")

    # ---------- Context/handle bridging ----------

    def _ensure_handle_from_context(self, context: "PluginContext") -> None:
        """If called via context, copy out essentials we need while remaining drop-in friendly."""
        if context is None:
            return
        self.addon_handle = context.addon_handle
        # prefer context.addon if present to stay consistent with localization/testing
        try:
            self.addon = context.addon or self.addon
            self.addon_id = self.addon.getAddonInfo('id')
        except Exception:
            pass

    def _require_handle(self) -> int:
        if self.addon_handle is None:
            raise RuntimeError("addon_handle is required but not set")
        return self.addon_handle

    def _end_directory(self, succeeded: bool, update: bool) -> None:
        if xbmcplugin and self.addon_handle is not None:
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=succeeded, updateListing=update)

    def _maybe_dir_response(
        self,
        items: List[Dict[str, Any]],
        success: bool,
        message: str,
        content_type: str = "movies",
    ) -> Optional["DirectoryResponse"]:
        """Return a DirectoryResponse if the newer response_types is available; otherwise None."""
        if DirectoryResponse is None:
            return None
        return DirectoryResponse(items=items, success=success, content_type=content_type)

    # ---------- Logging & notifications ----------

    def _info(self, msg: str) -> None:
        self.logger.info(msg)

    def _warn(self, msg: str) -> None:
        self.logger.warning(msg)

    def _error(self, msg: str) -> None:
        self.logger.error(msg)

    def _notify_info(self, msg: str, ms: int = 4000) -> None:
        xbmcgui.Dialog().notification(self.addon.getLocalizedString(35002), msg, xbmcgui.NOTIFICATION_INFO, ms)

    def _notify_warn(self, msg: str, ms: int = 4000) -> None:
        xbmcgui.Dialog().notification(self.addon.getLocalizedString(35002), msg, xbmcgui.NOTIFICATION_WARNING, ms)

    def _notify_error(self, msg: str, ms: int = 4000) -> None:
        xbmcgui.Dialog().notification(self.addon.getLocalizedString(35002), msg, xbmcgui.NOTIFICATION_ERROR, ms)

    # ---------- Small helpers ----------

    @staticmethod
    def _mark_used_remote(results: Dict[str, Any], used_remote: bool) -> Dict[str, Any]:
        if results is None:
            results = {}
        results['used_remote'] = used_remote
        results.setdefault('items', [])
        results.setdefault('total', len(results['items']))
        return results
