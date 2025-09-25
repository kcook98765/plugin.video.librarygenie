#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Database Configuration Calculator
Centralizes database optimization parameter calculation and PRAGMA settings
"""

import os
import sqlite3
from typing import Dict, Any, Optional

from lib.utils.kodi_log import get_kodi_logger


class DatabaseConfigCalculator:
    """Centralizes database configuration logic to eliminate code duplication"""
    
    def __init__(self):
        self.logger = get_kodi_logger('lib.data.db_config')
    
    def calculate_optimization_params(self, db_path: str) -> Dict[str, Any]:
        """
        Calculate database optimization parameters based on database size
        
        Returns dict with mmap_size, cache_pages, db_size_mb, and other metadata
        """
        config = {
            'db_path': db_path,
            'db_size_mb': 0,
            'mmap_size': 33554432,  # 32MB default
            'cache_pages': 500      # 2MB cache default
        }
        
        try:
            if os.path.exists(db_path):
                db_size_bytes = os.path.getsize(db_path)
                db_size_mb = db_size_bytes / (1024 * 1024)
                config['db_size_mb'] = db_size_mb
                
                # Centralized size-based optimization logic
                if db_size_mb < 16:
                    mmap_size = 33554432  # 32MB minimum for small DBs
                    cache_pages = 500     # 2MB cache
                elif db_size_mb < 64:
                    mmap_size = int(db_size_bytes * 2)  # 2x size for medium DBs
                    cache_pages = min(1500, int(db_size_mb * 75))  # Proportional, max 6MB
                else:
                    mmap_size = min(int(db_size_bytes * 1.5), 134217728)  # 1.5x size, max 128MB for large DBs
                    cache_pages = 2000  # 8MB cache for large DBs
                
                config.update({
                    'mmap_size': mmap_size,
                    'cache_pages': cache_pages
                })
                
                self.logger.debug(f"Calculated optimization params: {db_size_mb:.1f}MB DB, "
                                f"mmap={mmap_size//1048576}MB, cache={cache_pages} pages")
            else:
                # New database - use conservative defaults
                self.logger.debug("New database detected, using default optimization params")
                
        except Exception as e:
            self.logger.warning(f"Could not calculate optimization params, using defaults: {e}")
            
        return config
    
    def apply_pragma_settings(self, conn: sqlite3.Connection, config: Dict[str, Any], 
                            busy_timeout_ms: int) -> None:
        """
        Apply standardized PRAGMA settings to a database connection
        
        Args:
            conn: SQLite connection
            config: Configuration dict with mmap_size, cache_pages
            busy_timeout_ms: Busy timeout in milliseconds
        """
        try:
            mmap_size = config['mmap_size']
            cache_pages = config['cache_pages']
            
            # Apply all PRAGMA settings in standardized order
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(f"PRAGMA cache_size={cache_pages}")
            conn.execute("PRAGMA temp_store=memory")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA page_size=4096")
            conn.execute(f"PRAGMA mmap_size={mmap_size}")
            
            # Set row factory for dict-like access
            conn.row_factory = sqlite3.Row
            
            self.logger.debug(f"Applied PRAGMA settings: mmap={mmap_size//1048576}MB, "
                            f"cache={cache_pages} pages, timeout={busy_timeout_ms}ms")
            
        except Exception as e:
            self.logger.error(f"Failed to apply PRAGMA settings: {e}")
            raise
    
    def validate_schema_version(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate that cached schema version matches current target
        
        Args:
            metadata: Metadata dict containing schema version info
            
        Returns:
            True if schema versions are valid for optimization
        """
        try:
            cached_schema_version = metadata.get('schema_version', 0)
            cached_target_version = metadata.get('target_schema_version', 0)
            
            # Import current target version
            from lib.data.migrations import TARGET_SCHEMA_VERSION
            
            # Schema versions must match for safe optimization
            if cached_schema_version == cached_target_version == TARGET_SCHEMA_VERSION:
                return True
            
            self.logger.debug(f"Schema validation failed: cached={cached_schema_version}, "
                            f"cached_target={cached_target_version}, current_target={TARGET_SCHEMA_VERSION}")
            return False
            
        except Exception as e:
            self.logger.debug(f"Schema validation error: {e}")
            return False
    
    def get_current_schema_version(self, conn: sqlite3.Connection) -> int:
        """
        Get the current schema version from the database
        
        Args:
            conn: Database connection
            
        Returns:
            Current schema version or 0 if not found
        """
        try:
            schema_version_result = conn.execute(
                "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return schema_version_result['version'] if schema_version_result else 0
        except Exception as e:
            self.logger.error(f"Could not determine schema version: {e}")
            return 0
    
    def create_service_metadata(self, db_path: str) -> Dict[str, Any]:
        """
        Create complete metadata for service caching including schema version
        
        Args:
            db_path: Path to database file
            
        Returns:
            Complete metadata dict for caching
        """
        # Calculate optimization parameters
        metadata = self.calculate_optimization_params(db_path)
        
        # Add service-specific metadata
        metadata.update({
            'service_initialized': True
        })
        
        # Get current and target schema versions
        try:
            from lib.data.migrations import TARGET_SCHEMA_VERSION
            metadata['target_schema_version'] = TARGET_SCHEMA_VERSION
            
            # Get current schema version if database exists
            if os.path.exists(db_path):
                from lib.data import get_connection_manager
                connection_manager = get_connection_manager()
                with connection_manager.transaction() as conn:
                    metadata['schema_version'] = self.get_current_schema_version(conn)
            else:
                metadata['schema_version'] = 0
                
        except Exception as e:
            self.logger.error(f"Error getting schema versions: {e}")
            metadata.update({
                'schema_version': 0,
                'target_schema_version': 0
            })
            
        return metadata


# Singleton instance for global use
_db_config_calculator = None


def get_db_config_calculator() -> DatabaseConfigCalculator:
    """Get singleton DatabaseConfigCalculator instance"""
    global _db_config_calculator
    if _db_config_calculator is None:
        _db_config_calculator = DatabaseConfigCalculator()
    return _db_config_calculator