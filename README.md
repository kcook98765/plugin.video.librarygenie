
# LibraryGenie Kodi Addon

LibraryGenie is a comprehensive Kodi addon that bridges your local Kodi media library with remote AI-powered search capabilities. The addon enables natural language queries, intelligent list management, and seamless synchronization with remote search APIs.

## Features

### 🤖 AI-Powered Search
- **Natural Language Queries**: Search your media using plain English descriptions
- **Semantic Search**: Leverages AI embeddings for intelligent movie discovery
- **Interactive Search Interface**: Modal search window with real-time query refinement
- **Automatic Library Matching**: Seamlessly matches search results to your local Kodi library
- **Score-Based Results**: Search results ranked by relevance with automatic sorting

### 📚 Smart Library Management
- **Hierarchical Organization**: Create nested folders and lists with unlimited depth
- **Dynamic Lists**: Lists that update automatically based on search criteria
- **Manual Curation**: Add individual items from any addon or source via context menus
- **Batch Operations**: Efficiently manage large collections
- **Protected Search History**: Automatic permanent storage of all searches in a protected folder

### 🔄 Remote API Integration
- **Easy Pairing**: Simple 8-digit code pairing with remote servers
- **Chunked Batch Upload**: Efficiently sync your entire movie collection in chunks
- **Delta Synchronization**: Only upload changes since last sync
- **Multiple Auth Methods**: Support for API keys, pairing codes, and LGS authentication
- **Connection Testing**: Built-in connectivity verification and troubleshooting

### 🎯 Advanced Navigation & UI
- **Modal Interface System**: Clean, non-intrusive search and browse interfaces
- **Context Menu Integration**: Add items directly from any Kodi interface
- **Smart Navigation Management**: Prevents UI conflicts with timeout protection
- **Options & Tools Menu**: Centralized access to all addon functionality
- **Deferred Execution**: Handles complex operations without blocking the UI

### 🛠️ Technical Features
- **SQLite Database**: Local storage with comprehensive schema for lists, folders, and metadata
- **JSONRPC Integration**: Direct communication with Kodi's media library
- **Intelligent Matching**: Advanced algorithms for matching search results to local content
- **Comprehensive Logging**: Detailed debug logging with configurable levels
- **Settings Management**: Centralized configuration with validation
- **Window Management**: Proper Kodi window lifecycle management

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

### Remote API Configuration

#### Method 1: Easy Pairing (Recommended)
1. Visit your server's web dashboard and generate a pairing code
2. Open LibraryGenie addon settings
3. Go to **Remote API** section
4. Click **Setup Remote API (Easy)**
5. Enter the 8-digit pairing code when prompted
6. The addon will automatically configure the connection

#### Method 2: Manual Setup
1. Obtain your API key from the server dashboard
2. Open addon settings → **Remote API**
3. Set **Remote API Server URL** to your server address
4. Set **Remote API Key** to your API key
5. Click **Test Remote API Connection** to verify

### Library Upload
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

#### Quick Search Access
- **Plugin URL for Skins**: `plugin://plugin.video.librarygenie/?action=search`
- **Direct Window Access**: `ActivateWindow(Videos,"plugin://plugin.video.librarygenie/?action=search",return)`

#### Context Menu
- Right-click on any media item in Kodi
- Select **LibraryGenie** from the context menu
- Add items directly to existing lists or create new ones

### Using the Options & Tools Menu

The Options & Tools menu dynamically adapts based on your authentication status and available data:

- **Search Movies**: Available when authenticated to remote API
- **Search History**: Available when search history exists
- **Create New List**: Always available
- **Create New Folder**: Always available  
- **Settings**: Always available

### Search Functionality

#### Natural Language Search Examples
- "Psychological thrillers with plot twists"
- "Comedy movies from the 80s and 90s"
- "Sci-fi movies about time travel"
- "Action movies starring Tom Cruise"
- "Animated movies suitable for kids"

#### Search Process
1. Access search via Options menu or direct plugin call
2. Enter your natural language query in the search modal
3. Review results ranked by relevance score
4. Results are automatically saved to "Search History" folder
5. Navigate to saved search list to view matched local content

### Managing Collections

#### Folder Structure
- **Root Level**: Top-level folders and lists
- **Nested Folders**: Unlimited hierarchical organization
- **Search History**: Protected folder containing all search results
- **Context Preservation**: Folder context maintained across operations

#### List Management
- **View Lists**: Browse list contents with proper sorting options
- **Rename/Delete**: Full management capabilities via context menus
- **Move Lists**: Reorganize lists between folders
- **Manual Addition**: Add specific items via context menus
- **Remove Items**: Remove individual items from lists

### Search History Management

The Search History system automatically preserves all your searches:

- **Automatic Storage**: Every search creates a timestamped list in "Search History"
- **Protected Folder**: Cannot be deleted, renamed, or modified
- **Manageable Lists**: Individual search lists can be deleted, renamed, or moved
- **Score Preservation**: Search results maintain relevance scores
- **Full Archive**: Complete searchable history of all discoveries

## Configuration Options

### Remote API Settings
- **Remote API Server URL**: Base URL for your search API server
- **Remote API Key**: Your unique API authentication key
- **Connection Testing**: Verify API connectivity and troubleshoot issues

### LGS Integration Settings
- **LGS Upload API URL**: Your server's API endpoint
- **LGS Upload API Key**: Authentication key for uploads
- **LGS Username/Password**: Optional user credentials
- **One-Time Code Authentication**: Quick setup option

### Advanced Options
- **Debug Logging**: Enable detailed logging for troubleshooting
- **Database Management**: Backup and restore local data
- **Performance Tuning**: Adjust timeouts and batch sizes
- **Navigation Protection**: Configurable UI conflict prevention

## Architecture Overview

### Core Components

#### Database Layer
- **DatabaseManager**: SQLite operations and schema management
- **QueryManager**: Optimized SQL query building and execution
- **DatabaseSyncManager**: Kodi library synchronization

#### API Integration
- **RemoteAPIClient**: Search API communication
- **APIClient**: General API utilities
- **AuthenticationManager**: Pairing and credential management

#### User Interface
- **WindowSearch**: Modal search interface
- **OptionsManager**: Dynamic options menu system
- **NavigationManager**: UI state and navigation management
- **DirectoryBuilder**: Kodi directory listing construction

#### Media Management
- **ResultsManager**: Search result processing and display
- **MediaManager**: Kodi library integration
- **ListItemBuilder**: Kodi ListItem construction with proper metadata

### File Structure
```
resources/
├── lib/                    # Core addon logic
│   ├── database_manager.py     # Local database operations
│   ├── query_manager.py        # SQL query management
│   ├── remote_api_client.py    # Remote server integration
│   ├── options_manager.py      # Dynamic options menu
│   ├── navigation_manager.py   # UI navigation control
│   ├── window_search.py        # Search modal interface
│   ├── results_manager.py      # Search result processing
│   ├── folder_list_manager.py  # Folder/list operations
│   ├── route_handlers.py       # Action routing
│   ├── listitem_builder.py     # Kodi ListItem creation
│   └── utils.py               # Logging and utilities
├── media/                      # Addon graphics and icons
├── language/                   # Localization files
└── settings.xml               # Addon configuration schema
```

## Troubleshooting

### Common Issues

#### Search Not Working
- **Symptoms**: "Search Movies" not available in options
- **Solution**: Verify remote API configuration and authentication

#### Navigation Conflicts
- **Symptoms**: Options menu not responding or appearing multiple times
- **Solution**: Built-in navigation protection handles this automatically

#### Library Matching Issues
- **Symptoms**: Search results don't show local matches
- **Solution**: Ensure library upload completed successfully

#### Database Corruption
- **Symptoms**: Lists or folders not displaying correctly
- **Solution**: Check addon logs and consider database rebuild

### Debug Mode
1. Enable debug logging in addon settings
2. Reproduce the issue
3. Check Kodi's log file for entries prefixed with `[LibraryGenie]`
4. Look for ERROR, WARNING, and DEBUG level messages

### Log Analysis
The addon provides comprehensive logging with these levels:
- **ERROR**: Critical issues requiring attention
- **WARNING**: Potential problems or edge cases
- **INFO**: Important operational information
- **DEBUG**: Detailed execution flow and data

## API Integration

### Search API Endpoints
- **Search**: Natural language movie search with AI processing
- **Library Upload**: Chunked batch upload of user's movie collection
- **Authentication**: Pairing code and API key management

### Data Flow
1. User enters natural language query
2. Query sent to remote search API
3. AI processes query and returns ranked results
4. Results matched against local Kodi library
5. Combined results displayed with relevance scores
6. Search automatically saved to Search History

## Development

### Key Design Patterns
- **Singleton Pattern**: Used for configuration and database managers
- **Factory Pattern**: ListItem creation and directory building
- **Observer Pattern**: Navigation state management
- **Command Pattern**: Route handling and action execution

### Testing
- **Modal Testing**: Search interface validation
- **Database Testing**: SQLite schema and query validation
- **API Testing**: Remote endpoint connectivity
- **Navigation Testing**: UI state management

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, feature requests, or questions:
1. Enable debug logging in addon settings
2. Review log files for error messages
3. Check the troubleshooting section above
4. Open an issue with detailed error descriptions and log excerpts

## Contributing

Contributions are welcome! The codebase uses:
- **Python 3.x** compatible with Kodi's Python API
- **SQLite** for local data storage
- **Kodi's JSONRPC API** for media library integration
- **Modal UI patterns** for non-intrusive user interaction

## Acknowledgments

- Built for the Kodi media center platform
- Utilizes AI technologies for enhanced search capabilities
- Inspired by the need for better media discovery and organization tools
- Implements modern UI patterns for seamless user experience
