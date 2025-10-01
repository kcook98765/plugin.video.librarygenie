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


class ImportHandler:
    """Handles file-based media import operations"""
    
    def __init__(self, storage):
        self.logger = get_kodi_logger('lib.import_export.import_handler')
        self.storage = storage
        self.connection_manager = get_connection_manager()
        self.scanner = FileScanner()
        self.nfo_parser = NFOParser()
        self.classifier = MediaClassifier()
        self.art_extractor = ArtExtractor()
        self.cancel_requested = False
    
    def import_from_source(
        self,
        source_url: str,
        target_folder_id: Optional[int] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Import media from a source folder
        
        Args:
            source_url: URL/path to scan
            target_folder_id: Target LibraryGenie folder ID (None for root)
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dictionary with import results
        """
        self.cancel_requested = False
        results = {
            'success': False,
            'folders_created': 0,
            'lists_created': 0,
            'items_imported': 0,
            'errors': []
        }
        
        try:
            # Create import source record
            import_source_id = self._create_import_source(source_url, target_folder_id)
            
            # Scan the source directory
            if progress_callback:
                progress_callback("Scanning directory...")
            
            scan_result = self.scanner.scan_directory(source_url, recursive=True)
            
            # Classify the source folder
            classification = self.classifier.classify_folder(
                source_url,
                scan_result['videos'],
                scan_result['nfos'],
                scan_result['subdirs'],
                scan_result.get('disc_structure')
            )
            
            # Process based on classification
            if classification['type'] == 'tv_show':
                folder_results = self._import_tv_show(
                    source_url,
                    scan_result,
                    classification,
                    target_folder_id,
                    progress_callback
                )
                results.update(folder_results)
            
            elif classification['type'] == 'season':
                list_results = self._import_season(
                    source_url,
                    scan_result,
                    classification,
                    target_folder_id,
                    progress_callback
                )
                results.update(list_results)
            
            elif classification['type'] == 'single_video':
                item_results = self._import_single_video(
                    source_url,
                    scan_result,
                    classification,
                    target_folder_id,
                    progress_callback
                )
                results.update(item_results)
            
            else:  # mixed content
                mixed_results = self._import_mixed_content(
                    source_url,
                    scan_result,
                    classification,
                    target_folder_id,
                    progress_callback
                )
                results.update(mixed_results)
            
            # Update import source last_scan
            self._update_import_source(import_source_id)
            
            results['success'] = True
            
        except Exception as e:
            self.logger.error("Import failed: %s", e, exc_info=True)
            results['errors'].append(str(e))
        
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
        
        # Parse tvshow.nfo if available
        tvshow_nfo_path = self.scanner.find_folder_nfo(show_path, 'tvshow.nfo')
        tvshow_data = None
        if tvshow_nfo_path:
            tvshow_data = self.nfo_parser.parse_tvshow_nfo(Path(tvshow_nfo_path))
        
        # Extract show metadata and art
        show_title = self._get_show_title(tvshow_data, show_path)
        show_art = self.art_extractor.extract_show_art(
            scan_result['art'],
            tvshow_data
        )
        
        # Create show folder
        show_folder_id = self._create_or_get_folder(
            show_title,
            parent_folder_id,
            art_data=show_art
        )
        results['folders_created'] += 1
        
        # Process subdirectories (seasons)
        for subdir in scan_result['subdirs']:
            if self.cancel_requested:
                break
            
            subdir_result = self.scanner.scan_directory(subdir, recursive=True)
            subdir_classification = self.classifier.classify_folder(
                subdir,
                subdir_result['videos'],
                subdir_result['nfos'],
                subdir_result['subdirs']
            )
            
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
        
        # Determine season number and name
        season_number = classification.get('season_number', 0)
        season_name = f"Season {season_number}" if season_number else os.path.basename(season_path)
        
        # Create season list
        season_list_id = self._create_or_get_list(season_name, parent_folder_id)
        results['lists_created'] += 1
        
        # Import episode videos
        for video_path in scan_result['videos']:
            if self.cancel_requested:
                break
            
            # Find matching NFO
            nfo_path = self.scanner.find_matching_nfo(video_path, scan_result['nfos'])
            episode_data = None
            if nfo_path:
                parsed = self.nfo_parser.parse_episode_nfo(Path(nfo_path))
                # Episode parser returns a list, take the first episode
                if isinstance(parsed, list) and parsed:
                    episode_data = parsed[0]
                elif isinstance(parsed, dict):
                    episode_data = parsed
            
            # Extract art
            folder_art = self.art_extractor.extract_folder_art(scan_result['art'])
            episode_art = self.art_extractor.extract_art_for_video(
                video_path,
                scan_result['art'],
                episode_data,
                folder_art
            )
            
            # Merge with show art as fallback
            if show_art:
                episode_art = self.art_extractor.merge_art(episode_art, show_art)
            
            # Create media item
            media_item_id = self._create_episode_item(
                video_path,
                episode_data,
                episode_art,
                tvshow_data,
                season_number
            )
            
            # Add to season list (avoid duplicates)
            if media_item_id:
                self._add_item_to_list_if_not_exists(season_list_id, media_item_id)
                results['items_imported'] += 1
        
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
        
        # Determine actual video path
        if classification.get('is_disc'):
            video_path = classification['disc_info']['path']
        else:
            video_path = classification.get('video_path', scan_result['videos'][0] if scan_result['videos'] else video_path)
        
        # Find matching NFO
        nfo_path = self.scanner.find_matching_nfo(video_path, scan_result['nfos'])
        if not nfo_path:
            # Try folder NFO (movie.nfo or <foldername>.nfo)
            nfo_path = self.scanner.find_folder_nfo(os.path.dirname(video_path), 'movie.nfo')
        
        movie_data = None
        if nfo_path:
            movie_data = self.nfo_parser.parse_movie_nfo(Path(nfo_path))
        
        # Extract art
        folder_art = self.art_extractor.extract_folder_art(scan_result['art'])
        movie_art = self.art_extractor.extract_art_for_video(
            video_path,
            scan_result['art'],
            movie_data,
            folder_art
        )
        
        # Create media item
        media_item_id = self._create_movie_item(video_path, movie_data, movie_art)
        
        if media_item_id:
            results['items_imported'] += 1
        
        return results
    
    def _import_mixed_content(
        self,
        folder_path: str,
        scan_result: Dict,
        classification: Dict,
        parent_folder_id: Optional[int],
        progress_callback: Optional[Callable]
    ) -> Dict[str, int]:
        """Import mixed content folder"""
        results = {'folders_created': 0, 'lists_created': 0, 'items_imported': 0}
        
        # Create a list for this folder's videos if any
        if scan_result['videos']:
            folder_name = os.path.basename(folder_path)
            list_id = self._create_or_get_list(folder_name, parent_folder_id)
            results['lists_created'] += 1
            
            # Import each video
            for video_path in scan_result['videos']:
                if self.cancel_requested:
                    break
                
                nfo_path = self.scanner.find_matching_nfo(video_path, scan_result['nfos'])
                movie_data = None
                if nfo_path:
                    movie_data = self.nfo_parser.parse_movie_nfo(Path(nfo_path))
                
                folder_art = self.art_extractor.extract_folder_art(scan_result['art'])
                movie_art = self.art_extractor.extract_art_for_video(
                    video_path,
                    scan_result['art'],
                    movie_data,
                    folder_art
                )
                
                media_item_id = self._create_movie_item(video_path, movie_data, movie_art)
                if media_item_id:
                    self._add_item_to_list_if_not_exists(list_id, media_item_id)
                    results['items_imported'] += 1
        
        # Process subdirectories recursively
        for subdir in scan_result['subdirs']:
            if self.cancel_requested:
                break
            
            subdir_result = self.scanner.scan_directory(subdir, recursive=True)
            subdir_classification = self.classifier.classify_folder(
                subdir,
                subdir_result['videos'],
                subdir_result['nfos'],
                subdir_result['subdirs']
            )
            
            # Recurse based on classification
            if subdir_classification['type'] == 'tv_show':
                show_results = self._import_tv_show(
                    subdir, subdir_result, subdir_classification,
                    parent_folder_id, progress_callback
                )
                results['folders_created'] += show_results.get('folders_created', 0)
                results['lists_created'] += show_results.get('lists_created', 0)
                results['items_imported'] += show_results.get('items_imported', 0)
            else:
                mixed_results = self._import_mixed_content(
                    subdir, subdir_result, subdir_classification,
                    parent_folder_id, progress_callback
                )
                results['folders_created'] += mixed_results.get('folders_created', 0)
                results['lists_created'] += mixed_results.get('lists_created', 0)
                results['items_imported'] += mixed_results.get('items_imported', 0)
        
        return results
    
    def _get_show_title(self, tvshow_data: Optional[Dict], show_path: str) -> str:
        """Get TV show title from NFO data or folder name"""
        if tvshow_data and 'title' in tvshow_data:
            return tvshow_data['title']
        return os.path.basename(show_path)
    
    def _create_or_get_folder(
        self,
        name: str,
        parent_id: Optional[int],
        art_data: Optional[Dict] = None
    ) -> int:
        """Create or get existing folder"""
        # Check if folder exists
        conn = self.connection_manager.get_connection()
        
        if parent_id is None:
            cursor = conn.execute(
                "SELECT id FROM folders WHERE name = ? AND parent_id IS NULL",
                (name,)
            )
        else:
            cursor = conn.execute(
                "SELECT id FROM folders WHERE name = ? AND parent_id = ?",
                (name, parent_id)
            )
        
        row = cursor.fetchone()
        
        if row:
            return row[0]
        
        # Create new folder
        cursor = conn.execute(
            "INSERT INTO folders (name, parent_id, created_at) VALUES (?, ?, ?)",
            (name, parent_id, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid
    
    def _create_or_get_list(self, name: str, folder_id: Optional[int]) -> int:
        """Create or get existing list"""
        # Check if list exists
        conn = self.connection_manager.get_connection()
        
        if folder_id is None:
            cursor = conn.execute(
                "SELECT id FROM lists WHERE name = ? AND folder_id IS NULL",
                (name,)
            )
        else:
            cursor = conn.execute(
                "SELECT id FROM lists WHERE name = ? AND folder_id = ?",
                (name, folder_id)
            )
        
        row = cursor.fetchone()
        
        if row:
            return row[0]
        
        # Create new list
        cursor = conn.execute(
            "INSERT INTO lists (name, folder_id, created_at) VALUES (?, ?, ?)",
            (name, folder_id, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid
    
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
        
        # Build media item data
        item_data = {
            'media_type': 'episode',
            'play': video_path,
            'file_path': video_path,
            'art': json.dumps(art) if art else None,
            'title': episode_data.get('title'),
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
        
        # Build media item data
        item_data = {
            'media_type': 'movie',
            'play': video_path,
            'file_path': video_path,
            'art': json.dumps(art) if art else None,
            'title': movie_data.get('title'),
            'year': movie_data.get('year'),
            'plot': movie_data.get('plot'),
            'rating': movie_data.get('rating'),
            'imdbnumber': movie_data.get('imdbnumber'),
            'tmdb_id': movie_data.get('tmdb_id'),
            'duration': movie_data.get('runtime'),
            'mpaa': movie_data.get('mpaa'),
            'genre': json.dumps(movie_data.get('genre')) if movie_data.get('genre') else None,
            'director': json.dumps(movie_data.get('director')) if movie_data.get('director') else None,
            'studio': json.dumps(movie_data.get('studio')) if movie_data.get('studio') else None,
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
        return cursor.lastrowid
    
    def _update_import_source(self, import_source_id: int):
        """Update import source last_scan timestamp"""
        conn = self.connection_manager.get_connection()
        conn.execute(
            "UPDATE import_sources SET last_scan = ? WHERE id = ?",
            (datetime.now().isoformat(), import_source_id)
        )
        conn.commit()
    
    def _add_item_to_list_if_not_exists(self, list_id: int, media_item_id: int):
        """Add item to list only if not already present"""
        conn = self.connection_manager.get_connection()
        
        # Check if already exists
        cursor = conn.execute(
            "SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?",
            (list_id, media_item_id)
        )
        
        if not cursor.fetchone():
            # Not exists, add it
            self.storage.add_item_to_list(list_id, media_item_id)
    
    def cancel(self):
        """Request cancellation of current import"""
        self.cancel_requested = True
