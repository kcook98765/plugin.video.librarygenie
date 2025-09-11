#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Library Scanner
Handles full scans and delta detection of Kodi's video library
"""

import json
from datetime import datetime
from typing import List, Dict, Set, Any, Optional, Callable

from ..data import QueryManager
from ..data.connection_manager import get_connection_manager
from ..kodi.json_rpc_client import get_kodi_client
from ..utils.logger import get_logger
from ..utils.kodi_version import get_kodi_major_version
from ..config.settings import SettingsManager

from ..ui.localization import L

class LibraryScanner:
    """Scans and indexes Kodi's video library"""

    def __init__(self):
        self.logger = get_logger(__name__)
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
        scan_id = self._log_scan_start("full", scan_start, current_version)

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
                self._log_scan_complete(scan_id, scan_start, 0, 0, 0, 0)
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
                    self._log_scan_complete(scan_id, scan_start, offset, total_added, 0, 0, error="Aborted by user")
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

                self.logger.debug("Full scan progress: %s/%s movies processed (%s%%)", items_processed, total_movies, progress_percentage)

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

            self.logger.info("Movie scan complete: %s movies indexed", total_added)

            # TV Episode sync (if enabled)
            total_episodes_added = 0
            if self.settings.get_sync_tv_episodes():
                self.logger.info("TV episode sync enabled - starting episode scan")
                try:
                    total_episodes_added = self._sync_tv_episodes(dialog_bg, progress_dialog, progress_callback)
                    self.logger.info("TV episode sync complete: %s episodes indexed", total_episodes_added)
                except Exception as e:
                    self.logger.error("TV episode sync failed: %s", e)
                    # Continue with scan completion even if TV sync fails
            else:
                self.logger.debug("TV episode sync disabled - skipping")

            scan_end = datetime.now().isoformat()
            self._log_scan_complete(scan_id, scan_start, total_movies, total_added, 0, total_episodes_added, scan_end)

            self.logger.info("Full scan complete: %s movies, %s episodes indexed", total_added, total_episodes_added)

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
            self._log_scan_complete(scan_id, scan_start, 0, 0, 0, 0, error=str(e))
            return {"success": False, "error": str(e)}

    def perform_delta_scan(self) -> Dict[str, Any]:
        """Perform a delta scan to detect changes"""
        self.logger.debug("Starting delta library scan")

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
        scan_id = self._log_scan_start("delta", scan_start, current_version)

        try:
            # Get current Kodi library state (quick check)
            current_movies = self.kodi_client.get_movies_quick_check()
            current_ids = {movie["movieid"] for movie in current_movies}

            # Get our indexed movies
            indexed_movies = self._get_indexed_movies()
            indexed_ids = {movie["kodi_id"] for movie in indexed_movies}

            # Detect changes
            new_ids = current_ids - indexed_ids
            removed_ids = indexed_ids - current_ids

            items_added = 0
            items_updated = 0
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

            # Update last_seen for existing movies
            existing_ids = current_ids & indexed_ids
            if existing_ids:
                items_updated = self._update_last_seen(existing_ids)

            scan_end = datetime.now().isoformat()
            self._log_scan_complete(
                scan_id, scan_start, len(current_movies),
                items_added, items_updated, items_removed, scan_end
            )

            if items_added > 0 or items_removed > 0:
                self.logger.info("Delta scan complete: +%s -%s movies", items_added, items_removed)
            else:
                self.logger.debug("Delta scan complete: no changes detected")

            return {
                "success": True,
                "items_found": len(current_movies),
                "items_added": items_added,
                "items_updated": items_updated,
                "items_removed": items_removed,
                "scan_time": scan_end
            }

        except Exception as e:
            self.logger.error("Delta scan failed: %s", e)
            self._log_scan_complete(scan_id, scan_start, 0, 0, 0, 0, error=str(e))
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

            # Last scan info
            last_scan = self.conn_manager.execute_single("""
                SELECT scan_type, end_time, total_items, items_added, items_removed
                FROM library_scan_log
                WHERE end_time IS NOT NULL
                ORDER BY id DESC LIMIT 1
            """)

            if last_scan:
                stats["last_scan_type"] = last_scan["scan_type"]
                stats["last_scan_time"] = last_scan["end_time"]
                stats["last_scan_found"] = last_scan["total_items"]
                stats["last_scan_added"] = last_scan["items_added"]
                stats["last_scan_removed"] = last_scan["items_removed"]
            else:
                stats["last_scan_type"] = None
                stats["last_scan_time"] = None

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
                
                # Also clear TV episodes if sync is enabled
                if self.settings.get_sync_tv_episodes():
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

                        # Duration: always store in seconds (can convert to minutes for v19 if needed)
                        duration_minutes = movie.get("runtime", 0)
                        duration_seconds = duration_minutes * 60 if duration_minutes else 0

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
                            movie.get("runtime", 0),  # Duration in minutes
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

            self.logger.debug("Batch inserted %s/%s movies", inserted_count, len(movies))
            return inserted_count

        except Exception as e:
            self.logger.error("Batch insert failed: %s", e)
            return 0

    def perform_tv_episodes_only_scan(self, progress_dialog=None, progress_callback=None) -> Dict[str, Any]:
        """Perform TV episodes-only scan (no movies)"""
        self.logger.info("Starting TV episodes-only scan")
        
        if not self.settings.get_sync_tv_episodes():
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

            if progress_dialog:
                progress_dialog.update(10, "LibraryGenie", "Starting TV episodes sync...")

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
                    
                    # Calculate progress based on TV series processed: 20% to 90%
                    if dialog_bg:
                        overall_show_progress = (show_offset + idx) / total_tvshows
                        progress_percentage = int(20 + (overall_show_progress * 70))  # 20% to 90%
                        progress_msg = f"Processing: {tvshow_title} ({show_offset + idx + 1}/{total_tvshows} series)"
                        dialog_bg.update(progress_percentage, "LibraryGenie", progress_msg)
                    elif progress_dialog:
                        overall_show_progress = (show_offset + idx) / total_tvshows
                        progress_percentage = int(20 + (overall_show_progress * 70))  # 20% to 90%
                        progress_msg = f"Processing: {tvshow_title} ({show_offset + idx + 1}/{total_tvshows} series)"
                        progress_dialog.update(progress_percentage, "LibraryGenie", progress_msg)
                    
                    # Get all episodes for this TV show
                    episodes = self.kodi_client.get_episodes_for_tvshow(tvshow_id)
                    
                    if episodes:
                        # Insert episodes for this show
                        episodes_added = self._batch_insert_episodes(episodes, tvshow)
                        total_episodes_added += episodes_added
                        self.logger.debug("Added %s episodes for show '%s'", episodes_added, tvshow_title)
                
                show_offset += len(tvshows)
                self.logger.debug("Processed %s/%s TV shows", min(show_offset, total_tvshows), total_tvshows)
                
                # Brief pause to allow UI updates
                import time
                time.sleep(0.1)
            
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

            self.logger.debug("Batch inserted %s/%s episodes", inserted_count, len(episodes))
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
        """Fetch detailed movie data for specific Kodi IDs"""
        # This is a simplified implementation - in practice we'd need to make
        # individual requests or batch requests for specific IDs
        # For now, do a small scan to catch new movies
        response = self.kodi_client.get_movies(0, 50)  # Small batch to find new ones
        movies = response.get("movies", [])

        # Filter to just the IDs we want
        filtered_movies = [m for m in movies if m["kodi_id"] in kodi_ids]
        return filtered_movies

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

    def _log_scan_start(self, scan_type: str, started_at: str, kodi_version: int = None) -> Optional[int]:
        """Log the start of a scan"""
        try:
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO library_scan_log (scan_type, kodi_version, start_time)
                    VALUES (?, ?, ?)
                """, [scan_type, kodi_version, started_at])
                return cursor.lastrowid
        except Exception as e:
            self.logger.error("Failed to log scan start: %s", e)
            return None

    def _log_scan_complete(self, scan_id: Optional[int], started_at: str,
                          items_found: int, items_added: int, items_updated: int, items_removed: int,
                          completed_at: Optional[str] = None, error: Optional[str] = None):
        """Log the completion of a scan"""
        if not scan_id:
            return

        try:
            completed_at = completed_at or datetime.now().isoformat()

            with self.conn_manager.transaction() as conn:
                conn.execute("""
                    UPDATE library_scan_log
                    SET end_time = ?, total_items = ?, items_added = ?,
                        items_updated = ?, items_removed = ?, error = ?
                    WHERE id = ?
                """, [completed_at, items_found, items_added, items_updated, items_removed, error, scan_id])
        except Exception as e:
            self.logger.error("Failed to log scan completion: %s", e)

    def _has_kodi_version_changed(self, current_version: int) -> bool:
        """Check if Kodi version has changed since last scan"""
        try:
            last_scan = self.conn_manager.execute_single("""
                SELECT kodi_version
                FROM library_scan_log
                WHERE end_time IS NOT NULL AND kodi_version IS NOT NULL
                ORDER BY id DESC LIMIT 1
            """)

            if not last_scan:
                # No previous successful scan with version info
                return False

            last_version = last_scan['kodi_version']
            if last_version != current_version:
                self.logger.info("Kodi version changed from %s to %s", last_version, current_version)
                return True

            return False

        except Exception as e:
            self.logger.warning("Failed to check Kodi version change: %s", e)
            # Assume no change on error to avoid unnecessary full scans
            return False


# Global scanner instance
_scanner_instance = None


def get_library_scanner():
    """Get global library scanner instance"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = LibraryScanner()
    return _scanner_instance