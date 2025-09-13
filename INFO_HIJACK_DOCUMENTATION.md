
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

## Technical Implementation

### Core Functions

- **`InfoHijackManager.tick()`**: Main monitoring loop that:
  - Checks cooldown periods and progress state
  - Monitors dialog state changes via `DialogVideoInfo.xml` detection
  - Handles primary and fallback dialog close detection
  - Triggers hijack process when armed items are detected
  - Manages extended monitoring and XSP safety net features

- **`open_native_info_fast()`**: Orchestrates the complete hijack flow:
  1. Closes current dialog with verification
  2. Creates temporary XSP file via `_create_xsp_for_dbitem()`
  3. Navigates to XSP path and waits for videos window
  4. Opens info dialog on the single list item
  5. Sets up monitoring for dialog close detection

- **`_create_xsp_for_dbitem()`**: Generates temporary XSP files:
  - Retrieves actual file path from database item
  - Creates filename-based filter rules (not database ID filters)
  - Handles movies and episodes with appropriate XSP structure
  - Manages dedicated temp directory with fallback strategy

- **`restore_container_after_close()`**: Handles post-hijack navigation:
  - Detects XSP paths using pattern matching (`.xsp` or `smartplaylist`)
  - Executes double-back navigation for XSP cleanup
  - Uses single back navigation for non-XSP contexts
  - Leverages Kodi's navigation history for position restoration

### Helper Utilities

- **`wait_for_dialog_close()`**: Monitors dialog state changes with 20ms precision
- **`wait_until()`**: Adaptive polling with intelligent timing adjustments
- **`cleanup_old_hijack_files()`**: Prevents XSP file accumulation in temp directory
- **`_wait_videos_on()`**: Handles network storage scenarios with extended timeouts

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

- **Movies**: `special://temp/librarygenie_hijack/lg_hijack_movie_{dbid}.xsp`
- **Episodes**: `special://temp/librarygenie_hijack/lg_hijack_episode_{dbid}.xsp`

These XSP files use **filename-based filtering** rather than database ID filters. They filter items using the `filename` operator with the target file's basename (without extension), ensuring exactly one item appears in the native library context.

### XSP Content Structure

```xml
<!-- Example Movie XSP -->
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<smartplaylist type="movies">
  <name>LG Hijack movie 123</name>
  <match>all</match>
  <rule field="filename" operator="contains">
    <value>MovieTitle</value>
  </rule>
  <order direction="ascending">title</order>
</smartplaylist>
```

### XSP File Management

- Files are stored in a dedicated `librarygenie_hijack/` subdirectory under Kodi's temp folder
- Old hijack XSP files are automatically cleaned up via `cleanup_old_hijack_files()` to prevent accumulation
- If the subdirectory creation fails, fallback uses direct temp folder placement

## State Management

The InfoHijackManager maintains sophisticated state tracking to ensure reliable operation:

### Core State Variables
- **Cooldown System**: `_cooldown_until` prevents rapid-fire hijacks during navigation
- **Progress Tracking**: `_in_progress` prevents re-entry during active hijack operations  
- **Dialog State Monitoring**: Tracks dialog IDs and states using `_last_dialog_state` tuple
- **Navigation History**: Leverages Kodi's built-in navigation stack instead of manual state management

### Extended Monitoring Features
- **XSP Safety Net**: `_hijack_monitoring_expires` provides extended monitoring after hijack completion
- **Path Stability Tracking**: `_path_stable_since` ensures navigation has stabilized before actions
- **Safety Attempt Limiting**: `_safety_attempts` and `_last_safety_attempt` prevent excessive retry loops
- **Extended Monitoring Mode**: `_extended_monitoring_active` enables enhanced state tracking when needed

### Dialog Detection Mechanism
- **Primary Detection**: State change monitoring comparing previous and current dialog states
- **Fallback Detection**: Secondary check for missed state transitions
- **Specific Dialog Targeting**: Monitors `DialogVideoInfo.xml` and dialog ID changes
- **Debug Logging**: Periodic container scanning every 2.5 seconds for armed items (debug builds)

### State Reset Safety
- Comprehensive state reset in exception handlers ensures manager doesn't get stuck
- Automatic cleanup prevents memory leaks from incomplete hijack operations

## Performance Considerations

### Navigation Optimizations
- **XSP Detection**: Automatically detects temporary XSP lists and navigates back efficiently
- **No Container Refresh**: Eliminates expensive `Container.Update()` operations that cause 5-6 second delays
- **Double-Back Navigation**: Uses two fast `Action(Back)` commands (~250ms total) instead of container rebuilds
- **Navigation History**: Leverages Kodi's built-in navigation stack for automatic position restoration

### XSP and File Operations
- **Efficient XSP**: Minimal XML generation using filename-based filters instead of complex database queries
- **Dedicated Temp Directory**: Uses `special://temp/librarygenie_hijack/` to avoid conflicts with Kodi's playlist scanning
- **Automatic Cleanup**: `cleanup_old_hijack_files()` prevents XSP file accumulation
- **Fallback Strategy**: Graceful degradation to direct temp folder if subdirectory creation fails

### Dialog and Monitoring Performance
- **Adaptive Polling**: `wait_until()` uses intelligent polling that starts fast (30ms) and adapts up to reasonable intervals (200ms)
- **Responsive Dialog Detection**: 20ms check intervals in `wait_for_dialog_close()` for very responsive dialog state changes
- **Extended Timeout Handling**: Network storage scenarios get extended timeouts (minimum 10 seconds) for slower file access
- **Optimized Busy State Handling**: Removed DialogBusy checks since XSP navigation works even during library scanning

### Memory and Resource Management
- **State Variable Optimization**: Minimal memory footprint with efficient state tracking variables
- **Exception Safety**: Comprehensive try/catch blocks prevent resource leaks during failures
- **Debug Throttling**: Anti-spam debugging with `_debug_log_interval` to prevent log flooding
- **Monitoring Expiration**: Time-based monitoring expiration prevents indefinite resource usage

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

- 🎬 HIJACK HELPERS: Starting hijack process for {type} {id}
- 🔍 HIJACK DIALOG STATE CHANGE: Dialog state monitoring
- 🔄 HIJACK STEP 5: Dialog close detection and navigation back to plugin
- ✅ HIJACK STEP 5 COMPLETE: Successful navigation restoration
- ❌ HIJACK STEP 5 FAILED: Error conditions and failures

### Detailed Log Messages

The actual implementation provides specific log messages for each phase:

**Dialog State Monitoring:**
- `"🔍 HIJACK DIALOG STATE CHANGE: active={bool}, id={id} (was {previous_state})"`
- `"🔄 HIJACK STEP 5: DETECTED DIALOG CLOSE via state change - initiating navigation back to plugin"`
- `"🔄 HIJACK STEP 5: NATIVE INFO DIALOG CLOSED (fallback detection) - initiating navigation back to plugin"`

**XSP Operations:**
- `"Creating XSP for database item {type} {id}"`
- `"Creating XSP for {type} {id}: filename='{filename}', no_ext='{filename_no_ext}'"`
- `"XSP created successfully: {path}"`

**Performance Monitoring:**
- `"_wait_videos_on: Starting wait_until with {timeout}ms timeout"`
- `"_wait_videos_on SUCCESS after {elapsed:.3f}s"`
- `"Dialog close detected {context} after {elapsed:.3f}s"`

**Cleanup Operations:**
- `"Cleaned up old hijack file: {filename}"`
- `"Creating hijack temp directory: {path}"`

### Debug Throttling

The system includes anti-spam debugging with `_debug_log_interval` (10 seconds) to prevent log flooding during rapid state changes while maintaining essential debugging information.

## Usage Requirements

1. **Kodi Library Items**: Only works with items that exist in Kodi's video database
2. **Valid Database IDs**: Items must have movieid, episodeid, or similar Kodi identifiers
3. **Library Context**: Target items must be accessible via native Kodi library views
4. **XSP Support**: Requires Kodi's smart playlist functionality

## Future Enhancements

- **Custom Button Integration**: Add LibraryGenie-specific buttons to hijacked dialogs
- **Multiple Media Types**: Extend support to TV shows
- **Context Menu Actions**: Hijack context menu "Information" selections
- **Keyboard Shortcuts**: Detect 'i' key presses for info actions
