#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Database Schema Setup
Creates the complete database schema on first run
"""

import time
from lib.data.connection_manager import get_connection_manager
from lib.utils.kodi_log import get_kodi_logger

# Current target schema version
TARGET_SCHEMA_VERSION = 2


class MigrationManager:
    """Manages database schema initialization"""

    def __init__(self, conn_manager=None):
        self.logger = get_kodi_logger('lib.data.migrations')
        self.conn_manager = conn_manager or get_connection_manager()
        # Migration framework for future use - currently empty as all schema is in _create_complete_schema
        self.migrations = []

    def ensure_initialized(self):
        """Ensure database is initialized with complete schema"""
        try:
            # Delegate to the connection-based method for proper locking
            with self.conn_manager.transaction() as conn:
                self.ensure_initialized_with_connection(conn)

        except Exception as e:
            self.logger.error("Database initialization failed: %s", e)
            raise

    def ensure_initialized_with_connection(self, conn):
        """Ensure database is initialized with complete schema using provided connection"""
        # Use application-level locking to prevent concurrent initialization
        try:
            # First, try to acquire an exclusive lock on the database
            self._acquire_init_lock(conn)
            
            # Re-check version after acquiring lock (another process might have initialized)
            current_version = self._get_current_version_with_connection(conn)
            
            if current_version == 0:  # No schema_version table or empty database
                # Check if this is truly an empty database
                if self._is_database_empty_with_connection(conn):
                    self.logger.info("Initializing complete database schema for new database")
                    self._create_tables(conn)
                    self.logger.info("Database initialized successfully")
                else:
                    # Database has tables but no schema_version - likely an old version
                    self.logger.info("Existing database without schema version detected")
                    self._create_schema_version_table(conn)
                    self._set_schema_version(conn, TARGET_SCHEMA_VERSION)
                    self.logger.info("Schema version tracking added to existing database")
            else:
                self.logger.debug("Database already at version %s", current_version)

        except Exception as e:
            self.logger.error("Database initialization failed: %s", e)
            raise
        finally:
            self._release_init_lock(conn)

    def _is_database_empty(self):
        """Check if database is empty (no tables exist)"""
        try:
            result = self.conn_manager.execute_single(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            return result is None
        except Exception:
            return True

    def _is_database_empty_with_connection(self, conn):
        """Check if database is empty using provided connection (no tables exist)"""
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            result = cursor.fetchone()
            return result is None
        except Exception:
            return True

    def _create_complete_schema(self):
        """Create complete database schema matching DATABASE_SCHEMA.md"""
        with self.conn_manager.transaction() as conn:
            self._create_tables(conn)

    def _create_tables(self, conn):
        """Create all database tables"""
        # Execute complete schema as a single script to avoid indentation issues
        schema_sql = """
        -- Schema version tracking (single-row table)
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        );
        
        INSERT INTO schema_version (id, version, applied_at) VALUES (1, 2, datetime('now')) 
        ON CONFLICT(id) DO UPDATE SET version=excluded.version, applied_at=excluded.applied_at;
        
        -- Auth state table for device authorization (CRITICAL - fixes original error)
        CREATE TABLE auth_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_code TEXT,
            user_code TEXT,
            verification_uri TEXT,
            verification_uri_complete TEXT,
            expires_in INTEGER,
            interval_seconds INTEGER,
            api_key TEXT,
            token_type TEXT,
            scope TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Essential core tables
        CREATE TABLE folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL
        );
        
        CREATE UNIQUE INDEX idx_folders_name_parent ON folders (name, parent_id);
        CREATE INDEX idx_folders_parent_id ON folders (parent_id);
        
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            folder_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
        );
        
        CREATE UNIQUE INDEX idx_lists_name_folder ON lists (name, folder_id);
        CREATE INDEX idx_lists_folder_id ON lists (folder_id);
        
        CREATE TABLE media_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            title TEXT,
            year INTEGER,
            imdbnumber TEXT,
            tmdb_id TEXT,
            kodi_id INTEGER,
            source TEXT,
            play TEXT,
            plot TEXT,
            rating REAL,
            votes INTEGER,
            duration INTEGER,
            mpaa TEXT,
            genre TEXT,
            director TEXT,
            studio TEXT,
            country TEXT,
            writer TEXT,
            cast TEXT,
            art TEXT,
            file_path TEXT,
            normalized_path TEXT,
            is_removed INTEGER DEFAULT 0,
            display_title TEXT,
            duration_seconds INTEGER,
            tvshowtitle TEXT,
            season INTEGER,
            episode INTEGER,
            aired TEXT,
            tvshow_kodi_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX idx_media_items_imdbnumber ON media_items (imdbnumber);
        CREATE INDEX idx_media_items_media_type_kodi_id ON media_items (media_type, kodi_id);
        CREATE INDEX idx_media_items_title ON media_items (title COLLATE NOCASE);
        CREATE INDEX idx_media_items_year ON media_items (year);
        CREATE INDEX idx_media_items_episode_match ON media_items (tvshowtitle, season, episode);
        CREATE INDEX idx_media_items_tvshowtitle ON media_items (tvshowtitle COLLATE NOCASE);
        CREATE INDEX idx_media_items_tvshow_episode ON media_items (tvshow_kodi_id, season, episode);
        
        CREATE TABLE list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            media_item_id INTEGER NOT NULL,
            position INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE,
            FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE
        );
        
        CREATE UNIQUE INDEX idx_list_items_unique ON list_items (list_id, media_item_id);
        CREATE INDEX idx_list_items_position ON list_items (list_id, position);
        CREATE INDEX idx_list_items_list_id ON list_items (list_id);
        CREATE INDEX idx_list_items_media_item_id ON list_items (media_item_id);
        
        -- Additional essential tables
        CREATE TABLE sync_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_snapshot TEXT,
            server_version TEXT,
            server_etag TEXT,
            last_sync_at TEXT,
            server_url TEXT
        );
        
        CREATE TABLE pending_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            imdb_ids TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            retry_count INTEGER DEFAULT 0,
            idempotency_key TEXT
        );
        
        CREATE INDEX idx_pending_operations_processing ON pending_operations (operation, created_at);
        
        CREATE TABLE search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT NOT NULL,
            scope_type TEXT NOT NULL DEFAULT 'library',
            scope_id INTEGER,
            year_filter TEXT,
            sort_method TEXT NOT NULL DEFAULT 'title_asc',
            include_file_path INTEGER NOT NULL DEFAULT 0,
            result_count INTEGER NOT NULL DEFAULT 0,
            search_duration_ms INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX idx_search_history_query_created ON search_history (query_text, created_at);
        
        CREATE TABLE ui_preferences (
            id INTEGER PRIMARY KEY,
            ui_density TEXT NOT NULL DEFAULT 'compact',
            artwork_preference TEXT NOT NULL DEFAULT 'poster',
            show_secondary_label INTEGER NOT NULL DEFAULT 1,
            show_plot_in_detailed INTEGER NOT NULL DEFAULT 1,
            fallback_icon TEXT DEFAULT 'DefaultVideo.png',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        
        CREATE TABLE kodi_favorite (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_path TEXT,
            original_path TEXT,
            favorite_type TEXT,
            target_raw TEXT NOT NULL,
            target_classification TEXT NOT NULL,
            normalized_key TEXT NOT NULL UNIQUE,
            media_item_id INTEGER,
            is_mapped INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (media_item_id) REFERENCES media_items(id)
        );
        
        CREATE INDEX idx_kodi_favorite_normalized_key ON kodi_favorite (normalized_key);
        CREATE INDEX idx_kodi_favorite_media_item_id ON kodi_favorite (media_item_id);
        CREATE INDEX idx_kodi_favorite_target_classification ON kodi_favorite (target_classification);
        
        
        CREATE TABLE remote_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL UNIQUE,
            cache_value TEXT,
            cache_metadata TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT
        );
        
        CREATE INDEX idx_remote_cache_key ON remote_cache(cache_key);
        CREATE INDEX idx_remote_cache_expires ON remote_cache(expires_at);
        
        -- Insert default data
        INSERT INTO ui_preferences (id, ui_density, artwork_preference, show_secondary_label, show_plot_in_detailed)
        VALUES (1, 'compact', 'poster', 1, 1);
        
        INSERT INTO folders (name, parent_id)
        VALUES ('Search History', NULL);
        """
        
        # Execute the complete schema script
        try:
            conn.executescript(schema_sql)
            self.logger.debug("Database schema created successfully")
        except AttributeError:
            # Fallback for connections that don't support executescript
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            for statement in statements:
                if statement:
                    conn.execute(statement)
            self.logger.debug("Database schema created successfully (fallback method)")
        
        self.logger.info("Complete database schema created successfully")


    def _get_current_version(self):
        """Get the current schema version"""
        try:
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
                result = cursor.fetchone()
                if result:
                    # Ensure we return an integer, not a Row object
                    version = result[0]
                    return int(version) if version is not None else 0
                return 0
        except Exception:
            # If schema_version table doesn't exist, assume version 0
            return 0
            
    def _get_current_version_with_connection(self, conn):
        """Get the current schema version using provided connection"""
        try:
            cursor = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
            result = cursor.fetchone()
            if result:
                # Ensure we return an integer, not a Row object
                version = result[0]
                return int(version) if version is not None else 0
            return 0
        except Exception:
            # If schema_version table doesn't exist, assume version 0
            return 0

            
            


    def run_migrations(self):
        """Run all pending migrations - framework preserved for future use"""
        # Migrations removed for pre-release - using fresh schema reset instead
        # Framework preserved for future incremental migrations
        self.logger.debug("Migration framework available but no migrations defined for current version")
        
        # Future migrations can be added to self.migrations list and executed here
        current_version = self._get_current_version()
        if len(self.migrations) > 0:
            self.logger.info("Running %d pending migrations from version %d", len(self.migrations), current_version)
            # Migration execution logic would go here
        else:
            self.logger.debug("No migrations to apply - using fresh schema initialization")
        
    def _acquire_init_lock(self, conn):
        """Acquire an application-level lock for database initialization"""
        # Check if we're already in a transaction (avoid nested BEGIN)
        try:
            # Test if we can execute a simple query without starting a transaction
            conn.execute("SELECT 1")
            in_transaction = conn.in_transaction
        except Exception:
            in_transaction = False
            
        if in_transaction:
            self.logger.debug("Already in transaction, skipping lock acquisition")
            return
            
        max_retries = 5
        retry_delay = 0.2
        
        for attempt in range(max_retries):
            try:
                # Use BEGIN IMMEDIATE to get an exclusive write lock
                conn.execute("BEGIN IMMEDIATE")
                self.logger.debug("Acquired database initialization lock on attempt %d", attempt + 1)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.debug("Could not acquire initialization lock on attempt %d: %s, retrying...", attempt + 1, e)
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    self.logger.error("Could not acquire initialization lock after %d attempts: %s", max_retries, e)
                    raise Exception(f"Failed to acquire database lock after {max_retries} attempts: {e}")
                
    def _release_init_lock(self, conn):
        """Release the application-level initialization lock"""
        try:
            # Only commit if we're in a transaction
            if conn.in_transaction:
                conn.commit()
                self.logger.debug("Released database initialization lock")
            else:
                self.logger.debug("No transaction to commit, lock already released")
        except Exception as e:
            self.logger.debug("Lock release failed (may have been auto-released): %s", e)
            
    def _create_schema_version_table(self, conn):
        """Create schema_version table with single-row semantics"""
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL,
                    applied_at TEXT NOT NULL
                )
            """)
            self.logger.debug("Schema version table created or verified")
        except Exception as e:
            self.logger.error("Failed to create schema_version table: %s", e)
            raise
            
    def _set_schema_version(self, conn, version):
        """Set schema version using safe upsert semantics"""
        try:
            # Ensure schema_version table exists first
            self._create_schema_version_table(conn)
            
            # Try new single-row format first
            try:
                conn.execute("""
                    INSERT INTO schema_version (id, version, applied_at) 
                    VALUES (1, ?, datetime('now')) 
                    ON CONFLICT(id) DO UPDATE SET version=excluded.version, applied_at=excluded.applied_at
                """, (version,))
                self.logger.debug("Set schema version to %s using single-row format", version)
            except Exception as e:
                # Fallback for old schema_version table format
                self.logger.debug("Single-row format failed, trying legacy format: %s", e)
                conn.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, datetime('now'))", (version,))
                self.logger.debug("Set schema version to %s using legacy format", version)
                
        except Exception as e:
            self.logger.error("Failed to set schema version to %s: %s", version, e)
            raise


# Global migration manager instance
_migration_instance = None


def get_migration_manager():
    """Get global migration manager instance"""
    global _migration_instance
    if _migration_instance is None:
        _migration_instance = MigrationManager()
    return _migration_instance


def initialize_database():
    """Initialize database - convenience function for service.py"""
    manager = get_migration_manager()
    manager.ensure_initialized()