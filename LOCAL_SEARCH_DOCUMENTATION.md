
# LibraryGenie Local Search Documentation

This document provides detailed documentation on LibraryGenie's local search functionality, including architecture, implementation details, search algorithms, and usage patterns.

---

## Overview

LibraryGenie's local search system provides fast, offline search capabilities across the user's Kodi video library. The search is powered by a SQLite database index with keyword-based matching and intelligent result ranking.

### Key Features

- **Database-Backed Search**: Uses SQLite index for fast queries against local library
- **Keyword-Based Matching**: Simple, predictable keyword search across title and plot fields
- **Intelligent Ranking**: Prioritizes title matches over plot matches for better relevance
- **Text Normalization**: Handles diacritics, punctuation, case, and Unicode consistently
- **Flexible Search Scope**: Search titles only, plots only, or both fields
- **Match Logic Options**: "All keywords" or "any keyword" matching
- **Search History**: Automatic saving of search results to browsable lists

---

## Architecture

LibraryGenie's search system consists of several key components:

### Core Components

1. **Simple Search Engine** (`lib/search/simple_search_engine.py`)
   - Main search interface with database-backed keyword matching
   - Supports configurable search scope (title, plot, both)
   - Implements intelligent result ranking and filtering

2. **Query Interpreter** (`lib/search/simple_query_interpreter.py`)
   - Processes user input into structured search queries
   - Handles keyword extraction and normalization
   - Supports match logic configuration (all/any keywords)

3. **Text Normalizer** (`lib/search/normalizer.py`)
   - Unicode normalization and diacritic handling
   - Punctuation and whitespace cleaning
   - Case-insensitive matching support

4. **Search Query Object** (`lib/search/simple_search_query.py`)
   - Encapsulates search parameters and configuration
   - Manages scope, keywords, and match logic settings

### Database Integration

The search system leverages the `media_items` table with optimized queries:

```sql
-- Example search query structure
SELECT * FROM media_items 
WHERE (title LIKE ? OR plot LIKE ?) 
AND is_removed = 0 
ORDER BY (CASE WHEN title LIKE ? THEN 1 ELSE 2 END), title
```

### Search Flow

1. **Input Processing**: User query → Query Interpreter → Normalized keywords
2. **Database Query**: Keywords → SQL LIKE patterns → Result set
3. **Ranking**: Title matches prioritized over plot matches
4. **History**: Results saved to browsable search history lists

---

## Implementation Details

### Search Scope Options

- **Title Only**: Search only in media title fields
- **Plot Only**: Search only in plot/description fields  
- **Both**: Search across both title and plot fields (default)

### Match Logic

- **All Keywords**: All keywords must be present (AND logic)
- **Any Keyword**: Any keyword match returns result (OR logic)

### Result Ranking

1. **Primary Sort**: Title matches ranked higher than plot-only matches
2. **Secondary Sort**: Alphabetical by title within each group
3. **Filtering**: Automatically excludes removed/missing items

### Text Processing

The normalizer handles:
- **Unicode Normalization**: NFD decomposition for consistent character handling
- **Diacritic Removal**: Strips accents and diacritical marks
- **Case Folding**: Converts to lowercase for case-insensitive matching  
- **Punctuation Handling**: Removes or normalizes punctuation marks
- **Whitespace Cleanup**: Normalizes spaces and removes extra whitespace

### Components

1. **SimpleSearchEngine** (`lib/search/simple_search_engine.py`)
   - Main search orchestrator with ranking-based results
   - Handles keyword matching across title and plot fields
   - Implements SQL-based ranking for result prioritization

2. **SimpleSearchQuery** (`lib/search/simple_search_query.py`)
   - Represents a search query with keywords and options
   - Supports scope (library/list) and field selection
   - Includes pagination parameters

3. **TextNormalizer** (`lib/search/normalizer.py`)
   - Unified text normalization for consistent matching
   - Unicode handling and diacritic removal
   - Deterministic, language-agnostic normalization rules

4. **SimpleQueryInterpreter** (`lib/search/simple_query_interpreter.py`)
   - Parses user input into structured search queries
   - Tokenizes input text into searchable keywords
   - Applies search settings and scope configuration

5. **SearchHandler** (`lib/ui/search_handler.py`)
   - UI integration for search functionality
   - Manages user prompts and result display
   - Handles search history creation and navigation

---

## Search Flow

### Basic Search Process

1. **Input Processing**
   ```
   User Input → SimpleQueryInterpreter → SimpleSearchQuery
   ```

2. **Query Execution**
   ```
   SimpleSearchQuery → SimpleSearchEngine → SQL with Ranking → Database Query
   ```

3. **Result Display**
   ```
   Ranked Results → Search History List → UI Navigation
   ```

### Example Search Flow

```python
# User searches for "batman dark"
user_input = "batman dark"

# QueryInterpreter processes input
query = interpreter.parse_query(user_input)
# query.keywords = ["batman", "dark"]
# query.search_scope = "both"
# query.match_logic = "all"

# SimpleSearchEngine builds ranked SQL
sql = """
SELECT ..., 
  CASE 
    WHEN (title_matches) = 2 THEN 1  -- All keywords in title
    WHEN (title_matches) > 0 THEN 2  -- Some keywords in title
    WHEN (plot_matches) = 2 THEN 3   -- All keywords in plot
    WHEN (plot_matches) > 0 THEN 4   -- Some keywords in plot
    ELSE 5
  END as search_rank
FROM media_items 
WHERE (title LIKE '%batman%' OR plot LIKE '%batman%') 
  AND (title LIKE '%dark%' OR plot LIKE '%dark%')
ORDER BY search_rank ASC, title ASC
"""

# Results saved to search history and displayed
```

---

## Database Schema Integration

### Primary Table: `media_items`

The search operates on the `media_items` table:

| Field | Purpose in Search |
|-------|------------------|
| `title` | Primary text matching field |
| `plot` | Secondary text matching field |
| `media_type` | Filter movies vs episodes |
| `kodi_id` | Link to Kodi library |
| `imdbnumber` | Universal identifier |

### Search Indexes

Key indexes for search performance:
- `media_type` for filtering movies/episodes
- Text search relies on SQLite's built-in LIKE operations

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

## Search Algorithms

### Keyword Matching

Each keyword must match in at least one configured field:

**Search Scope "both" with Match Logic "all":**
```sql
WHERE (LOWER(title) LIKE '%keyword1%' OR LOWER(plot) LIKE '%keyword1%')
  AND (LOWER(title) LIKE '%keyword2%' OR LOWER(plot) LIKE '%keyword2%')
```

**Search Scope "title" with Match Logic "any":**
```sql
WHERE (LOWER(title) LIKE '%keyword1%' OR LOWER(title) LIKE '%keyword2%')
```

### Result Ranking

Results are ranked by match quality using SQL CASE expressions:

1. **Rank 1**: All keywords match in title
2. **Rank 2**: Some keywords match in title
3. **Rank 3**: All keywords match in plot
4. **Rank 4**: Some keywords match in plot
5. **Rank 5**: Default (should not occur with proper WHERE clauses)

```sql
ORDER BY 
    CASE 
        WHEN (title_match_count) = total_keywords THEN 1
        WHEN (title_match_count) > 0 THEN 2
        WHEN (plot_match_count) = total_keywords THEN 3
        WHEN (plot_match_count) > 0 THEN 4
        ELSE 5
    END ASC,
    LOWER(title) ASC
```

---

## Search Configuration

### Query Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `search_scope` | `"title"`, `"plot"`, `"both"` | `"both"` | Fields to search |
| `match_logic` | `"all"`, `"any"` | `"all"` | Keyword matching logic |
| `scope_type` | `"library"`, `"list"` | `"library"` | Search within library or specific list |
| `scope_id` | `int` | `None` | List ID when scope_type is "list" |
| `page_size` | `int` | `50` | Results per page |
| `page_offset` | `int` | `0` | Pagination offset |

### Search Scope Options

- **"title"**: Search only in movie/episode titles
- **"plot"**: Search only in plot summaries
- **"both"**: Search across both title and plot fields (default)

### Match Logic Options

- **"all"**: All keywords must be found (AND logic)
- **"any"**: Any keyword can match (OR logic)

---

## Search History

### Automatic History Creation

All successful searches are automatically saved to search history:

1. **Search Execution**: User performs search with results
2. **History List Creation**: New list created in "Search History" folder
3. **Result Population**: Search results added to the history list
4. **Navigation**: User redirected to view the search history list

### History List Naming

Search history lists are named with the search terms:
- Format: `"Search: {keywords}"`
- Example: `"Search: batman dark"`

### Search History Folder

All search history is organized under a dedicated folder:
- **Folder Name**: "Search History"
- **Auto-Creation**: Created automatically on first search
- **Organization**: Lists sorted by creation date (newest first)

---

## Performance Considerations

### Query Optimization

- **Parameterized Queries**: All user input safely parameterized
- **Efficient LIKE Operations**: Uses SQLite's optimized string matching
- **Ranking in SQL**: Ranking calculated at database level for performance
- **Limited Result Sets**: Pagination prevents large result set issues

### Memory Management

- **Lightweight Results**: Only essential fields returned in search results
- **Streaming Results**: Results processed as returned from database
- **Connection Reuse**: Database connections managed by connection pool

---

## Integration Points

### UI Integration

The search integrates with UI components:

1. **SearchHandler** (`lib/ui/search_handler.py`)
   - Provides search dialog and user interaction
   - Manages search execution and result navigation
   - Handles error states and user notifications

2. **Router Integration**
   - Search accessible via `action=search` parameter
   - Results displayed through standard list navigation
   - Search history accessible via normal list browsing

### List Integration

Search results are seamlessly integrated with the list system:
- **Search History Lists**: Standard lists containing search results
- **Context Menus**: Full context menu support on search results
- **List Management**: Search history lists can be renamed, deleted, etc.

---

## Error Handling

### Graceful Degradation

Search handles errors gracefully:

1. **Database Errors**: Returns empty results with error logging
2. **Malformed Input**: Sanitizes input and continues with valid portions
3. **No Results**: Shows appropriate user message

### Error Recovery

```python
try:
    # Execute search
    results = conn_manager.execute_query(sql, params)
except Exception as e:
    logger.error(f"Search failed: {e}")
    result = SimpleSearchResult()
    result.query_summary = "Search error"
    return result
```

---

## Current Limitations

### Removed Features

The following features were present in earlier versions but have been removed for simplification:

- **Year Filtering**: No special year parsing or filtering
- **File Path Search**: No searching within file paths
- **Advanced Query Syntax**: No special operators or prefixes
- **Pagination Controls**: Results are saved to lists instead of paginated views
- **Search Analytics**: No detailed search performance tracking
- **Multiple Search Engines**: Only the simplified engine is available

### Design Decisions

- **Simplicity Over Features**: Focus on reliable, predictable keyword search
- **List-Based Results**: Search results saved as browsable lists rather than temporary views
- **Automatic History**: All searches automatically saved for later browsing
- **Fixed Configuration**: Minimal user configuration options

---

## Testing and Debugging

### Debug Logging

Search operations include comprehensive logging:

```python
self.logger.debug(f"Executing search SQL: {sql}")
self.logger.debug(f"Search SQL parameters: {params}")
self.logger.debug(f"Simple search completed: {result.total_count} results in {result.search_duration_ms}ms")
```

### Test Scenarios

Key scenarios to test:

1. **Unicode Handling**: Movies with accented characters
2. **Keyword Combinations**: Multiple keyword searches
3. **Empty Results**: Searches that return no matches
4. **Large Libraries**: Performance with thousands of movies
5. **Special Characters**: Searches containing punctuation

---

## Best Practices

### For Users

1. **Use Simple Keywords**: Enter movie titles or plot keywords directly
2. **Try Different Combinations**: If no results, try fewer or different keywords
3. **Browse Search History**: Previous searches are saved as browsable lists

### For Developers

1. **Parameterized Queries**: Always use parameter binding for user input
2. **Error Handling**: Fail gracefully with useful error messages
3. **Performance Monitoring**: Log search execution times
4. **Input Validation**: Sanitize user input before processing

---

This documentation reflects the current simplified search implementation in LibraryGenie. The search system prioritizes reliability and simplicity over advanced features.
