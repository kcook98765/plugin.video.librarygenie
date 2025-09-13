
# LibraryGenie — Robust List Management for Kodi

LibraryGenie is a Kodi addon that provides advanced, flexible list and folder management with disaster recovery, portability, and intelligent media matching. It supports mixed content types, portable exports, and optional integration with external services.

---

## Overview

- Mixed content lists (movies, TV episodes, external plugin items).
- IMDb-first architecture with multiple fallback strategies.
- Robust export/import system with disaster recovery support.
- SQLite backend with safe transaction handling and optimized indexing.
- Optional integration with external search/similarity services (requires explicit user authorization).

---

## Key Features

### Media Types
- **Movies**: Full Kodi movie library support.
- **TV Episodes**: Episode-level handling with show/season/episode mapping.
- **External Items**: Playable plugin items from any addon, with context menu integration for easy list management.

### Lists & Folders
- Hierarchical folder structure with unlimited depth.
- **Tools & Options Menu**: Context-aware tools for list and folder management.
- Create, rename, move, and delete lists and folders with color-coded actions.
- Add/remove items via context menus from anywhere in Kodi.
- **Universal Context Menu**: Add any playable media to lists - movies, episodes, and plugin content.
- **Quick Save Feature**: Optional quick-add functionality to a configured default list with single-click access.
- **Dual Context Options**: When quick save is enabled, context menu shows both "Quick Add to Default List" and "Add to List..." options.
- Export functionality integrated into tools menu.
- Duplicate detection and unique constraint handling.
- Transaction-safe modifications to prevent corruption.

### Import & Export
- **Unified Format**: Backup, export, and import all use NDJSON format with consistent field schemas.
- **Universal Compatibility**: NDJSON format supports manual export, automated backup, and restore operations.
- **Manual Backups**: On-demand backup creation via Tools menu with timestamp-based naming.
- **Local & Network Storage**: Support for local paths and network shares configured in Kodi.
- **Tools Integration**: Export and backup accessible via Tools & Options menu with context-aware options.
- **IMDb-First Matching**: Highest-confidence mapping across systems for import/restore operations.
- **Enhanced Metadata**: Additional identifiers (TMDb, Kodi IDs, file paths) for robust fallback matching.
- **Fallbacks**: TMDb IDs, title/year, season/episode when IMDb is missing.
- **Safe Import**: Validation and preview before import, with duplicate detection and error handling.
- **Batch Operations**: Efficient chunked import/export of large lists.

#### Example Files

**export.ndjson:**
```
{"media_type": "movie", "imdb_id": "tt0111161", "title": "The Shawshank Redemption", "year": 1994, "list_name": "My Favorites"}
{"media_type": "episode", "show_title": "Breaking Bad", "season": 1, "episode": 1, "episode_title": "Pilot", "list_name": "TV Shows"}
```

**export.meta.json:**
```json
{
  "addon_version": "2.1.0",
  "schema_version": 3,
  "export_types": ["lists", "list_items"],
  "generated_at": "2025-09-12T15:30:00Z"
}
```

### Metadata Matching
- **Movies**: IMDb → TMDb (optional) → title/year/runtime fallback.
- **Episodes**: Episode IMDb → show IMDb + season/episode → show title fallback.
- **External Items**: Plugin identifiers and routes.

### Backup & Recovery
- **Manual Backups**: On-demand backup creation via Tools menu with timestamp-based naming.
- **Flexible Storage**: Local paths or network shares (SMB/NFS) configured in Kodi settings.
- **Backup Management**: List, restore, and delete backups through the Tools interface.
- **Configurable Coverage**: Backup lists and folders by default, with optional external items (plugins).
- **External Items Setting**: External plugin content excluded by default to reduce backup size, configurable via `backup_include_non_library` setting.
- **Storage Optimized**: No database logging during backup operations to minimize storage overhead on user devices.
- **Disaster Recovery**: Full system restore from unified backup files using same format as exports.
- **Cross-Compatible**: Backup files can be manually imported on other systems or after fresh installs.

### Performance
- **Database-First Architecture**: List operations use stored metadata instead of JSON-RPC calls
- **Enhanced Library Scanning**: Comprehensive lightweight metadata stored during scanning
- **Optimized List Building**: Single database queries replace multiple JSON-RPC batch calls
- **Selective Heavy Data**: Cast, streamdetails, and extensive artwork excluded from default storage
- **Cache-Friendly Schema**: Memory mappings and indexes optimized for large libraries (10k+ items)
- **Consistent Performance**: List loading times remain fast regardless of library size

---

## Export/Import Specification

### NDJSON Format
Uses NDJSON (newline-delimited JSON) format with separate metadata file:

**Export Structure:**
- `export.ndjson` - One JSON object per line for each media item
- `export.meta.json` - Metadata file with schema version and export info

**Media Item Fields:**

| Field           | Type    | Required | Notes                                      |
|-----------------|---------|----------|--------------------------------------------|
| media_type      | string  | yes      | `movie`, `episode`, `external` |
| imdb_id         | string  | no       | `tt…` identifier if available              |
| title           | string  | yes      | Title of item                              |
| year            | integer | no       | Release or air year                        |
| list_name       | string  | yes      | Context list name                          |

#### Movies
- `tmdb_id`, `runtime_minutes`.

#### Episodes
- `show_imdb_id`, `show_title`, `season`, `episode`, `air_date`, `episode_title`.


#### External Items
- `plugin_id`, `plugin_version`, `plugin_route`.

### Import Matching
Priority:
1. IMDb ID.
2. TMDb ID.
3. Title+Year fuzzy match.
4. Plugin identifiers.
5. Placeholder creation.

Normalization: case-folding, whitespace collapsing, article stripping.
Confidence scoring: 100% (IMDb) → 95% (TMDb) → 75–90% (title/year) → fallback placeholders.

---

## Settings & Configuration

- **Set Default List**: Button-style action opens list picker when lists exist, shows helpful message when none available.
- **Quick Save**: Enable quick-add functionality to bypass list selection dialog and add directly to default list.
- **Background Tasks**: Configurable interval (5-720 minutes) with safe defaults and clamping.
- **Backup Settings**: Storage location configuration for manual backup operations.
- **Storage Configuration**: Local paths and network share support via Kodi file settings.
- **Organized Categories**: Settings grouped into General, Lists, Background, and Backup sections.
- **Privacy-First**: External features disabled by default, require explicit user authorization.

## External Integration (Optional and not yet open to public)

- Disabled by default; requires user authorization.
- **Remote Search**: Free-text queries → AI RAG search → IMDb ID lists returned.
- **Similarity**: Given IMDb → AI RAG similarity search →  IMDb IDs.
- **Sync**: Required mirroring of user's IMDB list with server (IMDb only).
- **Privacy**: Only IMDb IDs and user queries transmitted; no file paths or playback data.

---

## Search Features

LibraryGenie provides powerful local search capabilities:

### Search Features

- **Database-Backed Search**: Uses SQLite index for fast queries against local library
- **Keyword-Based Matching**: Simple, predictable keyword search across title and plot fields
- **Intelligent Ranking**: Prioritizes title matches over plot matches for better relevance
- **Text Normalization**: Handles diacritics, punctuation, case, and Unicode consistently
- **Flexible Search Scope**: Search titles only, plots only, or both fields
- **Match Logic Options**: "All keywords" or "any keyword" matching
- **Search History**: Automatic saving of search results to browsable lists

### Search Configuration

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `search_scope` | `"title"`, `"plot"`, `"both"` | `"both"` | Fields to search |
| `match_logic` | `"all"`, `"any"` | `"all"` | Keyword matching logic |
| `page_size` | `int` | `50` | Results per page |

---

## Favorites Integration (Manual Operation)

LibraryGenie provides manual integration with Kodi's built-in Favorites system:

- **Scan on Demand**: Manually scan favorites via Tools menu or context actions
- **View Mapped Favorites**: Display favorites that map to your movie library
- **Quick Add**: Add mapped favorites to your custom lists
- **Smart Filtering**: Option to show/hide unmapped favorites
- **Robust Parsing**: Handles various favorites.xml formats and edge cases

**Manual Operation**: All favorites scanning is user-initiated. No background processing ensures optimal performance and gives you full control over when favorites are processed.

### Supported Target Types

- **File Paths**: Local files, network shares (SMB/NFS), archives (ZIP/RAR)
- **Kodi Database**: videodb:// URLs linking to library movies
- **Stack Files**: Multi-part movies defined as stack:// entries

### Privacy & Safety

- **Read-Only**: Never modifies your Kodi favorites file
- **Local Processing**: All parsing and mapping happens locally
- **No Data Collection**: No favorite names, paths, or metadata transmitted externally
- **Path Privacy**: Credentials stripped from network paths during processing

---

## Technical Notes

- Runs on Kodi 19+.
- Python 3.x, Kodi Python API.
- SQLite backend with WAL/PRAGMA tuning for low-power devices.
- JSON-RPC integration with batching and selective property fetching.
- Clear separation between UI (routes/dialogs), data (DB/mapping), and features (lists/export/import/sync).

---

### Plugin Architecture

The plugin uses a modular handler-based architecture:
- **Router**: Central request dispatcher (`lib/ui/router.py`)
- **Handlers**: Specialized UI handlers for different functionality
- **Response Types**: Structured response objects for consistent UI handling
- **Context**: Request context object for parameter access

### From Zip Package

1. Download the latest `plugin.video.library.genie-[version].zip` from releases
2. Install via Kodi: Settings → Add-ons → Install from zip file
3. The addon will be available in Videos → Video add-ons

---

## Troubleshooting

### Performance Issues with Large Libraries

If you experience slow scans or timeouts with large movie libraries (1000+ movies):

1. **Adjust JSON-RPC Settings**: In addon settings → Advanced → JSON-RPC Performance:
   - Increase JSON-RPC timeout to 15-20 seconds for slower systems
   - Reduce JSON-RPC page size to 100-150 for very large libraries

2. **Database Optimization**: In addon settings → Advanced → Database Performance:
   - Increase database batch size to 300-400 for faster bulk operations
   - Increase database busy timeout to 5000-7000ms for busy systems

3. **Background Task Settings**: In addon settings → Background:
   - Increase background interval to 60-120 minutes for large libraries
   - Disable background tasks temporarily during heavy usage periods

### Common Error Messages

**"Database connection failed"**
- Check available disk space in Kodi userdata folder
- Restart Kodi to reset database connections
- Check addon logs for specific SQLite errors

**"JSON-RPC request timed out"**
- Library scan was interrupted due to slow response
- Increase JSON-RPC timeout in Advanced settings
- Try manual library scan during low system usage

**"Migration failed"**
- Database schema update encountered an error
- Enable debug logging and check logs for details
- Backup userdata and reinstall addon if issues persist

### Reset and Recovery

If the addon stops working correctly:

1. **Soft Reset**: Clear addon data in Kodi settings → Add-ons → Installed → Video add-ons → LibraryGenie → Configure
2. **Database Reset**: Delete `movie_lists.db` from addon_data folder to start fresh
3. **Complete Reinstall**: Uninstall addon, delete addon_data folder, reinstall

### Performance Baselines

Expected performance for reference systems:

- **Small library** (< 500 movies): Full scan in seconds, Delta scan in seconds
- **Medium library** (500-2000 movies): Full scan seconds to minutes, Delta scan 10-30 seconds
- **Large library** (2000+ movies): Full scan 1-15 minutes, Delta scan 30-60 seconds

Times may vary significantly based on network storage, system performance, and library metadata complexity.


---

## Status

**Phase 5 - Full List Management**: Complete local-only list management functionality with CRUD operations, user interface flows, and persistent SQLite storage. Create, rename, and delete lists with confirmation dialogs and item counts. All operations are fully localized.

- **Stable Core**: Local lists, folders, import/export, search, favorites integration.
- **Alpha**: External server search/similarity/sync (invite-only, opt-in).
