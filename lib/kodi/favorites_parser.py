#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 4 Enhanced Favorites Parser
Rock-solid parsing with tolerant XML handling, deterministic path normalization,
and comprehensive classification system
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from urllib.parse import unquote

import xbmcvfs

from ..utils.kodi_log import get_kodi_logger


class Phase4FavoritesParser:
    """Phase 4: Rock-solid favorites parser with robust XML handling and path normalization"""
    
    def __init__(self, test_file_path: Optional[str] = None):
        self.logger = get_kodi_logger('lib.kodi.favorites_parser')
        self.test_file_path = test_file_path
    
    def find_favorites_file(self) -> Optional[str]:
        """Find Kodi favourites.xml file using special://profile/ consistently"""
        try:
            # If test file path is provided, use it directly
            if self.test_file_path:
                if os.path.isfile(self.test_file_path):
                    self.logger.info("Using test favorites file: %s", self.test_file_path)
                    return self.test_file_path
                else:
                    self.logger.warning("Test favorites file not found: %s", self.test_file_path)
                    return None
            
            profile_path = xbmcvfs.translatePath('special://profile/')
            favorites_path = os.path.join(profile_path, 'favourites.xml')
            
            if os.path.isfile(favorites_path):
                self.logger.info("Found favorites file via special://profile/: %s", favorites_path)
                return favorites_path
            else:
                self.logger.info("Favorites file not found at special://profile/favourites.xml")
                return None
            
            # Fallback paths for development/testing outside Kodi
            fallback_paths = []
            home_dir = os.path.expanduser('~')
            
            # Development test path
            test_path = os.path.join('tests', 'data', 'favourites.xml')
            if os.path.exists(test_path):
                fallback_paths.append(test_path)
            
            # Platform-specific fallback paths (for development)
            fallback_paths.extend([
                # Windows
                os.path.join(home_dir, 'AppData', 'Roaming', 'Kodi', 'userdata', 'favourites.xml'),
                # Linux
                os.path.join(home_dir, '.kodi', 'userdata', 'favourites.xml'),
                os.path.join(home_dir, '.local', 'share', 'kodi', 'userdata', 'favourites.xml'),
                # macOS
                os.path.join(home_dir, 'Library', 'Application Support', 'Kodi', 'userdata', 'favourites.xml'),
            ])
            
            # Try fallback paths
            for path in fallback_paths:
                if path and os.path.isfile(path):
                    self.logger.info("Found favorites file (fallback): %s", path)
                    return path
            
            self.logger.info("No favorites file found")
            return None
            
        except Exception as e:
            self.logger.error("Error locating favorites file: %s", e)
            return None
    
    def get_file_modified_time(self, file_path: str) -> Optional[str]:
        """Get file modification time as ISO string"""
        try:
            if os.path.isfile(file_path):
                mtime = os.path.getmtime(file_path)
                from datetime import datetime
                return datetime.fromtimestamp(mtime).isoformat()
            return None
        except Exception as e:
            self.logger.error("Error getting file modification time: %s", e)
            return None
    
    def parse_favorites_file(self, file_path: str) -> List[Dict]:
        """Parse favourites.xml with tolerant XML handling"""
        favorites = []
        
        try:
            if not os.path.isfile(file_path):
                self.logger.info("Favorites file not found: %s", file_path)
                return favorites
            
            # Phase 4: Tolerant XML parsing
            favorites = self._parse_xml_tolerantly(file_path)
            
            self.logger.info("Parsed %s favorites from %s", len(favorites), file_path)
            return favorites
            
        except Exception as e:
            self.logger.error("Error parsing favorites file: %s", e)
            return []
    
    def _parse_xml_tolerantly(self, file_path: str) -> List[Dict]:
        """Parse XML with tolerance for whitespace, CDATA, and unexpected nodes"""
        favorites = []
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Handle empty files
            if not content.strip():
                self.logger.debug("Favorites file is empty")
                return favorites
            
            # Parse with error handling
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                self.logger.warning("XML parse error: %s", e)
                # Try to recover by cleaning the content
                content = self._clean_xml_content(content)
                try:
                    root = ET.fromstring(content)
                    self.logger.debug("XML recovered after cleaning")
                except ET.ParseError as e2:
                    self.logger.error("XML unrecoverable: %s", e2)
                    return favorites
            
            # Handle different root tag variations
            if root.tag not in ['favourites', 'favorites']:
                self.logger.warning("Unexpected root tag: %s (expected 'favourites' or 'favorites')", root.tag)
                # Continue anyway - maybe it's a variant
            
            # Process each favorite entry with per-row error handling
            for i, element in enumerate(root):
                try:
                    favorite = self._parse_favorite_element(element)
                    if favorite:
                        favorites.append(favorite)
                except Exception as e:
                    self.logger.debug("Failed to parse favorite element %s: %s", i, e)
                    continue  # Skip this row, continue with others
            
            return favorites
            
        except Exception as e:
            self.logger.error("Error in tolerant XML parsing: %s", e)
            return []
    
    def _clean_xml_content(self, content: str) -> str:
        """Clean XML content to handle common formatting issues"""
        try:
            # Remove null bytes
            content = content.replace('\x00', '')
            
            # Ensure proper XML declaration if missing
            if not content.strip().startswith('<?xml'):
                content = '<?xml version="1.0" encoding="utf-8"?>\n' + content
            
            # Handle common encoding issues
            content = content.replace('&', '&amp;')
            content = content.replace('&amp;amp;', '&amp;')  # Fix double encoding
            
            return content
            
        except Exception as e:
            self.logger.error("Error cleaning XML content: %s", e)
            return content
    
    def _parse_favorite_element(self, element: ET.Element) -> Optional[Dict]:
        """Parse individual favorite element with robust extraction"""
        try:
            # Handle different element names
            if element.tag not in ['favourite', 'favorite']:
                self.logger.debug("Skipping element with unexpected tag: %s", element.tag)
                return None
            
            # Extract display label
            name = element.get('name', '').strip()
            if not name:
                # Try element text as fallback
                name = (element.text or '').strip()
            
            if not name:
                self.logger.debug("Skipping favorite with no name")
                return None
            
            # Extract target (URL or command)
            target = ''
            
            # First try element text (most common)
            if element.text:
                target = element.text.strip()
            
            # If no text, try CDATA or other child elements
            if not target:
                # Handle CDATA sections
                for child in element:
                    if child.text:
                        target = child.text.strip()
                        break
            
            # Extract thumb reference if present
            thumb_ref = ''
            thumb_element = element.find('thumb')
            if thumb_element is not None and thumb_element.text:
                thumb_ref = thumb_element.text.strip()
            
            if not target:
                self.logger.debug("Skipping favorite '%s' with no target", name)
                return None
            
            # Phase 4: Classify and normalize
            classification = self._classify_favorite_target(target)
            normalized_key = self._create_normalized_key(target, classification)
            
            self.logger.debug("Parsed favorite '%s': target='%s', classification='%s', normalized='%s'", name, target, classification, normalized_key)
            
            return {
                'name': name,
                'target_raw': target,
                'target_classification': classification,
                'normalized_key': normalized_key,
                'thumb_ref': thumb_ref
            }
            
        except Exception as e:
            self.logger.debug("Error parsing favorite element: %s", e)
            return None
    
    def _classify_favorite_target(self, target: str) -> str:
        """Classify favorite by target scheme - Phase 4 comprehensive classification"""
        try:
            target_lower = target.lower().strip()
            self.logger.debug("Classifying target: '%s'", target)
            
            # First check for PlayMedia commands and extract the path
            extracted_path = self._extract_path_from_command(target)
            if extracted_path and extracted_path != target:
                self.logger.info("Extracted path from command: '%s'", extracted_path)
                # Recursively classify the extracted path
                return self._classify_favorite_target(extracted_path)
            
            # Check for plugin URLs (both direct and in commands)
            if 'plugin://' in target_lower:
                self.logger.debug("Classified as 'plugin_or_script' (contains plugin://)")
                return 'plugin_or_script'
            
            # File/URL schemes we can attempt to map
            mappable_schemes = [
                'file://', 'smb://', 'nfs://', 'udf://', 
                'iso9660://', 'zip://', 'rar://', 'stack://'
            ]
            
            for scheme in mappable_schemes:
                if target_lower.startswith(scheme):
                    self.logger.debug("Classified as 'mappable_file' (scheme: %s)", scheme)
                    return 'mappable_file'
            
            # Kodi video database references
            if target_lower.startswith('videodb://'):
                self.logger.debug("Classified as 'videodb'")
                return 'videodb'
            
            # Unsupported for mapping (skip mapping, but may display)
            unsupported_schemes = [
                'script://', 'addon:'
            ]
            
            for scheme in unsupported_schemes:
                if target_lower.startswith(scheme):
                    self.logger.debug("Classified as 'plugin_or_script' (scheme: %s)", scheme)
                    return 'plugin_or_script'
            
            # Kodi built-in commands
            builtin_patterns = [
                'activatewindow(', 'runscript(', 'runplugin(',
                'playlistplayer.', 'player.', 'system.'
            ]
            
            for pattern in builtin_patterns:
                if pattern in target_lower:
                    self.logger.debug("Classified as 'builtin_command' (pattern: %s)", pattern)
                    return 'builtin_command'
            
            # Plain file paths (no scheme)
            if self._looks_like_file_path(target):
                self.logger.debug("Classified as 'mappable_file' (plain file path)")
                return 'mappable_file'
            
            self.logger.debug("Classified as 'unknown'")
            return 'unknown'
            
        except Exception as e:
            self.logger.debug("Error classifying target '%s': %s", target, e)
            return 'unknown'
    
    def _looks_like_file_path(self, target: str) -> bool:
        """Check if target looks like a plain file path"""
        try:
            # Common video file extensions
            video_extensions = [
                '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', 
                '.m4v', '.ts', '.m2ts', '.webm', '.ogv', '.3gp'
            ]
            
            target_lower = target.lower()
            
            # Has video extension
            if any(target_lower.endswith(ext) for ext in video_extensions):
                return True
            
            # Looks like Windows path
            if re.match(r'^[A-Za-z]:[\\\/]', target):
                return True
            
            # Looks like Unix absolute path
            if target.startswith('/'):
                return True
            
            # Contains path separators and looks file-like
            if ('/' in target or '\\' in target) and '.' in target:
                return True
            
            return False
            
        except Exception:
            return False
    
    def _extract_path_from_command(self, target: str) -> str:
        """Extract file path from Kodi commands like PlayMedia()"""
        try:
            target_stripped = target.strip()
            self.logger.debug("Extracting path from command: '%s'", target_stripped)
            
            # Handle PlayMedia("path", options)
            playmedia_match = re.match(r'PlayMedia\s*\(\s*"([^"]+)"(?:,.*?)?\s*\)', target_stripped, re.IGNORECASE)
            if playmedia_match:
                extracted = playmedia_match.group(1)
                self.logger.info("Extracted from PlayMedia: '%s'", extracted)
                return extracted
            
            # Handle ActivateWindow commands that might contain paths
            activatewindow_match = re.match(r'ActivateWindow\s*\([^,]+,\s*"([^"]+)"(?:,.*?)?\s*\)', target_stripped, re.IGNORECASE)
            if activatewindow_match:
                extracted = activatewindow_match.group(1)
                self.logger.info("Extracted from ActivateWindow: '%s'", extracted)
                return extracted
            
            # If no command wrapper found, return original
            self.logger.debug("No command wrapper found, using original target")
            return target
            
        except Exception as e:
            self.logger.warning("Error extracting path from command '%s': %s", target, e)
            return target

    def _create_normalized_key(self, target: str, classification: str) -> str:
        """Create deterministic canonical key for mapping and uniqueness"""
        try:
            # First extract the actual path from any command wrappers
            extracted_path = self._extract_path_from_command(target)
            self.logger.debug("Working with extracted path: '%s'", extracted_path)
            
            if classification == 'videodb':
                normalized = self._normalize_videodb_key(extracted_path)
                self.logger.debug("Normalized videodb key: '%s' -> '%s'", extracted_path, normalized)
                return normalized
            elif classification in ['mappable_file']:
                normalized = self._normalize_file_path_key(extracted_path)
                self.logger.debug("Normalized file path key: '%s' -> '%s'", extracted_path, normalized)
                return normalized
            else:
                # For non-mappable items, use a simple normalized form
                normalized = target.lower().strip()
                self.logger.debug("Simple normalized key: '%s' -> '%s'", target, normalized)
                return normalized
                
        except Exception as e:
            self.logger.debug("Error creating normalized key for '%s': %s", target, e)
            return target.lower().strip()
    
    def _normalize_videodb_key(self, target: str) -> str:
        """Normalize videodb:// URLs to extract movie dbid"""
        try:
            # Pattern: videodb://movies/titles/<id>...
            match = re.search(r'videodb://movies/titles/(\d+)', target.lower())
            if match:
                return f"videodb_movie_{match.group(1)}"
            
            # Fallback: just use the full videodb URL normalized
            return target.lower().replace(' ', '').replace('\t', '')
            
        except Exception:
            return target.lower()
    
    def _normalize_file_path_key(self, target: str) -> str:
        """Normalize file paths for deterministic canonical keys"""
        try:
            # Start with the raw target
            key = target.strip()
            
            # Extract and normalize scheme
            scheme = ''
            path_part = key
            
            # Handle schemes
            for scheme_prefix in ['file://', 'smb://', 'nfs://', 'udf://', 
                                'iso9660://', 'zip://', 'rar://', 'stack://']:
                if key.lower().startswith(scheme_prefix):
                    scheme = scheme_prefix.lower()
                    path_part = key[len(scheme_prefix):]
                    break
            
            # Handle SMB credentials - strip from key but preserve host/share/path
            if scheme == 'smb://':
                # Pattern: smb://user:pass@host/share/path -> smb://host/share/path
                match = re.match(r'^([^@]+@)?(.+)$', path_part)
                if match and match.group(1):  # Has credentials
                    path_part = match.group(2)  # Use part after @
            
            # Handle stack:// - normalize first component as key
            if scheme == 'stack://':
                # Pattern: stack://file1 , file2 , file3
                first_file = path_part.split(' ,')[0].strip()
                if first_file:
                    # Recursively normalize the first file
                    return self._normalize_file_path_key(first_file)
            
            # Handle archive paths (zip://, rar://)
            if scheme in ['zip://', 'rar://']:
                # Pattern: zip://archive.zip/inner/path
                parts = path_part.split('/', 1)
                if len(parts) == 2:
                    archive_path, inner_path = parts
                    # Normalize both parts
                    archive_normalized = self._normalize_path_component(archive_path)
                    inner_normalized = self._normalize_path_component(inner_path)
                    path_part = f"{archive_normalized}/{inner_normalized}"
                else:
                    path_part = self._normalize_path_component(path_part)
            else:
                # Regular path normalization
                path_part = self._normalize_path_component(path_part)
            
            # Reconstruct with normalized scheme and path
            if scheme:
                return f"{scheme}{path_part}"
            else:
                return path_part
            
        except Exception as e:
            self.logger.debug("Error normalizing file path '%s': %s", target, e)
            return target.lower()
    
    def _normalize_path_component(self, path: str) -> str:
        """Normalize individual path component"""
        try:
            # Percent-decode once (safely)
            try:
                decoded = unquote(path)
            except Exception:
                decoded = path
            
            # Convert backslashes to forward slashes
            normalized = decoded.replace('\\', '/')
            
            # Collapse duplicate slashes
            while '//' in normalized:
                normalized = normalized.replace('//', '/')
            
            # Lowercase for case-insensitive matching
            normalized = normalized.lower()
            
            # Strip trailing slash unless root
            if len(normalized) > 1 and normalized.endswith('/'):
                normalized = normalized[:-1]
            
            # Drop query strings and fragments for file-like schemes
            if '?' in normalized:
                normalized = normalized.split('?')[0]
            if '#' in normalized:
                normalized = normalized.split('#')[0]
            
            return normalized
            
        except Exception:
            return path.lower()


# Global Phase 4 parser instance
_phase4_parser_instance = None


def get_phase4_favorites_parser(test_file_path: Optional[str] = None):
    """Get global Phase 4 favorites parser instance"""
    global _phase4_parser_instance
    if _phase4_parser_instance is None or test_file_path:
        _phase4_parser_instance = Phase4FavoritesParser(test_file_path)
    return _phase4_parser_instance