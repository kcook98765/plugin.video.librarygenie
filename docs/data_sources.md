
# LibraryGenie Data Sources Documentation

This document explains the data source system used in LibraryGenie's database to track and manage different types of media content. Understanding these sources is crucial for proper data handling and debugging.

## Overview

LibraryGenie uses a `source` field in the `media_items` table to categorize content based on its origin and purpose. Each source type has specific characteristics, use cases, and handling logic.

## Source Types

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
2. **Library References**: Created via `upsert_reference_media_item()`
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
2. Stored via `upsert_external_media_item()`
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

### 3. `shortlist_import` - Imported Shortlist Content

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

### 4. `provider` - Content Provider References

**Purpose**: Reference entries for content from specific providers.

**Characteristics**:
- Similar to `lib` source but for external providers
- Minimal metadata (identifiers only)
- Used for cross-referencing provider content

**Data Flow**:
1. Provider integration creates reference entries
2. Links provider content to LibraryGenie lists
3. Metadata fetched from provider when needed

## Source-Specific Logic

### Query Handling

Different sources require different query strategies:

```python
# For shortlist imports and items with search scores
if source in ('shortlist_import', 'search') or media_data.get('search_score'):
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
elif source in ('search', 'lib') and imdb_id:
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

Library sync operations only affect library content without search scores:

```python
def sync_movies(self, movies):
    """Only clear library references, preserve search results and other sources"""
    # This preserves search results which have search_score field
    self.execute_query("DELETE FROM media_items WHERE source = 'lib' AND search_score IS NULL")
```

## Search History Management

Search history uses special handling within the `lib` source:

### Search Result Processing
1. Remote API returns search results with IMDB IDs and scores
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

## Best Practices

### 1. Source Selection

- Use `lib` for both Kodi library references AND search results
- Use `search_score` field to distinguish between library refs and search results
- Use `external` for complete external content
- Use `shortlist_import` for bulk imports
- Use `provider` for provider-specific references

### 2. Data Consistency

- Always set appropriate source when inserting
- Use `search_score` field to identify search results within `lib` source
- Use source-specific lookup logic
- Respect source-specific update strategies
- Maintain referential integrity

### 3. Performance Considerations

- `lib` sources (both types) minimize storage overhead for library content
- Search results within `lib` preserve relevance information
- `external` sources provide fast access to full metadata
- Use appropriate indexes for source-specific queries

### 4. Search vs Library Distinction

The key distinction within `lib` source:

```sql
-- Library references (no search_score)
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
- `DatabaseManager.sync_movies()` - Library sync operations that preserve search results
- `DatabaseManager.add_search_history()` - Search result handling within `lib` source
- `ResultsManager._enhance_search_history_items()` - Search result processing and display
