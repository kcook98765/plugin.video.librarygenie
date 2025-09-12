# LibraryGenie - Kodi List Management Addon

## Overview

LibraryGenie is a comprehensive Kodi addon that provides advanced list and folder management capabilities for media libraries. The addon enables users to create, organize, and manage custom lists of movies, TV episodes, music videos, and external plugin content with robust backup/restore functionality and intelligent media matching.

The addon follows a modular architecture with clear separation between UI handling, data management, and feature-specific functionality. It uses SQLite for local storage with transaction-safe operations and includes optional integration with external services for enhanced metadata and search capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

**2025-09-12**: 
- **Performance Optimization**: Surgically removed item count functionality and "show_item_counts" setting to eliminate N+1 query performance overhead for low-power devices. Removed all COUNT(*) operations from list/folder display while preserving legitimate validation queries. UI now displays lists and folders without item counts, resulting in faster menu rendering and reduced database load.

**2025-09-12**: 
- **Complete Fresh Install Re-Architecture**: Transformed sync system from auto-trigger monitoring to user-controlled sync with professional, non-blocking experience:
  - **Fresh Install Modal**: User-friendly setup dialog with Movies/TV Episodes/Both/Skip options replacing blocking library scans
  - **Service-Orchestrated Sync**: Background service manages sync operations using GlobalSyncLock for cross-process duplicate prevention
  - **Separate Progress Dialogs**: Individual DialogProgressBG indicators for movies (0-100% based on movie count) and TV episodes (0-100% based on TV series count) with smooth, non-resetting progress tracking
  - **Eliminated Double Syncing**: Created dedicated `perform_movies_only_scan()` method to prevent duplicate TV episode processing when both content types are enabled
  - **Non-Blocking UI**: Plugin returns instantly after setup, allowing users to continue navigation while sync runs in background
  - **Clean Progress Experience**: Removed redundant startup messages and progress resets, delivering professional user experience

- **Sync Controller Enhancements**: Implemented smart sync routing logic to prevent nested locking conflicts and duplicate operations. Service layer manages separate progress dialogs while SyncController handles internal locking and coordination.

**2025-09-11**: 
- **TV Episode Synchronization**: Implemented proactive TV episode sync system alongside movie sync with opt-in `sync_tv_episodes` setting (defaulting to off) for storage control. Includes comprehensive database migration framework with `tvshow_kodi_id` field for reliable episode lookup across shows with same season/episode numbers.

- **Previous**: Removed favorites_scan_log table per user request while maintaining all core favorites functionality. Fixed Kodi Favorites display in root plugin menu with proper startup initialization.

## System Architecture

### Core Components

**Plugin Architecture**: Uses Kodi's plugin system with URL-based routing. The main entry point (`plugin.py`) dispatches requests to modular handlers based on action parameters. A background service (`service.py`) orchestrates user-controlled sync operations, fresh install setup, and periodic tasks using GlobalSyncLock for cross-process coordination.

**Data Layer**: SQLite backend with WAL mode and optimized pragmas for performance on low-power devices. Includes schema migrations, connection management, and query abstraction. The database stores lists, folders, media items, favorites, search history, and user preferences with proper indexing and transaction safety.

**UI Layer**: Modular handler system with separate classes for different features (lists, search, favorites, main menu, tools). Uses a router pattern for action dispatch and context-aware rendering. Includes ListItem builders for different content types and universal context menu integration.

**Library Integration**: Deep integration with Kodi's JSON-RPC API for movie/episode metadata retrieval using batched calls. Service-orchestrated sync system with separate movie-only and TV episode-only scanning methods. User-controlled sync with non-blocking UI and professional progress tracking using separate DialogProgressBG instances.

**Import/Export System**: Unified JSON envelope format supporting backup, export, and import operations. IMDb-first matching strategy with multiple fallback mechanisms (TMDb IDs, title/year matching). Automated backup functionality with configurable intervals.

**Search Engine**: Local SQLite-based search with advanced text normalization, intelligent year parsing, and cross-field matching. Supports both "contains" and "starts with" modes with efficient pagination.

**Authentication**: OAuth2 device code flow for optional external service integration with automatic token refresh and secure storage.

### Design Patterns

**Modular Handlers**: Each major feature area (lists, search, favorites, tools) has its own handler class with clear interfaces and responsibilities.

**Factory Pattern**: ListItem builders create appropriate Kodi ListItem objects based on content type (library items vs external plugin content).

**Repository Pattern**: Query manager provides abstraction over database operations with consistent error handling and transaction management.

**Strategy Pattern**: Multiple matching strategies for import operations (IMDb, TMDb, title/year) with configurable fallback chains.

## External Dependencies

**Kodi APIs**: Extensive use of xbmc, xbmcgui, xbmcplugin, xbmcaddon, and xbmcvfs modules for UI, settings, and file system operations.

**SQLite**: Primary data storage with custom schema and migration system. Uses WAL mode and tuned pragmas for performance optimization.

**JSON-RPC**: Kodi's JSON-RPC API for library metadata retrieval, playback control, and system information access.

**Optional External Services**: Framework for integration with metadata services (TMDb, OMDb) and remote search/similarity services via OAuth2 authentication.

**Kodi Favorites**: Read-only integration with Kodi's native favorites.xml file for seamless favorites management without modification of the original file.

**Plugin Content**: Universal support for content from any Kodi addon through plugin URL handling and context menu integration.