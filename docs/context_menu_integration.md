
# Context Menu Integration Documentation

This document explains how LibraryGenie integrates with Kodi's context menu system to provide seamless access to addon functionality from anywhere in the Kodi interface.

## Overview

LibraryGenie registers context menu entries that appear when users right-click on media items throughout Kodi. This integration allows users to add items to lists, find similar content, and access addon features without navigating to the addon's main interface.

## Context Menu Registration

The context menu integration is configured in `addon.xml`:

```xml
<extension point="kodi.context.item" library="resources/lib/context.py">
    <item>
        <label>32001</label>
        <visible>true</visible>
    </item>
</extension>
```

## Entry Point

The main entry point is `resources/lib/context.py`, which acts as a compatibility shim:

```python
from resources.lib.core.context import run as _run

def run(*args, **kwargs):
    return _run(*args, **kwargs)
```

The actual implementation is in `resources.lib.core.context.py`.

## Context Menu Builder

The `ContextMenuBuilder` class (`resources.lib.kodi.context_menu_builder.py`) handles the construction and display of context menu options:

### Key Methods

- `show_context_menu()`: Main entry point for displaying context options
- `_build_context_options()`: Constructs available options based on current state
- `_is_authenticated()`: Checks remote API authentication status
- `_detect_viewing_context()`: Determines if user is viewing a LibraryGenie list

### Dynamic Options

Context menu options are dynamically generated based on:

1. **Authentication Status**: Some options require remote API access
2. **Current Context**: Different options when viewing LibraryGenie lists vs. other content
3. **Item Type**: Movie-specific options vs. general options

## Available Context Options

### Always Available

1. **Add to List**: Add the current item to an existing or new list
2. **Create New List**: Create a new list and add the item
3. **Settings**: Access addon configuration
4. **Refresh Metadata**: Update item information from library sources
5. **Search History**: Browse previously performed searches

### Authentication-Dependent (Alpha)

1. **Find Similar Movies**: Use AI to find movies similar to the current item
2. **Add Similar to List**: Find similar movies and add them to a list
3. **Search Movies**: Perform AI-powered movie searches

### Context-Specific

1. **Remove from List**: Available when viewing a LibraryGenie list
2. **List Management**: 
   - **Rename List**: Change the name of the current list
   - **Delete List**: Permanently remove the current list after confirmation
   - **Move List**: Move the current list to a different folder with folder selection dialog
   - **Add Movies to List**: Add additional movies to the current list (planned)
   - **Clear List**: Remove all items from the current list (planned)

## IMDb ID Detection

Context menu functionality relies on extracting IMDb IDs from the current item:

```python
# KodiHelper handles v19/v20+ compatibility
kodi_helper = KodiHelper()
imdb_id = kodi_helper.get_imdb_from_item()
```

### Detection Methods

1. **InfoLabel Extraction**: Uses `ListItem.getVideoInfoTag()` for v20+
2. **Legacy Path**: Uses `xbmc.getInfoLabel()` for v19 compatibility
3. **URL Parsing**: Extracts IMDb ID from item URLs when available

## Error Handling

Context menu operations include comprehensive error handling:

- **Missing IMDb ID**: Graceful degradation when ID cannot be detected
- **Authentication Failures**: Clear messaging for unauthenticated operations
- **Database Errors**: Transaction rollback and user notification
- **Network Issues**: Timeout handling for remote API calls

## Integration Points

### With Core Systems

- **Database Manager**: For list operations and storage
- **Navigation Manager**: For UI state management
- **Options Manager**: For shared option handling logic
- **Route Handlers**: For executing selected actions

### With Remote API (Alpha)

- **Remote API Client**: For similarity search operations
- **Authentication System**: For validating API access
- **Search Operations**: For AI-powered movie discovery

## Usage Flow

1. **User Right-Clicks**: On any media item in Kodi
2. **Context Detection**: System detects current viewing context
3. **IMDb ID Extraction**: Attempts to extract item identifier
4. **Options Building**: Constructs appropriate menu options
5. **User Selection**: User chooses from available actions
6. **Action Execution**: Selected operation is performed
7. **Result Display**: User receives feedback on operation success

### List Management Operations

When right-clicking on a LibraryGenie list item, additional management options become available:

1. **Move List**: Presents a folder selection dialog showing all available folders (excluding protected folders like Search History). The list is moved to the selected destination folder.

2. **Delete List**: Shows a confirmation dialog before permanently removing the list and all its contents from the database.

3. **Rename List**: Opens an input dialog to change the list name, with validation to prevent duplicate names within the same folder.

## Configuration

Context menu behavior can be configured through addon settings:

- **Debug Logging**: Enable detailed context menu logging
- **Remote API Settings**: Configure authentication for advanced features
- **UI Behavior**: Customize timeout and retry settings

## Troubleshooting

### Common Issues

1. **Context Menu Not Appearing**: Check addon installation and Kodi restart
2. **Missing Options**: Verify authentication status for Alpha features
3. **IMDb ID Detection Failures**: Enable debug logging to trace extraction process
4. **Slow Response**: Check network connectivity for remote API operations
5. **List Management Failures**: Ensure proper list_id extraction from the current container path
6. **Move List Shows No Folders**: Verify that target folders exist and are not protected (like Search History)

### Debug Information

Enable debug logging in addon settings to capture:
- IMDb ID detection process
- Context option building decisions
- API call results and timing
- Error conditions and recovery

### Log Analysis

Key log patterns to monitor:

```
LibraryGenie: IMDb ID from KodiHelper: tt1234567
LibraryGenie: Detected potential list_id: 123
LibraryGenie: Context menu options built: 5 options
LibraryGenie: User selected option: Add to List
```

## Best Practices

### For Users

1. **Verify IMDb Data**: Ensure your library has IMDb IDs for best functionality
2. **Configure Authentication**: Set up remote API for advanced features
3. **Use Descriptive Names**: When creating lists from context menu
4. **Check Results**: Verify items were added successfully

### For Developers

1. **Error Handling**: Always provide fallback options for failed operations
2. **User Feedback**: Give clear indication of operation success/failure
3. **Performance**: Cache authentication status and common data
4. **Compatibility**: Test across different Kodi versions and content types

## Future Enhancements

Potential improvements to context menu integration:

1. **Batch Operations**: Multi-select support for adding multiple items
2. **Smart Suggestions**: Context-aware list recommendations
3. **Keyboard Shortcuts**: Hotkey access to common operations
4. **Enhanced Detection**: Better IMDb ID extraction from various sources
5. **Custom Actions**: User-configurable context menu options

## Related Documentation

- [Database Schema](database_schema.md) - For understanding data storage
- [Data Sources](data_sources.md) - For item processing and source handling
- [Remote API Interactions](remote_api_interactions.md) - For Alpha feature integration
