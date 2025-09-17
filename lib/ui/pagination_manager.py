#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Pagination Manager
Handles adaptive pagination logic with device memory awareness and user overrides
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from lib.config.settings import SettingsManager
from lib.utils.device_memory import get_device_memory_profiler
from lib.utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('lib.ui.pagination_manager')


class PaginationInfo:
    """Container for pagination information"""
    
    def __init__(self, current_page: int, total_pages: int, page_size: int, 
                 total_items: int, start_index: int, end_index: int, 
                 has_previous: bool, has_next: bool):
        self.current_page = current_page
        self.total_pages = total_pages 
        self.page_size = page_size
        self.total_items = total_items
        self.start_index = start_index
        self.end_index = end_index
        self.has_previous = has_previous
        self.has_next = has_next
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert pagination info to dictionary"""
        return {
            'current_page': self.current_page,
            'total_pages': self.total_pages,
            'page_size': self.page_size,
            'total_items': self.total_items,
            'start_index': self.start_index,
            'end_index': self.end_index,
            'has_previous': self.has_previous,
            'has_next': self.has_next
        }


class PaginationManager:
    """Manages adaptive pagination with device memory awareness"""
    
    def __init__(self):
        self.settings = SettingsManager()
        self.memory_profiler = get_device_memory_profiler()
        
    def get_effective_page_size(self, base_size: int = 100) -> int:
        """
        Get effective page size based on user settings and device capabilities
        
        Args:
            base_size: Base page size for auto mode calculations
            
        Returns:
            int: Effective page size to use
        """
        pagination_mode = self.settings.get_list_pagination_mode()
        
        if pagination_mode == 'manual':
            # User has explicitly chosen manual mode - use their setting
            page_size = self.settings.get_list_manual_page_size()
            logger.debug("Using manual pagination mode: %d items per page", page_size)
            return page_size
        else:
            # Auto mode - use device-adaptive sizing
            page_size = self.memory_profiler.get_optimal_page_size(base_size)
            logger.debug("Using auto pagination mode: %d items per page (device tier: %s)", 
                        page_size, self.memory_profiler.detect_memory_tier())
            return page_size
            
    def calculate_pagination(self, total_items: int, current_page: int = 1, 
                           base_page_size: int = 100) -> PaginationInfo:
        """
        Calculate pagination information for a given dataset
        
        Args:
            total_items: Total number of items in dataset
            current_page: Current page number (1-based)
            base_page_size: Base page size for auto mode
            
        Returns:
            PaginationInfo: Complete pagination information
        """
        # Get effective page size
        page_size = self.get_effective_page_size(base_page_size)
        
        # Calculate total pages
        total_pages = max(1, math.ceil(total_items / page_size)) if total_items > 0 else 1
        
        # Validate and constrain current page
        current_page = max(1, min(current_page, total_pages))
        
        # Calculate start and end indices (0-based for database queries)
        start_index = (current_page - 1) * page_size
        end_index = min(start_index + page_size, total_items)
        
        # Calculate navigation flags
        has_previous = current_page > 1
        has_next = current_page < total_pages
        
        pagination_info = PaginationInfo(
            current_page=current_page,
            total_pages=total_pages,
            page_size=page_size,
            total_items=total_items,
            start_index=start_index,
            end_index=end_index,
            has_previous=has_previous,
            has_next=has_next
        )
        
        logger.debug("Calculated pagination: page %d/%d, items %d-%d of %d (page_size=%d)",
                    current_page, total_pages, start_index + 1, end_index, 
                    total_items, page_size)
        
        return pagination_info
        
    def create_pagination_items(self, pagination_info: PaginationInfo, 
                               base_url: str, url_params: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        Create pagination navigation items for list display
        
        Args:
            pagination_info: Pagination information
            base_url: Base URL for navigation (e.g., "plugin://plugin.id/?action=show_list")
            url_params: Additional URL parameters to preserve
            
        Returns:
            List[Dict]: List of pagination navigation items
        """
        if pagination_info.total_pages <= 1:
            return []  # No pagination needed for single page
            
        url_params = url_params or {}
        navigation_items = []
        
        # Previous Page item
        if pagination_info.has_previous:
            prev_params = url_params.copy()
            prev_params['page'] = str(pagination_info.current_page - 1)
            prev_url = self._build_url(base_url, prev_params)
            
            navigation_items.append({
                'title': f'← Previous Page ({pagination_info.current_page - 1}/{pagination_info.total_pages})',
                'url': prev_url,
                'media_type': 'none',  # Mark as action item
                'icon': 'DefaultArrowLeft.png',
                'is_navigation': True,
                'navigation_type': 'previous'
            })
            
        # Next Page item  
        if pagination_info.has_next:
            next_params = url_params.copy()
            next_params['page'] = str(pagination_info.current_page + 1)
            next_url = self._build_url(base_url, next_params)
            
            navigation_items.append({
                'title': f'Next Page ({pagination_info.current_page + 1}/{pagination_info.total_pages}) →',
                'url': next_url,
                'media_type': 'none',  # Mark as action item
                'icon': 'DefaultArrowRight.png',
                'is_navigation': True,
                'navigation_type': 'next'
            })
            
        logger.debug("Created %d pagination navigation items", len(navigation_items))
        return navigation_items
        
    def insert_pagination_items(self, items: List[Dict[str, Any]], 
                               pagination_info: PaginationInfo, 
                               base_url: str, url_params: Optional[Dict[str, str]] = None,
                               placement: str = 'both') -> List[Dict[str, Any]]:
        """
        Insert pagination controls into item list
        
        Args:
            items: Original list of items
            pagination_info: Pagination information  
            base_url: Base URL for navigation
            url_params: URL parameters to preserve
            placement: Where to place controls ('top', 'bottom', 'both')
            
        Returns:
            List[Dict]: Items with pagination controls inserted
        """
        nav_items = self.create_pagination_items(pagination_info, base_url, url_params)
        
        if not nav_items:
            return items  # No pagination needed
            
        result_items = items.copy()
        
        # Add to top of list
        if placement in ['top', 'both'] and pagination_info.has_next:
            # Only show "Next" at top for cleaner UX
            next_items = [item for item in nav_items if item.get('navigation_type') == 'next']
            result_items = next_items + result_items
            
        # Add to bottom of list
        if placement in ['bottom', 'both']:
            result_items.extend(nav_items)
            
        logger.debug("Inserted pagination controls (%s placement) into list of %d items", 
                    placement, len(items))
        return result_items
        
    def _build_url(self, base_url: str, params: Dict[str, str]) -> str:
        """
        Build URL with parameters
        
        Args:
            base_url: Base URL
            params: URL parameters
            
        Returns:
            str: Complete URL with parameters
        """
        if not params:
            return base_url
            
        # URL encode parameter values to handle special characters
        import urllib.parse
        param_strings = [f"{key}={urllib.parse.quote_plus(str(value))}" for key, value in params.items()]
        param_string = "&".join(param_strings)
        
        # Add to base URL
        separator = "&" if "?" in base_url else "?"
        final_url = f"{base_url}{separator}{param_string}"
        
        # Debug logging
        logger.debug("🔍 URL BUILD: base='%s' + params=%s = '%s'", base_url, params, final_url)
        return final_url
        
    def get_pagination_status_info(self, pagination_info: PaginationInfo) -> Dict[str, str]:
        """
        Get human-readable pagination status information
        
        Args:
            pagination_info: Pagination information
            
        Returns:
            Dict: Status information with formatted strings
        """
        mode = self.settings.get_list_pagination_mode()
        device_tier = self.memory_profiler.detect_memory_tier()
        
        if pagination_info.total_pages <= 1:
            status = f"Showing all {pagination_info.total_items} items"
        else:
            item_range = f"{pagination_info.start_index + 1}-{pagination_info.end_index}"
            status = f"Showing {item_range} of {pagination_info.total_items} items"
            
        return {
            'items_status': status,
            'page_status': f"Page {pagination_info.current_page} of {pagination_info.total_pages}",
            'pagination_mode': f"Mode: {mode.title()}",
            'device_tier': f"Device: {device_tier.replace('_', ' ').title()}",
            'page_size': f"Page size: {pagination_info.page_size}"
        }


# Global pagination manager instance
_pagination_manager = None


def get_pagination_manager() -> PaginationManager:
    """Get global pagination manager instance"""
    global _pagination_manager
    if _pagination_manager is None:
        _pagination_manager = PaginationManager()
    return _pagination_manager