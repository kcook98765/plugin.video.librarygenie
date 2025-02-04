<!-- """ /README.md """ -->

# LibraryGenie Kodi Addon

LibraryGenie is a Kodi addon that utilizes artificial intelligence to enable users to query a media library to be able to setup lists for use in kodi. Users can simply describe their search criteria in plain English, and the addon will consult the LLM, get an RPC call, call it and store the results to then be used in kodi lists.

## Features:
- **Natural Language Input**: Users can input queries in plain English without needing to know RPC syntax.
- **Streamin Addons**: While not searchable, users can use context menu to manually add any addon listitem to a list.
- **Exception flagging**: In any such list, user may use context menu option to block specific entries from the list.
- **Interactive Interface**: Users can refine queries based on initial results or receive suggestions for refining search criteria, so you can tweak the RPC generating the list easily.
- **Customization Options**: Advanced users can access and drietly adjust the RPC queries manually.

## Installation:
1. Download the LibraryGenie addon ZIP file from the releases page.
2. Launch Kodi and navigate to "Add-ons" > "Install from ZIP file".
3. Select the downloaded ZIP file and wait for the installation to complete.
4. Once installed, configure the addon settings to connect to your database.

## Usage:
1. Open the LibraryGenie addon from the Kodi Add-ons menu.
2. Use the interface to input your query in natural language or select from predefined templates.
3. Review the results displayed in the interface.

## Error Handling:
- If a generated RPC query produces an error when executed against the database, the addon will alert the user and offer to attempt to fix the query automatically via the LLM.

## Configuration:
- **AI Model Settings**: Adjust settings related to the ChatGPT AI model, such as API key and parameters.
- **No AI required**: Without an AI in use, users can still manually build lists, add individual media, etc.

## Support:
For any issues, feedback, or feature requests, please open an issue on the GitHub repository.

## License:
This project is licensed under the MIT License - see the LICENSE file for details.
