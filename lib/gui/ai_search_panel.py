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
        
        self._state = {
            'query': '',
            'max_results': 20  # Default number of results
        }

    def onInit(self):
        """Initialize the dialog"""
        self._wire_controls()
        self._apply_state_to_controls()
        self._load_and_display_stats()
        
        # Focus on Query field by default
        self.setFocusId(200)

    def onAction(self, action):
        """Handle actions"""
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()
    
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
            self.close()

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
        """Load library statistics from API with caching"""
        if not self.stats_text:
            return
        
        try:
            from lib.utils.cache import get_cached, set_cached
            from lib.remote.ai_search_client import AISearchClient
            
            # Check cache first (1 hour TTL)
            CACHE_KEY = 'ai_library_stats'
            cached_stats = get_cached(CACHE_KEY)
            
            if cached_stats:
                xbmc.log('[LG-AISearchPanel] Using cached library stats', xbmc.LOGDEBUG)
                self._display_stats(cached_stats)
                return
            
            # Fetch fresh stats
            client = AISearchClient()
            if not client.is_activated():
                self.stats_text.setText('[COLOR FFAAAAAA]AI Search not activated[/COLOR]')
                return
            
            stats = client.get_library_stats()
            if stats:
                # Cache for 1 hour (3600 seconds)
                set_cached(CACHE_KEY, stats, 3600)
                self._display_stats(stats)
            else:
                self.stats_text.setText('[COLOR FFAAAAAA]Unable to load statistics[/COLOR]')
        
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
                    lines.append('  Date Range: {} to {}'.format(earliest, latest))
                lines.append('')
            
            # Setup Status
            setup_status = stats.get('setup_status', {})
            if setup_status:
                completely_setup = setup_status.get('completely_setup', {})
                not_setup = setup_status.get('not_setup', {})
                
                lines.append('[COLOR FF00CED1]Setup Status:[/COLOR]')
                if completely_setup:
                    count = safe_int(completely_setup.get('count', 0))
                    pct = safe_float(completely_setup.get('percentage', 0))
                    lines.append('  Searchable: [B]{} ({:.1f}%)[/B]'.format(count, pct))
                
                if not_setup:
                    count = safe_int(not_setup.get('count', 0))
                    pct = safe_float(not_setup.get('percentage', 0))
                    lines.append('  Not Ready: {} ({:.1f}%)'.format(count, pct))
                lines.append('')
            
            # System Context
            sys_context = stats.get('system_context', {})
            if sys_context:
                lines.append('[COLOR FF00CED1]System Stats:[/COLOR]')
                
                total_sys = safe_int(sys_context.get('total_movies_in_system', 0))
                lines.append('  Total Movies: [B]{:,}[/B]'.format(total_sys))
                
                # OpenSearch stats
                os_stats = sys_context.get('opensearch_detailed_stats', {})
                if os_stats:
                    indexed = safe_int(os_stats.get('movies_indexed', 0))
                    completion = safe_float(os_stats.get('indexing_completion_rate', 0))
                    lines.append('  Indexed: {:,} ({:.1f}%)'.format(indexed, completion))
                
                # TMDB stats
                tmdb_stats = sys_context.get('tmdb_detailed_stats', {})
                if tmdb_stats:
                    success_rate = safe_float(tmdb_stats.get('success_rate', 0))
                    lines.append('  TMDB Success: {:.1f}%'.format(success_rate))
                
                # User lists stats
                user_stats = sys_context.get('user_lists_stats', {})
                if user_stats:
                    total_users = safe_int(user_stats.get('total_users_with_lists', 0))
                    avg_movies = safe_float(user_stats.get('average_movies_per_user', 0))
                    lines.append('  Active Users: {} (avg {:.0f} movies)'.format(total_users, avg_movies))
            
            # Join all lines
            formatted_text = '\n'.join(lines)
            self.stats_text.setText(formatted_text)
        
        except Exception as e:
            xbmc.log('[LG-AISearchPanel] Error formatting stats: {}'.format(str(e)), xbmc.LOGERROR)
            self.stats_text.setText('[COLOR FFAAAAAA]Error displaying statistics[/COLOR]')
    
    def _switch_to_local_search(self):
        """Switch to local search window"""
        xbmc.log('[LG-AISearchPanel] Switching to local search', xbmc.LOGDEBUG)
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
        
        # Prepare result
        self._result = {
            'query': query,
            'max_results': self._state.get('max_results', 20)
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
