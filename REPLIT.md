# LibraryGenie Development Notes for Replit

This document contains development notes specific to working with this project in the Replit environment.

## Python Version

This project targets **Python 3.8+** as used by Kodi 19+. All typing imports should use standard `from typing import` syntax without version fallbacks since Python 3.8 has full typing support. When implementing new features or fixing issues, ensure compatibility with Python 3.8 syntax and standard library features.

### Key Compatibility Notes for Coding Tasks:

- **Target Python 3.8** - Kodi v19 runs Python 3.8.x
- **Avoid Python 3.9+ features** such as:
  - Built-in generics (`list[str]`, `dict[str, int]`) → use `typing.List`, `typing.Dict`
  - `str.removeprefix()` / `str.removesuffix()` (added in 3.9)
  - `zoneinfo` module (added in 3.9)
  - `match`/`case` pattern matching (added in 3.10)
  - Newer typing features like `typing.Self`, `typing.TypeAlias` (3.11+)

### Kodi Addon XML Requirement

The addon.xml declares `<import addon="xbmc.python" version="3.0.0"/>` which corresponds to the Kodi Matrix API (Python 3.8).

### Development Environment

This Replit environment provides Python 3.8 compatibility for testing and development. All code should be written to work with Python 3.8 to ensure compatibility across Kodi v19 and newer versions.

## Running the Addon

Since this is a Kodi addon, it cannot be run directly in Replit. Use this environment for:
- Code development and editing
- Syntax checking and linting
- Testing import statements and basic functionality
- Preparing addon packages for deployment to Kodi


## Kodi ListItem Implementation

The addon uses a robust ListItem builder pattern that handles both library-backed and external items with proper version compatibility and performance optimization.

### Current Implementation Overview

The `ListItemBuilder` class in `lib/ui/listitem_builder.py` provides:

1. **Version-safe handling** for Kodi v19 (Matrix) and v20+ (Nexus+)
2. **Lightweight list rendering** that avoids heavy metadata in list views
3. **Proper library integration** for items with Kodi database IDs
4. **External item support** for plugin-only content

### Key Design Principles

#### Library Items (with kodi_id):
- Use `videodb://` URLs for direct library integration
- Set lightweight metadata only (no cast/crew arrays in list views)
- Apply version-guarded InfoTagVideo calls for v20+
- Always show resume information for library movies/episodes
- Mark as playable files (`IsPlayable='true'`, `isFolder=False`)

#### External Items (no kodi_id):
- Use plugin URLs for custom handling
- Apply same lightweight metadata profile as library items
- Skip resume information (library-only feature)
- Proper folder/playable flag handling

### Version Compatibility Handling

The implementation includes a `is_kodi_v20_plus()` helper that detects the Kodi version and applies appropriate API calls:

```python
# v19 (Matrix) - Uses classic properties
list_item.setProperty('ResumeTime', str(position_seconds))
list_item.setProperty('TotalTime', str(total_seconds))

# v20+ (Nexus+) - Uses InfoTagVideo with fallback
try:
    video_info_tag = list_item.getVideoInfoTag()
    video_info_tag.setMediaType(media_type)
    video_info_tag.setDbId(kodi_id)
    video_info_tag.setResumePoint(position_seconds, total_seconds)
except Exception:
    # Fallback to v19 properties if v20+ calls fail
    list_item.setProperty('ResumeTime', str(position_seconds))
    list_item.setProperty('TotalTime', str(total_seconds))
```

### Performance Optimizations

#### Lightweight List Rendering:
- **Avoids heavy fields** like cast/crew arrays, deep streamdetails
- **Duration in minutes** for Matrix compatibility
- **Basic metadata only**: title, year, genre, plot, rating, studio, country
- **Minimal artwork**: poster/fanart with sensible thumb fallbacks

#### Container Hygiene:
- Sets content type once per directory (`setContent()`)
- Adds sort methods once per build
- Ensures every item has a non-empty URL
- Proper `IsPlayable` flag handling

### URL Construction Patterns

#### Library Movies:
```python
url = f"videodb://movies/titles/{kodi_id}"  # NO trailing slash
```

#### Library Episodes:
```python
url = f"videodb://tvshows/titles/{tvshowid}/{season}/{episodeid}"
```

#### External Items:
```python
url = f"plugin://{addon_id}?action=info&item_id={item_id}"
```

### Metadata Normalization

The builder includes a comprehensive `_normalize_item()` method that:
- Handles various input formats from different sources
- Converts duration to minutes for Matrix compatibility
- Flattens artwork from JSON blobs
- Preserves resume information in seconds
- Maps common field variations to canonical names

### Why This Approach Works:
- **Version safety**: No warnings on v19, full feature support on v20+
- **Performance**: Fast list scrolling with lightweight metadata
- **Library integration**: Proper videodb URLs enable native Kodi features
- **Flexibility**: Handles mixed library/external content seamlessly
- **Maintainability**: Clear separation between library and external item handling



To test the actual addon functionality, package and install it in a Kodi environment.

Example structure:
```
lib/
├── ui/           # UI layer - routing, handlers, builders
├── data/         # Data layer - database, queries, migrations  
├── kodi/         # Kodi-specific integration
├── search/       # Search functionality
├── import_export/ # Import/export engines
├── library/      # Library scanning and indexing
├── auth/         # Authentication and token management
├── config/       # Configuration management
├── remote/       # Remote service integration
├── utils/        # Utility functions and helpers
└── integrations/ # Third-party integrations