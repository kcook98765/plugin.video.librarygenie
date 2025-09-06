
# Info Hijack System Documentation

## Overview

The Info Hijack System allows LibraryGenie to provide native Kodi info dialogs for plugin-sourced media items. When a user opens info on a LibraryGenie item, the system intercepts this action and redirects to a native Kodi library dialog with full metadata.

## Architecture

### Core Components

- **InfoHijackManager** (`lib/ui/info_hijack_manager.py`): Main controller that monitors dialog states and triggers hijack process
- **Info Hijack Helpers** (`lib/ui/info_hijack_helpers.py`): XSP generation and native dialog opening utilities

### 5-Step Hijack Process

1. **💾 STEP 1: TRUST KODI NAVIGATION** - Use Kodi's built-in navigation history (no manual saving needed)
2. **🚪 STEP 2: CLOSE CURRENT DIALOG** - Close the plugin info dialog
3. **🚀 STEP 3: OPEN NATIVE INFO VIA XSP** - Create XSP file and navigate to native library view
4. **📺 STEP 4: NATIVE DIALOG OPENS** - User sees full Kodi native info dialog
5. **🔄 STEP 5: DOUBLE-BACK NAVIGATION** - When user closes dialog, detect XSP and issue two back commands

## Item Arming System

LibraryGenie items are "armed" for hijacking by setting these ListItem properties:

```python
li.setProperty("LG.InfoHijack.Armed", "1")
li.setProperty("LG.InfoHijack.DBID", str(kodi_id))
li.setProperty("LG.InfoHijack.DBType", media_type)
```

Only armed items with valid Kodi database IDs can be hijacked.

## XSP Generation

The system creates temporary XSP (XML Smart Playlist) files to generate single-item native library views:

- **Movies**: `special://temp/lg_hijack_movie_{dbid}.xsp`
- **Episodes**: `special://temp/lg_hijack_episode_{dbid}.xsp`

These XSP files contain Kodi database ID filters to show exactly one item in a native library context.

## State Management

- **Cooldown System**: Prevents rapid-fire hijacks during navigation
- **Progress Tracking**: Prevents re-entry during active hijack operations  
- **Dialog State Monitoring**: Tracks when native info dialogs open and close
- **Navigation History**: Leverages Kodi's built-in navigation stack instead of manual state management

## Performance Considerations

- **XSP Detection**: Automatically detects temporary XSP lists and navigates back efficiently
- **No Container Refresh**: Eliminates expensive `Container.Update()` operations that cause 5-6 second delays
- **Double-Back Navigation**: Uses two fast `Action(Back)` commands (~250ms total) instead of container rebuilds
- **Navigation History**: Leverages Kodi's built-in navigation stack for automatic position restoration
- **Efficient XSP**: Minimal XML generation using database ID filters
- **Memory Management**: Temporary XSP files are cleaned up automatically

## Navigation Flow

The hijack system uses a streamlined navigation approach:

1. **User closes native info** → First back command (returns to temporary XSP list)
2. **XSP Detection** → Check if current path contains `.xsp` or `smartplaylist`
3. **Second Back** → If XSP detected, issue another back command to return to original plugin list
4. **Automatic Position** → Kodi's navigation history automatically restores the user's position

This flow eliminates the need for manual container rebuilds and provides sub-second performance on all devices.

## Error Handling

- **DBID Validation**: Ensures valid integer conversion before XSP creation
- **Dialog State Validation**: Confirms dialogs open/close as expected
- **Exception Recovery**: Comprehensive try/catch blocks with detailed logging
- **State Reset**: Ensures manager state is reset even if hijack fails

## Logging

The system provides detailed logging with emoji prefixes for easy debugging:

- 🎯 Hijack triggers and detection
- 💾 Navigation history trust operations  
- 🚪 Dialog close operations
- 🚀 Native info opening
- 🔄 XSP detection and double-back navigation
- ✅ Success confirmations
- ❌ Error conditions

Key log messages include:
- "Using Kodi's navigation history (no saving needed)"
- "Detected XSP path: {path}, issuing second back"
- "Not on XSP path, single back was sufficient"

## Usage Requirements

1. **Kodi Library Items**: Only works with items that exist in Kodi's video database
2. **Valid Database IDs**: Items must have movieid, episodeid, or similar Kodi identifiers
3. **Library Context**: Target items must be accessible via native Kodi library views
4. **XSP Support**: Requires Kodi's smart playlist functionality

## Future Enhancements

- **Custom Button Integration**: Add LibraryGenie-specific buttons to hijacked dialogs
- **Multiple Media Types**: Extend support to music videos and TV shows
- **Context Menu Actions**: Hijack context menu "Information" selections
- **Keyboard Shortcuts**: Detect 'i' key presses for info actions
