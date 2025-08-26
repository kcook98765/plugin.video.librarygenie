#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Complete Database Schema Setup
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
                self._set_schema_version(1)
                self.logger.info("Database initialized with complete schema")
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
        """Create complete database schema"""
        with self.conn_manager.transaction() as conn:
            # Schema version tracking
            conn.execute("""
                CREATE TABLE schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)

            # User lists table
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

            # Library movies table with all columns
            conn.execute("""
                CREATE TABLE library_movie (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
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
            conn.execute("CREATE INDEX idx_library_movie_tmdb_id ON library_movie (tmdb_id) WHERE tmdb_id IS NOT NULL")
            conn.execute("CREATE UNIQUE INDEX idx_library_movie_composite ON library_movie (title, year, file_path) WHERE is_removed = 0")
            conn.execute("CREATE INDEX idx_library_movie_last_seen ON library_movie (last_seen)")
            conn.execute("CREATE INDEX idx_library_movie_normalized_title ON library_movie (normalized_title) WHERE is_removed = 0")
            conn.execute("CREATE INDEX idx_library_movie_title_search ON library_movie (title COLLATE NOCASE) WHERE is_removed = 0")
            conn.execute("CREATE INDEX idx_library_movie_year_search ON library_movie (year) WHERE is_removed = 0 AND year IS NOT NULL")
            conn.execute("CREATE INDEX idx_library_movie_file_path_search ON library_movie (file_path COLLATE NOCASE) WHERE is_removed = 0")
            conn.execute("CREATE INDEX idx_library_movie_rating ON library_movie (rating DESC) WHERE is_removed = 0 AND rating > 0")
            conn.execute("CREATE INDEX idx_library_movie_runtime ON library_movie (runtime) WHERE is_removed = 0 AND runtime > 0")
            conn.execute("CREATE INDEX idx_library_movie_genre ON library_movie (genre) WHERE is_removed = 0 AND genre != ''")
            conn.execute("CREATE INDEX idx_library_movie_date_added_desc ON library_movie (date_added DESC) WHERE is_removed = 0 AND date_added IS NOT NULL")
            conn.execute("CREATE INDEX idx_library_movie_active_title ON library_movie (is_removed, title COLLATE NOCASE)")
            conn.execute("CREATE INDEX idx_library_movie_active_year_title ON library_movie (is_removed, year, title COLLATE NOCASE) WHERE year IS NOT NULL")
            conn.execute("CREATE INDEX idx_library_movie_imdb_active ON library_movie (imdb_id, is_removed) WHERE imdb_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_library_movie_tmdb_active ON library_movie (tmdb_id, is_removed) WHERE tmdb_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_library_movie_normalized_path ON library_movie (normalized_path) WHERE is_removed = 0 AND normalized_path != ''")
            conn.execute("CREATE INDEX idx_library_movie_normalized_path_search ON library_movie (normalized_path) WHERE is_removed = 0 AND normalized_path != ''")

            # List items table
            conn.execute("""
                CREATE TABLE list_item (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
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

            # List item indexes
            conn.execute("CREATE INDEX idx_list_item_list_id ON list_item (list_id)")
            conn.execute("CREATE UNIQUE INDEX idx_list_item_unique_external ON list_item (list_id, imdb_id) WHERE imdb_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_list_item_library_movie ON list_item (library_movie_id)")
            conn.execute("CREATE UNIQUE INDEX idx_list_item_unique_library ON list_item (list_id, library_movie_id) WHERE library_movie_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_list_item_search ON list_item (list_id, library_movie_id) WHERE library_movie_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_list_item_position ON list_item (list_id, id)")

            # Kodi favorites table
            conn.execute("""
                CREATE TABLE kodi_favorite (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_path TEXT NOT NULL UNIQUE,
                    original_path TEXT NOT NULL,
                    favorite_type TEXT NOT NULL,
                    library_movie_id INTEGER,
                    target_raw TEXT DEFAULT '',
                    target_classification TEXT DEFAULT 'unknown',
                    normalized_key TEXT DEFAULT '',
                    present INTEGER NOT NULL DEFAULT 1,
                    thumb_ref TEXT DEFAULT '',
                    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                    is_mapped INTEGER NOT NULL DEFAULT 0,
                    is_missing INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (library_movie_id) REFERENCES library_movie (id) ON DELETE SET NULL
                )
            """)

            # Kodi favorites indexes
            conn.execute("CREATE INDEX idx_kodi_favorite_normalized_path ON kodi_favorite (normalized_path)")
            conn.execute("CREATE INDEX idx_kodi_favorite_library_movie ON kodi_favorite (library_movie_id) WHERE library_movie_id IS NOT NULL")
            conn.execute("CREATE INDEX idx_kodi_favorite_mapped_active ON kodi_favorite (is_mapped, is_missing, library_movie_id) WHERE library_movie_id IS NOT NULL")
            conn.execute("CREATE UNIQUE INDEX idx_kodi_favorite_normalized_key ON kodi_favorite (normalized_key) WHERE normalized_key != ''")
            conn.execute("CREATE INDEX idx_kodi_favorite_present_mapped ON kodi_favorite (present, is_mapped, target_classification)")
            conn.execute("CREATE INDEX idx_kodi_favorite_library_present ON kodi_favorite (library_movie_id, present) WHERE library_movie_id IS NOT NULL")

            # Scan logs tables
            conn.execute("""
                CREATE TABLE library_scan_log (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
                    scan_type TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    items_found INTEGER DEFAULT 0,
                    items_added INTEGER DEFAULT 0,
                    items_updated INTEGER DEFAULT 0,
                    items_removed INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("CREATE INDEX idx_library_scan_log_recent ON library_scan_log (completed_at DESC) WHERE completed_at IS NOT NULL")

            conn.execute("""
                CREATE TABLE favorites_scan_log (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
                    scan_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_modified TEXT,
                    items_found INTEGER NOT NULL DEFAULT 0,
                    items_mapped INTEGER NOT NULL DEFAULT 0,
                    items_added INTEGER NOT NULL DEFAULT 0,
                    items_updated INTEGER NOT NULL DEFAULT 0,
                    scan_duration_ms INTEGER NOT NULL DEFAULT 0,
                    success INTEGER NOT NULL DEFAULT 1,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("CREATE INDEX idx_favorites_scan_log_recent ON favorites_scan_log (created_at DESC)")

            # Operation log table
            conn.execute("""
                CREATE TABLE list_operation_log (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    list_id INTEGER NOT NULL,
                    library_movie_id INTEGER,
                    movie_title TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (list_id) REFERENCES user_list (id) ON DELETE CASCADE,
                    FOREIGN KEY (library_movie_id) REFERENCES library_movie (id) ON DELETE SET NULL
                )
            """)

            # Search tables
            conn.execute("""
                CREATE TABLE search_history (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
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

            conn.execute("CREATE INDEX idx_search_history_cleanup ON search_history (created_at)")
            conn.execute("CREATE INDEX idx_search_history_recent ON search_history (created_at DESC, scope_type)")

            conn.execute("""
                CREATE TABLE search_preferences (
                    id INTEGER PRIMARYKEY AUTOINCREMENT,
                    preference_key TEXT NOT NULL UNIQUE,
                    preference_value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            conn.execute("CREATE INDEX idx_search_preferences_key ON search_preferences (preference_key)")

            # UI preferences table
            conn.execute("""
                CREATE TABLE ui_preferences (
                    id INTEGER PRIMARYKEY,
                    ui_density TEXT NOT NULL DEFAULT 'compact',
                    artwork_preference TEXT NOT NULL DEFAULT 'poster',
                    show_secondary_label INTEGER NOT NULL DEFAULT 1,
                    show_plot_in_detailed INTEGER NOT NULL DEFAULT 1,
                    fallback_icon TEXT DEFAULT 'DefaultVideo.png',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Triggers
            conn.execute("""
                CREATE TRIGGER update_user_list_timestamp
                AFTER INSERT ON list_item
                FOR EACH ROW
                BEGIN
                    UPDATE user_list 
                    SET updated_at = datetime('now') 
                    WHERE id = NEW.list_id;
                END
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


# Global migration manager instance
_migration_instance = None


def get_migration_manager():
    """Get global migration manager instance"""
    global _migration_instance
    if _migration_instance is None:
        _migration_instance = MigrationManager()
    return _migration_instance