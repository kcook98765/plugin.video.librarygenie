#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Database Schema Setup
Creates the complete database schema on first run
"""

import json
import time
from lib.data.connection_manager import get_connection_manager
from lib.utils.kodi_log import get_kodi_logger

# Current target schema version
TARGET_SCHEMA_VERSION = 12


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
                # Check if we need to run migrations for version upgrades
                if current_version < TARGET_SCHEMA_VERSION:
                    self.logger.info("Upgrading database from version %s to %s", current_version, TARGET_SCHEMA_VERSION)
                    self._run_migrations(conn, current_version)
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
        
        INSERT INTO schema_version (id, version, applied_at) VALUES (1, 12, datetime('now')) 
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
            art_data TEXT,
            is_import_sourced INTEGER DEFAULT 0,
            import_source_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL,
            FOREIGN KEY (import_source_id) REFERENCES import_sources(id) ON DELETE CASCADE
        );
        
        CREATE UNIQUE INDEX idx_folders_name_parent ON folders (name, parent_id);
        CREATE INDEX idx_folders_parent_id ON folders (parent_id);
        -- F-06b: root folders (parent_id IS NULL) need their own uniqueness
        -- because SQLite treats NULLs as distinct in ordinary unique
        -- indexes, so idx_folders_name_parent does not enforce root-level
        -- name uniqueness. This partial index restricts root rows only.
        CREATE UNIQUE INDEX idx_folders_root_unique ON folders (name) WHERE parent_id IS NULL;
        
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            folder_id INTEGER,
            is_import_sourced INTEGER DEFAULT 0,
            import_source_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL,
            FOREIGN KEY (import_source_id) REFERENCES import_sources(id) ON DELETE CASCADE
        );
        
        CREATE UNIQUE INDEX idx_lists_name_folder ON lists (name, folder_id);
        CREATE INDEX idx_lists_folder_id ON lists (folder_id);
        -- F-06: root lists (folder_id IS NULL) need their own uniqueness
        -- because SQLite treats NULLs as distinct in ordinary unique
        -- indexes, so idx_lists_name_folder does not enforce root-level
        -- name uniqueness. This partial index restricts root rows only.
        CREATE UNIQUE INDEX idx_lists_root_unique ON lists (name) WHERE folder_id IS NULL;
        
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
        CREATE UNIQUE INDEX idx_media_items_lib_unique ON media_items (media_type, source, kodi_id) WHERE kodi_id IS NOT NULL AND source = 'lib';
        CREATE UNIQUE INDEX idx_media_items_imdb_unique ON media_items (media_type, imdbnumber) WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL);
        
        CREATE TABLE list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            media_item_id INTEGER NOT NULL,
            position INTEGER,
            search_score REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE,
            FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE
        );
        
        CREATE UNIQUE INDEX idx_list_items_unique ON list_items (list_id, media_item_id);
        CREATE INDEX idx_list_items_position ON list_items (list_id, position);
        CREATE INDEX idx_list_items_list_id ON list_items (list_id);
        CREATE INDEX idx_list_items_media_item_id ON list_items (media_item_id);
        
        -- Intersection lists tables
        CREATE TABLE intersection_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
        );
        
        CREATE INDEX idx_intersection_lists_list_id ON intersection_lists (list_id);
        
        CREATE TABLE intersection_list_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersection_list_id INTEGER NOT NULL,
            source_list_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (intersection_list_id) REFERENCES intersection_lists(id) ON DELETE CASCADE,
            FOREIGN KEY (source_list_id) REFERENCES lists(id) ON DELETE CASCADE
        );
        
        CREATE INDEX idx_intersection_list_sources_intersection_id ON intersection_list_sources (intersection_list_id);
        CREATE INDEX idx_intersection_list_sources_source_list ON intersection_list_sources (source_list_id);
        CREATE UNIQUE INDEX idx_intersection_list_sources_unique ON intersection_list_sources (intersection_list_id, source_list_id);
        
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
        
        -- Sync snapshot table for memory-efficient delta detection
        CREATE TABLE sync_snapshot (
            kodi_id INTEGER PRIMARY KEY,
            media_type TEXT NOT NULL,
            title TEXT,
            file_path TEXT,
            dateadded TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        ) WITHOUT ROWID;
        
        CREATE INDEX idx_sync_snapshot_media_type ON sync_snapshot (media_type);
        CREATE INDEX idx_sync_snapshot_media_type_kodi_id ON sync_snapshot (media_type, kodi_id);
        
        -- Import sources table for tracking file-based media imports
        CREATE TABLE IF NOT EXISTS import_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            folder_id INTEGER,
            scan_policy TEXT,
            last_scan TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_import_sources_folder_id ON import_sources (folder_id);
        CREATE INDEX IF NOT EXISTS idx_import_sources_source_url ON import_sources (source_url);
        
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

            
            


    def _run_migrations(self, conn, current_version):
        """Run incremental migrations from current_version to TARGET_SCHEMA_VERSION"""
        try:
            # Migration from version 4 to 5: Add import_sources table
            if current_version < 5:
                self.logger.info("Migrating from version 4 to 5: Adding import_sources table")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS import_sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_url TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        folder_id INTEGER,
                        scan_policy TEXT,
                        last_scan TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_import_sources_folder_id ON import_sources (folder_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_import_sources_source_url ON import_sources (source_url)")
                self.logger.info("import_sources table created successfully")
            
            # Migration from version 5 to 6: Add art_data column to folders table
            if current_version < 6:
                self.logger.info("Migrating from version 5 to 6: Adding art_data column to folders table")
                conn.execute("ALTER TABLE folders ADD COLUMN art_data TEXT")
                self.logger.info("art_data column added to folders table successfully")
            
            # Migration from version 6 to 7: Add import locking columns
            if current_version < 7:
                self.logger.info("Migrating from version 6 to 7: Adding import locking columns")
                conn.execute("ALTER TABLE folders ADD COLUMN is_import_sourced INTEGER DEFAULT 0")
                conn.execute("ALTER TABLE folders ADD COLUMN import_source_id INTEGER REFERENCES import_sources(id) ON DELETE CASCADE")
                conn.execute("ALTER TABLE lists ADD COLUMN is_import_sourced INTEGER DEFAULT 0")
                conn.execute("ALTER TABLE lists ADD COLUMN import_source_id INTEGER REFERENCES import_sources(id) ON DELETE CASCADE")
                self.logger.info("Import locking columns added successfully")
            
            # Migration from version 7 to 8: Add unique constraints to prevent duplicate media items
            if current_version < 8:
                self.logger.info("Migrating from version 7 to 8: Adding unique constraints for media_items")
                
                # Step 1a: Remove duplicate list_items that would conflict after re-homing
                self.logger.info("Removing duplicate list_items entries for library duplicates")
                conn.execute("""
                    DELETE FROM list_items
                    WHERE id NOT IN (
                        SELECT MIN(li.id)
                        FROM list_items li
                        INNER JOIN media_items mi ON li.media_item_id = mi.id
                        WHERE mi.kodi_id IS NOT NULL AND mi.source = 'lib'
                        GROUP BY li.list_id, mi.media_type, mi.source, mi.kodi_id
                    )
                    AND media_item_id IN (
                        SELECT id FROM media_items
                        WHERE kodi_id IS NOT NULL AND source = 'lib'
                    )
                """)
                
                # Step 1b: Migrate remaining list_items references for library duplicates
                self.logger.info("Re-homing list_items references for duplicate library items")
                conn.execute("""
                    UPDATE list_items
                    SET media_item_id = (
                        SELECT MAX(id)
                        FROM media_items AS m2
                        WHERE m2.media_type = (SELECT media_type FROM media_items WHERE id = list_items.media_item_id)
                          AND m2.source = (SELECT source FROM media_items WHERE id = list_items.media_item_id)
                          AND m2.kodi_id = (SELECT kodi_id FROM media_items WHERE id = list_items.media_item_id)
                          AND m2.kodi_id IS NOT NULL AND m2.source = 'lib'
                    )
                    WHERE media_item_id IN (
                        SELECT id FROM media_items
                        WHERE kodi_id IS NOT NULL AND source = 'lib'
                          AND id NOT IN (
                              SELECT MAX(id)
                              FROM media_items
                              WHERE kodi_id IS NOT NULL AND source = 'lib'
                              GROUP BY media_type, source, kodi_id
                          )
                    )
                """)
                
                # Step 1c: Migrate kodi_favorite references for library duplicates
                self.logger.info("Re-homing kodi_favorite references for duplicate library items")
                conn.execute("""
                    UPDATE kodi_favorite
                    SET media_item_id = (
                        SELECT MAX(id)
                        FROM media_items AS m2
                        WHERE m2.media_type = (SELECT media_type FROM media_items WHERE id = kodi_favorite.media_item_id)
                          AND m2.source = (SELECT source FROM media_items WHERE id = kodi_favorite.media_item_id)
                          AND m2.kodi_id = (SELECT kodi_id FROM media_items WHERE id = kodi_favorite.media_item_id)
                          AND m2.kodi_id IS NOT NULL AND m2.source = 'lib'
                    )
                    WHERE media_item_id IN (
                        SELECT id FROM media_items
                        WHERE kodi_id IS NOT NULL AND source = 'lib'
                          AND id NOT IN (
                              SELECT MAX(id)
                              FROM media_items
                              WHERE kodi_id IS NOT NULL AND source = 'lib'
                              GROUP BY media_type, source, kodi_id
                          )
                    )
                """)
                
                # Step 2: Remove duplicate library items (now safe - list_items updated)
                self.logger.info("Removing duplicate library items (keeping most recent)")
                conn.execute("""
                    DELETE FROM media_items 
                    WHERE id NOT IN (
                        SELECT MAX(id) 
                        FROM media_items 
                        WHERE kodi_id IS NOT NULL AND source = 'lib'
                        GROUP BY media_type, source, kodi_id
                    ) 
                    AND kodi_id IS NOT NULL AND source = 'lib'
                """)
                
                # Step 3a: Remove duplicate list_items that would conflict after re-homing (IMDb duplicates)
                self.logger.info("Removing duplicate list_items entries for non-library IMDb duplicates")
                conn.execute("""
                    DELETE FROM list_items
                    WHERE id NOT IN (
                        SELECT MIN(li.id)
                        FROM list_items li
                        INNER JOIN media_items mi ON li.media_item_id = mi.id
                        WHERE mi.imdbnumber IS NOT NULL AND mi.imdbnumber != '' 
                          AND (mi.source != 'lib' OR mi.source IS NULL)
                        GROUP BY li.list_id, mi.media_type, mi.imdbnumber
                    )
                    AND media_item_id IN (
                        SELECT id FROM media_items
                        WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                    )
                """)
                
                # Step 3b: Migrate remaining list_items references for IMDb duplicates (non-library items only)
                self.logger.info("Re-homing list_items references for duplicate non-library items with IMDb IDs")
                conn.execute("""
                    UPDATE list_items
                    SET media_item_id = (
                        SELECT MAX(id)
                        FROM media_items AS m2
                        WHERE m2.media_type = (SELECT media_type FROM media_items WHERE id = list_items.media_item_id)
                          AND m2.imdbnumber = (SELECT imdbnumber FROM media_items WHERE id = list_items.media_item_id)
                          AND m2.imdbnumber IS NOT NULL AND m2.imdbnumber != ''
                          AND (m2.source != 'lib' OR m2.source IS NULL)
                    )
                    WHERE media_item_id IN (
                        SELECT id FROM media_items
                        WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                          AND id NOT IN (
                              SELECT MAX(id)
                              FROM media_items
                              WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                              GROUP BY media_type, imdbnumber
                          )
                    )
                """)
                
                # Step 3c: Migrate kodi_favorite references for IMDb duplicates (non-library items only)
                self.logger.info("Re-homing kodi_favorite references for duplicate non-library items with IMDb IDs")
                conn.execute("""
                    UPDATE kodi_favorite
                    SET media_item_id = (
                        SELECT MAX(id)
                        FROM media_items AS m2
                        WHERE m2.media_type = (SELECT media_type FROM media_items WHERE id = kodi_favorite.media_item_id)
                          AND m2.imdbnumber = (SELECT imdbnumber FROM media_items WHERE id = kodi_favorite.media_item_id)
                          AND m2.imdbnumber IS NOT NULL AND m2.imdbnumber != ''
                          AND (m2.source != 'lib' OR m2.source IS NULL)
                    )
                    WHERE media_item_id IN (
                        SELECT id FROM media_items
                        WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                          AND id NOT IN (
                              SELECT MAX(id)
                              FROM media_items
                              WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                              GROUP BY media_type, imdbnumber
                          )
                    )
                """)
                
                # Step 4: Remove duplicate non-library items with IMDb IDs (now safe - list_items updated)
                self.logger.info("Removing duplicate non-library items with IMDb IDs (keeping most recent)")
                conn.execute("""
                    DELETE FROM media_items 
                    WHERE id NOT IN (
                        SELECT MAX(id) 
                        FROM media_items 
                        WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                        GROUP BY media_type, imdbnumber
                    ) 
                    AND imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                """)
                
                # Step 5: Create unique index for library items (source = 'lib' with kodi_id)
                # This prevents duplicate library items during sync
                conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_media_items_lib_unique 
                    ON media_items (media_type, source, kodi_id) 
                    WHERE kodi_id IS NOT NULL AND source = 'lib'
                """)
                
                # Step 6: Create unique index for items with IMDb IDs (excluding library items)
                # This prevents duplicate non-library items while preserving library items
                conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_media_items_imdb_unique 
                    ON media_items (media_type, imdbnumber) 
                    WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND (source != 'lib' OR source IS NULL)
                """)
                
                self.logger.info("Unique constraints for media_items added successfully")
            
            # Migration from version 8 to 9: Add search_score column to list_items table
            if current_version < 9:
                self.logger.info("Migrating from version 8 to 9: Adding search_score column to list_items table")
                conn.execute("ALTER TABLE list_items ADD COLUMN search_score REAL")
                self.logger.info("search_score column added to list_items table successfully")
            
            # Migration from version 9 to 10: Add intersection lists tables
            if current_version < 10:
                self.logger.info("Migrating from version 9 to 10: Adding intersection lists tables")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS intersection_lists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        list_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_intersection_lists_list_id ON intersection_lists (list_id)")
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS intersection_list_sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        intersection_list_id INTEGER NOT NULL,
                        source_list_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (intersection_list_id) REFERENCES intersection_lists(id) ON DELETE CASCADE,
                        FOREIGN KEY (source_list_id) REFERENCES lists(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_intersection_list_sources_intersection_id ON intersection_list_sources (intersection_list_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_intersection_list_sources_source_list ON intersection_list_sources (source_list_id)")
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_intersection_list_sources_unique ON intersection_list_sources (intersection_list_id, source_list_id)")
                self.logger.info("Intersection lists tables created successfully")

            # Migration from version 10 to 11 (F-06): enforce root-level list
            # name uniqueness. The existing unique index
            # idx_lists_name_folder ON lists (name, folder_id) cannot enforce
            # uniqueness among root lists because SQLite treats NULL values as
            # distinct in ordinary UNIQUE indexes (folder_id IS NULL for root
            # lists). This migration:
            #   1. deduplicates any pre-existing duplicate root lists, keeping
            #      the newest one (MAX id) so no user data is lost: list_items,
            #      intersection rows and import provenance are re-homed onto
            #      the surviving list;
            #   2. creates the partial unique index that makes root names
            #      unique among roots while leaving sibling uniqueness
            #      (idx_lists_name_folder) and cross-folder name reuse
            #      (same name under different folders) completely untouched.
            if current_version < 11:
                self.logger.info("Migrating from version 10 to 11: enforcing root-level list name uniqueness")

                # Step 1: re-home list_items from duplicate root lists onto the
                # surviving (newest) duplicate. Rows that would collide after
                # re-homing (same media item already linked to the survivor)
                # are not copied again.
                self.logger.info("Re-homing list_items from duplicate root lists onto the surviving list")
                conn.execute("""
                    INSERT OR IGNORE INTO list_items (list_id, media_item_id, position, search_score)
                    SELECT MIN(surv.id), li.media_item_id, li.position, li.search_score
                    FROM list_items li
                    INNER JOIN lists dup ON dup.id = li.list_id
                    INNER JOIN lists surv
                        ON surv.name = dup.name
                        AND surv.folder_id IS NULL
                        AND surv.id = (
                            SELECT MAX(s.id)
                            FROM lists s
                            WHERE s.name = dup.name AND s.folder_id IS NULL
                        )
                        AND surv.id != dup.id
                    WHERE dup.folder_id IS NULL
                    GROUP BY surv.id, li.media_item_id
                """)

                # Step 2: re-home intersection references from duplicate root
                # lists onto the surviving list.
                self.logger.info("Re-homing intersection list references from duplicate root lists")
                conn.execute("""
                    UPDATE intersection_lists
                    SET list_id = (
                        SELECT MAX(s.id)
                        FROM lists s
                        WHERE s.name = (SELECT l2.name FROM lists l2 WHERE l2.id = intersection_lists.list_id)
                          AND s.folder_id IS NULL
                    )
                    WHERE list_id IN (
                        SELECT l.id
                        FROM lists l
                        WHERE l.folder_id IS NULL
                          AND l.id NOT IN (
                              SELECT MAX(s.id)
                              FROM lists s
                              WHERE s.folder_id IS NULL
                              GROUP BY s.name
                          )
                    )
                """)

                # Step 2b (F-06a): re-home intersection-source references
                # (intersection_list_sources.source_list_id) from duplicate root
                # lists onto the surviving list. This column is a persisted FK to
                # lists(id) with ON DELETE CASCADE, so leaving it untouched would
                # have Step 3 silently drop those rows, widening the intersection
                # (an AND filter losing a term) and losing user configuration.
                #
                # Build a deterministic mapping old_id -> new_id (the survivor,
                # MAX(id) per root name group) so the reconciliation does not
                # repeat fragile nested name lookups.
                self.logger.info("Building duplicate-root mapping for intersection-source re-homing")
                conn.execute("""
                    CREATE TEMP TABLE f06a_list_map (
                        old_id INTEGER PRIMARY KEY,
                        new_id INTEGER NOT NULL
                    )
                """)
                conn.execute("""
                    INSERT INTO f06a_list_map (old_id, new_id)
                    SELECT l.id,
                           (SELECT MAX(s.id)
                              FROM lists s
                              WHERE s.name = l.name AND s.folder_id IS NULL)
                    FROM lists l
                    WHERE l.folder_id IS NULL
                      AND l.id NOT IN (
                          SELECT MAX(s.id)
                          FROM lists s
                          WHERE s.folder_id IS NULL
                          GROUP BY s.name
                      )
                """)

                # Collision-safe reconciliation of source rows, done in two
                # ordered operations so the unique index
                # idx_intersection_list_sources_unique (intersection_list_id,
                # source_list_id) is never violated:
                #
                #   (i)   Materialize one source row per surviving
                #         (intersection, survivor) relationship with
                #         INSERT OR IGNORE. Rows whose relationship already
                #         exists (the intersection already references the
                #         survivor) are skipped, and when several duplicate
                #         sources map onto the same survivor only one new row
                #         is kept - OR IGNORE enforces the unique index per
                #         row, so this cannot create a duplicate pair and
                #         cannot fail.
                #   (ii)  Delete every remaining source row that still points
                #         at a non-survivor duplicate root; its logical
                #         relationship now exists on the survivor row from (i).
                #
                # Order matters: inserts happen before the deletes, so the
                # logical source is never transiently missing, and no UPDATE
                # re-write (which would hit a transient unique violation when
                # two duplicates map onto one survivor) is required.
                self.logger.info("Re-homing intersection source references from duplicate root lists")
                conn.execute("""
                    INSERT OR IGNORE INTO intersection_list_sources
                        (intersection_list_id, source_list_id, created_at)
                    SELECT s.intersection_list_id, m.new_id, s.created_at
                    FROM intersection_list_sources s
                    INNER JOIN f06a_list_map m ON m.old_id = s.source_list_id
                """)
                conn.execute("""
                    DELETE FROM intersection_list_sources
                    WHERE source_list_id IN (SELECT old_id FROM f06a_list_map)
                """)
                conn.execute("DROP TABLE f06a_list_map")

                # Step 3: delete the extra duplicate root lists, keeping the
                # newest one per name (MAX id). Their list_items and
                # intersection rows were re-homed above; any that remain
                # (e.g. already-existing links) are removed by the FK cascade
                # on the connection's PRAGMA foreign_keys=ON.
                self.logger.info("Removing duplicate root lists (keeping the newest per name)")
                conn.execute("""
                    DELETE FROM lists
                    WHERE folder_id IS NULL
                      AND id NOT IN (
                          SELECT MAX(s.id)
                          FROM lists s
                          WHERE s.folder_id IS NULL
                          GROUP BY s.name
                      )
                """)

                # Step 4: create the partial unique index on root rows.
                conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_root_unique
                    ON lists (name) WHERE folder_id IS NULL
                """)
                self.logger.info("Root-level list name uniqueness index created")

            # Migration from version 11 to 12 (F-06b): enforce root-level
            # folder name uniqueness. The existing unique index
            # idx_folders_name_parent ON folders (name, parent_id) cannot
            # enforce uniqueness among root folders because SQLite treats
            # NULL values as distinct in ordinary UNIQUE indexes
            # (parent_id IS NULL for root folders). This migration:
            #   1. deduplicates any pre-existing duplicate root folders,
            #      keeping the oldest one (MIN id, the original) so
            #      persisted references (startup_folder_id, folder cache
            #      files, export files) keep pointing at the same row;
            #   2. re-homes every relationship that points at a removed
            #      duplicate onto the surviving folder - child folders,
            #      lists, and import sources - before the index can be
            #      created;
            #   3. creates the partial unique index that makes root names
            #      unique among roots while leaving sibling uniqueness
            #      (idx_folders_name_parent) and cross-parent name reuse
            #      (same name under different parents) completely untouched.
            if current_version < 12:
                self.logger.info("Migrating from version 11 to 12: enforcing root-level folder name uniqueness")

                # Step 1: build a deterministic duplicate-root mapping
                # old_id -> new_id (the survivor, MIN(id) per root name
                # group) for every duplicate root folder that must be
                # removed.
                self.logger.info("Building duplicate-root folder mapping for re-homing")
                conn.execute("""
                    CREATE TEMP TABLE IF NOT EXISTS f06b_folder_map (
                        old_id INTEGER PRIMARY KEY,
                        new_id INTEGER NOT NULL
                    )
                """)
                conn.execute("DELETE FROM f06b_folder_map")
                conn.execute("""
                    INSERT INTO f06b_folder_map (old_id, new_id)
                    SELECT f.id,
                           (SELECT MIN(s.id)
                              FROM folders s
                              WHERE s.name = f.name AND s.parent_id IS NULL)
                    FROM folders f
                    WHERE f.parent_id IS NULL
                      AND f.id NOT IN (
                          SELECT MIN(s.id)
                          FROM folders s
                          WHERE s.parent_id IS NULL
                          GROUP BY s.name
                      )
                """)

                # Step 2: re-home child folders from duplicate roots onto
                # the surviving root. Collisions (a child with the same
                # name already exists under the survivor, or the survivor
                # already contains a duplicate root's child with the same
                # name as one of its other children) are handled by
                # renaming the incoming child with a numeric suffix so no
                # user data or hierarchy is lost.
                self.logger.info("Re-homing child folders from duplicate root folders onto the surviving root")
                collision_ids = conn.execute(
                    "SELECT old_id, new_id FROM f06b_folder_map ORDER BY old_id"
                ).fetchall()
                for cid in collision_ids:
                    old_id, new_id = int(cid["old_id"]), int(cid["new_id"])
                    # For each child of the duplicate root, check for a
                    # name collision under the survivor and, if needed,
                    # rename the child to a unique sibling name before
                    # re-homing it.
                    child_rows = conn.execute(
                        "SELECT id, name FROM folders WHERE parent_id = ? ORDER BY id",
                        [old_id],
                    ).fetchall()
                    for child in child_rows:
                        child_id, child_name = int(child["id"]), child["name"]
                        target_name = child_name
                        taken = conn.execute(
                            "SELECT name FROM folders WHERE parent_id = ? AND name = ?",
                            [new_id, child_name],
                        ).fetchall()
                        if taken:
                            # Append a suffix derived from the folder id
                            # (stable, and free of characters that break
                            # folder names) until the name is unique.
                            candidate = "%s (%d)" % (child_name, child_id)
                            while conn.execute(
                                "SELECT 1 FROM folders WHERE parent_id = ? AND name = ?",
                                [new_id, candidate],
                            ).fetchone():
                                candidate = "%s %d" % (candidate, child_id)
                            target_name = candidate
                        # Apply the destination-safe name and parent together.
                        # Renaming first can collide with an existing sibling
                        # under the old duplicate parent.
                        conn.execute(
                            "UPDATE folders SET name = ?, parent_id = ? WHERE id = ?",
                            [target_name, new_id, child_id],
                        )
                        if taken:
                            self.logger.info(
                                "Renamed child folder %s from '%s' to '%s' to avoid sibling collision under folder %s",
                                child_id, child_name, target_name, new_id,
                            )

                # Step 3: re-home lists from duplicate roots onto the
                # surviving root folder. list.folder_id has ON DELETE SET
                # NULL, so deleting a duplicate root without this step
                # would silently move its lists to the root level -
                # user data reorganization, not loss. Lists whose name
                # collides with an existing list under the survivor get a
                # numeric suffix instead (list names are unique per
                # folder via idx_lists_name_folder).
                self.logger.info("Re-homing lists from duplicate root folders onto the surviving root folder")
                for cid in collision_ids:
                    old_id, new_id = int(cid["old_id"]), int(cid["new_id"])
                    list_rows = conn.execute(
                        "SELECT id, name FROM lists WHERE folder_id = ? ORDER BY id",
                        [old_id],
                    ).fetchall()
                    for lst in list_rows:
                        list_id, list_name = int(lst["id"]), lst["name"]
                        target_name = list_name
                        taken = conn.execute(
                            "SELECT 1 FROM lists WHERE folder_id = ? AND name = ?",
                            [new_id, list_name],
                        ).fetchone()
                        if taken:
                            candidate = "%s (%d)" % (list_name, list_id)
                            while conn.execute(
                                "SELECT 1 FROM lists WHERE folder_id = ? AND name = ?",
                                [new_id, candidate],
                            ).fetchone():
                                candidate = "%s %d" % (candidate, list_id)
                            target_name = candidate
                        # Apply the destination-safe name and folder together
                        # so old-folder siblings cannot block the rename.
                        conn.execute(
                            "UPDATE lists SET name = ?, folder_id = ? WHERE id = ?",
                            [target_name, new_id, list_id],
                        )
                        if taken:
                            self.logger.info(
                                "Renamed list %s from '%s' to '%s' to avoid folder collision under folder %s",
                                list_id, list_name, target_name, new_id,
                            )

                # Step 4: re-home import sources pointing at duplicate
                # roots onto the surviving root. import_sources.folder_id
                # is ON DELETE CASCADE, so without this step those rows
                # would be dropped, losing the import provenance and
                # unlocking the import folders' structure.
                self.logger.info("Re-homing import sources from duplicate root folders onto the surviving root folder")
                conn.execute("""
                    UPDATE import_sources
                    SET folder_id = (
                        SELECT m.new_id
                        FROM f06b_folder_map m
                        WHERE m.old_id = import_sources.folder_id
                    )
                    WHERE folder_id IN (SELECT old_id FROM f06b_folder_map)
                """)

                # Step 5 (best effort): remap the persisted
                # startup_folder_id setting if it pointed at a duplicate
                # root that is about to be removed. The app already
                # degrades gracefully for stale folder ids (the main menu
                # validates the folder before redirecting), but remapping
                # keeps the user's configured startup target intact. The
                # survivor folder always exists regardless of whether the
                # rest of this migration commits, so this write is safe
                # in both outcomes.
                try:
                    from lib.config.config_manager import get_config
                    cfg = get_config()
                    startup_id = str(cfg.get("startup_folder_id") or "").strip()
                    if startup_id.isdigit():
                        remap_row = conn.execute(
                            "SELECT new_id FROM f06b_folder_map WHERE old_id = ?",
                            [int(startup_id)],
                        ).fetchone()
                        if remap_row:
                            cfg.set("startup_folder_id", str(remap_row["new_id"]))
                            cfg.invalidate("startup_folder_id")
                            self.logger.info(
                                "Remapped startup_folder_id from %s to %s",
                                startup_id, remap_row["new_id"],
                            )
                except Exception as cfg_err:
                    self.logger.warning(
                        "Could not remap startup_folder_id setting: %s", cfg_err
                    )

                conn.execute("DROP TABLE f06b_folder_map")

                # Step 5: delete the duplicate root folders themselves.
                # All relationships were re-homed in steps 2-4; with
                # PRAGMA foreign_keys=ON any remaining referent is
                # handled by the declared FK action (SET NULL / CASCADE)
                # rather than leaving an orphan.
                self.logger.info("Removing duplicate root folders (keeping the oldest per name)")
                conn.execute("""
                    DELETE FROM folders
                    WHERE parent_id IS NULL
                      AND id NOT IN (
                          SELECT MIN(s.id)
                          FROM folders s
                          WHERE s.parent_id IS NULL
                          GROUP BY s.name
                      )
                """)

                # Step 6: create the partial unique index on root rows.
                conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_root_unique
                    ON folders (name) WHERE parent_id IS NULL
                """)
                self.logger.info("Root-level folder name uniqueness index created")

            # Set final version
            self._set_schema_version(conn, TARGET_SCHEMA_VERSION)
            self.logger.info("Database migration completed successfully")
            
        except Exception as e:
            self.logger.error("Migration failed: %s", e)
            raise
            
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