
# LibraryGenie Kodi Addon

LibraryGenie is a comprehensive Kodi addon that bridges your local Kodi media library with remote AI-powered search capabilities. The addon enables natural language queries, intelligent list management, and seamless synchronization with remote search APIs.

## Features

### 🤖 AI-Powered Search
- **Natural Language Queries**: Search your media using plain English descriptions
- **Semantic Search**: Leverages AI embeddings for intelligent movie discovery
- **Query Refinement**: Interactive interface to improve and adjust search results
- **Automatic Matching**: Seamlessly matches search results to your local Kodi library

### 📚 Smart Library Management
- **Hierarchical Organization**: Create nested folders and lists for better organization
- **Dynamic Lists**: Lists that update automatically based on your search criteria
- **Manual Curation**: Add individual items from any addon or source
- **Exception Handling**: Block specific entries from appearing in lists
- **Batch Operations**: Efficiently manage large collections

### 🔄 Remote API Integration
- **Easy Pairing**: Simple 8-digit code pairing with remote servers
- **Batch Upload**: Efficiently sync your entire movie collection
- **Delta Synchronization**: Only upload changes since last sync
- **Multiple Auth Methods**: Support for API keys and pairing codes
- **Connection Testing**: Verify connectivity and troubleshoot issues

### 🎯 Advanced List Features
- **Context Menu Integration**: Add items directly from any Kodi interface
- **List Browser**: Navigate and manage your collections easily
- **Search History**: Automatic permanent storage of all search results in a protected top-level folder
- **Export/Import**: Backup and restore your list configurations

### 🛠️ Technical Features
- **SQLite Database**: Local storage for lists, folders, and metadata
- **Seamless Integration**: Direct communication with Kodi's media library
- **Intelligent Matching**: Automatic matching of search results to local content
- **Debug Logging**: Comprehensive logging for troubleshooting
- **Settings Management**: Centralized configuration system

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
3. The addon will scan your Kodi library and upload movie data
4. This enables AI-powered search functionality

## Usage Guide

### Creating Lists
1. Launch LibraryGenie from the Kodi Add-ons menu
2. Navigate to create a new list or folder
3. Enter your search criteria in natural language
4. Review and refine results as needed
5. Save the list for future use
6. **Automatic**: Search results are also automatically saved to "Search History" folder

### Natural Language Search Examples
- "Psychological thrillers with plot twists"
- "Comedy movies from the 80s and 90s"
- "Sci-fi movies about time travel"
- "Action movies starring Tom Cruise"
- "Animated movies suitable for kids"

### Managing Collections
- **Folders**: Organize your lists into hierarchical folders
- **Manual Addition**: Use context menus to add specific items
- **Exceptions**: Block unwanted items from appearing in lists
- **Batch Operations**: Perform actions on multiple items at once

### Search History Management
- **Automatic Storage**: Every search is automatically saved as a new list under "Search History"
- **Protected Folder**: The "Search History" folder cannot be deleted, renamed, or modified
- **Timestamped Lists**: Each search creates a timestamped list showing the exact query and results
- **Full Management**: Search history lists support all normal operations (view, edit items, etc.)
- **Permanent Archive**: Build a complete archive of all your search discoveries over time

### Context Menu Integration
- Right-click on any media item in Kodi
- Select LibraryGenie options from the context menu
- Add items directly to existing lists
- Create new lists on the fly

## Configuration Options

### LibraryGenie Server Settings
- **LGS Upload API URL**: Your server's API endpoint
- **LGS Upload API Key**: Authentication key for uploads
- **LGS Username/Password**: Optional user credentials
- **Authenticate with One-Time Code**: Quick setup option

### Remote API Settings
- **Remote API Server URL**: Base URL for your search API server
- **Remote API Key**: Your unique API authentication key
- **Connection Testing**: Verify API connectivity
- **Upload Management**: Sync your library with the server

### Advanced Options
- **Debug Logging**: Enable detailed logging for troubleshooting
- **Database Management**: Backup and restore local data
- **Performance Tuning**: Adjust timeouts and batch sizes

## Troubleshooting

### Common Issues

#### Authentication Problems
- **Error**: "Invalid or missing API key"
- **Solution**: Re-pair the addon or regenerate your API key

#### Connection Issues
- **Error**: "Cannot connect to server"
- **Solution**: Verify server URL and check network connectivity

#### Search Not Working
- **Error**: "No results found"
- **Solution**: Ensure your library has been uploaded to the server

#### Library Matching Issues
- **Error**: "Search results don't match local content"
- **Solution**: The addon will automatically attempt to find matching content in your library

### Debug Mode
1. Enable debug logging in addon settings
2. Reproduce the issue
3. Check Kodi's log file for detailed error information
4. Look for entries prefixed with `[LibraryGenie]`

### Getting Help
- Check the addon's log output for error messages
- Verify all settings are correctly configured
- Test the remote API connection
- Review the server documentation for API changes

## Development

### File Structure
```
resources/
├── lib/                    # Core addon logic
│   ├── api_client.py      # API communication
│   ├── database_manager.py # Local database operations
│   ├── query_manager.py   # SQL query management
│   ├── remote_api_client.py # Remote server integration
│   └── window_*.py        # UI components
├── language/              # Localization files
└── settings.xml          # Addon configuration
```

### Key Components
- **DatabaseManager**: Handles local SQLite operations and search history management
- **RemoteAPIClient**: Manages server communication
- **QueryManager**: Builds and executes database queries
- **Window Classes**: Implement the user interface
- **Utils**: Common utility functions and logging
- **Search History**: Automatic preservation of all search queries and results

## API Integration

The addon integrates with a remote search API that provides:
- AI-powered semantic search capabilities
- Movie metadata and recommendations
- User library synchronization
- Natural language query processing

See `docs/remote_api_interactions.md` for detailed API documentation.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, feature requests, or questions:
1. Check the troubleshooting section above
2. Enable debug logging and review log files
3. Open an issue on the project repository
4. Provide log excerpts and detailed error descriptions

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with proper documentation
4. Submit a pull request with a clear description

## Acknowledgments

- Built for the Kodi media center platform
- Utilizes AI technologies for enhanced search capabilities
- Inspired by the need for better media discovery tools
