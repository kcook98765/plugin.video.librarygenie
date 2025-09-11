#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Database Schema Setup
Creates the complete database schema on first run
"""

from .connection_manager import get_connection_manager
from ..utils.logger import get_logger


class MigrationManager:
    """Manages database schema initialization"""

    def __init__(self, conn_manager=None):
        self.logger = get_logger(__name__)
        self.conn_manager = conn_manager or get_connection_manager()
        # Migration framework for future use - currently empty as all schema is in _create_complete_schema
        self.migrations = []

    def ensure_initialized(self):
        """Ensure database is initialized with complete schema"""
        try:
            if self._is_database_empty():
                self.logger.info("Initializing complete database schema")
                self._create_complete_schema()
                self.logger.info("Database initialized successfully")
            else:
                self.logger.debug("Database already initialized")
                # No migrations to run in this version

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    def ensure_initialized_with_connection(self, conn):
        """Ensure database is initialized with complete schema using provided connection"""
        try:
            if self._is_database_empty_with_connection(conn):
                self.logger.info("Initializing complete database schema")
                self._create_tables(conn)  # Use connection directly
                self.logger.info("Database initialized successfully")
            else:
                self.logger.debug("Database already initialized")
                # No migrations to run in this version

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

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
        -- Schema version tracking
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        
        INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'));
        
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
        
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            folder_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
        );
        
        CREATE UNIQUE INDEX idx_lists_name_folder ON lists (name, folder_id);
        
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
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX idx_media_items_imdbnumber ON media_items (imdbnumber);
        CREATE INDEX idx_media_items_media_type_kodi_id ON media_items (media_type, kodi_id);
        CREATE INDEX idx_media_items_title ON media_items (title COLLATE NOCASE);
        CREATE INDEX idx_media_items_year ON media_items (year);
        CREATE INDEX idx_media_items_episode_match ON media_items (tvshowtitle, season, episode);
        CREATE INDEX idx_media_items_tvshowtitle ON media_items (tvshowtitle COLLATE NOCASE);
        
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
        
        -- Additional essential tables
        CREATE TABLE movie_heavy_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kodi_movieid INTEGER,
            imdbnumber TEXT,
            cast_json TEXT,
            ratings_json TEXT,
            showlink_json TEXT,
            stream_json TEXT,
            uniqueid_json TEXT,
            tags_json TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE imdb_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imdb_id TEXT,
            title TEXT,
            year INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX idx_imdb_exports_imdb_id ON imdb_exports (imdb_id);
        
        CREATE TABLE imdb_to_kodi (
            imdb_id TEXT,
            kodi_id INTEGER,
            media_type TEXT
        );
        
        CREATE UNIQUE INDEX idx_imdb_to_kodi_unique ON imdb_to_kodi (imdb_id, kodi_id, media_type);
        
        CREATE TABLE kv_cache (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
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
        
        CREATE TABLE search_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preference_key TEXT NOT NULL UNIQUE,
            preference_value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE ui_preferences (
            id INTEGER PRIMARY KEY,
            ui_density TEXT NOT NULL DEFAULT 'compact',
            artwork_preference TEXT NOT NULL DEFAULT 'poster',
            show_secondary_label INTEGER NOT NULL DEFAULT 1,
            show_plot_in_detailed INTEGER NOT NULL DEFAULT 1,
            fallback_icon TEXT DEFAULT 'DefaultVideo.png',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE TABLE library_scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT NOT NULL,
            kodi_version INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT,
            total_items INTEGER DEFAULT 0,
            items_added INTEGER DEFAULT 0,
            items_updated INTEGER DEFAULT 0,
            items_removed INTEGER DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        CREATE INDEX idx_library_scan_log_type_time ON library_scan_log (scan_type, start_time);
        
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
        
        INSERT INTO search_preferences (preference_key, preference_value) 
        VALUES 
            ('match_mode', 'contains'),
            ('include_file_path', 'false'),
            ('page_size', '50'),
            ('enable_decade_shorthand', 'false');
        
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
            result = self.conn_manager.execute_single("SELECT version FROM schema_version")
            return result if result is not None else 0
        except Exception:
            # If schema_version table doesn't exist, assume version 0
            return 0

    def run_migrations(self):
        """Run all pending migrations"""
        # No migrations needed for pre-release - fresh database only
        self.logger.debug("No migrations to apply for pre-release version")


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