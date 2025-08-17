# LibraryGenie Data Sources Documentation

This document explains the data source system used in LibraryGenie's database to track and manage different types of media content. Understanding these sources is crucial for proper data handling and debugging.

## Overview

LibraryGenie uses a `source` field in the `media_items` table to categorize content based on its origin and purpose. Each source type has specific characteristics, use cases, and handling logic.

## Source Types

### 1. Manual (`manual`)
**Purpose**: Items manually added via context menus from native Kodi library  
**Characteristics**:
- Added through LibraryGenie context menu actions
- Contains library-sourced content but marked as manually curated
- Processed through standard library item path (not external path)
- Distinguishes manually added items from search results
- Uses same lookup and display logic as library items

**Data Flow**:
1. User selects "Add to List" from LibraryGenie context menu
2. Item stored with `source = 'manual'` and library metadata
3. Processed through library item display path in `ResultsManager`
4. Matched against Kodi library via JSON-RPC for playback

**Example**: Movie added to list via "Add to List" context menu

### 2. Library (`lib`) - Legacy

### 1. `lib` - Kodi Library Content & Search Results

**Purpose**: Reference entries for movies that exist in the user's Kodi library, as well as search results from AI-powered semantic search.

**Characteristics**:
- **Library References**: Minimal metadata stored (identifiers only), contains `kodi_id` linking to Kodi's database
- **Search Results**: Contains search relevance scores and IMDB IDs, automatically saved to "Search History" folder
- May include `imdbnumber` for cross-referencing
- Full metadata fetched on-demand via JSON-RPC for library items
- Search results include title/year from `imdb_exports` table lookup
- Library references automatically cleared during library sync operations

**Data Flow**:
1. **Library Sync**: Removes all `source = 'lib'` records without `search_score`
2. **Library References**: Created via `QueryManager.insert_media_item()`
3. **Search Results**: Saved with `search_score` field, organized into timestamped lists
4. **Display**: Full metadata retrieved from Kodi when displaying library items

**Identification Logic**:
- Library items: `source = 'lib'` AND `search_score IS NULL`
- Search results: `source = 'lib'` AND `search_score IS NOT NULL`

**Example Use Cases**:
- Library movie references in user-created lists
- AI search results with relevance scoring
- Cross-referencing with external data sources
- Maintaining list membership without duplicating Kodi's data

```sql
-- Example lib record (library reference)
INSERT INTO media_items (kodi_id, imdbnumber, source, media_type, title, year)
VALUES (123, 'tt0111161', 'lib', 'movie', '', 0);

-- Example lib record (search result)
INSERT INTO media_items (
    imdbnumber, source, search_score, title, year, 
    plot, play, media_type
) VALUES (
    'tt0111161', 'lib', 9.85, 'The Shawshank Redemption', 1994,
    'Search result for "prison drama" - Score: 9.85 - IMDb: tt0111161',
    'search_history://tt0111161', 'movie'
);
```

### 2. `external` - External Addon Content

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

### 3. `plugin_addon` - Plugin Addon Content

**Purpose**: Content provided by plugin addons with special handling.

**Characteristics**:
- Similar to `external` but specifically from plugin sources
- May have different metadata structure
- Handled similarly to external content in display logic

**Data Flow**:
1. Plugin addon provides metadata
2. Stored with `source = 'plugin_addon'`
3. Processed alongside external content for display

### 4. `shortlist_import` - Imported Shortlist Content

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

## Source-Specific Logic

### Query Handling

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
elif source in ('lib',) and imdb_id:
    if media_data.get('search_score'):
        # For search results, look up by IMDb ID and search_score presence
        cursor.execute(
            "SELECT id FROM media_items WHERE imdbnumber = ? AND search_score IS NOT NULL",
            (imdb_id,)
        )
    else:
        # For regular lib items
        cursor.execute(
            "SELECT id FROM media_items WHERE imdbnumber = ? AND source = ?",
            (imdb_id, source)
        )
```

### Library Sync Protection

Library sync operations only affect library content without search scores in `QueryManager.sync_movies()`:

```python
def sync_movies(self, movies):
    """Only clear library references, preserve search results and other sources"""
    # This preserves search results which have search_score field
    self.execute_query("DELETE FROM media_items WHERE source = 'lib' AND search_score IS NULL")
```

## Search History Management

Search history uses special handling within the `lib` source via `DatabaseManager.add_search_history()`:

### Search Result Processing
1. Remote API returns search results with IMDB IDs and scores via `RemoteAPIClient.search_movies()`
2. Title/year looked up from `imdb_exports` table if available
3. Results stored with `source = 'lib'` AND `search_score = relevance_score`
4. Automatically organized into timestamped lists in "Search History" folder

### Search History Identification
```python
def is_search_result(self, media_item):
    """Check if a media item is a search result"""
    return (media_item.get('source') == 'lib' and 
            media_item.get('search_score') is not None)

def is_library_reference(self, media_item):
    """Check if a media item is a library reference"""
    return (media_item.get('source') == 'lib' and 
            media_item.get('search_score') is None and
            media_item.get('kodi_id', 0) > 0)
```

## Display Logic in ResultsManager

The `ResultsManager.build_display_items_for_list()` method handles different sources:

### External/Plugin Content
```python
src = (r.get('source') or '').lower()
if src == 'external' or src == 'plugin_addon':
    external.append(r)
    continue
```

### Library Content Processing
Manual items (`source = 'manual'`) are processed alongside library items since they reference the same Kodi library content:

```python
# Manual items fall through to library processing (not caught by external filter)
src = (r.get('source') or '').lower()
if src == 'external' or src == 'plugin_addon':
    external.append(r)
    continue
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

## Best Practices

### 1. Source Selection

- Use `lib` for both Kodi library references AND search results
- Use `search_score` field to distinguish between library refs and search results
- Use `external` for complete external content
- Use `plugin_addon` for plugin-specific content
- Use `shortlist_import` for bulk imports

### 2. Data Consistency

- Always set appropriate source when inserting via `QueryManager.insert_media_item()`
- Use `search_score` field to identify search results within `lib` source
- Use source-specific lookup logic
- Respect source-specific update strategies
- Maintain referential integrity

### 3. Performance Considerations

- `lib` sources (both types) minimize storage overhead for library content
- Search results within `lib` preserve relevance information
- `external` sources provide fast access to full metadata
- Use appropriate indexes for source-specific queries

### 4. Manual vs Library vs Search Distinction

The key distinctions:

```sql
-- Manually added items (no search_score)
SELECT * FROM media_items 
WHERE source = 'manual' AND search_score IS NULL;

-- Library references (no search_score) - Legacy
SELECT * FROM media_items 
WHERE source = 'lib' AND search_score IS NULL;

-- Search results (has search_score)  
SELECT * FROM media_items 
WHERE source = 'lib' AND search_score IS NOT NULL;
```

## Debugging Source Issues

### Common Problems

1. **Search Result Conflicts**: Multiple search results for same IMDB ID
2. **Missing Library References**: Library content without proper references after sync
3. **Stale Library Data**: Outdated library references after sync
4. **Source Confusion**: Mixing up library references and search results

### Diagnostic Queries

```sql
-- Check source distribution including search results
SELECT 
    source,
    CASE 
        WHEN source = 'lib' AND search_score IS NOT NULL THEN 'search_result'
        WHEN source = 'lib' AND search_score IS NULL THEN 'library_ref'
        ELSE source
    END as effective_source,
    COUNT(*) as count 
FROM media_items 
GROUP BY source, effective_source;

-- Find duplicate IMDB entries across all sources
SELECT imdbnumber, source, search_score, COUNT(*) as count 
FROM media_items 
WHERE imdbnumber IS NOT NULL 
GROUP BY imdbnumber, source, (search_score IS NOT NULL)
HAVING count > 1;

-- Verify search history organization
SELECT l.name, COUNT(li.id) as items
FROM lists l
JOIN list_items li ON l.id = li.list_id
JOIN media_items mi ON li.media_item_id = mi.id
WHERE mi.source = 'lib' AND mi.search_score IS NOT NULL
GROUP BY l.name
ORDER BY l.name;
```

### Log Analysis

Enable debug logging to trace source-specific operations:

```python
utils.log(f"Successfully inserted media item with ID: {inserted_id} for source: {source}, search_score: {search_score}", "DEBUG")
```

## Migration Considerations

When updating source handling:

1. **Backup Database**: Always backup before source changes
2. **Test Migrations**: Verify source transitions work correctly
3. **Update Logic**: Ensure all source-specific logic accounts for search results within `lib`
4. **Validate Results**: Check data integrity after changes
5. **Search Score Migration**: Ensure existing search results maintain their scores

## Conclusion

The unified `lib` source system provides flexible content management while maintaining data integrity. The `search_score` field serves as the key differentiator between library references and search results within the same source. Understanding this dual nature is essential for proper LibraryGenie operation and development.

For implementation details, see:
- `QueryManager.insert_media_item()` - Source-specific insertion logic with search score handling
- `QueryManager.sync_movies()` - Library sync operations that preserve search results
- `DatabaseManager.add_search_history()` - Search result handling within `lib` source
- `ResultsManager.build_display_items_for_list()` - Search result processing and display