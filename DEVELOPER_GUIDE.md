# LibraryGenie Developer Guidance

This document provides guidance for developers working on LibraryGenie. It outlines architecture, coding practices, and integration details.

---

## Architecture Overview

LibraryGenie consists of three main layers:

1. **UI Layer** (`lib/ui/`)
   - Plugin routing and action handling (`router.py`, `plugin_context.py`)
   - Directory views and list building (`listitem_builder.py`, `listitem_renderer.py`, `menu_builder.py`)
   - Handler modules for specific features (`lists_handler.py`, `search_handler.py`, `favorites_handler.py`, `main_menu_handler.py`, `tools_handler.py`)
   - Global context menu integration (`context.py`) with universal media type support and quick save functionality
   - Localization with caching (`localization.py`)
   - Playback actions and info dialog hijacking (`playback_actions.py`, `info_hijack_manager.py`)
   - Session state management (`session_state.py`)

2. **Data Layer** (`lib/data/`)
   - SQLite backend with connection management (`connection_manager.py`)
   - Schema migrations and versioning (`migrations.py`)
   - Query abstraction and CRUD operations (`query_manager.py`)
   - List and library management (`list_library_manager.py`)
   - Storage utilities (`storage_manager.py`)
   - Schema centers around `media_items` as the unified media table, with supporting tables: `lists`, `folders`, `list_items`, `kodi_favorite`, `search_history`, `search_preferences`, `ui_preferences`, `library_scan_log`, auth/sync tables, and various cache tables

3. **Feature Layer**
   - **Import/Export** (`lib/import_export/`): NDJSON format engines, backup management, ShortList integration
   - **Library Management** (`lib/library/`): Enhanced scanning with favorites integration (`enhanced_scanner.py`, `scanner.py`)
   - **Search** (`lib/search/`): Simplified keyword-based search engine, query interpretation, text normalization
   - **Kodi Integration** (`lib/kodi/`): JSON-RPC client, favorites parsing and management
   - **Remote Services** (`lib/remote/`): External API clients, caching, search/similarity services
   - **Authentication** (`lib/auth/`): Device code OAuth2 flow, token management, refresh handling
   - **Configuration** (`lib/config/`): Settings management, favorites configuration helpers

---

## Development Guidelines

### Database Access
- Use **ConnectionManager** for all database operations (`get_connection_manager()`).
- Use **standard methods**: `execute_query()`, `execute_single()`, `transaction()` context manager.
- **No direct cursor access** - all queries go through the connection manager interface.
- Use **parameterized queries** only (no f-strings).  
- Wrap inserts/updates in **transactions** using `with conn_manager.transaction() as conn:`.
- Add proper **indexes** for high-frequency queries.  
- Use `WAL` mode and tuned `PRAGMAs` for performance.

### JSON-RPC
- **Library Scanning**: Use comprehensive property requests during scanning to populate media_items table
- **List Operations**: Avoid JSON-RPC calls for list building - use stored media_items data instead
- **Batch Operations**: When JSON-RPC needed, use batched calls (≤200 items per request)
- **Heavy Properties**: Exclude cast, streamdetails, and extensive artwork from default requests

### List Items
- **Database-First**: Build list items from media_items table data, not live JSON-RPC calls
- **Stored Metadata**: Use comprehensive metadata stored during library scanning
- **Fallback Handling**: Implement graceful fallbacks when stored metadata is missing
- **Performance**: Single database query per list instead of multiple JSON-RPC batch calls

### Export/Import & Backup
- **Unified System**: Backup and export use the same engine and NDJSON format.
- **Enhanced Metadata**: Include additional identifiers (TMDb, Kodi IDs, file paths) for robust matching.
- **Automated Backups**: Timestamp-based scheduling with configurable intervals and retention.
- **Storage Flexibility**: Local paths and network shares (no HTTP/remote servers).
- Export: NDJSON with universal and type-specific fields.  
- Import: IMDb-first mapping; fallback to title/year or other identifiers.  
- Placeholders: create when no match is found.

### Favorites Integration
- **Read-only access**: Never modify Kodi's `favourites.xml` file
- **Manual operation**: All scanning is user-initiated, no background processing
- **Smart parsing**: Handle various XML formats and edge cases gracefully
- **Library mapping**: Map favorites to library items via normalized path matching
- **Privacy protection**: Strip credentials from network paths during processing
- **Change detection**: Track file modification times to avoid unnecessary rescans

### External Services
- All integrations are **opt-in**.  
- OTP-based pairing for server access.  
- Cache results to minimize load.
- **Differential sync**: Use version checking and diff computation to minimize bandwidth.
- **Idempotent operations**: All sync endpoints use Idempotency-Key headers for safe retries.
- **State persistence**: Maintain local snapshots, server metadata, and pending queues.

### Performance
- **Database-Driven Lists**: Use stored media_items data instead of JSON-RPC calls for list operations
- **Enhanced Scanning**: Store comprehensive lightweight metadata during library scans
- **Version-Aware Scanning**: Automatically detect Kodi version changes and trigger appropriate scan types
- **Pre-computed Metadata**: Store metadata in format optimized for current Kodi version (v19 setInfo vs v20+ InfoTagVideo)
- **Batch Operations**: Batch DB writes in chunks using configurable batch sizes
- **Memory Caching**: Cache lookups in memory where possible (e.g., IMDb→Kodi mapping via `imdb_to_kodi` table)
- **Connection Management**: Use SQLite prepared statements and connection pooling (`connection_manager.py`)
- **Background Processing**: Delegate heavy operations to background service, avoid UI thread blocking
- **Incremental Updates**: Implement delta detection for efficient library synchronization
- **Optimized Queries**: Single database queries replace multiple JSON-RPC batch calls

### Background Service (CLIENT-KODI-SERVICE)
- **Runtime constraints**: Never sync during video playback or pause; defer until idle.
- **Graceful shutdown**: Abort immediately on Kodi shutdown signals.
- **Rate limiting**: Sleep generously between steps; use jitter to avoid busy loops.
- **Triggers**: Run on addon start, library updates, periodic timer, manual force, and scheduled backups.
- **Backup Management**: Automated timestamp-based backups with configurable scheduling.
- **Guardrails**: Check auth state, playback status, and recent run timestamps before proceeding.
- **No Favorites Processing**: Favorites scanning removed from background service for performance and user control.
- **Background services**: Respect playback state - never perform heavy operations during video playback.
- **Info hijack**: Decouple heavy operations from dialog opening - save state, open dialog immediately, restore after close.

### UI/UX Guidelines
- **Tools & Options**: Use centralized tools menu for context-aware actions.
- **Color Coding**: Apply Kodi-style colors - yellow for tools, red for destructive actions, green for additive actions, white for modify actions.
- **Localization**: Use cached localized strings to reduce overhead in menus with many items.
- **Context Awareness**: Tool options should adapt based on where they are opened from (lists vs favorites vs root).
- **Universal Context Menus**: Context menu integration works for all playable media types including plugin content from any addon.
- **Performance**: Cache localized strings to reduce overhead in menus with many items.

### Compatibility
- Support **Kodi 19 and newer**.  
- Handle both `uniqueid.imdb` (preferred) and `imdbnumber` fields.
- **Version Tracking**: Store Kodi major version with scan results for compatibility detection
- **Automatic Migration**: Trigger full library scans when Kodi version changes
- **Metadata Format**: Pre-compute metadata in format appropriate for detected Kodi version  

---

## File Structure

- `plugin.py`: main plugin entry point using modular architecture with handlers and router
- `service.py`: background service for periodic tasks (library scanning, favorites sync, token refresh)
- `lib/ui/`: UI layer - modular handlers, router, response types, builders, context menus, session management
- `lib/data/`: Data layer - database connection, queries, migrations, storage management
- `lib/import_export/`: Unified import/export/backup engines, timestamp management, storage handling
- `lib/library/`: Library scanning and indexing with favorites integration
- `lib/search/`: Simplified keyword-based search engine, query interpretation, text normalization
- `lib/kodi/`: Kodi-specific integration - JSON-RPC, favorites parsing
- `lib/remote/`: External service integration - API clients, caching, search services
- `lib/auth/`: Authentication flow - device code OAuth2, token management
- `lib/config/`: Configuration management and settings helpers
- `lib/utils/`: Shared utilities - logging, helpers
- `resources/`: Kodi addon resources - language files, settings XML

---

## Developer Notes

- **Logging**: Use consistent prefixes (`[LibraryGenie]`).  
- **Error handling**: Catch exceptions, log clearly, continue gracefully.  
- **Testing**: Validate with both small and large libraries.  
- **Extensibility**: Keep new features modular (e.g., additional integrations in `integrations/`).  

---

## Contribution Guidelines

- Follow PEP8 for Python code style.  
- Write docstrings for all public functions.  
- Submit PRs with clear descriptions and testing notes.  
- Open issues with logs and reproducible steps.  

---

This guidance ensures consistency, reliability, and performance for LibraryGenie development.