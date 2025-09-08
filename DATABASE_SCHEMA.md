# LibraryGenie Database Schema

This document describes the SQLite database schema used by LibraryGenie for storing lists, folders, media references, and Kodi favorites.

---

## Overview

- SQLite backend with WAL and tuned PRAGMAs for low-power devices.
- Transaction-safe operations with UNIQUE constraints to prevent duplicates.
- Schema supports mixed media (movies, episodes, music videos, external items).
- Primary keys are auto-increment integer IDs.
- All timestamp fields use ISO 8601 format (`YYYY-MM-DD HH:MM:SS`).

---

## Tables

### `lists`
Stores user-created lists.

| Column      | Type    | Notes |
|-------------|---------|-------|
| `id`        | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name`      | TEXT    | NOT NULL |
| `folder_id` | INTEGER | FK → folders.id (nullable) |
| `created_at`| TEXT    | timestamp |

Constraints:
- UNIQUE(name, folder_id) to prevent duplicate list names in the same folder.

---

### `folders`
Hierarchical folder structure for organizing lists.

| Column      | Type    | Notes |
|-------------|---------|-------|
| `id`        | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name`      | TEXT    | NOT NULL |
| `parent_id` | INTEGER | FK → folders.id (nullable) |
| `created_at`| TEXT    | timestamp |

Constraints:
- UNIQUE(name, parent_id).
- Creates reserved "Search History" folder during initialization

---

## Media Items (`media_items`)

The unified table for storing all media content metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `media_type` | TEXT | Type: 'movie', 'episode', 'season', 'tvshow' |
| `title` | TEXT | Media title |
| `year` | INTEGER | Release year |
| `imdbnumber` | TEXT | IMDb identifier (primary for portability) |
| `tmdb_id` | TEXT | TMDb identifier |
| `kodi_id` | INTEGER | Kodi database ID (movieid, episodeid, etc.) |
| `source` | TEXT | Source classification (e.g., 'library', 'external') |
| `play` | TEXT | Play command or URL |
| `plot` | TEXT | Plot/description |
| `rating` | REAL | Rating score |
| `votes` | INTEGER | Number of votes |
| `duration` | INTEGER | Duration in minutes |
| `mpaa` | TEXT | Content rating |
| `genre` | TEXT | Genre information |
| `director` | TEXT | Director name |
| `studio` | TEXT | Studio/production company |
| `country` | TEXT | Country of origin |
| `writer` | TEXT | Writer information |
| `cast` | TEXT | Cast information (JSON) |
| `art` | TEXT | Additional artwork (JSON) |
| `file_path` | TEXT | Original file path |
| `normalized_path` | TEXT | Normalized file path for matching |
| `is_removed` | INTEGER | Flag indicating if item was removed (0/1) |
| `display_title` | TEXT | Pre-computed display title with year |
| `duration_seconds` | INTEGER | Duration in seconds (pre-computed) |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

---

### `list_items`
Associates media items with lists.

| Column         | Type    | Notes |
|----------------|---------|-------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `list_id`      | INTEGER | FK → lists.id |
| `media_item_id`| INTEGER | FK → media_items.id |
| `position`     | INTEGER | ordering |
| `created_at`   | TEXT    | |

Constraints:
- UNIQUE(list_id, media_item_id) prevents duplicates in the same list.
- INDEX on `(list_id, position)`.

---

## Kodi Favorites (`kodi_favorite`)

Maps Kodi favorites to library items for integration.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `name` | TEXT | Favorite display name |
| `normalized_path` | TEXT | Normalized path for matching |
| `original_path` | TEXT | Original favorite path |
| `favorite_type` | TEXT | Type of favorite |
| `target_raw` | TEXT | Raw target command |
| `target_classification` | TEXT | Classification of target |
| `normalized_key` | TEXT UNIQUE | Unique key for deduplication |
| `media_item_id` | INTEGER FK | Reference to media_items.id |
| `is_mapped` | INTEGER | Whether favorite is mapped (0/1) |
| `is_missing` | INTEGER | Whether favorite target is missing (0/1) |
| `present` | INTEGER | Whether favorite is present in current scan (0/1) |
| `thumb_ref` | TEXT | Thumbnail reference |
| `first_seen` | TEXT | When first detected |
| `last_seen` | TEXT | When last seen |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

Constraints:
- FOREIGN KEY (media_item_id) REFERENCES media_items (id)

Indexes:
- INDEX on `normalized_key`.
- INDEX on `media_item_id`.
- INDEX on `is_mapped`.
- INDEX on `present`.

**Note**: The `media_items` table serves as the primary source for all list operations and UI building. During library scanning, comprehensive lightweight metadata is stored here to eliminate the need for JSON-RPC batch calls during list rendering. Heavy metadata (cast, streamdetails) is stored separately to maintain performance.

Kodi Favorites are also integrated into the unified lists system. A special list named "Kodi Favorites" is created in the `lists` table, and mapped favorites are added as `list_items` pointing to `media_items`. The favorites handler is registered with the router using the action name "kodi_favorites". Context menus are handled globally via addon.xml registration instead of per-item context menu generation.

---

### `favorites_scan_log`
Records favorites scan operations and their results.

| Column             | Type    | Notes |
|--------------------|---------|-------|
| `id`               | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `scan_type`        | TEXT    | NOT NULL - type of scan performed |
| `file_path`        | TEXT    | NOT NULL - path to favorites file |
| `file_modified`    | TEXT    | File modification timestamp |
| `items_found`      | INTEGER | DEFAULT 0 - favorites found in file |
| `items_mapped`     | INTEGER | DEFAULT 0 - favorites mapped to library |
| `items_added`      | INTEGER | DEFAULT 0 - new favorites added |
| `items_updated`    | INTEGER | DEFAULT 0 - existing favorites updated |
| `scan_duration_ms` | INTEGER | DEFAULT 0 - scan duration in milliseconds |
| `success`          | INTEGER | DEFAULT 1 - whether scan succeeded |
| `error_message`    | TEXT    | Error message if scan failed |
| `created_at`       | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

Indexes:
- INDEX on `file_path`.
- INDEX on `created_at`.

---

### `movie_heavy_meta`
Extended metadata for movies/episodes.

| Column         | Type    | Notes |
|----------------|---------|-------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `kodi_movieid` | INTEGER | Kodi DBID |
| `imdbnumber`   | TEXT    | |
| `cast_json`    | TEXT    | JSON |
| `ratings_json` | TEXT    | JSON |
| `showlink_json`| TEXT    | JSON |
| `stream_json`  | TEXT    | JSON |
| `uniqueid_json`| TEXT    | JSON |
| `tags_json`    | TEXT    | JSON |
| `updated_at`   | TEXT    | |

---

### `search_history`
Stores search query history and performance metrics.

| Column               | Type    | Notes |
|----------------------|---------|-------|
| `id`                 | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `query_text`         | TEXT    | NOT NULL - search query |
| `scope_type`         | TEXT    | NOT NULL DEFAULT 'library' |
| `scope_id`           | INTEGER | Scope identifier |
| `year_filter`        | TEXT    | Year filter applied |
| `sort_method`        | TEXT    | NOT NULL DEFAULT 'title_asc' |
| `include_file_path`  | INTEGER | NOT NULL DEFAULT 0 |
| `result_count`       | INTEGER | NOT NULL DEFAULT 0 |
| `search_duration_ms` | INTEGER | NOT NULL DEFAULT 0 |
| `created_at`         | TEXT    | NOT NULL DEFAULT (datetime('now')) |

---

### `search_preferences`
Stores user search preferences.

| Column             | Type    | Notes |
|--------------------|---------|-------|
| `id`               | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `preference_key`   | TEXT    | NOT NULL UNIQUE |
| `preference_value` | TEXT    | NOT NULL |
| `created_at`       | TEXT    | NOT NULL DEFAULT (datetime('now')) |
| `updated_at`       | TEXT    | NOT NULL DEFAULT (datetime('now')) |

---

### `ui_preferences`
Stores UI-related user preferences.

| Column                   | Type    | Notes |
|--------------------------|---------|-------|
| `id`                     | INTEGER | PRIMARY KEY |
| `ui_density`             | TEXT    | NOT NULL DEFAULT 'compact' |
| `artwork_preference`     | TEXT    | NOT NULL DEFAULT 'poster' |
| `show_secondary_label`   | INTEGER | NOT NULL DEFAULT 1 |
| `show_plot_in_detailed`  | INTEGER | NOT NULL DEFAULT 1 |
| `fallback_icon`          | TEXT    | DEFAULT 'DefaultVideo.png' |
| `updated_at`             | TEXT    | NOT NULL DEFAULT (datetime('now')) |

**Note**: This table uses a fixed ID of 1 for a single-row configuration pattern.

---

### `imdb_exports`
Lightweight table for export/import/backup matching with enhanced metadata.

| Column     | Type    | Notes |
|------------|---------|-------|
| `id`       | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `imdb_id`  | TEXT    | Primary identifier |
| `tmdb_id`  | TEXT    | TMDb identifier for fallback |
| `kodi_id`  | INTEGER | Kodi database ID |
| `title`    | TEXT    | Media title |
| `year`     | INTEGER | Release year |
| `file_path`| TEXT    | Original file path |
| `created_at` | TEXT  | Creation timestamp |

Indexes:
- INDEX on `imdb_id`.
- INDEX on `tmdb_id`.
- INDEX on `kodi_id`.

---

### `imdb_to_kodi`
Mapping table for fast lookups.

| Column     | Type    | Notes |
|------------|---------|-------|
| `imdb_id`  | TEXT    | |
| `kodi_id`  | INTEGER | |
| `media_type` | TEXT  | |

Constraints:
- UNIQUE(imdb_id, kodi_id, media_type).

---

### `library_scan_log`
Records library scan operations and their results.

| Column         | Type    | Notes |
|----------------|---------|-------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `scan_type`    | TEXT    | `full`, `delta` |
| `kodi_version` | INTEGER | Kodi major version when scan was performed |
| `start_time`   | TEXT    | ISO 8601 timestamp |
| `end_time`     | TEXT    | ISO 8601 timestamp (nullable) |
| `total_items`  | INTEGER | Items found during scan |
| `items_added`  | INTEGER | Items added to index |
| `items_updated`| INTEGER | Items updated in index |
| `items_removed`| INTEGER | Items removed from index |
| `error`        | TEXT    | Error message if scan failed |
| `created_at`   | TEXT    | Record creation timestamp |

Indexes:
- INDEX on `(scan_type, start_time)`.

---

### `kv_cache`
Generic key-value cache.

| Column     | Type    | Notes |
|------------|---------|-------|
| `key`      | TEXT    | PRIMARY KEY |
| `value`    | TEXT    | |
| `updated_at`| TEXT   | |

---

### `sync_state` (CLIENT-KODI-SERVICE)
Stores differential sync state for efficient client-server synchronization.

| Column              | Type    | Notes |
|---------------------|---------|-------|
| `id`                | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `local_snapshot`    | TEXT    | JSON array of normalized IMDb IDs |
| `server_version`    | TEXT    | Server version/etag from last sync |
| `server_etag`       | TEXT    | Server ETag for cache validation |
| `last_sync_at`      | TEXT    | Timestamp of last successful sync |
| `server_url`        | TEXT    | Base server URL |

---

### `auth_state` (CLIENT-KODI-SERVICE)
Stores authentication token and expiry information.

| Column         | Type    | Notes |
|----------------|---------|-------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `access_token` | TEXT    | Bearer token for API access |
| `expires_at`   | TEXT    | Token expiry timestamp |
| `token_type`   | TEXT    | Usually "Bearer" |
| `scope`        | TEXT    | Token permissions |

---

### `pending_operations` (CLIENT-KODI-SERVICE)
Queues sync operations that failed due to network issues for retry.

| Column         | Type    | Notes |
|----------------|---------|-------|
| `id`           | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `operation`    | TEXT    | `add` or `remove` |
| `imdb_ids`     | TEXT    | JSON array of IMDb IDs |
| `created_at`   | TEXT    | When operation was queued |
| `retry_count`  | INTEGER | Number of retry attempts |
| `idempotency_key` | TEXT | Unique key for safe retries |

Indexes:
- INDEX on `(operation, created_at)` for FIFO processing.

---

### `backup_history`
Records backup operations and retention management.

| Column              | Type    | Notes |
|---------------------|---------|-------|
| `id`                | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `backup_type`       | TEXT    | 'automatic' or 'manual' |
| `filename`          | TEXT    | NOT NULL - backup filename |
| `file_path`         | TEXT    | NOT NULL - full file path |
| `storage_type`      | TEXT    | NOT NULL - 'local' |
| `export_types`      | TEXT    | JSON array of included types |
| `file_size`         | INTEGER | Backup file size in bytes |
| `items_count`       | INTEGER | Total items in backup |
| `success`           | INTEGER | DEFAULT 1 - whether backup succeeded |
| `error_message`     | TEXT    | Error message if backup failed |
| `created_at`        | TEXT    | NOT NULL DEFAULT (datetime('now')) |

Indexes:
- INDEX on `backup_type`.
- INDEX on `created_at`.
- INDEX on `storage_type`.

### `backup_preferences`
Stores backup configuration and preferences.

| Column                | Type    | Notes |
|-----------------------|---------|-------|
| `id`                  | INTEGER | PRIMARY KEY |
| `auto_backup_enabled` | INTEGER | NOT NULL DEFAULT 0 |
| `backup_interval_days`| INTEGER | NOT NULL DEFAULT 7 |
| `max_backups_to_keep` | INTEGER | NOT NULL DEFAULT 5 |
| `backup_location`     | TEXT    | NOT NULL DEFAULT 'special://userdata/addon_data/script.librarygenie/backups/' |
| `last_auto_backup`    | TEXT    | Last automatic backup timestamp |
| `updated_at`          | TEXT    | NOT NULL DEFAULT (datetime('now')) |

**Note**: This table uses a fixed ID of 1 for a single-row configuration pattern.

### `schema_version`
Tracks database schema version for migrations.

| Column       | Type    | Notes |
|--------------|---------|-------|
| `version`    | INTEGER | PRIMARY KEY - schema version number |
| `applied_at` | TEXT    | NOT NULL - when migration was applied |

---

## Implementation Notes

### Database Initialization
The database is created with a complete schema on first startup. Migration framework is preserved for future incremental updates, but no legacy compatibility is maintained - this ensures a clean implementation without historical baggage.

### Favorites Integration
Kodi favorites are handled through a dual approach:
1. **Direct Storage**: Favorites are stored in the `kodi_favorite` table with detailed metadata
2. **List Integration**: Mapped favorites are also added to a special "Kodi Favorites" list in the unified `lists`/`list_items` system

This allows favorites to be treated like any other list while maintaining the detailed favorite-specific metadata.

### Default Data
The schema includes these default entries on initialization:
- A "Search History" folder in the `folders` table
- Default search preferences in `search_preferences`
- Default UI preferences in `ui_preferences` (single row with ID=1)
- Default backup preferences with weekly scheduling disabled

### Backup System
The backup system provides:
- **Unified Format**: Uses the same NDJSON engine as export functionality
- **Enhanced Metadata**: Includes additional identifiers for robust recovery
- **Flexible Storage**: Local paths and network shares via Kodi file settings
- **Automated Scheduling**: Configurable intervals with timestamp-based naming
- **Retention Management**: Automatic cleanup of old backups based on policies

### Authentication and Sync
The auth and sync tables support optional external service integration:
- Device code OAuth2 flow for secure authorization
- Differential sync with local snapshots and server ETags
- Pending operations queue for offline resilience
- Token refresh and expiry handling

---

## Relationships

- One-to-many: folders → lists.  
- One-to-many: lists → list_items → media_items.  
- One-to-one/many: media_items ↔ movie_heavy_meta.  
- One-to-many: media_items ← kodi_favorite (via media_item_id).
- Many-to-many mapping: imdb_to_kodi.  
- Special relationship: kodi_favorite entries can also appear as list_items in the "Kodi Favorites" list.

---

## Notes

- IMDb is the primary identifier for portability (`imdbnumber` field in `media_items`).  
- All fallbacks (TMDb, title/year, season/episode, artist/track) are secondary.  
- Schema designed for **resilience** (recovery after Kodi crash, portable export/import).
- Kodi favorites are mapped to media_items via media_item_id for integration with lists.
- The main table for media storage is `media_items`, not `library_movie`.
- Database is created fresh on first startup with complete schema.
- Migration framework preserved for future incremental updates.
- No legacy migration compatibility - clean slate approach ensures reliable operation.