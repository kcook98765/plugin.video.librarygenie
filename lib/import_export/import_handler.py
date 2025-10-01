"""
LibraryGenie - Import File Media Handler
Orchestrates the import process for file-based media
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from lib.utils.kodi_log import get_kodi_logger
from lib.import_export.file_scanner import FileScanner
from lib.import_export.nfo_parser import NFOParser
from lib.import_export.media_classifier import MediaClassifier
from lib.import_export.art_extractor import ArtExtractor
from lib.data.connection_manager import get_connection_manager
from lib.data.query_manager import QueryManager
from lib.ui.dialog_service import get_dialog_service


class ImportHandler:
    """Handles file-based media import operations"""
    
    def __init__(self, storage):
        self.logger = get_kodi_logger('lib.import_export.import_handler')
        self.storage = storage
        self.connection_manager = get_connection_manager()
        self.query_manager = QueryManager()
        self.scanner = FileScanner()
        self.nfo_parser = NFOParser()
        self.classifier = MediaClassifier()
        self.art_extractor = ArtExtractor()
        self.cancel_requested = False
        self.current_import_source_id = None  # Track current import for locking
    
    def import_from_source(
        self,
        source_url: str,
        target_folder_id: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        root_folder_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import media from a source folder
        
        Args:
            source_url: URL/path to scan
            target_folder_id: Target LibraryGenie folder ID (None for root)
            progress_callback: Optional callback for progress updates
            root_folder_name: Optional custom name for root import folder
        
        Returns:
            Dictionary with import results including 'root_folder_id'
        """
        # Set import-in-progress flag to pause background cache operations
        from lib.utils.sync_lock import set_import_in_progress, clear_import_in_progress
        set_import_in_progress("file_import")
        
        # Show start notification
        dialog = get_dialog_service()
        dialog.show_success("Starting media import...", time_ms=2000)
        
        self.cancel_requested = False
        results = {
            'success': False,
            'folders_created': 0,
            'lists_created': 0,
            'items_imported': 0,
            'errors': [],
            'root_folder_id': None
        }
        
        try:
            # Create import source record first so we can lock all created folders/lists
            # Initially set folder_id to target_folder_id (will be updated if root_folder_name provided)
            import_source_id = self._create_import_source(source_url, target_folder_id)
            self.current_import_source_id = import_source_id
            
            # If root_folder_name is provided, create a wrapper folder (mark as import-sourced)
            actual_target_folder_id = target_folder_id
            if root_folder_name:
                self.logger.debug("Creating root import folder: '%s'", root_folder_name)
                actual_target_folder_id = self._create_or_get_folder(
                    root_folder_name, 
                    target_folder_id,
                    mark_as_import=True
                )
                self.logger.debug("Root import folder ID: %s", actual_target_folder_id)
                results['folders_created'] += 1
                
                # Update import_source with actual target folder
                self._update_import_source_folder(import_source_id, actual_target_folder_id)
            
            # Scan the source directory
            if progress_callback:
                progress_callback("Scanning directory...")
            
            # Disable ignore patterns during user-initiated imports - import everything found
            scan_result = self.scanner.scan_directory(source_url, recursive=True, apply_ignore_patterns=False)
            
            self.logger.debug("=== IMPORT FROM SOURCE ===")
            self.logger.debug("  Source URL: %s", source_url)
            self.logger.debug("  Original target folder ID: %s", target_folder_id)
            self.logger.debug("  Root folder name: %s", root_folder_name if root_folder_name else "None (use source structure)")
            self.logger.debug("  Actual target folder ID: %s", actual_target_folder_id)
            self.logger.debug("  Scan results: %d videos, %d NFOs, %d subdirs, %d art files",
                            len(scan_result['videos']), len(scan_result['nfos']), 
                            len(scan_result['subdirs']), len(scan_result['art']))
            
            # Classify the source folder
            classification = self.classifier.classify_folder(
                source_url,
                scan_result['videos'],
                scan_result['nfos'],
                scan_result['subdirs'],
                scan_result.get('disc_structure')
            )
            
            self.logger.debug("  Classification result: %s", classification)
            
            # Process based on classification
            if classification['type'] == 'tv_show':
                folder_results = self._import_tv_show(
                    source_url,
                    scan_result,
                    classification,
                    actual_target_folder_id,
                    progress_callback
                )
                results.update(folder_results)
            
            elif classification['type'] == 'season':
                list_results = self._import_season(
                    source_url,
                    scan_result,
                    classification,
                    actual_target_folder_id,
                    progress_callback
                )
                results.update(list_results)
            
            elif classification['type'] == 'single_video':
                item_results = self._import_single_video(
                    source_url,
                    scan_result,
                    classification,
                    actual_target_folder_id,
                    progress_callback
                )
                results.update(item_results)
            
            else:  # mixed content
                mixed_results = self._import_mixed_content(
                    source_url,
                    scan_result,
                    classification,
                    actual_target_folder_id,
                    progress_callback,
                    is_root_import=True  # Flag to prevent duplicate folder creation
                )
                results.update(mixed_results)
            
            # Update import source last_scan
            self._update_import_source(import_source_id)
            
            # Store root folder ID for navigation
            results['root_folder_id'] = actual_target_folder_id
            results['success'] = True
            
        except Exception as e:
            self.logger.error("Import failed: %s", e, exc_info=True)
            results['errors'].append(str(e))
        
        finally:
            # Synchronously rebuild cache for imported folder hierarchy, then clear import-in-progress flag
            try:
                # If import succeeded and we have a root folder, synchronously rebuild cache hierarchy
                if results.get('success') and results.get('root_folder_id'):
                    self.logger.info("Import completed - rebuilding cache hierarchy for root folder %s", 
                                   results['root_folder_id'])
                    from lib.ui.folder_cache import FolderCache
                    cache = FolderCache()  # Use default cache directory
                    
                    # Recursively delete stale caches for the entire folder hierarchy
                    invalidate_results = cache.invalidate_folder_hierarchy(str(results['root_folder_id']))
                    invalidated_count = sum(1 for success in invalidate_results.values() if success and success != "error")
                    affected_folders = [fid for fid in invalidate_results.keys() if fid != "error"]
                    self.logger.info("Invalidated %d folders in hierarchy for root folder %s: %s", 
                                   invalidated_count, results['root_folder_id'], affected_folders)
                    
                    # Synchronously rebuild cache for ALL folders in the hierarchy
                    # This ensures no stale caches remain when user navigates
                    rebuild_count = 0
                    for folder_id in affected_folders:
                        self.logger.debug("Pre-warming folder %s after import", folder_id)
                        if cache.pre_warm_folder(folder_id):
                            rebuild_count += 1
                        else:
                            self.logger.warning("Failed to pre-warm folder %s - will rebuild on navigation", folder_id)
                    
                    self.logger.info("Successfully rebuilt cache for %d/%d folders in hierarchy", 
                                   rebuild_count, len(affected_folders))
                
                # Clear flag AFTER cache hierarchy rebuild to prevent pre-warming from racing
                clear_import_in_progress()
                self.logger.info("Import-in-progress flag cleared")
                    
            except Exception as e:
                self.logger.error("Failed to rebuild cache hierarchy or clear import flag: %s", e)
                # Always clear the flag even if cache rebuild failed
                try:
                    clear_import_in_progress()
                except:
                    pass
            
            # Show completion notification
            if results.get('success'):
                items_count = results.get('items_imported', 0)
                folders_count = results.get('folders_created', 0)
                lists_count = results.get('lists_created', 0)
                
                message = f"Import complete: {items_count} items"
                if folders_count > 0:
                    message += f", {folders_count} folders"
                if lists_count > 0:
                    message += f", {lists_count} lists"
                
                dialog.show_success(message, time_ms=4000)
            else:
                error_msg = results.get('errors', ['Unknown error'])[0] if results.get('errors') else 'Unknown error'
                dialog.show_error(f"Import failed: {error_msg}", time_ms=5000)
        
        return results
    
    def _import_tv_show(
        self,
        show_path: str,
        scan_result: Dict,
        classification: Dict,
        parent_folder_id: Optional[int],
        progress_callback: Optional[Callable]
    ) -> Dict[str, int]:
        """Import a TV show with seasons"""
        results = {'folders_created': 0, 'lists_created': 0, 'items_imported': 0}
        
        self.logger.debug("=== IMPORTING TV SHOW ===")
        self.logger.debug("  Path: %s", show_path)
        self.logger.debug("  Classification: %s", classification)
        self.logger.debug("  Parent folder ID: %s", parent_folder_id)
        
        # Parse tvshow.nfo if available
        tvshow_nfo_path = self.scanner.find_folder_nfo(show_path, 'tvshow.nfo')
        tvshow_data = None
        if tvshow_nfo_path:
            self.logger.debug("  Found tvshow.nfo: %s", tvshow_nfo_path)
            tvshow_data = self.nfo_parser.parse_tvshow_nfo(Path(tvshow_nfo_path))
            self.logger.debug("  Parsed tvshow.nfo data: %s", json.dumps(tvshow_data, indent=2) if tvshow_data else "None")
        else:
            self.logger.debug("  No tvshow.nfo found")
        
        # Extract show metadata and art
        show_title = self._get_show_title(tvshow_data, show_path)
        self.logger.debug("  Show title: %s", show_title)
        
        show_art = self.art_extractor.extract_show_art(
            scan_result['art'],
            tvshow_data
        )
        self.logger.debug("  Show artwork extracted: %s", json.dumps(show_art, indent=2) if show_art else "None")
        self.logger.debug("  Available art files in scan: %s", scan_result['art'])
        
        # Create show folder (mark as import-sourced)
        show_folder_id = self._create_or_get_folder(
            show_title,
            parent_folder_id,
            art_data=show_art,
            mark_as_import=True
        )
        self.logger.debug("  Created/found show folder ID: %s", show_folder_id)
        results['folders_created'] += 1
        
        # Process subdirectories (seasons)
        self.logger.debug("Processing %d subdirectories of TV show", len(scan_result['subdirs']))
        for subdir in scan_result['subdirs']:
            if self.cancel_requested:
                break
            
            self.logger.debug("  === Processing subdirectory: %s ===", subdir)
            subdir_result = self.scanner.scan_directory(subdir, recursive=True)
            self.logger.debug("    Scan results: %d videos, %d NFOs, %d subdirs", 
                            len(subdir_result['videos']), len(subdir_result['nfos']), len(subdir_result['subdirs']))
            
            subdir_classification = self.classifier.classify_folder(
                subdir,
                subdir_result['videos'],
                subdir_result['nfos'],
                subdir_result['subdirs']
            )
            self.logger.debug("    Classification: %s", subdir_classification)
            
            if subdir_classification['type'] == 'season':
                season_results = self._import_season(
                    subdir,
                    subdir_result,
                    subdir_classification,
                    show_folder_id,
                    progress_callback,
                    show_art=show_art,
                    tvshow_data=tvshow_data
                )
                results['lists_created'] += season_results.get('lists_created', 0)
                results['items_imported'] += season_results.get('items_imported', 0)
        
        return results
    
    def _import_season(
        self,
        season_path: str,
        scan_result: Dict,
        classification: Dict,
        parent_folder_id: Optional[int],
        progress_callback: Optional[Callable],
        show_art: Optional[Dict] = None,
        tvshow_data: Optional[Dict] = None
    ) -> Dict[str, int]:
        """Import a TV season"""
        results = {'lists_created': 0, 'items_imported': 0}
        
        self.logger.debug("=== IMPORTING SEASON ===")
        self.logger.debug("  Path: %s", season_path)
        self.logger.debug("  Classification: %s", classification)
        self.logger.debug("  Parent folder ID: %s", parent_folder_id)
        
        # Determine season number and name
        season_number = classification.get('season_number', 0)
        if season_number:
            season_name = f"Season {season_number}"
        else:
            # Strip trailing slashes to get proper folder name
            season_name = os.path.basename(season_path.rstrip(os.sep).rstrip('/').rstrip('\\')) or "Season"
        self.logger.debug("  Season name: %s (number: %s)", season_name, season_number)
        
        # Create season list (mark as import-sourced)
        season_list_id = self._create_or_get_list(season_name, parent_folder_id, mark_as_import=True)
        self.logger.debug("  Created/found season list ID: %s", season_list_id)
        results['lists_created'] += 1
        
        # Import episode videos
        self.logger.debug("  Processing %d video files", len(scan_result['videos']))
        for video_path in scan_result['videos']:
            if self.cancel_requested:
                break
            
            self.logger.debug("  --- Processing episode: %s", video_path)
            
            # Find matching NFO
            nfo_path = self.scanner.find_matching_nfo(video_path, scan_result['nfos'])
            episode_data = None
            if nfo_path:
                self.logger.debug("    Found episode NFO: %s", nfo_path)
                parsed = self.nfo_parser.parse_episode_nfo(Path(nfo_path))
                # Episode parser returns a list, take the first episode
                if isinstance(parsed, list) and parsed:
                    episode_data = parsed[0]
                elif isinstance(parsed, dict):
                    episode_data = parsed
                self.logger.debug("    Parsed episode data: %s", json.dumps(episode_data, indent=2) if episode_data else "None")
            else:
                self.logger.debug("    No episode NFO found")
            
            # Extract art
            folder_art = self.art_extractor.extract_folder_art(scan_result['art'])
            self.logger.debug("    Folder art extracted: %s", json.dumps(folder_art, indent=2) if folder_art else "None")
            
            episode_art = self.art_extractor.extract_art_for_video(
                video_path,
                scan_result['art'],
                episode_data,
                folder_art
            )
            self.logger.debug("    Episode art extracted: %s", json.dumps(episode_art, indent=2) if episode_art else "None")
            
            # Merge with show art as fallback
            if show_art:
                episode_art = self.art_extractor.merge_art(episode_art, show_art)
                self.logger.debug("    Merged with show art: %s", json.dumps(episode_art, indent=2))
            
            # Create media item
            media_item_id = self._create_episode_item(
                video_path,
                episode_data,
                episode_art,
                tvshow_data,
                season_number
            )
            self.logger.debug("    Created episode media item ID: %s", media_item_id)
            
            # Add to season list (avoid duplicates)
            if media_item_id:
                self._add_item_to_list_if_not_exists(season_list_id, media_item_id)
                results['items_imported'] += 1
                self.logger.debug("    Added to season list (total imported: %d)", results['items_imported'])
        
        return results
    
    def _import_single_video(
        self,
        video_path: str,
        scan_result: Dict,
        classification: Dict,
        parent_folder_id: Optional[int],
        progress_callback: Optional[Callable]
    ) -> Dict[str, int]:
        """Import a single video (movie or standalone)"""
        results = {'items_imported': 0}
        
        self.logger.debug("=== IMPORTING SINGLE VIDEO ===")
        self.logger.debug("  Path: %s", video_path)
        self.logger.debug("  Classification: %s", classification)
        self.logger.debug("  Parent folder ID: %s", parent_folder_id)
        
        # Determine actual video path
        if classification.get('is_disc'):
            video_path = classification['disc_info']['path']
            self.logger.debug("  Disc structure detected, using path: %s", video_path)
        else:
            video_path = classification.get('video_path', scan_result['videos'][0] if scan_result['videos'] else video_path)
        
        # Find matching NFO
        nfo_path = self.scanner.find_matching_nfo(video_path, scan_result['nfos'])
        if not nfo_path:
            # Try folder NFO (movie.nfo or <foldername>.nfo)
            nfo_path = self.scanner.find_folder_nfo(os.path.dirname(video_path), 'movie.nfo')
        
        movie_data = None
        if nfo_path:
            self.logger.debug("  Found movie NFO: %s", nfo_path)
            movie_data = self.nfo_parser.parse_movie_nfo(Path(nfo_path))
            self.logger.debug("  Parsed movie data: %s", json.dumps(movie_data, indent=2) if movie_data else "None")
        else:
            self.logger.debug("  No movie NFO found")
        
        # Extract art
        folder_art = self.art_extractor.extract_folder_art(scan_result['art'])
        self.logger.debug("  Folder art extracted: %s", json.dumps(folder_art, indent=2) if folder_art else "None")
        
        movie_art = self.art_extractor.extract_art_for_video(
            video_path,
            scan_result['art'],
            movie_data,
            folder_art
        )
        self.logger.debug("  Movie art extracted: %s", json.dumps(movie_art, indent=2) if movie_art else "None")
        self.logger.debug("  Available art files in scan: %s", scan_result['art'])
        
        # Create media item
        media_item_id = self._create_movie_item(video_path, movie_data, movie_art)
        self.logger.debug("  Created movie media item ID: %s", media_item_id)
        
        if media_item_id:
            results['items_imported'] += 1
        
        return results
    
    def _import_mixed_content(
        self,
        folder_path: str,
        scan_result: Dict,
        classification: Dict,
        parent_folder_id: Optional[int],
        progress_callback: Optional[Callable],
        is_root_import: bool = False
    ) -> Dict[str, int]:
        """Import mixed content folder"""
        results = {'folders_created': 0, 'lists_created': 0, 'items_imported': 0}
        
        self.logger.debug("=== IMPORTING MIXED CONTENT ===")
        self.logger.debug("  Path: %s", folder_path)
        self.logger.debug("  Classification: %s", classification)
        self.logger.debug("  Parent folder ID: %s", parent_folder_id)
        self.logger.debug("  Scan results: %d videos (direct), %d subdirs", len(scan_result['videos']), len(scan_result['subdirs']))
        
        # Get folder name
        folder_name = os.path.basename(folder_path.rstrip(os.sep).rstrip('/').rstrip('\\')) or "Imported Media"
        
        # Determine structure based on content
        folder_id_for_content = parent_folder_id
        has_videos = len(scan_result['videos']) > 0
        has_subdirs = len(scan_result['subdirs']) > 0
        
        # If we have subdirectories, create a folder for organization
        # BUT skip this if it's the root import and we already have a wrapper folder
        if has_subdirs and not is_root_import:
            self.logger.debug("  Has subdirs - creating folder: '%s'", folder_name)
            folder_id_for_content = self._create_or_get_folder(folder_name, parent_folder_id, mark_as_import=True)
            self.logger.debug("  Created/found folder ID: %s", folder_id_for_content)
            results['folders_created'] += 1
        elif is_root_import:
            self.logger.debug("  Root import - using wrapper folder directly (no duplicate)")
            folder_id_for_content = parent_folder_id
        
        # Only create a list if we have videos DIRECTLY in this folder
        # (Scanner no longer merges subdir videos, so this is accurate)
        if has_videos:
            self.logger.debug("  Has %d direct videos - creating list: '%s'", len(scan_result['videos']), folder_name)
            list_id = self._create_or_get_list(folder_name, folder_id_for_content, mark_as_import=True)
            self.logger.debug("  Created/found list ID: %s in folder: %s", list_id, folder_id_for_content)
            results['lists_created'] += 1
            
            # Import each video
            self.logger.debug("  Processing %d video files", len(scan_result['videos']))
            for video_path in scan_result['videos']:
                if self.cancel_requested:
                    break
                
                self.logger.debug("  --- Processing video: %s", video_path)
                
                nfo_path = self.scanner.find_matching_nfo(video_path, scan_result['nfos'])
                movie_data = None
                if nfo_path:
                    self.logger.debug("    Found NFO: %s", nfo_path)
                    movie_data = self.nfo_parser.parse_movie_nfo(Path(nfo_path))
                    self.logger.debug("    Parsed movie data: %s", json.dumps(movie_data, indent=2) if movie_data else "None")
                else:
                    self.logger.debug("    No NFO found")
                
                folder_art = self.art_extractor.extract_folder_art(scan_result['art'])
                self.logger.debug("    Folder art: %s", json.dumps(folder_art, indent=2) if folder_art else "None")
                
                movie_art = self.art_extractor.extract_art_for_video(
                    video_path,
                    scan_result['art'],
                    movie_data,
                    folder_art
                )
                self.logger.debug("    Video art: %s", json.dumps(movie_art, indent=2) if movie_art else "None")
                
                media_item_id = self._create_movie_item(video_path, movie_data, movie_art)
                self.logger.debug("    Created media item ID: %s", media_item_id)
                
                if media_item_id:
                    self._add_item_to_list_if_not_exists(list_id, media_item_id)
                    results['items_imported'] += 1
                    self.logger.debug("    Added to list (total imported: %d)", results['items_imported'])
        
        # Process subdirectories recursively - pass the folder we created (or parent if no folder created)
        self.logger.debug("Processing %d subdirectories of mixed content folder", len(scan_result['subdirs']))
        for subdir in scan_result['subdirs']:
            if self.cancel_requested:
                break
            
            self.logger.debug("  === Processing subdirectory: %s ===", subdir)
            subdir_result = self.scanner.scan_directory(subdir, recursive=True)
            self.logger.debug("    Scan results: %d videos, %d NFOs, %d subdirs", 
                            len(subdir_result['videos']), len(subdir_result['nfos']), len(subdir_result['subdirs']))
            
            subdir_classification = self.classifier.classify_folder(
                subdir,
                subdir_result['videos'],
                subdir_result['nfos'],
                subdir_result['subdirs']
            )
            self.logger.debug("    Classification: %s", subdir_classification)
            
            # Recurse based on classification - use folder_id_for_content as parent
            if subdir_classification['type'] == 'tv_show':
                show_results = self._import_tv_show(
                    subdir, subdir_result, subdir_classification,
                    folder_id_for_content, progress_callback
                )
                results['folders_created'] += show_results.get('folders_created', 0)
                results['lists_created'] += show_results.get('lists_created', 0)
                results['items_imported'] += show_results.get('items_imported', 0)
            else:
                mixed_results = self._import_mixed_content(
                    subdir, subdir_result, subdir_classification,
                    folder_id_for_content, progress_callback
                )
                results['folders_created'] += mixed_results.get('folders_created', 0)
                results['lists_created'] += mixed_results.get('lists_created', 0)
                results['items_imported'] += mixed_results.get('items_imported', 0)
        
        return results
    
    def _get_show_title(self, tvshow_data: Optional[Dict], show_path: str) -> str:
        """Get TV show title from NFO data or folder name"""
        if tvshow_data and 'title' in tvshow_data:
            return tvshow_data['title']
        # Strip trailing slashes to get proper folder name
        return os.path.basename(show_path.rstrip(os.sep).rstrip('/').rstrip('\\')) or "TV Show"
    
    def _create_or_get_folder(
        self,
        name: str,
        parent_id: Optional[int],
        art_data: Optional[Dict] = None,
        mark_as_import: bool = False
    ) -> int:
        """Create or get existing folder using QueryManager
        
        Args:
            name: Folder name
            parent_id: Parent folder ID
            art_data: Artwork dictionary
            mark_as_import: Whether to mark folder as import-sourced (locked)
        """
        self.logger.debug("_create_or_get_folder called: name='%s', parent_id=%s, has_art=%s, mark_as_import=%s",
                         name, parent_id, bool(art_data), mark_as_import)
        
        # Check if folder exists
        if parent_id is None:
            existing = self.connection_manager.execute_single(
                "SELECT id FROM folders WHERE name = ? AND parent_id IS NULL",
                (name,)
            )
        else:
            existing = self.connection_manager.execute_single(
                "SELECT id FROM folders WHERE name = ? AND parent_id = ?",
                (name, parent_id)
            )
        
        if existing:
            self.logger.debug("  Found existing folder ID: %s", existing['id'])
            return existing['id']
        
        # Create new folder using QueryManager with art_data and import locking
        self.logger.debug("  Creating new folder...")
        import_source_id = self.current_import_source_id if mark_as_import else None
        result = self.query_manager.create_folder(
            name, 
            parent_id, 
            art_data=art_data,
            is_import_sourced=1 if mark_as_import else 0,
            import_source_id=import_source_id
        )
        
        if result.get('success'):
            self.logger.debug("  Successfully created folder ID: %s (import_locked: %s)", 
                            result['folder_id'], mark_as_import)
            return result['folder_id']
        else:
            # Handle error or duplicate (shouldn't happen due to check above)
            self.logger.error("Failed to create folder '%s': %s", name, result.get('error'))
            raise RuntimeError(f"Failed to create folder: {result.get('error')}")
    
    def _create_or_get_list(self, name: str, folder_id: Optional[int], mark_as_import: bool = False) -> int:
        """Create or get existing list using QueryManager
        
        Args:
            name: List name
            folder_id: Parent folder ID
            mark_as_import: Whether to mark list as import-sourced (locked)
        """
        self.logger.debug("_create_or_get_list called: name='%s', folder_id=%s, mark_as_import=%s", 
                         name, folder_id, mark_as_import)
        
        # Check if list exists
        if folder_id is None:
            existing = self.connection_manager.execute_single(
                "SELECT id FROM lists WHERE name = ? AND folder_id IS NULL",
                (name,)
            )
        else:
            existing = self.connection_manager.execute_single(
                "SELECT id FROM lists WHERE name = ? AND folder_id = ?",
                (name, folder_id)
            )
        
        if existing:
            self.logger.debug("  Found existing list ID: %s", existing['id'])
            return existing['id']
        
        # Create new list using QueryManager with import locking
        self.logger.debug("  Creating new list...")
        import_source_id = self.current_import_source_id if mark_as_import else None
        result = self.query_manager.create_list(
            name, 
            folder_id=folder_id,
            is_import_sourced=1 if mark_as_import else 0,
            import_source_id=import_source_id
        )
        
        if 'id' in result:
            self.logger.debug("  Successfully created list ID: %s", result['id'])
            return int(result['id'])
        else:
            # Handle error or duplicate (shouldn't happen due to check above)
            self.logger.error("Failed to create list '%s': %s", name, result.get('error'))
            raise RuntimeError(f"Failed to create list: {result.get('error')}")
    
    def _create_episode_item(
        self,
        video_path: str,
        episode_data: Optional[Dict],
        art: Dict,
        tvshow_data: Optional[Dict],
        season_number: int
    ) -> Optional[int]:
        """Create or update episode media item"""
        if not episode_data:
            episode_data = {}
        
        conn = self.connection_manager.get_connection()
        
        # Check if item already exists
        cursor = conn.execute(
            "SELECT id FROM media_items WHERE file_path = ? AND media_type = 'episode'",
            (video_path,)
        )
        existing = cursor.fetchone()
        
        # Fallback: use filename as title if no title from NFO
        title = episode_data.get('title')
        if not title:
            title = os.path.splitext(os.path.basename(video_path))[0]
        
        # Build media item data
        item_data = {
            'media_type': 'episode',
            'source': 'files',
            'play': video_path,
            'file_path': video_path,
            'art': json.dumps(art) if art else None,
            'title': title,
            'plot': episode_data.get('plot'),
            'tvshowtitle': tvshow_data.get('title') if tvshow_data else None,
            'season': episode_data.get('season', season_number),
            'episode': episode_data.get('episode'),
            'aired': episode_data.get('aired'),
            'rating': episode_data.get('rating'),
            'year': episode_data.get('year'),
            'duration': episode_data.get('runtime'),
            'director': json.dumps(episode_data.get('director')) if episode_data.get('director') else None,
            'writer': json.dumps(episode_data.get('writer')) if episode_data.get('writer') else None,
            'cast': json.dumps(episode_data.get('actor', [])) if episode_data.get('actor') else None,
            'updated_at': datetime.now().isoformat()
        }
        
        if existing:
            # Update existing item
            set_clause = ', '.join(f"{k} = ?" for k in item_data.keys() if item_data[k] is not None)
            values = [v for v in item_data.values() if v is not None]
            values.append(existing[0])
            
            conn.execute(
                f"UPDATE media_items SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()
            return existing[0]
        else:
            # Insert new item
            item_data['created_at'] = datetime.now().isoformat()
            columns = ', '.join(k for k in item_data.keys() if item_data[k] is not None)
            placeholders = ', '.join('?' for k in item_data.keys() if item_data[k] is not None)
            values = [v for v in item_data.values() if v is not None]
            
            cursor = conn.execute(
                f"INSERT INTO media_items ({columns}) VALUES ({placeholders})",
                values
            )
            conn.commit()
            return cursor.lastrowid
    
    def _create_movie_item(
        self,
        video_path: str,
        movie_data: Optional[Dict],
        art: Dict
    ) -> Optional[int]:
        """Create or update movie media item"""
        if not movie_data:
            movie_data = {}
        
        conn = self.connection_manager.get_connection()
        
        # Check if item already exists
        cursor = conn.execute(
            "SELECT id FROM media_items WHERE file_path = ? AND media_type = 'movie'",
            (video_path,)
        )
        existing = cursor.fetchone()
        
        # Fallback: use filename as title if no title from NFO
        title = movie_data.get('title')
        if not title:
            title = os.path.splitext(os.path.basename(video_path))[0]
        
        # Build media item data
        item_data = {
            'media_type': 'movie',
            'source': 'files',
            'play': video_path,
            'file_path': video_path,
            'art': json.dumps(art) if art else None,
            'title': title,
            'year': movie_data.get('year'),
            'plot': movie_data.get('plot'),
            'rating': movie_data.get('rating'),
            'imdbnumber': movie_data.get('imdbnumber'),
            'tmdb_id': movie_data.get('tmdb_id'),
            'duration': movie_data.get('runtime'),
            'mpaa': movie_data.get('mpaa'),
            # Store genre and studio as comma-separated strings (matching library sync format)
            # Join lists, preserve strings as-is, keep None for missing values
            'genre': (", ".join(movie_data['genre']) if isinstance(movie_data.get('genre'), list) and movie_data.get('genre') else (str(movie_data['genre']) if movie_data.get('genre') else None)),
            'director': json.dumps(movie_data.get('director')) if movie_data.get('director') else None,
            'studio': (", ".join(movie_data['studio']) if isinstance(movie_data.get('studio'), list) and movie_data.get('studio') else (str(movie_data['studio']) if movie_data.get('studio') else None)),
            'writer': json.dumps(movie_data.get('writer')) if movie_data.get('writer') else None,
            'cast': json.dumps(movie_data.get('actor', [])) if movie_data.get('actor') else None,
            'updated_at': datetime.now().isoformat()
        }
        
        if existing:
            # Update existing item
            set_clause = ', '.join(f"{k} = ?" for k in item_data.keys() if item_data[k] is not None)
            values = [v for v in item_data.values() if v is not None]
            values.append(existing[0])
            
            conn.execute(
                f"UPDATE media_items SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()
            return existing[0]
        else:
            # Insert new item
            item_data['created_at'] = datetime.now().isoformat()
            columns = ', '.join(k for k in item_data.keys() if item_data[k] is not None)
            placeholders = ', '.join('?' for k in item_data.keys() if item_data[k] is not None)
            values = [v for v in item_data.values() if v is not None]
            
            cursor = conn.execute(
                f"INSERT INTO media_items ({columns}) VALUES ({placeholders})",
                values
            )
            conn.commit()
            return cursor.lastrowid
    
    def _create_import_source(self, source_url: str, folder_id: Optional[int]) -> int:
        """Create or get existing import source record"""
        conn = self.connection_manager.get_connection()
        
        # Check if import source already exists
        if folder_id is None:
            cursor = conn.execute(
                "SELECT id FROM import_sources WHERE source_url = ? AND folder_id IS NULL",
                (source_url,)
            )
        else:
            cursor = conn.execute(
                "SELECT id FROM import_sources WHERE source_url = ? AND folder_id = ?",
                (source_url, folder_id)
            )
        
        existing = cursor.fetchone()
        
        if existing:
            return existing[0]
        
        # Create new import source
        cursor = conn.execute(
            """INSERT INTO import_sources (source_url, source_type, folder_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (source_url, 'file', folder_id, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid or 0
    
    def _update_import_source(self, import_source_id: int):
        """Update import source last_scan timestamp"""
        conn = self.connection_manager.get_connection()
        conn.execute(
            "UPDATE import_sources SET last_scan = ? WHERE id = ?",
            (datetime.now().isoformat(), import_source_id)
        )
        conn.commit()
    
    def _update_import_source_folder(self, import_source_id: int, folder_id: int):
        """Update import source folder_id (for root wrapper folder updates)"""
        conn = self.connection_manager.get_connection()
        conn.execute(
            "UPDATE import_sources SET folder_id = ? WHERE id = ?",
            (folder_id, import_source_id)
        )
        conn.commit()
    
    def _add_item_to_list_if_not_exists(self, list_id: int, media_item_id: int):
        """Add item to list only if not already present"""
        with self.connection_manager.transaction() as conn:
            # Check if already exists
            cursor = conn.execute(
                "SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?",
                (list_id, media_item_id)
            )
            
            if not cursor.fetchone():
                # Get next position
                position_result = conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 as next_position FROM list_items WHERE list_id = ?",
                    (list_id,)
                ).fetchone()
                next_position = position_result[0] if position_result else 0
                
                # Insert with proper position
                conn.execute(
                    "INSERT INTO list_items (list_id, media_item_id, position, created_at) VALUES (?, ?, ?, ?)",
                    (list_id, media_item_id, next_position, datetime.now().isoformat())
                )
    
    def cancel(self):
        """Request cancellation of current import"""
        self.cancel_requested = True
