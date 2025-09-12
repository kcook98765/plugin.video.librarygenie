# LibraryGenie Skin Control Mappings

This document describes the intelligent skin control mapping system that optimizes navigation control detection for different Kodi skins.

## Overview

The skin control system replaces the old brute-force approach with a database-backed, intelligent control mapping system that automatically detects and configures appropriate control IDs for different Kodi skins.

## Supported Skins

| **Skin Name** | **Kodi Skin ID** | **Down Controls** | **Right Controls** |
|---------------|------------------|-------------------|-------------------|
| **Auto-Detect** | *(dynamic)* | *(detects automatically)* | *(detects automatically)* |
| **Custom** | *(user-defined)* | *(user configurable)* | *(user configurable)* |
| **Estuary (Default)** | `skin.estuary` | `50,55` | `500,501,502,51,52,53,54` |
| **Arctic Zephyr Reloaded** | `skin.arctic.zephyr.mod` | `50,58,59,52` | `53,55` |
| **Aeon Nox SiLVO** | `skin.aeon.nox.silvo` | `50,55` | `500,501,502,56,57,58,59` |
| **Mimic** | `skin.mimic` | `50,52,55` | `500,501,502,504,505,507,509,520` |
| **Confluence** | `skin.confluence` | `50,52` | `500,501` |

## Control Types

### Down Controls
- **Usage**: List and WideList views
- **Navigation**: Vertical navigation using the ⬇️ Down arrow key
- **View Types**: Traditional list displays, detailed list views

### Right Controls  
- **Usage**: Panel, Grid, and Wall views
- **Navigation**: Horizontal navigation using the ➡️ Right arrow key
- **View Types**: Thumbnail grids, poster walls, panel displays

## Special Configuration Options

### Auto-Detect
- **Function**: Automatically detects the current Kodi skin
- **Method**: Uses `xbmc.getInfoLabel("Skin.CurrentSkin")` to identify skin
- **Behavior**: 
  - Applies appropriate preset if skin is recognized
  - Falls back to safe defaults for unknown skins
  - Default fallbacks: `50,55` (down), `500,501,502` (right)

### Custom
- **Function**: Allows manual control ID configuration
- **Use Cases**: 
  - Custom or modified skins
  - When presets don't work correctly
  - Advanced user customization
- **Configuration**: Comma-separated control IDs in addon settings

## System Architecture

### Database Schema
The system uses a `skin_mappings` table with the following structure:

```sql
CREATE TABLE skin_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skin_id TEXT UNIQUE,
    preset_key TEXT UNIQUE, 
    display_name TEXT NOT NULL,
    down_controls TEXT NOT NULL DEFAULT '',
    right_controls TEXT NOT NULL DEFAULT '',
    is_builtin INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Settings Integration
- **Category**: Settings > Skin Controls
- **Options**: Dropdown with alphabetized skin presets
- **Manual Config**: Text fields for down/right control lists
- **Apply Button**: Immediate configuration application

## How It Works

### First-Run Setup
1. **Detection**: System automatically detects current skin during initial setup
2. **Configuration**: Applies appropriate preset if skin is recognized
3. **Fallback**: Uses safe defaults for unknown skins
4. **Persistence**: Saves configuration to prevent re-detection

### Runtime Operation
1. **Focus Check**: Verifies if list control already has focus
2. **Control Selection**: Uses configured control lists instead of hardcoded IDs
3. **Smart Retry**: Tries controls in configured priority order
4. **Error Guidance**: Provides helpful messages when navigation fails

### Settings Management
1. **Preset Selection**: User chooses from dropdown in settings
2. **Manual Override**: Custom control lists for advanced users
3. **Apply Action**: Button triggers immediate configuration
4. **Validation**: System validates and confirms changes

## Performance Benefits

### Before (Brute-Force Approach)
- ❌ Tried hardcoded control IDs in multiple rounds
- ❌ Random navigation failures
- ❌ Poor performance with repeated attempts
- ❌ No user guidance on failures

### After (Intelligent System)
- ✅ Uses skin-specific control configurations
- ✅ Checks if control already has focus before attempting manual focus
- ✅ Provides helpful error messages and settings guidance
- ✅ One-time configuration with persistent settings

## User Experience

### Automatic Configuration
- **First Run**: Skin detection happens transparently during setup
- **Just Works**: Navigation works correctly out-of-the-box for supported skins
- **No Intervention**: Most users never need to manually configure controls

### Manual Configuration
- **Easy Access**: Settings > Skin Controls
- **Clear Options**: Labeled presets for popular skins
- **Immediate Feedback**: Apply button shows confirmation dialog
- **Helpful Guidance**: Error messages direct users to correct settings

## Adding New Skins

### For Developers
New skins can be added by updating the default mappings in `SkinMappingsManager._ensure_default_mappings()`:

```python
defaults = [
    ("skin.newskin", "newskin_preset", "New Skin Name", "down_controls", "right_controls", True),
    # ... other mappings
]
```

### For Users
Users can add support for custom skins using the "Custom" preset:
1. Select "Custom" from the skin preset dropdown
2. Enter down control IDs (comma-separated)
3. Enter right control IDs (comma-separated)  
4. Click "Apply skin preset"

## Troubleshooting

### Navigation Not Working
1. **Check Settings**: Go to Settings > Skin Controls
2. **Try Auto-Detect**: Select "Auto-Detect" and click "Apply skin preset"
3. **Use Custom**: If auto-detect fails, try "Custom" with manual control IDs
4. **Check Logs**: Enable debug logging for detailed control ID information

### Finding Control IDs
1. **Skin Documentation**: Check your skin's documentation or forums
2. **Kodi Logs**: Enable debug logging and check for control focus messages
3. **Trial and Error**: Use "Custom" preset to test different control IDs
4. **Community Support**: Ask on Kodi forums for skin-specific control IDs

## Technical Implementation

### Key Components
- **SkinMappingsManager**: Database operations and skin control management
- **SettingsManager**: Configuration persistence and skin detection
- **Router**: Action handling for "Apply skin preset" button
- **info_hijack_helpers**: Optimized focus logic using configured controls

### Integration Points
- **First-run setup**: Automatic skin detection during initial configuration
- **Settings interface**: User-friendly preset selection and manual configuration
- **Navigation system**: Intelligent control selection replacing brute-force approach
- **Error handling**: Helpful guidance when navigation fails

This system ensures reliable navigation control across the diverse Kodi skin ecosystem while maintaining backwards compatibility and providing easy customization options for advanced users.