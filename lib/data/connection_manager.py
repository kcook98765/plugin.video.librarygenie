#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Database Connection Manager
Handles SQLite connections with proper safety and performance settings
"""

import os
import sqlite3
import threading
import atexit
from typing import Optional
from contextlib import contextmanager

from lib.utils.kodi_log import get_kodi_logger
from lib.config import get_config
from lib.data.storage_manager import get_storage_manager
from lib.data.db_config import get_db_config_calculator


class ConnectionManager:
    """Manages SQLite database connections with safety and performance optimizations"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.data.connection_manager')
        self.storage_manager = get_storage_manager()
        self.db_config = get_db_config_calculator()

        self.config = get_config()
        self._connection = None
        self._lock = threading.RLock()

        # Register cleanup on interpreter exit
        atexit.register(self.close)

    def get_connection(self):
        """Get database connection, creating if necessary"""
        if self._connection is None:
            with self._lock:
                if self._connection is None:
                    self._connection = self._create_connection()

        return self._connection

    def _create_connection(self):
        """Create database connection with service optimization"""
        # Check if service already initialized database with cached metadata
        service_metadata = self._get_service_metadata()
        
        if service_metadata:
            return self._create_optimized_connection(service_metadata)
        else:
            return self._create_standard_connection()

    def _get_service_metadata(self):
        """Get database optimization metadata from service"""
        try:
            import xbmcgui
            import json
            
            window = xbmcgui.Window(10000)
            metadata_str = window.getProperty('librarygenie.db.optimized')
            
            if metadata_str:
                metadata = json.loads(metadata_str)
                self.logger.debug("Found service database optimization metadata")
                return metadata
            
            return None
            
        except Exception as e:
            self.logger.debug(f"No service metadata available: {e}")
            return None

    def _create_optimized_connection(self, metadata):
        """Create connection using service-calculated optimization parameters with schema validation"""
        # Validate schema version before using optimized path
        if not self._validate_schema_version(metadata):
            self.logger.debug("Schema version mismatch - falling back to standard connection")
            return self._create_standard_connection()
            
        db_path = metadata['db_path']
        self.logger.debug(f"Optimized connection: {db_path}")
        
        try:
            busy_timeout_ms = self.config.get_db_busy_timeout_ms()
            busy_timeout_seconds = busy_timeout_ms / 1000.0
            
            # Direct connection with service-optimized parameters
            conn = sqlite3.connect(
                db_path,
                timeout=busy_timeout_seconds,
                check_same_thread=False
            )
            
            # Apply pre-calculated optimizations using centralized logic
            self.db_config.apply_pragma_settings(conn, metadata, busy_timeout_ms)
            
            # Skip schema initialization - service already handled it
            self.logger.debug("Optimized database connection established (service-optimized)")
            return conn
            
        except Exception as e:
            self.logger.error(f"Optimized connection failed: {e}")
            raise

    def _validate_schema_version(self, metadata):
        """Validate that cached schema version matches current target"""
        return self.db_config.validate_schema_version(metadata)

    def _create_standard_connection(self):
        """Standard connection creation using centralized configuration"""
        db_path = self.storage_manager.get_database_path()
        self.logger.debug("Standard connection: Creating database connection to: %s", db_path)
        
        # Log the absolute path for debugging
        try:
            abs_path = os.path.abspath(db_path)
            self.logger.debug("Absolute database path: %s", abs_path)
        except Exception as e:
            self.logger.warning("Could not resolve absolute path: %s", e)

        # Calculate optimization parameters using centralized logic
        config = self.db_config.calculate_optimization_params(db_path)

        try:
            # Use configurable busy timeout
            busy_timeout_ms = self.config.get_db_busy_timeout_ms()
            busy_timeout_seconds = busy_timeout_ms / 1000.0

            # Create connection with proper settings
            conn = sqlite3.connect(
                db_path,
                timeout=busy_timeout_seconds,
                check_same_thread=False  # Allow cross-thread access with our lock
            )

            # Apply PRAGMA settings using centralized logic
            self.db_config.apply_pragma_settings(conn, config, busy_timeout_ms)

            self.logger.debug("Database connection established: %s (busy_timeout: %sms)", db_path, busy_timeout_ms)
            
            # Initialize database schema if needed (pass connection directly to avoid recursion)
            try:
                from lib.data.migrations import MigrationManager
                migration_manager = MigrationManager(self)  # Pass self to avoid circular dependency
                migration_manager.ensure_initialized_with_connection(conn)  # Pass connection directly
                self.logger.debug("Database schema initialization completed")
            except Exception as e:
                self.logger.error("Database schema initialization failed: %s", e)
                conn.close()
                raise
            
            return conn

        except Exception as e:
            self.logger.error("Failed to create database connection: %s", e)
            raise

    @contextmanager
    def transaction(self):
        """Context manager for database transactions with proper locking"""
        with self._lock:
            conn = self.get_connection()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                self.logger.error("Transaction failed, rolling back: %s", e)
                conn.rollback()
                raise

    def execute_query(self, query, params=None):
        """Execute a query and return results"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute(query, params or [])
                return cursor.fetchall()
            except Exception as e:
                self.logger.error("Query failed: %s, params: %s, error: %s", query, params, e)
                raise

    def execute_single(self, query, params=None):
        """Execute a query and return single result"""
        results = self.execute_query(query, params)
        return results[0] if results else None

    def close(self):
        """Close database connection"""
        with self._lock:
            if self._connection:
                try:
                    self._connection.close()
                    self.logger.debug("Database connection closed")
                except Exception as e:
                    self.logger.warning("Error closing database connection: %s", e)
                finally:
                    self._connection = None

    # Phase 3: Batched operations support

    @contextmanager
    def batched_transaction(self, batch_size: Optional[int] = None):
        """
        Context manager for batched database operations
        Commits every batch_size operations to avoid long-running transactions
        """
        if batch_size is None:
            batch_size = self.config.get_db_batch_size()

        with self._lock:
            conn = self.get_connection()
            try:
                class BatchedConnection:
                    def __init__(self, conn, batch_size, logger):
                        self.conn = conn
                        self.batch_size = batch_size
                        self.logger = logger
                        self.operation_count = 0

                    def execute(self, query, params=None):
                        result = self.conn.execute(query, params or [])
                        self.operation_count += 1

                        # Commit batch if we've reached the batch size
                        if self.operation_count >= self.batch_size:
                            self.conn.commit()
                            self.operation_count = 0
                            # Silent batch commit - final count reported at process end

                        return result

                batched_conn = BatchedConnection(conn, batch_size, self.logger)
                yield batched_conn

                # Final commit for any remaining operations
                if batched_conn.operation_count > 0:
                    conn.commit()
                    # Silent final commit - final count reported at process end

            except Exception as e:
                self.logger.error("Batched transaction failed, rolling back: %s", e)
                conn.rollback()
                raise


# Global connection manager instance
_connection_instance = None


def get_connection_manager():
    """Get global connection manager instance"""
    global _connection_instance
    if _connection_instance is None:
        _connection_instance = ConnectionManager()
    return _connection_instance