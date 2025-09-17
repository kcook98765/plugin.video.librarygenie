#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Base Tools Provider
Common interface for all tools providers
"""

from abc import ABC, abstractmethod
from typing import List, Any
from ..types import ToolAction, ToolsContext
from lib.utils.error_handler import create_error_handler
from lib.ui.response_types import DialogResponse


class BaseToolsProvider(ABC):
    """Base class for all tools providers"""
    
    def __init__(self):
        """Initialize base provider with error handling"""
        self.error_handler = create_error_handler(self.__class__.__module__)
    
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
    
    def _handle_with_error_logging(self, operation_name: str, handler_func, *args, **kwargs) -> DialogResponse:
        """
        Standard error handling wrapper for provider handlers
        
        Args:
            operation_name: Name of the operation for logging
            handler_func: The handler function to execute
            *args, **kwargs: Arguments to pass to the handler function
            
        Returns:
            DialogResponse from the handler or error response
        """
        try:
            result = handler_func(*args, **kwargs)
            if isinstance(result, DialogResponse):
                return result
            else:
                # If handler doesn't return DialogResponse, create success response without message
                # to avoid spurious UI notifications
                return DialogResponse(success=True)
        except Exception as e:
            self.error_handler.logger.error(f"Error in {operation_name}: %s", e)
            return DialogResponse(
                success=False,
                message=f"Error in {operation_name.replace('_', ' ')}"
            )