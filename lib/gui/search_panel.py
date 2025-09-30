#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Search Panel Dialog
Provides custom search dialog with advanced options
"""

import json
import os
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
PRESETS_PATH = os.path.join(PROFILE, 'search_presets.json')

# Localization helper
L = ADDON.getLocalizedString

CONTENT_MOVIES, CONTENT_SERIES, CONTENT_ALL = 0, 1, 2
FIELDS_TITLE, FIELDS_PLOT, FIELDS_BOTH = 0, 1, 2
MATCH_ANY, MATCH_ALL, MATCH_PHRASE = 0, 1, 2


class SearchPanel(xbmcgui.WindowXMLDialog):
    """Custom search panel dialog for LibraryGenie"""
    
    XML_FILENAME = 'DialogLibraryGenieSearch.xml'
    XML_PATH = 'Default'  # Skin folder name (Kodi looks in resources/skins/Default/1080i automatically)

    def __init__(self, *args, **kwargs):
        super(SearchPanel, self).__init__()
        self._result = None
        self._state = {
            'content_type': ADDON.getSettingInt('default_content_type') if ADDON.getSettingInt('default_content_type') else 0,
            'fields': ADDON.getSettingInt('default_fields') if ADDON.getSettingInt('default_fields') else 2,
            'match_mode': ADDON.getSettingInt('default_match_mode') if ADDON.getSettingInt('default_match_mode') else 0,
            'query': ''
        }
        if ADDON.getSettingBool('remember_last_values'):
            self._load_last_state()

    def onInit(self):
        """Initialize the dialog"""
        self._wire_controls()
        self._apply_state_to_controls()
        self.setFocusId(200)

    def onAction(self, action):
        """Handle actions"""
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()

    def onClick(self, control_id):
        """Handle control clicks"""
        if control_id in (201, 202, 203):
            self._set_content_type_by_control(control_id)
        elif control_id in (211, 212):
            self._toggle_fields()
        elif control_id in (221, 222, 223):
            self._set_match_mode_by_control(control_id)
        elif control_id == 200:
            # Clicking on query box opens keyboard
            self._open_keyboard()
        elif control_id == 252:
            self._save_as_default()
        elif control_id == 260:
            self._finalize_and_close()
        elif control_id == 261:
            self._result = None
            self.close()

    def _wire_controls(self):
        """Wire up all controls"""
        self.q_edit = self.getControl(200)
        self.rb_movies = self.getControl(201)
        self.rb_series = self.getControl(202)
        self.rb_all = self.getControl(203)
        self.tb_title = self.getControl(211)
        self.tb_plot = self.getControl(212)
        self.rb_any = self.getControl(221)
        self.rb_allw = self.getControl(222)
        self.rb_phrase = self.getControl(223)
        self.btn_set_default = self.getControl(252)
        self.btn_search = self.getControl(260)
        self.btn_cancel = self.getControl(261)

    def _apply_state_to_controls(self):
        """Apply current state to dialog controls"""
        # Content type
        self.rb_movies.setSelected(self._state['content_type'] == CONTENT_MOVIES)
        self.rb_series.setSelected(self._state['content_type'] == CONTENT_SERIES)
        self.rb_all.setSelected(self._state['content_type'] == CONTENT_ALL)
        # Fields
        self.tb_title.setSelected(self._state['fields'] in (FIELDS_TITLE, FIELDS_BOTH))
        self.tb_plot.setSelected(self._state['fields'] in (FIELDS_PLOT, FIELDS_BOTH))
        # Match mode
        self.rb_any.setSelected(self._state['match_mode'] == MATCH_ANY)
        self.rb_allw.setSelected(self._state['match_mode'] == MATCH_ALL)
        self.rb_phrase.setSelected(self._state['match_mode'] == MATCH_PHRASE)
        # Query
        self.q_edit.setText(self._state.get('query', ''))

    def _set_content_type_by_control(self, cid):
        """Set content type based on control ID"""
        self._state['content_type'] = {201: CONTENT_MOVIES, 202: CONTENT_SERIES, 203: CONTENT_ALL}[cid]
        self._apply_state_to_controls()

    def _toggle_fields(self):
        """Toggle field selection"""
        t = self.tb_title.isSelected()
        p = self.tb_plot.isSelected()
        self._state['fields'] = FIELDS_BOTH if (t and p) else (FIELDS_TITLE if t else (FIELDS_PLOT if p else FIELDS_TITLE))
        self._apply_state_to_controls()

    def _set_match_mode_by_control(self, cid):
        """Set match mode based on control ID"""
        self._state['match_mode'] = {221: MATCH_ANY, 222: MATCH_ALL, 223: MATCH_PHRASE}[cid]
        self._apply_state_to_controls()

    def _open_keyboard(self):
        """Open keyboard for query input"""
        # Get current text from edit control
        current_text = self.q_edit.getText()
        kb = xbmc.Keyboard(current_text, L(30333))  # "Enter search text"
        kb.doModal()
        if kb.isConfirmed():
            text = kb.getText()
            self._state['query'] = text
            self.q_edit.setText(text)

    def _load_presets(self):
        """Load presets into list"""
        self.list_presets.reset()
        presets = self._read_presets()
        for p in presets:
            li = xbmcgui.ListItem(label=p['name'])
            li.setProperty('preset_payload', json.dumps(p))
            self.list_presets.addItem(li)
        # If no presets, seed with one localized example label
        if not presets:
            li = xbmcgui.ListItem(label=L(30342))
            li.setProperty('preset_payload', json.dumps({
                'name': L(30342),
                'content_type': CONTENT_MOVIES,
                'fields': FIELDS_TITLE,
                'match_mode': MATCH_ANY,
                'query': ''
            }))
            self.list_presets.addItem(li)

    def _apply_selected_preset(self):
        """Apply selected preset to current state"""
        idx = self.list_presets.getSelectedPosition()
        if idx < 0:
            return
        li = self.list_presets.getListItem(idx)
        payload = json.loads(li.getProperty('preset_payload'))
        self._state.update({
            'content_type': payload.get('content_type', CONTENT_ALL),
            'fields': payload.get('fields', FIELDS_BOTH),
            'match_mode': payload.get('match_mode', MATCH_ANY),
            'query': payload.get('query', self._state.get('query', '')),
        })
        self._apply_state_to_controls()

    def _generate_preset_name(self):
        """Generate preset name from current state"""
        # Content type
        content_names = [L(30288), L(30286), L(30287)]  # All, Movies, Series
        content = content_names[self._state['content_type']]
        
        # Fields
        if self._state['fields'] == FIELDS_TITLE:
            fields = L(32300)  # Title
        elif self._state['fields'] == FIELDS_PLOT:
            fields = L(32301)  # Plot
        else:
            fields = L(30339)  # Title + Plot
        
        # Match mode
        match_names = [L(30323), L(30324), L(30325)]  # Any word, All words, Exact phrase
        match = match_names[self._state['match_mode']]
        
        return '{} – {} – {}'.format(content, fields, match)

    def _save_as_preset(self):
        """Save current state as preset with auto-generated name"""
        name = self._generate_preset_name()
        presets = self._read_presets()
        presets.append({
            'name': name,
            'content_type': self._state['content_type'],
            'fields': self._state['fields'],
            'match_mode': self._state['match_mode'],
            'query': self._state.get('query', ''),
            'version': 1
        })
        self._write_presets(presets)
        self._load_presets()

    def _save_as_default(self):
        """Save current state as default settings"""
        ADDON.setSettingInt('default_content_type', self._state['content_type'])
        ADDON.setSettingInt('default_fields', self._state['fields'])
        ADDON.setSettingInt('default_match_mode', self._state['match_mode'])
        xbmcgui.Dialog().notification('LibraryGenie', L(32307), xbmcgui.NOTIFICATION_INFO, 3000)

    def _finalize_and_close(self):
        """Finalize and close dialog"""
        # Get query from edit control using getText() (not getLabel!)
        query = self.q_edit.getText().strip()
        
        # Update state with the final query
        self._state['query'] = query
        
        # DEBUG: Log what we're sending
        xbmc.log('[LG-SearchPanel] _finalize_and_close called', xbmc.LOGDEBUG)
        xbmc.log('[LG-SearchPanel] Query from getText(): "{}"'.format(query), xbmc.LOGDEBUG)
        xbmc.log('[LG-SearchPanel] Full state: {}'.format(self._state), xbmc.LOGDEBUG)
        
        # Persist last state if desired
        if ADDON.getSettingBool('remember_last_values'):
            self._save_last_state()
        # Prepare result
        self._result = {
            'content_type': self._state['content_type'],
            'fields': self._state['fields'],
            'match_mode': self._state['match_mode'],
            'query': query,
        }
        xbmc.log('[LG-SearchPanel] Result being returned: {}'.format(self._result), xbmc.LOGDEBUG)
        self.close()

    def _read_presets(self):
        """Read presets from file"""
        try:
            with open(PRESETS_PATH, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return []

    def _write_presets(self, presets):
        """Write presets to file"""
        os.makedirs(PROFILE, exist_ok=True)
        with open(PRESETS_PATH, 'w', encoding='utf-8') as fh:
            json.dump(presets, fh, ensure_ascii=False, indent=2)

    def _last_state_path(self):
        """Get last state file path"""
        return os.path.join(PROFILE, 'search_last_state.json')

    def _load_last_state(self):
        """Load last used state"""
        try:
            with open(self._last_state_path(), 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                self._state.update(data)
        except Exception:
            pass

    def _save_last_state(self):
        """Save last used state"""
        os.makedirs(PROFILE, exist_ok=True)
        with open(self._last_state_path(), 'w', encoding='utf-8') as fh:
            json.dump(self._state, fh, ensure_ascii=False, indent=2)

    @classmethod
    def prompt(cls, initial_query=''):
        """Show search panel and return result"""
        addon_path = ADDON.getAddonInfo('path')
        w = cls(cls.XML_FILENAME, addon_path, cls.XML_PATH)
        try:
            w._state['query'] = initial_query or w._state.get('query', '')
            w.doModal()
            return w._result
        finally:
            del w
