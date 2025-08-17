
# LibraryGenie Data Sources Documentation

This document explains the data source system used in LibraryGenie's database to track and manage different types of media content. Understanding these sources is crucial for proper data handling and debugging.

## Overview

LibraryGenie uses a `source` field in the `media_items` table to categorize content based on its origin and purpose. Each source type has specific characteristics, use cases, and handling logic.

## Source Types

### 1. `lib` - Kodi Library Content

**Purpose**: Reference entries for movies that exist in the user's Kodi library.

**Characteristics**:
- Minimal metadata stored (identifiers only)
- Contains `kodi_id` linking to Kodi's database
- May include `imdbnumber` for cross-referencing
- Full metadata fetched on-demand via JSON-RPC
- Automatically cleared during library sync operations

**Data Flow**:
1. Library sync removes all `source = 'lib'` records
2. Reference entries created via `upsert_reference_media_item()`
3. Full metadata retrieved from Kodi when displaying lists

**Example Use Cases**:
- Library movie references in user-created lists
- Cross-referencing with external data sources
- Maintaining list membership without duplicating Kodi's data

```sql
-- Example lib record
INSERT INTO media_items (kodi_id, imdbnumber, source, media_type, title, year)
VALUES (123, 'tt0111161', 'lib', 'movie', '', 0);
```

### 2. `search_library` - Search Results from Library Content

**Purpose**: Semantic search results that match content in the user's library.

**Characteristics**:
- Contains search relevance scores
- Includes IMDB ID for library matching
- Title/year looked up from `imdb_exports` table
- Automatically saved to "Search History" folder
- Uses `INSERT OR REPLACE` for updates

**Data Flow**:
1. Remote API returns search results with IMDB IDs and scores
2. Title/year looked up from `imdb_exports` table
3. Search results stored with `source = 'search_library'`
4. Automatically organized into timestamped lists

**Key Fields**:
- `search_score`: Relevance score from semantic search
- `imdbnumber`: IMDB ID for library matching
- `plot`: Contains search query and score information

```sql
-- Example search_library record
INSERT INTO media_items (
    imdbnumber, source, search_score, title, year, 
    plot, play, media_type
) VALUES (
    'tt0111161', 'search_library', 9.85, 'The Shawshank Redemption', 1994,
    'Search result for "prison drama" - Score: 9.85 - IMDb: tt0111161',
    'search_history://tt0111161', 'movie'
);
```

### 3. `external` - External Addon Content

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

### 5. `provider` - Content Provider References

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
# For shortlist imports, search, and search_library
if source in ('shortlist_import', 'search', 'search_library'):
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
elif source in ('search', 'search_library') and imdb_id:
    # Look up by IMDb ID and source
    cursor.execute(
        "SELECT id FROM media_items WHERE imdbnumber = ? AND source = ?",
        (imdb_id, source)
    )
```

### Library Sync Protection

Library sync operations only affect library content:

```python
def sync_movies(self, movies):
    """Only clear library references, preserve other sources"""
    self.execute_query("DELETE FROM media_items WHERE source = 'lib'")
```

## Best Practices

### 1. Source Selection

- Use `lib` for Kodi library references
- Use `search_library` for AI search results
- Use `external` for complete external content
- Use `shortlist_import` for bulk imports
- Use `provider` for provider-specific references

### 2. Data Consistency

- Always set appropriate source when inserting
- Use source-specific lookup logic
- Respect source-specific update strategies
- Maintain referential integrity

### 3. Performance Considerations

- `lib` sources minimize storage overhead
- `external` sources provide fast access to full metadata
- Search sources preserve relevance information
- Use appropriate indexes for source-specific queries

### 4. Search History Management

Search history uses special handling:

```python
def is_search_history(self, list_id):
    """Check if a list is in the Search History folder"""
    list_data = self.fetch_list_by_id(list_id)
    search_history_folder_id = self.get_folder_id_by_name("Search History")
    return list_data.get('folder_id') == search_history_folder_id
```

## Debugging Source Issues

### Common Problems

1. **Source Conflicts**: Multiple sources for same content
2. **Missing References**: Library content without proper references
3. **Stale Data**: Outdated library references after sync
4. **Search Duplication**: Multiple search results for same query

### Diagnostic Queries

```sql
-- Check source distribution
SELECT source, COUNT(*) as count FROM media_items GROUP BY source;

-- Find duplicate IMDB entries across sources
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
WHERE mi.source = 'search_library'
GROUP BY l.name;
```

### Log Analysis

Enable debug logging to trace source-specific operations:

```python
utils.log(f"Successfully inserted media item with ID: {inserted_id} for source: {source}", "DEBUG")
```

## Migration Considerations

When updating source handling:

1. **Backup Database**: Always backup before source changes
2. **Test Migrations**: Verify source transitions work correctly
3. **Update Logic**: Ensure all source-specific logic is updated
4. **Validate Results**: Check data integrity after changes

## Conclusion

The source system provides flexible content management while maintaining data integrity. Understanding each source type's purpose and characteristics is essential for proper LibraryGenie operation and development.

For implementation details, see:
- `QueryManager.insert_media_item()` - Source-specific insertion logic
- `DatabaseManager.sync_movies()` - Library sync operations
- `DatabaseManager.add_search_history()` - Search result handling
