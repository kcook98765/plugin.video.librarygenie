
# Info Hijack System Documentation

## Overview

The Info Hijack System allows LibraryGenie to provide native Kodi info dialogs for plugin-sourced media items. When a user opens info on a LibraryGenie item, the system intercepts this action and redirects to a native Kodi library dialog with full metadata.

## Architecture

### Core Components

- **InfoHijackManager** (`lib/ui/info_hijack_manager.py`): Main controller that monitors dialog states and triggers hijack process
- **Info Hijack Helpers** (`lib/ui/info_hijack_helpers.py`): XSP generation and native dialog opening utilities

### 5-Step Hijack Process

1. **💾 STEP 1: SAVE RETURN TARGET** - Store current container path and position for restoration
2. **🚪 STEP 2: CLOSE CURRENT DIALOG** - Close the plugin info dialog
3. **🚀 STEP 3: OPEN NATIVE INFO VIA XSP** - Create XSP file and navigate to native library view
4. **📺 STEP 4: NATIVE DIALOG OPENS** - User sees full Kodi native info dialog
5. **🔄 STEP 5: CONTAINER RESTORE** - When user closes dialog, restore original plugin container

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
- **Return Target Storage**: Uses Kodi window properties to store restoration data

## Performance Considerations

- **Decoupled Operation**: Heavy operations (XSP creation, container rebuild) happen after dialog opens
- **Fast Native Opening**: Native info appears immediately without waiting for container restoration
- **Efficient XSP**: Minimal XML generation using database ID filters
- **Memory Management**: Temporary XSP files are cleaned up automatically

## Error Handling

- **DBID Validation**: Ensures valid integer conversion before XSP creation
- **Dialog State Validation**: Confirms dialogs open/close as expected
- **Exception Recovery**: Comprehensive try/catch blocks with detailed logging
- **State Reset**: Ensures manager state is reset even if hijack fails

## Logging

The system provides detailed logging with emoji prefixes for easy debugging:

- 🎯 Hijack triggers and detection
- 💾 Return target operations  
- 🚪 Dialog close operations
- 🚀 Native info opening
- 🔄 Container restoration
- ✅ Success confirmations
- ❌ Error conditions

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
