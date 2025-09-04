#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 11 Playback Actions
Safe playback handlers using Kodi built-ins and JSON-RPC
"""

import xbmc
import xbmcgui

import json
from typing import Optional, Dict, Any, List

from ..utils.logger import get_logger
from .localization import L


class PlaybackActionHandler:
    """Handles movie playback actions using Kodi's native mechanisms"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def play_movie(self, kodi_id: int, resume: bool = False) -> bool:
        """Play a movie by Kodi ID, optionally resuming from last position"""
        
        try:
            # Use JSON-RPC to start playback
            if resume:
                # Resume from last position
                request = {
                    "jsonrpc": "2.0",
                    "method": "Player.Open",
                    "params": {
                        "item": {"movieid": kodi_id},
                        "options": {"resume": True}
                    },
                    "id": 1
                }
            else:
                # Play from beginning
                request = {
                    "jsonrpc": "2.0", 
                    "method": "Player.Open",
                    "params": {
                        "item": {"movieid": kodi_id}
                    },
                    "id": 1
                }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                self.logger.error(f"Playback failed: {response['error']}")
                return False
            
            self.logger.info(f"Successfully started playback of movie {kodi_id} (resume={resume})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting playback for movie {kodi_id}: {e}")
            return False
    
    def queue_movie(self, kodi_id: int) -> bool:
        """Add movie to the current playlist"""
        
        try:
            # Add to video playlist
            request = {
                "jsonrpc": "2.0",
                "method": "Playlist.Add",
                "params": {
                    "playlistid": 1,  # Video playlist
                    "item": {"movieid": kodi_id}
                },
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                self.logger.error(f"Queue failed: {response['error']}")
                return False
            
            self.logger.info(f"Successfully queued movie {kodi_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error queuing movie {kodi_id}: {e}")
            return False
    
    def show_movie_info(self, kodi_id: int) -> bool:
        """Show the movie information dialog"""
        
        try:
            # Use built-in function to show info dialog
            builtin_cmd = f"Action(Info,{kodi_id})"
            xbmc.executebuiltin(builtin_cmd)
            
            self.logger.info(f"Opened info dialog for movie {kodi_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error showing info for movie {kodi_id}: {e}")
            # Try alternative method
            try:
                builtin_cmd = f"ShowVideoInfo({kodi_id})"
                xbmc.executebuiltin(builtin_cmd)
                return True
            except:
                return False
    
    def get_movie_resume_info(self, kodi_id: int) -> Optional[Dict[str, Any]]:
        """Get resume information for a movie"""
        
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetMovieDetails",
                "params": {
                    "movieid": kodi_id,
                    "properties": ["resume", "runtime"]
                },
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                self.logger.error(f"Failed to get resume info: {response['error']}")
                return None
            
            movie_details = response.get("result", {}).get("moviedetails", {})
            resume_data = movie_details.get("resume", {})
            runtime = movie_details.get("runtime", 0)
            
            return {
                "position": resume_data.get("position", 0),
                "total": resume_data.get("total", runtime * 60)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting resume info for movie {kodi_id}: {e}")
            return None
    
    def check_player_status(self) -> Dict[str, Any]:
        """Check current player status"""
        
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "Player.GetActivePlayers",
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                return {"active": False, "type": "none"}
            
            players = response.get("result", [])
            if players:
                player = players[0]
                return {
                    "active": True,
                    "type": player.get("type", "unknown"),
                    "playerid": player.get("playerid", -1)
                }
            else:
                return {"active": False, "type": "none"}
                
        except Exception as e:
            self.logger.error(f"Error checking player status: {e}")
            return {"active": False, "type": "none"}
    
    def stop_playback(self) -> bool:
        """Stop current playback"""
        
        try:
            player_status = self.check_player_status()
            if not player_status["active"]:
                return True  # Nothing to stop
            
            request = {
                "jsonrpc": "2.0",
                "method": "Player.Stop",
                "params": {
                    "playerid": player_status["playerid"]
                },
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                self.logger.error(f"Stop playback failed: {response['error']}")
                return False
            
            self.logger.info("Successfully stopped playback")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping playback: {e}")
            return False
    
    def handle_playback_error(self, error_message: str, kodi_id: Optional[int] = None):
        """Handle playback errors with user-friendly messages"""
        
        self.logger.error(f"Playback error for movie {kodi_id}: {error_message}")
        
        # Show user-friendly error dialog
        dialog = xbmcgui.Dialog()
        dialog.ok(L(35001) or "Playback Error", 
                 f"Unable to play movie.\n{error_message}\n\nPlease check that the file exists and is accessible.")
        
    def get_movie_file_path(self, kodi_id: int) -> Optional[str]:
        """Get the file path for a movie"""
        
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetMovieDetails",
                "params": {
                    "movieid": kodi_id,
                    "properties": ["file"]
                },
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response = json.loads(response_str)
            
            if "error" in response:
                return None
            
            movie_details = response.get("result", {}).get("moviedetails", {})
            return movie_details.get("file")
            
        except Exception as e:
            self.logger.error(f"Error getting file path for movie {kodi_id}: {e}")
            return None


class PlaybackContextMenuHandler:
    """Handles context menu actions for playback"""
    
    def __init__(self, base_url: str, string_getter=None):
        self.logger = get_logger(__name__)
        self.base_url = base_url
        self.playback_handler = PlaybackActionHandler()
        self._get_string = string_getter or self._fallback_string_getter
    
    def handle_playback_action(self, action: str, kodi_id: int) -> bool:
        """Handle a playback action from the context menu"""
        
        try:
            kodi_id = int(kodi_id)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid kodi_id for playback action: {kodi_id}")
            return False
        
        success = False
        
        if action == "play_movie":
            success = self.playback_handler.play_movie(kodi_id, resume=False)
            if not success:
                self.playback_handler.handle_playback_error("Failed to start playback", kodi_id)
        
        elif action == "resume_movie":
            success = self.playback_handler.play_movie(kodi_id, resume=True)
            if not success:
                self.playback_handler.handle_playback_error("Failed to resume playback", kodi_id)
        
        elif action == "queue_movie":
            success = self.playback_handler.queue_movie(kodi_id)
            if success:
                # Show confirmation
                xbmcgui.Dialog().notification(L(35002) or "LibraryGenie", 
                                            L(35010) or "Movie added to playlist", 
                                            xbmcgui.NOTIFICATION_INFO, 2000)
        
        elif action == "show_info":
            success = self.playback_handler.show_movie_info(kodi_id)
        
        else:
            self.logger.warning(f"Unknown playback action: {action}")
            return False
        
        if success:
            self.logger.info(f"Successfully handled playback action: {action} for movie {kodi_id}")
        
        return success
    
    def _fallback_string_getter(self, string_id: int) -> str:
        """Fallback string getter"""
        strings = {
            35001: "Play",
            35002: "Resume",
            35003: "Add to Queue", 
            35004: "Movie Information"
        }
        return strings.get(string_id, f"String {string_id}")


# Global handler instances
_playback_handler = None
_context_handler = None


def get_playback_handler():
    """Get global playback action handler"""
    global _playback_handler
    if _playback_handler is None:
        _playback_handler = PlaybackActionHandler()
    return _playback_handler


def get_context_menu_handler(base_url: str, string_getter=None):
    """Get context menu handler for playback actions"""
    return PlaybackContextMenuHandler(base_url, string_getter)