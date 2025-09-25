# LibraryGenie Navigation and Context Action Guide

## Overview
This document provides a complete analysis of all navigation patterns, context actions, and container management behaviors in the LibraryGenie Kodi addon.

## Recent Navigation Fix (September 2025)
**Issue Resolved**: Fixed critical navigation bug where users could exit the plugin when using ".." (parent directory) navigation, taking them to Kodi's default directory instead of staying within LibraryGenie.

**Root Cause**: The NavigationPolicy was defaulting to REPLACE navigation for most in-plugin transitions, which broke Kodi's internal navigation stack. When users reached the plugin root and clicked "..", Kodi had no plugin-internal parent to navigate to.

**Solution Implemented**: 
- Modified NavigationPolicy in `lib/ui/nav_policy.py` to default to PUSH navigation for in-plugin transitions
- Reserved REPLACE navigation only for true page morphs (explicit sort/filter/pagination changes)
- This maintains Kodi's built-in navigation stack, ensuring ".." works correctly within plugin boundaries

**Technical Details**:
- Changed `_is_page_morph()` default from `return True` (REPLACE) to `return False` (PUSH)
- Enhanced list navigation logic to require explicit morph parameters for REPLACE behavior
- Users can now navigate deep into plugin hierarchy and use ".." to go back through their navigation history without exiting the plugin

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

## 4. Router System (router.py) - UPDATED

### Modern Router Architecture

The `Router` class provides a modular, handler-based architecture that dispatches actions to specialized handlers using lazy loading and smart navigation.

#### Core Router Components

```python
class Router:
    """Routes actions to appropriate handler functions"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}  # Action registry
    
    def register_handler(self, action: str, handler: Callable):
        """Register a handler function for an action"""
        self._handlers[action] = handler
    
    def dispatch(self, context: PluginContext) -> bool:
        """Dispatch request to appropriate handler based on context"""
```

#### Handler Factory Integration

**File**: `lib/ui/handler_factory.py`

The router uses a `HandlerFactory` for lazy loading of handler instances:

```python
class HandlerFactory:
    """Factory class for lazy handler instantiation"""
    
    def get_lists_handler(self):
        """Get lists handler instance (lazy loaded)"""
        if 'lists' not in self._handler_cache:
            from lib.ui.lists_handler import ListsHandler
            self._handler_cache['lists'] = ListsHandler(self.context)
        return self._handler_cache['lists']
```

**Benefits**:
- **Performance**: Handlers only loaded when first used
- **Memory Efficiency**: Unused handlers not instantiated
- **Caching**: Handler instances reused across requests

#### Smart Navigation Integration

**Current Route Detection**:
```python
def _get_current_route_info(self):
    """Get current route information for navigation decisions"""
    current_path = xbmc.getInfoLabel('Container.FolderPath')
    # Parse action and parameters from current path
    return current_route, current_params
```

**Smart Navigation**:
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

#### Router-Managed Actions (Built-in Handlers)

The router directly handles these critical actions without requiring separate handler registration:

##### 1. Lists and Folders
- **`lists` / `show_lists_menu`**: Main lists directory via factory
- **`show_list` / `view_list`**: List contents with Kodi Favorites special handling
- **`show_folder`**: Folder contents display
- **`delete_folder`**: Folder deletion with auto-refresh
- **`rename_folder`**: Folder renaming with auto-refresh  
- **`move_folder`**: Folder moving with auto-refresh

##### 2. Tools and Options System
- **`show_list_tools`**: Centralized tools menu with session state management
- **`restore_backup`**: Backup restoration handling
- **`activate_ai_search`**: AI search activation workflow

##### 3. List Management
- **`add_to_list`**: Multi-variant adding (media items, library items, external items)
- **`remove_from_list`**: Item removal from lists  
- **`quick_add*`**: Quick add variants with context detection

##### 4. Search Operations
- **`prompt_and_search`**: Search prompt and results display
- **`show_search_history`**: Search history folder access
- **`find_similar_movies`**: AI-powered similarity search

##### 5. Special Actions
- **`noop`**: Safe no-operation for directory ending
- **AI Search**: Various AI search sync and authorization actions

#### Context Action Detection

**External vs Plugin Context**:
```python
# Check if this is a context action (called from outside the plugin)
container_path = xbmc.getInfoLabel('Container.FolderPath')
is_context_action = not container_path or 'plugin.video.librarygenie' not in container_path
```

**Context-Specific Handling**:
- **Context Actions**: No `endOfDirectory` call, use NavigationIntents
- **Plugin Actions**: Standard directory completion via Navigator
- **Settings Operations**: Skip `endOfDirectory` to prevent empty directory flash

#### Breadcrumb Context Generation

**Performance-Optimized**:
```python
# Generate breadcrumb context for navigation (skip for Tools & Options for performance)
if action != "show_list_tools":
    breadcrumb_helper = get_breadcrumb_helper()
    breadcrumb_path = breadcrumb_helper.get_breadcrumb_for_action(action, params, context.query_manager)
    context.breadcrumb_path = breadcrumb_path
else:
    # Tools & Options don't need breadcrumbs - skip for performance
    context.breadcrumb_path = None
```

#### Response Handler Integration

**Consistent Response Processing**:
```python
# Modern pattern using response handlers
from lib.ui.response_handler import get_response_handler
response_handler = get_response_handler()
response = lists_handler.view_list(context, list_id)
return response_handler.handle_directory_response(response, context)
```

**Benefits**:
- **Standardized**: All responses processed through common handler
- **NavigationIntent Support**: Automatic intent execution
- **Error Handling**: Consistent error response patterns

#### Session State Management

**Tools Return Location**:
```python
# Store current location for returning after tools operations
current_path = xbmc.getInfoLabel('Container.FolderPath')
session_state = get_session_state()
session_state.set_tools_return_location(current_path)
```

#### Error Handling Patterns

**Modern Error Handling**:
- **Missing Parameters**: `xbmcplugin.endOfDirectory(context.addon_handle, succeeded=False)`
- **Handler Exceptions**: Logged with context, graceful fallback
- **Factory Failures**: Lazy loading prevents startup crashes
- **Navigation Errors**: Smart navigation with push fallback

## 5. Tools & Options Modal System (NEW)

### Overview

The Tools & Options system provides context-aware modal dialogs for list and folder management operations. It uses a provider-based architecture to deliver relevant tools based on the user's current location within the addon.

**File**: `lib/ui/tools_menu/service.py`

### Core Architecture

#### ToolsMenuService - Central Orchestrator

```python
class ToolsMenuService:
    """Centralized service for building and displaying tools & options modals"""
    
    def register_provider(self, context_type: str, provider: Any) -> None:
        """Register a tools provider for a context type"""
        self._providers[context_type] = provider
    
    def build_menu(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build menu actions for the given context"""
        provider = self._providers.get(context.list_type)
        return provider.build_tools(context, plugin_context)
    
    def show_menu(self, title: str, actions: List[ToolAction], plugin_context: Any) -> DialogResponse:
        """Show tools menu and handle user selection"""
```

### Context System

#### ToolsContext - Context Definition

**File**: `lib/ui/tools_menu/types.py`

```python
@dataclass 
class ToolsContext:
    """Context information for tools menu"""
    list_type: Literal["favorites", "user_list", "folder", "lists_main"]
    list_id: Optional[str] = None
    folder_id: Optional[str] = None
    
    def get_context_key(self) -> str:
        """Get unique key for this context"""
```

#### ToolAction - Individual Tool Definition

```python
@dataclass
class ToolAction:
    """Definition of a tool action"""
    id: str
    label: str
    icon: Optional[str] = None
    enabled: bool = True
    visible: bool = True
    needs_confirmation: Optional[ConfirmSpec] = None
    handler: Optional[ToolHandler] = None
    payload: Optional[Dict[str, Any]] = None
```

### Provider System

#### BaseToolsProvider - Abstract Provider

**File**: `lib/ui/tools_menu/providers/base_provider.py`

```python
class BaseToolsProvider(ABC):
    """Base class for all tools providers"""
    
    @abstractmethod
    def build_tools(self, context: ToolsContext, plugin_context: Any) -> List[ToolAction]:
        """Build list of tool actions for the given context"""
        
    def _create_action(self, action_id: str, label: str, handler: Any, 
                      payload: dict = None, needs_confirmation=None) -> ToolAction:
        """Helper to create ToolAction with standard defaults"""
```

#### Context-Specific Providers

##### 1. UserListToolsProvider
**Context**: `user_list` - Individual user lists
**File**: `lib/ui/tools_menu/providers/user_list_provider.py`

**Actions Available**:
- **Standard Lists**: Rename, Export, Delete, Move to Folder
- **Search History Lists**: Move to New List, Export, Delete (with confirmation)
- **Kodi Favorites**: Save As New List, Export (read-only list)

**Special Handling**:
```python
# Context-specific tools based on list type
is_search_history = list_info.get('folder_name') == 'Search History'
is_kodi_favorites = list_info.get('name') == 'Kodi Favorites'
```

##### 2. FolderToolsProvider
**Context**: `folder` - Folder management
**File**: `lib/ui/tools_menu/providers/folder_provider.py`

**Actions Available**:
- **Standard Folders**: Create List, Create Subfolder, Rename, Delete, Move, Export
- **Reserved Folders (Search History)**: Export All Lists, Clear Search History

**Reserved Folder Detection**:
```python
is_reserved = folder_info.get('is_reserved', False)
# Limited operations for Search History folder
```

##### 3. FavoritesToolsProvider
**Context**: `favorites` - Kodi Favorites management
**File**: `lib/ui/tools_menu/providers/favorites_provider.py`

**Actions Available**:
- **Scan Favorites**: Update from Kodi database
- **Save As New List**: Convert favorites to LibraryGenie list

##### 4. ListsMainToolsProvider
**Context**: `lists_main` - Main menu administrative tools
**File**: `lib/ui/tools_menu/providers/lists_main_provider.py`

**Actions Available**:
- **Search Operations**: Local Movie Search, AI Movie Search, Local Episodes Search, Search History
- **Creation Operations**: Create New List, Create New Folder
- **Import/Export**: Import Lists from File, Export All Lists
- **Administrative**: Manual Backup, Restore Backup, Settings

### Dialog System Integration

#### DialogAdapter - Type-Safe Dialog Wrapper

**File**: `lib/ui/tools_menu/types.py`

```python
class DialogAdapter:
    """Type-safe wrapper around xbmcgui.Dialog with proper error handling"""
    
    def select(self, title: str, options: Sequence[Union[str, xbmcgui.ListItem]]) -> int:
        """Show selection dialog with type-safe parameters"""
        
    def yesno(self, title: str, message: str, yes_label=None, no_label=None) -> bool:
        """Show yes/no confirmation dialog"""
        
    def input(self, title: str, default="", input_type=xbmcgui.INPUT_ALPHANUM) -> Optional[str]:
        """Show input dialog"""
        
    def notification(self, title: str, message: str, icon="info", time_ms=5000) -> None:
        """Show notification to user"""
```

#### Confirmation System

```python
@dataclass
class ConfirmSpec:
    """Specification for confirmation dialogs"""
    title: str
    message: str
    confirm_label: Optional[str] = None
    cancel_label: Optional[str] = None
```

**Usage in Tools**:
```python
self._create_action(
    action_id="delete_list",
    label=L(36055).replace('%s', short_name),  # "Delete %s"
    handler=self._handle_delete_list,
    payload={"list_id": context.list_id},
    needs_confirmation=ConfirmSpec(
        title="Confirm Delete",
        message=f"Delete list '{list_name}'?"
    )
)
```

### Navigation Integration

#### Router Integration

**Tools Menu Trigger**: `action=show_list_tools`

```python
# Router directly handles tools menu
elif action == "show_list_tools":
    # Store current location for returning after tools operations
    current_path = xbmc.getInfoLabel('Container.FolderPath')
    session_state.set_tools_return_location(current_path)
    
    tools_handler = factory.get_tools_handler()
    result = tools_handler.show_list_tools(context, list_type, list_id)
    
    # Use response handler to process the result
    response_handler.handle_dialog_response(result, context)
```

#### Session State Management

**Return Location Tracking**:
- Current container path stored before showing tools
- Used to restore user location after tools operation
- Enables seamless navigation back to original context

#### NavigationIntent Integration

**Tools operations generate NavigationIntents**:
- **Success Operations**: May include `navigate_to_folder`, `navigate_to_lists`, or `refresh_needed`
- **No-Change Operations**: Return to previous location via session state
- **Settings Operations**: Skip `endOfDirectory` to prevent empty directory flash

### Benefits of Provider Architecture

1. **Context-Aware**: Tools automatically adapt to current user location
2. **Extensible**: New providers easily added for new context types  
3. **Consistent**: Uniform dialog patterns across all tools
4. **Type-Safe**: DialogAdapter prevents common dialog errors
5. **Maintainable**: Each provider encapsulates its specific logic
6. **Performance**: Lazy loading and context filtering reduce overhead

## 6. Info Hijack System (NEW)

### Overview

The Info Hijack System intercepts Kodi info dialogs for plugin-sourced media to provide native Kodi library dialogs with full metadata, artwork, and functionality. This creates a seamless integration between LibraryGenie content and Kodi's native interface.

**Files**: 
- `lib/ui/info_hijack_manager.py` - Main controller
- `lib/ui/info_hijack_helpers.py` - XSP generation and dialog utilities

### Core Architecture

#### InfoHijackManager - Main Controller

```python
class InfoHijackManager:
    """
    Redesigned hijack manager that separates native info opening from directory rebuild.
    
    Flow:
    1. When tagged item detected -> save return target and open native info immediately
    2. When native info closes -> restore container to original plugin path
    """
```

**State Tracking**:
- **Dialog State**: Monitors `DialogVideoInfo.xml` activation/deactivation
- **Hijack Progress**: Prevents re-entry during active hijack operations
- **XSP Monitoring**: Tracks temporary XSP files and auto-navigation
- **Cooldown Management**: Prevents spam hijacking with adaptive timing

### 5-Step Hijack Process

The system follows a precise 5-step process to seamlessly replace plugin info dialogs with native Kodi dialogs:

#### Step 1: 💾 Trust Kodi Navigation
```python
# STEP 1: TRUST KODI NAVIGATION HISTORY
log("HIJACK STEP 1: Using Kodi's navigation history (no saving needed)")
log("HIJACK STEP 1 COMPLETE: Navigation history will handle return")
```
- **Purpose**: Rely on Kodi's built-in navigation stack
- **Benefit**: Eliminates need for manual path saving
- **Navigation**: Uses Kodi's back navigation for seamless return

#### Step 2: 🚪 Close Current Dialog
```python
# STEP 2: CLOSE CURRENT DIALOG
log("HIJACK STEP 2: CLOSING CURRENT DIALOG")
if not close_video_info_dialog(self._logger, timeout=1.0):
    log_error("❌ HIJACK STEP 2 FAILED: Could not close dialog - ActivateWindow will be refused")
    return  # Abort early to prevent ActivateWindow refusal
```
- **Purpose**: Close plugin info dialog to prepare for native dialog
- **Method**: Uses `xbmc.executebuiltin('Action(Back)')` with timeout
- **Safety**: Aborts hijack if dialog cannot be closed (prevents ActivateWindow refusal)

#### Step 3: 🚀 Open Native Info via XSP
```python
# STEP 3: OPEN NATIVE INFO VIA XSP
self._logger.debug("HIJACK STEP 3: OPENING NATIVE INFO for %s %s", dbtype, dbid_int)
ok = open_native_info_fast(dbtype, dbid_int, self._logger)
```
- **XSP Generation**: Creates temporary smart playlist targeting specific DBID
- **Navigation**: Opens XSP in native library view
- **Timing**: Optimized for fast execution with minimal UI disruption

#### Step 4: 📺 Native Dialog Opens
- **Result**: User sees full native Kodi info dialog
- **Features**: Complete metadata, artwork, play options, library integration
- **State**: `_native_info_was_open = True` for close detection

#### Step 5: 🔄 Double-Back Navigation
```python
# PRIMARY DETECTION: dialog was active, now not active, and we had a native info open
if last_active and not dialog_active and self._native_info_was_open:
    log("HIJACK STEP 5: DETECTED DIALOG CLOSE via state change - initiating navigation back to plugin")
    self._handle_native_info_closed()
```
- **Detection**: Monitors dialog state changes for close events
- **Restoration**: Returns user to original plugin location
- **Cleanup**: Removes temporary XSP files and resets state

### XSP (Smart Playlist) System

#### XSP File Structure

**Movie XSP Example**:
```xml
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

#### XSP Creation Process

**Dynamic Generation**:
```python
def create_movie_xsp(dbid: int, title: str) -> str:
    """Create XSP file for movie with specific DBID"""
    # Generate unique filename with timestamp
    # Create XML content targeting specific movie
    # Write to hijack directory
    # Return file path for navigation
```

**File Management**:
- **Location**: `special://profile/addon_data/plugin.video.librarygenie/hijack/`
- **Naming**: `hijack_movie_{dbid}_{timestamp}.xsp`
- **Lifecycle**: Created on hijack, cleaned up after use
- **Safety**: Multiple XSP files supported for concurrent users

### Dialog State Monitoring

#### Advanced State Detection

```python
def tick(self):
    """Main monitoring loop with dual detection system"""
    dialog_active = xbmc.getCondVisibility('Window.IsActive(DialogVideoInfo.xml)')
    current_dialog_id = xbmcgui.getCurrentWindowDialogId()
    
    # PRIMARY DETECTION: State change monitoring
    if last_active and not dialog_active and self._native_info_was_open:
        self._handle_native_info_closed()
    
    # SECONDARY DETECTION: Fallback for missed changes
    if not dialog_active and self._native_info_was_open:
        self._handle_native_info_closed()  # Fallback
```

**Monitoring Features**:
- **Dual Detection**: Primary state change + fallback detection
- **Adaptive Polling**: Optimized polling intervals for performance
- **State Persistence**: Tracks last known dialog state across ticks
- **Spam Prevention**: Cooldown periods and attempt counters

### Armed Item Detection

#### Item Tagging System

```python
# Items are "armed" by setting ListItem properties
list_item.setProperty('LG.InfoHijack.Armed', '1')
list_item.setProperty('LG.InfoHijack.DBID', str(dbid))
list_item.setProperty('LG.InfoHijack.DBType', dbtype)
```

**Armed Detection**:
```python
def _collect_hijack_properties_batch(self) -> dict:
    """Batch collect all hijack properties for performance"""
    return {
        'armed': get_cached_info('ListItem.Property(LG.InfoHijack.Armed)') == '1',
        'dbid': get_cached_info('ListItem.Property(LG.InfoHijack.DBID)'),
        'dbtype': get_cached_info('ListItem.Property(LG.InfoHijack.DBType)'),
        'label': get_cached_info('ListItem.Label')
    }
```

### Navigation Integration

#### Container Restoration

**XSP Auto-Navigation Monitoring**:
```python
def _monitor_and_handle_xsp_appearance(self, current_time: float):
    """Monitor for user landing on LibraryGenie XSP pages and navigate back"""
    if time.time() < self._hijack_monitoring_expires:
        container_path = get_cached_info('Container.FolderPath')
        if self._is_hijack_xsp_path(container_path):
            # User landed on our XSP - navigate back immediately
            restore_container_after_close()
```

**Back Navigation**:
- **Detection**: Monitors for XSP container paths
- **Action**: Issues `xbmc.executebuiltin('Action(Back)')` to return to plugin
- **Timing**: 120-second monitoring window after hijack
- **Safety**: Multiple back navigation attempts with exponential backoff

### Performance Optimizations

#### Caching and Efficiency

**Navigation Cache Integration**:
```python
from lib.ui.navigation_cache import get_cached_info, navigation_action

# Cached info retrieval reduces Kodi API calls
container_path = get_cached_info('Container.FolderPath')
listitem_label = get_cached_info('ListItem.Label')
```

**Batch Property Collection**:
- **Single API Call**: Collect all hijack properties at once
- **Performance**: Reduces API overhead during dialog detection
- **Efficiency**: Optimized for low-power devices

#### Anti-Spam Mechanisms

**Cooldown System**:
```python
# Set cooldown based on operation time
operation_time = time.time() - current_time
self._cooldown_until = time.time() + max(0.5, operation_time * 2)
```

**Rate Limiting**:
- **Dialog Detection**: Prevent duplicate hijack attempts
- **Logging**: Reduced frequency debug logging (every 10 seconds)
- **Container Scanning**: Periodic armed item detection (every 2.5 seconds)

### Error Handling and Recovery

#### Graceful Degradation

**Hijack Failure Recovery**:
```python
try:
    ok = open_native_info_fast(dbtype, dbid_int, self._logger)
    if ok:
        # Success path
        self._native_info_was_open = True
    else:
        # Failed to open native dialog - graceful degradation
        log_error("❌ HIJACK STEP 3 FAILED: Failed to open native info")
except Exception as e:
    log_error("HIJACK: 💥 Exception during hijack: %s", e)
finally:
    self._in_progress = False
```

**Safety Mechanisms**:
- **Exception Handling**: Full try/catch with detailed logging
- **State Reset**: Always reset `_in_progress` flag in finally blocks
- **Timeout Protection**: Dialog close operations with configurable timeouts
- **Abort Conditions**: Early exit when preconditions not met

### Benefits of Info Hijack System

1. **Native Integration**: Full Kodi library features (play options, artwork, metadata)
2. **Seamless UX**: Transparent transition between plugin and native dialogs  
3. **Performance**: Optimized caching and batch operations
4. **Reliability**: Dual detection system with fallback mechanisms
5. **Maintainability**: Clear separation between hijack controller and helpers
6. **Extensibility**: XSP system supports movies, episodes, and future media types

## 7. Centralized Navigation System

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

## 8. Response Handler System (UPDATED)

### Overview

The `ResponseHandler` class standardizes processing of `DialogResponse` and `DirectoryResponse` objects, providing consistent user feedback, navigation management, and directory completion throughout the addon.

**File**: `lib/ui/response_handler.py`

### Core Architecture

```python
class ResponseHandler:
    """Handles standardized processing of response types"""
    
    def __init__(self):
        self.navigator = get_navigator()  # Centralized navigation
    
    def handle_dialog_response(self, response: DialogResponse, context: PluginContext) -> None:
        """Handle DialogResponse by showing messages and performing actions"""
    
    def handle_directory_response(self, response: DirectoryResponse, context: PluginContext) -> bool:
        """Handle DirectoryResponse with proper directory completion"""
```

### DialogResponse Processing (UPDATED)

#### User Notification System

**Success/Error Notifications**:
```python
if response.message:
    if response.success:
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            response.message,
            xbmcgui.NOTIFICATION_INFO,
            3000  # 3 second timeout
        )
    else:
        xbmcgui.Dialog().notification(
            "LibraryGenie", 
            response.message,
            xbmcgui.NOTIFICATION_ERROR,
            5000  # 5 second timeout for errors
        )
```

**Notification Features**:
- **Success**: Green notification, 3-second display
- **Error**: Red notification, 5-second display  
- **Automatic**: Based on `response.success` flag
- **Fallback**: Generic error notification if processing fails

#### Navigation Management (UPDATED)

**Navigation Priority Hierarchy**:
1. **NavigationIntent** (modern approach)
2. **Legacy Navigation Flags** (backward compatibility)
3. **Failure Navigation** (error handling)

#### Legacy Navigation Flags Support

**Priority Order for Success Responses**:
```python
if response.success:
    # 1. Folder navigation (highest priority)
    if getattr(response, 'navigate_to_folder', None):
        session_state.bump_refresh_token()
        folder_url = context.build_cache_busted_url("show_folder", folder_id=folder_id)
        self.navigator.replace(folder_url)
        return
        
    # 2. Lists navigation
    elif getattr(response, 'navigate_to_lists', None):
        session_state.bump_refresh_token()
        lists_url = context.build_cache_busted_url("lists")
        self.navigator.replace(lists_url)
        return
        
    # 3. Main menu navigation
    elif getattr(response, 'navigate_to_main', None):
        session_state.bump_refresh_token()
        main_url = context.build_cache_busted_url("main_menu")
        self.navigator.replace(main_url)
        return
        
    # 4. Favorites navigation
    elif getattr(response, 'navigate_to_favorites', None):
        session_state.bump_refresh_token()
        favorites_url = context.build_cache_busted_url("kodi_favorites")
        self.navigator.replace(favorites_url)
        return
        
    # 5. Refresh current location
    elif getattr(response, 'refresh_needed', None):
        # Handle tools return location
        tools_return_location = session_state.get_tools_return_location()
        if tools_return_location and 'show_list_tools' in current_path:
            self.navigator.replace(tools_return_location)
            session_state.clear_tools_return_location()
            xbmc.sleep(100)  # Allow update
            self.navigator.refresh()
        else:
            self.navigator.refresh()
```

#### Cache-Busting System

**Session State Integration**:
```python
from lib.ui.session_state import get_session_state

session_state = get_session_state()
session_state.bump_refresh_token()  # Increment cache-busting token
cache_busted_url = context.build_cache_busted_url(action, **params)
```

**Benefits**:
- **Cache Prevention**: Ensures fresh data loading
- **UI Consistency**: Prevents stale content display
- **Session Management**: Token-based cache invalidation

#### Tools Return Location Management

**Session State Storage**:
```python
# Storing location before tools (in router.py)
current_path = xbmc.getInfoLabel('Container.FolderPath')
session_state.set_tools_return_location(current_path)

# Returning after tools operation
if tools_return_location and 'show_list_tools' in current_path:
    self.navigator.replace(tools_return_location)
    session_state.clear_tools_return_location()
```

**Tools Navigation Flow**:
1. **Store Location**: Current path saved before showing tools
2. **Tools Operation**: User performs action in tools modal
3. **Return Navigation**: Seamless return to original location
4. **State Cleanup**: Clear stored location after use

#### Failure Navigation Handling

**Navigate on Failure**:
```python
else:  # response.success == False
    navigate_on_failure = getattr(response, 'navigate_on_failure', None)
    if navigate_on_failure == 'return_to_tools_location':
        tools_return_url = session_state.get_tools_return_location()
        if tools_return_url:
            self.navigator.replace(tools_return_url)
            session_state.clear_tools_return_location()
```

**Failure Navigation Options**:
- **return_to_tools_location**: Navigate back to stored tools origin
- **None**: No navigation on failure (default)
- **Custom**: Extensible for future failure handling patterns

#### NavigationIntent Integration (Modern Approach)

**Intent Execution**:
```python
# Execute NavigationIntent if present (after legacy flags)
if response.intent:
    context.logger.debug("RESPONSE HANDLER: Executing NavigationIntent: %s", response.intent)
    self.navigator.execute_intent(response.intent)
```

**Intent Priority**:
- **Legacy flags take precedence** for backward compatibility
- **NavigationIntent executed last** if no legacy navigation occurred
- **Flexible**: Supports `push`, `replace`, `refresh` modes

### DirectoryResponse Processing (UPDATED)

#### Navigator Integration

**Directory Completion**:
```python
def handle_directory_response(self, response: DirectoryResponse, context: PluginContext) -> bool:
    """Handle DirectoryResponse with proper directory completion"""
    
    # Set content type if specified
    if hasattr(response, 'content_type') and response.content_type:
        import xbmcplugin
        xbmcplugin.setContent(context.addon_handle, response.content_type)
    
    # Get Kodi parameters from response
    kodi_params = response.to_kodi_params()
    
    # Handle sort methods separately
    sort_methods = kodi_params.get('sortMethods')
    if sort_methods:
        for sort_method in sort_methods:
            xbmcplugin.addSortMethod(context.addon_handle, sort_method)
    
    # End directory using Navigator instead of direct xbmcplugin call
    self.navigator.finish_directory(
        context.addon_handle,
        succeeded=bool(kodi_params.get('succeeded', True)),
        update=bool(kodi_params.get('updateListing', False))
    )
    
    # Execute NavigationIntent if present
    if response.intent:
        self.navigator.execute_intent(response.intent)
    
    return response.success
```

**Key Features**:
- **Navigator Integration**: All `endOfDirectory` calls go through centralized Navigator
- **Consistent Parameters**: `cacheToDisc=False` enforced automatically
- **Content Type Support**: Automatic content type setting for Kodi
- **Sort Methods**: Proper sort method registration
- **NavigationIntent Support**: Automatic execution after directory completion

#### Error Handling and Recovery

**Graceful Degradation**:
```python
try:
    # Main processing logic
    return self._process_directory_response(response, context)
except Exception as e:
    self.logger.error("Error handling directory response: %s", e)
    # Fallback directory ending using Navigator
    try:
        self.navigator.finish_directory(context.addon_handle, succeeded=False)
    except Exception:
        pass
    return False
```

**Recovery Mechanisms**:
- **Exception Handling**: Full try/catch with detailed logging
- **Fallback Directory**: Always attempt to end directory properly
- **Boolean Return**: Clear success/failure indication
- **No Crash**: Graceful degradation prevents addon crashes

### Response Handler Benefits

1. **Consistency**: Standardized processing across all response types
2. **User Feedback**: Automatic notification display based on response status
3. **Navigation Management**: Centralized navigation through Navigator integration
4. **Backward Compatibility**: Legacy navigation flags preserved alongside modern NavigationIntent
5. **Error Resilience**: Comprehensive error handling with graceful degradation
6. **Session Management**: Tools return location and cache-busting support

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