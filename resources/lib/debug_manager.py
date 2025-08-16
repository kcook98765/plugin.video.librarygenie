
"""Debug manager for LibraryGenie IMDb debugging functionality"""
import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager


class DebugManager:
    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)

    def debug_imdb_info(self, params):
        """Debug IMDB information from database tables"""
        try:
            # Get IMDb ID from params or from currently focused item
            imdb_id = params.get('imdb_id', [None])[0] if params.get('imdb_id') else None
            
            if not imdb_id:
                # Get from focused item using KodiHelper
                from resources.lib.kodi_helper import KodiHelper
                kodi_helper = KodiHelper()
                imdb_id = kodi_helper.get_imdb_from_item()
            
            if not imdb_id or not imdb_id.startswith('tt'):
                xbmcgui.Dialog().ok('LibraryGenie Debug', "No valid IMDb ID found for the current item.")
                return
            
            # Collect debug information from all relevant tables
            debug_info = self._collect_debug_info(imdb_id)
            
            # Display in a large text viewer dialog
            full_text = "\n".join(debug_info)
            
            # Use TextViewer dialog for large scrollable text display
            xbmcgui.Dialog().textviewer(f"LibraryGenie IMDB Debug: {imdb_id}", full_text)
            
        except Exception as e:
            utils.log(f"Error in debug_imdb_info: {str(e)}", "ERROR")
            xbmcgui.Dialog().notification('LibraryGenie', f'Debug error: {str(e)}', xbmcgui.NOTIFICATION_ERROR)

    def _collect_debug_info(self, imdb_id):
        """Collect debug information from all relevant tables"""
        debug_info = []
        debug_info.append(f"=== IMDB DEBUG INFO FOR {imdb_id} ===\n")
        
        # Check media_items table
        debug_info.append("MEDIA_ITEMS TABLE:")
        try:
            media_items = self.db_manager.fetch_data('media_items', f"imdbnumber = '{imdb_id}'")
            if media_items:
                for item in media_items:
                    debug_info.append(f"  ID: {item.get('id')}")
                    debug_info.append(f"  Title: {item.get('title')}")
                    debug_info.append(f"  Year: {item.get('year')}")
                    debug_info.append(f"  Source: {item.get('source')}")
                    debug_info.append(f"  Kodi ID: {item.get('kodi_id')}")
                    debug_info.append(f"  Search Score: {item.get('search_score')}")
                    debug_info.append("  ---")
            else:
                debug_info.append("  No entries found")
        except Exception as e:
            debug_info.append(f"  Error: {str(e)}")
        debug_info.append("")
        
        # Check imdb_exports table
        debug_info.append("IMDB_EXPORTS TABLE:")
        try:
            imdb_exports = self.db_manager.fetch_data('imdb_exports', f"imdb_id = '{imdb_id}'")
            if imdb_exports:
                for item in imdb_exports:
                    debug_info.append(f"  ID: {item.get('id')}")
                    debug_info.append(f"  Title: {item.get('title')}")
                    debug_info.append(f"  Year: {item.get('year')}")
                    debug_info.append(f"  Rating: {item.get('rating')}")
                    debug_info.append(f"  Genres: {item.get('genres')}")
                    debug_info.append("  ---")
            else:
                debug_info.append("  No entries found")
        except Exception as e:
            debug_info.append(f"  Error: {str(e)}")
        debug_info.append("")
        
        # Check which lists contain this IMDB ID
        debug_info.extend(self._get_lists_containing_imdb(imdb_id))
        debug_info.append("")
        
        # Show Kodi library status
        debug_info.extend(self._get_kodi_library_status(imdb_id))
        
        debug_info.append("\n=== END DEBUG INFO ===")
        
        return debug_info

    def _get_lists_containing_imdb(self, imdb_id):
        """Get information about lists containing this IMDB ID"""
        debug_info = ["LISTS CONTAINING THIS IMDB:"]
        
        try:
            # Get media items with this IMDB ID
            media_items = self.db_manager.fetch_data('media_items', f"imdbnumber = '{imdb_id}'")
            if media_items:
                media_item_ids = [str(item['id']) for item in media_items]
                media_ids_str = "(" + ",".join(media_item_ids) + ")"
                
                list_items = self.db_manager.fetch_data('list_items', f"media_item_id IN {media_ids_str}")
                if list_items:
                    list_ids = [str(item['list_id']) for item in list_items]
                    list_ids_str = "(" + ",".join(list_ids) + ")"
                    
                    lists = self.db_manager.fetch_data('lists', f"id IN {list_ids_str}")
                    for list_item in lists:
                        debug_info.append(f"  List ID: {list_item.get('id')}")
                        debug_info.append(f"  List Name: {list_item.get('name')}")
                        debug_info.append(f"  Folder ID: {list_item.get('folder_id')}")
                        debug_info.append("  ---")
                else:
                    debug_info.append("  Not in any lists")
            else:
                debug_info.append("  No media items found")
        except Exception as e:
            debug_info.append(f"  Error: {str(e)}")
            
        return debug_info

    def _get_kodi_library_status(self, imdb_id):
        """Get Kodi library status for the IMDB ID"""
        debug_info = ["KODI LIBRARY STATUS:"]
        
        try:
            from resources.lib.jsonrpc_manager import JSONRPC
            jsonrpc = JSONRPC()
            
            # Try to find in Kodi library by IMDB ID
            response = jsonrpc.execute('VideoLibrary.GetMovies', {
                'properties': ['title', 'year', 'imdbnumber', 'uniqueid'],
                'filter': {
                    'field': 'path',
                    'operator': 'contains',
                    'value': ''  # Get all movies to search
                }
            })
            
            kodi_matches = []
            if 'result' in response and 'movies' in response['result']:
                for movie in response['result']['movies']:
                    movie_imdb = ''
                    
                    # Check uniqueid first
                    if 'uniqueid' in movie and isinstance(movie.get('uniqueid'), dict):
                        movie_imdb = movie.get('uniqueid', {}).get('imdb', '')
                    
                    # Check imdbnumber as fallback
                    if not movie_imdb:
                        movie_imdb = movie.get('imdbnumber', '')
                    
                    if movie_imdb == imdb_id:
                        kodi_matches.append(movie)
            
            if kodi_matches:
                for movie in kodi_matches:
                    debug_info.append(f"  Movie ID: {movie.get('movieid')}")
                    debug_info.append(f"  Title: {movie.get('title')}")
                    debug_info.append(f"  Year: {movie.get('year')}")
                    debug_info.append(f"  IMDb Number: {movie.get('imdbnumber')}")
                    debug_info.append(f"  UniqueID: {movie.get('uniqueid')}")
                    debug_info.append("  ---")
            else:
                debug_info.append("  Not found in Kodi library")
                
        except Exception as e:
            debug_info.append(f"  Error checking Kodi library: {str(e)}")
            
        return debug_info
