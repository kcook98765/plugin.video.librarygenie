
import json
import xbmc
import xbmcgui
from resources.lib import utils
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib.jsonrpc_manager import JSONRPC


class ShortlistImporter:
    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)
        self.jsonrpc = JSONRPC()

    def _rpc(self, method, params):
        """Execute JSON-RPC call with error handling"""
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = xbmc.executeJSONRPC(json.dumps(req))
        data = json.loads(resp)
        if "error" in data:
            utils.log(f"JSON-RPC error: {data['error']}", "ERROR")
            raise RuntimeError(data["error"])
        return data.get("result", {})

    def get_dir(self, url, start=0, end=200, props=None):
        """Get directory contents with pagination using progressive property fallback"""
        utils.log(f"Getting directory: {url} (start={start}, end={end})", "DEBUG")
        
        # Define property sets in order of preference (most comprehensive to most basic)
        property_sets = [
            # Comprehensive set for maximum details
            ["title", "year", "rating", "plot", "plotoutline", "genre", "director", 
             "cast", "duration", "runtime", "art", "thumbnail", "fanart", "poster", 
             "tagline", "studio", "mpaa", "writer", "country", "premiered", 
             "dateadded", "votes", "trailer", "file", "filetype"],
            
            # Standard set with common properties
            ["title", "year", "rating", "plot", "plotoutline", "genre", "director", 
             "cast", "duration", "art", "thumbnail", "fanart", "file", "filetype"],
            
            # Reduced set without potentially problematic properties
            ["title", "year", "rating", "plot", "genre", "director", "art", "filetype"],
            
            # Basic set with core properties
            ["title", "year", "rating", "plot", "filetype"],
            
            # Minimal set - last resort
            ["title", "filetype"]
        ]
        
        # If specific props provided, try those first
        if props is not None:
            property_sets.insert(0, props)
        
        # Try each property set until one works
        for i, prop_set in enumerate(property_sets):
            try:
                utils.log(f"Trying property set {i+1}/{len(property_sets)}: {len(prop_set)} properties", "DEBUG")
                
                result = self._rpc("Files.GetDirectory", {
                    "directory": url,
                    "media": "video", 
                    "properties": prop_set,
                    "limits": {"start": start, "end": end}
                })
                
                utils.log(f"Successfully used property set {i+1} with {len(prop_set)} properties", "INFO")
                break
                
            except RuntimeError as e:
                error_str = str(e)
                utils.log(f"Property set {i+1} failed: {error_str}", "DEBUG")
                
                # If this is the last property set, re-raise the error
                if i == len(property_sets) - 1:
                    utils.log("All property sets failed, re-raising last error", "ERROR")
                    raise
                
                # Continue to next property set
                continue
        
        files = result.get("files", [])
        lims = result.get("limits", {"total": len(files), "end": end})
        total = lims.get("total", len(files))
        
        utils.log(f"Got {len(files)} files, total: {total}", "DEBUG")
        
        # Paginate if needed
        while len(files) < total:
            start = len(files)
            utils.log(f"Paginating: start={start}", "DEBUG")
            chunk = self._rpc("Files.GetDirectory", {
                "directory": url,
                "media": "video",
                "properties": props,
                "limits": {"start": start, "end": start + 200}
            }).get("files", [])
            if not chunk:
                break
            files.extend(chunk)
            
        utils.log(f"Final file count: {len(files)}", "DEBUG")
        return files

    def is_shortlist_installed(self):
        """Check if Shortlist addon is installed"""
        try:
            result = self._rpc("Addons.GetAddonDetails", {
                "addonid": "plugin.program.shortlist",
                "properties": ["enabled"]
            })
            is_enabled = result.get("addon", {}).get("enabled", False)
            utils.log(f"Shortlist addon enabled: {is_enabled}", "DEBUG")
            return is_enabled
        except Exception as e:
            utils.log(f"Shortlist addon not found: {str(e)}", "DEBUG")
            return False

    def scrape_shortlist(self):
        """Scrape all lists from Shortlist addon"""
        base = "plugin://plugin.program.shortlist/"
        lists = []
        
        utils.log("Starting Shortlist scrape", "INFO")
        
        try:
            # Discover lists (directories)
            entries = self.get_dir(base)
            utils.log(f"Found {len(entries)} top-level entries in Shortlist", "INFO")
            
            for entry in entries:
                if entry.get("filetype") != "directory":
                    utils.log(f"Skipping non-directory entry: {entry.get('label')}", "DEBUG")
                    continue
                    
                list_name = entry.get("label") or entry.get("title") or "Unnamed"
                list_url = entry.get("file")
                
                utils.log(f"Processing Shortlist: {list_name} ({list_url})", "INFO")
                
                # Fetch items in this list
                items_raw = self.get_dir(list_url)
                utils.log(f"Found {len(items_raw)} raw items in list '{list_name}'", "DEBUG")
                
                items = []
                for it in items_raw:
                    if it.get("filetype") == "directory":
                        utils.log(f"Skipping directory item: {it.get('label')}", "DEBUG")
                        continue
                        
                    # Extract all available data from Shortlist item
                    item_data = {
                        "label": it.get("label") or it.get("title"),
                        "title": it.get("title") or it.get("label"),
                        "file": it.get("file"),
                        "year": it.get("year"),
                        "rating": it.get("rating"),
                        "duration": it.get("duration") or it.get("runtime"),
                        "plot": it.get("plot"),
                        "plotoutline": it.get("plotoutline"),
                        "art": it.get("art", {}),
                        "position": len(items),
                        
                        # Additional metadata that might be available
                        "genre": it.get("genre"),
                        "director": it.get("director"),
                        "cast": it.get("cast"),
                        "tagline": it.get("tagline"),
                        "studio": it.get("studio"),
                        "mpaa": it.get("mpaa"),
                        "writer": it.get("writer"),
                        "country": it.get("country"),
                        "premiered": it.get("premiered"),
                        "dateadded": it.get("dateadded"),
                        "votes": it.get("votes"),
                        "trailer": it.get("trailer"),
                        "thumbnail": it.get("thumbnail"),
                        "fanart": it.get("fanart"),
                        "poster": it.get("poster")
                    }
                    
                    # Extract duration from streamdetails if available and not already set
                    if not item_data["duration"]:
                        streamdetails = it.get("streamdetails", {})
                        if streamdetails and "video" in streamdetails and len(streamdetails["video"]) > 0:
                            item_data["duration"] = streamdetails["video"][0].get("duration")
                    
                    # Log what we actually extracted
                    non_empty_fields = {k: v for k, v in item_data.items() if v not in (None, "", [], {})}
                    utils.log(f"Extracted {len(non_empty_fields)} fields for: {item_data['title']} ({item_data['year']})", "DEBUG")
                    utils.log(f"Available fields: {list(non_empty_fields.keys())}", "DEBUG")
                    
                    items.append(item_data)
                
                if items:  # Only add lists that have items
                    lists.append({"name": list_name, "url": list_url, "items": items})
                    utils.log(f"Added list '{list_name}' with {len(items)} items", "INFO")
                else:
                    utils.log(f"Skipping empty list '{list_name}'", "DEBUG")
                    
        except Exception as e:
            utils.log(f"Error scraping Shortlist: {str(e)}", "ERROR")
            raise
            
        utils.log(f"Shortlist scrape complete: {len(lists)} lists found", "INFO")
        return lists

    def lookup_in_kodi_library(self, title, year):
        """Try to find movie in Kodi library and return full data"""
        utils.log(f"Looking up '{title}' ({year}) in Kodi library", "DEBUG")
        
        try:
            # Search for movie in Kodi library
            movies = self.jsonrpc.get_movies()
            
            for movie in movies:
                movie_title = movie.get('title', '').lower()
                movie_year = movie.get('year', 0)
                
                # Simple title matching with year verification
                if (title.lower() in movie_title or movie_title in title.lower()) and \
                   (not year or abs(movie_year - year) <= 1):
                    utils.log(f"Found library match: {movie['title']} ({movie['year']}) - ID: {movie['movieid']}", "INFO")
                    
                    # Get full movie details
                    full_movie = self.jsonrpc.get_movie_details(movie['movieid'])
                    if full_movie:
                        utils.log(f"Retrieved full library data for: {full_movie.get('title')}", "DEBUG")
                        return full_movie
                        
        except Exception as e:
            utils.log(f"Error looking up movie in library: {str(e)}", "DEBUG")
            
        utils.log(f"No library match found for '{title}' ({year})", "DEBUG")
        return None

    def convert_shortlist_item_to_media_dict(self, item, kodi_movie=None):
        """Convert Shortlist item to LibraryGenie media dictionary format"""
        if kodi_movie:
            # Use Kodi library data
            utils.log(f"Converting library movie: {kodi_movie.get('title')}", "DEBUG")
            media_dict = {
                'title': kodi_movie.get('title', ''),
                'year': kodi_movie.get('year', 0),
                'plot': kodi_movie.get('plot', ''),
                'rating': kodi_movie.get('rating', 0.0),
                'duration': kodi_movie.get('runtime', 0) * 60 if kodi_movie.get('runtime') else 0,  # Convert minutes to seconds
                'genre': ', '.join(kodi_movie.get('genre', [])) if kodi_movie.get('genre') else '',
                'director': ', '.join(kodi_movie.get('director', [])) if kodi_movie.get('director') else '',
                'cast': ', '.join([actor.get('name', '') for actor in kodi_movie.get('cast', [])[:5]]),  # Limit to 5 actors
                'studio': ', '.join(kodi_movie.get('studio', [])) if kodi_movie.get('studio') else '',
                'mpaa': kodi_movie.get('mpaa', ''),
                'tagline': kodi_movie.get('tagline', ''),
                'writer': ', '.join(kodi_movie.get('writer', [])) if kodi_movie.get('writer') else '',
                'country': ', '.join(kodi_movie.get('country', [])) if kodi_movie.get('country') else '',
                'premiered': kodi_movie.get('premiered', ''),
                'dateadded': kodi_movie.get('dateadded', ''),
                'votes': kodi_movie.get('votes', 0),
                'trailer': kodi_movie.get('trailer', ''),
                'path': kodi_movie.get('file', ''),
                'play': kodi_movie.get('file', ''),
                'kodi_id': kodi_movie.get('movieid', 0),
                'media_type': 'movie',
                'source': 'kodi_library',
                'imdbnumber': '',
                'thumbnail': '',
                'poster': '',
                'fanart': '',
                'art': '',
                'uniqueid': '',
                'stream_url': '',
                'status': 'available'
            }
            
            # Extract art
            art = kodi_movie.get('art', {})
            media_dict['thumbnail'] = art.get('thumb', '')
            media_dict['poster'] = art.get('poster', '')
            media_dict['fanart'] = art.get('fanart', '')
            media_dict['art'] = json.dumps(art) if art else ''
            
            # Extract IMDb ID from uniqueid
            uniqueid = kodi_movie.get('uniqueid', {})
            if 'imdb' in uniqueid:
                media_dict['imdbnumber'] = uniqueid['imdb']
            media_dict['uniqueid'] = json.dumps(uniqueid) if uniqueid else ''
            
        else:
            # Use Shortlist data - preserve all available information
            utils.log(f"Converting Shortlist item: {item.get('title')}", "DEBUG")
            
            # Helper function to safely convert lists to strings
            def list_to_string(value):
                if isinstance(value, list):
                    return ', '.join(str(v) for v in value if v)
                return str(value) if value else ''
            
            media_dict = {
                'title': item.get('title', '') or item.get('label', ''),
                'year': item.get('year', 0) or 0,
                'plot': item.get('plot', '') or item.get('plotoutline', ''),
                'rating': item.get('rating', 0.0) or 0.0,
                'duration': item.get('duration', 0) or 0,
                'genre': list_to_string(item.get('genre', '')),
                'director': list_to_string(item.get('director', '')),
                'cast': list_to_string(item.get('cast', '')),
                'studio': list_to_string(item.get('studio', '')),
                'mpaa': item.get('mpaa', ''),
                'tagline': item.get('tagline', ''),
                'writer': list_to_string(item.get('writer', '')),
                'country': list_to_string(item.get('country', '')),
                'premiered': item.get('premiered', ''),
                'dateadded': item.get('dateadded', ''),
                'votes': item.get('votes', 0) or 0,
                'trailer': item.get('trailer', ''),
                'path': item.get('file', ''),
                'play': item.get('file', ''),
                'kodi_id': 0,
                'media_type': 'movie',
                'source': 'shortlist_import',
                'imdbnumber': '',
                'thumbnail': '',
                'poster': '',
                'fanart': '',
                'art': '',
                'uniqueid': '',
                'stream_url': '',
                'status': 'available'
            }
            
            # Extract art from Shortlist with multiple fallback sources
            art = item.get('art', {})
            if art:
                media_dict['thumbnail'] = art.get('thumb', '') or art.get('icon', '') or item.get('thumbnail', '')
                media_dict['poster'] = art.get('poster', '') or item.get('poster', '')
                media_dict['fanart'] = art.get('fanart', '') or item.get('fanart', '')
                media_dict['art'] = json.dumps(art)
            else:
                # Try direct properties if art object is empty
                media_dict['thumbnail'] = item.get('thumbnail', '')
                media_dict['poster'] = item.get('poster', '')
                media_dict['fanart'] = item.get('fanart', '')
        
        utils.log(f"Converted media dict for: {media_dict['title']} ({media_dict['year']}) - Source: {media_dict['source']}", "DEBUG")
        return media_dict

    def clear_imported_lists_folder(self, imported_folder_id):
        """Clear all contents of the Imported Lists folder"""
        utils.log(f"Clearing contents of Imported Lists folder (ID: {imported_folder_id})", "INFO")
        
        # Get all subfolders and lists in the imported folder
        subfolders = self.db_manager.fetch_folders(imported_folder_id)
        lists = self.db_manager.fetch_lists(imported_folder_id)
        
        # Delete all lists first
        for list_item in lists:
            utils.log(f"Deleting list: {list_item['name']} (ID: {list_item['id']})", "DEBUG")
            self.db_manager.delete_list(list_item['id'])
        
        # Delete all subfolders (this will cascade to their contents)
        for folder in subfolders:
            utils.log(f"Deleting folder: {folder['name']} (ID: {folder['id']})", "DEBUG")
            self.db_manager.delete_folder(folder['id'])
        
        utils.log("Imported Lists folder cleared", "INFO")

    def import_from_shortlist(self):
        """Main import function"""
        utils.log("=== Starting Shortlist import process ===", "INFO")
        
        # Check if Shortlist is installed
        if not self.is_shortlist_installed():
            xbmcgui.Dialog().notification("LibraryGenie", "Shortlist addon not found or disabled", xbmcgui.NOTIFICATION_WARNING)
            return False
        
        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("Importing from Shortlist", "Scanning Shortlist addon...")
        progress.update(10)
        
        try:
            # Scrape Shortlist data
            lists = self.scrape_shortlist()
            if not lists:
                progress.close()
                xbmcgui.Dialog().notification("LibraryGenie", "No lists found in Shortlist", xbmcgui.NOTIFICATION_WARNING)
                return False
            
            progress.update(30, "Creating Imported Lists folder...")
            
            # Ensure "Imported Lists" folder exists
            imported_folder_id = self.db_manager.ensure_folder_exists("Imported Lists", None)
            utils.log(f"Imported Lists folder ID: {imported_folder_id}", "DEBUG")
            
            # Clear existing data in the folder
            progress.update(40, "Clearing existing imported data...")
            self.clear_imported_lists_folder(imported_folder_id)
            
            # Process each list
            total_lists = len(lists)
            for i, shortlist_list in enumerate(lists):
                list_name = shortlist_list['name']
                items = shortlist_list['items']
                
                progress_percent = 50 + int((i / total_lists) * 40)
                progress.update(progress_percent, f"Processing list: {list_name}")
                
                utils.log(f"Processing list {i+1}/{total_lists}: {list_name} ({len(items)} items)", "INFO")
                
                if progress.iscanceled():
                    break
                
                # Create list in LibraryGenie
                list_id = self.db_manager.create_list(list_name, imported_folder_id)
                utils.log(f"Created LibraryGenie list: {list_name} (ID: {list_id})", "INFO")
                
                # Process each item in the list
                for j, item in enumerate(items):
                    item_title = item.get('title') or item.get('label', 'Unknown')
                    item_year = item.get('year', 0)
                    
                    utils.log(f"Processing item {j+1}/{len(items)}: {item_title} ({item_year})", "DEBUG")
                    
                    # Try to find in Kodi library first
                    kodi_movie = None
                    if item_title and item_year:
                        kodi_movie = self.lookup_in_kodi_library(item_title, item_year)
                    
                    # Convert to media dict
                    media_dict = self.convert_shortlist_item_to_media_dict(item, kodi_movie)
                    
                    # Add to list
                    try:
                        self.db_manager.add_media_to_list(list_id, media_dict)
                        utils.log(f"Added '{media_dict['title']}' to list '{list_name}' - Source: {media_dict['source']}", "DEBUG")
                    except Exception as e:
                        utils.log(f"Error adding item to list: {str(e)}", "ERROR")
            
            progress.update(100, "Import complete!")
            progress.close()
            
            if not progress.iscanceled():
                message = f"Successfully imported {total_lists} lists from Shortlist to 'Imported Lists' folder"
                xbmcgui.Dialog().notification("LibraryGenie", message, xbmcgui.NOTIFICATION_INFO, 5000)
                utils.log(f"=== Shortlist import complete: {total_lists} lists imported ===", "INFO")
                return True
            else:
                utils.log("Shortlist import cancelled by user", "INFO")
                return False
                
        except Exception as e:
            progress.close()
            error_msg = f"Import failed: {str(e)}"
            utils.log(f"Shortlist import error: {error_msg}", "ERROR")
            import traceback
            utils.log(f"Shortlist import traceback: {traceback.format_exc()}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", error_msg, xbmcgui.NOTIFICATION_ERROR, 5000)
            return False


def import_from_shortlist():
    """Standalone function for settings action"""
    importer = ShortlistImporter()
    return importer.import_from_shortlist()
