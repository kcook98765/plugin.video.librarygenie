#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - File System Scanner
Scans directories for media files, NFO files, and artwork
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, unquote
from lib.utils.kodi_log import get_kodi_logger

try:
    import xbmc
    import xbmcvfs
except ImportError:
    xbmc = None
    xbmcvfs = None


# Constants for file identification
VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm',
    '.mpg', '.mpeg', '.m2ts', '.ts', '.vob', '.3gp', '.ogv', '.divx'
}

NFO_EXTENSION = '.nfo'

ART_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tbn', '.gif'}

# Ignore patterns (hardcoded as per requirements)
IGNORE_PATTERNS = [
    'sample', 'trailer', 'extras', 'deleted', 'behind the scenes',
    '.actors', 'featurette', 'interview', 'scene'
]

IGNORE_FOLDERS = {
    'subs', 'subtitles', 'extras', 'deleted scenes', 'behind the scenes',
    '.actors', 'featurettes', 'interviews'
}

IGNORE_EXTENSIONS = {'.srt', '.sub', '.idx', '.ssa', '.ass', '.smi'}

# Disc structures
DISC_FOLDERS = {'VIDEO_TS', 'BDMV'}
DISC_EXTENSIONS = {'.iso', '.img'}


class FileScanner:
    """Scans file systems for media, NFO, and art files"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.file_scanner')
        self._dir_cache = {}  # Cache directory listings within a scan
    
    def scan_directory(self, source_url: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Scan a directory and return structured information about its contents
        
        Args:
            source_url: Kodi URL or filesystem path
            recursive: Whether to scan subdirectories
            
        Returns:
            Dict with files, folders, and metadata
        """
        self.logger.info("Scanning directory: %s", source_url)
        self._dir_cache.clear()  # Clear cache for new scan
        
        # Determine scan method based on URL
        if self._is_local_path(source_url):
            return self._scan_local_directory(source_url, recursive)
        else:
            return self._scan_vfs_directory(source_url, recursive)
    
    def _is_local_path(self, url: str) -> bool:
        """Check if URL is a local filesystem path"""
        # Only treat true local paths as local - everything else goes through VFS
        if url.startswith('/') or (len(url) > 2 and url[1:3] == ':\\'):
            # But check if it's actually a special:// or other Kodi protocol
            if url.startswith('special://'):
                return False
            return True
        
        # All network paths (SMB, NFS, etc.) and Kodi protocols use VFS
        return False
    
    def _scan_local_directory(self, path_str: str, recursive: bool) -> Dict[str, Any]:
        """Scan local filesystem directory"""
        result = {
            'videos': [],
            'nfos': [],
            'art': [],
            'subdirs': [],
            'disc_structure': None
        }
        
        try:
            # Convert SMB/NFS paths if needed
            local_path = self._convert_to_local_path(path_str)
            path = Path(local_path)
            
            if not path.exists():
                self.logger.warning("Path does not exist: %s", path)
                return result
            
            # Cache directory listing with string paths for consistency
            entries = list(path.iterdir())
            self._dir_cache[str(path)] = [str(e) for e in entries]
            
            # Check for disc structure first
            disc_info = self._check_disc_structure(entries)
            if disc_info:
                result['disc_structure'] = disc_info
                return result
            
            # Scan files and folders
            for entry in entries:
                entry_name = entry.name.lower()
                
                # Skip ignored items
                if self._should_ignore(entry_name):
                    continue
                
                if entry.is_file():
                    ext = entry.suffix.lower()
                    
                    if ext in VIDEO_EXTENSIONS:
                        result['videos'].append(str(entry))
                    elif ext == NFO_EXTENSION:
                        result['nfos'].append(str(entry))
                    elif ext in ART_EXTENSIONS:
                        result['art'].append(str(entry))
                
                elif entry.is_dir():
                    # Check if folder should be ignored
                    if entry_name not in IGNORE_FOLDERS:
                        result['subdirs'].append(str(entry))
                        if recursive:
                            # Recursively scan subdirectory and merge results
                            subdir_result = self._scan_local_directory(str(entry), recursive=True)
                            result['videos'].extend(subdir_result['videos'])
                            result['nfos'].extend(subdir_result['nfos'])
                            result['art'].extend(subdir_result['art'])
                            result['subdirs'].extend(subdir_result['subdirs'])
            
        except Exception as e:
            self.logger.error("Error scanning local directory %s: %s", path_str, e)
        
        return result
    
    def _scan_vfs_directory(self, url: str, recursive: bool) -> Dict[str, Any]:
        """Scan directory using Kodi VFS (JSON-RPC Files.GetDirectory)"""
        result = {
            'videos': [],
            'nfos': [],
            'art': [],
            'subdirs': [],
            'disc_structure': None
        }
        
        if not xbmc:
            self.logger.error("Kodi xbmc module not available for VFS scanning")
            return result
        
        try:
            # Use Files.GetDirectory from JSON-RPC
            request = {
                "jsonrpc": "2.0",
                "method": "Files.GetDirectory",
                "params": {
                    "directory": url,
                    "media": "files",
                    "properties": ["file", "filetype", "mimetype"]
                },
                "id": 1
            }
            
            response_str = xbmc.executeJSONRPC(json.dumps(request))
            response_data = json.loads(response_str)
            
            if "error" in response_data:
                self.logger.error("JSON-RPC error for %s: %s", url, response_data['error'])
                return result
            
            response = response_data.get("result", {})
            if not response or 'files' not in response:
                self.logger.warning("No files returned for: %s", url)
                return result
            
            files = response['files']
            # Store paths as strings for consistency with local scanning
            file_paths = [f.get('file', '') for f in files]
            self._dir_cache[url] = file_paths
            
            # Check for disc structure (folders and image files)
            disc_found = None
            for file_info in files:
                file_label = file_info.get('label', '')
                file_type = file_info.get('filetype', 'file')
                
                # Check for disc folders (VIDEO_TS, BDMV) - normalize casing
                if file_type == 'directory' and file_label.upper() in DISC_FOLDERS:
                    disc_found = {
                        'type': 'folder',
                        'path': file_info.get('file', ''),
                        'name': file_label.upper()
                    }
                    break
                
                # Check for disc image files (.iso, .img)
                if file_type == 'file':
                    ext = os.path.splitext(file_label)[1].lower()
                    if ext in DISC_EXTENSIONS:
                        disc_found = {
                            'type': 'file',
                            'path': file_info.get('file', ''),
                            'name': file_label
                        }
                        break
            
            # If disc structure found, return it (but only after checking all entries)
            if disc_found:
                result['disc_structure'] = disc_found
                return result
            
            # Process files
            for file_info in files:
                file_label = file_info.get('label', '')
                file_path = file_info.get('file', '')
                file_type = file_info.get('filetype', 'file')
                mimetype = file_info.get('mimetype', '')
                
                # Skip ignored items
                if self._should_ignore(file_label.lower()):
                    continue
                
                if file_type == 'file':
                    ext = os.path.splitext(file_label)[1].lower()
                    
                    # Check if video
                    if ext in VIDEO_EXTENSIONS or (mimetype and mimetype.startswith('video/')):
                        result['videos'].append(file_path)
                    elif ext == NFO_EXTENSION:
                        result['nfos'].append(file_path)
                    elif ext in ART_EXTENSIONS:
                        result['art'].append(file_path)
                
                elif file_type == 'directory':
                    if file_label.lower() not in IGNORE_FOLDERS:
                        result['subdirs'].append(file_path)
                        if recursive:
                            # Recursively scan subdirectory and merge results
                            subdir_result = self._scan_vfs_directory(file_path, recursive=True)
                            result['videos'].extend(subdir_result['videos'])
                            result['nfos'].extend(subdir_result['nfos'])
                            result['art'].extend(subdir_result['art'])
                            result['subdirs'].extend(subdir_result['subdirs'])
            
        except Exception as e:
            self.logger.error("Error scanning VFS directory %s: %s", url, e)
        
        return result
    
    def _should_ignore(self, name: str) -> bool:
        """Check if file/folder should be ignored based on name"""
        name_lower = name.lower()
        
        # Check ignore patterns
        for pattern in IGNORE_PATTERNS:
            if pattern in name_lower:
                return True
        
        # Check file extension
        ext = os.path.splitext(name)[1].lower()
        if ext in IGNORE_EXTENSIONS:
            return True
        
        return False
    
    def _check_disc_structure(self, entries: List[Path]) -> Optional[Dict[str, str]]:
        """Check if directory contains disc structure"""
        for entry in entries:
            if entry.is_dir() and entry.name.upper() in DISC_FOLDERS:
                return {
                    'type': 'folder',
                    'name': entry.name.upper(),
                    'path': str(entry)
                }
            elif entry.is_file():
                ext = entry.suffix.lower()
                if ext in DISC_EXTENSIONS:
                    return {
                        'type': 'file',
                        'name': entry.name,
                        'path': str(entry)
                    }
        
        return None
    
    def _convert_to_local_path(self, url: str) -> str:
        """Convert Kodi URL to local filesystem path if possible"""
        # Remove protocol if present
        if url.startswith('smb://'):
            # Convert SMB to UNC path for Windows or mounted path for Linux
            # This is simplified - actual conversion may need platform-specific logic
            url = url.replace('smb://', '//')
        
        elif url.startswith('nfs://'):
            # NFS paths might be mounted locally
            # This is simplified - actual conversion may need platform-specific logic
            url = url.replace('nfs://', '/')
        
        # URL decode
        url = unquote(url)
        
        return url
    
    def find_matching_nfo(self, video_path: str, nfos: List[str]) -> Optional[str]:
        """Find NFO file matching a video file"""
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        
        for nfo_path in nfos:
            nfo_name = os.path.splitext(os.path.basename(nfo_path))[0]
            if nfo_name == video_name:
                return nfo_path
        
        return None
    
    def find_folder_nfo(self, folder_path: str, nfo_name: str = 'tvshow.nfo') -> Optional[str]:
        """Find specific NFO in folder (e.g., tvshow.nfo)"""
        # Get cached directory listing
        entries = self._dir_cache.get(folder_path, [])
        
        if not entries:
            # Try to scan if not cached
            result = self.scan_directory(folder_path, recursive=False)
            entries = result['nfos']
        
        for nfo_path in entries if isinstance(entries, list) else []:
            if isinstance(nfo_path, str):
                if os.path.basename(nfo_path).lower() == nfo_name.lower():
                    return nfo_path
            elif hasattr(nfo_path, 'name'):
                if nfo_path.name.lower() == nfo_name.lower():
                    return str(nfo_path)
        
        return None
    
    def find_art_for_file(self, file_path: str, art_type: str, art_files: List[str]) -> Optional[str]:
        """Find art file for specific video file"""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Look for <basename>-<arttype>.*
        for art_path in art_files:
            art_name = os.path.basename(art_path)
            art_stem = os.path.splitext(art_name)[0]
            
            if art_stem.lower() == f"{base_name.lower()}-{art_type.lower()}":
                return art_path
        
        return None
    
    def find_folder_art(self, folder_path: str, art_type: str) -> Optional[str]:
        """Find folder-level art (poster.jpg, fanart.jpg, etc.)"""
        # Get cached directory listing
        entries = self._dir_cache.get(folder_path, [])
        
        if not entries:
            result = self.scan_directory(folder_path, recursive=False)
            entries = result['art']
        
        # Look for art type
        for art_path in entries if isinstance(entries, list) else []:
            art_name = os.path.basename(str(art_path)).lower()
            art_stem = os.path.splitext(art_name)[0]
            
            if art_stem == art_type.lower():
                return str(art_path)
            # Also check for folder.jpg as generic
            if art_type == 'poster' and art_stem == 'folder':
                return str(art_path)
        
        return None
    
    def get_cached_listing(self, path: str) -> List[Any]:
        """Get cached directory listing"""
        return self._dir_cache.get(path, [])


def get_file_scanner() -> FileScanner:
    """Get file scanner instance"""
    return FileScanner()
