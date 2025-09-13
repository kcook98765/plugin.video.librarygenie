
# LibraryGenie Artwork & Icons Documentation

This document outlines the Kodi artwork system and available artwork options for LibraryGenie's directory entries and list items.

---

## Directory Entry Types in LibraryGenie

Based on the addon architecture, these are the main navigational directory entry types:

### 1. **Lists** (User-created lists)
- **Location**: `lib/ui/listitem_renderer.py` → `_build_list_item()`
- **Navigation**: `show_list` action
- **Purpose**: Display user-created movie/media lists
- **Current Art**: `DefaultFolder.png`

### 2. **Folders** (Hierarchical organization)
- **Location**: `lib/ui/listitem_renderer.py` → `_build_folder_item()`
- **Navigation**: `show_folder` action
- **Purpose**: Organize lists in folder structure
- **Current Art**: `DefaultFolder.png`

### 3. **Media Items** (Movies/Episodes)
- **Location**: `lib/ui/listitem_builder.py` → `_create_library_listitem()` and `_create_external_item()`
- **Navigation**: Direct playback or info display
- **Purpose**: Individual movie/episode entries
- **Current Art**: Database-driven (poster, fanart, thumb from media metadata)

### 4. **Action Items** (Menu actions/tools)
- **Location**: `lib/ui/listitem_builder.py` → `_create_action_item()`
- **Navigation**: Various actions (`scan_favorites`, `create_list`, etc.)
- **Purpose**: Trigger specific addon functions
- **Current Art**: `DefaultAddonService.png` (sync actions) or `DefaultFolder.png` (others)

### 5. **Main Menu Items**
- **Location**: `lib/ui/menu_builder.py` and `lib/ui/main_menu_handler.py`
- **Navigation**: Root level navigation
- **Purpose**: Top-level addon navigation
- **Current Art**: Varies by menu type

### 6. **Search Results**
- **Location**: `lib/ui/search_handler.py`
- **Navigation**: Display search results
- **Purpose**: Show filtered/searched content
- **Current Art**: Based on media type

### 7. **Favorites**
- **Location**: `lib/ui/favorites_handler.py`
- **Navigation**: `kodi_favorites` action
- **Purpose**: Display Kodi favorites integration
- **Current Art**: `DefaultShortcut.png` or media-specific

---

## Standard Kodi Icon Options

### **Folder & Directory Icons**
```python
'DefaultFolder.png'           # Standard folder icon (current default)
'DefaultFolderSquare.png'     # Square folder variant
'DefaultFolderBack.png'       # Back/up folder icon
'DefaultAddSource.png'        # Add/create actions
'DefaultHardDisk.png'         # Storage/backup related
```

### **Video & Media Icons**
```python
'DefaultVideo.png'            # Generic video file
'DefaultMovies.png'           # Movies category
'DefaultTVShows.png'          # TV Shows category
'DefaultEpisodes.png'         # Episodes
'DefaultSeason.png'           # TV Season
'DefaultRecentlyAdded.png'    # Recently added content
'DefaultInProgressShows.png'  # In-progress content
```

### **Action & Tool Icons**
```python
'DefaultAddonService.png'     # Service/sync operations (current for sync)
'DefaultAddonProgram.png'     # Program/tool actions
'DefaultAddonRepository.png'  # Repository/source actions
'DefaultAddonNone.png'        # Generic addon icon
'DefaultShortcut.png'         # Shortcuts/favorites (current for favorites)
'DefaultAddons.png'           # General addon icon
```

### **System & Utility Icons**
```python
'DefaultNetwork.png'          # Network operations
'DefaultUser.png'             # User-related actions
'DefaultPlaylist.png'         # Playlist/list operations
'DefaultTags.png'             # Tags/categories
'DefaultGenre.png'            # Genre-based content
'DefaultStudio.png'           # Studio-based content
'DefaultActor.png'            # Actor-based content
'DefaultDirector.png'         # Director-based content
'DefaultWriter.png'           # Writer-based content
'DefaultYear.png'             # Year-based content
```

### **Search & Filter Icons**
```python
'DefaultAddonsSearch.png'     # Search functionality
'DefaultAddonsLook.png'       # Browse/look functionality
'DefaultSearchNew.png'        # New search
'DefaultSearchHistory.png'    # Search history
'DefaultSearchClear.png'      # Clear/reset search
```

### **Special Purpose Icons**
```python
'DefaultVideoPlaylists.png'   # Video playlists
'DefaultMusicPlaylists.png'   # Music playlists
'DefaultSettings.png'         # Settings/configuration
'DefaultHelp.png'             # Help/documentation
'DefaultScript.png'           # Script/automation
'DefaultCountry.png'          # Country-based content
'DefaultMPAA.png'             # Rating-based content
```

---

## Kodi Art Dictionary System

When using `listitem.setArt()`, you can specify multiple art types:

### **Primary Artwork Keys**
```python
art_dict = {
    'icon': 'path_to_icon.png',           # List view icon (shown in lists)
    'thumb': 'path_to_thumbnail.jpg',     # Thumbnail image
    'poster': 'path_to_poster.jpg',       # Movie poster (primary for movies)
    'fanart': 'path_to_fanart.jpg',       # Background fanart
}
```

### **Additional Artwork Keys**
```python
art_dict = {
    'banner': 'path_to_banner.jpg',       # Wide banner image
    'landscape': 'path_to_landscape.jpg', # Landscape orientation
    'clearlogo': 'path_to_logo.png',      # Clear logo overlay
    'clearart': 'path_to_clearart.png',   # Clear art overlay
    'discart': 'path_to_disc.png',        # Disc artwork
    'characterart': 'path_to_char.png',   # Character artwork
    'keyart': 'path_to_key.png',          # Key artwork
    'tvshow.poster': 'path_to_show.jpg',  # TV show poster (for episodes)
    'season.poster': 'path_to_season.jpg' # Season poster (for episodes)
}
```

---

## Current LibraryGenie Art Implementation

### **Lists and Folders**
```python
# From lib/ui/listitem_renderer.py
list_item.setArt({
    'icon': 'DefaultFolder.png',
    'thumb': 'DefaultFolder.png'
})
```

### **Action Items**
```python
# From lib/ui/listitem_builder.py
if 'Sync' in title or action == 'scan_favorites_execute':
    icon = 'DefaultAddonService.png'
else:
    icon = 'DefaultFolder.png'

li.setArt({'icon': icon, 'thumb': icon})
```

### **Media Items**
```python
# From lib/ui/listitem_builder.py
# Uses database-driven art from media_items table
art = self._build_art_dict(item)  # Includes poster, fanart, thumb, etc.
```

---

## Recommended Art Improvements

### **Enhanced List/Folder Icons**
- **User Lists**: `DefaultPlaylist.png` or `DefaultVideoPlaylists.png`
- **Search History Folder**: `DefaultSearchHistory.png`
- **Backup/Export Actions**: `DefaultHardDisk.png`
- **Import Actions**: `DefaultAddSource.png`

### **Context-Aware Action Icons**
- **Create List**: `DefaultAddSource.png`
- **Search**: `DefaultAddonsSearch.png`
- **Backup**: `DefaultHardDisk.png`
- **Import**: `DefaultAddSource.png`
- **Settings**: `DefaultSettings.png`
- **Help**: `DefaultHelp.png`

### **Media Type Specific Icons**
- **Movie Lists**: `DefaultMovies.png`
- **TV Episode Lists**: `DefaultTVShows.png`
- **Mixed Content Lists**: `DefaultVideo.png`

### **Dynamic Art Selection**
Consider implementing logic to select icons based on:
- **List Content**: Analyze list content to choose appropriate media type icon
- **Folder Purpose**: Special folders (Search History, Backups) get specific icons
- **Action Type**: Different tools get contextually appropriate icons
- **User Preferences**: Allow users to choose icon themes in settings

---

## Implementation Notes

### **Art Priority**
1. **Database Art**: For media items, use poster/fanart from library metadata
2. **Fallback Icons**: Use appropriate Kodi default icons when metadata unavailable
3. **Consistent Theming**: Maintain visual consistency across similar item types

### **Performance Considerations**
- **Icon Caching**: Kodi automatically caches default icons
- **Network Art**: For custom artwork, consider local caching strategies
- **Fallback Chain**: Always provide fallback to standard Kodi icons

### **Future Enhancements**
- **Custom Icon Sets**: Allow users to choose from different icon themes
- **Dynamic Folder Icons**: Show preview of folder contents in icon
- **Smart List Icons**: Automatically select icons based on list content analysis
- **Artwork Downloads**: Integration with metadata providers for enhanced artwork

---

This documentation provides a complete reference for current and future artwork implementation in LibraryGenie, ensuring consistent visual design and optimal user experience within the Kodi ecosystem.
