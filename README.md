# LibraryGenie Kodi Addon

LibraryGenie is a comprehensive Kodi addon focused on intelligent list management and organization for your media library. The addon provides hierarchical folder structures, smart list creation, and seamless integration with Kodi's interface.

## Current Features (Available Now)

### 📚 Smart Library Management
- **Hierarchical Organization**: Create nested folders and lists with unlimited depth
- **Manual Curation**: Add individual items from any addon or source via context menus
- **Batch Operations**: Efficiently manage large collections
- **Context Menu Integration**: Add items directly from any Kodi interface
- **Smart Navigation Management**: Prevents UI conflicts with timeout protection

### 🎯 Advanced Navigation & UI
- **Modal Interface System**: Clean, non-intrusive browse interfaces
- **Options & Tools Menu**: Centralized access to all addon functionality
- **Deferred Execution**: Handles complex operations without blocking the UI
- **Window Management**: Proper Kodi window lifecycle management

### 🛠️ Technical Features
- **SQLite Database**: Local storage with comprehensive schema for lists, folders, and metadata
- **JSONRPC Integration**: Direct communication with Kodi's media library
- **Comprehensive Logging**: Detailed debug logging with configurable levels
- **Settings Management**: Centralized configuration with validation

## Future AI Features (Invite-Only Alpha) 🚀

> ⚠️ **Alpha Status Notice**: The AI-powered features below are currently in invite-only alpha testing. These capabilities are not available in the general release and require special server access. Contact the development team for alpha testing opportunities.

### 🤖 AI-Powered Search (Alpha)
- **Natural Language Queries**: Search your media using plain English descriptions
- **Semantic Search**: Leverages AI embeddings for intelligent movie discovery
- **Interactive Search Interface**: Modal search window with real-time query refinement
- **Automatic Library Matching**: Seamlessly matches search results to your local Kodi library
- **Score-Based Results**: Search results ranked by relevance with automatic sorting

### 🔄 Remote API Integration (Alpha)
- **Easy Pairing**: Simple 8-digit code pairing with remote servers
- **Chunked Batch Upload**: Efficiently sync your entire movie collection in chunks
- **Delta Synchronization**: Only upload changes since last sync
- **Multiple Auth Methods**: Support for API keys, pairing codes, and LGS authentication
- **Connection Testing**: Built-in connectivity verification and troubleshooting

### 📊 Advanced Search Features (Alpha)
- **Dynamic Lists**: Lists that update automatically based on search criteria
- **Protected Search History**: Automatic permanent storage of all searches in a protected folder
- **Intelligent Matching**: Advanced algorithms for matching search results to local content

## Installation

### From ZIP File
1. Download the latest LibraryGenie addon ZIP from the releases page
2. In Kodi, go to **Add-ons** → **Install from ZIP file**
3. Select the downloaded ZIP file
4. Wait for installation confirmation

### From Repository (if available)
1. Add the LibraryGenie repository to Kodi
2. Go to **Add-ons** → **Install from repository**
3. Select LibraryGenie from the list
4. Click Install

## Initial Setup

The addon works immediately after installation with no additional configuration required for list management features.

### For Alpha AI Features (Invite-Only)

> ⚠️ **Alpha Access Required**: These setup steps only apply to users with alpha testing access.

#### Method 1: Easy Pairing (Recommended for Alpha Users)
1. Visit your server's web dashboard and generate a pairing code
2. Open LibraryGenie addon settings
3. Go to **Remote API** section
4. Click **Setup Remote API (Easy)**
5. Enter the 8-digit pairing code when prompted
6. The addon will automatically configure the connection

#### Method 2: Manual Setup (Alpha Users)
1. Obtain your API key from the server dashboard
2. Open addon settings → **Remote API**
3. Set **Remote API Server URL** to your server address
4. Set **Remote API Key** to your API key
5. Click **Test Remote API Connection** to verify

#### Library Upload (Alpha Users)
1. After API setup, go to **Remote API** in settings
2. Click **Upload IMDB List to Server**
3. The addon will scan your Kodi library and upload movie data in chunks
4. This enables AI-powered search functionality

## Usage Guide

### Accessing LibraryGenie

#### From Add-ons Menu
1. Navigate to **Add-ons** → **Video add-ons**
2. Select **LibraryGenie**
3. Choose from available options

#### Context Menu
- Right-click on any media item in Kodi
- Select **LibraryGenie** from the context menu
- Add items directly to existing lists or create new ones

### Using the Options & Tools Menu

The Options & Tools menu adapts based on your authentication status:

**Always Available:**
- **Create New List**: Create new lists in any folder
- **Create New Folder**: Organize lists in hierarchical folders
- **Settings**: Access addon configuration

**Alpha Users Only:**
- **Search Movies**: Available when authenticated to remote API
- **Search History**: Available when search history exists

### Managing Collections

#### Folder Structure
- **Root Level**: Top-level folders and lists
- **Nested Folders**: Unlimited hierarchical organization
- **Context Preservation**: Folder context maintained across operations

#### List Management
- **View Lists**: Browse list contents with proper sorting options
- **Rename/Delete**: Full management capabilities via context menus
- **Move Lists**: Reorganize lists between folders
- **Manual Addition**: Add specific items via context menus
- **Remove Items**: Remove individual items from lists

### Alpha AI Features Usage (Invite-Only)

> ⚠️ **Alpha Access Required**: These features require special server access.

#### Natural Language Search Examples
- "Psychological thrillers with plot twists"
- "Comedy movies from the 80s and 90s"
- "Sci-fi movies about time travel"
- "Action movies starring Tom Cruise"
- "Animated movies suitable for kids"

#### Search Process (Alpha)
1. Access search via Options menu
2. Enter your natural language query in the search modal
3. Review results ranked by relevance score
4. Results are automatically saved to "Search History" folder
5. Navigate to saved search list to view matched local content

## Configuration Options

### Basic Settings (Available to All Users)
- **Debug Logging**: Enable detailed logging for troubleshooting
- **Performance Tuning**: Adjust timeouts and batch sizes
- **Navigation Protection**: Configurable UI conflict prevention

### Alpha Settings (Invite-Only)
- **Remote API Server URL**: Base URL for your search API server
- **Remote API Key**: Your unique API authentication key
- **Connection Testing**: Verify API connectivity and troubleshoot issues
- **LGS Integration Settings**: Alternative authentication methods

## Architecture Overview

### Core Components

#### Database Layer
- **DatabaseManager**: SQLite operations and schema management
- **QueryManager**: Optimized SQL query building and execution

#### User Interface
- **OptionsManager**: Dynamic options menu system
- **NavigationManager**: UI state and navigation management
- **DirectoryBuilder**: Kodi directory listing construction

#### Alpha Components (Future Release)
- **RemoteAPIClient**: Search API communication
- **WindowSearch**: Modal search interface
- **ResultsManager**: Search result processing and display

### File Structure
```
resources/
├── lib/                        # Core addon logic
│   ├── config/                 # Configuration management
│   │   ├── addon_helper.py         # Addon execution wrapper
│   │   ├── addon_ref.py            # Addon reference utilities
│   │   ├── config_manager.py       # Configuration management
│   │   └── settings_manager.py     # Settings management
│   ├── core/                   # Core functionality
│   │   ├── context.py              # Context menu implementation
│   │   ├── directory_builder.py    # Kodi directory construction
│   │   ├── navigation_manager.py   # UI navigation control
│   │   ├── options_manager.py      # Dynamic options menu
│   │   ├── route_handlers.py       # Action routing
│   │   └── runner.py               # Core runner functionality
│   ├── data/                   # Database operations
│   │   ├── database_manager.py     # Local database operations
│   │   ├── folder_list_manager.py  # Folder/list operations
│   │   ├── query_manager.py        # SQL query management
│   │   └── results_manager.py      # (Alpha) Search result processing
│   ├── integrations/           # External integrations
│   │   ├── jsonrpc/               # Kodi JSON-RPC integration
│   │   │   └── jsonrpc_manager.py      # JSON-RPC communication
│   │   └── remote_api/            # (Alpha) Remote API integration
│   │       ├── authenticate_code.py    # Authentication handling
│   │       ├── imdb_upload_manager.py  # Library upload management
│   │       ├── remote_api_client.py    # Remote server integration
│   │       ├── remote_api_setup.py     # API setup workflows
│   │       └── shortlist_importer.py   # Shortlist import functionality
│   ├── kodi/                   # Kodi-specific utilities
│   │   ├── context_menu_builder.py # Context menu construction
│   │   ├── kodi_helper.py          # Kodi utility functions
│   │   ├── listitem_builder.py     # Kodi ListItem creation
│   │   ├── listitem_infotagvideo.py # Video info tag handling
│   │   ├── url_builder.py          # URL construction utilities
│   │   └── window_search.py        # (Alpha) Search modal interface
│   ├── media/                  # Media management
│   │   └── media_manager.py        # Media processing utilities
│   ├── utils/                  # Utility functions
│   │   ├── singleton_base.py       # Singleton pattern base class
│   │   └── utils.py               # Logging and utilities
│   └── context.py              # Compatibility shim for addon.xml
├── media/                      # Addon graphics and icons
├── language/                   # Localization files
└── settings.xml               # Addon configuration schema
```

## Troubleshooting

### Common Issues

#### Lists Not Displaying
- **Symptoms**: Folders or lists not showing correctly
- **Solution**: Check addon logs for database errors

#### Navigation Conflicts
- **Symptoms**: Options menu not responding or appearing multiple times
- **Solution**: Built-in navigation protection handles this automatically

#### Context Menu Not Working
- **Symptoms**: LibraryGenie option not appearing in context menus
- **Solution**: Verify addon is properly installed and enabled

### Alpha-Specific Issues (Invite-Only)

#### Search Not Working
- **Symptoms**: "Search Movies" not available in options
- **Solution**: Verify remote API configuration and alpha access

#### Library Matching Issues
- **Symptoms**: Search results don't show local matches
- **Solution**: Ensure library upload completed successfully

### Debug Mode
1. Enable debug logging in addon settings
2. Reproduce the issue
3. Check Kodi's log file for entries prefixed with `[LibraryGenie]`
4. Look for ERROR, WARNING, and DEBUG level messages

## Alpha Testing Program

> 🔬 **Join the Alpha**: Interested in testing AI-powered search features? The alpha program provides early access to cutting-edge media discovery capabilities powered by artificial intelligence.

**What Alpha Testers Get:**
- Early access to AI-powered natural language search
- Advanced semantic matching algorithms
- Automatic search history and smart recommendations
- Direct feedback channel to influence feature development

**Requirements for Alpha Access:**
- Stable internet connection for API communication
- Willingness to provide feedback and bug reports
- Understanding that features are experimental and may change

**How to Request Alpha Access:**
Contact the development team with your use case and testing environment details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, feature requests, or questions:
1. Enable debug logging in addon settings
2. Review log files for error messages
3. Check the troubleshooting section above
4. Open an issue with detailed error descriptions and log excerpts

For alpha testing inquiries, contact the development team directly.

## Contributing

Contributions are welcome! The codebase uses:
- **Python 3.x** compatible with Kodi's Python API
- **SQLite** for local data storage
- **Kodi's JSONRPC API** for media library integration
- **Modal UI patterns** for non-intrusive user interaction

## Acknowledgments

- Built for the Kodi media center platform
- Core list management available to all users
- AI capabilities powered by cutting-edge machine learning technologies (alpha)
- Inspired by the need for better media discovery and organization tools