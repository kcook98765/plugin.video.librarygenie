
# LibraryGenie - Replit Development Notes

This document contains Replit-specific development information for the LibraryGenie Kodi addon.

## Python Version

This project uses **Python 3.8** to maintain compatibility with Kodi v19 "Matrix" and newer versions.

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

To test the actual addon functionality, package and install it in a Kodi environment.
