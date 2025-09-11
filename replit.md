# LibraryGenie - Kodi List Management Addon

## Overview

LibraryGenie is a comprehensive Kodi addon that provides advanced list and folder management capabilities for media libraries. The addon enables users to create, organize, and manage custom lists of movies, TV episodes, music videos, and external plugin content with robust backup/restore functionality and intelligent media matching.

The addon follows a modular architecture with clear separation between UI handling, data management, and feature-specific functionality. It uses SQLite for local storage with transaction-safe operations and includes optional integration with external services for enhanced metadata and search capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

**2025-09-11**: Removed favorites_scan_log table and all logging functionality per user request. The favorites scan process still works correctly but no longer stores scan history, timing data, or file modification tracking. This simplifies the database schema and eliminates unnecessary data storage while maintaining all core functionality. Also fixed previous Kodi Favorites display issue in root plugin menu with startup initialization logic.

## System Architecture

### Core Components

**Plugin Architecture**: Uses Kodi's plugin system with URL-based routing. The main entry point (`plugin.py`) dispatches requests to modular handlers based on action parameters. A background service (`service.py`) handles periodic tasks like token refresh and library monitoring.

**Data Layer**: SQLite backend with WAL mode and optimized pragmas for performance on low-power devices. Includes schema migrations, connection management, and query abstraction. The database stores lists, folders, media items, favorites, search history, and user preferences with proper indexing and transaction safety.

**UI Layer**: Modular handler system with separate classes for different features (lists, search, favorites, main menu, tools). Uses a router pattern for action dispatch and context-aware rendering. Includes ListItem builders for different content types and universal context menu integration.

**Library Integration**: Deep integration with Kodi's JSON-RPC API for movie/episode metadata retrieval using batched calls. Enhanced scanner with favorites integration and library change monitoring.

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