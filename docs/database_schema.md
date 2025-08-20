# LibraryGenie Database Schema Documentation

This document describes the complete database schema for the LibraryGenie Kodi addon, including all tables, their structure, purpose, and data flow.

## Overview

LibraryGenie uses SQLite as its local database to store lists, folders, media items, search history, and library synchronization data. The database is managed through the `DatabaseManager` and `QueryManager` classes.

## Core Tables

### 1. folders
**Purpose**: Hierarchical organization of lists into nested folder structures.

```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    parent_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Data Sources**:
- **Writes**: User creates folders through UI (`DatabaseManager.insert_folder`)
- **Reads**: Folder browser UI (`DatabaseManager.fetch_folders`, `DatabaseManager.fetch_all_folders`)

**Key Features**:
- Supports hierarchical nesting with configurable depth limits
- Special "Search History" folder is automatically created and protected

### 2. lists
**Purpose**: Contains list definitions and metadata.

```sql
CREATE TABLE lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER,
    name TEXT UNIQUE,
    query TEXT,
    protected INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Data Sources**:
- **Writes**: User creates lists, search results auto-saved (`DatabaseManager.insert_data`)
- **Reads**: List browser, list management UI (`DatabaseManager.fetch_lists`, `DatabaseManager.fetch_all_lists`)

**Key Features**:
- `protected` column prevents deletion of system-generated lists
- `query` field stores original search queries for dynamic lists
- Protected column is automatically added via `_ensure_protected_column()` method

### 3. media_items
**Purpose**: Central repository for all media metadata from various sources.

```sql
CREATE TABLE media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cast TEXT,
    country TEXT,
    dateadded TEXT,
    director TEXT,
    duration INTEGER,
    fanart TEXT,
    genre TEXT,
    imdbnumber TEXT,
    kodi_id INTEGER,
    media_type TEXT DEFAULT 'movie',
        file TEXT
    )
```

**Data Sources**:
- **Writes**: 
  - Remote API search results (`DatabaseManager.search_remote_movies`)
  - Search history preservation (`DatabaseManager.add_search_history`)
- **Reads**: List item display, media playback (`DatabaseManager.fetch_list_items`)

**Key Features**:
- `source` field tracks origin: 'Lib', 'external', etc.
- `kodi_id` links to Kodi library entries when available
- `imdbnumber` provides cross-referencing capability
- `search_score` preserves semantic search relevance
- `cast` field stores JSON-encoded cast arrays

### 4. list_items
**Purpose**: Many-to-many relationship between lists and media items.

```sql
CREATE TABLE list_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER,
    media_item_id INTEGER,
    FOREIGN KEY (list_id) REFERENCES lists (id),
    FOREIGN KEY (media_item_id) REFERENCES media_items (id)
)
```

**Data Sources**:
- **Writes**: Adding items to lists (`QueryManager.insert_list_item`)
- **Reads**: List content display (`DatabaseManager.fetch_list_items`)

**Key Features**:
- Enables items to belong to multiple lists
- Cascading deletes when lists are removed

## Search and AI Tables



### 5. original_requests
**Purpose**: Archives original LLM API requests and responses.

```sql
CREATE TABLE original_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT,
    response_json TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Data Sources**:
- **Writes**: LLM API interactions (`DatabaseManager.insert_original_request`)
- **Reads**: Request history analysis (`QueryManager.save_llm_response`)

### 6. parsed_movies
**Purpose**: Stores parsed movie data from LLM responses.

```sql
CREATE TABLE parsed_movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    title TEXT,
    year INTEGER,
    director TEXT,
    FOREIGN KEY (request_id) REFERENCES original_requests (id)
)
```

**Data Sources**:
- **Writes**: LLM response parsing (`DatabaseManager.insert_parsed_movie`)
- **Reads**: Movie matching and validation

## Library Synchronization Tables

### 7. movies_reference
**Purpose**: Reference table for Kodi library synchronization and export functionality.

```sql
CREATE TABLE movies_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    file_name TEXT,
    movieid INTEGER,
    imdbnumber TEXT,
    tmdbnumber TEXT,
    tvdbnumber TEXT,
    addon_file TEXT,
    source TEXT NOT NULL CHECK(source IN ('Lib','File'))
)
```

**Data Sources**:
- **Writes**: Library sync operations via DatabaseManager and QueryManager
- **Reads**: Export and matching operations

**Key Features**:
- `source` differentiates library entries ('Lib') from addon files ('File')
- Unique indexes prevent duplicates based on source type
- Managed by DatabaseManager and QueryManager classes

### 8. imdb_exports
**Purpose**: Tracks movies exported for remote API synchronization.

```sql
CREATE TABLE imdb_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kodi_id INTEGER,
    title TEXT,
    year INTEGER,
    imdb_id TEXT,
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Data Sources**:
- **Writes**: Library export operations (`DatabaseManager.insert_imdb_export`)
- **Reads**: Export statistics and validation (`DatabaseManager.get_imdb_export_stats`)

### 9. search_history
**Purpose**: Tracks individual search queries and metadata for search history management.

```sql
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    list_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (list_id) REFERENCES lists (id)
)
```

**Data Sources**:
- **Writes**: Search operations via `DatabaseManager.add_search_history()`
- **Reads**: Search history display and management

**Key Features**:
- Links search queries to their resulting lists
- Provides audit trail for search operations
- Supports search history browsing functionality

### 10. user_settings
**Purpose**: Stores user-specific settings and preferences.

```sql
CREATE TABLE user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Data Sources**:
- **Writes**: Settings management operations
- **Reads**: Configuration retrieval

**Key Features**:
- Key-value storage for user preferences
- Timestamp tracking for settings changes
- Unique constraint on setting keys

## Data Flow Patterns

### Search History Flow
1. User performs semantic search via `RemoteAPIClient`
2. Results stored in `media_items` with `source='Lib'`
3. Automatic list created in "Search History" folder with `protected=0` (lists in Search History can be managed)
4. Items linked via `list_items` table
5. Search preserved permanently for future reference with timestamped list names

### List Management Flow
1. User creates folder structure in `folders` table
2. Lists created and linked to folders via `folder_id`
3. Media items added to `media_items` from various sources
4. Relationships established in `list_items` table
5. UI reads hierarchical structure for display

### Library Synchronization Flow
1. JSONRPCManager scans Kodi library via JSON-RPC API
2. Movie metadata stored in `movies_reference` with proper source tracking
3. IMDB IDs extracted from both `imdbnumber` field and `uniqueid` object
4. Export data prepared in `imdb_exports`
5. Remote API receives synchronized library data via `IMDbUploadManager`

## Heavy Fields Caching System

### Overview
LibraryGenie implements a performance optimization system that separates frequently-accessed "light" fields from resource-intensive "heavy" fields during JSON-RPC operations with Kodi.

### Heavy Fields Definition
The following fields are considered "heavy" due to their processing overhead:
- **`cast`** - Actor/actress information (large JSON arrays)
- **`ratings`** - Rating information from multiple sources (complex objects)
- **`showlink`** - TV show link information (arrays)
- **`streamdetails`** - Technical stream information (complex nested objects)
- **`uniqueid`** - External database IDs (objects with multiple ID sources)
- **`tag`** - User-defined tags (arrays)

### Caching Storage
Heavy fields are cached in the `movie_heavy_meta` table:
- **Primary Key**: `kodi_movieid` (links to Kodi's internal movie ID)
- **Storage Format**: JSON blobs for fast serialization/deserialization
- **Update Strategy**: Full replacement on library scans with timestamp tracking
- **Indexing**: Indexed on both `kodi_movieid` and `imdbnumber` for fast lookups

### Performance Strategy
1. **Full Library Scans**: Request all fields (light + heavy) and cache heavy fields in batched transactions
2. **List Operations**: Request only light fields via JSON-RPC, then merge heavy fields from local cache
3. **Fallback Handling**: If heavy data is missing, populate with appropriate empty values rather than additional JSON-RPC calls
4. **Transaction Batching**: Heavy field caching uses `BEGIN IMMEDIATE` transactions for reduced fsync overhead

### Benefits
- **Faster List Rendering**: 50-80% reduction in JSON-RPC response time for list views
- **Reduced Kodi Load**: Fewer complex field requests during frequent operations
- **Graceful Degradation**: Missing cache data doesn't break functionality
- **Storage Efficiency**: Heavy fields stored as compressed JSON blobs

## Database Connection Management

### Connection Pooling and Retry Logic
- `QueryManager` implements connection pooling with retry mechanisms
- `_execute_with_retry()` method handles database locks with exponential backoff
- Connection timeouts set to 30 seconds for better reliability
- WAL (Write-Ahead Logging) mode enabled for better concurrency

### Performance Optimizations
```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = MEMORY;
```

## Database Indexes

The database includes several indexes for performance:

```sql
-- Unique constraints for library entries
CREATE UNIQUE INDEX idx_movies_lib_unique
    ON movies_reference(file_path, file_name)
    WHERE source = 'Lib';

-- Unique constraints for addon file entries  
CREATE UNIQUE INDEX idx_movies_file_unique
    ON movies_reference(addon_file)
    WHERE source = 'File';
```

## Configuration and Field Mapping

### Config Class Integration
The `Config` class defines field mappings that align with database schema:
- `FIELDS` array maps to `media_items` table columns
- Singleton pattern ensures consistent field definitions
- Used for both database operations and Kodi ListItem building

### Field Data Types and Handling
- **JSON Fields**: `cast` arrays are JSON-encoded before storage
- **List Fields**: `country`, `director`, `genre`, `studio`, `writer` converted from arrays to comma-separated strings
- **Integer Fields**: `kodi_id`, `duration`, `votes`, `year` with proper type validation
- **Float Fields**: `rating`, `search_score` with default values

## Search History Management

### Automatic Preservation
- Every search automatically creates a timestamped list in "Search History" folder
- Search results store only IMDB IDs and scores initially
- Title/year data populated from `imdb_exports` table when available
- Lists are not protected (can be deleted, renamed, or moved)

### Search History Folder Protection
- "Search History" folder is automatically created if missing
- Folder itself cannot be deleted, renamed, or moved
- Contains individual search result lists that are fully manageable

## Key Manager Classes

- **resources.lib.data.database_manager.DatabaseManager**: High-level database operations, singleton pattern with retry logic
- **resources.lib.data.query_manager.QueryManager**: Low-level SQL execution with connection pooling and management
- **resources.lib.data.dao.listing_dao.ListingDAO**: Data Access Object for folder and list operations, receives injected query executor
- **resources.lib.integrations.jsonrpc.jsonrpc_manager.JSONRPCManager**: JSON-RPC communication with Kodi's API  
- **resources.lib.config.config_manager.Config**: Database schema definitions and field mappings
- **resources.lib.integrations.remote_api.imdb_upload_manager.IMDbUploadManager**: Handles server upload operations and batch management
- **resources.lib.integrations.remote_api.shortlist_importer.ShortlistImporter**: Handles importing from Shortlist addon with UNIQUE constraint handling
- **resources.lib.integrations.remote_api.favorites_importer.FavoritesImporter**: Handles importing from Kodi favorites with metadata conversion

## Shortlist Import Handling

### UNIQUE Constraint Management
The `add_shortlist_items` method in DatabaseManager implements sophisticated duplicate detection:

```python
# Multiple strategies to avoid UNIQUE constraint violations
existing_media_query = """
    SELECT id FROM media_items 
    WHERE (title = ? AND year = ? AND source = ?) 
    OR (kodi_id = ? AND kodi_id > 0)
    OR (play = ? AND play IS NOT NULL AND play != '')
    LIMIT 1
"""
```

### INSERT OR IGNORE Strategy
For shortlist imports, the system uses `INSERT OR IGNORE` with fallback lookup to handle constraint violations gracefully:

```python
# Insert new media item using INSERT OR IGNORE
media_query = f'INSERT OR IGNORE INTO media_items ({columns}) VALUES ({placeholders})'
cursor.execute(media_query, tuple(filtered_data.values()))
media_id = cursor.lastrowid

# If INSERT OR IGNORE didn't create a new record, find the existing one
if not media_id or media_id == 0:
    cursor.execute(existing_media_query, lookup_params)
    existing_media = cursor.fetchone()
    if existing_media:
        media_id = existing_media[0]
```

### Method Signature Updates

The `fetch_folders_with_item_status` method has been updated to use proper parameter names:
- **DatabaseManager**: `fetch_folders_with_item_status(media_item_id, parent_id=None)`
- **QueryManager**: `fetch_folders_with_item_status(parent_id, media_item_id)`

### Recent Schema Updates

#### File Column Addition
A `file` column has been added to the `media_items` table to store file paths for media items:

```sql
ALTER TABLE media_items ADD COLUMN file TEXT;
```

This column supports improved file path handling and URL generation for media playback.

## DAO Pattern Implementation

The ListingDAO pattern separates folder and list concerns from QueryManager:

- **ListingDAO**: Handles all folder and list SQL operations
- **QueryManager**: Provides connection management and delegates to DAO
- **Dependency Injection**: DAO receives both `execute_query` and `execute_write` callables from QueryManager
- **Separate Execution Paths**: Read operations use `execute_query`, write operations use `execute_write`
- **Meaningful Return Values**: INSERT methods return `lastrowid`, UPDATE/DELETE methods return `rowcount`
- **API Preservation**: Public method signatures remain unchanged for backward compatibility

## Error Handling and Reliability

### Database Lock Management
- Exponential backoff retry mechanism (up to 10 retries)
- Connection timeout handling with proper error messages
- Transaction rollback on failures

### Data Integrity
- Foreign key constraints enforced
- Source validation with CHECK constraints
- Proper NULL handling for optional fields
- JSON validation for cast data

This schema supports the complete LibraryGenie workflow from search and discovery through organization and playback, while maintaining data integrity, performance, and reliability through robust connection management and error handling.