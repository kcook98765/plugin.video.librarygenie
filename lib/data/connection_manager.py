#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Database Connection Manager
Handles SQLite connections with proper safety and performance settings
"""

import sqlite3
import threading
import atexit
try:
    from typing import Any, List, Dict, Optional, Union, Callable
except ImportError:
    # Python < 3.5 fallback
    Any = object
    List = list
    Dict = dict
    Optional = object
    Union = object
    Callable = object

from contextlib import contextmanager

from ..utils.logger import get_logger
from ..config import get_config
from .storage_manager import get_storage_manager


class ConnectionManager:
    """Manages SQLite database connections with safety and performance optimizations"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.storage_manager = get_storage_manager()

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
        """Create and configure database connection"""
        db_path = self.storage_manager.get_database_path()
        self.logger.info(f"Creating database connection to: {db_path}")
        
        # Log the absolute path for debugging
        try:
            abs_path = os.path.abspath(db_path)
            self.logger.info(f"Absolute database path: {abs_path}")
        except Exception as e:
            self.logger.warning(f"Could not resolve absolute path: {e}")

        try:
            # Phase 3: Use configurable busy timeout
            busy_timeout_ms = self.config.get_db_busy_timeout_ms()
            busy_timeout_seconds = busy_timeout_ms / 1000.0

            # Create connection with proper settings
            conn = sqlite3.connect(
                db_path,
                timeout=busy_timeout_seconds,  # Phase 3: Configurable busy timeout
                check_same_thread=False  # Allow cross-thread access with our lock
            )

            # Phase 3: Enhanced database configuration
            # Enable WAL mode for better concurrent reads (idempotent)
            conn.execute("PRAGMA journal_mode=WAL")

            # Set busy timeout at the connection level too
            conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")

            # Other performance optimizations
            conn.execute("PRAGMA synchronous=NORMAL")  # Balanced durability vs performance
            conn.execute("PRAGMA cache_size=2000")     # 2MB cache
            conn.execute("PRAGMA temp_store=memory")   # Use memory for temp tables

            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys=ON")

            # Phase 3: Additional optimizations for large libraries
            conn.execute("PRAGMA page_size=4096")      # Standard page size
            conn.execute("PRAGMA mmap_size=268435456") # 256MB memory-mapped I/O

            # Set row factory for easier data access
            conn.row_factory = sqlite3.Row  # Enable dict-like access

            self.logger.info(f"Database connection established: {db_path} (busy_timeout: {busy_timeout_ms}ms)")
            return conn

        except Exception as e:
            self.logger.error(f"Failed to create database connection: {e}")
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
                self.logger.error(f"Transaction failed, rolling back: {e}")
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
                self.logger.error(f"Query failed: {query}, params: {params}, error: {e}")
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
                    self.logger.warning(f"Error closing database connection: {e}")
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
                operation_count = 0

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
                            self.logger.debug(f"Committed batch of {self.batch_size} operations")

                        return result

                batched_conn = BatchedConnection(conn, batch_size, self.logger)
                yield batched_conn

                # Final commit for any remaining operations
                if batched_conn.operation_count > 0:
                    conn.commit()
                    self.logger.debug(f"Final commit of {batched_conn.operation_count} operations")

            except Exception as e:
                self.logger.error(f"Batched transaction failed, rolling back: {e}")
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