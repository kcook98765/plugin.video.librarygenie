#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Sync Controller
Centralized control for all movie and TV episode sync operations
"""

from __future__ import annotations

import time
from typing import Optional, Tuple, Dict, Any

from ..config.settings import SettingsManager
from ..utils.logger import get_logger
from ..ui.localization import L
from .scanner import LibraryScanner


class SyncController:
    """Centralized controller for all library sync operations"""

    # Class-level flag to prevent duplicate scans
    _sync_in_progress = False

    def __init__(self):
        self.settings = SettingsManager()
        self.logger = get_logger(__name__)
        self.scanner = LibraryScanner()

    def is_first_run(self) -> bool:
        """Check if this is the first run that needs setup"""
        return not self.settings.get_first_run_completed()

    def complete_first_run_setup(self, sync_movies: bool = True, sync_tv_episodes: bool = False) -> None:
        """Complete first run setup with user's sync preferences"""
        try:
            self.logger.info("Completing first run setup - Movies: %s, TV: %s", sync_movies, sync_tv_episodes)
            
            # Set user preferences
            self.settings.set_sync_movies(sync_movies)
            self.settings.set_sync_tv_episodes(sync_tv_episodes)
            
            # Mark first run as completed
            self.settings.set_first_run_completed(True)
            
            # Set initial sync request flag for service to pick up (non-blocking)
            if sync_movies or sync_tv_episodes:
                self.settings.addon.setSetting('initial_sync_requested', 'true')
                self.settings.addon.setSetting('initial_sync_movies', str(sync_movies).lower())
                self.settings.addon.setSetting('initial_sync_tv_episodes', str(sync_tv_episodes).lower())
                self.logger.info("Initial sync requested - service will process in background")
            else:
                self.logger.info("No sync options enabled in first run setup")
                
        except Exception as e:
            self.logger.error("Error during first run setup: %s", e)
            raise

    def perform_manual_sync(self, progress_dialog=None, progress_callback=None) -> Tuple[bool, str]:
        """
        Perform manual library sync based on current toggle states
        Returns: (success, status_message)
        """
        # Import global lock
        from lib.utils.sync_lock import GlobalSyncLock
        
        # Try to acquire global cross-process lock
        lock = GlobalSyncLock("sync-controller")
        if not lock.acquire():
            lock_info = lock.get_lock_info()
            owner = lock_info.get('owner', 'unknown') if lock_info else 'unknown'
            message = f"Sync already in progress by {owner} - skipping duplicate sync"
            self.logger.info(message)
            return False, message
            
        try:
            
            sync_movies = self.settings.get_sync_movies()
            sync_tv_episodes = self.settings.get_sync_tv_episodes()
            
            if not sync_movies and not sync_tv_episodes:
                message = "No sync options enabled. Enable Movies or TV Episodes sync in settings."
                self.logger.info(message)
                return False, message

            self.logger.info("Starting manual library sync - Movies: %s, TV: %s", sync_movies, sync_tv_episodes)
            
            start_time = time.time()
            results = {'movies': 0, 'episodes': 0, 'errors': []}
            
            # Sync movies if enabled
            if sync_movies:
                try:
                    if progress_dialog:
                        progress_dialog.update(30, "LibraryGenie", "Syncing movies...")
                    movie_count = self._sync_movies(progress_dialog=progress_dialog)
                    results['movies'] = movie_count
                    self.logger.info("Synced %d movies", movie_count)
                except Exception as e:
                    error_msg = f"Movie sync failed: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)

            # Sync TV episodes if enabled
            if sync_tv_episodes:
                try:
                    if progress_dialog:
                        progress_dialog.update(60, "LibraryGenie", "Syncing TV episodes...")
                    episode_count = self._sync_tv_episodes(progress_dialog=progress_dialog)
                    results['episodes'] = episode_count
                    self.logger.info("Synced %d TV episodes", episode_count)
                except Exception as e:
                    error_msg = f"TV episode sync failed: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)

            # Calculate duration and create status message
            duration = time.time() - start_time
            message = self._format_sync_results(results, duration)
            
            success = len(results['errors']) == 0 or (results['movies'] > 0 or results['episodes'] > 0)
            return success, message

        except Exception as e:
            error_msg = f"Manual sync failed: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        finally:
            # Always release global lock when done
            lock.release()

    def perform_periodic_sync(self) -> bool:
        """
        Perform periodic sync check based on current settings
        Called by background service instead of auto-trigger monitoring
        Returns: True if sync was performed
        """
        try:
            # Skip if first run not completed
            if self.is_first_run():
                self.logger.debug("Skipping periodic sync - first run not completed")
                return False

            # Skip if sync already in progress (prevents duplicate scans)
            if SyncController._sync_in_progress:
                self.logger.debug("Skipping periodic sync - sync already in progress")
                return False

            sync_movies = self.settings.get_sync_movies()
            sync_tv_episodes = self.settings.get_sync_tv_episodes()
            
            # Skip if no sync options enabled
            if not sync_movies and not sync_tv_episodes:
                self.logger.debug("Skipping periodic sync - no sync options enabled")
                return False

            # Check if library has changed since last sync
            if not self._should_perform_periodic_sync():
                self.logger.debug("Skipping periodic sync - no library changes detected")
                return False

            self.logger.info("Starting periodic library sync")
            success, message = self.perform_manual_sync()
            
            if success:
                self.logger.info("Periodic sync completed: %s", message)
            else:
                self.logger.warning("Periodic sync had issues: %s", message)
                
            return success

        except Exception as e:
            self.logger.error("Error during periodic sync: %s", e)
            return False

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync configuration and status"""
        return {
            'first_run_completed': self.settings.get_first_run_completed(),
            'sync_movies_enabled': self.settings.get_sync_movies(),
            'sync_tv_episodes_enabled': self.settings.get_sync_tv_episodes(),
            'track_library_changes': self.settings.get_track_library_changes(),
        }

    def _sync_movies(self, progress_dialog=None) -> int:
        """Sync movies and return count"""
        try:
            # Use existing scanner logic for movies
            result = self.scanner.perform_full_scan(progress_dialog=progress_dialog)
            if result.get("success", False):
                return result.get("items_added", 0)
            else:
                raise Exception(f"Movie scan failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.logger.error("Error syncing movies: %s", e)
            raise

    def _sync_tv_episodes(self, progress_dialog=None) -> int:
        """Sync TV episodes and return count"""
        try:
            # Use scanner's TV episodes scan method
            result = self.scanner.perform_tv_episodes_only_scan(progress_dialog=progress_dialog)
            if result.get("success", False):
                return result.get("episodes_added", 0)
            else:
                raise Exception(f"TV episode scan failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.logger.error("Error syncing TV episodes: %s", e)
            raise

    def _should_perform_periodic_sync(self) -> bool:
        """Check if periodic sync should be performed based on library changes"""
        try:
            # If library change tracking is disabled, always sync
            if not self.settings.get_track_library_changes():
                return True
                
            # Check for library changes since last scan
            # This would integrate with existing library change detection logic
            # For now, return True to ensure sync happens
            return True
            
        except Exception as e:
            self.logger.error("Error checking if periodic sync needed: %s", e)
            return True  # Err on the side of syncing

    def _format_sync_results(self, results: Dict[str, Any], duration: float) -> str:
        """Format sync results into a user-friendly message"""
        try:
            parts = []
            
            if results['movies'] > 0:
                parts.append(f"{results['movies']} movies")
            
            if results['episodes'] > 0:
                parts.append(f"{results['episodes']} episodes")
                
            if not parts:
                if results['errors']:
                    return f"Sync failed: {'; '.join(results['errors'])}"
                else:
                    return "No new items found"
            
            items_text = " and ".join(parts)
            time_text = f"in {duration:.1f}s"
            
            message = f"Synced {items_text} {time_text}"
            
            if results['errors']:
                message += f" (with {len(results['errors'])} error(s))"
                
            return message
            
        except Exception as e:
            self.logger.error("Error formatting sync results: %s", e)
            return "Sync completed with unknown results"