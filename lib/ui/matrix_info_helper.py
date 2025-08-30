
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Matrix Info Helper
Provides functionality to open info dialogs for Kodi v19 library items using XSP navigation
"""

import json
import time
import os
import html
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import xbmc
import xbmcvfs

from ..utils.logger import get_logger


class MatrixInfoHelper:
    """Helper for opening info dialogs on Kodi v19 library items"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.LIST_ID = 50  # Working list control ID for Matrix
        self.VIDEOS_WINDOW = "MyVideoNav.xml"
    
    def open_movie_info(self, movieid: int, return_path: Optional[str] = None) -> bool:
        """
        Open info dialog for a movie on Kodi v19 using XSP navigation
        
        Args:
            movieid: Kodi movie database ID
            return_path: Path to return to when info is closed (defaults to current container path)
            
        Returns:
            bool: True if info dialog was successfully opened
        """
        try:
            self.logger.info(f"Opening Matrix info dialog for movie {movieid}")
            
            # Get return path if not provided
            if not return_path:
                return_path = xbmc.getInfoLabel('Container.FolderPath') or ''
            
            # Verify the movie exists and get details
            movie_details = self._get_movie_details(movieid)
            if not movie_details:
                self.logger.error(f"Movie {movieid} not found in library")
                return False
            
            title = movie_details.get("title", "Unknown")
            self.logger.debug(f"Found movie: {title}")
            
            # Create XSP for this specific movie
            xsp_path = self._create_movie_xsp(movieid)
            if not xsp_path:
                self.logger.error("Failed to create smart playlist")
                return False
            
            # Navigate to XSP and wait for it to load
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{xsp_path}",return)')
            
            if not self._wait_for_xsp_loaded(xsp_path):
                self.logger.error("Timed out waiting for playlist to load")
                self._cleanup_xsp(xsp_path)
                return False
            
            # Focus the list control
            if not self._focus_list():
                self.logger.error("Failed to focus list")
                self._cleanup_xsp(xsp_path)
                return False
            
            # Navigate to find the correct movie item
            if not self._navigate_to_movie(movieid):
                self.logger.warning(f"Could not navigate to movie {movieid}")
                # Continue anyway - might still work
            
            # Open info dialog and swap container underneath
            xbmc.executebuiltin('Action(Info)')
            self._swap_container_under_info(return_path, xsp_path)
            
            # Verify info dialog opened
            if self._wait_for_info_dialog():
                self.logger.info(f"Successfully opened info dialog for {title}")
                return True
            else:
                self.logger.error("Info dialog failed to open")
                self._cleanup_xsp(xsp_path)
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to open movie info for {movieid}: {e}")
            return False
    
    def _get_movie_details(self, movieid: int) -> Optional[Dict[str, Any]]:
        """Get movie details from Kodi library"""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetMovieDetails",
                "params": {
                    "movieid": movieid,
                    "properties": ["title", "file"]
                },
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                self.logger.error(f"JSON-RPC error getting movie {movieid}: {response['error']}")
                return None
            
            return response.get("result", {}).get("moviedetails")
            
        except Exception as e:
            self.logger.error(f"Exception getting movie details for {movieid}: {e}")
            return None
    
    def _create_movie_xsp(self, movieid: int) -> Optional[str]:
        """Create smart playlist XSP file for a specific movie"""
        try:
            movie_details = self._get_movie_details(movieid)
            if not movie_details:
                return None
            
            file_path = movie_details.get("file")
            if not file_path:
                self.logger.error(f"No file path for movie {movieid}")
                return None
            
            filename = os.path.basename(file_path)
            self.logger.debug(f"Creating XSP for filename: {filename}")
            
            xsp_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
    <name>LibraryGenie Info Helper - Movie {movieid}</name>
    <match>all</match>
    <rule field="filename" operator="is">
        <value>{html.escape(filename)}</value>
    </rule>
    <order direction="ascending">title</order>
</smartplaylist>"""
            
            xsp_path = f"special://temp/libgenie_info_{movieid}.xsp"
            
            if self._write_xsp_file(xsp_path, xsp_content):
                self.logger.debug(f"Created XSP at {xsp_path}")
                return xsp_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to create XSP for movie {movieid}: {e}")
            return None
    
    def _write_xsp_file(self, path: str, content: str) -> bool:
        """Write XSP content to special:// path"""
        try:
            f = xbmcvfs.File(path, 'w')
            f.write(content.encode('utf-8'))
            f.close()
            return True
        except Exception as e:
            self.logger.error(f"Failed to write XSP file {path}: {e}")
            return False
    
    def _wait_for_xsp_loaded(self, xsp_path: str, timeout_ms: int = 8000) -> bool:
        """Wait for XSP to load in Videos window"""
        try:
            target_path = xsp_path.rstrip('/')
            start_time = time.time() * 1000
            
            while (time.time() * 1000 - start_time) < timeout_ms:
                if not xbmc.getCondVisibility(f'Window.IsActive({self.VIDEOS_WINDOW})'):
                    xbmc.sleep(120)
                    continue
                
                current_path = (xbmc.getInfoLabel('Container.FolderPath') or '').rstrip('/')
                num_items = int(xbmc.getInfoLabel('Container.NumItems') or '0')
                is_busy = xbmc.getCondVisibility('Window.IsActive(DialogBusy.xml)')
                
                if current_path == target_path and num_items > 0 and not is_busy:
                    return True
                
                xbmc.sleep(120)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for XSP to load: {e}")
            return False
    
    def _focus_list(self, tries: int = 20) -> bool:
        """Focus the list control"""
        try:
            for _ in range(tries):
                xbmc.executebuiltin(f'SetFocus({self.LIST_ID})')
                if xbmc.getCondVisibility(f'Control.HasFocus({self.LIST_ID})'):
                    return True
                xbmc.sleep(30)
            return False
        except Exception as e:
            self.logger.error(f"Error focusing list: {e}")
            return False
    
    def _navigate_to_movie(self, movieid: int, max_attempts: int = 10) -> bool:
        """Navigate using Down arrow to find the correct movie item"""
        try:
            for attempt in range(max_attempts):
                current_dbid = xbmc.getInfoLabel('ListItem.DBID')
                if current_dbid == str(movieid):
                    self.logger.debug(f"Found target movie at attempt {attempt + 1}")
                    return True
                
                xbmc.executebuiltin('Action(Down)')
                xbmc.sleep(150)
            
            self.logger.warning(f"Could not find movie {movieid} after {max_attempts} navigation attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to movie {movieid}: {e}")
            return False
    
    def _swap_container_under_info(self, return_path: str, xsp_path: str, timeout_ms: int = 2000):
        """Wait for info dialog to open, then replace container underneath"""
        try:
            if self._wait_for_info_dialog(timeout_ms):
                self.logger.debug(f"Swapping container back to: {return_path}")
                xbmc.executebuiltin(f'Container.Update("{return_path}",replace)')
                # Clean up XSP after successful swap
                self._cleanup_xsp(xsp_path)
            else:
                self.logger.warning("Info dialog did not open in time for container swap")
                self._cleanup_xsp(xsp_path)
        except Exception as e:
            self.logger.error(f"Error during container swap: {e}")
            self._cleanup_xsp(xsp_path)
    
    def _wait_for_info_dialog(self, timeout_ms: int = 1500) -> bool:
        """Wait for info dialog to open"""
        try:
            start_time = time.time() * 1000
            while (time.time() * 1000 - start_time) < timeout_ms:
                if xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)'):
                    return True
                xbmc.sleep(30)
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for info dialog: {e}")
            return False
    
    def _cleanup_xsp(self, xsp_path: str):
        """Clean up temporary XSP file"""
        try:
            if xsp_path and xbmcvfs.exists(xsp_path):
                xbmcvfs.delete(xsp_path)
                self.logger.debug(f"Cleaned up XSP: {xsp_path}")
        except Exception as e:
            self.logger.debug(f"XSP cleanup failed (non-critical): {e}")


# Global helper instance
_matrix_info_helper = None


def get_matrix_info_helper() -> MatrixInfoHelper:
    """Get global Matrix info helper instance"""
    global _matrix_info_helper
    if _matrix_info_helper is None:
        _matrix_info_helper = MatrixInfoHelper()
    return _matrix_info_helper


def open_movie_info_v19(movieid: int, return_path: Optional[str] = None) -> bool:
    """
    Convenience function to open movie info dialog on Kodi v19
    
    Args:
        movieid: Kodi movie database ID
        return_path: Optional path to return to when info is closed
        
    Returns:
        bool: True if info dialog was successfully opened
    """
    helper = get_matrix_info_helper()
    return helper.open_movie_info(movieid, return_path)
