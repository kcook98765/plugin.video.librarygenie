
"""Shortlist addon importer for LibraryGenie"""

import json
import xbmc
import xbmcgui
import xbmcaddon
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager

class ShortlistImporter:
    """Handles importing data from Shortlist addon"""
    
    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)
    
    def _rpc(self, method, params):
        """Execute JSON-RPC request"""
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = xbmc.executeJSONRPC(json.dumps(req))
        data = json.loads(resp)
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result", {})
    
    def _get_dir(self, url, start=0, end=200, props=None):
        """Get directory contents via JSON-RPC with pagination"""
        if props is None:
            props = ["title", "art", "thumbnail", "year", "rating", "plot", "plotoutline", "filetype", "streamdetails", "dateadded"]
        
        result = self._rpc("Files.GetDirectory", {
            "directory": url,
            "media": "video", 
            "properties": props,
            "limits": {"start": start, "end": end}
        })
        
        files = result.get("files", [])
        lims = result.get("limits", {"total": len(files), "end": end})
        total = lims.get("total", len(files))
        
        # Paginate if needed
        while len(files) < total:
            start = len(files)
            chunk = self._rpc("Files.GetDirectory", {
                "directory": url,
                "media": "video",
                "properties": props,
                "limits": {"start": start, "end": start + 200}
            }).get("files", [])
            if not chunk:
                break
            files.extend(chunk)
        
        return files
    
    def check_shortlist_available(self):
        """Check if Shortlist addon is installed and available"""
        try:
            addon = xbmcaddon.Addon('plugin.program.shortlist')
            return True
        except RuntimeError:
            return False
    
    def scrape_shortlist_data(self, progress_callback=None):
        """Scrape all data from Shortlist addon"""
        utils.log("Starting Shortlist data scraping", "INFO")
        
        base_url = "plugin://plugin.program.shortlist/"
        lists = []
        
        try:
            if progress_callback:
                progress_callback.update(10, "Discovering Shortlist directories...")
            
            # 1) Discover lists (directories)
            directory_entries = self._get_dir(base_url)
            total_lists = len([e for e in directory_entries if e.get("filetype") == "directory"])
            
            if progress_callback:
                progress_callback.update(20, f"Found {total_lists} lists. Processing...")
            
            processed_lists = 0
            
            for entry in directory_entries:
                if entry.get("filetype") != "directory":
                    continue
                
                list_name = entry.get("label") or entry.get("title") or "Unnamed"
                list_url = entry.get("file")
                
                utils.log(f"Processing Shortlist list: {list_name}", "DEBUG")
                
                # 2) Fetch items in this list
                try:
                    items_raw = self._get_dir(list_url)
                    items = []
                    
                    for it in items_raw:
                        if it.get("filetype") == "directory":
                            continue
                        
                        # Extract duration from streamdetails if available
                        duration = None
                        streamdetails = it.get("streamdetails", {})
                        if streamdetails and "video" in streamdetails and streamdetails["video"]:
                            duration = streamdetails["video"][0].get("duration")
                        
                        item = {
                            "label": it.get("label") or it.get("title"),
                            "title": it.get("title") or it.get("label"),
                            "file": it.get("file"),
                            "year": it.get("year"),
                            "rating": it.get("rating"),
                            "duration": duration,
                            "plot": it.get("plot"),
                            "plotoutline": it.get("plotoutline"),
                            "art": it.get("art", {}),
                            "position": len(items)  # Preserve order
                        }
                        items.append(item)
                    
                    lists.append({
                        "name": list_name,
                        "url": list_url,
                        "items": items
                    })
                    
                    utils.log(f"Found {len(items)} items in list: {list_name}", "DEBUG")
                    
                except Exception as e:
                    utils.log(f"Error processing list {list_name}: {str(e)}", "ERROR")
                    continue
                
                processed_lists += 1
                if progress_callback:
                    progress = 20 + int((processed_lists / total_lists) * 60)
                    progress_callback.update(progress, f"Processed {processed_lists}/{total_lists} lists...")
                    if progress_callback.iscanceled():
                        return None
            
            utils.log(f"Successfully scraped {len(lists)} lists from Shortlist", "INFO")
            return lists
            
        except Exception as e:
            utils.log(f"Error scraping Shortlist data: {str(e)}", "ERROR")
            raise
    
    def clear_imported_data(self):
        """Clear existing imported data"""
        utils.log("Clearing existing imported data", "INFO")
        
        # Find the "Imported Lists" folder
        imported_folder_id = self.db_manager.get_folder_id_by_name("Imported Lists")
        
        if imported_folder_id:
            # Get all subfolders and lists in the Imported Lists folder
            subfolders = self.db_manager.fetch_folders(imported_folder_id)
            lists = self.db_manager.fetch_lists_by_folder(imported_folder_id)
            
            # Delete all lists first (including their media items)
            for list_item in lists:
                self.db_manager.delete_data('list_media', f"list_id = {list_item['id']}")
                self.db_manager.delete_data('lists', f"id = {list_item['id']}")
                utils.log(f"Deleted list: {list_item['name']}", "DEBUG")
            
            # Delete all subfolders recursively
            for folder in subfolders:
                self._delete_folder_recursive(folder['id'])
            
            utils.log("Cleared all existing imported data", "INFO")
    
    def _delete_folder_recursive(self, folder_id):
        """Recursively delete a folder and all its contents"""
        # Get subfolders and lists
        subfolders = self.db_manager.fetch_folders(folder_id)
        lists = self.db_manager.fetch_lists_by_folder(folder_id)
        
        # Delete lists
        for list_item in lists:
            self.db_manager.delete_data('list_media', f"list_id = {list_item['id']}")
            self.db_manager.delete_data('lists', f"id = {list_item['id']}")
        
        # Recursively delete subfolders
        for subfolder in subfolders:
            self._delete_folder_recursive(subfolder['id'])
        
        # Delete the folder itself
        self.db_manager.delete_data('folders', f"id = {folder_id}")
    
    def _enhance_item_with_kodi_data(self, item):
        """Try to match item with Kodi library and enhance with complete data"""
        from resources.lib.jsonrpc_manager import JSONRPC
        
        title = item.get('title', '').strip()
        year = item.get('year')
        
        if not title:
            return item
        
        try:
            jsonrpc = JSONRPC()
            utils.log(f"Checking Kodi library for: {title} ({year})", "DEBUG")
            
            # Try to find movie in Kodi library by title and year
            filter_obj = {
                'field': 'title',
                'operator': 'is', 
                'value': title
            }
            
            # Add year filter if available
            if year and str(year).isdigit():
                filter_obj = {
                    'and': [
                        {'field': 'title', 'operator': 'is', 'value': title},
                        {'field': 'year', 'operator': 'is', 'value': str(year)}
                    ]
                }
            
            response = jsonrpc.search_movies(filter_obj)
            
            if 'result' in response and 'movies' in response['result']:
                movies = response['result']['movies']
                
                if movies:
                    # Found match in Kodi library - get comprehensive details
                    kodi_movie = movies[0]  # Take first match
                    movie_id = kodi_movie.get('movieid')
                    
                    if movie_id:
                        utils.log(f"Found Kodi library match for '{title}' - getting full details", "DEBUG")
                        
                        # Get comprehensive movie details
                        details_response = jsonrpc.get_movie_details_comprehensive(movie_id)
                        
                        if 'result' in details_response and 'moviedetails' in details_response['result']:
                            full_details = details_response['result']['moviedetails']
                            
                            # Enhance item with complete Kodi data
                            enhanced_item = {
                                'title': full_details.get('title', item.get('title', '')),
                                'year': full_details.get('year', item.get('year', 0)),
                                'rating': full_details.get('rating', item.get('rating', 0.0)),
                                'plot': full_details.get('plot', item.get('plot', '')),
                                'plotoutline': full_details.get('plotoutline', item.get('plotoutline', '')),
                                'duration': full_details.get('runtime', item.get('duration', 0)),
                                'file': full_details.get('file', item.get('file', '')),
                                'art': full_details.get('art', item.get('art', {})),
                                'position': item.get('position', 0),
                                'genre': ' / '.join(full_details.get('genre', [])) if full_details.get('genre') else '',
                                'director': ' / '.join(full_details.get('director', [])) if full_details.get('director') else '',
                                'writer': ' / '.join(full_details.get('writer', [])) if full_details.get('writer') else '',
                                'cast': json.dumps(full_details.get('cast', [])),
                                'studio': ' / '.join(full_details.get('studio', [])) if full_details.get('studio') else '',
                                'country': ' / '.join(full_details.get('country', [])) if full_details.get('country') else '',
                                'tagline': full_details.get('tagline', ''),
                                'trailer': full_details.get('trailer', ''),
                                'mpaa': full_details.get('mpaa', ''),
                                'votes': full_details.get('votes', 0),
                                'premiered': full_details.get('premiered', ''),
                                'dateadded': full_details.get('dateadded', ''),
                                'imdbnumber': full_details.get('imdbnumber', ''),
                                'uniqueid': full_details.get('uniqueid', {}),
                                'kodi_id': movie_id,
                                'in_kodi_library': True
                            }
                            
                            utils.log(f"Enhanced '{title}' with complete Kodi library data", "INFO")
                            return enhanced_item
            
            # No match found in Kodi library - use original Shortlist data
            utils.log(f"No Kodi library match found for '{title}' - using Shortlist data", "DEBUG")
            item['in_kodi_library'] = False
            return item
            
        except Exception as e:
            utils.log(f"Error checking Kodi library for '{title}': {str(e)}", "ERROR")
            item['in_kodi_library'] = False
            return item

    def import_to_librarygenie(self, shortlist_data, progress_callback=None):
        """Import scraped Shortlist data into LibraryGenie with Kodi library enhancement"""
        utils.log("Starting import to LibraryGenie with Kodi library matching", "INFO")
        
        try:
            # Clear existing imported data first
            self.clear_imported_data()
            
            if progress_callback:
                progress_callback.update(10, "Creating Imported Lists folder...")
            
            # Create or get "Imported Lists" folder at root level
            imported_folder_id = self.db_manager.get_folder_id_by_name("Imported Lists")
            if not imported_folder_id:
                imported_folder_id = self.db_manager.create_folder("Imported Lists", None)
                utils.log("Created 'Imported Lists' folder", "INFO")
            
            total_lists = len(shortlist_data)
            total_items = sum(len(list_data["items"]) for list_data in shortlist_data)
            imported_lists = 0
            processed_items = 0
            kodi_matches = 0
            
            for list_data in shortlist_data:
                list_name = list_data["name"]
                items = list_data["items"]
                
                if progress_callback:
                    progress = 10 + int((imported_lists / total_lists) * 80)
                    progress_callback.update(progress, f"Processing list: {list_name}")
                    if progress_callback.iscanceled():
                        return False
                
                # Create the list under "Imported Lists" folder
                list_id = self.db_manager.create_list(list_name, imported_folder_id)
                utils.log(f"Created list: {list_name} (ID: {list_id})", "DEBUG")
                
                # Process items with Kodi library enhancement
                for item in items:
                    try:
                        if progress_callback:
                            item_progress = 10 + int((processed_items / total_items) * 80)
                            progress_callback.update(item_progress, f"Enhancing: {item.get('title', 'Unknown')}")
                            if progress_callback.iscanceled():
                                return False
                        
                        # Enhance item with Kodi library data if available
                        enhanced_item = self._enhance_item_with_kodi_data(item)
                        
                        if enhanced_item.get('in_kodi_library'):
                            kodi_matches += 1
                        
                        # Create comprehensive media item entry
                        media_data = {
                            'title': enhanced_item.get('title', 'Unknown'),
                            'year': enhanced_item.get('year') or 0,
                            'rating': enhanced_item.get('rating') or 0.0,
                            'plot': enhanced_item.get('plot', ''),
                            'plotoutline': enhanced_item.get('plotoutline', ''),
                            'duration': enhanced_item.get('duration') or 0,
                            'file_url': enhanced_item.get('file', ''),
                            'art_data': json.dumps(enhanced_item.get('art', {})),
                            'source': 'shortlist_import',
                            'media_type': 'movie',
                            'genre': enhanced_item.get('genre', ''),
                            'director': enhanced_item.get('director', ''),
                            'writer': enhanced_item.get('writer', ''),
                            'cast': enhanced_item.get('cast', '[]'),
                            'studio': enhanced_item.get('studio', ''),
                            'country': enhanced_item.get('country', ''),
                            'tagline': enhanced_item.get('tagline', ''),
                            'trailer': enhanced_item.get('trailer', ''),
                            'mpaa': enhanced_item.get('mpaa', ''),
                            'votes': enhanced_item.get('votes', 0),
                            'premiered': enhanced_item.get('premiered', ''),
                            'dateadded': enhanced_item.get('dateadded', ''),
                            'imdbnumber': enhanced_item.get('imdbnumber', ''),
                            'kodi_id': enhanced_item.get('kodi_id', 0),
                            'in_kodi_library': enhanced_item.get('in_kodi_library', False)
                        }
                        
                        media_id = self.db_manager.create_media_item(media_data)
                        
                        # Add to list
                        self.db_manager.add_media_to_list(list_id, media_id, enhanced_item.get('position', 0))
                        
                        processed_items += 1
                        
                    except Exception as e:
                        utils.log(f"Error importing item {item.get('title', 'Unknown')}: {str(e)}", "ERROR")
                        processed_items += 1
                        continue
                
                imported_lists += 1
                utils.log(f"Imported list '{list_name}' with {len(items)} items", "INFO")
            
            utils.log(f"Successfully imported {imported_lists} lists with {kodi_matches}/{total_items} Kodi library matches", "INFO")
            return True
            
        except Exception as e:
            utils.log(f"Error importing to LibraryGenie: {str(e)}", "ERROR")
            raise
    
    def run_import(self):
        """Main import process with progress dialog"""
        if not self.check_shortlist_available():
            xbmcgui.Dialog().ok(
                "LibraryGenie", 
                "Shortlist addon is not installed or not available."
            )
            return False
        
        # Confirm import
        if not xbmcgui.Dialog().yesno(
            "Import From Shortlist",
            "This will import all your Shortlist data into LibraryGenie.\n\n"
            "Any existing imported data will be replaced.\n\n"
            "Continue?"
        ):
            return False
        
        progress = xbmcgui.DialogProgress()
        progress.create("Importing From Shortlist", "Starting import...")
        
        try:
            # Scrape Shortlist data
            shortlist_data = self.scrape_shortlist_data(progress)
            
            if shortlist_data is None:
                progress.close()
                return False
            
            if not shortlist_data:
                progress.close()
                xbmcgui.Dialog().ok("LibraryGenie", "No lists found in Shortlist addon.")
                return False
            
            # Import to LibraryGenie
            success = self.import_to_librarygenie(shortlist_data, progress)
            
            progress.update(100, "Import completed!")
            xbmc.sleep(1000)
            progress.close()
            
            if success:
                # Calculate enhancement statistics for user feedback
                total_items = sum(len(list_data["items"]) for list_data in shortlist_data)
                
                xbmcgui.Dialog().ok(
                    "Import Complete",
                    f"Successfully imported {len(shortlist_data)} lists from Shortlist.\n\n"
                    f"Items enhanced with Kodi library data where available.\n\n"
                    "You can find them under 'Imported Lists' in your LibraryGenie root folder."
                )
                # Refresh the container to show new data
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                xbmcgui.Dialog().ok("Import Error", "Import was cancelled or failed.")
                return False
                
        except Exception as e:
            progress.close()
            utils.log(f"Import failed: {str(e)}", "ERROR")
            xbmcgui.Dialog().ok("Import Error", f"Import failed: {str(e)}")
            return False

def import_from_shortlist():
    """Entry point for importing from Shortlist"""
    importer = ShortlistImporter()
    return importer.run_import()
