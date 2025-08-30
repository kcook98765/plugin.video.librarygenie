#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Complete Database Schema Setup
Creates the full database schema without incremental migrations
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
            current_version = self._get_schema_version()
            self.logger.debug(f"Current schema version: {current_version}")

            if current_version == 0:
                self.logger.info("Initializing complete database schema")
                self._create_complete_schema()
                self._set_schema_version(9)
                self.logger.info("Database initialized with complete schema")
            elif current_version < 9:
                self.logger.info("Migrating to unified lists structure")
                self._migrate_to_unified_lists()
                self._set_schema_version(9)
                self.logger.info("Migration to unified lists complete")
            else:
                self.logger.info(f"Database already initialized at version {current_version}")

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    def _get_schema_version(self):
        """Get current schema version"""
        try:
            result = self.conn_manager.execute_single(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            return result['version'] if result else 0
        except Exception:
            # Schema version table doesn't exist yet
            return 0

    def _set_schema_version(self, version):
        """Record schema version"""
        with self.conn_manager.transaction() as conn:
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                [version]
            )

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

            # Lists table
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

            # Media items table - core metadata
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
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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

            # Legacy compatibility tables for existing functionality

            # User list table (legacy compatibility)
            conn.execute("""
                CREATE TABLE user_list (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("""
                CREATE UNIQUE INDEX idx_user_list_name_unique 
                ON user_list (name COLLATE NOCASE)
            """)

            # Library movie table (legacy compatibility)
            conn.execute("""
                CREATE TABLE library_movie (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kodi_id INTEGER NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    year INTEGER,
                    imdb_id TEXT,
                    tmdb_id TEXT,
                    file_path TEXT NOT NULL,
                    normalized_path TEXT DEFAULT '',
                    normalized_title TEXT,
                    date_added TEXT,
                    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                    is_removed BOOLEAN NOT NULL DEFAULT 0,
                    poster TEXT DEFAULT '',
                    fanart TEXT DEFAULT '',
                    thumb TEXT DEFAULT '',
                    plot TEXT DEFAULT '',
                    plotoutline TEXT DEFAULT '',
                    runtime INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    genre TEXT DEFAULT '',
                    mpaa TEXT DEFAULT '',
                    director TEXT DEFAULT '',
                    country TEXT DEFAULT '[]',
                    studio TEXT DEFAULT '[]',
                    playcount INTEGER DEFAULT 0,
                    resume_time INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Library movie indexes
            conn.execute("CREATE INDEX idx_library_movie_kodi_id ON library_movie (kodi_id)")
            conn.execute("CREATE INDEX idx_library_movie_imdb_id ON library_movie (imdb_id) WHERE imdb_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_library_movie_title_search ON library_movie (title COLLATE NOCASE) WHERE is_removed = 0")
            conn.execute("CREATE INDEX idx_library_movie_year_search ON library_movie (year) WHERE is_removed = 0 AND year IS NOT NULL")

            # List item table (legacy compatibility)
            conn.execute("""
                CREATE TABLE list_item (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    year INTEGER,
                    imdb_id TEXT,
                    tmdb_id TEXT,
                    library_movie_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (list_id) REFERENCES user_list (id) ON DELETE CASCADE,
                    FOREIGN KEY (library_movie_id) REFERENCES library_movie(id) ON DELETE SET NULL
                )
            """)

            conn.execute("CREATE INDEX idx_list_item_list_id ON list_item (list_id)")
            conn.execute("CREATE UNIQUE INDEX idx_list_item_unique_external ON list_item (list_id, imdb_id) WHERE imdb_id IS NOT NULL")

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

            # No default lists - users will create their own

    def _migrate_to_unified_lists(self):
        """Migrate data from legacy user_list/list_item to unified lists/list_items structure"""
        with self.conn_manager.transaction() as conn:
            self.logger.info("Starting migration to unified lists structure")

            # Migrate user_list to lists (no folder_id, so they go to root)
            conn.execute("""
                INSERT INTO lists (id, name, folder_id, created_at)
                SELECT id, name, NULL, created_at FROM user_list
            """)

            # Migrate list_item to media_items and list_items
            # First create media_items from list_item data
            conn.execute("""
                INSERT INTO media_items 
                (media_type, title, year, imdbnumber, tmdb_id, kodi_id, source, 
                 play, poster, fanart, plot, rating, votes, duration, mpaa, 
                 genre, director, studio, country, writer, cast, art, created_at)
                SELECT 
                    'movie' as media_type,
                    li.title,
                    li.year,
                    li.imdb_id,
                    li.tmdb_id,
                    lm.kodi_id,
                    'manual' as source,
                    '' as play,
                    '' as poster,
                    '' as fanart,
                    '' as plot,
                    0.0 as rating,
                    0 as votes,
                    0 as duration,
                    '' as mpaa,
                    '' as genre,
                    '' as director,
                    '' as studio,
                    '' as country,
                    '' as writer,
                    '' as cast,
                    '' as art,
                    li.created_at
                FROM list_item li
                LEFT JOIN library_movie lm ON li.library_movie_id = lm.id
            """)

            # Create mapping from old list_item.id to new media_items.id
            # Then create list_items entries
            conn.execute("""
                INSERT INTO list_items (list_id, media_item_id, position, created_at)
                SELECT 
                    li.list_id,
                    mi.id as media_item_id,
                    ROW_NUMBER() OVER (PARTITION BY li.list_id ORDER BY li.created_at) - 1 as position,
                    li.created_at
                FROM list_item li
                JOIN media_items mi ON (
                    li.title = mi.title 
                    AND COALESCE(li.year, 0) = COALESCE(mi.year, 0)
                    AND COALESCE(li.imdb_id, '') = COALESCE(mi.imdbnumber, '')
                    AND mi.source = 'manual'
                    AND li.created_at = mi.created_at
                )
            """)

            self.logger.info("Migration to unified lists structure completed")


# Global migration manager instance
_migration_instance = None


def get_migration_manager():
    """Get global migration manager instance"""
    global _migration_instance
    if _migration_instance is None:
        _migration_instance = MigrationManager()
    return _migration_instance