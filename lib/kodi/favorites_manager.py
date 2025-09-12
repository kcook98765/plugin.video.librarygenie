#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 4 Enhanced Favorites Manager
Robust favorites integration with reliable mapping, idempotent updates, and batch processing
"""

import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import xbmcvfs

from ..data import get_query_manager
from ..data.connection_manager import get_connection_manager
from ..utils.kodi_log import get_kodi_logger
from ..config import get_config
from .favorites_parser import Phase4FavoritesParser
from ..data.list_library_manager import get_list_library_manager


class Phase4FavoritesManager:
    """Phase 4: Enhanced favorites manager with reliable mapping and batch processing"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.kodi.favorites_manager')
        self.query_manager = get_query_manager()
        self.conn_manager = get_connection_manager()
        self.config = get_config()
        self.parser = Phase4FavoritesParser()
        self.library_manager = get_list_library_manager()

    def scan_favorites(self, file_path: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Scan and import favorites with file-based optimization"""
        start_time = datetime.now()

        try:
            # Find favorites file if not provided
            if not file_path:
                file_path = self.parser.find_favorites_file()
                if not file_path:
                    self.logger.info("Favorites file not found - showing empty state")
                    return {
                        "success": True,
                        "scan_type": "empty_state",
                        "items_found": 0,
                        "items_mapped": 0,
                        "message": "No favorites file found"
                    }

            # Check if scan is needed (unless forced)
            if not force_refresh and not self._should_scan_favorites(file_path):
                self.logger.debug("Favorites file unchanged since last scan - skipping")
                return {
                    "success": True,
                    "scan_type": "skipped",
                    "items_found": 0,
                    "items_mapped": 0,
                    "message": "No changes detected, scan skipped"
                }

            # Parse favorites file with enhanced parser
            favorites = self.parser.parse_favorites_file(file_path)

            # Phase 4: Process in batches with reliable mapping
            result = self._import_favorites_batch(favorites)

            # Calculate duration
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)


            # Update scan marker file after successful scan
            self._update_scan_marker()
            
            self.logger.info("Favorites scan complete: %s/%s mapped, %s added, %s updated", result['items_mapped'], len(favorites), result['items_added'], result['items_updated'])

            return {
                "success": True,
                "scan_type": "full",
                "items_found": len(favorites),
                "items_mapped": result["items_mapped"],
                "items_added": result["items_added"],
                "items_updated": result["items_updated"],
                "duration_ms": duration_ms,
                "message": f"Processed {len(favorites)} favorites"
            }

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)


            self.logger.error("Favorites scan failed: %s", e)
            return {
                "success": False,
                "error": "scan_error",
                "message": str(e),
                "duration_ms": duration_ms
            }

    def _import_favorites_batch(self, favorites: List[Dict]) -> Dict[str, int]:
        """Import favorites into unified lists table as 'Kodi Favorites' list"""
        items_added = 0
        items_updated = 0
        items_mapped = 0

        self.logger.info("Starting batch import of %s favorites", len(favorites))

        try:
            with self.conn_manager.transaction() as conn:
                # Ensure 'Kodi Favorites' list exists in the unified lists table
                kodi_list = conn.execute("""
                    SELECT id FROM lists WHERE name = 'Kodi Favorites'
                """).fetchone()

                if not kodi_list:
                    # Create the Kodi Favorites list
                    cursor = conn.execute("""
                        INSERT INTO lists (name, created_at)
                        VALUES ('Kodi Favorites', datetime('now'))
                    """)
                    kodi_list_id = cursor.lastrowid
                    self.logger.info("Created 'Kodi Favorites' list in unified lists table")
                else:
                    kodi_list_id = kodi_list["id"]
                    self.logger.info("Using existing 'Kodi Favorites' list with ID %s", kodi_list_id)

                # Clear existing items from the Kodi Favorites list
                deleted_count = conn.execute("DELETE FROM list_items WHERE list_id = ?", [kodi_list_id]).rowcount
                self.logger.info("Cleared %s existing items from Kodi Favorites list", deleted_count)

                # Log database stats before processing
                media_count = conn.execute("SELECT COUNT(*) as count FROM media_items WHERE is_removed = 0").fetchone()["count"]
                self.logger.info("Database contains %s active media items for matching", media_count)

                # Process favorites and add mapped ones to the list
                for i, favorite in enumerate(favorites):
                    favorite_name = favorite.get('name', 'unknown')
                    self.logger.info("Processing favorite %s/%s: '%s'", i+1, len(favorites), favorite_name)
                    self.logger.info("  Raw target: %s", favorite['target_raw'])
                    self.logger.info("  Classification: %s", favorite['target_classification'])
                    self.logger.info("  Normalized key: %s", favorite['normalized_key'])

                    try:
                        # Try to find library match
                        library_movie_id = self._find_library_match_enhanced(
                            favorite["target_raw"],
                            favorite["target_classification"],
                            favorite["normalized_key"]
                        )

                        if library_movie_id:
                            self.logger.info("  ✓ MATCHED to library item ID %s", library_movie_id)

                            # Add to the unified list_items table
                            conn.execute("""
                                INSERT INTO list_items (list_id, media_item_id, position, created_at)
                                VALUES (?, ?, ?, datetime('now'))
                            """, [kodi_list_id, library_movie_id, items_mapped])

                            items_mapped += 1
                            items_added += 1
                        else:
                            self.logger.info("  ✗ NO MATCH found for '%s'", favorite_name)

                    except Exception as e:
                        self.logger.warning("Error processing favorite '%s': %s", favorite_name, e)
                        continue

                # Note: lists table doesn't have updated_at column in current schema

            self.logger.info("Batch import complete: %s/%s mapped, %s added", items_mapped, len(favorites), items_added)

            return {
                "items_added": items_added,
                "items_updated": items_updated,
                "items_mapped": items_mapped
            }

        except Exception as e:
            self.logger.error("Error in batch import: %s", e)
            return {
                "items_added": 0,
                "items_updated": 0,
                "items_mapped": 0
            }

    def _find_library_match_enhanced(self, target_raw: str, classification: str, normalized_key: str) -> Optional[int]:
        """Phase 4: Enhanced library matching with multiple strategies"""
        self.logger.info("    Starting library match for classification '%s'", classification)

        try:
            # Strategy 1: videodb dbid matching
            if classification == 'videodb':
                self.logger.info("    Using videodb matching strategy")
                
                # Check for movie videodb URLs: videodb://movies/titles/123
                movie_match = re.search(r'videodb://movies/titles/(\d+)', target_raw.lower())
                if movie_match:
                    kodi_dbid = int(movie_match.group(1))
                    self.logger.info("    Extracted movie Kodi dbid: %s", kodi_dbid)
                    return self._find_or_create_movie_by_kodi_id(kodi_dbid)
                
                # Check for TV show/episode videodb URLs: videodb://tvshows/titles/123/ or videodb://tvshows/titles/123/1/5/
                tvshow_match = re.search(r'videodb://tvshows/titles/(\d+)(?:/(\d+)/(\d+))?', target_raw.lower())
                if tvshow_match:
                    show_kodi_id = int(tvshow_match.group(1))
                    season = int(tvshow_match.group(2)) if tvshow_match.group(2) else None
                    episode = int(tvshow_match.group(3)) if tvshow_match.group(3) else None
                    
                    if season is not None and episode is not None:
                        self.logger.info("    Extracted episode: show_id=%s, season=%s, episode=%s", show_kodi_id, season, episode)
                        return self._find_or_create_episode_by_show_season_episode(show_kodi_id, season, episode)
                    else:
                        self.logger.info("    TV show favorite detected but no specific episode: show_id=%s", show_kodi_id)
                        # TV show favorites (not specific episodes) are not supported for now
                        return None
                
                self.logger.info("    Could not extract dbid from videodb URL: %s", target_raw)

            # Strategy 2: Normalized path matching
            elif classification == 'mappable_file':
                self.logger.info("    Using file path matching strategy")
                self.logger.info("    Looking for normalized_path: '%s'", normalized_key)

                # Try exact normalized path match
                result = self.conn_manager.execute_single("""
                    SELECT id, title, file_path, normalized_path, media_type FROM media_items
                    WHERE normalized_path = ? AND is_removed = 0
                """, [normalized_key])

                if result:
                    media_type = result['media_type'] or 'unknown'
                    self.logger.info("    Found exact normalized path match: ID %s - '%s' (type: %s)", result['id'], result['title'], media_type)
                    self.logger.info("    Matched file_path: %s", result['file_path'])
                    return result["id"]
                else:
                    self.logger.info("    No exact normalized path match found")

                    # Show some sample normalized paths for debugging
                    sample_paths = self.conn_manager.execute_query("""
                        SELECT normalized_path, file_path FROM media_items 
                        WHERE is_removed = 0 AND normalized_path IS NOT NULL AND normalized_path != ''
                        LIMIT 5
                    """)

                    if sample_paths:
                        self.logger.info("    Sample normalized paths in database:")
                        for sample in sample_paths:
                            self.logger.info("      normalized: '%s'", sample['normalized_path'])
                            self.logger.info("      file_path:  '%s'", sample['file_path'])
                    else:
                        self.logger.info("    No normalized paths found in database")

                    # Always try file_path matching as backup
                    self.logger.info("    Trying file_path matching")
                    result = self._try_file_path_matching(normalized_key)
                    if result:
                        self.logger.info("    Found file_path match: ID %s", result)
                        return result

                # Try fuzzy path matching for variations
                self.logger.info("    Attempting fuzzy path matching")
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    self.logger.info("    Fuzzy match found: ID %s", result)
                    return result
                else:
                    self.logger.info("    No fuzzy match found")
            else:
                self.logger.info("    Classification '%s' not supported for matching", classification)

            self.logger.info("    No library match found")
            return None

        except Exception as e:
            self.logger.error("Error finding library match for '%s': %s", target_raw, e)
            import traceback
            self.logger.error("Traceback: %s", traceback.format_exc())
            return None

    def _try_file_path_matching(self, normalized_key: str) -> Optional[int]:
        """Attempt to match using the raw file_path with multiple strategies"""
        self.logger.info("    Attempting file path matching for key: '%s'", normalized_key)
        try:
            with self.conn_manager.transaction() as conn:
                # Strategy 1: Try exact file path match
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE file_path = ? AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info("    Found exact file_path match: ID %s - '%s'", result['id'], result['title'])
                    return result["id"]

                # Strategy 2: Try case-insensitive file_path match
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE LOWER(file_path) = LOWER(?) AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info("    Found case-insensitive file_path match: ID %s - '%s'", result['id'], result['title'])
                    return result["id"]

                # Strategy 3: Try normalized_path match (in case it exists but wasn't found earlier)
                result = conn.execute("""
                    SELECT id, title, file_path, normalized_path FROM media_items
                    WHERE LOWER(normalized_path) = LOWER(?) AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info("    Found case-insensitive normalized_path match: ID %s - '%s'", result['id'], result['title'])
                    return result["id"]

                # Strategy 4: Try to match by converting backslashes to forward slashes in file_path
                backslash_version = normalized_key.replace('/', '\\')
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE file_path = ? AND is_removed = 0
                """, [backslash_version]).fetchone()

                if result:
                    self.logger.info("    Found backslash file_path match: ID %s - '%s'", result['id'], result['title'])
                    return result["id"]

                # Strategy 5: Try fuzzy path matching for variations
                self.logger.info("    Attempting fuzzy file_path matching")
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    self.logger.info("    Fuzzy file_path match found: ID %s", result)
                    return result

                self.logger.info("    No file_path matches found")
                return None

        except Exception as e:
            self.logger.error("Error in file path matching: %s", e)
            return None

    def _fuzzy_path_match(self, normalized_key: str) -> Optional[int]:
        """Fuzzy path matching for path variations"""
        try:
            # Extract just the filename for fuzzy matching
            filename = normalized_key.split('/')[-1] if '/' in normalized_key else normalized_key
            filename = filename.split('\\')[-1] if '\\' in filename else filename  # Handle backslashes too
            self.logger.info("      Fuzzy matching with filename: '%s'", filename)

            if not filename or len(filename) < 3:
                self.logger.info("      Filename too short for fuzzy matching: '%s'", filename)
                return None

            # Look for files with same filename but different paths
            with self.conn_manager.transaction() as conn:
                backslash_filename = filename.replace('/', '\\')
                results = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE is_removed = 0
                    AND (file_path LIKE ? OR file_path LIKE ?)
                    LIMIT 10
                """, [f"%{filename}%", f"%{backslash_filename}%"]).fetchall()

                self.logger.info("      Found %s potential fuzzy matches", len(results))

                for i, result in enumerate(results):
                    self.logger.info("        Match %s: ID %s - '%s' - %s", i+1, result['id'], result['title'], result['file_path'])

                if results and len(results) == 1:
                    # Exactly one match - probably correct
                    result = results[0]
                    self.logger.info("      Single fuzzy match selected: ID %s", result['id'])
                    return result["id"]
                elif len(results) > 1:
                    # Try to find exact filename match (case insensitive)
                    for result in results:
                        result_filename = result['file_path'].split('/')[-1].split('\\')[-1].lower()
                        if result_filename == filename.lower():
                            self.logger.info("      Exact filename match found: ID %s - '%s'", result['id'], result['title'])
                            return result["id"]

                    self.logger.info("      Multiple fuzzy matches found but no exact filename match - skipping for reliability")
                else:
                    self.logger.info("      No fuzzy matches found")

                return None

        except Exception as e:
            self.logger.error("Error in fuzzy path matching: %s", e)
            return None

    def _find_or_create_movie_by_kodi_id(self, kodi_dbid: int) -> Optional[int]:
        """Find movie by Kodi dbid with media_type constraint, create if missing"""
        try:
            # Find existing movie by Kodi dbid with media_type constraint
            with self.conn_manager.transaction() as conn:
                result = conn.execute("""
                    SELECT id, title FROM media_items
                    WHERE kodi_id = ? AND media_type = 'movie' AND is_removed = 0
                """, [kodi_dbid]).fetchone()

                if result:
                    self.logger.info("    Found existing movie: ID %s - '%s'", result['id'], result['title'])
                    return result["id"]
                else:
                    self.logger.info("    No existing movie found for Kodi dbid %s", kodi_dbid)
                    
                    # TODO: Implement on-demand movie creation from Kodi JSON-RPC
                    # For now, return None - movies should exist from library scan
                    self.logger.info("    Movie creation not implemented - skipping")
                    return None

        except Exception as e:
            self.logger.error("Error finding/creating movie by Kodi ID %s: %s", kodi_dbid, e)
            return None

    def _find_or_create_episode_by_show_season_episode(self, show_kodi_id: int, season: int, episode: int) -> Optional[int]:
        """Find episode by show/season/episode - episodes should exist from proactive sync"""
        try:
            self.logger.info("    Looking for episode: show_id=%s S%02dE%02d", show_kodi_id, season, episode)
            
            with self.conn_manager.transaction() as conn:
                # Strategy 1: Try to find by tvshow_kodi_id + season + episode (most reliable)
                # Use safe column check to handle missing tvshow_kodi_id in older database schemas
                try:
                    result = conn.execute("""
                        SELECT id, title, tvshowtitle FROM media_items
                        WHERE tvshow_kodi_id = ? 
                        AND season = ? 
                        AND episode = ? 
                        AND media_type = 'episode'
                        AND is_removed = 0
                    """, [show_kodi_id, season, episode]).fetchone()
                    
                    if result:
                        self.logger.info("    Found episode by tvshow_kodi_id match: ID %s - '%s' from show '%s'", result['id'], result['title'], result.get('tvshowtitle', 'Unknown'))
                        return result["id"]
                        
                except Exception as db_error:
                    # Column likely doesn't exist in older database schema - fall back to legacy approach
                    if "no such column: tvshow_kodi_id" in str(db_error).lower():
                        self.logger.debug("    tvshow_kodi_id column not found - using legacy episode lookup")
                    else:
                        self.logger.warning("    Database error in tvshow_kodi_id lookup: %s", db_error)
                
                # Strategy 2: Fallback to episode kodi_id lookup (if available from videodb URL parsing)
                # Note: This would require extracting episode kodi_id from more complex videodb URLs
                # For now, this strategy is not implemented as it requires URL parsing changes
                
                # Strategy 3: Try finding by season + episode with show title matching
                # This is the legacy approach that works with older schemas
                result = conn.execute("""
                    SELECT id, title, tvshowtitle FROM media_items
                    WHERE season = ? 
                    AND episode = ? 
                    AND media_type = 'episode'
                    AND is_removed = 0
                """, [season, episode]).fetchall()
                
                if result:
                    self.logger.info("    Found %s episodes with S%02dE%02d", len(result), season, episode)
                    if len(result) == 1:
                        ep = result[0]
                        self.logger.info("    Using unique episode: ID %s - '%s' from show '%s'", ep['id'], ep['title'], ep.get('tvshowtitle', 'Unknown'))
                        return ep["id"]
                    else:
                        # Multiple episodes - log the ambiguity but still return first match
                        # This maintains existing behavior while we improve the sync to store tvshow_kodi_id
                        ep = result[0]
                        self.logger.warning("    Multiple S%02dE%02d episodes found - using first: ID %s from '%s'", ep['id'], ep.get('tvshowtitle', 'Unknown'))
                        return ep["id"]
                
                # No existing episode found - try minimal on-demand creation for favorites compatibility
                self.logger.info("    No existing episode found for show_id=%s S%02dE%02d", show_kodi_id, season, episode)
                
                # Check if TV sync is enabled - if so, episode should exist from sync
                from ..config.settings import SettingsManager
                settings = SettingsManager()
                if settings.get_sync_tv_episodes():
                    self.logger.info("    TV episode sync is enabled but episode not found - may need full library scan")
                    return None
                else:
                    # TV sync disabled - try minimal on-demand creation for favorites compatibility
                    self.logger.info("    TV episode sync disabled - attempting minimal on-demand episode creation for favorites")
                    episode_id = self._create_single_episode_on_demand(show_kodi_id, season, episode)
                    if episode_id:
                        self.logger.info("    Created episode on-demand: ID %s", episode_id)
                        return episode_id
                    else:
                        self.logger.info("    Failed to create episode on-demand")
                        return None

        except Exception as e:
            self.logger.error("Error finding episode for show %s S%sE%s: %s", show_kodi_id, season, episode, e)
            return None


    def _create_single_episode_on_demand(self, show_kodi_id: int, season: int, episode: int) -> Optional[int]:
        """Create a single episode on-demand for favorites compatibility when sync is disabled"""
        try:
            # Import here to avoid circular imports
            from ..kodi.json_rpc_client import get_kodi_client
            
            kodi_client = get_kodi_client()
            
            # Get show information first
            show_response = kodi_client.get_tvshows(0, 1000)  # Get all shows to find the right one
            target_show = None
            
            for show in show_response.get("tvshows", []):
                if show.get("kodi_id") == show_kodi_id:
                    target_show = show
                    break
            
            if not target_show:
                self.logger.warning("    Could not find show with kodi_id %s for on-demand episode creation", show_kodi_id)
                return None
            
            # Get episodes for this show
            episodes = kodi_client.get_episodes_for_tvshow(show_kodi_id)
            
            # Find the specific episode
            target_episode = None
            for ep in episodes:
                if ep.get("season") == season and ep.get("episode") == episode:
                    target_episode = ep
                    break
            
            if not target_episode:
                self.logger.warning("    Could not find S%02dE%02d in show %s for on-demand creation", season, episode, target_show.get("title", "Unknown"))
                return None
            
            # Create episode record using the same logic as the scanner but for a single episode
            from datetime import datetime
            import json
            
            with self.conn_manager.transaction() as conn:
                # Prepare episode data
                episode_title = target_episode.get("title", f"Episode {episode}")
                tvshowtitle = target_show.get("title", "Unknown Show")
                display_title = f"{tvshowtitle} - S{season:02d}E{episode:02d} - {episode_title}"
                
                # Extract metadata
                art_json = json.dumps(target_episode.get("art", {})) if target_episode.get("art") else ""
                file_path = target_episode.get("file_path", "")
                normalized_path = file_path.lower() if file_path else ""
                
                # Duration handling
                duration_seconds = target_episode.get("runtime", 0)
                duration_minutes = duration_seconds // 60 if duration_seconds else 0
                
                # Store episode with tvshow_kodi_id for reliable lookup (if column exists)
                try:
                    # Try new schema with tvshow_kodi_id
                    cursor = conn.execute("""
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
                        target_episode.get("kodi_id"),
                        episode_title,
                        target_show.get("year"),
                        target_show.get("imdb_id", ""),
                        target_episode.get("tmdb_id", ""),
                        file_path,
                        'lib',  # Mark as Kodi library item
                        # Metadata
                        target_episode.get("plot", ""),
                        target_episode.get("rating", 0.0),
                        target_episode.get("votes", 0),
                        duration_minutes,
                        target_show.get("mpaa", ""),
                        target_show.get("genre", ""),
                        "",  # Episodes don't typically have directors
                        target_show.get("studio", ""),
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
                        episode,
                        target_episode.get("firstaired", ""),
                        show_kodi_id  # Store show's Kodi ID for reliable lookup
                    ])
                    
                except Exception as new_schema_error:
                    if "no such column: tvshow_kodi_id" in str(new_schema_error).lower():
                        # Fall back to legacy schema without tvshow_kodi_id
                        self.logger.debug("    Using legacy schema for on-demand episode creation")
                        cursor = conn.execute("""
                            INSERT OR REPLACE INTO media_items
                            (media_type, kodi_id, title, year, imdbnumber, tmdb_id, play, source, created_at, updated_at,
                             plot, rating, votes, duration, mpaa, genre, director, studio, country, 
                             writer, art, file_path, normalized_path, is_removed, display_title, duration_seconds,
                             tvshowtitle, season, episode, aired)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'),
                                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?,
                                    ?, ?, ?, ?)
                        """, [
                            'episode',
                            target_episode.get("kodi_id"),
                            episode_title,
                            target_show.get("year"),
                            target_show.get("imdb_id", ""),
                            target_episode.get("tmdb_id", ""),
                            file_path,
                            'lib',  # Mark as Kodi library item
                            # Metadata
                            target_episode.get("plot", ""),
                            target_episode.get("rating", 0.0),
                            target_episode.get("votes", 0),
                            duration_minutes,
                            target_show.get("mpaa", ""),
                            target_show.get("genre", ""),
                            "",  # Episodes don't typically have directors
                            target_show.get("studio", ""),
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
                            episode,
                            target_episode.get("firstaired", "")
                        ])
                    else:
                        raise new_schema_error
                
                episode_media_id = cursor.lastrowid
                self.logger.info("    Created episode on-demand: ID %s - '%s'", episode_media_id, display_title)
                return episode_media_id
                
        except Exception as e:
            self.logger.error("Error creating episode on-demand for show %s S%sE%s: %s", show_kodi_id, season, episode, e)
            return None

    def _normalize_episode_path(self, file_path: str) -> str:
        """Normalize episode file path for matching"""
        try:
            if not file_path:
                return ""
            
            # Use the same normalization logic as the favorites parser
            from .favorites_parser import get_phase4_favorites_parser
            parser = get_phase4_favorites_parser()
            return parser._normalize_file_path_key(file_path)
            
        except Exception as e:
            self.logger.debug("Error normalizing episode path '%s': %s", file_path, e)
            return file_path.lower()

    def get_mapped_favorites(self, show_unmapped: bool = False) -> List[Dict]:
        """Get favorites from unified lists table using standard list query approach"""
        try:
            # Use the standard query manager to get list items - same as any other list
            from ..data.query_manager import get_query_manager
            query_manager = get_query_manager()

            # Get the Kodi Favorites list ID
            with self.conn_manager.transaction() as conn:
                kodi_list = conn.execute("""
                    SELECT id FROM lists WHERE name = 'Kodi Favorites'
                """).fetchone()

                if not kodi_list:
                    self.logger.info("No 'Kodi Favorites' list found")
                    return []

                kodi_list_id = kodi_list["id"]

            # Use the standard list items query - same as other lists use
            favorites = query_manager.get_list_items(kodi_list_id)

            self.logger.info("Retrieved %s favorites using standard list query approach", len(favorites))
            return favorites

        except Exception as e:
            self.logger.error("Error getting mapped favorites: %s", e)
            return []

    def get_favorites_stats(self) -> Dict[str, int]:
        """Get statistics about favorites from unified lists table"""
        try:
            with self.conn_manager.transaction() as conn:
                stats = conn.execute("""
                    SELECT COUNT(*) as total
                    FROM lists l
                    JOIN list_items li ON l.id = li.list_id
                    WHERE l.name = 'Kodi Favorites'
                """).fetchone()

                total = stats["total"] if stats else 0

                return {
                    "total": total,
                    "present": total,
                    "mapped": total,
                    "unmapped": 0,
                    "missing": 0
                }

        except Exception as e:
            self.logger.error("Error getting favorites stats: %s", e)
            return {"total": 0, "present": 0, "mapped": 0, "unmapped": 0, "missing": 0}

    def add_favorites_to_list(self, list_id: int, favorite_ids: List[int]) -> Dict[str, Any]:
        """Add mapped favorites to a list with duplicate detection"""
        try:
            added_count = 0
            skipped_count = 0

            with self.conn_manager.transaction() as conn:
                for favorite_id in favorite_ids:
                    # Get favorite from unified lists (Kodi Favorites list)
                    favorite = conn.execute("""
                        SELECT li.media_item_id, mi.title
                        FROM lists l
                        JOIN list_items li ON l.id = li.list_id
                        JOIN media_items mi ON li.media_item_id = mi.id
                        WHERE l.name = 'Kodi Favorites' AND li.id = ?
                    """, [favorite_id]).fetchone()

                    if not favorite or not favorite["media_item_id"]:
                        skipped_count += 1
                        continue

                    # Check if already in target list
                    existing = conn.execute("""
                        SELECT id FROM list_items
                        WHERE list_id = ? AND media_item_id = ?
                    """, [list_id, favorite["media_item_id"]]).fetchone()

                    if existing:
                        skipped_count += 1
                        continue

                    # Add to list
                    conn.execute("""
                        INSERT INTO list_items (list_id, media_item_id, created_at)
                        VALUES (?, ?, datetime('now'))
                    """, [list_id, favorite["media_item_id"]])

                    added_count += 1

            message = f"Added {added_count} favorites to list"
            if skipped_count > 0:
                message += f", skipped {skipped_count} (duplicates or unmapped)"

            return {
                "success": True,
                "added_count": added_count,
                "skipped_count": skipped_count,
                "message": message
            }

        except Exception as e:
            self.logger.error("Error adding favorites to list: %s", e)
            return {
                "success": False,
                "error": "operation_error",
                "message": str(e)
            }

    def _should_scan_favorites(self, favorites_file_path: str) -> bool:
        """Check if favorites scan is needed by comparing file timestamps"""
        try:
            # Get addon userdata directory
            userdata_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.librarygenie/')
            if not xbmcvfs.exists(userdata_dir):
                xbmcvfs.mkdirs(userdata_dir)
            
            # Marker file path (use xbmcvfs path)
            marker_file_path = userdata_dir + '.kodi_favorites_last_scan'
            
            # If marker file doesn't exist, scan is needed
            if not xbmcvfs.exists(marker_file_path):
                self.logger.debug("No scan marker file found - scan needed")
                return True
            
            # If favorites file doesn't exist, no scan needed
            if not xbmcvfs.exists(favorites_file_path):
                self.logger.debug("Favorites file doesn't exist - no scan needed")
                return False
            
            # Compare modification times using xbmcvfs.Stat
            try:
                favorites_stat = xbmcvfs.Stat(favorites_file_path)
                marker_stat = xbmcvfs.Stat(marker_file_path)
                
                favorites_mtime = favorites_stat.st_mtime()
                marker_mtime = marker_stat.st_mtime()
                
                # Scan needed if favorites file is newer than marker
                scan_needed = favorites_mtime > marker_mtime
                self.logger.debug("Timestamp comparison: favorites=%s, marker=%s, scan_needed=%s", favorites_mtime, marker_mtime, scan_needed)
                self.logger.debug("File paths: favorites='%s', marker='%s'", favorites_file_path, marker_file_path)
                return scan_needed
                
            except Exception as e:
                self.logger.warning("Error comparing file timestamps: %s", e)
                return True  # Default to scan if can't compare
                
        except Exception as e:
            self.logger.warning("Error checking scan necessity: %s", e)
            return True  # Default to scan on any error

    def _update_scan_marker(self):
        """Update the scan marker file timestamp"""
        try:
            # Get addon userdata directory
            userdata_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.librarygenie/')
            if not xbmcvfs.exists(userdata_dir):
                xbmcvfs.mkdirs(userdata_dir)
            
            # Marker file path (use xbmcvfs path)
            marker_file_path = userdata_dir + '.kodi_favorites_last_scan'
            
            # Touch the marker file (create or update timestamp) using xbmcvfs
            marker_file = xbmcvfs.File(marker_file_path, 'w')
            try:
                marker_file.write('')  # Write empty content to create/update file
            finally:
                marker_file.close()
                
            self.logger.debug("Updated scan marker file: %s", marker_file_path)
            
        except Exception as e:
            self.logger.warning("Error updating scan marker file: %s", e)

    def _fetch_artwork_from_kodi(self, kodi_id: int, media_type: str) -> Dict[str, str]:
        """Fetch artwork for library item from Kodi JSON-RPC"""
        try:
            import json
            import xbmc

            if media_type == 'movie':
                # Get movie details with artwork
                request = {
                    "jsonrpc": "2.0",
                    "method": "VideoLibrary.GetMovieDetails",
                    "params": {
                        "movieid": kodi_id,
                        "properties": ["art", "thumbnail", "fanart"]
                    },
                    "id": 1
                }
                response_str = xbmc.executeJSONRPC(json.dumps(request))
                response = json.loads(response_str)

                if response and "moviedetails" in response:
                    movie_details = response["moviedetails"]
                    artwork = {}

                    # Extract art dictionary
                    if "art" in movie_details and isinstance(movie_details["art"], dict):
                        artwork.update(movie_details["art"])

                    # Add top-level fields
                    if "thumbnail" in movie_details:
                        artwork["thumb"] = movie_details["thumbnail"]
                        artwork["poster"] = movie_details["thumbnail"]
                    if "fanart" in movie_details:
                        artwork["fanart"] = movie_details["fanart"]

                    self.logger.debug("ARTWORK: Retrieved %s art items for movie %s", len(artwork), kodi_id)
                    return artwork

            elif media_type == 'episode':
                # Get episode details with artwork
                request = {
                    "jsonrpc": "2.0",
                    "method": "VideoLibrary.GetEpisodeDetails",
                    "params": {
                        "episodeid": kodi_id,
                        "properties": ["art", "thumbnail", "fanart"]
                    },
                    "id": 1
                }
                response_str = xbmc.executeJSONRPC(json.dumps(request))
                response = json.loads(response_str)

                if response and "episodedetails" in response:
                    episode_details = response["episodedetails"]
                    artwork = {}

                    # Extract art dictionary
                    if "art" in episode_details and isinstance(episode_details["art"], dict):
                        artwork.update(episode_details["art"])

                    # Add top-level fields
                    if "thumbnail" in episode_details:
                        artwork["thumb"] = episode_details["thumbnail"]
                        artwork["poster"] = episode_details["thumbnail"]
                    if "fanart" in episode_details:
                        artwork["fanart"] = episode_details["fanart"]

                    self.logger.debug("ARTWORK: Retrieved %s art items for episode %s", len(artwork), kodi_id)
                    return artwork

            self.logger.debug("ARTWORK: No artwork retrieved for %s %s", media_type, kodi_id)
            return {}

        except Exception as e:
            self.logger.warning("ARTWORK: Failed to fetch artwork for %s %s: %s", media_type, kodi_id, e)
            return {}



# Global Phase 4 favorites manager instance
_phase4_favorites_manager_instance = None


def get_phase4_favorites_manager():
    """Get global Phase 4 favorites manager instance"""
    global _phase4_favorites_manager_instance
    if _phase4_favorites_manager_instance is None:
        _phase4_favorites_manager_instance = Phase4FavoritesManager()
    return _phase4_favorites_manager_instance