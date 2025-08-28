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

When building ListItems for Kodi library content, set complete lightweight metadata while avoiding heavyweight data that Kodi handles natively:

### For Library Items (items with kodi_id):
- Set **all usual metadata fields** that are lightweight and useful for display in list views or dialogs:
  - `title`, `year`, `genre`, `plot` (full plot is fine), `mpaa`, `rating`, `votes`, `runtime`, `director`, `writer`, `studio`, `country`, etc.
- Set **critical identity properties** so Kodi can link the item to its own library record:
  - `dbtype`, `dbid`, `mediatype`
- Set **artwork as normal** (poster, fanart, thumb, clearlogo, discart, etc.) — whatever you have available
- **DO NOT** set or fetch heavyweight data that Kodi's info dialog already handles natively:
  - `cast` / `crew`
  - `streamdetails` (audio/video/codec info)

### Why This Approach:
- Provides complete display information for list views and dialogs
- The `dbtype` and `dbid` properties tell Kodi this is a library item for native integration
- Avoids heavyweight operations (cast/crew/streamdetails) that Kodi populates automatically
- Maintains optimal performance while ensuring rich display metadata
- Kodi's native info dialog will handle cast/crew with proper formatting and behavior

### For External Items (no kodi_id):
- Set **full metadata** including cast since Kodi can't fetch it from the library
- Include all available metadata as these won't be auto-populated

This approach ensures rich display information while maintaining optimal performance and proper Kodi integration.



To test the actual addon functionality, package and install it in a Kodi environment.