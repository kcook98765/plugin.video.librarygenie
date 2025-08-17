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

### 2. Search (`search`) - AI-Powered Search Results

**Purpose**: Search results from AI-powered semantic search with relevance scoring.

**Characteristics**:
- Contains search relevance scores and IMDB IDs
- Automatically saved to "Search History" folder
- Include title/year from `imdb_exports` table lookup
- Contains `search_score` field for result ranking
- Protected from library sync operations

**Data Flow**:
1. **Search Results**: Saved with `search_score` field, organized into timestamped lists
2. **Search History**: Automatically organized into "Search History" folder
3. **Display**: Full metadata retrieved from Kodi when displaying search results

**Identification Logic**:
- Library items: `source = 'lib'`
- Search results: `source = 'search'`

**Example Use Cases**:
- Library movie references in user-created lists
- AI search results with relevance scoring
- Cross-referencing with external data sources
- Maintaining list membership without duplicating Kodi's data

```sql
-- Example lib record (library reference)
INSERT INTO media_items (kodi_id, imdbnumber, source, media_type, title, year)
VALUES (123, 'tt0111161', 'lib', 'movie', '', 0);

-- Example search record
INSERT INTO media_items (
    imdbnumber, source, search_score, title, year, 
    plot, play, media_type
) VALUES (
    'tt0111161', 'search', 9.85, 'The Shawshank Redemption', 1994,
    'Search result for "prison drama" - Score: 9.85 - IMDb: tt0111161',
    'search_history://tt0111161', 'movie'
);
```

### 2. Manual (`manual`)

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
- Does NOT use `movieid://` protocol (which caused the original issue)

**Example**: Movie added to list via "Add to List" context menu

```sql
-- Example manual record
INSERT INTO media_items (imdbnumber, source, media_type, title, year)
VALUES ('tt0111161', 'manual', 'movie', 'The Shawshank Redemption', 1994);
```

### 3. External (`external`) - External Addon Content

**Purpose**: Full metadata storage for content from external addons/sources.

**Characteristics**:
- Complete metadata stored locally
- No `kodi_id` (external to library)
- Full playback information included
- Persistent storage of external content details

**Data Flow**:
1. External addon provides complete media metadata
2. Stored via `QueryManager.insert_media_item()` with `source = 'external'`
3. Looked up by title/year/play combination for deduplication

**Use Cases**:
- Content from streaming addons
- External media sources
- Non-library content in lists

```sql
-- Example external record
INSERT INTO media_items (
    title, year, plot, genre, director, source, play, media_type
) VALUES (
    'Example Movie', 2024, 'Full plot description...', 'Action',
    'Director Name', 'external', 'plugin://some.addon/?id=123', 'movie'
);
```

### 4. Plugin Addon (`plugin_addon`) - Plugin Addon Content

**Purpose**: Content provided by plugin addons with special handling.

**Characteristics**:
- Similar to `external` but specifically from plugin sources
- May have different metadata structure
- Handled similarly to external content in display logic

**Data Flow**:
1. Plugin addon provides metadata
2. Stored with `source = 'plugin_addon'`
3. Processed alongside external content for display

### 5. Shortlist Import (`shortlist_import`) - Imported Shortlist Content

**Purpose**: Content imported from external shortlist files or sources.

**Characteristics**:
- Uses `INSERT OR REPLACE` for updates
- May contain partial or complete metadata
- Preserves original import source information
- Looked up by title/year/play combination

**Data Flow**:
1. Shortlist import process extracts media information
2. Data stored with `source = 'shortlist_import'`
3. Allows for re-importing and updating existing records

**Use Cases**:
- Importing IMDB lists
- Bulk content imports
- External list migrations

## Source-Specific Logic in ResultsManager

The `ResultsManager.build_display_items_for_list()` method handles different sources:

### External/Plugin Content Processing
```python
src = (r.get('source') or '').lower()
if src == 'external' or src == 'plugin_addon':
    external.append(r)
    continue
```

### Library Content Processing (lib, manual)
Manual items fall through to library processing since they reference the same Kodi library content:

```python
# Manual items continue to library processing...
# Try to get title/year from imdb_exports first
if imdb:
    q = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
    hit = self.query_manager.execute_query(q, (imdb,))
    if hit:
        rec = hit[0]
        title = (rec.get('title') if isinstance(rec, dict) else rec[0]) or ''
        year = int((rec.get('year') if isinstance(rec, dict) else rec[1]) or 0)
```

### URL Generation Logic
The recent fix addresses URL generation for all library-referenced items:

```python
# Determine the appropriate URL for this item
# For manual items and library items, use the file path if available
file_path = meta.get('file')
if file_path:
    item_url = file_path  # Use actual file path (e.g., smb://server/movie.mp4)
else:
    # Fallback for items without file path
    item_url = f"info://{r.get('id', 'unknown')}"
```

## Query Manager Source Handling

Different sources require different query strategies in `QueryManager.insert_media_item()`:

```python
# For shortlist imports - allow updates
if source == 'shortlist_import':
    query_type = 'INSERT OR REPLACE'
else:
    query_type = 'INSERT OR IGNORE'
```

### Lookup Logic

Source-specific lookup prevents conflicts:

```python
if source == 'shortlist_import':
    # Look up by title, year, and play path
    cursor.execute(
        "SELECT id FROM media_items WHERE title = ? AND year = ? AND play = ? AND source = ?",
        (title, year, play, source)
    )
elif source in ('lib', 'search'): # Updated to include 'search' source
    if source == 'search':
        # For search results, look up by IMDb ID
        cursor.execute(
            "SELECT id FROM media_items WHERE imdbnumber = ? AND source = ?",
            (imdb_id, source)
        )
    else: # source == 'lib'
        # For regular lib items
        cursor.execute(
            "SELECT id FROM media_items WHERE imdbnumber = ? AND source = ?",
            (imdb_id, source)
        )
```

### Library Sync Protection

Library sync operations only affect library content in `QueryManager.sync_movies()`:

```python
def sync_movies(self, movies):
    """Only clear library references, preserve search results and other sources"""
    # This preserves search results which have search_score field
    self.execute_query("DELETE FROM media_items WHERE source = 'lib'") # Simplified to clear all 'lib' sources
```

## Search History Management

Search history uses special handling within the `search` source via `DatabaseManager.add_search_history()`:

### Search Result Processing
1. Remote API returns search results with IMDB IDs and scores via `RemoteAPIClient.search_movies()`
2. Title/year looked up from `imdb_exports` table if available
3. Results stored with `source = 'search'`
4. Automatically organized into timestamped lists in "Search History" folder

### Search History Identification
```python
def is_search_result(self, media_item):
    """Check if a media item is a search result"""
    return media_item.get('source') == 'search'

def is_library_reference(self, media_item):
    """Check if a media item is a library reference"""
    return media_item.get('source') == 'lib' and media_item.get('kodi_id', 0) > 0
```

## Best Practices

### 1. Source Selection

- Use `lib` for Kodi library references.
- Use `search` for AI-powered search results.
- Use `manual` for user-curated library items via context menu.
- Use `external` for complete external content.
- Use `plugin_addon` for plugin-specific content.
- Use `shortlist_import` for bulk imports.

### 2. Data Consistency

- Always set appropriate source when inserting via `QueryManager.insert_media_item()`
- Use source-specific lookup logic
- Respect source-specific update strategies
- Maintain referential integrity

### 3. Performance Considerations

- `lib` and `manual` sources minimize storage overhead for library content
- `search` sources preserve relevance information
- `external` sources provide fast access to full metadata
- Use appropriate indexes for source-specific queries

### 4. Library vs Search Distinction

The key distinctions:

```sql
-- Manually added items (user-curated library content)
SELECT * FROM media_items 
WHERE source = 'manual';

-- Library references (system-generated)
SELECT * FROM media_items 
WHERE source = 'lib';

-- Search results (AI-generated with scores)  
SELECT * FROM media_items 
WHERE source = 'search';
```

## Debugging Source Issues

### Common Problems

1. **URL Generation Issues**: Invalid protocols like `movieid://` causing playback failures
2. **Search Result Conflicts**: Multiple search results for same IMDB ID
3. **Missing Library References**: Library content without proper references after sync
4. **Source Confusion**: Mixing up library references and search results

### Diagnostic Queries

```sql
-- Check source distribution
SELECT 
    source,
    COUNT(*) as count 
FROM media_items 
GROUP BY source;

-- Find duplicate IMDB entries across all sources
SELECT imdbnumber, source, COUNT(*) as count 
FROM media_items 
WHERE imdbnumber IS NOT NULL 
GROUP BY imdbnumber, source
HAVING count > 1;

-- Verify search history organization
SELECT l.name, COUNT(li.id) as items
FROM lists l
JOIN list_items li ON l.id = li.list_id
JOIN media_items mi ON li.media_item_id = mi.id
WHERE mi.source = 'search'
GROUP BY l.name
ORDER BY l.name;
```

### Log Analysis

Enable debug logging to trace source-specific operations:

```python
utils.log(f"Successfully inserted media item with ID: {inserted_id} for source: {source}", "DEBUG")
```

Look for URL generation logs:
```python
utils.log(f"Set ListItem path for '{title}': {play_url}", "DEBUG")
```

## Migration Considerations

When updating source handling:

1. **Backup Database**: Always backup before source changes
2. **Test Migrations**: Verify source transitions work correctly
3. **Update Logic**: Ensure all source-specific logic accounts for search results within `search` source
4. **Validate Results**: Check data integrity after changes
5. **URL Generation**: Verify playback URLs are generated correctly for each source

## Recent Fixes

### Manual Source URL Generation Fix
The recent fix in `ResultsManager.build_display_items_for_list()` corrected URL generation for manual items:

**Before (Broken)**:
```python
movieid = meta.get('movieid', 0)
if movieid and movieid > 0:
    item_url = f"movieid://{movieid}/"  # Invalid protocol
```

**After (Fixed)**:
```python
file_path = meta.get('file')
if file_path:
    item_url = file_path  # Use actual file path from Kodi
else:
    item_url = f"info://{r.get('id', 'unknown')}"  # Fallback
```

This ensures that manually added library items use valid file paths for playback instead of invalid `movieid://` URLs.

## Conclusion

The source system provides flexible content management while maintaining data integrity. The `manual` source specifically handles user-curated library content with proper file path resolution for playback. Understanding source-specific processing is essential for proper LibraryGenie operation and development.

For implementation details, see:
- `QueryManager.insert_media_item()` - Source-specific insertion logic
- `QueryManager.sync_movies()` - Library sync operations that preserve search results
- `DatabaseManager.add_search_history()` - Search result handling within `search` source
- `ResultsManager.build_display_items_for_list()` - Source-specific processing and URL generation