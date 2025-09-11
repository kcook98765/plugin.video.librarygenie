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
from ..utils.logger import get_logger
from ..config import get_config
from .favorites_parser import Phase4FavoritesParser
from ..data.list_library_manager import get_list_library_manager


class Phase4FavoritesManager:
    """Phase 4: Enhanced favorites manager with reliable mapping and batch processing"""

    def __init__(self):
        self.logger = get_logger(__name__)
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
                            self.logger.info(f"      normalized: '{sample['normalized_path']}'")
                            self.logger.info(f"      file_path:  '{sample['file_path']}'")
                    else:
                        self.logger.info("    No normalized paths found in database")

                    # Always try file_path matching as backup
                    self.logger.info("    Trying file_path matching")
                    result = self._try_file_path_matching(normalized_key)
                    if result:
                        self.logger.info(f"    Found file_path match: ID {result}")
                        return result

                # Try fuzzy path matching for variations
                self.logger.info("    Attempting fuzzy path matching")
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    self.logger.info(f"    Fuzzy match found: ID {result}")
                    return result
                else:
                    self.logger.info("    No fuzzy match found")
            else:
                self.logger.info(f"    Classification '{classification}' not supported for matching")

            self.logger.info("    No library match found")
            return None

        except Exception as e:
            self.logger.error(f"Error finding library match for '{target_raw}': {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _try_file_path_matching(self, normalized_key: str) -> Optional[int]:
        """Attempt to match using the raw file_path with multiple strategies"""
        self.logger.info(f"    Attempting file path matching for key: '{normalized_key}'")
        try:
            with self.conn_manager.transaction() as conn:
                # Strategy 1: Try exact file path match
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE file_path = ? AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info(f"    Found exact file_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 2: Try case-insensitive file_path match
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE LOWER(file_path) = LOWER(?) AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info(f"    Found case-insensitive file_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 3: Try normalized_path match (in case it exists but wasn't found earlier)
                result = conn.execute("""
                    SELECT id, title, file_path, normalized_path FROM media_items
                    WHERE LOWER(normalized_path) = LOWER(?) AND is_removed = 0
                """, [normalized_key]).fetchone()

                if result:
                    self.logger.info(f"    Found case-insensitive normalized_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 4: Try to match by converting backslashes to forward slashes in file_path
                backslash_version = normalized_key.replace('/', '\\')
                result = conn.execute("""
                    SELECT id, title, file_path FROM media_items
                    WHERE file_path = ? AND is_removed = 0
                """, [backslash_version]).fetchone()

                if result:
                    self.logger.info(f"    Found backslash file_path match: ID {result['id']} - '{result['title']}'")
                    return result["id"]

                # Strategy 5: Try fuzzy path matching for variations
                self.logger.info("    Attempting fuzzy file_path matching")
                result = self._fuzzy_path_match(normalized_key)
                if result:
                    self.logger.info(f"    Fuzzy file_path match found: ID {result}")
                    return result

                self.logger.info("    No file_path matches found")
                return None

        except Exception as e:
            self.logger.error(f"Error in file path matching: {e}")
            return None

    def _fuzzy_path_match(self, normalized_key: str) -> Optional[int]:
        """Fuzzy path matching for path variations"""
        try:
            # Extract just the filename for fuzzy matching
            filename = normalized_key.split('/')[-1] if '/' in normalized_key else normalized_key
            filename = filename.split('\\')[-1] if '\\' in filename else filename  # Handle backslashes too
            self.logger.info(f"      Fuzzy matching with filename: '{filename}'")

            if not filename or len(filename) < 3:
                self.logger.info(f"      Filename too short for fuzzy matching: '{filename}'")
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

                self.logger.info(f"      Found {len(results)} potential fuzzy matches")

                for i, result in enumerate(results):
                    self.logger.info(f"        Match {i+1}: ID {result['id']} - '{result['title']}' - {result['file_path']}")

                if results and len(results) == 1:
                    # Exactly one match - probably correct
                    result = results[0]
                    self.logger.info(f"      Single fuzzy match selected: ID {result['id']}")
                    return result["id"]
                elif len(results) > 1:
                    # Try to find exact filename match (case insensitive)
                    for result in results:
                        result_filename = result['file_path'].split('/')[-1].split('\\')[-1].lower()
                        if result_filename == filename.lower():
                            self.logger.info(f"      Exact filename match found: ID {result['id']} - '{result['title']}'")
                            return result["id"]

                    self.logger.info("      Multiple fuzzy matches found but no exact filename match - skipping for reliability")
                else:
                    self.logger.info("      No fuzzy matches found")

                return None

        except Exception as e:
            self.logger.error(f"Error in fuzzy path matching: {e}")
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
                    self.logger.info(f"    Found existing movie: ID {result['id']} - '{result['title']}'")
                    return result["id"]
                else:
                    self.logger.info(f"    No existing movie found for Kodi dbid {kodi_dbid}")
                    
                    # TODO: Implement on-demand movie creation from Kodi JSON-RPC
                    # For now, return None - movies should exist from library scan
                    self.logger.info(f"    Movie creation not implemented - skipping")
                    return None

        except Exception as e:
            self.logger.error(f"Error finding/creating movie by Kodi ID {kodi_dbid}: {e}")
            return None

    def _find_or_create_episode_by_show_season_episode(self, show_kodi_id: int, season: int, episode: int) -> Optional[int]:
        """Find episode by show/season/episode, create if missing using on-demand loading"""
        try:
            # Get episode info from Kodi first to get episode kodi_id and file path
            episode_data = self._get_episode_data_from_kodi(show_kodi_id, season, episode)
            if not episode_data:
                self.logger.info(f"    Could not retrieve episode data for show {show_kodi_id} S{season}E{episode}")
                return None
            
            episode_kodi_id = episode_data.get('episodeid')
            episode_file = episode_data.get('file', '')
            show_title = episode_data.get('show_title', '')
            
            self.logger.info(f"    Looking for episode: '{show_title}' S{season:02d}E{episode:02d} (kodi_id: {episode_kodi_id})")
            
            with self.conn_manager.transaction() as conn:
                # Strategy 1: Try to find by episode kodi_id (most reliable)
                if episode_kodi_id:
                    result = conn.execute("""
                        SELECT id, title FROM media_items
                        WHERE kodi_id = ? AND media_type = 'episode' AND is_removed = 0
                    """, [episode_kodi_id]).fetchone()
                    
                    if result:
                        self.logger.info(f"    Found existing episode by kodi_id: ID {result['id']} - '{result['title']}'")
                        return result["id"]
                
                # Strategy 2: Try to find by file path
                if episode_file:
                    normalized_path = self._normalize_episode_path(episode_file)
                    result = conn.execute("""
                        SELECT id, title FROM media_items
                        WHERE (file_path = ? OR normalized_path = ?) 
                        AND media_type = 'episode' AND is_removed = 0
                    """, [episode_file, normalized_path]).fetchone()
                    
                    if result:
                        self.logger.info(f"    Found existing episode by file path: ID {result['id']} - '{result['title']}'")
                        return result["id"]
                
                # Strategy 3: Try to find by show title + season + episode (fallback)
                if show_title:
                    result = conn.execute("""
                        SELECT id, title FROM media_items
                        WHERE LOWER(tvshowtitle) = LOWER(?) 
                        AND season = ? 
                        AND episode = ? 
                        AND media_type = 'episode'
                        AND is_removed = 0
                    """, [show_title, season, episode]).fetchone()

                    if result:
                        self.logger.info(f"    Found existing episode by show+season+episode: ID {result['id']} - '{result['title']}'")
                        return result["id"]
                
                # No existing episode found - create on-demand
                self.logger.info(f"    No existing episode found - creating on-demand")
                episode_id = self._create_episode_from_episode_data(episode_data)
                if episode_id:
                    self.logger.info(f"    Successfully created episode: ID {episode_id}")
                    return episode_id
                else:
                    self.logger.info(f"    Failed to create episode from Kodi")
                    return None

        except Exception as e:
            self.logger.error(f"Error finding/creating episode for show {show_kodi_id} S{season}E{episode}: {e}")
            return None

    def _get_show_info_from_kodi(self, show_kodi_id: int) -> Optional[Dict]:
        """Get TV show information from Kodi using JSON-RPC"""
        try:
            import xbmc
            import json
            
            # Use Kodi's JSON-RPC to get show information
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetTVShowDetails",
                "params": {
                    "tvshowid": show_kodi_id,
                    "properties": ["title", "plot", "year", "premiered", "rating", "votes", "genre", "studio", "imdbnumber", "uniqueid"]
                },
                "id": 1
            }
            
            response = xbmc.executeJSONRPC(json.dumps(request))
            response_data = json.loads(response)
            
            if "result" in response_data and "tvshowdetails" in response_data["result"]:
                show_details = response_data["result"]["tvshowdetails"]
                self.logger.info(f"    Retrieved show info: '{show_details.get('title')}'")
                return show_details
            else:
                self.logger.warning(f"    No show details found for Kodi show ID {show_kodi_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting show info from Kodi for ID {show_kodi_id}: {e}")
            return None

    def _get_episode_data_from_kodi(self, show_kodi_id: int, season: int, episode: int) -> Optional[Dict]:
        """Get combined TV show and episode data from Kodi using JSON-RPC"""
        try:
            # Get show info first
            show_info = self._get_show_info_from_kodi(show_kodi_id)
            if not show_info:
                return None
            
            import xbmc
            import json
            
            # Get episode details from Kodi using JSON-RPC
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "tvshowid": show_kodi_id,
                    "season": season,
                    "properties": ["title", "plot", "rating", "votes", "runtime", "firstaired", 
                                 "playcount", "lastplayed", "file", "streamdetails", "art", "uniqueid"]
                },
                "id": 1
            }
            
            response = xbmc.executeJSONRPC(json.dumps(request))
            response_data = json.loads(response)
            
            if "result" not in response_data or "episodes" not in response_data["result"]:
                self.logger.warning(f"    No episodes found for show {show_kodi_id} season {season}")
                return None
            
            # Find the specific episode
            target_episode = None
            for ep in response_data["result"]["episodes"]:
                if ep.get("episode") == episode:
                    target_episode = ep
                    break
            
            if not target_episode:
                self.logger.warning(f"    Episode {episode} not found in season {season} of show {show_kodi_id}")
                return None
            
            # Combine show and episode data
            combined_data = {
                'show_info': show_info,
                'episode_info': target_episode,
                'show_title': show_info.get('title', ''),
                'season': season,
                'episode': episode,
                'episodeid': target_episode.get('episodeid'),
                'file': target_episode.get('file', '')
            }
            
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error getting episode data from Kodi for show {show_kodi_id} S{season}E{episode}: {e}")
            return None

    def _create_episode_from_kodi(self, show_kodi_id: int, season: int, episode: int, show_info: Dict) -> Optional[int]:
        """Create episode media_item from Kodi JSON-RPC data"""
        try:
            import xbmc
            import json
            from datetime import datetime
            
            # Get episode details from Kodi using JSON-RPC
            request = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "tvshowid": show_kodi_id,
                    "season": season,
                    "properties": ["title", "plot", "rating", "votes", "runtime", "firstaired", 
                                 "playcount", "lastplayed", "file", "streamdetails", "art", "uniqueid"]
                },
                "id": 1
            }
            
            response = xbmc.executeJSONRPC(json.dumps(request))
            response_data = json.loads(response)
            
            if "result" not in response_data or "episodes" not in response_data["result"]:
                self.logger.warning(f"    No episodes found for show {show_kodi_id} season {season}")
                return None
            
            # Find the specific episode
            target_episode = None
            for ep in response_data["result"]["episodes"]:
                if ep.get("episode") == episode:
                    target_episode = ep
                    break
            
            if not target_episode:
                self.logger.warning(f"    Episode {episode} not found in season {season} of show {show_kodi_id}")
                return None
            
            # Extract episode data
            episode_title = target_episode.get("title", f"Episode {episode}")
            plot = target_episode.get("plot", "")
            rating = target_episode.get("rating", 0.0)
            votes = target_episode.get("votes", 0)
            runtime = target_episode.get("runtime", 0)  # in seconds
            duration = runtime // 60 if runtime else 0  # convert to minutes
            firstaired = target_episode.get("firstaired", "")
            file_path = target_episode.get("file", "")
            episode_kodi_id = target_episode.get("episodeid")
            
            # Get show metadata
            show_title = show_info.get("title", "Unknown Show")
            show_year = show_info.get("year")
            show_genre = show_info.get("genre", [])
            genre_str = ", ".join(show_genre) if isinstance(show_genre, list) else str(show_genre) if show_genre else ""
            show_studio = show_info.get("studio", [])
            studio_str = ", ".join(show_studio) if isinstance(show_studio, list) else str(show_studio) if show_studio else ""
            
            # Get external IDs
            imdb_id = show_info.get("imdbnumber", "")
            tmdb_id = ""
            if "uniqueid" in show_info and isinstance(show_info["uniqueid"], dict):
                tmdb_id = show_info["uniqueid"].get("tmdb", "")
                # Episode-specific IMDb ID if available
                if "uniqueid" in target_episode and isinstance(target_episode["uniqueid"], dict):
                    episode_imdb = target_episode["uniqueid"].get("imdb", "")
                    if episode_imdb:
                        imdb_id = episode_imdb
            
            # Create normalized path
            normalized_path = self._normalize_episode_path(file_path) if file_path else ""
            
            # Create display title
            display_title = f"{show_title} - S{season:02d}E{episode:02d} - {episode_title}"
            
            # Insert into media_items table
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO media_items (
                        media_type, title, year, imdbnumber, tmdb_id, kodi_id, source,
                        play, plot, rating, votes, duration, genre, studio,
                        file_path, normalized_path, is_removed, display_title, 
                        duration_seconds, created_at, updated_at,
                        tvshowtitle, season, episode, aired
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    'episode', episode_title, show_year, imdb_id, tmdb_id, episode_kodi_id, 'library',
                    file_path, plot, rating, votes, duration, genre_str, studio_str,
                    file_path, normalized_path, 0, display_title,
                    runtime, datetime.now().isoformat(), datetime.now().isoformat(),
                    show_title, season, episode, firstaired
                ])
                
                episode_media_id = cursor.lastrowid
                self.logger.info(f"    Created episode media_item: ID {episode_media_id} - '{display_title}'")
                return episode_media_id
                
        except Exception as e:
            self.logger.error(f"Error creating episode from Kodi for show {show_kodi_id} S{season}E{episode}: {e}")
            return None

    def _create_episode_from_episode_data(self, episode_data: Dict) -> Optional[int]:
        """Create episode media_item from combined episode data"""
        try:
            from datetime import datetime
            
            show_info = episode_data['show_info']
            episode_info = episode_data['episode_info']
            show_title = episode_data['show_title']
            season = episode_data['season']
            episode = episode_data['episode']
            
            # Extract episode data
            episode_title = episode_info.get("title", f"Episode {episode}")
            plot = episode_info.get("plot", "")
            rating = episode_info.get("rating", 0.0)
            votes = episode_info.get("votes", 0)
            runtime = episode_info.get("runtime", 0)  # in seconds
            duration = runtime // 60 if runtime else 0  # convert to minutes
            firstaired = episode_info.get("firstaired", "")
            file_path = episode_info.get("file", "")
            episode_kodi_id = episode_info.get("episodeid")
            
            # Get show metadata
            show_year = show_info.get("year")
            show_genre = show_info.get("genre", [])
            genre_str = ", ".join(show_genre) if isinstance(show_genre, list) else str(show_genre) if show_genre else ""
            show_studio = show_info.get("studio", [])
            studio_str = ", ".join(show_studio) if isinstance(show_studio, list) else str(show_studio) if show_studio else ""
            
            # Get external IDs
            imdb_id = show_info.get("imdbnumber", "")
            tmdb_id = ""
            if "uniqueid" in show_info and isinstance(show_info["uniqueid"], dict):
                tmdb_id = show_info["uniqueid"].get("tmdb", "")
                # Episode-specific IMDb ID if available
                if "uniqueid" in episode_info and isinstance(episode_info["uniqueid"], dict):
                    episode_imdb = episode_info["uniqueid"].get("imdb", "")
                    if episode_imdb:
                        imdb_id = episode_imdb
            
            # Create normalized path
            normalized_path = self._normalize_episode_path(file_path) if file_path else ""
            
            # Create display title
            display_title = f"{show_title} - S{season:02d}E{episode:02d} - {episode_title}"
            
            # Insert into media_items table with consistent schema usage
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO media_items (
                        media_type, title, year, imdbnumber, tmdb_id, kodi_id, source,
                        play, plot, rating, votes, duration, genre, studio,
                        file_path, normalized_path, is_removed, display_title, 
                        duration_seconds, created_at, updated_at,
                        tvshowtitle, season, episode, aired
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    'episode', episode_title, show_year, imdb_id, tmdb_id, episode_kodi_id, 'library',
                    file_path, plot, rating, votes, duration, genre_str, studio_str,
                    file_path, normalized_path, 0, display_title,
                    runtime, datetime.now().isoformat(), datetime.now().isoformat(),
                    show_title, season, episode, firstaired
                ])
                
                episode_media_id = cursor.lastrowid
                self.logger.info(f"    Created episode media_item: ID {episode_media_id} - '{display_title}'")
                return episode_media_id
                
        except Exception as e:
            self.logger.error(f"Error creating episode from episode data: {e}")
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
            self.logger.debug(f"Error normalizing episode path '{file_path}': {e}")
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

            self.logger.info(f"Retrieved {len(favorites)} favorites using standard list query approach")
            return favorites

        except Exception as e:
            self.logger.error(f"Error getting mapped favorites: {e}")
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
            self.logger.error(f"Error getting favorites stats: {e}")
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
            self.logger.error(f"Error adding favorites to list: {e}")
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
                self.logger.debug(f"Timestamp comparison: favorites={favorites_mtime}, marker={marker_mtime}, scan_needed={scan_needed}")
                self.logger.debug(f"File paths: favorites='{favorites_file_path}', marker='{marker_file_path}'")
                return scan_needed
                
            except Exception as e:
                self.logger.warning(f"Error comparing file timestamps: {e}")
                return True  # Default to scan if can't compare
                
        except Exception as e:
            self.logger.warning(f"Error checking scan necessity: {e}")
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
                
            self.logger.debug(f"Updated scan marker file: {marker_file_path}")
            
        except Exception as e:
            self.logger.warning(f"Error updating scan marker file: {e}")

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

                    self.logger.debug(f"ARTWORK: Retrieved {len(artwork)} art items for movie {kodi_id}")
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

                    self.logger.debug(f"ARTWORK: Retrieved {len(artwork)} art items for episode {kodi_id}")
                    return artwork

            self.logger.debug(f"ARTWORK: No artwork retrieved for {media_type} {kodi_id}")
            return {}

        except Exception as e:
            self.logger.warning(f"ARTWORK: Failed to fetch artwork for {media_type} {kodi_id}: {e}")
            return {}



# Global Phase 4 favorites manager instance
_phase4_favorites_manager_instance = None


def get_phase4_favorites_manager():
    """Get global Phase 4 favorites manager instance"""
    global _phase4_favorites_manager_instance
    if _phase4_favorites_manager_instance is None:
        _phase4_favorites_manager_instance = Phase4FavoritesManager()
    return _phase4_favorites_manager_instance