
# LibraryGenie Context Menu Documentation

This document provides a comprehensive overview of the context menu system in LibraryGenie, detailing all possible actions and scenarios that can appear in different contexts.

## Overview

The LibraryGenie context menu system provides contextual actions for media items based on their source, type, and viewing context. The system intelligently prioritizes contexts and shows appropriate options to enhance the user experience.

## Context Menu Structure

Every LibraryGenie context menu begins with a **"Search"** option, followed by conditional options based on item type and context.

## Context Priority System

The context menu logic prioritizes contexts in this hierarchical order:

1. **LibraryGenie context** (highest priority)
2. **Library context** (Kodi database items)
3. **Container context** (movies/episodes/musicvideos containers)
4. **Plugin context** (plugin:// file paths)
5. **Unknown context** (search only - lowest priority)

## Detailed Scenarios

### 1. LibraryGenie Context Items (Highest Priority)

Detected when:
- Container path starts with `plugin://plugin.video.librarygenie/`
- File path starts with `plugin://plugin.video.librarygenie/`
- InfoHijack is armed (`LG.InfoHijack.Armed=1`) with valid DBID

#### A. Existing LibraryGenie Items (`media_item_id` available)
**Available Actions:**
- **Search** (always first)
- **Quick Add to Default** (if quick-add enabled + default list configured)
- **Add to List...**
- **Remove from List** (if viewing within a list context)

**Action Details:**
- Uses `media_item_id` for precise item identification
- Remove option appears when `list_id` is detected in container path or item properties

#### B. Library Items in LibraryGenie Context (`dbtype` + `dbid` available)
**Available Actions:**
- **Search** (always first)
- **Remove from List** (if in list context - appears first)
- **Quick Add to Default** (if enabled)
- **Add to List...**

**Action Details:**
- Uses library metadata (`dbtype`/`dbid`) for identification
- Specialized handling for library items viewed through LibraryGenie interface
- Does NOT call standard library functions to prevent duplicate options

#### C. External Items in LibraryGenie Context (title available)
**Available Actions:**
- **Search** (always first)
- **Remove from List** (if in list context - appears first)
- **Add to List...** (external item handling)

**Action Details:**
- Handles non-library items viewed through LibraryGenie
- Metadata gathered from InfoLabels during action execution

### 2. Regular Library Items (Second Priority)

When NOT in LibraryGenie context but item has valid library metadata (`dbtype` + `dbid`).

#### A. Library Movies (`dbtype='movie'` + valid `dbid`)
**Available Actions:**
- **Search**
- **Remove from List** (if container path indicates list context)
- **Quick Add to Default List** (if enabled)
- **Add to List...**

#### B. Library Episodes (`dbtype='episode'` + valid `dbid`)
**Available Actions:**
- **Search**
- **Remove from List** (if in list context, excluding Search History)
- **Quick Add to Default List** (if enabled)
- **Add to List...**

#### C. Library Music Videos (`dbtype='musicvideo'` + valid `dbid`)
**Available Actions:**
- **Search**
- **Remove from List** (if in list context, excluding Search History)
- **Quick Add to Default List** (if enabled)  
- **Add to List...**

### 3. External/Plugin Items (Third Priority)

Items without library metadata but in recognizable containers.

#### A. Items in Movie Containers (`Container.Content(movies)`)
**Available Actions:**
- **Search**
- **Add to List...** (external item handling)

#### B. Items in Episode Containers (`Container.Content(episodes)`)
**Available Actions:**
- **Search**
- **Add to List...** (external item handling)

#### C. Items in Music Video Containers (`Container.Content(musicvideos)`)
**Available Actions:**
- **Search**
- **Add to List...** (external item handling)

#### D. Other Plugin Items (`plugin://` file paths)
**Available Actions:**
- **Search**
- **Add to List...** (external item handling)

### 4. Fallback Items (Lowest Priority)

Unknown or unsupported items receive minimal functionality.

**Available Actions:**
- **Search** (only option available)

## Action Types Explained

### Core Actions

1. **Search**
   - Always available as first option
   - Launches LibraryGenie search interface
   - Action: `search`

2. **Add to List...**
   - Opens list selection dialog for adding items
   - Variants: library items, external items, media items
   - Actions: `add_library_item_to_list_context`, `add_external_item`, `add_to_list`

3. **Quick Add to Default**
   - Instantly adds to pre-configured default list
   - Only appears when enabled in settings with default list configured
   - Actions: `quick_add_context`, `quick_add_library_item`, `quick_add`

4. **Remove from List**
   - Removes item from current list context
   - Appears first when in list contexts
   - Excludes Search History lists
   - Actions: `remove_from_list`, `remove_library_item_from_list`

### Action Variations by Item Type

#### Library Item Actions
- Work with Kodi database IDs (`dbtype`/`dbid`)
- Direct integration with Kodi's media database
- Efficient identification and processing

#### External Item Actions
- Gather metadata from Kodi InfoLabels
- Collect comprehensive artwork information
- Support for various media types (movies, episodes, music videos)

#### Media Item Actions
- Use LibraryGenie's internal `media_item_id`
- Most efficient for existing LibraryGenie items
- Direct database operations

## Context Detection Logic

### LibraryGenie Context Detection
```python
is_librarygenie_context = (
    container_path.startswith('plugin://plugin.video.librarygenie/') or
    (file_path and file_path.startswith('plugin://plugin.video.librarygenie/')) or
    (item_info.get('hijack_armed') == '1' and item_info.get('hijack_dbid'))
)
```

### List Context Detection
- Container path contains `list_id=` parameter
- Item properties include `list_id`
- Used to determine when "Remove from List" options should appear

### InfoHijack Fallback System
When regular properties are unavailable, the system uses InfoHijack properties:
- `LG.InfoHijack.DBID` → fallback for `ListItem.DBID`
- `LG.InfoHijack.DBType` → fallback for `ListItem.DBTYPE`
- `LG.InfoHijack.Armed` → indicates InfoHijack is active

## Special Behaviors

### Remove Options Prioritization
- Remove options appear **first** when in list contexts
- Provides immediate access to list management functionality
- Context-sensitive labeling and action parameters

### Quick Add Functionality
- Only appears when enabled in addon settings
- Requires a default list to be configured
- Streamlines workflow for frequent list additions

### Search History Exclusion
- Remove options are excluded from Search History lists
- Prevents accidental removal of search result references
- Search History items are read-only by design

### External Item Metadata Gathering
When adding external items, the system collects:
- Basic metadata (title, year, plot, rating, etc.)
- Media type detection (movie, episode, music video)
- Comprehensive artwork collection
- Unique identifiers (IMDb, TMDb when available)

## Error Handling and Fallbacks

### Property Caching
All item properties are cached before showing dialogs to prevent context loss:
```python
item_info = {
    'dbtype': xbmc.getInfoLabel('ListItem.DBTYPE'),
    'dbid': xbmc.getInfoLabel('ListItem.DBID'),
    # ... other properties
}
```

### Graceful Degradation
- If specialized actions fail, system falls back to basic functionality
- Missing localization strings use English fallbacks
- Invalid or missing metadata doesn't prevent core functionality

### Debug Logging
Comprehensive logging throughout the context detection process:
- Item property values
- Context detection results
- Action selection logic
- Execution paths

## Configuration Dependencies

### Settings Integration
- Quick Add functionality requires `quick_add_enabled` setting
- Default list selection requires `default_list_id` setting
- Context menu behavior adapts to user preferences

### Localization Support
- All menu labels support localization
- Fallback to English labels when localization unavailable
- String IDs: `31000` (Add to List), `31001` (Quick Add), `31010` (Remove from List), `33000` (Search)

This context menu system provides a comprehensive and intuitive interface for managing media across different contexts while maintaining consistency and performance.
