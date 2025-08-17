import json
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib import utils
from resources.lib.singleton_base import Singleton

class ResultsManager(Singleton):
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.jsonrpc = JSONRPC()
            from resources.lib.query_manager import QueryManager
            from resources.lib.config_manager import Config
            self.query_manager = QueryManager(Config().db_path)
            self._initialized = True

    def search_movie_by_criteria(self, title, year=None, director=None):
        try:
            return self.query_manager.get_matched_movies(title, year, director)
        except Exception as e:
            utils.log(f"Error searching movies: {e}", "ERROR")
            return []

    def build_display_items_for_list(self, list_id, handle):
        """Build display items for a specific list with proper error handling"""
        try:
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Starting for list_id {list_id} ===", "DEBUG")

            # Get list items from database
            list_items = self.query_manager.fetch_list_items_with_details(list_id)
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Retrieved {len(list_items)} list items ===", "DEBUG")

            if not list_items:
                utils.log(f"=== BUILD_DISPLAY_ITEMS: No items found for list {list_id} ===", "DEBUG")
                return []

            # Log first item structure for debugging
            if list_items:
                first_item = list_items[0]
                utils.log(f"=== BUILD_DISPLAY_ITEMS: First item keys: {list(first_item.keys())} ===", "DEBUG")
                sample_data = {k: v for k, v in list(first_item.items())[:4]}
                utils.log(f"=== BUILD_DISPLAY_ITEMS: First item sample data: {sample_data} ===", "DEBUG")

            # Check if this is from Search History folder
            list_info = self.query_manager.fetch_list_by_id(list_id)
            is_search_history = False
            if list_info and list_info.get('folder_id'):
                search_history_folder_id = self.query_manager.get_folder_id_by_name("Search History")
                is_search_history = (list_info['folder_id'] == search_history_folder_id)

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Is search history: {is_search_history} ===", "DEBUG")

            # Enhance search history items if applicable
            if is_search_history:
                list_items = self._enhance_search_history_items(list_items)

            display_items = []

            for item in list_items:
                try:
                    # Add viewing context to media info for proper context menu handling
                    item['_viewing_list_id'] = list_id
                    item['media_id'] = item.get('id')  # Ensure media_id is set for context menu

                    # Check if this is a plugin item (has plugin_item:// in play field or source is plugin_addon)
                    is_plugin_item = (
                        item.get('source') == 'plugin_addon' or
                        (item.get('play', '').startswith('plugin_item://'))
                    )

                    utils.log(f"Processing item: {item.get('title', 'Unknown')}, Playable: {item.get('playable', 'N/A')}", "DEBUG")

                    # Build ListItem using the centralized builder
                    from resources.lib.listitem_builder import ListItemBuilder
                    li = ListItemBuilder.build_video_item(item, is_search_history=is_search_history)

                    # Determine the appropriate URL for this item
                    item_url = None
                    if item.get('playable', False):
                        if item.get('play'):
                            item_url = item['play']
                        elif item.get('file'):
                            item_url = item['file']
                    else:
                        # If not playable, use an info URL or skip
                        if item.get('imdb_id'): # Assuming imdb_id is available for non-playable items
                            item_url = f"info://{item.get('imdb_id')}"
                        elif item.get('id'): # Fallback to item id if imdb_id is not present
                            item_url = f"info://{item.get('id')}"
                        else:
                            utils.log(f"Skipping non-playable item without identifier: {item.get('title', 'Unknown')}", "WARNING")
                            continue

                    if item_url:
                        utils.log(f"Adding item: {item.get('title', 'Unknown')} with URL: {item_url}", "DEBUG")
                        display_items.append((item_url, li, False))  # False = not a folder
                    else:
                        utils.log(f"Skipping item due to missing URL: {item.get('title', 'Unknown')}", "WARNING")


                except Exception as item_error:
                    utils.log(f"Error processing list item {item.get('id', 'unknown')}: {str(item_error)}", "ERROR")
                    import traceback
                    utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
                    continue

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Created {len(display_items)} display items ===", "DEBUG")
            return display_items

        except Exception as e:
            utils.log(f"Error in build_display_items_for_list: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return []

    def _enhance_search_history_items(self, items):
        """Enhanced processing for search history items with library matching"""
        try:
            utils.log("=== ENHANCING SEARCH HISTORY ITEMS ===", "DEBUG")

            # Initialize JSONRPC for library lookups
            import xbmc
            import json

            enhanced_items = []

            for item in items:
                enhanced_item = dict(item)

                # Check if this item has a library match
                imdb_id = item.get('imdbnumber', '')
                if imdb_id and imdb_id.startswith('tt'):
                    try:
                        # Try to find this movie in the user's library using direct JSONRPC call
                        query = {
                            "jsonrpc": "2.0",
                            "method": "VideoLibrary.GetMovies",
                            "params": {
                                "properties": ["title", "year", "file", "movieid", "imdbnumber"],
                                "filter": {
                                    "field": "imdbnumber",
                                    "operator": "is",
                                    "value": imdb_id
                                }
                            },
                            "id": 1
                        }

                        response = xbmc.executeJSONRPC(json.dumps(query))
                        result = json.loads(response)

                        if result.get('result', {}).get('movies'):
                            library_movie = result['result']['movies'][0]

                            # This is a library match - make it playable
                            enhanced_item['kodi_id'] = library_movie['movieid']
                            enhanced_item['is_playable'] = True
                            enhanced_item['file'] = library_movie.get('file', '')
                            enhanced_item['source'] = 'lib'  # Mark as library source

                            # Set proper play path
                            enhanced_item['play'] = f"movieid://{library_movie['movieid']}"

                            utils.log(f"Found library match for {imdb_id}: {library_movie['title']} (ID: {library_movie['movieid']})", "DEBUG")
                        else:
                            utils.log(f"No library match found for {imdb_id}", "DEBUG")
                            enhanced_item['is_playable'] = False

                    except Exception as e:
                        utils.log(f"Error finding library match for {imdb_id}: {str(e)}", "ERROR")
                        enhanced_item['is_playable'] = False
                else:
                    enhanced_item['is_playable'] = False

                enhanced_items.append(enhanced_item)

            return enhanced_items

        except Exception as e:
            utils.log(f"Error enhancing search history items: {str(e)}", "ERROR")
            return items

    def _find_library_match_by_imdb(self, imdb_id):
        """Find library movie by IMDB ID using JSON-RPC"""
        try:
            # Get all movies from library
            movies_result = self.jsonrpc.VideoLibrary.GetMovies({
                'properties': ['movieid', 'title', 'year', 'imdbnumber', 'uniqueid', 'file'],
                'limits': {'start': 0, 'end': 999999}
            })

            if movies_result and 'movies' in movies_result:
                for movie in movies_result['movies']:
                    # Check direct imdbnumber match
                    if movie.get('imdbnumber') == imdb_id:
                        return movie

                    # Check uniqueid for imdb match
                    uniqueid = movie.get('uniqueid', {})
                    if isinstance(uniqueid, dict) and uniqueid.get('imdb') == imdb_id:
                        return movie

            return None

        except Exception as e:
            utils.log(f"Error finding library match for {imdb_id}: {str(e)}", "ERROR")
            return None