#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Library Scanner
Handles full scans and delta detection of Kodi's video library
"""

import json
from datetime import datetime
from typing import List, Dict, Set, Any, Optional, Callable

from lib.data import QueryManager
from lib.data.connection_manager import get_connection_manager
from lib.kodi.json_rpc_client import get_kodi_client
from lib.utils.kodi_log import get_kodi_logger
from lib.utils.kodi_version import get_kodi_major_version
from lib.config.settings import SettingsManager

from lib.ui.localization import L

class LibraryScanner:
    """Scans and indexes Kodi's video library"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.library.scanner')
        self.query_manager = QueryManager()
        self.kodi_client = get_kodi_client()
        self.conn_manager = get_connection_manager()
        self.settings = SettingsManager()
        self.batch_size = 200  # Batch size for database operations
        self._abort_requested = False

    def request_abort(self):
        """Request abort of current scan operation"""
        self._abort_requested = True
        self.logger.info("Scan abort requested")

    def _should_abort(self) -> bool:
        """Check if scan should be aborted"""
        return self._abort_requested

    def perform_full_scan(self, progress_callback: Optional[Callable] = None, progress_dialog: Optional[Any] = None, use_dialog_bg: bool = False) -> Dict[str, Any]:
        """Perform a complete library scan with optional DialogBG support"""
        self.logger.info("Starting full library scan")

        # Initialize query manager
        if not self.query_manager.initialize():
            self.logger.error("Failed to initialize database for full scan")
            return {"success": False, "error": "Database initialization failed"}

        # Initialize progress dialog if requested
        dialog_bg = None
        if use_dialog_bg:
            import xbmcgui
            dialog_bg = xbmcgui.DialogProgressBG()
            dialog_bg.create("LibraryGenie", "Initializing library scan...")

        # Get current Kodi version for tracking
        try:
            current_version = get_kodi_major_version()
        except Exception as e:
            self.logger.warning("Failed to get Kodi version: %s", e)
            current_version = None

        scan_start = datetime.now().isoformat()

        try:
            # Reset abort flag
            self._abort_requested = False

            # Clear existing data (full refresh)
            if dialog_bg:
                dialog_bg.update(10, "LibraryGenie", "Clearing existing index...")
            elif progress_dialog:
                progress_dialog.update(20, "LibraryGenie", "Clearing existing index...")
            self._clear_library_index()

            # Get total count for progress tracking
            total_movies = self.kodi_client.get_movie_count()
            self.logger.info("Full scan: %s movies to process", total_movies)

            if total_movies == 0:
                if dialog_bg:
                    dialog_bg.update(100, "LibraryGenie", "No movies found")
                    dialog_bg.close()
                return {"success": True, "items_found": 0, "items_added": 0}

            # Calculate paging
            total_pages = (total_movies + self.batch_size - 1) // self.batch_size
            self.logger.info("Processing %s pages of %s items each", total_pages, self.batch_size)

            if dialog_bg:
                dialog_bg.update(20, "LibraryGenie", f"Processing {total_movies} movies...")
            elif progress_dialog:
                progress_dialog.update(30, "LibraryGenie", f"Processing {total_movies} movies...")

            # Process movies in pages
            offset = 0
            total_added = 0
            page_num = 0

            while offset < total_movies:
                page_num += 1

                # Check for abort between pages
                if self._should_abort():
                    self.logger.info("Full scan aborted by user at page %s/%s", page_num, total_pages)
                    if dialog_bg:
                        dialog_bg.update(100, "LibraryGenie", "Scan aborted")
                        dialog_bg.close()
                    return {"success": False, "error": "Scan aborted by user", "items_added": total_added}

                response = self.kodi_client.get_movies(offset, self.batch_size)
                movies = response.get("movies", [])

                if not movies:
                    break

                # Batch insert movies
                added_count = self._batch_insert_movies(movies)
                total_added += added_count

                offset += len(movies)
                items_processed = min(offset, total_movies)

                # Calculate percentage for more frequent updates
                progress_percentage = min(int((items_processed / total_movies) * 80) + 20, 100)  # Reserve 20% for initialization

                # Progress tracking without spam - only log via UI progress dialog

                # Call progress callback if provided
                if progress_callback:
                    try:
                        progress_callback(page_num, total_pages, items_processed)
                    except Exception as e:
                        self.logger.warning("Progress callback error: %s", e)
                
                # Update dialog progress more frequently
                progress_message = f"Processing: {items_processed}/{total_movies} ({progress_percentage}%)"
                if dialog_bg:
                    dialog_bg.update(progress_percentage, "LibraryGenie", progress_message)
                elif progress_dialog:
                    progress_dialog.update(progress_percentage, "LibraryGenie", progress_message)

                # Brief pause to allow UI updates - reduced for better performance
                import time
                time.sleep(0.05)  # Reduced from 0.1 to 0.05 seconds

            self.logger.info("=== MOVIE SYNC COMPLETE: %s movies successfully indexed ===", total_added)

            # TV Episode sync (if enabled) - read directly from Kodi to bypass caching
            total_episodes_added = 0
            import xbmcaddon
            fresh_addon = xbmcaddon.Addon()
            try:
                sync_tv_episodes = fresh_addon.getSettingBool('sync_tv_episodes')
            except Exception:
                sync_tv_episodes = False
                
            if sync_tv_episodes:
                self.logger.info("TV episode sync enabled - starting episode scan")
                try:
                    total_episodes_added = self._sync_tv_episodes(dialog_bg, progress_dialog, progress_callback)
                    self.logger.info("=== TV EPISODE SYNC COMPLETE: %s episodes successfully indexed ===", total_episodes_added)
                except Exception as e:
                    self.logger.error("TV episode sync failed: %s", e)
                    # Continue with scan completion even if TV sync fails
            else:
                self.logger.debug("TV episode sync disabled - skipping")

            scan_end = datetime.now().isoformat()

            self.logger.info("=== FULL LIBRARY SYNC COMPLETE ===\n" +
                              "  Movies: %s indexed\n" +
                              "  Episodes: %s indexed\n" +
                              "  Total: %s items processed", total_added, total_episodes_added, total_added + total_episodes_added)

            if dialog_bg:
                if total_episodes_added > 0:
                    dialog_bg.update(100, "LibraryGenie", f"Scan complete: {total_added} movies, {total_episodes_added} episodes indexed")
                else:
                    dialog_bg.update(100, "LibraryGenie", f"Scan complete: {total_added} movies indexed")
                dialog_bg.close()
            elif progress_dialog:
                progress_dialog.update(100, "LibraryGenie", "Full scan complete.")

            return {
                "success": True,
                "items_found": total_movies,
                "items_added": total_added,
                "episodes_added": total_episodes_added,
                "scan_time": scan_end
            }

        except Exception as e:
            self.logger.error("Full scan failed: %s", e)
            if dialog_bg:
                dialog_bg.update(100, "LibraryGenie", f"Scan failed: {e}")
                dialog_bg.close()
            elif progress_dialog:
                progress_dialog.update(100, "LibraryGenie", f"Scan failed: {e}")
            return {"success": False, "error": str(e)}

    def perform_delta_scan(self) -> Dict[str, Any]:
        """Perform a delta scan to detect changes using memory-efficient database snapshots"""
        self.logger.debug("Starting memory-efficient delta library scan")

        if not self.query_manager.initialize():
            self.logger.error("Failed to initialize database for delta scan")
            return {"success": False, "error": "Database initialization failed"}

        # Get current Kodi version
        try:
            current_version = get_kodi_major_version()
        except Exception as e:
            self.logger.warning("Failed to get Kodi version: %s", e)
            current_version = None

        # Check if Kodi version has changed since last scan
        if current_version and self._has_kodi_version_changed(current_version):
            self.logger.info("Kodi version changed to %s, forcing full scan", current_version)
            return self.perform_full_scan()

        scan_start = datetime.now().isoformat()

        try:
            # Use database-centric snapshot approach for memory efficiency
            from lib.library.sync_snapshot_manager import SyncSnapshotManager
            snapshot_manager = SyncSnapshotManager()
            
            # Create snapshot of current library state
            snapshot_result = snapshot_manager.create_snapshot('movie')
            if not snapshot_result.get("success"):
                self.logger.error("Failed to create snapshot: %s", snapshot_result.get("error"))
                return {"success": False, "error": "Snapshot creation failed"}
            
            self.logger.info("Created snapshot with %d movies using batch size %d", 
                            snapshot_result.get("total_items", 0), 
                            snapshot_result.get("batch_size", 0))
            
            # Detect changes using SQL operations (memory efficient - no Python sets)
            changes = snapshot_manager.detect_changes('movie')
            new_ids = changes['new']
            removed_ids = changes['removed']
            existing_count = changes['existing_count']

            items_added = 0
            items_updated = existing_count  # Already updated by SQL in detect_changes
            items_removed = 0

            # Process new movies
            if new_ids:
                self.logger.debug("Delta scan: %s new movies detected", len(new_ids))
                new_movies_data = self._fetch_movies_by_ids(new_ids)
                items_added = self._batch_insert_movies(new_movies_data)

            # Mark removed movies
            if removed_ids:
                self.logger.debug("Delta scan: %s removed movies detected", len(removed_ids))
                items_removed = self._mark_movies_removed(removed_ids)

            scan_end = datetime.now().isoformat()

            if items_added > 0 or items_removed > 0:
                self.logger.info("=== DELTA SCAN COMPLETE: +%s new, -%s removed movies ===", items_added, items_removed)
            else:
                self.logger.debug("Delta scan complete: no changes detected")
            
            # Cleanup snapshot to prevent table bloat
            snapshot_manager.cleanup_snapshot()

            return {
                "success": True,
                "items_found": snapshot_result.get("total_items", 0),
                "items_added": items_added,
                "items_updated": items_updated,
                "items_removed": items_removed,
                "scan_time": scan_end
            }

        except Exception as e:
            self.logger.error("Delta scan failed: %s", e)
            # Ensure cleanup on failure
            try:
                from lib.library.sync_snapshot_manager import SyncSnapshotManager
                snapshot_manager = SyncSnapshotManager()
                snapshot_manager.cleanup_snapshot()
            except Exception:
                pass  # Don't let cleanup errors mask the original error
            return {"success": False, "error": str(e)}

    def get_library_stats(self) -> Dict[str, Any]:
        """Get library indexing statistics"""
        try:
            stats = {}

            # Movie counts
            total_result = self.conn_manager.execute_single(
                "SELECT COUNT(*) as total FROM media_items WHERE media_type = 'movie'"
            )
            stats["total_movies"] = total_result["total"] if total_result else 0

            # Removed movies don't exist in new schema - set to 0
            stats["removed_movies"] = 0

            # Last scan info - removed scan logging
            stats["last_scan_type"] = None
            stats["last_scan_time"] = None
            stats["last_scan_found"] = None
            stats["last_scan_added"] = None
            stats["last_scan_removed"] = None

            return stats

        except Exception as e:
            self.logger.error("Failed to get library stats: %s", e)
            return {"total_movies": 0, "removed_movies": 0}

    def get_indexed_movies(self, include_removed: bool = False, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get indexed movies from the database"""
        try:
            where_clause = "" if include_removed else "WHERE is_removed = 0"

            movies = self.conn_manager.execute_query(f"""
                SELECT kodi_id, title, year, imdbnumber as imdb_id, tmdb_id, play as file_path,
                       created_at, updated_at, is_removed, created_at,
                       art, plot, plot as plotoutline, duration as runtime,
                       rating, genre, mpaa, director, country, studio,
                       0 as playcount, 0 as resume_time
                FROM media_items
                WHERE media_type = 'movie' {where_clause.replace('WHERE', 'AND') if where_clause else ''}
                ORDER BY title, year
                LIMIT ? OFFSET ?
            """, [limit, offset])

            # Convert sqlite3.Row objects to dictionaries for compatibility
            if movies:
                return [dict(movie) for movie in movies]
            return []

        except Exception as e:
            self.logger.error("Failed to get indexed movies: %s", e)
            return []

    def is_library_indexed(self) -> bool:
        """Check if the library has been indexed"""
        try:
            # Ensure database is initialized first
            if not self.query_manager.initialize():
                self.logger.warning("Database not initialized, library not indexed")
                return False

            result = self.conn_manager.execute_single(
                "SELECT COUNT(*) as count FROM media_items WHERE media_type = 'movie' AND is_removed = 0"
            )
            if result:
                # Handle both dict-like and sqlite3.Row objects
                count = result['count'] if hasattr(result, '__getitem__') else getattr(result, 'count', 0)
                return count > 0
            return False
        except Exception as e:
            self.logger.warning("Failed to check if library is indexed: %s", e)
            return False

    def _clear_library_index(self):
        """Clear the existing library index"""
        try:
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM media_items WHERE media_type = 'movie'")
                
                # Also clear TV episodes if sync is enabled - read directly from Kodi to bypass caching
                import xbmcaddon
                fresh_addon = xbmcaddon.Addon()
                try:
                    sync_tv_episodes = fresh_addon.getSettingBool('sync_tv_episodes')
                except Exception:
                    sync_tv_episodes = False
                    
                if sync_tv_episodes:
                    conn.execute("DELETE FROM media_items WHERE media_type = 'episode'")
                    self.logger.debug("Library index cleared for full scan (movies and episodes)")
                else:
                    self.logger.debug("Library index cleared for full scan (movies only)")
        except Exception as e:
            self.logger.error("Failed to clear library index: %s", e)
            raise

    def _batch_insert_movies(self, movies: List[Dict[str, Any]]) -> int:
        """Insert movies in batches with full metadata"""
        if not movies:
            return 0

        try:
            inserted_count = 0

            with self.conn_manager.transaction() as conn:
                for movie in movies:
                    try:
                        # Store comprehensive movie data from JSON-RPC
                        # Art data as JSON string for artwork URLs
                        art_json = json.dumps(movie.get("art", {})) if movie.get("art") else ""

                        # Extract unique IDs
                        uniqueid = movie.get("uniqueid", {})
                        tmdb_id = uniqueid.get("tmdb", "") if uniqueid else ""

                        # Handle resume data
                        resume_data = movie.get("resume", {})
                        resume_json = json.dumps(resume_data) if resume_data else ""

                        # Detect Kodi version once and store appropriate format
                        kodi_major = get_kodi_major_version()

                        # Pre-compute display fields for faster list building
                        display_title = f"{movie['title']} ({movie.get('year', '')})" if movie.get('year') else movie['title']

                        # Store genre in version-appropriate format
                        genre_list = movie.get('genre', '').split(',') if isinstance(movie.get('genre'), str) else movie.get('genre', [])
                        if kodi_major >= 20:
                            # v20+: Store as JSON array for InfoTagVideo.setGenres()
                            genre_data = json.dumps([g.strip() for g in genre_list if g.strip()]) if genre_list else "[]"
                        else:
                            # v19: Store as comma-separated string for setInfo()
                            genre_data = ', '.join([g.strip() for g in genre_list if g.strip()]) if genre_list else ''

                        # Store director in version-appropriate format
                        director_str = movie.get("director", "")
                        if isinstance(director_str, list):
                            director_str = ", ".join(director_str) if director_str else ""

                        if kodi_major >= 20:
                            # v20+: Store as JSON array for InfoTagVideo.setDirectors()
                            director_data = json.dumps([director_str]) if director_str else "[]"
                        else:
                            # v19: Store as string for setInfo()
                            director_data = director_str

                        # Duration: JSON-RPC returns runtime in seconds, store and convert properly
                        duration_seconds = movie.get("runtime", 0)  # JSON-RPC runtime is in seconds
                        duration_minutes = duration_seconds // 60 if duration_seconds else 0

                        # Studio handling
                        studio_str = movie.get("studio", "")
                        if isinstance(studio_str, list):
                            studio_str = studio_str[0] if studio_str else ""

                        conn.execute("""
                            INSERT OR REPLACE INTO media_items
                            (media_type, kodi_id, title, year, imdbnumber, tmdb_id, play, source, created_at, updated_at,
                             plot, rating, votes, duration, mpaa, genre, director, studio, country, 
                             writer, art, file_path, normalized_path, is_removed, display_title, duration_seconds)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'),
                                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """, [
                            'movie',
                            movie["kodi_id"],
                            movie["title"],
                            movie.get("year"),
                            movie.get("imdb_id"),
                            tmdb_id,
                            movie["file_path"],
                            'lib',  # Mark as Kodi library item
                            # Metadata
                            movie.get("plot", ""),
                            movie.get("rating", 0.0),
                            movie.get("votes", 0),
                            duration_minutes,  # Duration in minutes (converted from seconds)
                            movie.get("mpaa", ""),
                            genre_data,  # Version-appropriate genre format
                            director_data,  # Version-appropriate director format
                            studio_str,
                            movie.get("country", ""),
                            movie.get("writer", ""),
                            # JSON fields - store complete art data
                            art_json,
                            # File paths
                            movie["file_path"],
                            movie["file_path"].lower() if movie.get("file_path") else "",
                            # Pre-computed fields
                            display_title,
                            duration_seconds
                        ])
                        inserted_count += 1
                    except Exception as e:
                        self.logger.warning("Failed to insert movie '%s': %s", movie.get('title', 'Unknown'), e)

            # Silent batch insert - final count reported at process end
            return inserted_count

        except Exception as e:
            self.logger.error("Batch insert failed: %s", e)
            return 0

    def perform_movies_only_scan(self, progress_dialog=None, progress_callback=None) -> Dict[str, Any]:
        """Perform movies-only scan (no TV episodes)"""
        self.logger.info("Starting movies-only scan")

        # Initialize query manager
        if not self.query_manager.initialize():
            self.logger.error("Failed to initialize database for movies scan")
            return {"success": False, "error": "Database initialization failed"}

        try:
            # Reset abort flag
            self._abort_requested = False

            if progress_dialog:
                progress_dialog.update(0, "LibraryGenie", "Preparing movie scan...")

            # Clear existing movies only
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM media_items WHERE media_type = 'movie'")
                self.logger.debug("Cleared existing movies for resync")

            # Service already shows "Starting movie sync..." when creating dialog
            # Skip redundant startup message to avoid 0% flash

            # Get total count for progress tracking
            total_movies = self.kodi_client.get_movie_count()
            self.logger.info("Movies-only scan: %s movies to process", total_movies)

            if total_movies == 0:
                self.logger.info("No movies found in library")
                if progress_dialog:
                    progress_dialog.update(100, "LibraryGenie", "No movies found")
                return {"success": True, "items_added": 0, "episodes_added": 0}

            # Process movies in pages
            page_size = self.kodi_client.page_size
            total_pages = (total_movies + page_size - 1) // page_size
            self.logger.info("Processing %s pages of %s items each", total_pages, page_size)

            total_movies_added = 0
            for page in range(total_pages):
                if self._should_abort():
                    self.logger.info("Movies scan aborted by user")
                    break

                offset = page * page_size
                movies_response = self.kodi_client.get_movies(offset, page_size)
                movies = movies_response.get("movies", [])

                if not movies:
                    break

                # Insert this batch of movies
                movies_added = self._batch_insert_movies(movies)
                total_movies_added += movies_added

                # Update progress for movies: 0% to 100%
                progress_percentage = min(int(((page + 1) / total_pages) * 100), 99)  # 0% to 99%
                if progress_dialog:
                    progress_message = f"Processed {min(offset + len(movies), total_movies)}/{total_movies} movies"
                    progress_dialog.update(progress_percentage, "LibraryGenie", progress_message)

                # Silent page processing - final count reported at process end

            if progress_dialog:
                progress_dialog.update(100, "LibraryGenie", f"Movies scan complete: {total_movies_added} movies")

            self.logger.info("=== MOVIES-ONLY SYNC COMPLETE: %s movies successfully indexed ===", total_movies_added)
            
            return {
                "success": True,
                "items_added": total_movies_added,
                "episodes_added": 0  # No episodes in movies-only scan
            }
            
        except Exception as e:
            self.logger.error("Movies-only scan failed: %s", e)
            if progress_dialog:
                progress_dialog.update(100, "LibraryGenie", f"Movies scan failed: {e}")
            return {"success": False, "error": str(e)}

    def perform_tv_episodes_only_scan(self, progress_dialog=None, progress_callback=None) -> Dict[str, Any]:
        """Perform TV episodes-only scan (no movies)"""
        self.logger.info("Starting TV episodes-only scan")
        
        # Read directly from Kodi settings to bypass inter-process caching issues
        import xbmcaddon
        fresh_addon = xbmcaddon.Addon()
        try:
            sync_tv_episodes = fresh_addon.getSettingBool('sync_tv_episodes')
        except Exception:
            sync_tv_episodes = False
            
        if not sync_tv_episodes:
            self.logger.warning("TV episode sync is disabled - cannot perform episodes-only scan")
            return {"success": False, "error": "TV episode sync is disabled"}

        # Initialize query manager
        if not self.query_manager.initialize():
            self.logger.error("Failed to initialize database for TV episodes scan")
            return {"success": False, "error": "Database initialization failed"}

        try:
            # Reset abort flag
            self._abort_requested = False

            if progress_dialog:
                progress_dialog.update(0, "LibraryGenie", "Preparing TV episodes scan...")

            # Clear existing TV episodes only
            with self.conn_manager.transaction() as conn:
                conn.execute("DELETE FROM media_items WHERE media_type = 'episode'")
                self.logger.debug("Cleared existing TV episodes for resync")

            # Service already shows "Starting TV episodes sync..." when creating dialog  
            # Skip redundant startup message to avoid 0% flash

            # Sync TV episodes
            total_episodes_added = self._sync_tv_episodes(progress_dialog=progress_dialog, progress_callback=progress_callback)
            
            if progress_dialog:
                progress_dialog.update(100, "LibraryGenie", f"TV episodes scan complete: {total_episodes_added} episodes")
            
            self.logger.info("TV episodes-only scan complete: %s episodes indexed", total_episodes_added)
            
            return {
                "success": True,
                "episodes_added": total_episodes_added,
                "items_added": 0  # No movies in episodes-only scan
            }
            
        except Exception as e:
            self.logger.error("TV episodes-only scan failed: %s", e)
            if progress_dialog:
                progress_dialog.update(100, "LibraryGenie", f"TV episodes scan failed: {e}")
            return {"success": False, "error": str(e)}

    def _sync_tv_episodes(self, dialog_bg=None, progress_dialog=None, progress_callback=None) -> int:
        """Sync all TV episodes from Kodi library"""
        self.logger.info("Starting TV episode sync")
        
        try:
            # Get all TV shows first
            total_tvshows = self.kodi_client.get_tvshow_count()
            self.logger.info("Found %s TV shows to process for episodes", total_tvshows)
            
            if total_tvshows == 0:
                self.logger.info("No TV shows found, skipping episode sync")
                return 0
            
            total_episodes_added = 0
            show_offset = 0
            show_page_size = 50  # Process TV shows in smaller batches
            
            while show_offset < total_tvshows:
                if self._should_abort():
                    self.logger.info("TV episode sync aborted by user")
                    break
                
                # Get batch of TV shows
                tvshow_response = self.kodi_client.get_tvshows(show_offset, show_page_size)
                tvshows = tvshow_response.get("tvshows", [])
                
                if not tvshows:
                    break
                
                # Process episodes for each TV show
                for idx, tvshow in enumerate(tvshows):
                    if self._should_abort():
                        break
                    
                    tvshow_id = tvshow.get("kodi_id")
                    tvshow_title = tvshow.get("title", "Unknown Show")
                    
                    # Calculate cumulative progress across all TV series: 0% to 100%
                    shows_processed = show_offset + idx + 1  # Current show being processed (1-based)
                    overall_progress = shows_processed / total_tvshows
                    progress_percentage = min(int(overall_progress * 100), 99)  # Cap at 99% until completion
                    
                    progress_msg = f"Processing: {tvshow_title} ({shows_processed}/{total_tvshows} series)"
                    
                    if dialog_bg:
                        dialog_bg.update(progress_percentage, "LibraryGenie", progress_msg)
                    elif progress_dialog:
                        progress_dialog.update(progress_percentage, "LibraryGenie", progress_msg)
                    
                    # Get all episodes for this TV show
                    episodes = self.kodi_client.get_episodes_for_tvshow(tvshow_id)
                    
                    if episodes:
                        # Insert episodes for this show
                        episodes_added = self._batch_insert_episodes(episodes, tvshow)
                        total_episodes_added += episodes_added
                        # Silent episode insertion - final count reported at process end
                
                show_offset += len(tvshows)
                # Silent TV show processing - final count reported at process end
                
                # Brief pause to allow UI updates
                import time
                time.sleep(0.1)
            
            # Final progress update to 100%
            if dialog_bg:
                dialog_bg.update(100, "LibraryGenie", f"TV episodes sync complete: {total_episodes_added} episodes")
            elif progress_dialog:
                progress_dialog.update(100, "LibraryGenie", f"TV episodes sync complete: {total_episodes_added} episodes")
            
            self.logger.info("TV episode sync completed: %s episodes added", total_episodes_added)
            return total_episodes_added
            
        except Exception as e:
            self.logger.error("TV episode sync failed: %s", e)
            return 0

    def _batch_insert_episodes(self, episodes: List[Dict[str, Any]], tvshow_data: Dict[str, Any]) -> int:
        """Insert TV episodes in batches with full metadata"""
        if not episodes:
            return 0

        try:
            inserted_count = 0

            with self.conn_manager.transaction() as conn:
                for episode in episodes:
                    try:
                        # Store comprehensive episode data from JSON-RPC
                        art_json = json.dumps(episode.get("art", {})) if episode.get("art") else ""

                        # Extract unique IDs from episode and show
                        episode_uniqueid = episode.get("uniqueid", {})
                        episode_tmdb_id = episode_uniqueid.get("tmdb", "") if episode_uniqueid else ""
                        episode_imdb_id = episode_uniqueid.get("imdb", "") if episode_uniqueid else ""
                        
                        # Use show's IMDb ID if episode doesn't have one
                        show_imdb_id = tvshow_data.get("imdb_id", "")
                        final_imdb_id = episode_imdb_id or show_imdb_id

                        # Create normalized path for episode file
                        file_path = episode.get("file_path", "")
                        normalized_path = file_path.lower() if file_path else ""

                        # Create display title
                        season = episode.get("season", 0)
                        episode_num = episode.get("episode", 0)
                        episode_title = episode.get("title", f"Episode {episode_num}")
                        tvshowtitle = episode.get("tvshowtitle", tvshow_data.get("title", "Unknown Show"))
                        display_title = f"{tvshowtitle} - S{season:02d}E{episode_num:02d} - {episode_title}"

                        # Store genre from show data
                        show_genre = tvshow_data.get("genre", "")
                        show_studio = tvshow_data.get("studio", "")

                        # Duration handling
                        duration_seconds = episode.get("runtime", 0)
                        duration_minutes = duration_seconds // 60 if duration_seconds else 0

                        conn.execute("""
                            INSERT OR REPLACE INTO media_items
                            (media_type, kodi_id, title, year, imdbnumber, tmdb_id, play, source, created_at, updated_at,
                             plot, rating, votes, duration, mpaa, genre, director, studio, country, 
                             writer, art, file_path, normalized_path, is_removed, display_title, duration_seconds,
                             tvshowtitle, season, episode, aired, tvshow_kodi_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'),
                                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?,
                                    ?, ?, ?, ?, ?)
                        """, [
                            'episode',
                            episode["kodi_id"],
                            episode_title,
                            tvshow_data.get("year"),  # Use show's year
                            final_imdb_id,
                            episode_tmdb_id,
                            file_path,
                            'lib',  # Mark as Kodi library item
                            # Metadata
                            episode.get("plot", ""),
                            episode.get("rating", 0.0),
                            episode.get("votes", 0),
                            duration_minutes,
                            tvshow_data.get("mpaa", ""),  # Use show's rating
                            show_genre,  # Use show's genre
                            "",  # Episodes don't typically have directors
                            show_studio,  # Use show's studio
                            "",  # Country from show if needed
                            "",  # Writer from episode if available
                            # JSON fields
                            art_json,
                            # File paths
                            file_path,
                            normalized_path,
                            # Pre-computed fields
                            display_title,
                            duration_seconds,
                            # TV-specific fields
                            tvshowtitle,
                            season,
                            episode_num,
                            episode.get("firstaired", ""),
                            tvshow_data.get("kodi_id")  # Store show's Kodi ID for reliable lookup
                        ])
                        inserted_count += 1
                    except Exception as e:
                        self.logger.warning("Failed to insert episode '%s': %s", episode.get('title', 'Unknown'), e)

            # Silent batch insert - final count reported at process end
            return inserted_count

        except Exception as e:
            self.logger.error("Episode batch insert failed: %s", e)
            return 0

    def _get_indexed_movies(self) -> List[Dict[str, Any]]:
        """Get all indexed movies (internal use)"""
        try:
            movies = self.conn_manager.execute_query("""
                SELECT kodi_id, title, year, play as file_path
                FROM media_items
                WHERE media_type = 'movie'
            """)
            return movies or []
        except Exception as e:
            self.logger.error("Failed to get indexed movies: %s", e)
            return []

    def _fetch_movies_by_ids(self, kodi_ids: Set[int]) -> List[Dict[str, Any]]:
        """Fetch detailed movie data for specific Kodi IDs using precise individual requests"""
        movies = []
        
        for kodi_id in kodi_ids:
            movie_data = self.kodi_client.get_movie_details(kodi_id)
            if movie_data:
                movies.append(movie_data)
                self.logger.debug("Fetched details for new movie ID %s: %s", kodi_id, movie_data.get("title", "Unknown"))
            else:
                self.logger.debug("Could not fetch details for movie ID %s (may have been removed)", kodi_id)
        
        self.logger.info("Successfully fetched %d/%d movies by ID", len(movies), len(kodi_ids))
        return movies

    def _mark_movies_removed(self, kodi_ids: Set[int]) -> int:
        """Mark movies as removed (soft delete)"""
        if not kodi_ids:
            return 0

        try:
            removed_count = 0

            with self.conn_manager.transaction() as conn:
                for kodi_id in kodi_ids:
                    result = conn.execute("""
                        UPDATE media_items
                        SET is_removed = 1, updated_at = datetime('now')
                        WHERE kodi_id = ? AND is_removed = 0 AND media_type = 'movie'
                    """, [kodi_id])

                    if result.rowcount > 0:
                        removed_count += 1

            self.logger.debug("Marked %s movies as removed", removed_count)
            return removed_count

        except Exception as e:
            self.logger.error("Failed to mark movies as removed: %s", e)
            return 0

    def _update_last_seen(self, kodi_ids: Set[int]) -> int:
        """Update last_seen timestamp for existing movies"""
        if not kodi_ids:
            return 0

        try:
            updated_count = 0

            with self.conn_manager.transaction() as conn:
                for kodi_id in kodi_ids:
                    result = conn.execute("""
                        UPDATE media_items
                        SET updated_at = datetime('now')
                        WHERE kodi_id = ? AND is_removed = 0 AND media_type = 'movie'
                    """, [kodi_id])

                    if result.rowcount > 0:
                        updated_count += 1

            self.logger.debug("Updated last_seen for %s movies", updated_count)
            return updated_count

        except Exception as e:
            self.logger.error("Failed to update last_seen: %s", e)
            return 0


    def _has_kodi_version_changed(self, current_version: int) -> bool:
        """Check if Kodi version has changed since last scan"""
        # Without scan logging, assume version hasn't changed
        return False


# Global scanner instance
_scanner_instance = None


def get_library_scanner():
    """Get global library scanner instance"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = LibraryScanner()
    return _scanner_instance