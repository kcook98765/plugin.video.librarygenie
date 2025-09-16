#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Device Memory Detection Utility
Detects available device memory for adaptive pagination sizing
"""

import xbmc
from typing import Dict, Optional, Any, Union
from lib.utils.kodi_log import get_kodi_logger

logger = get_kodi_logger('lib.utils.device_memory')


class DeviceMemoryProfiler:
    """Detects and profiles device memory characteristics for adaptive pagination"""
    
    def __init__(self):
        self._cached_tier = None
        self._cached_memory_mb = None
        
    def detect_memory_tier(self) -> str:
        """
        Detect device memory tier for adaptive pagination
        
        Returns:
            str: 'very_low', 'low', 'medium', or 'high'
        """
        if self._cached_tier is not None:
            return self._cached_tier
            
        memory_mb = self._get_available_memory_mb()
        self._cached_memory_mb = memory_mb
        
        # Define memory tiers based on available RAM
        if memory_mb < 512:
            tier = 'very_low'
        elif memory_mb < 1024:
            tier = 'low' 
        elif memory_mb < 2048:
            tier = 'medium'
        else:
            tier = 'high'
            
        self._cached_tier = tier
        logger.debug("Detected memory tier: %s (available: %d MB)", tier, memory_mb)
        return tier
        
    def get_optimal_page_size(self, base_size: int = 100) -> int:
        """
        Get optimal page size based on device memory tier
        
        Args:
            base_size: Base page size to scale from
            
        Returns:
            int: Optimal page size for device
        """
        tier = self.detect_memory_tier()
        
        # Define scaling factors for each tier
        scaling_factors = {
            'very_low': 0.25,   # 25% of base (25 items for base=100)
            'low': 0.5,         # 50% of base (50 items for base=100)
            'medium': 1.0,      # 100% of base (100 items for base=100)
            'high': 2.0         # 200% of base (200 items for base=100)
        }
        
        scale_factor = scaling_factors.get(tier, 1.0)
        optimal_size = int(base_size * scale_factor)
        
        # Apply safety bounds
        optimal_size = max(10, min(500, optimal_size))
        
        logger.debug("Optimal page size for tier %s: %d (scale factor: %.2f)", 
                    tier, optimal_size, scale_factor)
        return optimal_size
        
    def get_memory_info(self) -> Dict[str, Union[int, str]]:
        """
        Get detailed memory information
        
        Returns:
            dict: Memory information with keys: total_mb, free_mb, used_mb, tier
        """
        memory_mb = self._get_available_memory_mb()
        tier = self.detect_memory_tier()
        
        return {
            'available_mb': memory_mb,
            'tier': tier,
            'optimal_page_size': self.get_optimal_page_size()
        }
        
    def _get_available_memory_mb(self) -> int:
        """
        Get available memory in MB from Kodi system info
        
        Returns:
            int: Available memory in MB, or fallback value if detection fails
        """
        try:
            # Try to get free memory from Kodi
            free_memory = xbmc.getInfoLabel('System.Memory(free)')
            
            if free_memory:
                # Parse memory string (could be like "1024 MB" or "1.5 GB")
                memory_mb = self._parse_memory_string(free_memory)
                if memory_mb > 0:
                    return memory_mb
                    
            # Fallback: try total memory and estimate available as 70%
            total_memory = xbmc.getInfoLabel('System.Memory(total)')
            if total_memory:
                total_mb = self._parse_memory_string(total_memory)
                if total_mb > 0:
                    available_mb = int(total_mb * 0.7)  # Assume 70% available
                    logger.debug("Using estimated available memory: %d MB (70%% of %d MB total)", 
                               available_mb, total_mb)
                    return available_mb
                    
        except Exception as e:
            logger.warning("Error detecting system memory: %s", e)
            
        # Final fallback: conservative estimate for unknown devices
        fallback_mb = 1024  # Assume 1GB available as safe fallback
        logger.warning("Could not detect system memory, using fallback: %d MB", fallback_mb)
        return fallback_mb
        
    def _parse_memory_string(self, memory_str: str) -> int:
        """
        Parse Kodi memory string to MB
        
        Args:
            memory_str: Memory string like "1024 MB", "1.5 GB", "512"
            
        Returns:
            int: Memory in MB, or 0 if parsing fails
        """
        try:
            # Clean up the string
            memory_str = memory_str.strip().lower()
            
            # Extract numeric value
            import re
            numeric_match = re.search(r'(\d+\.?\d*)', memory_str)
            if not numeric_match:
                return 0
                
            value = float(numeric_match.group(1))
            
            # Determine unit
            if 'gb' in memory_str:
                return int(value * 1024)  # Convert GB to MB
            elif 'mb' in memory_str or 'mb' not in memory_str:
                return int(value)  # Already in MB or assume MB
            elif 'kb' in memory_str:
                return int(value / 1024)  # Convert KB to MB
            else:
                return int(value)  # Assume MB if no unit specified
                
        except Exception as e:
            logger.warning("Error parsing memory string '%s': %s", memory_str, e)
            return 0


# Global instance
_device_memory_profiler = None


def get_device_memory_profiler() -> DeviceMemoryProfiler:
    """Get global device memory profiler instance"""
    global _device_memory_profiler
    if _device_memory_profiler is None:
        _device_memory_profiler = DeviceMemoryProfiler()
    return _device_memory_profiler


def detect_optimal_page_size(base_size: int = 100) -> int:
    """
    Convenience function to get optimal page size for current device
    
    Args:
        base_size: Base page size to scale from
        
    Returns:
        int: Optimal page size
    """
    profiler = get_device_memory_profiler()
    return profiler.get_optimal_page_size(base_size)


def get_device_tier() -> str:
    """
    Convenience function to get current device memory tier
    
    Returns:
        str: Device tier ('very_low', 'low', 'medium', 'high')
    """
    profiler = get_device_memory_profiler()
    return profiler.detect_memory_tier()