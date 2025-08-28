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

To test the actual addon functionality, package and install it in a Kodi environment.