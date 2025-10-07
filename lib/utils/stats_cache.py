#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Stats Cache
Handles caching of library statistics to avoid redundant API calls
"""

import json
import os
from typing import Optional, Dict, Any
from datetime import datetime

from lib.utils.kodi_log import get_kodi_logger
from lib.data.storage_manager import get_storage_manager


class StatsCache:
    """Manages library statistics caching"""
    
    STATS_FILENAME = "library_stats.json"
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.utils.stats_cache')
        self.storage_manager = get_storage_manager()
        
    def _get_stats_file_path(self) -> str:
        """Get the full path to the stats cache file"""
        profile_path = self.storage_manager.get_profile_path()
        return os.path.join(profile_path, self.STATS_FILENAME)
    
    def fetch_and_save_stats(self) -> bool:
        """
        Fetch library stats from AI server and save to file
        
        Returns:
            bool: True if successfully fetched and saved, False otherwise
        """
        try:
            from lib.remote.ai_search_client import get_ai_search_client
            
            ai_client = get_ai_search_client()
            
            # Check if AI search is activated
            if not ai_client.is_activated():
                self.logger.debug("AI search not activated, skipping stats fetch")
                return False
            
            # Fetch stats from API
            self.logger.info("Fetching library stats from AI server...")
            stats = ai_client.get_library_stats()
            
            if not stats:
                self.logger.warning("Failed to fetch library stats from server")
                return False
            
            # Add metadata
            stats_data = {
                "stats": stats,
                "fetched_at": datetime.now().isoformat(),
                "version": 1
            }
            
            # Save to file
            stats_file = self._get_stats_file_path()
            
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(stats_file), exist_ok=True)
            
            with open(stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2)
            
            self.logger.info("Library stats saved to: %s", stats_file)
            return True
            
        except Exception as e:
            self.logger.error("Error fetching and saving stats: %s", e)
            return False
    
    def load_stats(self) -> Optional[Dict[str, Any]]:
        """
        Load library stats from cached file
        
        Returns:
            Dict with stats data or None if not available
        """
        try:
            stats_file = self._get_stats_file_path()
            
            # Check if file exists
            if not os.path.exists(stats_file):
                self.logger.debug("Stats cache file not found: %s", stats_file)
                return None
            
            # Load from file
            with open(stats_file, 'r') as f:
                stats_data = json.load(f)
            
            # Validate structure
            if "stats" not in stats_data:
                self.logger.warning("Invalid stats cache format")
                return None
            
            self.logger.debug("Loaded stats from cache (fetched: %s)", 
                            stats_data.get('fetched_at', 'unknown'))
            
            return stats_data.get("stats")
            
        except Exception as e:
            self.logger.error("Error loading stats from cache: %s", e)
            return None
    
    def clear_stats(self) -> bool:
        """
        Clear the stats cache file
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            stats_file = self._get_stats_file_path()
            
            if os.path.exists(stats_file):
                os.remove(stats_file)
                self.logger.info("Stats cache cleared")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error("Error clearing stats cache: %s", e)
            return False


# Singleton instance
_stats_cache_instance = None

def get_stats_cache() -> StatsCache:
    """Get singleton StatsCache instance"""
    global _stats_cache_instance
    if _stats_cache_instance is None:
        _stats_cache_instance = StatsCache()
    return _stats_cache_instance
