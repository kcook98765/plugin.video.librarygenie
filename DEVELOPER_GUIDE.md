# LibraryGenie Developer Guidance

This document provides guidance for developers working on LibraryGenie. It outlines architecture, coding practices, and integration details.

---

## Architecture Overview

LibraryGenie consists of three main layers:

1. **UI Layer** (`lib/ui/`)
   - Plugin routing and action handling (`router.py`, `plugin_context.py`)
   - Directory views and list building (`listitem_builder.py`, `listitem_renderer.py`, `menu_builder.py`)
   - Handler modules for specific features (`lists_handler.py`, `search_handler.py`, `favorites_handler.py`, `main_menu_handler.py`, `tools_handler.py`)
   - Context menu integration (`context_menu.py`)
   - Localization with caching (`localization.py`)
   - Playback actions and info dialog hijacking (`playback_actions.py`, `info_hijack_manager.py`)
   - Session state management (`session_state.py`)

2. **Data Layer** (`lib/data/`)
   - SQLite backend with connection management (`connection_manager.py`)
   - Schema migrations and versioning (`migrations.py`)
   - Query abstraction and CRUD operations (`query_manager.py`)
   - List and library management (`list_library_manager.py`)
   - Storage utilities (`storage_manager.py`)
   - Schema includes `lists`, `folders`, `media_items`, `list_items`, `kodi_favorite`, `search_history`, `search_preferences`, `ui_preferences`, `library_scan_log`, auth/sync tables, and various cache tables

3. **Feature Layer**
   - **Import/Export** (`lib/import_export/`): NDJSON format engines, backup management, ShortList integration
   - **Library Management** (`lib/library/`): Enhanced scanning with favorites integration (`enhanced_scanner.py`, `scanner.py`)
   - **Search** (`lib/search/`): Local search engines, query interpretation, text normalization, year parsing
   - **Kodi Integration** (`lib/kodi/`): JSON-RPC client, favorites parsing and management
   - **Remote Services** (`lib/remote/`): External API clients, caching, search/similarity services
   - **Authentication** (`lib/auth/`): Device code OAuth2 flow, token management, refresh handling
   - **Configuration** (`lib/config/`): Settings management, favorites configuration helpers

---

## Development Guidelines

### Database Access
- Use **parameterized queries** only (no f-strings).  
- Wrap inserts/updates in **transactions**.  
- Add proper **indexes** for high-frequency queries.  
- Use `WAL` mode and tuned `PRAGMAs` for performance.

### JSON-RPC
- Always use **batched calls** (≤200 items per request).  
- Request only **lightweight properties** for list display.  

### List Items
- Minimal fields for display (title, year, art, tmdb, other non heavy fields from JsonRPC).  
- Always set `IsPlayable` where applicable.

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
- Batch DB writes in chunks using configurable batch sizes
- Cache lookups in memory where possible (e.g., IMDb→Kodi mapping via `imdb_to_kodi` table)
- Use SQLite prepared statements and connection pooling (`connection_manager.py`)
- Avoid heavy operations in the UI thread - delegate to background service
- Use the background service for periodic tasks (library scanning, favorites sync, token refresh)
- Implement incremental scanning with delta detection for large libraries
- Use chunked JSON-RPC requests with configurable page sizes (≤200 items per call)

### Background Service (CLIENT-KODI-SERVICE)
- **Runtime constraints**: Never sync during video playback or pause; defer until idle.
- **Graceful shutdown**: Abort immediately on Kodi shutdown signals.
- **Rate limiting**: Sleep generously between steps; use jitter to avoid busy loops.
- **Triggers**: Run on addon start, library updates, periodic timer, manual force, and scheduled backups.
- **Backup Management**: Automated timestamp-based backups with configurable scheduling.
- **Guardrails**: Check auth state, playback status, and recent run timestamps before proceeding.
- **No Favorites Processing**: Favorites scanning removed from background service for performance and user control.

### UI/UX Guidelines
- **Tools & Options**: Use centralized tools menu for context-aware actions.
- **Color Coding**: Apply Kodi-style colors - yellow for tools, red for destructive actions, green for additive actions, white for modify actions.
- **Localization**: Use cached localization helper (`L()` function) for all user-visible strings, especially in context menus.
- **Context Awareness**: Tool options should adapt based on where they are opened from (lists vs favorites vs root).
- **Performance**: Cache localized strings to reduce overhead in menus with many items.

### Compatibility
- Support **Kodi 19 and newer**.  
- Handle both `uniqueid.imdb` (preferred) and `imdbnumber` fields.  

---

## File Structure

- `plugin.py`: main plugin entry point (routes to `lib/ui/router.py`)
- `service.py`: background service for periodic tasks (library scanning, favorites sync, token refresh)
- `lib/ui/`: UI layer - routing, handlers, builders, context menus, session management
- `lib/data/`: Data layer - database connection, queries, migrations, storage management
- `lib/import_export/`: Unified import/export/backup engines, timestamp management, storage handling
- `lib/library/`: Library scanning and indexing with favorites integration
- `lib/search/`: Local search engines, query parsing, text normalization
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
