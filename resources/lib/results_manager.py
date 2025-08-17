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

                    if is_plugin_item:
                        utils.log(f"Processing plugin item: {item.get('title', 'Unknown')}", "DEBUG")

                    # Build ListItem using the centralized builder
                    from resources.lib.listitem_builder import ListItemBuilder
                    li = ListItemBuilder.build_video_item(item, is_search_history=is_search_history)

                    # Determine the appropriate URL for this item
                    if is_plugin_item and item.get('file'):
                        # For plugin items, use the original file path if available
                        item_url = item['file']
                        utils.log(f"Using plugin file path: {item_url}", "DEBUG")
                    elif item.get('play') and not item.get('play').startswith('plugin_item://'):
                        # Use play URL if it's not a stored plugin item reference
                        item_url = item['play']
                    elif item.get('file'):
                        # Fallback to file path
                        item_url = item['file']
                    else:
                        # Skip items without valid URLs
                        utils.log(f"Skipping item without valid URL: {item.get('title', 'Unknown')}", "WARNING")
                        continue

                    display_items.append((item_url, li, False))  # False = not a folder

                except Exception as item_error:
                    utils.log(f"Error processing list item {item.get('id', 'unknown')}: {str(item_error)}", "ERROR")
                    continue

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Created {len(display_items)} display items ===", "DEBUG")
            return display_items

        except Exception as e:
            utils.log(f"Error in build_display_items_for_list: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return []