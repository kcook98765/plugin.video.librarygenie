
# LibraryGenie Future Work

This document outlines potential future enhancements and features for LibraryGenie, organized by priority and implementation complexity.

---

## High Priority Features to Pursue

### 1. Info Hijack System
**Status**: Framework exists but minimal implementation  
**Files**: `lib/ui/info_hijack_manager.py`, `lib/ui/info_hijack_helpers.py`  
**Description**: Intercept movie info dialogs to add custom "Add to List" buttons  
**Benefits**: Seamless integration with Kodi's native movie info experience  
**Effort**: Medium - Framework present, needs UI integration and event handling  

### 2. Music Video Support  
**Status**: Database schema complete, missing UI and scanning  
**Files**: Database `media_items` table, export/import engine  
**Description**: Full music video library integration with artist/track matching  
**Benefits**: Complete media type coverage beyond just movies  
**Effort**: Medium - Schema ready, needs scanning logic and UI handlers  

### 3. TV Episode Support
**Status**: Database schema supports episodes, missing UI flows  
**Files**: Database schema with show/season/episode mapping  
**Description**: Episode-level list management with show context  
**Benefits**: Granular TV content organization  
**Effort**: High - Complex UI flows and metadata handling required  

### 4. External Service Integration
**Status**: Framework exists, currently just placeholder  
**Files**: `lib/integrations/`, `lib/remote/`, `lib/auth/`  
**Description**: TMDb, OMDb, or other metadata service integration  
**Benefits**: Enhanced metadata and artwork for library items  
**Effort**: Medium - Auth system complete, needs service-specific clients  

### 5. Enhanced Favorites Features
**Status**: Read-only scanning implemented  
**Files**: `lib/kodi/favorites_manager.py`, `lib/kodi/favorites_parser.py`  
**Description**: Favorite creation, editing, and organization  
**Benefits**: Full favorites lifecycle management  
**Effort**: Low-Medium - Core parsing done, needs creation/editing flows  

---

## Medium Priority Features

### 6. Advanced Search Enhancements
**Status**: Basic engine exists, some advanced features unused  
**Files**: `lib/search/enhanced_query_interpreter.py`, `lib/search/enhanced_search_engine.py`  
**Description**: Decade parsing, complex query operators, saved searches  
**Benefits**: Power user search capabilities  
**Effort**: Low - Features exist but not fully utilized  

### 7. Backup System Improvements
**Status**: Basic backup exists, needs automation and management  
**Files**: `lib/import_export/backup_manager.py`, `lib/import_export/timestamp_backup_manager.py`  
**Description**: Scheduled backups, retention policies, backup verification  
**Benefits**: Automated data protection and recovery  
**Effort**: Medium - Core backup works, needs scheduling and management UI  

### 8. Cross-Platform Sync
**Status**: Full implementation exists but may be over-engineered  
**Files**: `sync_state`, `auth_state`, `pending_operations` database tables  
**Description**: Synchronize lists across multiple Kodi instances  
**Benefits**: Multi-device list management  
**Effort**: Low-Medium - Implementation complete, needs simplification and testing  

---

## Low Priority / Cleanup Items

### 9. Database Optimization
**Status**: Some unused tables and duplicate functionality  
**Files**: `movie_heavy_meta` table, multiple storage managers  
**Description**: Remove unused tables, consolidate storage management  
**Benefits**: Cleaner codebase, better performance  
**Effort**: Low - Removal and consolidation work  

### 10. Service Integration Simplification
**Status**: Background service exists but integration incomplete  
**Files**: `service.py`, background task integration  
**Description**: Streamline background tasks or simplify to essential operations  
**Benefits**: More reliable background processing  
**Effort**: Medium - Requires careful analysis of current usage patterns  

---

## Experimental / Research Items

### 11. Plugin Ecosystem
**Status**: Generic plugin handling exists  
**Files**: External item support in database schema  
**Description**: Deep integration with popular Kodi addons  
**Benefits**: Broader content source support  
**Effort**: High - Requires research into addon APIs and integration patterns  

### 12. AI-Powered Features
**Status**: Not implemented  
**Files**: None  
**Description**: Smart list suggestions, duplicate detection, metadata correction  
**Benefits**: Intelligent content organization  
**Effort**: High - Requires AI/ML integration and training data  

### 13. Web Interface
**Status**: Not implemented  
**Files**: None  
**Description**: Browser-based list management interface  
**Benefits**: Management from any device  
**Effort**: Very High - Separate web application development  

---

## Technical Debt & Maintenance

### Code Quality Improvements
- Consolidate duplicate storage management classes
- Remove unused import modules (e.g., `shortlist_importer.py`)
- Standardize error handling patterns across modules
- Improve test coverage for complex features

### Performance Optimizations
- Database query optimization for large libraries
- Reduce memory usage during bulk operations
- Improve JSON-RPC batching efficiency
- Cache management for frequently accessed data

### Documentation Updates
- Complete API documentation for all modules
- User guide with screenshots and workflows
- Troubleshooting guide expansion
- Developer onboarding documentation

---

## Decision Framework

When evaluating future work items, consider:

1. **User Impact**: How many users would benefit?
2. **Implementation Effort**: Time and complexity required
3. **Maintenance Burden**: Ongoing support and update requirements
4. **Architectural Fit**: Alignment with existing codebase patterns
5. **External Dependencies**: Reliance on third-party services or APIs

---

## Implementation Notes

- Prioritize features that build on existing infrastructure
- Consider user feedback and usage analytics when available
- Maintain backward compatibility for database schema changes
- Follow established patterns for UI integration and error handling
- Test thoroughly with various library sizes and configurations

---

*Last Updated: Based on codebase analysis as of current review*
