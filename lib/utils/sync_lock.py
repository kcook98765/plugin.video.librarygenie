"""
Cross-process sync lock for preventing duplicate library scans
Uses Window property + lockfile for bulletproof duplicate prevention
"""

import time
import json
import os
from typing import Optional, Dict, Any
from lib.utils.logger import get_logger


class GlobalSyncLock:
    """Cross-process lock to prevent duplicate library scans"""
    
    WINDOW_PROPERTY = 'librarygenie.sync.lock'
    LOCK_FILE = 'special://temp/librarygenie_sync.lock'
    LOCK_TTL = 3600  # 1 hour TTL for stale locks
    
    def __init__(self, owner: str = "unknown"):
        self.owner = owner
        self.logger = get_logger(__name__)
        self.locked = False
        
    def acquire(self) -> bool:
        """
        Acquire the global sync lock
        Returns: True if lock acquired, False if already held by another process
        """
        try:
            import xbmc
            import xbmcgui
            import xbmcvfs
            
            # Check Window property first (fastest check)
            window = xbmcgui.Window(10000)  # Home window - always available
            existing_prop = window.getProperty(self.WINDOW_PROPERTY)
            
            if existing_prop:
                # Parse existing lock info
                try:
                    lock_info = json.loads(existing_prop)
                    lock_time = lock_info.get('timestamp', 0)
                    
                    # Check if lock is stale (TTL expired)
                    if time.time() - lock_time > self.LOCK_TTL:
                        self.logger.info("Stale lock detected - clearing expired lock")
                        self._force_release()
                    else:
                        # Valid lock held by another process
                        lock_owner = lock_info.get('owner', 'unknown')
                        self.logger.info("Sync lock already held by: %s", lock_owner)
                        return False
                except (json.JSONDecodeError, KeyError) as e:
                    self.logger.warning("Invalid lock property format - clearing: %s", e)
                    self._force_release()
            
            # Check lockfile as secondary verification
            if xbmcvfs.exists(self.LOCK_FILE):
                try:
                    lock_file = xbmcvfs.File(self.LOCK_FILE, 'r')
                    lock_content = lock_file.read()
                    lock_file.close()
                    
                    if lock_content:
                        lock_info = json.loads(lock_content)
                        lock_time = lock_info.get('timestamp', 0)
                        
                        # Check TTL on lockfile too
                        if time.time() - lock_time > self.LOCK_TTL:
                            self.logger.info("Stale lockfile detected - removing")
                            xbmcvfs.delete(self.LOCK_FILE)
                        else:
                            lock_owner = lock_info.get('owner', 'unknown')
                            self.logger.info("Lockfile exists for owner: %s", lock_owner)
                            return False
                except (json.JSONDecodeError, Exception) as e:
                    self.logger.warning("Invalid lockfile - removing: %s", e)
                    xbmcvfs.delete(self.LOCK_FILE)
            
            # Both checks passed - acquire the lock
            lock_info = {
                'owner': self.owner,
                'timestamp': time.time(),
                'pid': os.getpid() if hasattr(os, 'getpid') else 0
            }
            lock_data = json.dumps(lock_info)
            
            # Set Window property
            window.setProperty(self.WINDOW_PROPERTY, lock_data)
            
            # Create lockfile
            lock_file = xbmcvfs.File(self.LOCK_FILE, 'w')
            lock_file.write(lock_data)
            lock_file.close()
            
            self.locked = True
            self.logger.info("Global sync lock acquired by: %s", self.owner)
            return True
            
        except Exception as e:
            self.logger.error("Failed to acquire sync lock: %s", e)
            return False
    
    def release(self) -> None:
        """Release the global sync lock"""
        if not self.locked:
            return
            
        try:
            self._force_release()
            self.locked = False
            self.logger.info("Global sync lock released by: %s", self.owner)
            
        except Exception as e:
            self.logger.error("Failed to release sync lock: %s", e)
    
    def _force_release(self) -> None:
        """Force release lock (used for cleanup of stale locks)"""
        try:
            import xbmcgui
            import xbmcvfs
            
            # Clear Window property
            window = xbmcgui.Window(10000)
            window.clearProperty(self.WINDOW_PROPERTY)
            
            # Remove lockfile
            if xbmcvfs.exists(self.LOCK_FILE):
                xbmcvfs.delete(self.LOCK_FILE)
                
        except Exception as e:
            self.logger.error("Failed to force release lock: %s", e)
    
    def is_locked(self) -> bool:
        """Check if sync is currently locked by any process"""
        try:
            import xbmcgui
            import xbmcvfs
            
            # Quick check via Window property
            window = xbmcgui.Window(10000)
            existing_prop = window.getProperty(self.WINDOW_PROPERTY)
            
            if existing_prop:
                try:
                    lock_info = json.loads(existing_prop)
                    lock_time = lock_info.get('timestamp', 0)
                    
                    # Check if lock is stale
                    if time.time() - lock_time > self.LOCK_TTL:
                        return False  # Stale lock doesn't count
                    
                    return True  # Valid lock exists
                    
                except (json.JSONDecodeError, KeyError):
                    return False  # Invalid lock data
            
            return False  # No lock property
            
        except Exception as e:
            self.logger.error("Failed to check lock status: %s", e)
            return False
    
    def get_lock_info(self) -> Optional[Dict[str, Any]]:
        """Get information about current lock holder"""
        try:
            import xbmcgui
            
            window = xbmcgui.Window(10000)
            existing_prop = window.getProperty(self.WINDOW_PROPERTY)
            
            if existing_prop:
                return json.loads(existing_prop)
                
        except Exception as e:
            self.logger.error("Failed to get lock info: %s", e)
            
        return None
    
    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            raise RuntimeError(f"Could not acquire sync lock for {self.owner}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()