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
