#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Tools Menu Service
Centralized service for building and displaying tools & options modals
"""

from typing import List, Optional, Dict, Any
from lib.utils.kodi_log import get_kodi_logger
from lib.ui.response_types import DialogResponse
from .types import ToolAction, ToolsContext, DialogAdapter, ConfirmSpec


class ToolsMenuService:
    """Centralized service for tools & options modals"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.ui.tools_menu.service')
        self.dialog_adapter = DialogAdapter()
        self._providers: Dict[str, Any] = {}
    
    def register_provider(self, context_type: str, provider: Any) -> None:
        """Register a tools provider for a context type"""
        self._providers[context_type] = provider
    
    def build_menu(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build menu actions for the given context"""
        try:
            provider = self._providers.get(context.list_type)
            if not provider:
                self.logger.warning("No provider found for context type: %s", context.list_type)
                return []
            
            return provider.build_tools(context, plugin_context)
        except Exception as e:
            self.logger.error("Error building menu for context %s: %s", context.get_context_key(), e)
            return []
    
    def show_menu(self, title: str, actions: List[ToolAction], 
                  plugin_context: Any) -> DialogResponse:
        """Show tools menu and handle user selection"""
        try:
            if not actions:
                return DialogResponse(
                    success=False,
                    message="No tools available"
                )
            
            # Filter to visible actions
            visible_actions = [action for action in actions if action.visible and action.enabled]
            if not visible_actions:
                return DialogResponse(
                    success=False,
                    message="No tools available"
                )
            
            # Build options list
            options = [action.get_display_label() for action in visible_actions]
            
            # Show selection dialog
            selected_index = self.dialog_adapter.select(title, options)
            
            if selected_index < 0:  # User cancelled
                return self._handle_cancel()
            
            if selected_index >= len(visible_actions):
                return DialogResponse(
                    success=False,
                    message="Invalid selection"
                )
            
            selected_action = visible_actions[selected_index]
            
            # Handle confirmation if needed
            if selected_action.needs_confirmation:
                if not self._show_confirmation(selected_action.needs_confirmation):
                    return DialogResponse(success=False)  # User declined
            
            # Execute the action
            if selected_action.handler:
                payload = selected_action.payload or {}
                return selected_action.handler(plugin_context, payload)
            else:
                return DialogResponse(
                    success=False,
                    message=f"No handler for action: {selected_action.id}"
                )
                
        except Exception as e:
            self.logger.error("Error showing tools menu: %s", e)
            return DialogResponse(
                success=False,
                message="Menu error occurred"
            )
    
    def _handle_cancel(self) -> DialogResponse:
        """Handle menu cancellation with session state navigation"""
        try:
            # Check for stored return location and navigate back to it
            from lib.ui.session_state import get_session_state
            session_state = get_session_state()
            if session_state and session_state.get_tools_return_location():
                self.logger.debug("Returning to stored location: %s", session_state.get_tools_return_location())
                return DialogResponse(
                    success=False, 
                    navigate_on_failure='return_to_tools_location'
                )
            else:
                self.logger.debug("No stored return location, staying in current view")
                return DialogResponse(success=False)
        except Exception as e:
            self.logger.error("Error handling cancel: %s", e)
            return DialogResponse(success=False)
    
    def _show_confirmation(self, confirm_spec: ConfirmSpec) -> bool:
        """Show confirmation dialog"""
        try:
            return self.dialog_adapter.yesno(
                title=confirm_spec.title,
                message=confirm_spec.message,
                yes_label=confirm_spec.confirm_label,
                no_label=confirm_spec.cancel_label
            )
        except Exception as e:
            self.logger.error("Error showing confirmation: %s", e)
            return False