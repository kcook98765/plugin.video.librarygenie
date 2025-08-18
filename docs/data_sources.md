# LibraryGenie Data Sources Documentation

This document explains the data source system used in LibraryGenie's database to track and manage different types of media content. Understanding these sources is crucial for proper data handling and debugging.

## Overview

LibraryGenie uses a `source` field in the `media_items` table to categorize content based on its origin and purpose. Each source type has specific characteristics, use cases, and handling logic in the `ResultsManager.build_display_items_for_list()` method.

## Source Types

### 1. Library (`lib`) - Kodi Library Content References

**Purpose**: Reference entries for movies that exist in the user's Kodi library.

**Characteristics**:
- Minimal metadata stored (identifiers only), contains `kodi_id` linking to Kodi's database
- May include `imdbnumber` for cross-referencing
- Full metadata fetched on-demand via JSON-RPC when displaying lists
- Library references automatically cleared during library sync operations

**Data Flow**:
1. **Library Sync**: Removes all `source = 'lib'` records during sync operations
2. **Library References**: Created via `QueryManager.insert_media_item()`
3. **Display**: Full metadata retrieved from Kodi when displaying library items

### 2. Manual (`manual`) - User-Curated Library Content

**Purpose**: Items manually added via context menus from native Kodi library

**Characteristics**:
- Added through LibraryGenie context menu actions on existing Kodi library items
- Contains library-sourced content but marked as manually curated
- **Processed through standard library item path** (not external path)
- Distinguishes manually added items from automatic search results
- Uses same lookup and display logic as library items
- **Uses file path from Kodi for playback** (not movieid:// protocol)

**Data Flow**:
1. User selects "Add to List" from LibraryGenie context menu on library item
2. Item stored with `source = 'manual'` and library metadata
3. **Processed through library item display path** in `ResultsManager`
4. Matched against Kodi library via JSON-RPC for full metadata
5. **Uses file path from JSON-RPC response for playable URL**

**URL Generation**:
- Uses `file` path from Kodi metadata (e.g., `smb://server/movie.mp4`)
- Fallback to `info://` URL if no file path available
- Does NOT use `movieid://` protocol (which caused playback issues)

### 3. Search Results (`search`) - AI-Powered Search Results (Alpha)

**Purpose**: Search results from AI-powered semantic search with relevance scoring.

**Characteristics**:
- Stored with `source = 'search'`
- Contains search relevance scores and IMDB IDs
- Automatically saved to "Search History" folder
- Include title/year from `imdb_exports` table lookup
- Use `search_score` field for result ranking
- Protected from library sync operations
- **Alpha Feature**: Available only with remote API access

**Data Flow**:
1. **Search Results**: Saved with `source = 'search'` and `search_score` field, organized into timestamped lists
2. **Search History**: Automatically organized into "Search History" folder
3. **Display**: Full metadata retrieved from Kodi when displaying search results

### 4. Kodi Library (`kodi_library`) - Shortlist Import Library Matches

**Purpose**: Items imported from Shortlist that were found to exist in the Kodi library.

**Characteristics**:
- Created during shortlist import when items match existing Kodi library content
- Contains full Kodi library metadata and valid `kodi_id`
- **Processed through library item path** like `lib` and `manual` sources
- Uses library data instead of shortlist data for better quality
- Preserves library references while tracking shortlist import origin

**Data Flow**:
1. **Shortlist Import**: Items looked up in Kodi library via JSON-RPC
2. **Library Match Found**: Stored with `source = 'kodi_library'` and Kodi metadata
3. **Display Processing**: Follows library item processing path with JSON-RPC lookup
4. **URL Generation**: Uses file paths from Kodi library

**Processing Logic**:
```python
# In ResultsManager.build_display_items_for_list()
# kodi_library sources follow library processing path
if src == 'external' or src == 'plugin_addon':
    external.append(r)
    continue
# kodi_library falls through to library processing with lib, manual, search
```

### 5. Shortlist Import (`shortlist_import`) - Non-Library Shortlist Content

**Purpose**: Items imported from Shortlist that were NOT found in the Kodi library.

**Characteristics**:
- Uses `INSERT OR REPLACE` for updates during import
- Contains complete metadata from shortlist addon
- No valid `kodi_id` (set to 0)
- Preserves original shortlist metadata
- **Processed through library item path** for consistency

**Data Flow**:
1. **Shortlist Import**: Items NOT found in Kodi library during lookup
2. **Shortlist Data**: Complete metadata stored from shortlist addon
3. **Display Processing**: Follows library processing but shows as "[Unmatched]"
4. **URL Generation**: Uses `info://` URLs for non-playable items

**Lookup Logic in QueryManager**:
```python
if source == 'shortlist_import':
    # Look up by title, year, and play path for uniqueness
    cursor.execute(
        "SELECT id FROM media_items WHERE title = ? AND year = ? AND play = ? AND source = ?",
        (title, year, play, source)
    )
```

### 6. External (`external`) - External Addon Content

**Purpose**: Full metadata storage for content from external addons/sources.

**Characteristics**:
- Complete metadata stored locally
- No `kodi_id` (external to library)
- Full playback information included
- Persistent storage of external content details
- **Processed through external processing path**

**Data Flow**:
1. External addon provides complete media metadata
2. Stored via `QueryManager.insert_media_item()` with `source = 'external'`
3. **Processed separately from library items in ResultsManager**

### 7. Plugin Addon (`plugin_addon`) - Plugin Addon Content

**Purpose**: Content provided by plugin addons with special handling.

**Characteristics**:
- Similar to `external` but specifically from plugin sources
- May have different metadata structure
- **Processed through external processing path** alongside external content

## Source-Specific Logic in ResultsManager

The `ResultsManager.build_display_items_for_list()` method uses a clear branching strategy:

### Library Processing Path
```python
src = (r.get('source') or '').lower()
# Only external and plugin_addon sources go to external processing
# All other sources (lib, manual, search, kodi_library) follow library item processing path
if src == 'external' or src == 'plugin_addon':
    external.append(r)
    continue
```

**Sources using library processing**: `lib`, `manual`, `search`, `kodi_library`, `shortlist_import`

**Processing steps**:
1. Title/year lookup from `imdb_exports` table
2. Batch JSON-RPC lookup for library metadata
3. File path URL generation for playback
4. Search score preservation for ordering

### External Processing Path
```python
# External items processed separately with stored metadata
external_sorted = sorted(external, key=lambda x: x.get('search_score', 0), reverse=True)
```

**Sources using external processing**: `external`, `plugin_addon`

**Processing steps**:
1. Use stored metadata directly
2. Sort by search score if available
3. Use stored file paths or external URLs

## Query Manager Source Handling

Different sources require different query strategies in `QueryManager.insert_media_item()`:

### Update Strategy
```python
if source == 'shortlist_import':
    query_type = 'INSERT OR REPLACE'  # Allow updates
else:
    query_type = 'INSERT OR IGNORE'   # Prevent duplicates
```

### Lookup Logic
```python
if source == 'shortlist_import':
    # Look up by title, year, and play path
    cursor.execute(
        "SELECT id FROM media_items WHERE title = ? AND year = ? AND play = ? AND source = ?",
        (title, year, play, source)
    )
elif source in ('search', 'lib') and media_data.get('imdbnumber'):
    # Look up by IMDb ID and source
    cursor.execute(
        "SELECT id FROM media_items WHERE imdbnumber = ? AND source = ?",
        (media_data.get('imdbnumber'), source)
    )
else:
    # Original lookup logic for other sources
    cursor.execute(
        "SELECT id FROM media_items WHERE kodi_id = ? AND play = ?",
        (lookup_kodi_id, lookup_play)
    )
```

## Shortlist Import System

The shortlist import system implements sophisticated logic for handling different data sources:

### Library Detection Process
```python
def lookup_in_kodi_library(self, title, year):
    # 1. Direct title search using JSON-RPC
    # 2. Fuzzy title search (contains)
    # 3. Fallback manual search through all movies
    # 4. Returns None if no match found
```

### Data Conversion Logic
```python
def convert_shortlist_item_to_media_dict(self, item, kodi_movie=None):
    if kodi_movie:
        # Use Kodi library data - preferred when available
        media_dict['source'] = 'kodi_library'
        media_dict['kodi_id'] = kodi_movie.get('movieid')
    else:
        # Use Shortlist data with enhanced validation
        media_dict['source'] = 'shortlist_import'  
        media_dict['kodi_id'] = 0
```

## Library Sync Protection

Library sync operations only affect library content:

```python
def sync_movies(self, movies):
    """Only clear library references, preserve other sources"""
    self.execute_query("DELETE FROM media_items WHERE source = 'lib'")
    # Preserves search, shortlist_import, kodi_library, external sources
```

## URL Generation Strategy

### Library Sources (lib, manual, search, kodi_library, shortlist_import)
```python
# Use file path from Kodi metadata when available
file_path = meta.get('file')
if file_path:
    item_url = file_path  # e.g., smb://server/movie.mp4
else:
    item_url = f"info://{r.get('id', 'unknown')}"  # Fallback
```

### External Sources (external, plugin_addon)
```python
# Use stored file path or external URL
item_url = item.get('file', f"external://{item.get('id', 'unknown')}")
```

## Best Practices

### 1. Source Selection Guidelines

- Use `lib` for automatic Kodi library references
- Use `manual` for user-curated library items via context menu
- Use `search` for AI-powered search results with scores
- Use `kodi_library` for shortlist imports that match library content
- Use `shortlist_import` for shortlist imports without library matches
- Use `external` for complete external content with metadata
- Use `plugin_addon` for plugin-specific content

### 2. Data Consistency Rules

- Always set appropriate source when inserting via `QueryManager.insert_media_item()`
- Use source-specific lookup logic to prevent duplicates
- Respect source-specific update strategies (`INSERT OR REPLACE` vs `INSERT OR IGNORE`)
- Maintain proper `kodi_id` values (0 for non-library content)

### 3. Processing Path Considerations

- Library processing path: Fetches fresh metadata via JSON-RPC
- External processing path: Uses stored metadata directly
- URL generation depends on processing path and source type
- Search scores preserved across all processing paths

## Troubleshooting Source Issues

### Common Problems

1. **Playback URL Issues**: Wrong processing path for source type
2. **Duplicate Content**: Incorrect lookup logic for source
3. **Missing Metadata**: Source processed through wrong path
4. **Library Sync Conflicts**: Sources not properly protected

### Diagnostic Queries

```sql
-- Check source distribution
SELECT source, COUNT(*) as count 
FROM media_items 
GROUP BY source;

-- Find items by processing path
-- Library path sources
SELECT * FROM media_items 
WHERE source IN ('lib', 'manual', 'search', 'kodi_library', 'shortlist_import');

-- External path sources  
SELECT * FROM media_items
WHERE source IN ('external', 'plugin_addon');

-- Verify shortlist import results
SELECT 
    source,
    COUNT(*) as count,
    COUNT(CASE WHEN kodi_id > 0 THEN 1 END) as with_kodi_id
FROM media_items 
WHERE source IN ('kodi_library', 'shortlist_import')
GROUP BY source;
```

### Log Analysis

Key log patterns to monitor:

```python
# Source processing decisions
"Only external and plugin_addon sources go to external processing"

# Shortlist import decisions
"JSONRPC DECISION: Using library data instead of shortlist data"
"JSONRPC DECISION: Will use shortlist data as no library match exists"

# URL generation
"Set ListItem path for '{title}': {play_url}"
```

## Migration Considerations

When updating source handling:

1. **Backup Database**: Always backup before source logic changes
2. **Test Source Processing**: Verify each source follows correct processing path
3. **Validate URL Generation**: Ensure playback URLs work for each source type
4. **Check Import Logic**: Test shortlist imports create correct source types
5. **Verify Sync Protection**: Confirm library sync preserves non-library sources

## Recent Updates

### Kodi Library Source Integration
Added `kodi_library` source to library processing path to ensure shortlist imports that match library content are handled consistently with other library sources.

### Processing Path Clarification
Clarified that most sources (`lib`, `manual`, `search`, `kodi_library`, `shortlist_import`) use the library processing path, while only `external` and `plugin_addon` use the external processing path.

### URL Generation Fix
Fixed URL generation for manual and library sources to use actual file paths instead of invalid `movieid://` protocols.

## Conclusion

The source system provides flexible content management while maintaining clear processing paths. The key distinction is between:

- **Library Processing Path**: Sources that reference or relate to Kodi library content
- **External Processing Path**: Sources with complete standalone metadata

Understanding this distinction is essential for proper LibraryGenie operation and debugging.

For implementation details, see:
- `resources.lib.data.results_manager.ResultsManager.build_display_items_for_list()` - Source-specific processing logic
- `resources.lib.data.query_manager.QueryManager.insert_media_item()` - Source-specific insertion and lookup
- `resources.lib.integrations.remote_api.shortlist_importer.ShortlistImporter.convert_shortlist_item_to_media_dict()` - Source assignment logic
- `resources.lib.data.database_manager.DatabaseManager.add_shortlist_items()` - Batch import with source handling

## Key Manager Classes

- **resources.lib.data.database_manager.DatabaseManager**: High-level database operations, singleton pattern with retry logic
- **resources.lib.data.query_manager.QueryManager**: Low-level SQL execution with connection pooling and management
- **resources.lib.data.dao.listing_dao.ListingDAO**: Data Access Object for folder and list operations, receives injected query executor
- **resources.lib.data.results_manager.ResultsManager**: Handles search result processing and display item building
- **resources.lib.integrations.jsonrpc.jsonrpc_manager.JSONRPCManager**: JSON-RPC communication with Kodi's API  
- **resources.lib.config.config_manager.Config**: Database schema definitions and field mappings
- **resources.lib.integrations.remote_api.imdb_upload_manager.IMDbUploadManager**: Handles server upload operations and batch management
- **resources.lib.core.navigation_manager.NavigationManager**: Manages UI navigation state and conflict prevention
- **resources.lib.core.options_manager.OptionsManager**: Handles dynamic options menu generation and execution