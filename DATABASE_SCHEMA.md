
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
- Create reserved Search History folder

---

### `media_items`
Core metadata entries for movies, episodes, music videos, or external items. For Kodi library items (`source='lib'`), only core identification fields are populated; rich metadata is fetched from JSON-RPC when needed. For external items (`source='ext'`), all fields may be populated.

| Column       | Type    | Notes |
|--------------|---------|-------|
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `media_type` | TEXT    | `movie`, `episode`, `musicvideo`, `external` |
| `title`      | TEXT    | |
| `year`       | INTEGER | |
| `imdbnumber` | TEXT    | IMDb ID if known |
| `tmdb_id`    | TEXT    | Optional TMDb ID |
| `kodi_id`    | INTEGER | Optional Kodi DBID |
| `source`     | TEXT    | e.g. `lib`, `ext` |
| `play`       | TEXT    | Playback URL or file |
| `poster`     | TEXT    | Poster artwork (external items only) |
| `fanart`     | TEXT    | Fanart artwork (external items only) |
| `plot`       | TEXT    | Plot summary |
| `rating`     | REAL    | Rating (external items only) |
| `votes`      | INTEGER | Vote count (external items only) |
| `duration`   | INTEGER | Duration in seconds (external items only) |
| `mpaa`       | TEXT    | MPAA rating (external items only) |
| `genre`      | TEXT    | Comma-separated genres (external items only) |
| `director`   | TEXT    | Director (external items only) |
| `studio`     | TEXT    | Studio (external items only) |
| `country`    | TEXT    | Country (external items only) |
| `writer`     | TEXT    | Writer (external items only) |
| `cast`       | TEXT    | JSON cast data (external items only) |
| `art`        | TEXT    | JSON art data (external items only) |
| `created_at` | TEXT    | |

Indexes:
- INDEX on `imdbnumber`.
- INDEX on `(media_type, kodi_id)`.
- INDEX on `title COLLATE NOCASE`.
- INDEX on `year`.

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

### `kodi_favorite`
Stores Kodi favorites with mapping to library movies.

| Column                 | Type    | Notes |
|------------------------|---------|-------|
| `id`                   | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name`                 | TEXT    | NOT NULL - favorite display name |
| `normalized_path`      | TEXT    | Normalized path for matching |
| `original_path`        | TEXT    | Original path from favorites |
| `favorite_type`        | TEXT    | Type classification |
| `target_raw`           | TEXT    | NOT NULL - raw target data |
| `target_classification`| TEXT    | NOT NULL - classification result |
| `normalized_key`       | TEXT    | NOT NULL UNIQUE - normalized identifier |
| `library_movie_id`     | INTEGER | FK → media_items.id (nullable) |
| `is_mapped`            | INTEGER | DEFAULT 0 - whether mapped to library |
| `is_missing`           | INTEGER | DEFAULT 0 - whether target is missing |
| `present`              | INTEGER | DEFAULT 1 - whether favorite is active |
| `thumb_ref`            | TEXT    | Thumbnail reference |
| `first_seen`           | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `last_seen`            | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `created_at`           | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `updated_at`           | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

Constraints:
- FOREIGN KEY (library_movie_id) REFERENCES media_items (id)

Indexes:
- INDEX on `normalized_key`.
- INDEX on `library_movie_id`.
- INDEX on `is_mapped`.
- INDEX on `present`.

**Note**: Kodi Favorites are also integrated into the unified lists system. A special list named "Kodi Favorites" is created in the `lists` table, and mapped favorites are added as `list_items` pointing to `media_items`.

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
Lightweight table for export/import matching.

| Column     | Type    | Notes |
|------------|---------|-------|
| `id`       | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `imdb_id`  | TEXT    | |
| `title`    | TEXT    | |
| `year`     | INTEGER | |
| `created_at` | TEXT  | |

Indexes:
- INDEX on `imdb_id`.

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

**Note**: There is a typo in the actual implementation where `PRIMARY KEY` is misspelled as `PRIMARYKEY`.

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

### `schema_version`
Tracks database schema version for migrations.

| Column       | Type    | Notes |
|--------------|---------|-------|
| `version`    | INTEGER | PRIMARY KEY - schema version number |
| `applied_at` | TEXT    | NOT NULL - when migration was applied |

---

## Implementation Notes

### SQL Syntax Issues
The current implementation has several SQL syntax errors that need to be addressed:

1. **PRIMARY KEY Typos**: Several tables use `PRIMARYKEY` instead of `PRIMARY KEY AUTOINCREMENT`
2. **Missing AUTOINCREMENT**: Some tables are missing the `AUTOINCREMENT` keyword

These issues may prevent proper database initialization and should be fixed in the migration code.

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

---

## Relationships

- One-to-many: folders → lists.  
- One-to-many: lists → list_items → media_items.  
- One-to-one/many: media_items ↔ movie_heavy_meta.  
- One-to-many: media_items ← kodi_favorite (via library_movie_id).
- Many-to-many mapping: imdb_to_kodi.  
- Special relationship: kodi_favorite entries can also appear as list_items in the "Kodi Favorites" list.

---

## Notes

- IMDb is the primary identifier for portability.  
- All fallbacks (TMDb, title/year, season/episode, artist/track) are secondary.  
- Schema designed for **resilience** (recovery after Kodi crash, portable export/import).
- Kodi favorites are mapped to media_items via library_movie_id for integration with lists.
- The main table for media storage is `media_items`, not `library_movie`.
- Database is created fresh on first startup with complete schema
- Migration framework preserved for future incremental updates
- No legacy migration compatibility - clean slate approachn future migrations.
