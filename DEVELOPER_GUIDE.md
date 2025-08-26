# Movie List Manager Developer Guidance

This document provides guidance for developers working on Movie List Manager. It outlines architecture, coding practices, and integration details.

---

## Architecture Overview

Movie List Manager consists of three main layers:

1. **UI Layer**
   - Handles routing of Kodi plugin actions.
   - Builds directory views, context menus, and dialogs.
   - Provides context menu entries for list/folder management.

2. **Data Layer**
   - SQLite backend (`database.py`).
   - Query abstraction (`query_manager.py`).
   - Schema includes `media_items`, `list_items`, `lists`, `folders`, `imdb_to_kodi`, and caches.

3. **Feature Layer**
   - List/folder CRUD (`lists_service.py`).
   - Export/import in NDJSON format (`export_import.py`).
   - Directory building with batched JSON-RPC (`directory_builder.py`).
   - Mapping indexer (IMDb → Kodi DBIDs).
   - External integrations (remote API, TMDb enrichment).

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

### Export/Import
- Export: NDJSON with universal and type-specific fields.  
- Import: IMDb-first mapping; fallback to title/year or other identifiers.  
- Placeholders: create when no match is found.

### External Services
- All integrations are **opt-in**.  
- OTP-based pairing for server access.  
- Cache results to minimize load.
- **Differential sync**: Use version checking and diff computation to minimize bandwidth.
- **Idempotent operations**: All sync endpoints use Idempotency-Key headers for safe retries.
- **State persistence**: Maintain local snapshots, server metadata, and pending queues.

### Performance
- Batch DB writes in chunks.  
- Cache lookups in memory where possible (e.g., IMDb→Kodi mapping).  
- Avoid heavy operations in the UI thread.  
- Use the background service for periodic tasks.

### Background Service (CLIENT-KODI-SERVICE)
- **Runtime constraints**: Never sync during video playback or pause; defer until idle.
- **Graceful shutdown**: Abort immediately on Kodi shutdown signals.
- **Rate limiting**: Sleep generously between steps; use jitter to avoid busy loops.
- **Triggers**: Run on addon start, library updates, periodic timer, and manual force.
- **Guardrails**: Check auth state, playback status, and recent run timestamps before proceeding.

### Compatibility
- Support **Kodi 19 and newer**.  
- Handle both `uniqueid.imdb` (preferred) and `imdbnumber` fields.  

---

## File Structure

- `default.py`: entry point for addon (routes to `ui/entry.py`).  
- `service.py`: background tasks (periodic mapping refresh, sync).  
- `resources/lib/ui`: UI helpers, routes, dialogs.  
- `resources/lib/data`: database, query manager, schema.  
- `resources/lib/features`: list management, export/import, directory building, mapping, sync.  
- `resources/lib/integrations`: remote API, TMDb.  
- `resources/lib/utils`: logging, batching, helpers.

---

## Developer Notes

- **Logging**: Use consistent prefixes (`[Movie List Manager]`).  
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

This guidance ensures consistency, reliability, and performance for Movie List Manager development.
