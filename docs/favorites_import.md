# Import Favorites Feature

The Import Favorites feature allows you to scan your Kodi favorites and automatically import playable video items into LibraryGenie lists with enhanced metadata.

## How It Works

1. **Favorites Scanning**: The system scans all media-type favorites in your Kodi installation
2. **Playability Detection**: Only video items that can be played are considered for import
3. **Library Enhancement**: If a favorite item matches something in your Kodi library, full library metadata is used
4. **Minimal Import**: For non-library items, basic playable information is preserved

## Usage

### From Settings
1. Open LibraryGenie addon settings
2. Navigate to the **Remote API** section
3. Click **Import from Favorites**
4. The system will scan and present import options

### What Gets Imported

**Playable Items Only**: 
- Video files with valid paths
- Streamable content with working URLs
- Library items with proper metadata

**Enhanced Metadata**: 
- Movies in your Kodi library get full details (title, year, plot, artwork, etc.)
- External items get basic playable information
- IMDb IDs are preserved when available

**Organized Import**: 
- Items can be imported into existing lists
- New lists can be created during import
- Folder organization is maintained

## Technical Details

### Detection Process
1. **JSON-RPC Query**: Uses `Favourites.GetFavourites` to retrieve media favorites
2. **Playability Check**: Tests each item with `Files.GetFileDetails` 
3. **Library Matching**: Attempts to match favorites with library content via paths and IDs
4. **Metadata Enrichment**: Enhances matched items with full library details

### Supported Formats
- **File Types**: Video files with recognized extensions (MP4, MKV, AVI, WMV, MOV, FLV, etc.)
- **Network Paths**: SMB, NFS, FTP, FTPS network shares
- **Streaming**: HTTP/HTTPS URLs for streamable content
- **Plugins**: Plugin video URLs (plugin://plugin.video.*)
- **Library Items**: videodb:// URLs and files in your Kodi library
- **Local Files**: File:// URLs and local file paths

### Path Validation
The import process validates paths using multiple criteria:
- **Plugin URLs**: Always accepted as playable
- **videodb URLs**: Always accepted as playable
- **File Extensions**: Quick validation for common video formats
- **Streamdetails**: JSON-RPC verification of video stream information
- **Directory Probing**: Fallback verification for unclear paths

### Import Options
- **Automatic Import**: All playable favorites are imported automatically
- **Organized Structure**: Creates timestamped list under "Imported Lists/Favorites" folder
- **Library Enhancement**: Favorites matching library content get full metadata
- **Path Validation**: Only imports items with valid playable paths
- **Batch Processing**: Efficient single-transaction import of large favorite collections
- **Clear and Replace**: Each import clears previous favorites imports before adding new content

## Troubleshooting

### Common Issues

**No Items Found**
- Ensure you have media-type favorites in Kodi
- Check that favorites contain playable video content
- Verify favorites aren't corrupted or pointing to missing files

**Missing Metadata**
- Non-library items will have minimal metadata
- Ensure library items have proper IMDb IDs for best results
- Library matching depends on accurate file paths

**Import Failures**
- Enable debug logging to see detailed import process
- Check Kodi logs for JSON-RPC errors
- Verify favorites are accessible and playable

### Debug Information

Enable debug logging in LibraryGenie settings to see:
- Detailed JSON-RPC request/response logs
- Playability detection results
- Library matching attempts
- Import success/failure reasons

## Best Practices

1. **Organize Favorites First**: Clean up your Kodi favorites before importing
2. **Use Library Items**: Items in your Kodi library will import with better metadata
3. **Check Paths**: Ensure favorite paths are still valid before importing
4. **Selective Import**: Review the import list before proceeding
5. **Regular Updates**: Re-run import after adding new favorites

This feature bridges the gap between Kodi's built-in favorites system and LibraryGenie's advanced organization capabilities, making it easy to migrate and enhance your existing favorite collections.