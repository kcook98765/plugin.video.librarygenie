# LibraryGenie Context Menu Documentation

This document provides a comprehensive overview of the current context menu system in LibraryGenie, detailing all available actions and menu structures.

## Overview

The LibraryGenie context menu system provides a unified interface for managing media items across different contexts. When activated, it displays a "LibraryGenie" dialog with contextually relevant options for adding, managing, and searching for media items.

## Main Context Menu Structure

The LibraryGenie context menu always shows a dialog titled **"LibraryGenie"** with the following options in order:

### 1. LG Search / LG Search/Favorites
- **Always appears first**
- Label changes based on Kodi Favorites integration setting:
  - "LG Search/Favorites" (if favorites integration enabled)
  - "LG Search" (if favorites integration disabled)
- Opens the **Search Submenu** with multiple search options
- Action: `show_search_submenu`

### 2. LG Quick Add (Conditional)
- **Only appears when both conditions are met:**
  - Quick Add is enabled in addon settings
  - A default list is configured
- Instantly adds the current item to the pre-configured default list
- Uses different actions based on available item metadata:
  - `quick_add&media_item_id=X` (if media_item_id available)
  - `quick_add_context&dbtype=X&dbid=X&title=X` (if library metadata available)
  - `quick_add_external` (for external items)

### 3. LG Add to List...
- **Always appears**
- Opens a dialog to select which list to add the item to
- Uses different actions based on available item metadata:
  - `add_to_list&media_item_id=X` (if media_item_id available)
  - `add_to_list&dbtype=X&dbid=X&title=X` (if library metadata available)
  - `add_external_item` (for external items)

### 4. LG Remove from List (Conditional)
- **Only appears when in a list context:**
  - Container path contains `list_id=` parameter, OR
  - Item properties include `list_id`
- Removes the item from the current list
- Uses different actions based on available item metadata:
  - `remove_from_list&list_id=X&item_id=X` (if media_item_id available)
  - `remove_library_item_from_list&list_id=X&dbtype=X&dbid=X&title=X` (if library metadata available)
  - `remove_from_list_generic` (fallback)

### 5. LG more...
- **Always appears last**
- Opens the **More Options Submenu** with advanced actions
- Action: `show_more_submenu`

## Search Submenu Structure

When "LG Search" is selected, it opens a dialog titled **"LibraryGenie Search Options"** with these options:

### 1. Local Movie Search
- Searches local Kodi movie library
- Action: `search_movies`

### 2. Local TV Search  
- Searches local Kodi TV show library
- Action: `search_tv`

### 3. AI Movie Search (Conditional)
- **Only appears when both conditions are met:**
  - AI search is activated in configuration
  - AI search API key is configured
- Provides AI-powered movie search
- Action: `search_ai`

### 4. Search History
- **Always appears**
- Access to previous search results
- Action: `search_history`

### 5. Kodi Favorites (Conditional)
- **Only appears when favorites integration is enabled**
- Access to Kodi favorites functionality
- Action: `show_favorites`

## More Options Submenu Structure

When "LG more..." is selected, it opens a dialog titled **"LibraryGenie More Options"** with these options:

### 1. Move to Another List...
- **Currently the only option in this submenu**
- Allows moving the item from current list to another list
- Displayed with yellow text color
- Action: `move_to_list`

## Context Detection Logic

The system caches all item information before showing any dialogs to prevent context loss:

```python
item_info = {
    'dbtype': xbmc.getInfoLabel('ListItem.DBTYPE'),
    'dbid': xbmc.getInfoLabel('ListItem.DBID'),
    'file_path': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
    'title': xbmc.getInfoLabel('ListItem.Title'),
    'label': xbmc.getInfoLabel('ListItem.Label'),
    'media_item_id': xbmc.getInfoLabel('ListItem.Property(media_item_id)'),
    'list_id': xbmc.getInfoLabel('ListItem.Property(list_id)'),
    'container_content': xbmc.getInfoLabel('Container.Content'),
    'is_movies': xbmc.getCondVisibility('Container.Content(movies)'),
    'is_episodes': xbmc.getCondVisibility('Container.Content(episodes)'),
    # InfoHijack fallback properties
    'hijack_dbid': xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBID)'),
    'hijack_dbtype': xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.DBType)'),
    'hijack_armed': xbmc.getInfoLabel('ListItem.Property(LG.InfoHijack.Armed)')
}
```

### LibraryGenie Context Detection
The system detects if it's operating in a LibraryGenie context using:
```python
is_librarygenie_context = (
    container_path.startswith('plugin://plugin.video.librarygenie/') or
    (file_path and file_path.startswith('plugin://plugin.video.librarygenie/')) or
    (item_info.get('hijack_armed') == '1' and item_info.get('hijack_dbid'))
)
```

### List Context Detection
The system determines if an item is in a list context by checking:
- Container path contains `list_id=` parameter
- Item properties include `list_id`

### InfoHijack Fallback System
When regular properties are unavailable, the system uses InfoHijack properties:
- `LG.InfoHijack.DBID` → fallback for `ListItem.DBID`
- `LG.InfoHijack.DBType` → fallback for `ListItem.DBTYPE`
- `LG.InfoHijack.Armed` → indicates InfoHijack is active

## Action Priority Logic

The system determines which action to use based on available metadata, in this priority order:

### 1. Media Item Actions (Highest Priority)
- Used when `media_item_id` is available
- Most efficient for existing LibraryGenie items
- Direct database operations using internal ID

### 2. Library Item Actions (Medium Priority)
- Used when `dbtype` and `dbid` are available
- Works with Kodi database IDs
- Direct integration with Kodi's media database

### 3. External Item Actions (Lowest Priority)
- Used when only basic metadata is available
- Gathers metadata from Kodi InfoLabels during execution
- Handles non-library items and plugin content

## Configuration Dependencies

### Settings Integration
- **Quick Add functionality** requires `quick_add_enabled` setting
- **Default list selection** requires `default_list_id` setting
- **Favorites integration** requires `enable_favorites_integration` setting

### AI Search Dependencies
- **AI search availability** requires `ai_search_activated` configuration
- **AI search functionality** requires `ai_search_api_key` configuration

### Localization Support
All menu labels support localization with fallbacks:
- `37100`: "LG Search"
- `37101`: "LG Quick Add"  
- `37102`: "LG Add to List..."
- `37103`: "LG Remove from List"
- `37104`: "LG more..."
- `37105`: "LG Search/Favorites"
- `37200`: "Local Movie Search"
- `37201`: "Local TV Search"
- `37202`: "AI Movie Search"
- `37203`: "Search History"
- `37204`: "Kodi Favorites"

## Error Handling and Fallbacks

### Graceful Degradation
- Missing settings default to disabled functionality
- Missing localization strings use English fallbacks
- Invalid metadata doesn't prevent core functionality
- Menu errors fall back to basic search functionality

### Debug Logging
Comprehensive logging throughout the context menu process:
- Item property values and caching
- Menu option building and selection
- Action execution and results
- Error conditions and fallbacks

This simplified, unified context menu system provides consistent functionality across all contexts while maintaining flexibility for different item types and user configurations.