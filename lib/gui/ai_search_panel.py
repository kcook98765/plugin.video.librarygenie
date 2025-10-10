#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - AI Search Panel Dialog
Provides custom AI-powered search dialog with natural language input
"""

import json
import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

# Localization helper
L = ADDON.getLocalizedString


class AISearchPanel(xbmcgui.WindowXMLDialog):
    """Custom AI search panel dialog for LibraryGenie"""
    
    XML_FILENAME = 'DialogLibraryGenieAISearch.xml'
    XML_PATH = 'Default'  # Skin folder name

    def __init__(self, *args, **kwargs):
        super(AISearchPanel, self).__init__()
        self._result = None
        self._keyboard_closed_time = 0
        
        # Get result limit from settings
        result_limit = ADDON.getSettingInt('ai_search_result_limit')
        if result_limit <= 0:
            result_limit = 20  # Fallback default
        
        self._state = {
            'query': '',
            'max_results': result_limit,  # From settings
            'mode': 'hybrid',  # Hard-coded: Always use Hybrid mode
            'use_llm': True,  # Hard-coded: Always use AI Understanding
            'debug_intent': False  # Hard-coded: Debug always off
        }
        
        # Initialize search history flag before checking
        self._has_search_history = False
        
        # Check if search history exists
        self._check_search_history_exists()

    def onInit(self):
        """Initialize the dialog"""
        self._wire_controls()
        self._apply_state_to_controls()
        self._load_and_display_stats()
        
        # Re-check search history and update property now that window is initialized
        self._check_search_history_exists()
        self._update_search_history_property()
        
        # Focus on Query field by default
        self.setFocusId(200)
        
        # Auto-open keyboard on dialog init to prevent keyboard shortcut leak-through
        # This allows users to start typing immediately instead of accidentally triggering
        # global shortcuts (like 'b' for PVR Timers) while navigating the dialog
        self._open_keyboard()

    def onAction(self, action):
        """Handle actions"""
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self._cleanup_properties()
            self.close()
    
    def _cleanup_properties(self):
        """Clean up window properties when dialog closes"""
        try:
            self.clearProperty('SearchHistoryExists')
            xbmc.log('[LG-AISearchPanel] Cleaned up window properties on close', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error cleaning up properties: {}'.format(e), xbmc.LOGERROR)
    
    def onClick(self, control_id):
        """Handle control clicks"""
        if control_id == 200:
            # Clicking on query box opens keyboard (with debounce)
            import time
            current_time = time.time()
            time_since_close = current_time - self._keyboard_closed_time
            
            if time_since_close < 0.5:  # Ignore clicks within 500ms
                xbmc.log('[LG-AISearchPanel] Ignoring click - keyboard closed {:.2f}s ago'.format(time_since_close), xbmc.LOGDEBUG)
            else:
                self._open_keyboard()
        elif control_id == 210:
            # Switch to Local Search
            self._switch_to_local_search()
        elif control_id == 260:
            # Search button
            self._finalize_and_close()
        elif control_id == 261:
            # Cancel button
            self._result = None
            self._cleanup_properties()
            self.close()
        elif control_id == 262:
            # Search History button
            self._open_search_history()

    def _wire_controls(self):
        """Wire up all controls"""
        self.q_edit = self.getControl(200)
        self.btn_switch = self.getControl(210)
        self.btn_search = self.getControl(260)
        self.btn_cancel = self.getControl(261)
        try:
            self.stats_text = self.getControl(270)
        except:
            self.stats_text = None

    def _apply_state_to_controls(self):
        """Apply current state to dialog controls"""
        # Query (using button label)
        self.q_edit.setLabel(self._state.get('query', ''))

    def _open_keyboard(self):
        """Open keyboard for query input"""
        import time
        
        # Get current text from button label
        current_text = self.q_edit.getLabel()
        kb = xbmc.Keyboard(current_text, 'Enter natural language search (e.g., "action movies from the 90s")')
        kb.doModal()
        
        # Record when keyboard closed
        self._keyboard_closed_time = time.time()
        
        if kb.isConfirmed():
            text = kb.getText()
            self._state['query'] = text
            self.q_edit.setLabel(text)
        
        # Move focus to Search button after keyboard closes
        self.setFocusId(260)

    def _load_and_display_stats(self):
        """Load library statistics from cached file"""
        if not self.stats_text:
            return
        
        try:
            from lib.utils.stats_cache import get_stats_cache
            from lib.remote.ai_search_client import AISearchClient
            
            # Check if AI Search is activated
            client = AISearchClient()
            if not client.is_activated():
                self.stats_text.setText('[COLOR FFAAAAAA]AI Search not activated[/COLOR]')
                return
            
            # Load stats from cached file
            stats_cache = get_stats_cache()
            stats = stats_cache.load_stats()
            
            if stats:
                xbmc.log('[LG-AISearchPanel] Using cached library stats from file', xbmc.LOGDEBUG)
                self._display_stats(stats)
            else:
                self.stats_text.setText('[COLOR FFAAAAAA]No statistics available yet[/COLOR]\n[COLOR FF888888]Stats will be cached after next sync[/COLOR]')
        
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error loading stats: {}'.format(str(e)), xbmc.LOGERROR)
            self.stats_text.setText('[COLOR FFAAAAAA]Error loading statistics[/COLOR]')
    
    def _display_stats(self, stats):
        """Format and display library statistics"""
        if not stats or not self.stats_text:
            return
        
        try:
            lines = ['[B]Library Statistics[/B]', '']
            
            # Helper to safely convert to float
            def safe_float(val, default=0.0):
                try:
                    return float(val) if val is not None else default
                except (ValueError, TypeError):
                    return default
            
            # Helper to safely convert to int
            def safe_int(val, default=0):
                try:
                    return int(val) if val is not None else default
                except (ValueError, TypeError):
                    return default
            
            # Library Overview
            lib_overview = stats.get('library_overview', {})
            if lib_overview:
                total = safe_int(lib_overview.get('total_uploaded', 0))
                lines.append('[COLOR FF00CED1]Your Library:[/COLOR]')
                lines.append('  Total Movies: [B]{}[/B]'.format(total))
                
                date_range = lib_overview.get('upload_date_range', {})
                if date_range:
                    earliest = date_range.get('earliest', 'N/A')
                    latest = date_range.get('latest', 'N/A')
                    if earliest != 'N/A':
                        earliest = earliest.split('T')[0]
                    if latest != 'N/A':
                        latest = latest.split('T')[0]
                    lines.append('  Upload Range: {} to {}'.format(earliest, latest))
                lines.append('')
            
            # Data Quality
            data_quality = stats.get('data_quality', {})
            if data_quality:
                lines.append('[COLOR FF00CED1]Data Quality:[/COLOR]')
                
                tmdb_avail = data_quality.get('tmdb_data_available', {})
                if tmdb_avail:
                    count = safe_int(tmdb_avail.get('count', 0))
                    pct = safe_float(tmdb_avail.get('percentage', 0))
                    lines.append('  TMDB Data: {} ({:.1f}%)'.format(count, pct))
                
                tmdb_errors = data_quality.get('tmdb_errors', {})
                if tmdb_errors:
                    count = safe_int(tmdb_errors.get('count', 0))
                    pct = safe_float(tmdb_errors.get('percentage', 0))
                    lines.append('  TMDB Errors: {} ({:.1f}%)'.format(count, pct))
                
                os_indexed = data_quality.get('opensearch_indexed', {})
                if os_indexed:
                    count = safe_int(os_indexed.get('count', 0))
                    pct = safe_float(os_indexed.get('percentage', 0))
                    lines.append('  AI Searchable: [B]{} ({:.1f}%)[/B]'.format(count, pct))
                lines.append('')
            
            # Setup Status with Breakdown
            setup_status = stats.get('setup_status', {})
            if setup_status:
                not_setup = setup_status.get('not_setup', {})
                
                lines.append('[COLOR FF00CED1]Not Ready Breakdown:[/COLOR]')
                
                breakdown = not_setup.get('breakdown', {})
                if breakdown:
                    missing_tmdb = breakdown.get('missing_tmdb_data', {})
                    if missing_tmdb:
                        count = safe_int(missing_tmdb.get('count', 0))
                        lines.append('  Missing TMDB: {}'.format(count))
                    
                    not_indexed = breakdown.get('not_in_opensearch', {})
                    if not_indexed:
                        count = safe_int(not_indexed.get('count', 0))
                        lines.append('  Not Indexed: {}'.format(count))
                    
                    tmdb_err = breakdown.get('tmdb_errors', {})
                    if tmdb_err:
                        count = safe_int(tmdb_err.get('count', 0))
                        if count > 0:
                            lines.append('  TMDB Errors: {}'.format(count))
                lines.append('')
            
            # Batch History
            batch_history = stats.get('batch_history', {})
            if batch_history:
                lines.append('[COLOR FF00CED1]Sync History:[/COLOR]')
                
                total_batches = safe_int(batch_history.get('total_batches', 0))
                successful = safe_int(batch_history.get('successful_batches', 0))
                failed = safe_int(batch_history.get('failed_batches', 0))
                
                lines.append('  Total Syncs: {}'.format(total_batches))
                if total_batches > 0:
                    lines.append('  Success: {} | Failed: {}'.format(successful, failed))
                
                recent = batch_history.get('recent_batches', [])
                if recent and len(recent) > 0:
                    last_batch = recent[0]
                    items = safe_int(last_batch.get('successful_imports', 0))
                    status = last_batch.get('status', 'N/A')
                    lines.append('  Last Sync: {} items ({})'.format(items, status))
                lines.append('')
            
            # System Context
            sys_context = stats.get('system_context', {})
            if sys_context:
                lines.append('[COLOR FF00CED1]System-Wide:[/COLOR]')
                
                total_sys = safe_int(sys_context.get('total_movies_in_system', 0))
                lines.append('  Total Movies: [B]{:,}[/B]'.format(total_sys))
                
                # User lists stats
                user_stats = sys_context.get('user_lists_stats', {})
                if user_stats:
                    total_users = safe_int(user_stats.get('total_users_with_lists', 0))
                    avg_movies = safe_float(user_stats.get('average_movies_per_user', 0))
                    largest = safe_int(user_stats.get('largest_user_collection', 0))
                    lines.append('  Active Users: {}'.format(total_users))
                    lines.append('  Avg Collection: {:.0f} movies'.format(avg_movies))
                    lines.append('  Largest: {:,} movies'.format(largest))
            
            # Join all lines
            formatted_text = '\n'.join(lines)
            self.stats_text.setText(formatted_text)
        
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error formatting stats: {}'.format(str(e)), xbmc.LOGERROR)
            self.stats_text.setText('[COLOR FFAAAAAA]Error displaying statistics[/COLOR]')
    
    def _check_search_history_exists(self):
        """Check if search history exists"""
        try:
            from lib.data.query_manager import QueryManager
            query_manager = QueryManager()
            
            # Initialize query manager if needed
            if not query_manager.initialize():
                xbmc.log('[LG-AISearchPanel] Failed to initialize query manager', xbmc.LOGWARNING)
                self._has_search_history = False
                return
            
            folder_id = query_manager.get_or_create_search_history_folder()
            if folder_id:
                # Convert folder_id to string for API compatibility
                lists = query_manager.get_lists_in_folder(str(folder_id))
                self._has_search_history = len(lists) > 0
                xbmc.log('[LG-AISearchPanel] Search history check: folder_id={}, {} lists found, enabled={}'.format(
                    folder_id, len(lists), self._has_search_history), xbmc.LOGDEBUG)
            else:
                self._has_search_history = False
                xbmc.log('[LG-AISearchPanel] Search history check: no folder found', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error checking search history: {}'.format(e), xbmc.LOGERROR)
            self._has_search_history = False

    def _update_search_history_property(self):
        """Update window property for search history button state"""
        try:
            # Set property directly on the dialog window using self.setProperty
            if self._has_search_history:
                self.setProperty('SearchHistoryExists', 'true')
                xbmc.log('[LG-AISearchPanel] Search History button ENABLED (property set)', xbmc.LOGDEBUG)
            else:
                self.clearProperty('SearchHistoryExists')
                xbmc.log('[LG-AISearchPanel] Search History button DISABLED (property cleared)', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error updating search history property: {}'.format(e), xbmc.LOGERROR)

    def _open_search_history(self):
        """Open search history in a modal selector"""
        xbmc.log('[LG-AISearchPanel] Opening search history modal', xbmc.LOGDEBUG)
        
        try:
            from lib.data.query_manager import QueryManager
            query_manager = QueryManager()
            
            # Initialize query manager if needed
            if not query_manager.initialize():
                xbmcgui.Dialog().notification('LibraryGenie', 'Database error', xbmcgui.NOTIFICATION_ERROR, 3000)
                return
            
            # Get search history folder and lists
            folder_id = query_manager.get_or_create_search_history_folder()
            if not folder_id:
                xbmcgui.Dialog().notification('LibraryGenie', 'No search history available', xbmcgui.NOTIFICATION_INFO, 3000)
                return
            
            lists = query_manager.get_lists_in_folder(str(folder_id))
            if not lists:
                xbmcgui.Dialog().notification('LibraryGenie', 'No search history found', xbmcgui.NOTIFICATION_INFO, 3000)
                return
            
            # Sort by ID descending (most recent first)
            lists.sort(key=lambda x: int(x.get('id', 0)), reverse=True)
            
            # Format list names for display
            list_labels = [lst.get('name', 'Unnamed Search') for lst in lists]
            
            # Show modal selector
            selected_index = xbmcgui.Dialog().select('Search History', list_labels)
            
            # If user cancelled (returns -1), stay in dialog
            if selected_index < 0:
                xbmc.log('[LG-AISearchPanel] Search history selection cancelled', xbmc.LOGDEBUG)
                return
            
            # User selected a search - navigate to it
            selected_list = lists[selected_index]
            list_id = selected_list.get('id')
            if list_id:
                xbmc.log('[LG-AISearchPanel] User selected search history list ID: {}'.format(list_id), xbmc.LOGDEBUG)
                
                # Return navigation intent instead of executing it
                # Caller will perform actual navigation after dialog fully closes
                import xbmcaddon
                addon_id = xbmcaddon.Addon().getAddonInfo('id')
                plugin_url = 'plugin://{}/?action=show_list&list_id={}'.format(addon_id, list_id)
                
                self._result = {
                    'navigate_away': True,
                    'target': plugin_url,
                    'list_id': list_id
                }
                xbmc.log('[LG-AISearchPanel] Set _result to navigate_away for list {}, closing dialog now'.format(list_id), xbmc.LOGDEBUG)
                self._cleanup_properties()
                self.close()
            
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error showing search history modal: {}'.format(e), xbmc.LOGERROR)
            xbmcgui.Dialog().notification('LibraryGenie', 'Error loading search history', xbmcgui.NOTIFICATION_ERROR, 3000)
    
    def _switch_to_local_search(self):
        """Switch to local search window"""
        xbmc.log('[LG-AISearchPanel] Switching to local search', xbmc.LOGDEBUG)
        
        # Save preference (sticky preference)
        try:
            from lib.config.config_manager import get_config
            config = get_config()
            config.set('preferred_search_mode', 'local')
            xbmc.log('[LG-AISearchPanel] Saved preferred search mode: local', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error saving search mode preference: {}'.format(e), xbmc.LOGERROR)
        
        self._result = {
            'switch_to_local': True
        }
        self.close()

    def _finalize_and_close(self):
        """Finalize and close dialog"""
        # Get query from button label
        query = self.q_edit.getLabel().strip()
        
        # Update state with the final query
        self._state['query'] = query
        
        xbmc.log('[LG-AISearchPanel] _finalize_and_close called', xbmc.LOGDEBUG)
        xbmc.log('[LG-AISearchPanel] Query: "{}"'.format(query), xbmc.LOGDEBUG)
        xbmc.log('[LG-AISearchPanel] Full state: {}'.format(self._state), xbmc.LOGDEBUG)
        
        # Prepare result with all search parameters
        self._result = {
            'query': query,
            'max_results': self._state.get('max_results', 20),
            'mode': self._state.get('mode', 'hybrid'),
            'use_llm': self._state.get('use_llm', False),
            'debug_intent': self._state.get('debug_intent', False)
        }
        xbmc.log('[LG-AISearchPanel] Result being returned: {}'.format(self._result), xbmc.LOGDEBUG)
        self.close()

    @classmethod
    def prompt(cls, initial_query=''):
        """Show AI search panel and return result"""
        addon_path = ADDON.getAddonInfo('path')
        w = cls(cls.XML_FILENAME, addon_path, cls.XML_PATH)
        try:
            w._state['query'] = initial_query or w._state.get('query', '')
            w.doModal()
            xbmc.log('[LG-AISearchPanel] prompt() returning result: {}'.format(w._result), xbmc.LOGDEBUG)
            return w._result
        finally:
            del w
