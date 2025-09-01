
# LibraryGenie Local Search Documentation

This document provides detailed documentation on LibraryGenie's local search functionality, including architecture, implementation details, search algorithms, and usage patterns.

---

## Overview

LibraryGenie's local search system provides fast, offline search capabilities across the user's Kodi video library. The search is powered by a SQLite database index and includes advanced text normalization, year filtering, and intelligent matching algorithms.

### Key Features

- **Database-Backed Search**: Uses SQLite index for fast queries against local library
- **Advanced Text Normalization**: Handles diacritics, punctuation, case, and Unicode
- **Intelligent Year Parsing**: Robust year filter detection with title protection
- **Multiple Match Modes**: Contains and "starts with" search modes
- **Cross-Field Matching**: Searches across title, plot, and optionally file paths
- **Efficient Pagination**: Smart paging with "has next page" detection
- **Search Analytics**: Performance tracking and query logging

---

## Architecture

### Components

1. **LocalSearchEngine** (`lib/search/local_engine.py`)
   - Main search orchestrator
   - Handles movie and episode searches
   - Formats results for UI consumption

2. **EnhancedSearchEngine** (`lib/search/enhanced_search_engine.py`)
   - Advanced search with complex query building
   - Sophisticated pagination and performance optimization
   - Integrated search logging and analytics

3. **TextNormalizer** (`lib/search/normalizer.py`)
   - Unified text normalization for consistent matching
   - Unicode handling and diacritic removal
   - Token extraction and cleaning

4. **YearParser** (`lib/search/year_parser.py`)
   - Robust year filter extraction
   - Title protection to avoid false positives
   - Support for ranges, comparisons, and decade shorthand

5. **QueryInterpreter** (`lib/search/enhanced_query_interpreter.py`)
   - Parses user input into structured search queries
   - Handles settings integration and defaults
   - Validates and sanitizes input

---

## Search Flow

### Basic Search Process

1. **Input Processing**
   ```
   User Input → QueryInterpreter → SearchQuery Object
   ```

2. **Query Execution**
   ```
   SearchQuery → EnhancedSearchEngine → SQL Generation → Database Query
   ```

3. **Result Formatting**
   ```
   Raw Results → Result Formatting → UI-Ready Items
   ```

### Example Search Flow

```python
# User searches for "batman 2008"
user_input = "batman 2008"

# QueryInterpreter processes input
query = interpreter.parse_query(user_input)
# query.tokens = ["batman"]
# query.year_filter = 2008

# EnhancedSearchEngine builds SQL
sql = "SELECT ... FROM media_items WHERE 
       LOWER(title) LIKE '%batman%' AND year = 2008"

# Results formatted for UI
results = [
    {
        'label': 'The Dark Knight (2008)',
        'type': 'movie',
        'ids': {'imdb': 'tt0468569', 'kodi_id': 123},
        # ... additional metadata
    }
]
```

---

## Database Schema Integration

### Primary Table: `media_items`

The search operates primarily on the `media_items` table:

| Field | Purpose in Search |
|-------|------------------|
| `title` | Primary text matching field |
| `plot` | Secondary text matching field |
| `year` | Year filtering |
| `play` | File path search (optional) |
| `media_type` | Filter movies vs episodes |
| `kodi_id` | Link to Kodi library |
| `imdbnumber` | Universal identifier |

### Search Indexes

Key indexes for search performance:
- `media_type` for filtering movies/episodes
- `year` for year-based queries
- Text search relies on SQLite's built-in string matching

---

## Text Normalization

### Normalization Pipeline

```python
def normalize(text: str) -> str:
    # 1. Unicode NFKD normalize, remove diacritics
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(char for char in normalized 
                        if unicodedata.category(char) not in ('Mn', 'Mc'))
    
    # 2. Lowercase with casefold()
    normalized = normalized.casefold()
    
    # 3. Replace hyphens and underscores with spaces
    normalized = re.sub(r'[-–—_]', ' ', normalized)
    
    # 4. Replace punctuation with spaces
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # 5. Collapse spaces and trim
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized
```

### Examples

| Original | Normalized |
|----------|------------|
| `"The Lord of the Rings"` | `"the lord of the rings"` |
| `"Amélie (2001)"` | `"amelie 2001"` |
| `"Spider-Man: Homecoming"` | `"spider man homecoming"` |

---

## Year Filtering

### Year Filter Types

1. **Explicit Prefixes** (highest priority)
   - `y:1999` or `year:1999` - Exact year
   - `year:1990-2000` - Year range
   - `year>=2010` - Comparison operators

2. **Decade Shorthand** (when enabled)
   - `'90s` or `1990s` - Decade ranges

3. **Isolated Years** (with protection)
   - Single 4-digit years (1900-2099)
   - Protected if part of known titles

### Title Protection

Prevents false year detection in movie titles:

```python
protected_patterns = [
    '2001: a space odyssey',
    'fahrenheit 451',
    'area 51',
    'apollo 13',
    # ... more patterns
]
```

### Year Parsing Examples

| Input | Parsed Year Filter | Remaining Text |
|-------|-------------------|----------------|
| `"batman year:2008"` | `2008` | `"batman"` |
| `"movies from 1990-2000"` | `(1990, 2000)` | `"movies from"` |
| `"2001: A Space Odyssey"` | `None` | `"2001: A Space Odyssey"` |

---

## Search Algorithms

### Cross-Field Word Matching

Each search word must match in at least one field (title OR plot):

```sql
-- For query "dark knight"
WHERE (LOWER(title) LIKE '%dark%' OR LOWER(plot) LIKE '%dark%')
  AND (LOWER(title) LIKE '%knight%' OR LOWER(plot) LIKE '%knight%')
```

### Result Prioritization

Results are ordered by:
1. **Title Match Count** - How many words match in title
2. **Alphabetical** - Secondary sort by title

```sql
ORDER BY 
    (CASE WHEN LOWER(title) LIKE '%word1%' THEN 1 ELSE 0 END +
     CASE WHEN LOWER(title) LIKE '%word2%' THEN 1 ELSE 0 END) DESC,
    title ASC
```

### Match Modes

1. **Contains Mode** (default)
   - All words can appear anywhere in title/plot
   - Most flexible matching

2. **Starts With Mode**
   - First word must start the title
   - Remaining words can appear anywhere
   - More precise for known titles

---

## Pagination and Performance

### Efficient Pagination

Uses "page size + 1" technique to avoid expensive COUNT(*) queries:

```python
# Request one extra item to detect if there are more pages
limit = page_size + 1
results = execute_query(sql + " LIMIT ? OFFSET ?", [limit, offset])

has_more = len(results) > page_size
if has_more:
    results = results[:-1]  # Remove extra item
```

### Performance Optimizations

1. **Batch Processing**: Handles large result sets efficiently
2. **Index Usage**: Leverages SQLite indexes for filtering
3. **Minimal Field Selection**: Only fetches needed fields
4. **Result Caching**: Session-level caching for repeated queries

---

## Search Analytics

### Query Logging

Every search is logged to `search_history` table:

```sql
INSERT INTO search_history 
(query_text, scope_type, scope_id, year_filter, sort_method, 
 include_file_path, result_count, search_duration_ms)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

### Performance Metrics

- **Search Duration**: Time from query to results
- **Result Count**: Number of matches found
- **Query Patterns**: Most common search terms
- **Performance Trends**: Search speed over time

---

## Integration Points

### UI Integration

The search integrates with UI components:

1. **SearchHandler** (`lib/ui/search_handler.py`)
   - Bridges search engines with UI
   - Handles local vs remote search selection
   - Manages error states and notifications

2. **ListItemBuilder** (`lib/ui/listitem_builder.py`)
   - Formats search results for Kodi UI
   - Handles artwork and metadata display

### Remote Search Fallback

When local search fails or is insufficient:

```python
def search(self, query, limit=200):
    # Try local search first
    local_results = self._search_local(query, limit)
    
    if local_results['total'] > 0:
        return local_results
    
    # Fallback to remote if authorized
    if is_authorized():
        return self._search_remote(query, limit)
    
    return local_results
```

---

## Configuration

### Search Settings

Users can configure search behavior:

| Setting | Default | Purpose |
|---------|---------|---------|
| `search_include_file_path` | `false` | Include file paths in search |
| `search_match_mode` | `"contains"` | Match mode (contains/starts_with) |
| `search_page_size` | `50` | Results per page (25-200) |
| `search_enable_decade_shorthand` | `false` | Enable '90s syntax |

### Runtime Configuration

```python
# Settings are loaded at runtime with fallbacks
query.include_file_path = kwargs.get("include_file_path",
    self._get_setting_bool("search_include_file_path", False))
query.match_mode = kwargs.get("match_mode",
    self._get_setting_string("search_match_mode", "contains"))
```

---

## Error Handling

### Graceful Degradation

Search handles errors gracefully:

1. **Database Errors**: Falls back to empty results
2. **Malformed Queries**: Sanitizes and continues
3. **Performance Issues**: Times out long queries

### Error Recovery

```python
try:
    # Execute search
    results = conn_manager.execute_query(sql, params)
except Exception as e:
    logger.error(f"Search failed: {e}")
    return {'items': [], 'total': 0, 'used_remote': False}
```

---

## Testing and Debugging

### Debug Logging

Comprehensive logging for troubleshooting:

```python
self.logger.debug(f"Executing SQL query: {sql}")
self.logger.debug(f"Query parameters: {params}")
self.logger.debug(f"Search returned {len(results)} results")
```

### Test Cases

Key scenarios to test:

1. **Unicode Handling**: Movies with accented characters
2. **Year Parsing**: Complex year expressions
3. **Large Libraries**: Performance with 10,000+ movies
4. **Edge Cases**: Empty queries, special characters
5. **Pagination**: Boundary conditions

---

## Best Practices

### For Users

1. **Use Explicit Years**: Prefix with `year:` for precise filtering
2. **Keep Queries Simple**: Fewer words often work better
3. **Use Quotes**: For exact phrase matching (future feature)

### For Developers

1. **Parameterized Queries**: Always use parameter binding
2. **Index Optimization**: Ensure proper database indexes
3. **Error Handling**: Fail gracefully with useful messages
4. **Performance Monitoring**: Track search times and optimize

---

## Future Enhancements

### Planned Features

1. **Fuzzy Matching**: Handle typos and approximations
2. **Weighted Results**: Boost results by popularity/rating
3. **Saved Searches**: Store and recall common queries
4. **Search Suggestions**: Auto-complete based on library
5. **Advanced Filters**: Genre, director, rating ranges

### Performance Improvements

1. **Full-Text Search**: SQLite FTS5 integration
2. **Search Indexes**: Optimized indexing strategies
3. **Caching Layer**: In-memory result caching
4. **Background Indexing**: Async index updates

---

This documentation provides a comprehensive overview of LibraryGenie's local search functionality. For implementation details, refer to the source code in the `lib/search/` directory.
