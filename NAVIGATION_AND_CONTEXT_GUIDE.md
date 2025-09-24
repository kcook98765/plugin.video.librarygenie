# LibraryGenie Navigation and Context Action Guide

## Overview
This document provides a complete analysis of all navigation patterns, context actions, and container management behaviors in the LibraryGenie Kodi addon.

## 1. Kodi-Level Context Actions (addon.xml)

### Main Context Entry Point
```xml
<extension point="kodi.context.item">
  <menu id="kodi.core.main">
    <item library="context.py">
      <label>37028</label>
      <visible>true</visible>
    </item>
  </menu>
</extension>
```

**Navigation Flow:**
- **Entry Point**: `context.py` main() function
- **Container Behavior**: No endOfDirectory call - context menus don't create directories
- **Container Refresh**: None - context actions trigger plugin calls that handle their own navigation

## 2. Dynamic Context Menu System (context.py)

### Main Context Menu Builder
**Function**: `_show_librarygenie_menu(addon)`

**Context Detection Logic:**
1. **Folder Context Check**: `_is_folder_context()` - skips context menu for folder navigation
2. **LibraryGenie Context Detection**: Checks for plugin:// URLs and hijack properties
3. **Library Item Detection**: Uses DBTYPE/DBID for library items
4. **External Item Detection**: For plugin content without library mapping

### Context Menu Options Priority Order

#### 1. LG Search (if enabled)
- **Label**: L(37100) / "LG Search"
- **Action**: `show_search_submenu`
- **Navigation**: Opens search submenu dialog, no container changes

#### 2. LG Quick Add (conditional)
- **Label**: L(37101) / "LG Quick Add"
- **Conditions**: 
  - `quick_add_enabled = True`
  - `default_list_id` configured
- **Actions**:
  - Media items: `quick_add&media_item_id={id}`
  - Library items: `quick_add_context&dbtype={type}&dbid={id}`
  - External items: `quick_add_external`
- **Navigation**: 
  - Container Refresh: Yes (after successful add)
  - endOfDirectory: `succeeded=False` for context actions

#### 3. LG Add to List...
- **Label**: L(37102) / "LG Add to List..."
- **Actions**:
  - Media items: `add_to_list&media_item_id={id}`
  - Library items: `add_to_list&dbtype={type}&dbid={id}`
  - External items: `add_external_item`
- **Navigation**:
  - Shows list selection dialog
  - Container Refresh: Yes (if in list context)
  - Container Update: To list view (if navigating to list)

#### 4. LG Remove from List (conditional)
- **Label**: L(37103) / "LG Remove from List"
- **Conditions**: In list context (`list_id=` in container path)
- **Actions**:
  - Media items: `remove_from_list&list_id={id}&item_id={item_id}`
  - Library items: `remove_library_item_from_list&list_id={id}&dbtype={type}&dbid={id}`
- **Navigation**:
  - Container Refresh: Yes (refreshes current list)
  - endOfDirectory: `succeeded=True` with `updateListing=True`

#### 5. LG more... (if available)
- **Action**: Opens additional options submenu
- **Navigation**: Dialog-based, no container changes

### Search Submenu Options
**Function**: `_show_search_submenu(addon)`

1. **Local Movie Search** → `search_movies`
2. **Local TV Search** → `search_tv`
3. **AI Movie Search** (if enabled) → `search_ai`
4. **Search History** → `search_history`
5. **Kodi Favorites** (if enabled) → `show_favorites`

**Navigation**: All search actions navigate to search results with endOfDirectory

## 3. ListItem Context Menus (Built-in)

### ContextMenuBuilder Class
**File**: `lib/utils/listitem_utils.py`

#### List Item Context Menu
**Function**: `build_context_menu(item_id, 'list')`
- **Rename**: `RunPlugin(...?action=rename_list&list_id={id})`
- **Delete**: `RunPlugin(...?action=delete_list&list_id={id})`
- **Export**: `RunPlugin(...?action=export_list&list_id={id})`

**Navigation**:
- **Container Refresh**: Yes (after rename/delete)
- **endOfDirectory**: `succeeded=True` for dialogs

#### Folder Item Context Menu
**Function**: `build_context_menu(item_id, 'folder')`
- **Rename**: `RunPlugin(...?action=rename_folder&folder_id={id})`
- **Delete**: `RunPlugin(...?action=delete_folder&folder_id={id})`
- **Protected Folders**: "Search History" - no rename/delete options

**Navigation**:
- **Container Refresh**: Yes (after folder operations)
- **Response**: Sets `refresh_needed = True` for auto-refresh

#### External Item Context Menu
**Function**: `_set_external_context_menu(list_item, item)`
- **Search in Library**: `RunPlugin(...?action=search_library&title={title})`
- **Add to List**: `RunPlugin(...?action=add_to_list&item_id={id})`

## 4. Main Navigation Patterns (router.py)

### Primary Navigation Actions

#### Lists and Folders
1. **show_lists_menu** (`action=lists`)
   - **Handler**: `lists_handler.show_lists_menu()`
   - **endOfDirectory**: `succeeded=True`, `updateListing=True`, `cacheToDisc=False`
   - **Container**: Creates new directory listing

2. **show_list** (`action=show_list` or `action=view_list`)
   - **Handler**: `lists_handler.view_list()`
   - **Special Case**: Kodi Favorites triggers scan-if-needed
   - **endOfDirectory**: Via response handler with update listing
   - **Container**: Replaces current listing

3. **show_folder** (`action=show_folder`)
   - **Handler**: `lists_handler.show_folder()`
   - **endOfDirectory**: Via response handler
   - **Container**: Navigates to folder contents

#### Search Actions
1. **prompt_and_search** (`action=prompt_and_search`)
   - **Handler**: `search_handler.prompt_and_search()`
   - **endOfDirectory**: Handler manages directory completion
   - **Container**: Shows search results

#### List Management Actions
1. **add_to_list** (various forms)
   - **Context Detection**: Checks if called from outside plugin
   - **Navigation**: 
     - Context actions: `endOfDirectory(succeeded=False)`
     - Plugin actions: Standard response handling

2. **remove_from_list** (various forms)
   - **Handler**: `lists_handler.remove_from_list()`
   - **Navigation**: Success triggers container refresh

#### Tools Actions
1. **show_list_tools** (`action=show_list_tools`)
   - **Session State**: Stores return location
   - **Handler**: `tools_handler.show_list_tools()`
   - **Navigation**: 
     - Settings operations: Skip endOfDirectory
     - Other operations: `endOfDirectory(succeeded=True)`

#### No-Op Actions
1. **noop** (`action=noop`)
   - **Purpose**: Safe directory ending
   - **endOfDirectory**: `succeeded=True` with no items

### Error Handling Navigation
- **Failed Actions**: `endOfDirectory(addon_handle, succeeded=False)`
- **Missing Parameters**: `endOfDirectory(addon_handle, succeeded=False)`
- **Exceptions**: Error notification + `endOfDirectory(succeeded=False)`

## 5. Centralized Navigation System (NEW)

### Navigator Class - Centralized Container Mutations
**File**: `lib/ui/nav.py`

The `Navigator` class provides a centralized API for managing all Kodi container mutations (PUSH / REPLACE / REFRESH) and endOfDirectory calls. This consolidates navigation logic that was previously scattered throughout the codebase.

#### Core Navigation Methods

```python
class Navigator:
    def push(self, url: str) -> None:
        """Navigate to URL by pushing to navigation stack"""
        xbmc.executebuiltin(f'Container.Update("{url}")')

    def replace(self, url: str) -> None:
        """Navigate to URL by replacing current location"""  
        xbmc.executebuiltin(f'Container.Update("{url}", replace)')

    def refresh(self) -> None:
        """Refresh current container"""
        xbmc.executebuiltin('Container.Refresh')

    def finish_directory(self, handle: int, succeeded: bool = True, update: bool = False) -> None:
        """End directory with consistent parameters"""
        xbmcplugin.endOfDirectory(handle, succeeded=succeeded, updateListing=update, cacheToDisc=False)
```

**Key Benefits**:
- **Centralized Logging**: All navigation actions logged with consistent format
- **Consistent Parameters**: `cacheToDisc=False` enforced for dynamic content
- **Single Point of Control**: All container mutations go through Navigator instance

#### Navigation Intent System

```python
def execute_intent(self, intent) -> None:
    """Execute a NavigationIntent"""
    if intent.mode == 'push':
        self.push(intent.url)
    elif intent.mode == 'replace':
        self.replace(intent.url)
    elif intent.mode == 'refresh':
        self.refresh()
```

**NavigationIntent Integration**:
- Response handlers generate `NavigationIntent` objects
- Navigator executes intents consistently
- Supports `push`, `replace`, `refresh`, and `None` modes

### Navigation Policy - Smart PUSH vs REPLACE Decisions
**File**: `lib/ui/nav_policy.py`

The `NavigationPolicy` class implements intelligent logic for deciding between PUSH and REPLACE navigation modes based on route transitions and context.

#### Decision Rules

```python
def decide_mode(current_route, next_route, reason, current_params, next_params) -> 'push'|'replace':
    """
    Rules:
    - Different logical page (route or id changes) → PUSH
    - Same page morph (sort/filter/pagination>1) → REPLACE
    """
```

#### Navigation Scenarios

| Scenario | Action | Mode | Rationale |
|---|---|---|---|
| Different actions | `show_list` → `show_folder` | **PUSH** | New logical page |
| Same action, different ID | `show_list&id=1` → `show_list&id=2` | **PUSH** | Different content |
| Sort/filter change | `show_list&sort=name` → `show_list&sort=date` | **REPLACE** | Same page morph |
| Pagination (page > 1) | `show_list&page=1` → `show_list&page=2` | **REPLACE** | Continuation |
| Initial navigation | No current route | **PUSH** | Starting point |

#### Smart Router Integration

```python
def _navigate_smart(self, next_route: str, reason: str = "navigation", next_params: Dict = None):
    """Navigate using navigation policy to determine push vs replace"""
    current_route, current_params = self._get_current_route_info()
    mode = decide_mode(current_route, next_route, reason, current_params, next_params)
    
    navigator = get_navigator()
    if mode == 'push':
        navigator.push(next_route)
    else:  # replace
        navigator.replace(next_route)
```

### Global Navigator Access

```python
# Singleton pattern for consistent access
def get_navigator() -> Navigator:
    """Get global navigator instance"""
    global _navigator_instance
    if _navigator_instance is None:
        _navigator_instance = Navigator()
    return _navigator_instance
```

**Usage Throughout Codebase**:
- `response_handler.py`: Uses Navigator for directory completion
- `router.py`: Uses Navigator for smart navigation
- All handlers: Access via `get_navigator()` for consistent behavior

## 6. Container Management (response_handler.py) - UPDATED

### DirectoryResponse Handling (UPDATED)
**Function**: `handle_directory_response(response, context)`

Now uses the centralized Navigator for consistent endOfDirectory handling:

```python
# End directory using Navigator instead of direct xbmcplugin call
# Navigator always uses cacheToDisc=False for dynamic content
self.navigator.finish_directory(
    context.addon_handle,
    succeeded=bool(kodi_params.get('succeeded', True)),
    update=bool(kodi_params.get('updateListing', False))
)

# Execute NavigationIntent if present
if response.intent:
    self.navigator.execute_intent(response.intent)
```

**Key Changes**:
- **Navigator Integration**: All endOfDirectory calls go through `navigator.finish_directory()`
- **NavigationIntent Support**: Automatic execution of navigation intents from responses
- **Consistent Parameters**: `cacheToDisc=False` enforced automatically for dynamic content

### DialogResponse Handling (UPDATED)
**Function**: `handle_dialog_response(response, context)`

Now uses centralized Navigator for all container mutations:

#### Navigation Priority Order:
1. **navigate_to_folder** → `navigator.replace(folder_url)` with cache-busting
2. **navigate_to_lists** → `navigator.replace(lists_url)` with cache-busting  
3. **navigate_to_main** → `navigator.replace(main_url)` with cache-busting
4. **navigate_to_favorites** → `navigator.replace(favorites_url)` with cache-busting
5. **refresh_needed** → `navigator.refresh()`

**Updated Implementation**:
```python
# Legacy navigation flags (for backward compatibility)
if response.navigate_to_folder:
    session_state.bump_refresh_token()
    folder_url = context.build_cache_busted_url("show_folder", folder_id=folder_id)
    self.navigator.replace(folder_url)
    
elif response.refresh_needed:
    self.navigator.refresh()
```

#### Cache-Busting
- **Session Token**: Bumped for main/favorites navigation
- **URL Modification**: `build_cache_busted_url()` adds refresh token

### Container.Refresh Usage (UPDATED)
**Triggers**:
- After successful list/folder operations
- When `refresh_needed = True` in response
- Tools return location with forced refresh

**Updated Implementation** (via Navigator):
```python
navigator = get_navigator()
navigator.refresh()
```

### Container.Update Usage (UPDATED)
**Triggers**:
- Navigation to specific locations (PUSH vs REPLACE determined by NavigationPolicy)
- After successful operations requiring navigation change
- Return from tools operations

**Updated Implementation** (via Navigator with smart mode detection):
```python
navigator = get_navigator()
# Smart navigation using NavigationPolicy
navigator.push(url)      # For new logical pages
navigator.replace(url)   # For same-page morphs (sort/filter/pagination)
```

**NavigationIntent Integration**:
```python
# Modern approach using NavigationIntent
intent = NavigationIntent(mode='push', url=url)
navigator.execute_intent(intent)
```

## 7. Pagination and Update Listing

### Pagination Control
**File**: `lib/ui/listitem_builder.py`

```python
current_page = int(self.context.get_param('page', '1'))
update_listing = current_page > 1  # Replace current listing for page 2+
xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=update_listing)
```

### List Rendering
**Files**: `lib/ui/listitem_renderer.py`

```python
# Lists rendering
xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)

# Folders rendering  
xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=True, cacheToDisc=False)
```

## 8. Special Navigation Cases

### Library Item Playback
**Function**: `handle_on_select()` in `plugin.py`
- **Action**: Direct playback via `PlayMedia(videodb://...)`
- **endOfDirectory**: `succeeded=False` (no directory to render)

### Fresh Install Setup
**Function**: `_check_and_handle_fresh_install()`
- **Navigation**: Setup dialogs, then continue to main menu
- **Container**: No impact on container state

### Settings Operations
- **Settings Menu**: `addon.openSettings()` - no container impact
- **Manual Backup**: Dialog-based, `endOfDirectory(succeeded=False)`
- **Import Operations**: Progress dialogs, no container navigation

## 9. Context Action Navigation Summary

| Context Action | Entry Point | Container Refresh | Container Update | endOfDirectory |
|---|---|---|---|---|
| LG Quick Add | context.py | Yes (success) | No | Context: succeeded=False |
| LG Add to List | context.py | Yes (if in list) | Yes (to list) | Plugin: standard |
| LG Remove from List | context.py | Yes | No | updateListing=True |
| List Rename | ListItem context | Yes | No | succeeded=True |
| List Delete | ListItem context | Yes | No | succeeded=True |
| Folder Operations | ListItem context | Yes | No | succeeded=True |
| Search Actions | Context submenu | No | Yes (to results) | succeeded=True |
| External Add | External context | Yes (if successful) | Optional | Context: succeeded=False |

## 10. Navigation Flow Patterns (UPDATED)

### Standard Directory Navigation (UPDATED)
1. **Action Triggered** → Router dispatch
2. **Handler Execution** → Business logic
3. **Response Generation** → Success/failure + NavigationIntent
4. **Response Handler** → Uses Navigator for container management
5. **Navigator.finish_directory()** → Centralized directory completion
6. **Navigator.execute_intent()** → Centralized container mutations (PUSH/REPLACE/REFRESH)

### Context Action Flow
1. **Context Menu Selection** → context.py
2. **Context Detection** → Determine item type/location
3. **Plugin URL Generation** → RunPlugin(...) call
4. **Router Dispatch** → Route to appropriate handler
5. **Context Check** → Is this from outside plugin?
6. **Action Execution** → Perform operation
7. **Navigation Decision** → Refresh vs Update vs None

### Dialog-Based Operations
1. **User Interaction** → Show dialog/progress
2. **Operation Execution** → Perform background work
3. **Result Processing** → Success/failure determination
4. **Navigation Response** → refresh_needed/navigate_to flags
5. **Container Management** → Refresh or navigate as appropriate

## 11. Centralized Navigation Benefits

The new Navigator system provides several key improvements over the previous scattered navigation approach:

### **Consistency**
- All endOfDirectory calls use consistent parameters (`cacheToDisc=False`)
- Standardized logging format for all navigation actions
- Single point of control for container behavior modifications

### **Intelligence** 
- NavigationPolicy automatically determines PUSH vs REPLACE semantics
- Smart decisions based on route transitions and user context
- Eliminates manual navigation mode decisions throughout handlers

### **Maintainability**
- Centralized container mutation logic in `lib/ui/nav.py`
- NavigationIntent system for declarative navigation
- Easy to modify navigation behavior globally

### **Debugging**
- All navigation actions logged with consistent prefixes ("NAVIGATOR:", "NAV POLICY:")
- Clear visibility into navigation decision-making process
- Simplified troubleshooting of navigation issues

---

This guide covers all navigation patterns and context actions in the LibraryGenie addon, including the new centralized Navigation helper that consolidates all container mutations (PUSH / REPLACE / REFRESH) and endOfDirectory calls, providing intelligent navigation decisions and consistent behavior throughout the application.