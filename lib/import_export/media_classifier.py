"""
LibraryGenie - Media Classifier
Determines folder type (TV show, movie, mixed) based on contents
"""

import os
import re
from typing import Any, Dict, List, Optional, Literal
from lib.utils.kodi_log import get_kodi_logger

FolderType = Literal['tv_show', 'movie', 'season', 'mixed', 'single_video']


class MediaClassifier:
    """Classifies folders based on their media content"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.media_classifier')
        self.season_pattern = re.compile(r'season\s*(\d+)', re.IGNORECASE)
        self.episode_pattern = re.compile(r'[sS](\d{1,2})[eE](\d{1,2})')
    
    def classify_folder(
        self,
        folder_path: str,
        videos: List[str],
        nfos: List[str],
        subdirs: List[str],
        disc_structure: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Classify a folder based on its contents
        
        Args:
            folder_path: Path to the folder being classified
            videos: List of video file paths in folder
            nfos: List of NFO file paths in folder
            subdirs: List of subdirectory paths
            disc_structure: Disc structure info if present
        
        Returns:
            Dictionary with 'type' and additional classification metadata
        """
        folder_name = os.path.basename(folder_path)
        
        # Check for disc structure
        if disc_structure:
            return {
                'type': 'single_video',
                'is_disc': True,
                'disc_info': disc_structure
            }
        
        # Check for tvshow.nfo
        has_tvshow_nfo = self._has_tvshow_nfo(nfos)
        
        # Check if folder name indicates a season
        is_season_folder = self._is_season_folder(folder_name)
        
        # Check for episode naming patterns in videos
        has_episode_files = self._has_episode_naming(videos)
        
        # Check if subdirectories indicate seasons (TV show indicator)
        has_season_subdirs = self._has_season_subdirectories(subdirs)
        
        # Count main videos (excluding extras, samples, etc.)
        main_video_count = len(videos)
        
        # Classification logic
        if has_tvshow_nfo or is_season_folder or has_episode_files or has_season_subdirs:
            if is_season_folder:
                return {
                    'type': 'season',
                    'season_number': self._extract_season_number(folder_name),
                    'has_tvshow_nfo': has_tvshow_nfo,
                    'video_count': main_video_count
                }
            else:
                return {
                    'type': 'tv_show',
                    'has_tvshow_nfo': has_tvshow_nfo,
                    'has_episode_files': has_episode_files,
                    'video_count': main_video_count,
                    'subdir_count': len(subdirs)
                }
        
        # Single video folder (movie or standalone)
        elif main_video_count == 1:
            return {
                'type': 'single_video',
                'is_disc': False,
                'video_path': videos[0]
            }
        
        # Multiple videos without TV show indicators
        elif main_video_count > 1:
            return {
                'type': 'mixed',
                'video_count': main_video_count,
                'subdir_count': len(subdirs)
            }
        
        # No videos, just subdirectories
        else:
            return {
                'type': 'mixed',
                'video_count': 0,
                'subdir_count': len(subdirs)
            }
    
    def _has_tvshow_nfo(self, nfos: List[str]) -> bool:
        """Check if tvshow.nfo exists in NFO list"""
        for nfo_path in nfos:
            nfo_name = os.path.basename(nfo_path).lower()
            if nfo_name == 'tvshow.nfo':
                return True
        return False
    
    def _is_season_folder(self, folder_name: str) -> bool:
        """Check if folder name indicates a season"""
        return bool(self.season_pattern.search(folder_name))
    
    def _has_season_subdirectories(self, subdirs: List[str]) -> bool:
        """Check if subdirectories indicate season folders (TV show structure)"""
        if not subdirs:
            return False
        
        season_count = 0
        for subdir_path in subdirs:
            subdir_name = os.path.basename(subdir_path)
            if self._is_season_folder(subdir_name):
                season_count += 1
        
        # Consider it a TV show if at least one season folder exists
        return season_count > 0
    
    def _extract_season_number(self, folder_name: str) -> Optional[int]:
        """Extract season number from folder name"""
        match = self.season_pattern.search(folder_name)
        if match:
            return int(match.group(1))
        return None
    
    def _has_episode_naming(self, videos: List[str]) -> bool:
        """Check if videos follow episode naming pattern (SxxExx)"""
        if not videos:
            return False
        
        episode_count = 0
        for video_path in videos:
            video_name = os.path.basename(video_path)
            if self.episode_pattern.search(video_name):
                episode_count += 1
        
        # Consider it episode naming if at least 50% of videos match
        return episode_count > 0 and episode_count >= len(videos) * 0.5
    
    def classify_subdirectory(
        self,
        parent_type: FolderType,
        subdir_name: str,
        subdir_videos: List[str]
    ) -> FolderType:
        """
        Classify a subdirectory based on parent context
        
        Args:
            parent_type: Type of parent folder
            subdir_name: Name of subdirectory
            subdir_videos: List of videos in subdirectory
        
        Returns:
            Folder type for the subdirectory
        """
        # If parent is TV show, subdirs are likely seasons
        if parent_type == 'tv_show':
            if self._is_season_folder(subdir_name):
                return 'season'
            elif self._has_episode_naming(subdir_videos):
                return 'season'
        
        # Single video folder
        if len(subdir_videos) == 1:
            return 'single_video'
        
        # Multiple videos
        if len(subdir_videos) > 1:
            if self._has_episode_naming(subdir_videos):
                return 'season'
            return 'mixed'
        
        return 'mixed'
