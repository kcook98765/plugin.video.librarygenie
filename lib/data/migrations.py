#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Phase 3 Enhanced Database Migrations
Handles database schema creation, versioning, and performance optimizations
"""

from .connection_manager import get_connection_manager
from ..utils.logger import get_logger


class MigrationManager:
    """Manages database schema migrations"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()

    def ensure_initialized(self):
        """Ensure database is initialized with latest schema"""
        try:
            current_version = self._get_schema_version()
            self.logger.debug(f"Current schema version: {current_version}")

            # Apply migrations in order
            for migration in self._get_migrations():
                if migration['version'] > current_version:
                    self.logger.info(f"Applying migration {migration['version']}: {migration['name']}")
                    self._apply_migration(migration)
                    self._set_schema_version(migration['version'])

            final_version = self._get_schema_version()
            self.logger.info(f"Database initialized at schema version {final_version}")

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

    def _apply_migration(self, migration):
        """Apply a single migration"""
        with self.conn_manager.transaction() as conn:
            for statement in migration['sql']:
                conn.execute(statement)

    def _get_migrations(self):
        """Get all available migrations in order"""
        return [
            {
                'version': 1,
                'name': 'Initial schema',
                'sql': [
                    """
                    CREATE TABLE schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE user_list (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL COLLATE NOCASE,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                    """
                    CREATE UNIQUE INDEX idx_user_list_name_unique 
                    ON user_list (name COLLATE NOCASE)
                    """,
                    """
                    CREATE TABLE list_item (
                        id INTEGER PRIMARYKEY AUTOINCREMENT,
                        list_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        year INTEGER,
                        imdb_id TEXT,
                        tmdb_id TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (list_id) REFERENCES user_list (id) ON DELETE CASCADE
                    )
                    """,
                    """
                    CREATE INDEX idx_list_item_list_id ON list_item (list_id)
                    """,
                    """
                    CREATE UNIQUE INDEX idx_list_item_unique_external 
                    ON list_item (list_id, imdb_id) 
                    WHERE imdb_id IS NOT NULL
                    """,
                    """
                    CREATE TRIGGER update_user_list_timestamp
                    AFTER INSERT ON list_item
                    FOR EACH ROW
                    BEGIN
                        UPDATE user_list 
                        SET updated_at = datetime('now') 
                        WHERE id = NEW.list_id;
                    END
                    """,
                ]
            },
            {
                'version': 2,
                'name': 'Library indexing support',
                'sql': [
                    """
                    CREATE TABLE library_movie (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        kodi_id INTEGER NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        year INTEGER,
                        imdb_id TEXT,
                        tmdb_id TEXT,
                        file_path TEXT NOT NULL,
                        date_added TEXT,
                        last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                        is_removed BOOLEAN NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                    """
                    CREATE INDEX idx_library_movie_kodi_id ON library_movie (kodi_id)
                    """,
                    """
                    CREATE INDEX idx_library_movie_imdb_id ON library_movie (imdb_id) 
                    WHERE imdb_id IS NOT NULL
                    """,
                    """
                    CREATE INDEX idx_library_movie_tmdb_id ON library_movie (tmdb_id)
                    WHERE tmdb_id IS NOT NULL
                    """,
                    """
                    CREATE UNIQUE INDEX idx_library_movie_composite 
                    ON library_movie (title, year, file_path) 
                    WHERE is_removed = 0
                    """,
                    """
                    CREATE INDEX idx_library_movie_last_seen ON library_movie (last_seen)
                    """,
                    """
                    CREATE TABLE library_scan_log (
                        id INTEGER PRIMARYKEY AUTOINCREMENT,
                        scan_type TEXT NOT NULL, -- 'full' or 'delta'
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        items_found INTEGER DEFAULT 0,
                        items_added INTEGER DEFAULT 0,
                        items_updated INTEGER DEFAULT 0,
                        items_removed INTEGER DEFAULT 0,
                        error_message TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                ]
            },
            {
                'version': 3,
                'name': 'Library-List integration',
                'sql': [
                    # Add library_movie_id to link list items to indexed movies
                    """
                    ALTER TABLE list_item ADD COLUMN library_movie_id INTEGER
                    REFERENCES library_movie(id) ON DELETE SET NULL
                    """,
                    # Update existing items to link with library where possible
                    """
                    UPDATE list_item 
                    SET library_movie_id = (
                        SELECT lm.id 
                        FROM library_movie lm 
                        WHERE lm.imdb_id = list_item.imdb_id 
                        AND lm.imdb_id IS NOT NULL
                        AND lm.is_removed = 0
                        LIMIT 1
                    )
                    WHERE library_movie_id IS NULL AND imdb_id IS NOT NULL
                    """,
                    # Create index for the new relationship
                    """
                    CREATE INDEX idx_list_item_library_movie 
                    ON list_item (library_movie_id)
                    """,
                    # Create unique constraint to prevent duplicates (list + library movie)
                    """
                    CREATE UNIQUE INDEX idx_list_item_unique_library
                    ON list_item (list_id, library_movie_id) 
                    WHERE library_movie_id IS NOT NULL
                    """,
                    # Add table to track list operation history
                    """
                    CREATE TABLE list_operation_log (
                        id INTEGER PRIMARYKEY AUTOINCREMENT,
                        operation TEXT NOT NULL, -- 'add' or 'remove'
                        list_id INTEGER NOT NULL,
                        library_movie_id INTEGER,
                        movie_title TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (list_id) REFERENCES user_list (id) ON DELETE CASCADE,
                        FOREIGN KEY (library_movie_id) REFERENCES library_movie (id) ON DELETE SET NULL
                    )
                    """,
                ]
            },
            {
                'version': 4,
                'name': 'Kodi Favorites integration',
                'sql': [
                    # Table to mirror Kodi favorites (read-only)
                    """
                    CREATE TABLE kodi_favorite (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        normalized_path TEXT NOT NULL UNIQUE,
                        original_path TEXT NOT NULL,
                        favorite_type TEXT NOT NULL, -- 'movie', 'tv', 'unknown'
                        library_movie_id INTEGER,
                        first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                        last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                        is_mapped INTEGER NOT NULL DEFAULT 0,
                        is_missing INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (library_movie_id) REFERENCES library_movie (id) ON DELETE SET NULL
                    )
                    """,
                    # Index for path lookups and library mapping
                    """
                    CREATE INDEX idx_kodi_favorite_normalized_path 
                    ON kodi_favorite (normalized_path)
                    """,
                    """
                    CREATE INDEX idx_kodi_favorite_library_movie 
                    ON kodi_favorite (library_movie_id) 
                    WHERE library_movie_id IS NOT NULL
                    """,
                    # Table to track favorites file state
                    """
                    CREATE TABLE favorites_scan_log (
                        id INTEGER PRIMARYKEY AUTOINCREMENT,
                        scan_type TEXT NOT NULL, -- 'full', 'check'
                        file_path TEXT NOT NULL,
                        file_modified TEXT, -- ISO timestamp of file modification
                        items_found INTEGER NOT NULL DEFAULT 0,
                        items_mapped INTEGER NOT NULL DEFAULT 0,
                        items_added INTEGER NOT NULL DEFAULT 0,
                        items_updated INTEGER NOT NULL DEFAULT 0,
                        scan_duration_ms INTEGER NOT NULL DEFAULT 0,
                        success INTEGER NOT NULL DEFAULT 1,
                        error_message TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                ]
            },
            {
                'version': 5,
                'name': 'Search optimization',
                'sql': [
                    # Add normalized title column for faster searching
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN normalized_title TEXT
                    """,
                    # Populate normalized titles from existing titles
                    """
                    UPDATE library_movie 
                    SET normalized_title = LOWER(TRIM(REPLACE(REPLACE(REPLACE(title, 'the ', ''), 'a ', ''), 'an ', '')))
                    WHERE normalized_title IS NULL
                    """,
                    # Add search-optimized indexes
                    """
                    CREATE INDEX idx_library_movie_normalized_title 
                    ON library_movie (normalized_title) 
                    WHERE is_removed = 0
                    """,
                    """
                    CREATE INDEX idx_library_movie_title_search 
                    ON library_movie (title COLLATE NOCASE) 
                    WHERE is_removed = 0
                    """,
                    """
                    CREATE INDEX idx_library_movie_year_search 
                    ON library_movie (year) 
                    WHERE is_removed = 0 AND year IS NOT NULL
                    """,
                    # Add file path search index (optional, for path-based search)
                    """
                    CREATE INDEX idx_library_movie_file_path_search 
                    ON library_movie (file_path COLLATE NOCASE) 
                    WHERE is_removed = 0
                    """,
                    # Add list search index for scoped searches
                    """
                    CREATE INDEX idx_list_item_search 
                    ON list_item (list_id, library_movie_id) 
                    WHERE library_movie_id IS NOT NULL
                    """,
                    # Table to store search history/preferences per user
                    """
                    CREATE TABLE search_history (
                        id INTEGER PRIMARYKEY AUTOINCREMENT,
                        query_text TEXT NOT NULL,
                        scope_type TEXT NOT NULL DEFAULT 'library', -- 'library', 'list'
                        scope_id INTEGER, -- list_id if scope_type = 'list'
                        year_filter TEXT, -- '2020' or '1999-2003'
                        sort_method TEXT NOT NULL DEFAULT 'title_asc', -- 'title_asc', 'year_desc', 'added_desc'
                        include_file_path INTEGER NOT NULL DEFAULT 0,
                        result_count INTEGER NOT NULL DEFAULT 0,
                        search_duration_ms INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                    # Index for search history cleanup
                    """
                    CREATE INDEX idx_search_history_cleanup 
                    ON search_history (created_at)
                    """,
                ]
            },
            {
                'version': 6,
                'name': 'Phase 11: Artwork and metadata support',
                'sql': [
                    # Add artwork columns to library_movie table
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN poster TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN fanart TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN thumb TEXT DEFAULT ''
                    """,
                    # Add extended metadata columns
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN plot TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN plotoutline TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN runtime INTEGER DEFAULT 0
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN rating REAL DEFAULT 0.0
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN genre TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN mpaa TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN director TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN country TEXT DEFAULT '[]'
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN studio TEXT DEFAULT '[]'
                    """,
                    # Add playback metadata columns
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN playcount INTEGER DEFAULT 0
                    """,
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN resume_time INTEGER DEFAULT 0
                    """,
                    # Create indexes for common searches
                    """
                    CREATE INDEX idx_library_movie_rating 
                    ON library_movie (rating DESC) 
                    WHERE is_removed = 0 AND rating > 0
                    """,
                    """
                    CREATE INDEX idx_library_movie_runtime 
                    ON library_movie (runtime) 
                    WHERE is_removed = 0 AND runtime > 0
                    """,
                    """
                    CREATE INDEX idx_library_movie_genre 
                    ON library_movie (genre) 
                    WHERE is_removed = 0 AND genre != ''
                    """,
                    # Table to store UI preferences for Phase 11
                    """
                    CREATE TABLE ui_preferences (
                        id INTEGER PRIMARY KEY,
                        ui_density TEXT NOT NULL DEFAULT 'compact', -- 'compact', 'detailed', 'art_heavy'
                        artwork_preference TEXT NOT NULL DEFAULT 'poster', -- 'poster', 'fanart'
                        show_secondary_label INTEGER NOT NULL DEFAULT 1, -- show year in secondary label
                        show_plot_in_detailed INTEGER NOT NULL DEFAULT 1, -- show plot in detailed mode
                        fallback_icon TEXT DEFAULT 'DefaultVideo.png', -- default icon for missing artwork
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                    # Insert default preferences
                    """
                    INSERT INTO ui_preferences (id, ui_density, artwork_preference, show_secondary_label, show_plot_in_detailed)
                    VALUES (1, 'compact', 'poster', 1, 1)
                    """,
                ]
            },
            {
                'version': 7,
                'name': 'Phase 3: Performance optimizations and additional indexes',
                'sql': [
                    # Additional search and filtering indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_date_added_desc 
                    ON library_movie (date_added DESC) 
                    WHERE is_removed = 0 AND date_added IS NOT NULL
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_active_title 
                    ON library_movie (is_removed, title COLLATE NOCASE) 
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_active_year_title 
                    ON library_movie (is_removed, year, title COLLATE NOCASE) 
                    WHERE year IS NOT NULL
                    """,
                    # List operation performance indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_list_item_position 
                    ON list_item (list_id, id) 
                    """,
                    # Scan log performance indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_scan_log_recent 
                    ON library_scan_log (completed_at DESC) 
                    WHERE completed_at IS NOT NULL
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_favorites_scan_log_recent 
                    ON favorites_scan_log (created_at DESC)
                    """,
                    # Search history maintenance index
                    """
                    CREATE INDEX IF NOT EXISTS idx_search_history_recent 
                    ON search_history (created_at DESC, scope_type)
                    """,
                    # Composite indexes for complex queries
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_imdb_active 
                    ON library_movie (imdb_id, is_removed) 
                    WHERE imdb_id IS NOT NULL
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_tmdb_active 
                    ON library_movie (tmdb_id, is_removed) 
                    WHERE tmdb_id IS NOT NULL
                    """,
                    # Kodi favorites performance
                    """
                    CREATE INDEX IF NOT EXISTS idx_kodi_favorite_mapped_active 
                    ON kodi_favorite (is_mapped, is_missing, library_movie_id) 
                    WHERE library_movie_id IS NOT NULL
                    """,
                ]
            },
            {
                'version': 8,
                'name': 'Phase 4: Enhanced Favorites integration',
                'sql': [
                    # Add missing columns to kodi_favorite table for Phase 4
                    """
                    ALTER TABLE kodi_favorite 
                    ADD COLUMN target_raw TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE kodi_favorite 
                    ADD COLUMN target_classification TEXT DEFAULT 'unknown'
                    """,
                    """
                    ALTER TABLE kodi_favorite 
                    ADD COLUMN normalized_key TEXT DEFAULT ''
                    """,
                    """
                    ALTER TABLE kodi_favorite 
                    ADD COLUMN present INTEGER NOT NULL DEFAULT 1
                    """,
                    """
                    ALTER TABLE kodi_favorite 
                    ADD COLUMN thumb_ref TEXT DEFAULT ''
                    """,
                    # Add normalized_path column to library_movie for better mapping
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN normalized_path TEXT DEFAULT ''
                    """,
                    # Populate normalized_path for existing library items
                    """
                    UPDATE library_movie 
                    SET normalized_path = LOWER(REPLACE(REPLACE(file_path, '\\', '/'), ' ', '%20'))
                    WHERE normalized_path = ''
                    """,
                    # Create index for normalized path lookups
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_normalized_path 
                    ON library_movie (normalized_path) 
                    WHERE is_removed = 0 AND normalized_path != ''
                    """,
                    # Create unique index for kodi_favorite on normalized_key
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_kodi_favorite_normalized_key 
                    ON kodi_favorite (normalized_key) 
                    WHERE normalized_key != ''
                    """,
                    # Additional indexes for Phase 4 performance
                    """
                    CREATE INDEX IF NOT EXISTS idx_kodi_favorite_present_mapped 
                    ON kodi_favorite (present, is_mapped, target_classification)
                    """,
                    """
                    CREATE INDEX IF NOT EXISTS idx_kodi_favorite_library_present 
                    ON kodi_favorite (library_movie_id, present) 
                    WHERE library_movie_id IS NOT NULL
                    """,
                ]
            },
            {
                'version': 9,
                'name': 'Phase 5: Enhanced search with improved normalization',
                'sql': [
                    # Add normalized_title column to media_items if it doesn't exist
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN normalized_title TEXT
                    """,
                    # Add normalized_path column to media_items if it doesn't exist
                    """
                    ALTER TABLE library_movie 
                    ADD COLUMN normalized_path TEXT
                    """,
                    # Update normalized_path using Phase 5 normalizer approach
                    """
                    UPDATE library_movie 
                    SET normalized_path = LOWER(REPLACE(REPLACE(REPLACE(file_path, '\\', '/'), '_', ' '), '-', ' '))
                    WHERE normalized_path = ''
                    """,
                    # Create index for normalized path searches
                    """
                    CREATE INDEX IF NOT EXISTS idx_library_movie_normalized_path_search 
                    ON library_movie (normalized_path) 
                    WHERE is_removed = 0 AND normalized_path != ''
                    """,
                    # Add search preferences table for user settings
                    """
                    CREATE TABLE IF NOT EXISTS search_preferences (
                        id INTEGER PRIMARYKEY AUTOINCREMENT,
                        preference_key TEXT NOT NULL UNIQUE,
                        preference_value TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """,
                    # Insert default search preferences
                    """
                    INSERT OR IGNORE INTO search_preferences (preference_key, preference_value) 
                    VALUES 
                        ('match_mode', 'contains'),
                        ('include_file_path', 'false'),
                        ('page_size', '50'),
                        ('enable_decade_shorthand', 'false')
                    """,
                    # Index for search preferences
                    """
                    CREATE INDEX IF NOT EXISTS idx_search_preferences_key 
                    ON search_preferences (preference_key)
                    """,
                ]
            }
        ]

    def _execute_safe(self, sql: str, params=None):
        """Execute SQL with proper error handling"""
        try:
            self.conn_manager.execute_write(sql, params or [])
        except Exception as e:
            self.logger.error(f"Migration SQL failed: {sql[:100]}... Error: {e}")
            raise

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            result = self.conn_manager.execute_single(
                "PRAGMA table_info(?)", [table_name]
            )
            if result:
                # PRAGMA table_info returns a list of column info
                columns_info = self.conn_manager.execute_many(
                    "PRAGMA table_info(?)", [table_name]
                )
                for column_info in columns_info:
                    if column_info and len(column_info) > 1 and column_info[1] == column_name:
                        return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking column existence: {e}")
            return False


# Global migration manager instance
_migration_instance = None


def get_migration_manager():
    """Get global migration manager instance"""
    global _migration_instance
    if _migration_instance is None:
        _migration_instance = MigrationManager()
    return _migration_instance