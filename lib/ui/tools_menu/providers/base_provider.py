#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Base Tools Provider
Common interface for all tools providers
"""

from abc import ABC, abstractmethod
from typing import List, Any
from ..types import ToolAction, ToolsContext


class BaseToolsProvider(ABC):
    """Base class for all tools providers"""
    
    @abstractmethod
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build list of tool actions for the given context"""
        pass
        
    def _create_action(self, action_id: str, label: str, handler: Any, 
                      payload: dict = None, needs_confirmation=None) -> ToolAction:
        """Helper to create ToolAction with standard defaults"""
        return ToolAction(
            id=action_id,
            label=label,
            handler=handler,
            payload=payload or {},
            needs_confirmation=needs_confirmation,
            enabled=True,
            visible=True
        )