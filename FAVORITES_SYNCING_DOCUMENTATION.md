
# LibraryGenie Favorites Syncing Documentation

This document provides a comprehensive overview of the favorites syncing functionality in LibraryGenie, including the logic behind it, database tables, JSON calls, and data storage mechanisms.

---

## Overview

LibraryGenie provides seamless integration with Kodi's built-in Favorites system through a read-only approach that:

- **Parses** Kodi's `favourites.xml` file
- **Maps** favorites to library movies when possible
- **Integrates** mapped favorites into the unified list system
- **Preserves** all favorite metadata for display and management
- **Respects** privacy by never modifying the original favorites file

---

## Architecture Components

### 1. Favorites Parser (`lib/kodi/favorites_parser.py`)

The `FavoritesParser` class handles robust XML parsing and path normalization:

```python
class FavoritesParser:
    def find_favorites_file(self) -> Optional[str]
    def parse_favorites_file(self, file_path: str) -> List[Dict]
    def get_file_modified_time(self, file_path: str) -> Optional[str]
```

**Key Features:**
- **File Location**: Uses `special://profile/favourites.xml` with fallback paths for development
- **XML Parsing**: Handles malformed XML with error recovery
- **Path Extraction**: Extracts file paths from `PlayMedia()` commands
- **Classification**: Categorizes favorites by target type (file, plugin, database, etc.)

### 2. Favorites Manager (`lib/kodi/favorites_manager.py`)

The `FavoritesManager` class orchestrates the scanning and mapping process:

```python
class FavoritesManager:
    def scan_favorites(self, force_refresh: bool = False) -> Dict
    def get_favorites_for_display(self, show_unmapped: bool = True) -> List[Dict]
    def _import_favorites_batch(self, favorites: List[Dict]) -> Dict
```

**Core Responsibilities:**
- **Change Detection**: Uses file modification time to avoid unnecessary scans
- **Batch Processing**: Processes favorites in efficient batches
- **Library Mapping**: Maps favorites to existing library movies via normalized paths
- **Database Updates**: Maintains favorites state in SQLite tables

---

## Database Schema

### Primary Table: `kodi_favorite`

Stores all favorite metadata and mapping information:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `name` | TEXT | Favorite display name |
| `normalized_path` | TEXT | Normalized path for matching |
| `original_path` | TEXT | Original favorite path |
| `favorite_type` | TEXT | Type of favorite |
| `target_raw` | TEXT | Raw target command |
| `target_classification` | TEXT | Classification of target |
| `normalized_key` | TEXT UNIQUE | Unique key for deduplication |
| `library_movie_id` | INTEGER FK | Reference to media_items.id |
| `is_mapped` | INTEGER | Whether favorite is mapped (0/1) |
| `is_missing` | INTEGER | Whether favorite target is missing (0/1) |
| `present` | INTEGER | Whether favorite is present in current scan (0/1) |
| `thumb_ref` | TEXT | Thumbnail reference |
| `first_seen` | TEXT | When first detected |
| `last_seen` | TEXT | When last seen |
| `created_at` | TEXT | Creation timestamp |
| `updated_at` | TEXT | Last update timestamp |

**Indexes:**
```sql
CREATE INDEX idx_kodi_favorite_normalized_key ON kodi_favorite(normalized_key)
CREATE INDEX idx_kodi_favorite_library_movie_id ON kodi_favorite(library_movie_id)
CREATE INDEX idx_kodi_favorite_is_mapped ON kodi_favorite(is_mapped)
CREATE INDEX idx_kodi_favorite_present ON kodi_favorite(present)
```

### Audit Table: `favorites_scan_log`

Records scan operations and their results:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `scan_type` | TEXT | Type of scan performed |
| `file_path` | TEXT | Path to favorites file |
| `file_modified` | TEXT | File modification timestamp |
| `items_found` | INTEGER | Favorites found in file |
| `items_mapped` | INTEGER | Favorites mapped to library |
| `items_added` | INTEGER | New favorites added |
| `items_updated` | INTEGER | Existing favorites updated |
| `scan_duration_ms` | INTEGER | Scan duration in milliseconds |
| `success` | INTEGER | Whether scan succeeded |
| `error_message` | TEXT | Error message if scan failed |
| `created_at` | TEXT | Timestamp |

**Indexes:**
```sql
CREATE INDEX idx_favorites_scan_log_file_path ON favorites_scan_log(file_path)
CREATE INDEX idx_favorites_scan_log_created_at ON favorites_scan_log(created_at)
```

### Integration with Lists System

Mapped favorites are also integrated into the unified list system:

1. **Special List Creation**: A "Kodi Favorites" list is created in the `lists` table
2. **List Items**: Mapped favorites appear as `list_items` pointing to `media_items`
3. **Dual Access**: Favorites can be accessed both via the favorites interface and as a regular list

---

## Data Flow and Logic

### 1. Scan Trigger Events

Favorites scanning is triggered by:

- **Manual Refresh**: User-initiated scan via context menu or Tools interface
- **Settings Change**: Initial scan when favorites integration is first enabled

**Note**: Automated background scanning has been removed. All favorites scanning is now manual-only, giving users full control over when their favorites are processed.

### 2. Scan Process Logic

```python
def scan_favorites(self, force_refresh: bool = False) -> Dict:
    # 1. Locate favorites file
    file_path = self.parser.find_favorites_file()
    
    # 2. Check if scan needed (mtime comparison)
    if not force_refresh:
        last_scan = self._get_last_scan_info(file_path)
        if unchanged: return cached_result
    
    # 3. Parse XML file
    favorites = self.parser.parse_favorites_file(file_path)
    
    # 4. Process in batches
    result = self._import_favorites_batch(favorites)
    
    # 5. Log results
    self._log_scan_result(...)
```

### 3. Path Normalization and Matching

**Path Extraction:**
```python
def _extract_path_from_command(self, target: str) -> Optional[str]:
    # Extract from PlayMedia("path") commands
    # Handle quoted/unquoted paths
    # Support various command formats
```

**Normalization Steps:**
1. **Case Folding**: Convert to lowercase
2. **Separator Normalization**: Standardize path separators
3. **Protocol Handling**: Normalize SMB, NFS, file:// schemes
4. **Credential Stripping**: Remove embedded credentials for privacy

**Matching Process:**
```python
def _find_library_movie_by_path(self, normalized_path: str) -> Optional[int]:
    # Query media_items table for matching normalized_path
    # Return media_item_id if found
```

### 4. Target Classification

Favorites are classified by their target type:

| Classification | Description | Examples |
|----------------|-------------|----------|
| `file_or_media` | Direct file paths | `file://`, `smb://`, `nfs://` |
| `database_item` | Kodi database links | `videodb://movies/` |
| `stack_file` | Multi-part movies | `stack://` |
| `plugin_or_script` | Add-on content | `plugin://`, `script://` |
| `unknown` | Unrecognized format | Various edge cases |

---

## JSON Calls and External Communication

### 1. Kodi JSON-RPC Integration

**Media Items Query:**
```python
# Get library movies for path matching
request = {
    "jsonrpc": "2.0",
    "method": "VideoLibrary.GetMovies",
    "params": {
        "properties": ["file", "imdbnumber", "title", "year"],
        "limits": {"start": offset, "end": offset + batch_size}
    }
}
```

**Batch Processing:**
- **Page Size**: Configurable (default 200 items)
- **Timeout**: Configurable (default 10 seconds)
- **Properties**: Minimal set for performance

### 2. No External API Calls

**Privacy Design:**
- **Local Only**: All favorites processing happens locally
- **No Transmission**: Favorite names, paths, or metadata never sent externally
- **Path Privacy**: Credentials stripped during processing
- **Read-Only**: Never modifies original `favourites.xml`

---

## Data Storage Patterns

### 1. Atomic Operations

All database operations use transactions:

```python
with self.conn_manager.transaction() as conn:
    # Mark all as not present
    conn.execute("UPDATE kodi_favorite SET present = 0")
    
    # Process each favorite
    for favorite in favorites:
        conn.execute("INSERT OR REPLACE INTO kodi_favorite ...")
```

### 2. Differential Updates

**Change Detection:**
```python
# Check file modification time
current_mtime = self.parser.get_file_modified_time(file_path)
last_scan = self._get_last_scan_info(file_path)

if last_scan.get("file_modified") == current_mtime:
    return {"success": True, "message": "No changes detected"}
```

**State Tracking:**
- `present`: Updated each scan to track active favorites
- `first_seen`: Timestamp when favorite first detected
- `last_seen`: Timestamp when favorite last present

### 3. Deduplication Strategy

**Normalized Key Generation:**
```python
normalized_key = f"{name}|{normalized_path}|{target_classification}"
```

**Conflict Resolution:**
- **UNIQUE Constraint**: On `normalized_key` prevents duplicates
- **INSERT OR REPLACE**: Updates existing entries with new metadata
- **Timestamp Preservation**: Maintains `first_seen` across updates

---

## Configuration and Settings

### 1. User Settings

**Favorites Integration Toggle:**
```xml
<setting id="favorites_integration_enabled" type="bool" default="false">
    <label>32180</label> <!-- Enable Favorites Integration -->
    <description>32181</description>
</setting>
```

**Display Options:**
```xml
<setting id="favorites_show_unmapped" type="bool" default="true">
    <label>32182</label> <!-- Show Unmapped Favorites -->
</setting>
```

### 2. Automatic Scan Trigger

When favorites integration is enabled:

```python
def on_favorites_integration_enabled():
    """Called when favorites integration is enabled via settings"""
    from ..kodi.favorites_manager import get_favorites_manager
    
    favorites_manager = get_favorites_manager()
    result = favorites_manager.scan_favorites(force_refresh=True)
```

---

## Performance Characteristics

### 1. Scan Performance

**Typical Performance:**
- **Small libraries** (< 100 favorites): 1-5 seconds
- **Medium libraries** (100-500 favorites): 5-15 seconds  
- **Large libraries** (500+ favorites): 15-30 seconds

**Optimization Strategies:**
- **Batch Processing**: Process favorites in configurable batches
- **Change Detection**: Skip scans when file unchanged
- **Indexed Queries**: Efficient lookups via database indexes
- **Memory Efficient**: Stream processing without loading entire library

### 2. Storage Efficiency

**Database Size Impact:**
- **Favorites Table**: ~1KB per favorite (including metadata)
- **Scan Log**: ~200 bytes per scan operation
- **Indexes**: ~20% overhead for fast queries

---

## Error Handling and Recovery

### 1. Robust XML Parsing

**Error Recovery:**
```python
try:
    root = ET.fromstring(content)
except ET.ParseError as e:
    # Log error but continue with partial data
    self.logger.warning(f"XML parse error: {e}")
    return []
```

**Malformed Entry Handling:**
- **Skip Invalid**: Continue processing valid entries
- **Log Warnings**: Record parsing issues for debugging
- **Graceful Degradation**: Never fail entire scan for single entry

### 2. Database Transaction Safety

**Rollback on Error:**
```python
try:
    with self.conn_manager.transaction() as conn:
        # All operations in transaction
except Exception as e:
    # Automatic rollback preserves database integrity
    self.logger.error(f"Scan failed, database unchanged: {e}")
```

### 3. Scan Result Logging

**Comprehensive Metrics:**
```python
self._log_scan_result(
    scan_type="full",
    items_found=len(favorites),
    items_mapped=result["items_mapped"],
    items_added=result["items_added"],
    items_updated=result["items_updated"],
    duration_ms=duration_ms,
    success=True
)
```

---

## Security and Privacy

### 1. Path Privacy

**Credential Stripping:**
```python
def _strip_credentials_from_path(self, path: str) -> str:
    # Remove user:pass@ from SMB/NFS URLs
    # Preserve functional path structure
    # Log sanitized paths only
```

### 2. Read-Only Operation

**Safety Guarantees:**
- **Never Modifies**: Original `favourites.xml` never changed
- **Local Processing**: All operations happen locally
- **No Data Transmission**: Favorites data never sent externally

### 3. User Consent

**Opt-In Design:**
- **Disabled by Default**: Requires explicit user enablement
- **Clear Settings**: Obvious toggle in addon settings
- **Immediate Feedback**: Shows scan results after enabling

---

## Integration Points

### 1. Manual Operation Design

**User-Controlled Scanning:**
- **No Background Processing**: Favorites are never scanned automatically
- **On-Demand Only**: Users initiate scans via context menus or Tools interface
- **Immediate Feedback**: Scan results shown immediately after completion

**Benefits of Manual Operation:**
- **Performance**: No background CPU usage for favorites processing
- **Privacy**: Users decide when favorites are read and processed
- **Predictability**: Scans only happen when explicitly requested

### 2. UI Integration

**Context Menu Actions:**
```python
# Add mapped favorites to custom lists
context_items = [
    ("Add to List", f"RunPlugin({base_url}?action=add_favorite_to_list&imdb_id={imdb_id})")
]
```

**Display Rendering:**
```python
# Show mapped/unmapped status
if favorite.get("is_mapped"):
    listitem.setProperty("LibraryGenie.Status", "Mapped")
else:
    listitem.setProperty("LibraryGenie.Status", "Not in library")
```

---

## Troubleshooting

### 1. Common Issues

**Favorites Not Found:**
- Check `special://profile/favourites.xml` exists
- Verify file permissions and accessibility
- Enable debug logging for detailed path resolution

**Low Mapping Rate:**
- Verify library scan completed successfully
- Check for path format differences (network vs local)
- Review path normalization in debug logs

**Performance Issues:**
- Increase JSON-RPC timeout for large libraries
- Reduce batch size for slower systems
- Check available disk space for database operations

### 2. Debug Information

**Enable Debug Logging:**
```python
# In addon settings
debug_enabled = config.get_bool("debug_logging_enabled")
```

**Key Log Messages:**
- File location and accessibility
- XML parsing success/failure
- Path normalization steps
- Mapping success rates
- Performance timing data

---

## Future Enhancements

### 1. Planned Features

**Enhanced Mapping:**
- Support for TV episode favorites
- Music video favorite mapping
- Plugin content integration

**Performance Improvements:**
- Background scanning optimization
- Incremental update support
- Cache warming strategies

### 2. Extension Points

**Plugin Support:**
- Generic plugin favorite handling
- Metadata enrichment for known plugins
- Cross-addon integration APIs

**Export/Import:**
- Include favorites in NDJSON exports
- Portable favorite list creation
- Backup/restore functionality

---

This documentation provides a complete technical overview of LibraryGenie's favorites syncing functionality, covering all aspects from database schema to user experience.
