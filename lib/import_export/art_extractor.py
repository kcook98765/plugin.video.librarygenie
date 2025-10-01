"""
LibraryGenie - Art Extractor
Extracts artwork from sidecar files and NFO metadata
"""

import os
from typing import Dict, List, Optional
from lib.utils.kodi_log import get_kodi_logger

# Supported art file extensions
ART_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tbn']

# Art types in precedence order
ART_TYPES = ['poster', 'fanart', 'thumb', 'banner', 'clearart', 'clearlogo', 'landscape', 'discart', 'characterart']


class ArtExtractor:
    """Extracts and manages artwork for media items"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.art_extractor')
    
    def extract_art_for_video(
        self,
        video_path: str,
        art_files: List[str],
        nfo_data: Optional[Dict] = None,
        folder_art: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Extract artwork for a video file
        
        Args:
            video_path: Path to the video file
            art_files: List of art file paths in the same directory
            nfo_data: Parsed NFO data (may contain art URLs)
            folder_art: Folder-level artwork dict
        
        Returns:
            Dictionary mapping art type to file path/URL
        """
        art = {}
        video_basename = os.path.splitext(os.path.basename(video_path))[0]
        
        # 1. Check for file-specific sidecar art (highest priority)
        for art_type in ART_TYPES:
            file_art = self._find_file_art(video_basename, art_type, art_files)
            if file_art:
                art[art_type] = file_art
        
        # 2. Extract art URLs from NFO data
        if nfo_data:
            nfo_art = self._extract_nfo_art(nfo_data)
            for art_type, art_url in nfo_art.items():
                if art_type not in art:
                    art[art_type] = art_url
        
        # 3. Fall back to folder-level art
        if folder_art:
            for art_type, art_path in folder_art.items():
                if art_type not in art:
                    art[art_type] = art_path
        
        # 4. Special fallback: if poster missing, use thumb
        if 'poster' not in art and 'thumb' in art:
            art['poster'] = art['thumb']
        
        return art
    
    def extract_folder_art(self, art_files: List[str]) -> Dict[str, str]:
        """
        Extract folder-level artwork
        
        Args:
            art_files: List of art file paths in the folder
        
        Returns:
            Dictionary mapping art type to file path
        """
        folder_art = {}
        
        for art_type in ART_TYPES:
            # Look for standard folder art (poster.jpg, fanart.png, etc.)
            for art_file in art_files:
                art_filename = os.path.basename(art_file).lower()
                art_name, art_ext = os.path.splitext(art_filename)
                
                if art_name == art_type and art_ext in ART_EXTENSIONS:
                    folder_art[art_type] = art_file
                    break
        
        # Check for legacy folder.jpg as poster
        if 'poster' not in folder_art:
            for art_file in art_files:
                if os.path.basename(art_file).lower() == 'folder.jpg':
                    folder_art['poster'] = art_file
                    break
        
        return folder_art
    
    def extract_show_art(
        self,
        art_files: List[str],
        tvshow_nfo_data: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Extract TV show artwork
        
        Args:
            art_files: List of art file paths in the show folder
            tvshow_nfo_data: Parsed tvshow.nfo data
        
        Returns:
            Dictionary mapping art type to file path/URL
        """
        show_art = self.extract_folder_art(art_files)
        
        # Add NFO art if available
        if tvshow_nfo_data:
            nfo_art = self._extract_nfo_art(tvshow_nfo_data)
            for art_type, art_url in nfo_art.items():
                if art_type not in show_art:
                    show_art[art_type] = art_url
        
        return show_art
    
    def _find_file_art(
        self,
        video_basename: str,
        art_type: str,
        art_files: List[str]
    ) -> Optional[str]:
        """Find file-specific art (e.g., video-poster.jpg)"""
        for art_file in art_files:
            art_filename = os.path.basename(art_file).lower()
            expected_pattern = f"{video_basename.lower()}-{art_type}"
            
            if art_filename.startswith(expected_pattern):
                art_ext = os.path.splitext(art_filename)[1]
                if art_ext in ART_EXTENSIONS:
                    return art_file
        
        return None
    
    def _extract_nfo_art(self, nfo_data: Dict) -> Dict[str, str]:
        """Extract art URLs from NFO data"""
        art = {}
        
        # Handle <thumb> elements with aspect attributes
        # <thumb aspect="poster">url</thumb> -> art['poster'] = url
        if 'thumb' in nfo_data:
            thumb_art = self._extract_aspect_art(nfo_data['thumb'])
            art.update(thumb_art)
        
        # Handle direct art elements (poster, banner, etc. without aspect)
        direct_art_keys = ['poster', 'banner', 'clearart', 'clearlogo', 'landscape']
        for art_key in direct_art_keys:
            if art_key in nfo_data and art_key not in art:
                art_url = self._extract_art_url(nfo_data[art_key], art_key)
                if art_url:
                    art[art_key] = art_url
        
        # Handle fanart structure: <fanart><thumb>url</thumb></fanart>
        if 'fanart' in nfo_data:
            fanart_data = nfo_data['fanart']
            if isinstance(fanart_data, dict):
                # Look for nested thumb elements
                if 'thumb' in fanart_data:
                    fanart_url = self._extract_art_url(fanart_data['thumb'], 'fanart')
                    if fanart_url and 'fanart' not in art:
                        art['fanart'] = fanart_url
            elif isinstance(fanart_data, str) and fanart_data.strip():
                if 'fanart' not in art:
                    art['fanart'] = fanart_data.strip()
        
        return art
    
    def _extract_aspect_art(self, thumb_value) -> Dict[str, str]:
        """
        Extract art from <thumb> elements with aspect attributes
        
        Handles:
        - <thumb aspect="poster">url</thumb>
        - Multiple thumbs with different aspects
        """
        art = {}
        
        # Aspect mapping to canonical art types
        aspect_map = {
            'poster': 'poster',
            'fanart': 'fanart',
            'thumb': 'thumb',
            'banner': 'banner',
            'clearart': 'clearart',
            'clearlogo': 'clearlogo',
            'landscape': 'landscape',
            'discart': 'discart',
            'characterart': 'characterart'
        }
        
        # List of thumbs
        if isinstance(thumb_value, list):
            for item in thumb_value:
                if isinstance(item, dict):
                    raw_aspect = item.get('@aspect', 'thumb').lower()
                    aspect = aspect_map.get(raw_aspect, raw_aspect)
                    url = item.get('#text', '')
                    if url and url.strip():
                        # Only store if it's a recognized art type
                        if aspect in ART_TYPES or aspect == 'thumb':
                            art[aspect] = url.strip()
                elif isinstance(item, str) and item.strip():
                    # No aspect, use as thumb
                    if 'thumb' not in art:
                        art['thumb'] = item.strip()
        
        # Single thumb dict
        elif isinstance(thumb_value, dict):
            raw_aspect = thumb_value.get('@aspect', 'thumb').lower()
            aspect = aspect_map.get(raw_aspect, raw_aspect)
            url = thumb_value.get('#text', '')
            if url and url.strip():
                # Only store if it's a recognized art type
                if aspect in ART_TYPES or aspect == 'thumb':
                    art[aspect] = url.strip()
        
        # Plain string
        elif isinstance(thumb_value, str) and thumb_value.strip():
            art['thumb'] = thumb_value.strip()
        
        return art
    
    def _extract_art_url(self, art_value, art_type: str) -> Optional[str]:
        """
        Extract art URL from various NFO formats
        
        Handles:
        - Plain string: "url"
        - Dict with #text: {"#text": "url", "@aspect": "poster"}
        - List of strings: ["url1", "url2"]
        - List of dicts: [{"#text": "url1", "@aspect": "poster"}, ...]
        """
        # String value
        if isinstance(art_value, str):
            return art_value.strip() if art_value.strip() else None
        
        # Dict with #text
        if isinstance(art_value, dict):
            if '#text' in art_value:
                text = art_value['#text']
                if isinstance(text, str) and text.strip():
                    return text.strip()
            # Dict might have direct URL as value
            for key, value in art_value.items():
                if isinstance(value, str) and value.strip() and not key.startswith('@'):
                    return value.strip()
        
        # List of values
        if isinstance(art_value, list) and art_value:
            # Try to find the best match based on aspect attribute
            for item in art_value:
                if isinstance(item, dict):
                    aspect = item.get('@aspect', '')
                    # Prefer poster aspect for thumb, fanart for fanart, etc.
                    if aspect == art_type or (art_type == 'poster' and aspect == 'poster'):
                        if '#text' in item and item['#text'].strip():
                            return item['#text'].strip()
            
            # No aspect match, take first available
            first_item = art_value[0]
            if isinstance(first_item, str) and first_item.strip():
                return first_item.strip()
            elif isinstance(first_item, dict) and '#text' in first_item:
                text = first_item['#text']
                if isinstance(text, str) and text.strip():
                    return text.strip()
        
        return None
    
    def merge_art(
        self,
        primary_art: Dict[str, str],
        fallback_art: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Merge two art dictionaries with primary taking precedence
        
        Args:
            primary_art: Primary art dictionary
            fallback_art: Fallback art dictionary
        
        Returns:
            Merged art dictionary
        """
        merged = fallback_art.copy()
        merged.update(primary_art)
        return merged
