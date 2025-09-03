# LibraryGenie — Robust List Management for Kodi

LibraryGenie is a Kodi addon that provides advanced, flexible list and folder management with disaster recovery, portability, and intelligent media matching. It supports mixed content types, portable exports, and optional integration with external services.

---

## Overview

- Mixed content lists (movies, TV episodes, music videos, external plugin items).
- IMDb-first architecture with multiple fallback strategies.
- Robust export/import system with disaster recovery support.
- SQLite backend with safe transaction handling and optimized indexing.
- Optional integration with external search/similarity services (requires explicit user authorization).

---

## Key Features

### Media Types
- **Movies**: Full Kodi movie library support.
- **TV Episodes**: Episode-level handling with show/season/episode mapping.
- **Music Videos**: Artist/track/album matching and metadata support.
- **External Items**: Playable plugin items from any addon, with context menu integration for easy list management.

### Lists & Folders
- Hierarchical folder structure with unlimited depth.
- **Tools & Options Menu**: Context-aware tools for list and folder management.
- Create, rename, move, and delete lists and folders with color-coded actions.
- Add/remove items via context menus from anywhere in Kodi.
- **Universal Context Menu**: Add any playable media to lists - movies, episodes, music videos, and plugin content.
- **Quick Save Feature**: Optional quick-add functionality to a configured default list with single-click access.
- **Dual Context Options**: When quick save is enabled, context menu shows both "Quick Add to Default List" and "Add to List..." options.
- Export functionality integrated into tools menu.
- Duplicate detection and unique constraint handling.
- Transaction-safe modifications to prevent corruption.

### Import & Export
- **Unified Format**: Backup, export, and import all use the same JSON envelope format with versioned schemas.
- **Universal Compatibility**: Single format supports manual export, automated backup, and restore operations.
- **Automated Backups**: Configurable timestamp-based backups (hourly, daily, weekly, monthly).
- **Local & Network Storage**: Support for local paths and network shares configured in Kodi.
- **Tools Integration**: Export and backup accessible via Tools & Options menu with context-aware options.
- **IMDb-First Matching**: Highest-confidence mapping across systems for import/restore operations.
- **Enhanced Metadata**: Additional identifiers (TMDb, Kodi IDs, file paths) for robust fallback matching.
- **Fallbacks**: TMDb IDs, title/year, season/episode, or artist/track when IMDb is missing.
- **Safe Import**: Validation and preview before import, with duplicate detection and error handling.
- **Batch Operations**: Efficient chunked import/export of large lists.

#### Format Structure
All export/backup files use a versioned JSON envelope containing:
- **Metadata**: Addon version, schema version, generation timestamp
- **Export Types**: Lists of included data types (lists, list_items, favorites, folders, library_snapshot)
- **Payload**: Actual data organized by type with consistent field names
- **Validation**: Required fields and format validation for safe import/restore

### Metadata Matching
- **Movies**: IMDb → TMDb (optional) → title/year/runtime fallback.
- **Episodes**: Episode IMDb → show IMDb + season/episode → show title fallback.
- **Music Videos**: IMDb (rare) → artist+track(+year).
- **External Items**: Plugin identifiers and routes.

### Backup & Recovery
- **Automated Backups**: Scheduled timestamp-based backups with configurable intervals.
- **Manual Backups**: On-demand backup creation via Tools menu.
- **Flexible Storage**: Local paths or network shares (SMB/NFS) configured in Kodi settings.
- **Backup Management**: List, restore, and delete backups through the Tools interface.
- **Comprehensive Coverage**: Backup lists, folders, favorites, and optionally library snapshots.
- **Disaster Recovery**: Full system restore from unified backup files using same format as exports.
- **Cross-Compatible**: Backup files can be manually imported on other systems or after fresh installs.

### Performance
- Batched JSON-RPC requests (≤200 items per call).
- Deferred loading of heavy fields (cast, streamdetails, extra artwork).
- Cache-friendly schema and memory mappings (IMDb→Kodi DBIDs).
- Indexes optimized for large libraries (10k+ items).

---

## Export/Import Specification

### NDJSON Format
Each line = one item. Universal fields:

| Field           | Type    | Required | Notes                                      |
|-----------------|---------|----------|--------------------------------------------|
| media_type      | string  | yes      | `movie`, `episode`, `musicvideo`, `external` |
| imdb_id         | string  | no       | `tt…` identifier if available              |
| title           | string  | yes      | Title of item                              |
| year            | integer | no       | Release or air year                        |
| list_name       | string  | yes      | Context list name                          |
| schema_version  | integer | yes      | Current schema version (2)                 |

#### Movies
- `tmdb_id`, `runtime_minutes`.

#### Episodes
- `show_imdb_id`, `show_title`, `season`, `episode`, `air_date`, `episode_title`.

#### Music Videos
- `artist`, `artist_mbid`, `track`, `album`, `album_year`, `duration_seconds`.

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
- **Backup Settings**: Automated backup scheduling, storage location, and retention policies.
- **Storage Configuration**: Local paths and network share support via Kodi file settings.
- **Organized Categories**: Settings grouped into General, Lists, Background, and Backup sections.
- **Privacy-First**: External features disabled by default, require explicit user authorization.

## External Integration (Optional)

- Disabled by default; requires user authorization.
- **Remote Search**: Free-text queries → IMDb ID lists returned.
- **Similarity**: Given IMDb, request server for similar items → IMDb IDs.
- **Sync**: Optional mirroring of user’s list with server (IMDb only).
- **Privacy**: Only IMDb IDs and user queries transmitted; no file paths or playback data.

---

## Technical Notes

- Runs on Kodi 19+.
- Python 3.x, Kodi Python API.
- SQLite backend with WAL/PRAGMA tuning for low-power devices.
- JSON-RPC integration with batching and selective property fetching.
- Clear separation between UI (routes/dialogs), data (DB/mapping), and features (lists/export/import/sync).

---

## Development Workflow

### Local Development Setup

1. **Install Development Dependencies**:
   ```bash
   make install-dev
   ```
   This installs linting tools (flake8), type checker (mypy), test runner (pytest), and formatting tools (black, isort).

2. **Run Quality Checks**:
   ```bash
   make lint        # Run linter with import order checking
   make typecheck   # Run type checker in warn mode
   make test        # Run test suite
   make format      # Format code with black and isort
   ```

3. **Build and Package**:
   ```bash
   make build       # Run all quality checks (lint + typecheck + test)
   make package     # Create clean addon zip
   make all         # Full workflow: clean + build + package
   ```

### Testing Environment

- **Kodi API Stubs**: Test-only stubs in `tests/stubs/` provide minimal Kodi API implementations for running tests without Kodi.
- **Import Safety Tests**: Verify all modules can be imported without Kodi dependencies.
- **Smoke Tests**: Basic functionality tests for plugin/service entry points and routing.
- **Clean Testing**: Stubs are excluded from the packaged addon and exist only for development.

### Development Files

Files used only for development (excluded from addon package):
- `requirements-dev.txt` - Development dependencies
- `.flake8`, `mypy.ini`, `pyproject.toml` - Tool configurations
- `Makefile` - Development task shortcuts
- `tests/` - Test suite and Kodi stubs

### Quality Gates

All changes must pass:
- **Linting**: Basic code style, import order, unused code detection
- **Type Checking**: Gradual typing with warnings (ignores missing Kodi types)
- **Import Safety**: All modules import without Kodi runtime
- **Smoke Tests**: Core functionality works in test environment

## Favorites (Manual) Integration

LibraryGenie provides manual integration with Kodi's built-in Favorites system, allowing you to:

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

### Unmapped Favorites

Favorites that don't map to your library (plugins, scripts, missing files) can be optionally displayed with:

- Clear "Not in library" badges
- Limited actions (no Play/Add to List)
- Separate "Unmapped" section in favorites view

## Search

LibraryGenie provides powerful local search with precision and predictability:

### Search Features

- **Smart Text Matching**: Advanced normalization handles diacritics, punctuation, and case automatically
- **Match Modes**: Choose between "Contains" (all words anywhere) or "Starts With" (first word at beginning)
- **Robust Year Filtering**: Explicit prefixes (`y:1999`, `year:2010-2015`) prevent accidental title filtering
- **File Path Search**: Optional inclusion of file paths in search (disabled by default)
- **Efficient Paging**: Clean navigation with "Next/Previous" and state preservation

### Year Filter Syntax

**Explicit Prefixes** (always treated as filters):
- `y:1999` or `year:1999` - Movies from 1999
- `year:1990-2000` - Movies from 1990 to 2000
- `year>=2010` - Movies from 2010 onwards
- `year<=2005` - Movies up to 2005

**Decade Shorthand** (when enabled in settings):
- `'90s` or `1990s` - Movies from 1990-1999

**Title Protection**: Numbers in movie titles like "2001: A Space Odyssey" or "Fahrenheit 451" are never treated as year filters unless explicitly prefixed.

### Match Modes

- **Contains** (default): All search words must appear somewhere in the title
- **Starts With**: First word must start the title, remaining words can appear anywhere

### Search Settings

- **Match Mode**: Choose between Contains/Starts With
- **Page Size**: 25-200 results per page (default: 50)
- **Include File Path**: Search within file paths (off by default)
- **Decade Shorthand**: Enable '90s style shortcuts (off by default)

---

## Installation

### From Zip Package

1. Download the latest `plugin.video.library.genie-[version].zip` from releases
2. Install via Kodi: Settings → Add-ons → Install from zip file
3. The addon will be available in Videos → Video add-ons

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


### Debug Information

Enable debug logging in addon settings → General → Debug & Logging to get detailed information for troubleshooting. Debug logs will show:

- JSON-RPC request timing and paging details
- Database operation performance metrics
- Library scan progress and error details
- Configuration validation and fallback behavior


### Reset and Recovery

If the addon stops working correctly:

1. **Soft Reset**: Clear addon data in Kodi settings → Add-ons → Installed → Video add-ons → LibraryGenie → Configure
2. **Database Reset**: Delete `movie_lists.db` from addon_data folder to start fresh
3. **Complete Reinstall**: Uninstall addon, delete addon_data folder, reinstall

### Performance Baselines

Expected performance for reference systems:

- **Small library** (< 500 movies): Full scan 30-60 seconds, Delta scan 5-10 seconds
- **Medium library** (500-2000 movies): Full scan 2-5 minutes, Delta scan 10-30 seconds
- **Large library** (2000+ movies): Full scan 5-15 minutes, Delta scan 30-60 seconds

Times may vary significantly based on network storage, system performance, and library metadata complexity.

---

## Status

## What works now

**Phase 5 - Full List Management**: Complete local-only list management functionality with CRUD operations, user interface flows, and persistent SQLite storage. Create, rename, and delete lists with confirmation dialogs and item counts. All operations are fully localized and work both in Kodi and standalone testing environments. No external services yet.

- **Stable Core**: Local lists, folders, import/export.
- **Alpha**: External server search/similarity/sync (invite-only, opt-in).
- **Optional**: TMDb enrichment with user-supplied API key.