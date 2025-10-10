#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - SQLite Backup & Restore
Handles binary database backups with Kodi ID remapping
"""

import os
import sqlite3
import zipfile
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from lib.utils.kodi_log import get_kodi_logger
from lib.data.storage_manager import get_storage_manager
from lib.data.connection_manager import get_connection_manager


class SQLiteBackupManager:
    """Manages SQLite database backups with settings"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.import_export.sqlite_backup')
        self.storage_manager = get_storage_manager()
        self.conn_manager = get_connection_manager()

    def create_backup_package(self, output_path: str) -> Dict[str, Any]:
        """
        Create backup ZIP containing database and settings
        
        Returns dict with success status and metadata
        """
        try:
            start_time = datetime.now()
            
            # Get paths
            db_path = self.storage_manager.get_database_path()
            addon_data_path = self.storage_manager.get_profile_path()
            settings_path = os.path.join(addon_data_path, 'settings.xml')
            
            # Create temp backup DB
            temp_dir = os.path.join(addon_data_path, 'temp_backup')
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_db = os.path.join(temp_dir, 'librarygenie.db')
            
            # Perform SQLite backup using backup API
            self.logger.info("Creating database backup...")
            backup_result = self._backup_database(db_path, temp_db)
            
            if not backup_result['success']:
                return {"success": False, "error": backup_result.get('error', 'Database backup failed')}
            
            # Verify backup integrity
            self.logger.info("Verifying backup integrity...")
            if not self._verify_database_integrity(temp_db):
                return {"success": False, "error": "Backup integrity check failed"}
            
            # Create ZIP archive
            self.logger.info("Creating backup archive...")
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # Add database
                backup_zip.write(temp_db, 'librarygenie.db')
                
                # Add settings.xml if it exists
                if os.path.exists(settings_path):
                    backup_zip.write(settings_path, 'settings.xml')
                    self.logger.info("Added settings.xml to backup")
                else:
                    self.logger.warning("settings.xml not found, skipping")
            
            # Cleanup temp files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Get backup metadata
            file_size = os.path.getsize(output_path)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self.logger.info("Backup created successfully: %s (%d bytes, %dms)", 
                           output_path, file_size, duration_ms)
            
            return {
                "success": True,
                "file_path": output_path,
                "file_size": file_size,
                "duration_ms": duration_ms,
                "backup_type": "sqlite"
            }
            
        except Exception as e:
            self.logger.error("Error creating backup package: %s", e)
            return {"success": False, "error": str(e)}

    def _backup_database(self, source_db: str, dest_db: str) -> Dict[str, Any]:
        """
        Use SQLite backup API for safe live backup
        """
        try:
            # Connect to source database
            source = sqlite3.connect(source_db)
            
            # Connect to destination (creates new file)
            dest = sqlite3.connect(dest_db)
            
            # Perform backup using SQLite's backup API
            # This handles locks and creates consistent snapshot
            source.backup(dest)
            
            # Close connections
            dest.close()
            source.close()
            
            self.logger.info("Database backup completed: %s", dest_db)
            return {"success": True}
            
        except Exception as e:
            self.logger.error("Database backup failed: %s", e)
            return {"success": False, "error": str(e)}

    def _verify_database_integrity(self, db_path: str) -> bool:
        """Verify database integrity after backup"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            conn.close()
            
            is_ok = result and result[0] == 'ok'
            
            if is_ok:
                self.logger.info("Database integrity check passed")
            else:
                self.logger.error("Database integrity check failed: %s", result)
            
            return is_ok
            
        except Exception as e:
            self.logger.error("Error verifying database integrity: %s", e)
            return False

    def restore_backup_package(self, backup_path: str, remap_kodi_ids: bool = True) -> Dict[str, Any]:
        """
        Restore backup ZIP to current installation
        
        Args:
            backup_path: Path to backup ZIP file
            remap_kodi_ids: Whether to remap Kodi IDs to current library
            
        Returns dict with success status and details
        """
        try:
            self.logger.info("Starting backup restore from: %s", backup_path)
            
            # Verify backup file exists
            if not os.path.exists(backup_path):
                return {"success": False, "error": "Backup file not found"}
            
            # Verify it's a ZIP file
            if not zipfile.is_zipfile(backup_path):
                return {"success": False, "error": "Invalid backup file (not a ZIP)"}
            
            addon_data_path = self.storage_manager.get_profile_path()
            temp_dir = os.path.join(addon_data_path, 'temp_restore')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Extract backup
            self.logger.info("Extracting backup archive...")
            with zipfile.ZipFile(backup_path, 'r') as backup_zip:
                backup_zip.extractall(temp_dir)
            
            temp_db = os.path.join(temp_dir, 'librarygenie.db')
            temp_settings = os.path.join(temp_dir, 'settings.xml')
            
            # Verify database exists in backup
            if not os.path.exists(temp_db):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"success": False, "error": "Database not found in backup"}
            
            # Verify database integrity
            self.logger.info("Verifying backup database integrity...")
            if not self._verify_database_integrity(temp_db):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"success": False, "error": "Backup database integrity check failed"}
            
            # Remap Kodi IDs if requested
            if remap_kodi_ids:
                self.logger.info("Remapping Kodi library IDs...")
                remap_result = self._remap_library_kodi_ids(temp_db)
                if not remap_result['success']:
                    self.logger.warning("Kodi ID remapping failed: %s", remap_result.get('error'))
            
            # Replace live database
            self.logger.info("Replacing live database...")
            db_path = self.storage_manager.get_database_path()
            
            # Close the database connection to release file lock
            self.logger.info("Closing database connections...")
            self.conn_manager.close()
            
            # Force garbage collection to ensure cleanup
            try:
                import gc
                gc.collect()
            except:
                pass
            
            # Backup current database first (if it exists)
            current_backup = db_path + '.before_restore'
            if os.path.exists(db_path):
                shutil.copy(db_path, current_backup)
                self.logger.info("Current database backed up to: %s", current_backup)
            else:
                self.logger.warning("No existing database to backup")
            
            # Replace database
            shutil.copy(temp_db, db_path)
            self.logger.info("Database restored successfully")
            
            # Restore settings.xml if present
            if os.path.exists(temp_settings):
                settings_path = os.path.join(addon_data_path, 'settings.xml')
                shutil.copy(temp_settings, settings_path)
                self.logger.info("Settings restored successfully")
            
            # Cleanup temp files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return {
                "success": True,
                "message": "Backup restored successfully. Restart addon to apply changes.",
                "requires_restart": True
            }
            
        except Exception as e:
            self.logger.error("Error restoring backup: %s", e)
            return {"success": False, "error": str(e)}

    def _remap_library_kodi_ids(self, db_path: str) -> Dict[str, Any]:
        """
        Remap library items' kodi_id to match current Kodi installation
        """
        try:
            # Scan current Kodi library
            self.logger.info("Scanning current Kodi library...")
            current_library = self._scan_kodi_library()
            
            if not current_library:
                return {"success": False, "error": "Could not scan Kodi library"}
            
            self.logger.info("Found %d items in current Kodi library", len(current_library))
            
            # Open restored database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # CRITICAL: Clear all kodi_ids first to prevent unique constraint violations
            # When remapping, IDs may swap between items, causing conflicts with the unique index
            # on (media_type, source, kodi_id). Nulling first ensures clean updates.
            self.logger.info("Clearing existing kodi_ids to prevent constraint violations...")
            cursor.execute("""
                UPDATE media_items 
                SET kodi_id = NULL 
                WHERE source = 'lib'
            """)
            conn.commit()
            self.logger.info("Kodi IDs cleared successfully")
            
            # Get all library items from backup
            cursor.execute("""
                SELECT id, file_path, imdbnumber, title, year, media_type 
                FROM media_items 
                WHERE source = 'lib'
            """)
            
            matched_count = 0
            removed_count = 0
            
            for row in cursor.fetchall():
                item_id, file_path, imdb_id, title, year, media_type = row
                new_kodi_id = None
                
                # Try matching by file_path first (most reliable)
                if file_path:
                    for kodi_item in current_library:
                        if kodi_item.get('file') == file_path:
                            # Get ID based on media type (movieid vs episodeid)
                            if media_type == 'movie':
                                new_kodi_id = kodi_item.get('movieid')
                            elif media_type == 'episode':
                                new_kodi_id = kodi_item.get('episodeid')
                            break
                
                # Try IMDb ID if no file match
                if not new_kodi_id and imdb_id:
                    for kodi_item in current_library:
                        if kodi_item.get('imdbnumber') == imdb_id:
                            if media_type == 'movie':
                                new_kodi_id = kodi_item.get('movieid')
                            elif media_type == 'episode':
                                new_kodi_id = kodi_item.get('episodeid')
                            break
                
                # Try title + year as last resort
                if not new_kodi_id and title and year:
                    for kodi_item in current_library:
                        if (kodi_item.get('title') == title and 
                            kodi_item.get('year') == year):
                            if media_type == 'movie':
                                new_kodi_id = kodi_item.get('movieid')
                            elif media_type == 'episode':
                                new_kodi_id = kodi_item.get('episodeid')
                            break
                
                # Update database
                if new_kodi_id:
                    cursor.execute("""
                        UPDATE media_items 
                        SET kodi_id = ?, is_removed = 0 
                        WHERE id = ?
                    """, (new_kodi_id, item_id))
                    matched_count += 1
                else:
                    cursor.execute("""
                        UPDATE media_items 
                        SET is_removed = 1 
                        WHERE id = ?
                    """, (item_id,))
                    removed_count += 1
            
            conn.commit()
            conn.close()
            
            self.logger.info("Kodi ID remapping complete: %d matched, %d marked removed", 
                           matched_count, removed_count)
            
            return {
                "success": True,
                "matched": matched_count,
                "removed": removed_count
            }
            
        except Exception as e:
            self.logger.error("Error remapping Kodi IDs: %s", e)
            return {"success": False, "error": str(e)}

    def _scan_kodi_library(self) -> list:
        """
        Scan current Kodi library and return list of items
        """
        try:
            import xbmc
            import json
            
            items = []
            
            # Scan movies
            query = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetMovies",
                "params": {
                    "properties": ["title", "year", "file", "imdbnumber"]
                },
                "id": 1
            }
            
            result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
            if 'result' in result and 'movies' in result['result']:
                for movie in result['result']['movies']:
                    movie['media_type'] = 'movie'
                    items.append(movie)
            
            # Scan TV episodes
            query = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "properties": ["title", "showtitle", "season", "episode", "file"]
                },
                "id": 2
            }
            
            result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
            if 'result' in result and 'episodes' in result['result']:
                for episode in result['result']['episodes']:
                    episode['media_type'] = 'episode'
                    items.append(episode)
            
            return items
            
        except Exception as e:
            self.logger.error("Error scanning Kodi library: %s", e)
            return []


# Global instance
_sqlite_backup_manager = None

def get_sqlite_backup_manager():
    """Get global SQLite backup manager instance"""
    global _sqlite_backup_manager
    if _sqlite_backup_manager is None:
        _sqlite_backup_manager = SQLiteBackupManager()
    return _sqlite_backup_manager
