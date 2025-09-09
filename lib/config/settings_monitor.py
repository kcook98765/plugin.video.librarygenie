#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Settings Monitor
Monitors settings changes and triggers appropriate actions
"""

import time
import threading
from typing import Optional, Dict, Any

import xbmc
from .settings import SettingsManager
from ..utils.logger import get_logger
from ..auth.auth_helper import get_auth_helper


class SettingsMonitor:
    """Monitors settings changes and triggers automatic actions"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = SettingsManager()
        self._last_otp_code = None
        self._monitoring = False
        self._monitor_thread = None
        
    def start_monitoring(self):
        """Start monitoring settings changes"""
        if self._monitoring:
            self.logger.debug("Settings monitor already running")
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("Settings monitor started")
        
    def stop_monitoring(self):
        """Stop monitoring settings changes"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        self.logger.info("Settings monitor stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting settings monitoring loop")
        
        # Initialize with current OTP code
        self._last_otp_code = self.settings.get_ai_search_otp_code()
        
        while self._monitoring:
            try:
                # Check for OTP code changes
                current_otp_code = self.settings.get_ai_search_otp_code()
                
                if current_otp_code and current_otp_code != self._last_otp_code:
                    self.logger.info(f"OTP code change detected: '{self._last_otp_code}' -> '{current_otp_code}'")
                    self._handle_otp_code_change(current_otp_code)
                    self._last_otp_code = current_otp_code
                elif current_otp_code != self._last_otp_code:
                    # Code was cleared
                    self._last_otp_code = current_otp_code
                    
                # Sleep for a short interval
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                self.logger.error(f"Error in settings monitor loop: {e}")
                time.sleep(5)  # Longer sleep on error
                
    def _handle_otp_code_change(self, otp_code: str):
        """Handle OTP code change by triggering authorization flow"""
        try:
            self.logger.info(f"Triggering automatic OTP authorization for code: {otp_code}")
            
            # Validate OTP code format
            if not otp_code or len(otp_code.strip()) != 8:
                self.logger.warning(f"Invalid OTP code format: {otp_code}")
                return
                
            # Check if server URL is configured
            server_url = self.settings.get_ai_search_server_url()
            if not server_url:
                self.logger.warning("Server URL not configured, cannot process OTP")
                return
                
            # Get auth helper and exchange OTP for API key
            from ..auth.otp_auth import exchange_otp_for_api_key
            
            self.logger.info("Exchanging OTP code for API key automatically")
            result = exchange_otp_for_api_key(otp_code, server_url)
            
            if result.get('success'):
                self.logger.info("Automatic OTP authorization successful")
                
                # Clear the OTP code from settings after successful exchange
                self.settings.set_ai_search_otp_code("")
                self._last_otp_code = ""
                
                # Set activated status
                self.settings.set_ai_search_activated(True)
                
                # Show success notification
                import xbmcgui
                xbmcgui.Dialog().notification(
                    "AI Search Authorization",
                    f"Successfully authorized! User: {result.get('user_email', 'Unknown')}",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )
                
            else:
                error_msg = result.get('error', 'Unknown error')
                self.logger.error(f"Automatic OTP authorization failed: {error_msg}")
                
                # Show error notification
                import xbmcgui
                xbmcgui.Dialog().notification(
                    "AI Search Authorization Failed",
                    f"Error: {error_msg[:50]}...",
                    xbmcgui.NOTIFICATION_ERROR,
                    8000
                )
                
        except Exception as e:
            self.logger.error(f"Error handling OTP code change: {e}")
            
            # Show error notification
            import xbmcgui
            xbmcgui.Dialog().notification(
                "Authorization Error",
                f"Failed to process OTP: {str(e)[:50]}...",
                xbmcgui.NOTIFICATION_ERROR,
                8000
            )


# Global settings monitor instance
_settings_monitor: Optional[SettingsMonitor] = None


def get_settings_monitor() -> SettingsMonitor:
    """Get or create the global settings monitor instance"""
    global _settings_monitor
    if _settings_monitor is None:
        _settings_monitor = SettingsMonitor()
    return _settings_monitor


def start_settings_monitor():
    """Start the global settings monitor"""
    monitor = get_settings_monitor()
    monitor.start_monitoring()


def stop_settings_monitor():
    """Stop the global settings monitor"""
    global _settings_monitor
    if _settings_monitor:
        _settings_monitor.stop_monitoring()
        _settings_monitor = None