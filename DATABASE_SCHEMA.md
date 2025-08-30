# LibraryGenie Database Schema

This document describes the SQLite database schema used by LibraryGenie for storing lists, folders, and media references.

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
            conn.execute("""
                INSERT INTO folders (name, parent_id)
                VALUES ('Search History', NULL)
            """)

            # No default lists - users will create their own

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

## Relationships

- One-to-many: folders → lists.  
- One-to-many: lists → list_items → media_items.  
- One-to-one/many: media_items ↔ movie_heavy_meta.  
- Many-to-many mapping: imdb_to_kodi.  

---

## Notes

- IMDb is the primary identifier for portability.  
- All fallbacks (TMDb, title/year, season/episode, artist/track) are secondary.  
- Schema designed for **resilience** (recovery after Kodi crash, portable export/import).