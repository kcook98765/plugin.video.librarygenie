# LibraryGenie Database Schema

## Overview
LibraryGenie uses SQLite with WAL (Write-Ahead Logging) mode for improved concurrency and performance. The database schema includes tables for lists, folders, media items, Kodi favorites, search history, bookmarks, and various system preferences.

## Current Schema Version: 4

## Core Tables

### bookmarks
Stores user-created bookmarks/links to various folder locations and content sources.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `url` | TEXT NOT NULL | Original URL for navigation (may contain credentials) |
| `normalized_url` | TEXT NOT NULL | Canonicalized URL for deduplication |
| `display_name` | TEXT NOT NULL | User-friendly name for the bookmark |
| `bookmark_type` | TEXT NOT NULL | Type of bookmark (plugin, file, network, library, special) |
| `description` | TEXT | Optional description |
| `metadata` | TEXT | JSON metadata (path info, credentials, parameters) |
| `art_data` | TEXT | JSON art/icon data |
| `folder_id` | INTEGER | Optional organization folder (FK to folders.id) |
| `position` | INTEGER | Sort position within folder |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

**Constraints:**
- `UNIQUE(folder_id, normalized_url)` - Prevent duplicate bookmarks within folder
- `CHECK (bookmark_type IN ('plugin','file','network','library','special'))` - Valid types
- `FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL`

**Indexes:**
- `idx_bookmarks_unique` on `folder_id, normalized_url` (unique constraint)
- `idx_bookmarks_type` on `bookmark_type`
- `idx_bookmarks_folder` on `folder_id`
- `idx_bookmarks_position` on `folder_id, position`
- `idx_bookmarks_display_name` on `folder_id, lower(display_name)`
- `idx_bookmarks_updated` on `updated_at`

### lists
Stores user-created lists containing media items.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `name` | TEXT NOT NULL | List name |
| `folder_id` | INTEGER | Parent folder (FK to folders.id) |
| `created_at` | TEXT | Creation timestamp |

**Constraints:**
- `UNIQUE(name, folder_id)` - Prevent duplicate list names in same folder

### folders
Hierarchical folder structure for organizing lists and bookmarks.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `name` | TEXT NOT NULL | Folder name |
| `parent_id` | INTEGER | Parent folder (FK to folders.id) |
| `created_at` | TEXT | Creation timestamp |

**Constraints:**
- `UNIQUE(name, parent_id)` - Prevent duplicate folder names in same parent

### media_items
Central table storing comprehensive lightweight metadata for all media.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `media_type` | TEXT NOT NULL | Type: movie, episode, etc. |
| `title` | TEXT | Media title |
| `year` | INTEGER | Release year |
| `imdbnumber` | TEXT | IMDb ID |
| `tmdb_id` | TEXT | TMDB ID |
| `kodi_id` | INTEGER | Kodi library ID |
| `source` | TEXT | Source information |
| `play` | TEXT | Playback path |
| `plot` | TEXT | Description/plot |
| `rating` | REAL | Rating score |
| `votes` | INTEGER | Vote count |
| `duration` | INTEGER | Duration in minutes |
| `mpaa` | TEXT | Rating (PG, R, etc.) |
| `genre` | TEXT | Genre information |
| `director` | TEXT | Director name |
| `studio` | TEXT | Studio/production company |
| `country` | TEXT | Country of origin |
| `writer` | TEXT | Writer/screenplay |
| `cast` | TEXT | Cast information |
| `art` | TEXT | JSON artwork data |
| `file_path` | TEXT | File system path |
| `normalized_path` | TEXT | Normalized path for matching |
| `is_removed` | INTEGER | Removal flag (0/1) |
| `display_title` | TEXT | Computed display title |
| `duration_seconds` | INTEGER | Duration in seconds |
| `tvshowtitle` | TEXT | TV show title (for episodes) |
| `season` | INTEGER | Season number |
| `episode` | INTEGER | Episode number |
| `aired` | TEXT | Air date |
| `tvshow_kodi_id` | INTEGER | TV show's Kodi ID |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

### list_items
Junction table connecting lists to media items.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `list_id` | INTEGER NOT NULL | List reference (FK to lists.id) |
| `media_item_id` | INTEGER NOT NULL | Media reference (FK to media_items.id) |
| `position` | INTEGER | Sort position |
| `created_at` | TEXT | Creation timestamp |

**Constraints:**
- `UNIQUE(list_id, media_item_id)` - Prevent duplicate items in same list

### kodi_favorite
Integration with Kodi's favorites system.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `name` | TEXT NOT NULL | Favorite display name |
| `normalized_path` | TEXT | Normalized path for matching |
| `original_path` | TEXT | Original favorite path |
| `favorite_type` | TEXT | Type of favorite |
| `target_raw` | TEXT NOT NULL | Raw target command |
| `target_classification` | TEXT NOT NULL | Classification of target |
| `normalized_key` | TEXT UNIQUE | Unique key for deduplication |
| `media_item_id` | INTEGER | Reference to media_items.id |
| `is_mapped` | INTEGER | Whether favorite is mapped (0/1) |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

## System Tables

### schema_version
Tracks database schema version for migrations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Always 1 (single row) |
| `version` | INTEGER NOT NULL | Current schema version |
| `applied_at` | TEXT NOT NULL | Application timestamp |

### search_history
Stores search query history and performance metrics.

### ui_preferences
User interface preferences and settings.

### sync_state
Synchronization state for multi-device scenarios.

### auth_state
Authentication state for external services.

### pending_operations
Queue for background operations.

### remote_cache
Cache for external API responses.

### sync_snapshot
Snapshot data for efficient delta detection.

## Indexes

The schema includes comprehensive indexes for performance:
- Primary key indexes (automatic)
- Foreign key indexes for joins
- Query-specific indexes for common operations
- Composite indexes for multi-column queries

## Migration Strategy

Schema changes increment the `TARGET_SCHEMA_VERSION` in `lib/data/migrations.py`. The migration system ensures clean initialization for new databases while preserving data for existing installations.