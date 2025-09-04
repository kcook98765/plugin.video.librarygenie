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

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()

    def ensure_initialized(self):
        """Ensure database is initialized with complete schema"""
        try:
            if self._is_database_empty():
                self.logger.info("Initializing complete database schema")
                self._create_complete_schema()
                self.logger.info("Database initialized successfully")
            else:
                self.logger.debug("Database already initialized")

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

    def _create_complete_schema(self):
        """Create complete database schema matching DATABASE_SCHEMA.md"""
        with self.conn_manager.transaction() as conn:
            # Schema version tracking
            conn.execute("""
                CREATE TABLE schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)

            # Set current schema version
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                [1]
            )

            # Folders table (must come before lists)
            conn.execute("""
                CREATE TABLE folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE UNIQUE INDEX idx_folders_name_parent 
                ON folders (name, parent_id)
            """)

            # Lists table - unified structure for all lists
            conn.execute("""
                CREATE TABLE lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    folder_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE UNIQUE INDEX idx_lists_name_folder 
                ON lists (name, folder_id)
            """)

            # Media items table - core metadata for all media types
            conn.execute("""
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
                    poster TEXT,
                    fanart TEXT,
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
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Media items indexes
            conn.execute("CREATE INDEX idx_media_items_imdbnumber ON media_items (imdbnumber)")
            conn.execute("CREATE INDEX idx_media_items_media_type_kodi_id ON media_items (media_type, kodi_id)")
            conn.execute("CREATE INDEX idx_media_items_title ON media_items (title COLLATE NOCASE)")
            conn.execute("CREATE INDEX idx_media_items_year ON media_items (year)")

            # List items table - associates media with lists
            conn.execute("""
                CREATE TABLE list_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    media_item_id INTEGER NOT NULL,
                    position INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE,
                    FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE UNIQUE INDEX idx_list_items_unique 
                ON list_items (list_id, media_item_id)
            """)

            conn.execute("""
                CREATE INDEX idx_list_items_position 
                ON list_items (list_id, position)
            """)

            # Movie heavy meta table
            conn.execute("""
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
                )
            """)

            # IMDB exports table
            conn.execute("""
                CREATE TABLE imdb_exports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imdb_id TEXT,
                    title TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("CREATE INDEX idx_imdb_exports_imdb_id ON imdb_exports (imdb_id)")

            # IMDB to Kodi mapping
            conn.execute("""
                CREATE TABLE imdb_to_kodi (
                    imdb_id TEXT,
                    kodi_id INTEGER,
                    media_type TEXT
                )
            """)

            conn.execute("""
                CREATE UNIQUE INDEX idx_imdb_to_kodi_unique 
                ON imdb_to_kodi (imdb_id, kodi_id, media_type)
            """)

            # Key-value cache
            conn.execute("""
                CREATE TABLE kv_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Sync state for remote services
            conn.execute("""
                CREATE TABLE sync_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_snapshot TEXT,
                    server_version TEXT,
                    server_etag TEXT,
                    last_sync_at TEXT,
                    server_url TEXT
                )
            """)

            # Auth state for remote services
            conn.execute("""
                CREATE TABLE auth_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    access_token TEXT,
                    expires_at TEXT,
                    token_type TEXT,
                    scope TEXT
                )
            """)

            # Pending operations for retry
            conn.execute("""
                CREATE TABLE pending_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    imdb_ids TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    retry_count INTEGER DEFAULT 0,
                    idempotency_key TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX idx_pending_operations_processing 
                ON pending_operations (operation, created_at)
            """)

            # Search and UI preferences tables
            conn.execute("""
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
                )
            """)

            conn.execute("""
                CREATE TABLE search_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    preference_key TEXT NOT NULL UNIQUE,
                    preference_value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("""
                CREATE TABLE ui_preferences (
                    id INTEGER PRIMARY KEY,
                    ui_density TEXT NOT NULL DEFAULT 'compact',
                    artwork_preference TEXT NOT NULL DEFAULT 'poster',
                    show_secondary_label INTEGER NOT NULL DEFAULT 1,
                    show_plot_in_detailed INTEGER NOT NULL DEFAULT 1,
                    fallback_icon TEXT DEFAULT 'DefaultVideo.png',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Insert default data
            conn.execute("""
                INSERT INTO ui_preferences (id, ui_density, artwork_preference, show_secondary_label, show_plot_in_detailed)
                VALUES (1, 'compact', 'poster', 1, 1)
            """)

            conn.execute("""
                INSERT INTO search_preferences (preference_key, preference_value) 
                VALUES 
                    ('match_mode', 'contains'),
                    ('include_file_path', 'false'),
                    ('page_size', '50'),
                    ('enable_decade_shorthand', 'false')
            """)

            # Library scan log table
            conn.execute("""
                CREATE TABLE library_scan_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_items INTEGER DEFAULT 0,
                    items_added INTEGER DEFAULT 0,
                    items_updated INTEGER DEFAULT 0,
                    items_removed INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("CREATE INDEX idx_library_scan_log_type_time ON library_scan_log (scan_type, start_time)")

            # Create reserved Search History folder
            conn.execute("""
                INSERT INTO folders (name, parent_id)
                VALUES ('Search History', NULL)
            """)

            # Kodi favorites tables
            conn.execute("""
                CREATE TABLE kodi_favorite (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_path TEXT,
                    original_path TEXT,
                    favorite_type TEXT,
                    target_raw TEXT NOT NULL,
                    target_classification TEXT NOT NULL,
                    normalized_key TEXT NOT NULL UNIQUE,
                    library_movie_id INTEGER,
                    is_mapped INTEGER DEFAULT 0,
                    is_missing INTEGER DEFAULT 0,
                    present INTEGER DEFAULT 1,
                    thumb_ref TEXT,
                    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (library_movie_id) REFERENCES media_items (id)
                )
            """)

            conn.execute("""
                CREATE TABLE favorites_scan_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_modified TEXT,
                    items_found INTEGER DEFAULT 0,
                    items_mapped INTEGER DEFAULT 0,
                    items_added INTEGER DEFAULT 0,
                    items_updated INTEGER DEFAULT 0,
                    scan_duration_ms INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # Favorites indexes
            conn.execute("CREATE INDEX idx_kodi_favorite_normalized_key ON kodi_favorite(normalized_key)")
            conn.execute("CREATE INDEX idx_kodi_favorite_library_movie_id ON kodi_favorite(library_movie_id)")
            conn.execute("CREATE INDEX idx_kodi_favorite_is_mapped ON kodi_favorite(is_mapped)")
            conn.execute("CREATE INDEX idx_kodi_favorite_present ON kodi_favorite(present)")
            conn.execute("CREATE INDEX idx_favorites_scan_log_file_path ON favorites_scan_log(file_path)")
            conn.execute("CREATE INDEX idx_favorites_scan_log_created_at ON favorites_scan_log(created_at)")


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