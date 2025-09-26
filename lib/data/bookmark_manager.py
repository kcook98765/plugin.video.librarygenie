#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Bookmark Manager
Handles saving, retrieving, and managing user bookmarks for folders and content sources
"""

import json
import re
import urllib.parse
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from lib.utils.kodi_log import get_kodi_logger
from lib.data.connection_manager import get_connection_manager


class BookmarkManager:
    """Manages bookmark operations with URL normalization and credential handling"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.data.bookmark_manager')
        self.connection_manager = get_connection_manager()
        
    def save_bookmark(
        self, 
        url: str, 
        display_name: str, 
        bookmark_type: str = 'plugin',
        description: str = '',
        folder_id: Optional[int] = None,
        art_data: Optional[Dict] = None,
        additional_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Save a bookmark with URL normalization and credential handling
        
        Args:
            url: Original URL to bookmark
            display_name: User-friendly name
            bookmark_type: Type (plugin, file, network, library, special)
            description: Optional description
            folder_id: Organization folder ID
            art_data: Artwork/icon data
            additional_metadata: Extra metadata to store
            
        Returns:
            Dict with success status and bookmark_id or error message
        """
        try:
            # Validate bookmark type
            valid_types = {'plugin', 'file', 'network', 'library', 'special'}
            if bookmark_type not in valid_types:
                return {
                    'success': False,
                    'error': f'Invalid bookmark type. Must be one of: {", ".join(valid_types)}'
                }
            
            # Process URL: normalize and extract credentials
            normalized_url, metadata = self._process_url(url, bookmark_type, additional_metadata)
            
            # Prepare art data
            art_json = json.dumps(art_data) if art_data else None
            metadata_json = json.dumps(metadata) if metadata else None
            
            # Get next position in folder
            position = self._get_next_position(folder_id)
            
            # Insert bookmark
            with self.connection_manager.transaction() as conn:
                try:
                    cursor = conn.execute("""
                        INSERT INTO bookmarks (
                            url, normalized_url, display_name, bookmark_type, 
                            description, metadata, art_data, folder_id, position
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        url, normalized_url, display_name, bookmark_type,
                        description, metadata_json, art_json, folder_id, position
                    ))
                    
                    bookmark_id = cursor.lastrowid
                    
                except sqlite3.IntegrityError as e:
                    if 'UNIQUE constraint failed' in str(e):
                        return {
                            'success': False,
                            'error': f'A bookmark for this location already exists in the selected folder'
                        }
                    else:
                        raise
                
            self.logger.info("Bookmark saved: %s -> %s (ID: %d)", display_name, normalized_url, bookmark_id)
            
            return {
                'success': True,
                'bookmark_id': bookmark_id,
                'normalized_url': normalized_url
            }
            
        except Exception as e:
            self.logger.error("Failed to save bookmark '%s': %s", display_name, e)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_bookmarks(
        self, 
        folder_id: Optional[int] = None, 
        bookmark_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve bookmarks with optional filtering
        
        Args:
            folder_id: Filter by folder (None for root level)
            bookmark_type: Filter by type
            
        Returns:
            List of bookmark dictionaries
        """
        try:
            query = """
                SELECT id, url, normalized_url, display_name, bookmark_type,
                       description, metadata, art_data, folder_id, position,
                       created_at, updated_at
                FROM bookmarks
                WHERE 1=1
            """
            params = []
            
            if folder_id is not None:
                query += " AND folder_id = ?"
                params.append(folder_id)
            else:
                query += " AND folder_id IS NULL"
                
            if bookmark_type:
                query += " AND bookmark_type = ?"
                params.append(bookmark_type)
                
            query += " ORDER BY folder_id, position, display_name"
            
            bookmarks = []
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute(query, params)
                for row in cursor.fetchall():
                    bookmark = dict(row)
                    
                    # Parse JSON fields
                    if bookmark['metadata']:
                        try:
                            bookmark['metadata'] = json.loads(bookmark['metadata'])
                        except json.JSONDecodeError:
                            bookmark['metadata'] = {}
                    else:
                        bookmark['metadata'] = {}
                        
                    if bookmark['art_data']:
                        try:
                            bookmark['art_data'] = json.loads(bookmark['art_data'])
                        except json.JSONDecodeError:
                            bookmark['art_data'] = {}
                    else:
                        bookmark['art_data'] = {}
                        
                    bookmarks.append(bookmark)
                    
            return bookmarks
            
        except Exception as e:
            self.logger.error("Failed to retrieve bookmarks: %s", e)
            return []
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID"""
        try:
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
                deleted = cursor.rowcount > 0
                
            if deleted:
                self.logger.info("Bookmark deleted: ID %d", bookmark_id)
            else:
                self.logger.warning("Bookmark not found: ID %d", bookmark_id)
                
            return deleted
            
        except Exception as e:
            self.logger.error("Failed to delete bookmark ID %d: %s", bookmark_id, e)
            return False
    
    def update_bookmark(
        self, 
        bookmark_id: int, 
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        folder_id: Optional[int] = None,
        art_data: Optional[Dict] = None
    ) -> bool:
        """Update bookmark properties"""
        try:
            updates = []
            params = []
            
            if display_name is not None:
                updates.append("display_name = ?")
                params.append(display_name)
                
            if description is not None:
                updates.append("description = ?")
                params.append(description)
                
            if folder_id is not None:
                updates.append("folder_id = ?")
                params.append(folder_id)
                
            if art_data is not None:
                updates.append("art_data = ?")
                params.append(json.dumps(art_data))
                
            if not updates:
                return True  # No changes requested
                
            updates.append("updated_at = datetime('now')")
            params.append(bookmark_id)
            
            query = f"UPDATE bookmarks SET {', '.join(updates)} WHERE id = ?"
            
            with self.connection_manager.transaction() as conn:
                cursor = conn.execute(query, params)
                updated = cursor.rowcount > 0
                
            if updated:
                self.logger.info("Bookmark updated: ID %d", bookmark_id)
            else:
                self.logger.warning("Bookmark not found for update: ID %d", bookmark_id)
                
            return updated
            
        except Exception as e:
            self.logger.error("Failed to update bookmark ID %d: %s", bookmark_id, e)
            return False
    
    def _process_url(
        self, 
        url: str, 
        bookmark_type: str, 
        additional_metadata: Optional[Dict] = None
    ) -> Tuple[str, Dict]:
        """
        Process URL for normalization and credential extraction
        
        Returns:
            Tuple of (normalized_url, metadata_dict)
        """
        metadata = additional_metadata.copy() if additional_metadata else {}
        
        try:
            # Infer type from URL scheme if it conflicts with provided type
            inferred_type = self._infer_bookmark_type(url)
            if inferred_type != bookmark_type:
                self.logger.debug("Type mismatch: provided=%s, inferred=%s for URL %s", 
                                bookmark_type, inferred_type, url[:50])
                # Use inferred type for normalization
                actual_type = inferred_type
            else:
                actual_type = bookmark_type
                
            if actual_type == 'plugin':
                normalized_url = self._normalize_plugin_url(url)
                
            elif actual_type == 'network':
                normalized_url, username = self._normalize_network_url(url)
                if username:
                    # Store only username and host - NO passwords
                    metadata['username'] = username
                    metadata['requires_credentials'] = True
                    
            elif actual_type == 'file':
                normalized_url = self._normalize_file_path(url)
                
            elif actual_type == 'special':
                normalized_url = self._normalize_special_path(url)
                
            elif actual_type == 'library':
                normalized_url = self._normalize_library_url(url)
                
            else:
                # Fallback: basic normalization
                normalized_url = url.strip().rstrip('/')
                
            # Store original URL info (but strip credentials first)
            metadata['original_url'] = self._strip_credentials_from_url(url)
            metadata['bookmark_type'] = bookmark_type
            metadata['inferred_type'] = actual_type
            
            return normalized_url, metadata
            
        except Exception as e:
            self.logger.warning("URL processing failed for %s: %s", url[:50], e)
            # Fallback to basic processing
            return self._strip_credentials_from_url(url).strip(), metadata
    
    def _normalize_plugin_url(self, url: str) -> str:
        """Normalize plugin URL by sorting query parameters"""
        try:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            
            # Sort parameters for consistent comparison
            sorted_params = sorted(query_params)
            normalized_query = urllib.parse.urlencode(sorted_params)
            
            # Ensure path is '/' for plugin URLs (many plugins expect this)
            path = parsed.path if parsed.path else '/'
            
            # Reconstruct URL
            normalized = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                path,
                parsed.params,
                normalized_query,
                ''  # Remove fragment
            ))
            
            return normalized
            
        except Exception:
            return url.strip()
    
    def _normalize_network_url(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Normalize network URL and extract username only (NO passwords)
        
        Returns:
            Tuple of (url_without_credentials, username_only)
        """
        try:
            parsed = urllib.parse.urlparse(url)
            username = None
            
            # Extract username only if present
            if parsed.username:
                username = parsed.username
                
            # Rebuild URL without credentials
            hostname = parsed.hostname or ''
            
            # Handle IPv6 addresses with brackets
            if ':' in hostname and not hostname.startswith('['):
                hostname = f'[{hostname}]'
                
            netloc = hostname
            if parsed.port:
                netloc += f':{parsed.port}'
                
            # Preserve original trailing slash state (don't force one)
            path = parsed.path
                
            normalized = urllib.parse.urlunparse((
                parsed.scheme,
                netloc,
                path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
                
            return normalized, username
            
        except Exception:
            return self._strip_credentials_from_url(url).strip(), None
    
    def _normalize_file_path(self, path: str) -> str:
        """Normalize file system path with scheme awareness"""
        import os
        try:
            if path.startswith('file://'):
                # Handle file:// URLs properly
                parsed = urllib.parse.urlparse(path)
                normalized_path = os.path.normpath(parsed.path)
                # Convert backslashes to forward slashes for consistency
                normalized_path = normalized_path.replace('\\', '/')
                
                # Reassemble file URL
                return urllib.parse.urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    normalized_path,
                    parsed.params,
                    parsed.query,
                    ''  # Remove fragment
                ))
            else:
                # Handle regular file paths
                normalized = os.path.normpath(path.strip())
                # Convert backslashes to forward slashes for consistency
                normalized = normalized.replace('\\', '/')
                return normalized
        except Exception:
            return path.strip()
    
    def _normalize_special_path(self, url: str) -> str:
        """Normalize Kodi special:// paths"""
        return url.strip().rstrip('/')
    
    def _normalize_library_url(self, url: str) -> str:
        """Normalize videodb:// and musicdb:// URLs"""
        return url.strip().rstrip('/')
    
    def _get_next_position(self, folder_id: Optional[int]) -> int:
        """Get the next position for a bookmark in a folder"""
        try:
            query = "SELECT COALESCE(MAX(position), 0) + 1 FROM bookmarks WHERE "
            if folder_id is not None:
                query += "folder_id = ?"
                params = (folder_id,)
            else:
                query += "folder_id IS NULL"
                params = ()
                
            result = self.connection_manager.execute_single(query, params)
            return result[0] if result else 1
            
        except Exception:
            return 1
    
    def _infer_bookmark_type(self, url: str) -> str:
        """Infer bookmark type from URL scheme"""
        try:
            scheme = urllib.parse.urlparse(url).scheme.lower()
            
            if scheme == 'plugin':
                return 'plugin'
            elif scheme in ('smb', 'nfs', 'ftp', 'sftp', 'http', 'https'):
                return 'network'
            elif scheme == 'special':
                return 'special'
            elif scheme in ('videodb', 'musicdb'):
                return 'library'
            elif scheme == 'file' or not scheme:
                return 'file'
            else:
                return 'network'  # Default for unknown network protocols
                
        except Exception:
            return 'file'
    
    def _strip_credentials_from_url(self, url: str) -> str:
        """Remove credentials from any URL"""
        try:
            parsed = urllib.parse.urlparse(url)
            
            if parsed.username or parsed.password:
                # Rebuild without credentials
                hostname = parsed.hostname or ''
                if ':' in hostname and not hostname.startswith('['):
                    hostname = f'[{hostname}]'
                    
                netloc = hostname
                if parsed.port:
                    netloc += f':{parsed.port}'
                    
                return urllib.parse.urlunparse((
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
            else:
                return url
                
        except Exception:
            return url


# Global bookmark manager instance
_bookmark_manager_instance = None

def get_bookmark_manager():
    """Get singleton bookmark manager instance"""
    global _bookmark_manager_instance
    if _bookmark_manager_instance is None:
        _bookmark_manager_instance = BookmarkManager()
    return _bookmark_manager_instance