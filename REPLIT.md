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


## Kodi ListItem Philosophy

When building ListItems for Kodi library content, proper setup is critical for cast display and native integration:

### For Library Items (items with kodi_id):

#### CRITICAL Requirements for Cast Display in Video Information Dialog:
1. **videodb URL format**: Use `videodb://movies/titles/{movieid}` with NO trailing slash
2. **Mark as playable file**: Set `isFolder=False` and `IsPlayable='true'`
3. **Set InfoTagVideo properties**: Call `setMediaType()` and `setDbId()` on the video info tag
4. **Set identity properties**: `dbtype`, `dbid`, `mediatype` properties on the ListItem

#### Complete Setup Pattern:
```python
# Build videodb URL - NO trailing slash for cast to work
videodb_path = f"videodb://movies/titles/{kodi_id}"  # NO trailing slash!

# Set ListItem properties
list_item.setProperty('dbtype', 'movie')
list_item.setProperty('dbid', str(kodi_id))
list_item.setProperty('mediatype', 'movie')

# CRITICAL: Set InfoTagVideo for cast display
video_info_tag = list_item.getVideoInfoTag()
video_info_tag.setMediaType('movie')
video_info_tag.setDbId(kodi_id)

# Mark as playable file (NOT folder) for cast to show
list_item.setProperty('IsPlayable', 'true')
xbmcplugin.addDirectoryItem(handle, videodb_path, list_item, isFolder=False)
```

#### Metadata to Include:
- Set **all usual metadata fields** that are lightweight and useful for display:
  - `title`, `year`, `genre`, `plot` (full plot is fine), `mpaa`, `rating`, `votes`, `runtime`, `director`, `writer`, `studio`, `country`, etc.
- Set **artwork as normal** (poster, fanart, thumb, clearlogo, discart, etc.) — whatever you have available
- **DO NOT** set heavyweight data that Kodi handles natively:
  - `cast` / `crew` (Kodi will populate this automatically when cast display works)
  - `streamdetails` (audio/video/codec info)

### For External Items (no kodi_id):
- Set **full metadata** including cast since Kodi can't fetch it from the library
- Include all available metadata as these won't be auto-populated
- Can be marked as folders or playable items as needed

### Why This Approach Works:
- The specific videodb URL format (no trailing slash) allows Kodi to properly identify the library item
- Marking as playable file instead of folder triggers Kodi's native cast population
- InfoTagVideo properties provide the direct database link Kodi needs
- Cast information appears automatically in the Video Information dialog
- Maintains optimal performance while ensuring proper Kodi integration



To test the actual addon functionality, package and install it in a Kodi environment.