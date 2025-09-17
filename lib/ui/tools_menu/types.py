#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Tools Menu Types
Core types for centralized tools & options system
"""

from typing import Dict, Any, Optional, Union, List, Callable, Protocol, Literal, Sequence, TYPE_CHECKING
from dataclasses import dataclass
from lib.ui.response_types import DialogResponse
from lib.ui.localization import L
import xbmcgui

if TYPE_CHECKING:
    from lib.ui.plugin_context import PluginContext


@dataclass
class ConfirmSpec:
    """Specification for confirmation dialogs"""
    title: str
    message: str
    confirm_label: Optional[str] = None
    cancel_label: Optional[str] = None


@dataclass 
class ToolsContext:
    """Context information for tools menu"""
    list_type: Literal["favorites", "user_list", "folder", "lists_main"]
    list_id: Optional[str] = None
    folder_id: Optional[str] = None
    
    def get_context_key(self) -> str:
        """Get unique key for this context"""
        if self.list_type == "user_list":
            return f"user_list:{self.list_id}"
        elif self.list_type == "folder":
            return f"folder:{self.folder_id}"
        else:
            return self.list_type


class ToolHandler(Protocol):
    """Protocol for tool action handlers"""
    def __call__(self, context: Any, payload: Dict[str, Any]) -> DialogResponse:
        ...


@dataclass
class ToolAction:
    """Definition of a tool action"""
    id: str
    label: str
    icon: Optional[str] = None
    enabled: bool = True
    visible: bool = True
    needs_confirmation: Optional[ConfirmSpec] = None
    handler: Optional[ToolHandler] = None
    payload: Optional[Dict[str, Any]] = None
    
    def get_display_label(self) -> str:
        """Get the display label with proper formatting"""
        return self.label


class DialogAdapter:
    """Type-safe wrapper around xbmcgui.Dialog with proper error handling"""
    
    def __init__(self):
        self.dialog = xbmcgui.Dialog()
    
    def select(self, title: str, options: Sequence[Union[str, xbmcgui.ListItem]], 
               preselect: int = -1, use_details: bool = False) -> int:
        """
        Show selection dialog with type-safe parameters
        
        Returns:
            int: Selected index (-1 if cancelled)
        """
        try:
            # Convert to list to satisfy xbmcgui requirements
            options_list = list(options)
            return self.dialog.select(
                heading=title,
                list=options_list,
                preselect=preselect,
                useDetails=use_details
            )
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.dialog_adapter')
            logger.error("Dialog select error: %s", e)
            return -1
    
    def yesno(self, title: str, message: str, 
             yes_label: Optional[str] = None, no_label: Optional[str] = None) -> bool:
        """
        Show yes/no confirmation dialog
        
        Returns:
            bool: True if confirmed, False if cancelled
        """
        try:
            return self.dialog.yesno(
                heading=title,
                message=message,
                yeslabel=yes_label if yes_label else "",
                nolabel=no_label if no_label else ""
            )
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.dialog_adapter')
            logger.error("Dialog yesno error: %s", e)
            return False
    
    def input(self, title: str, default: str = "", 
             input_type: int = xbmcgui.INPUT_ALPHANUM,
             hidden: bool = False) -> Optional[str]:
        """
        Show input dialog
        
        Returns:
            str: User input, None if cancelled
        """
        try:
            result = self.dialog.input(
                heading=title,
                defaultt=default,
                type=input_type,
                option=xbmcgui.ALPHANUM_HIDE_INPUT if hidden else 0
            )
            return result if result else None
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.dialog_adapter')
            logger.error("Dialog input error: %s", e)
            return None
    
    def notification(self, title: str, message: str, 
                    icon: str = "info",
                    time_ms: int = 5000) -> None:
        """Show notification to user"""
        try:
            # Map string icons to xbmcgui constants
            icon_map = {
                "info": xbmcgui.NOTIFICATION_INFO,
                "warning": xbmcgui.NOTIFICATION_WARNING, 
                "error": xbmcgui.NOTIFICATION_ERROR
            }
            icon_value = icon_map.get(icon, xbmcgui.NOTIFICATION_INFO)
            
            self.dialog.notification(
                heading=title,
                message=message,
                icon=icon_value,
                time=time_ms
            )
        except Exception as e:
            from lib.utils.kodi_log import get_kodi_logger
            logger = get_kodi_logger('lib.ui.tools_menu.dialog_adapter')
            logger.error("Dialog notification error: %s", e)