
# LibraryGenie Tools & Options Documentation

This document provides a comprehensive overview of the Tools & Options system in LibraryGenie, detailing all possible actions and scenarios that can appear in different contexts.

## Overview

The Tools & Options system in LibraryGenie provides contextual management actions for different types of content and containers. Unlike the context menu system which focuses on individual items, Tools & Options deals with bulk operations, container management, and administrative functions.

## Tools & Options Structure

Every Tools & Options dialog is organized by operation type with color-coded options:
- **🟢 Creation/Additive Operations** (lightgreen)
- **🟡 Modification Operations** (yellow) 
- **⚪ Export/Information Operations** (white)
- **🔴 Destructive Operations** (red)
- **🔘 Cancel** (gray)

## Context Detection System

The Tools & Options system activates based on `list_type` parameter:

1. **`favorites`** - Kodi Favorites management
2. **`user_list`** - Individual user list management  
3. **`folder`** - Folder and subfolder management
4. **`lists_main`** - Main Lists menu administration

## Detailed Scenarios

### 1. Kodi Favorites Tools (`list_type="favorites"`)

**Context**: Accessed from the Kodi Favorites main view

**Available Actions:**
- **🟢 Scan Favorites** (with timestamp display)
- **🟢 Save As New List** 
- **🔘 Cancel**

**Action Details:**
- **Scan Favorites**: Refreshes mapping between Kodi favorites and library items
  - Shows time since last scan (e.g., "Scan Favorites (2 hours ago)")
  - Displays "just now", minutes, hours, or days ago
  - Falls back to basic label if timestamp parsing fails
- **Save As New List**: Converts current favorites into a regular LibraryGenie list
  - Prompts for new list name
  - Creates list with mapped favorites content

**Special Behaviors:**
- Timestamp display provides user context about data freshness
- Limited options reflect read-only nature of Kodi favorites
- Actions focus on data refresh and conversion rather than modification

### 2. User List Tools (`list_type="user_list"`)

**Context**: Accessed from any user-created list view  
**Parameter**: `list_id` required

#### A. Regular User Lists

**Available Actions:**
- **🟢 Merge Into [ListName]** - Merge another list into this one
- **🟡 Rename [ListName]** - Change list name
- **🟡 Move [ListName] to Folder** - Relocate to different folder
- **⚪ Export [ListName]** - Export list data
- **🔴 Delete [ListName]** - Remove list entirely
- **🔘 Cancel**

**Action Details:**

**Merge Lists:**
- Shows selection dialog of all other available lists
- Displays item counts for context (e.g., "My Movies (45 items)")
- Confirmation dialog explains merge behavior
- Source list remains unchanged after merge
- Reports number of new items added

**Rename List:**
- Text input dialog for new name
- Validates against duplicate names in same folder
- Updates list metadata immediately

**Move to Folder:**
- Selection dialog showing "[Root Level]" plus all available folders
- Excludes "Search History" folder from options
- Updates folder assignment and refreshes view

**Export List:**
- Uses unified export engine for JSON output
- Includes all list items and metadata
- Reports export statistics (filename, items, file size)

**Delete List:**
- Confirmation dialog with destructive action warning
- Sets navigation flag to return to Lists menu
- Permanent deletion with no undo capability

#### B. Search History Lists

**Context**: Lists in the "Search History" folder  
**Special Behaviors**: Different option set due to read-only nature

**Available Actions:**
- **🟢 Copy to New List** - Convert search results to regular list
- **⚪ Export [SearchName]** - Export search results
- **🔴 Delete [SearchName]** - Remove search history entry
- **🔘 Cancel**

**Action Details:**

**Copy to New List:**
- Auto-suggests cleaned search term as list name
- Removes "Search: '" prefix and result count suffix
- Creates new regular list with search results
- Provides full list management capabilities for copied content

**Navigation Logic:**
- If deleting last search history item: Navigate to main menu
- If other search history remains: Navigate back to Search History folder

### 3. Folder Tools (`list_type="folder"`)

**Context**: Accessed from any folder view  
**Parameter**: `folder_id` required

#### A. Regular Folders

**Available Actions:**
- **🟢 Create New List in '[FolderName]'** - Add list to folder
- **🟢 Create New Subfolder in '[FolderName]'** - Add nested folder
- **🟡 Rename '[FolderName]'** - Change folder name
- **🟡 Move '[FolderName]' to Parent Folder** - Relocate folder
- **⚪ Export All Lists in '[FolderName]'** - Bulk export
- **🔴 Delete '[FolderName]'** - Remove folder and contents
- **🔘 Cancel**

**Action Details:**

**Create New List:**
- Text input for list name
- Validates against duplicates within folder
- Creates list directly in current folder context

**Create New Subfolder:**
- Text input for folder name  
- Validates against duplicate folder names in same location
- Establishes parent-child folder relationship

**Rename Folder:**
- Text input with current name as default
- Validates against duplicate names in same parent location
- Updates folder metadata immediately

**Move Folder:**
- Selection dialog showing "[Root Level]" plus valid parent folders
- Excludes self and "Search History" from options
- Prevents circular folder relationships

**Export All Lists:**
- Confirmation dialog showing list count in folder
- Bulk export of all lists and their items
- Uses unified export engine with folder context

**Delete Folder:**
- Confirmation dialog with warning about contents
- Cascading deletion of all lists and subfolders
- Sets navigation flag to return to Lists menu

#### B. Search History Folder (Reserved)

**Context**: The special "Search History" system folder  
**Special Behaviors**: Limited operations due to system folder status

**Available Actions:**
- **⚪ Export All Lists in 'Search History'** - Bulk export search results
- **🟡 Clear All Search History** - Remove all search history lists
- **🔘 Cancel**

**Action Details:**

**Export All Lists:**
- Exports all saved search results
- Includes full metadata and item details
- Useful for archiving search history

**Clear All Search History:**
- Confirmation dialog showing count of lists to delete
- Bulk deletion of all search history lists
- Irreversible operation with explicit warning

### 4. Lists Main Tools (`list_type="lists_main"`)

**Context**: Accessed from the main Lists menu  
**Purpose**: System-wide administration and bulk operations

**Available Actions:**
- **🟢 Create New List** - Add list at root level
- **🟢 Create New Folder** - Add folder at root level
- **⚪ Import Lists** - Import from external file
- **⚪ Export All Lists** - Complete system export
- **⚪ Manual Backup** - Create backup snapshot
- **⚪ Backup Manager** - Manage existing backups
- **⚪ Test Backup Config** - Validate backup settings
- **🟡 Library Statistics** - Show system stats
- **🟡 Force Library Rescan** - Refresh library data
- **🟡 Clear Search History** - Remove all search data
- **🟡 Reset Preferences** - Reset user settings
- **🔘 Cancel**

**Action Details:**

**Create New List:**
- Creates list at root level (no folder assignment)
- Text input for list name
- Validates against existing root-level list names

**Create New Folder:**
- Creates folder at root level
- Text input for folder name
- Establishes top-level folder hierarchy

**Import Lists:**
- File browser dialog for .json/.ndjson files
- Uses unified import engine
- Reports import statistics (lists, items, folders)
- Handles various import formats and validates data

**Export All Lists:**
- Confirmation dialog showing total list count
- Complete system export including folders and metadata
- Comprehensive backup of all user data

**Manual Backup:**
- Creates timestamped backup file
- Reports backup statistics (filename, size, items)
- Uses configured backup storage location

**Backup Manager:**
- Shows list of available backups (last 10)
- Displays backup age, size, and storage type
- Restore functionality with confirmation dialogs
- Replace vs append options for restore

**Test Backup Config:**
- Validates backup storage settings
- Tests write permissions and path accessibility
- Reports configuration status

**Library Statistics:**
- System-wide statistics display
- Library item counts and mapping status
- Performance and usage metrics

**Force Library Rescan:**
- Triggers complete library refresh
- Updates all library item mappings
- Progress indication for long operations

**Clear Search History:**
- Removes all search history data
- Cleans up search history folder
- Confirmation with count of affected items

**Reset Preferences:**
- Resets user settings to defaults
- Confirmation dialog with warning
- Does not affect lists or data, only preferences

## Menu Organization Principles

### Color Coding System
- **Green**: Safe, additive operations that create new content
- **Yellow**: Modification operations that change existing content
- **White**: Information/export operations that don't modify data
- **Red**: Destructive operations requiring confirmation
- **Gray**: Cancel/exit options

### Name Display Logic
For context menus, long names are shortened for readability:
- **Search History**: Extracts search terms (e.g., "Search: 'batman'" → "'batman'")
- **Regular Names**: Truncates with ellipsis (e.g., "Very Long List Name" → "Very Long List...")
- **Maximum Length**: 30 characters for menu display

### Navigation Behavior
Different actions set specific navigation flags:
- **`refresh_needed`**: Refresh current view after changes
- **`navigate_to_lists`**: Return to main Lists menu
- **`navigate_to_folder`**: Navigate to specific folder
- **`navigate_to_main`**: Return to main menu

## Administrative Functions

### Backup Management
- **Manual Backup**: User-initiated backup creation
- **Backup Manager**: List and restore from existing backups
- **Test Configuration**: Validate backup settings
- **Retention Management**: Automatic cleanup of old backups

### Import/Export Operations
- **Single List Export**: Individual list with metadata
- **Folder Export**: All lists within a folder
- **Complete Export**: Entire system including folders
- **Import**: External data integration with validation

### System Maintenance
- **Library Rescan**: Refresh all library mappings
- **Clear Search History**: Remove accumulated search data
- **Reset Preferences**: Return settings to defaults
- **Statistics Display**: System health and usage metrics

## Error Handling and Validation

### Input Validation
- **Name Uniqueness**: Prevents duplicate names in same context
- **Character Limits**: Enforces reasonable name lengths
- **Reserved Names**: Prevents conflicts with system folders
- **Path Validation**: Ensures valid folder hierarchies

### Confirmation Dialogs
- **Destructive Operations**: Always require explicit confirmation
- **Bulk Operations**: Show counts and scope before execution
- **Irreversible Actions**: Clear warning about permanence
- **Cancel Options**: Always provide escape mechanism

### Error Recovery
- **Graceful Degradation**: Continue operation if non-critical errors
- **Rollback Capability**: Undo changes if operation fails partway
- **User Feedback**: Clear error messages with context
- **Logging**: Comprehensive error logging for troubleshooting

## Integration with Settings

### Setting Dependencies
- **Default List**: Quick Add functionality requires configuration
- **Backup Settings**: Storage location and retention policies
- **Favorites Integration**: Enable/disable Kodi favorites features
- **Debug Logging**: Enhanced logging for troubleshooting

### Dynamic Behavior
- **Feature Availability**: Options appear based on settings state
- **Storage Configuration**: Backup locations adapt to user settings
- **Integration State**: Favorites tools only appear when enabled
- **Performance Tuning**: Batch sizes and timeouts from settings

This Tools & Options system provides comprehensive management capabilities while maintaining user safety through confirmation dialogs, clear organization, and logical navigation flows.
