import json
import xbmc
import xbmcgui
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC


class ShortlistImporter:
    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config.db_path)
        self.jsonrpc = JSONRPC()

    def _rpc(self, method, params):
        """Execute JSON-RPC call with error handling and detailed logging"""
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        # Log detailed request information
        utils.log("=== SHORTLIST JSON-RPC REQUEST ===", "INFO")
        utils.log(f"Method: {method}", "INFO")
        utils.log(f"Raw params: {json.dumps(params, indent=2)}", "INFO")
        utils.log(f"Full request JSON: {json.dumps(req, indent=2)}", "INFO")

        # Special logging for Files.GetDirectory calls to analyze properties
        if method == "Files.GetDirectory":
            properties = params.get("properties", [])
            utils.log(f"Properties requested ({len(properties)} total): {properties}", "INFO")
            if len(properties) > 0:
                utils.log(f"Property at index 7: {properties[7] if len(properties) > 7 else 'N/A'}", "INFO")
                utils.log("All properties with indices:", "INFO")
                for i, prop in enumerate(properties):
                    utils.log(f"  [{i}]: {prop}", "INFO")

        resp = xbmc.executeJSONRPC(json.dumps(req))

        # Log raw response
        utils.log("=== SHORTLIST JSON-RPC RESPONSE ===", "INFO")
        utils.log(f"Raw response length: {len(resp)} characters", "INFO")
        utils.log(f"Raw response preview: {resp[:500]}{'...' if len(resp) > 500 else ''}", "INFO")

        data = json.loads(resp)

        # Log parsed response details
        if "error" in data:
            utils.log("=== SHORTLIST JSON-RPC ERROR ANALYSIS ===", "ERROR")
            error = data["error"]
            utils.log(f"Error code: {error.get('code')}", "ERROR")
            utils.log(f"Error message: {error.get('message')}", "ERROR")
            utils.log(f"Error data: {json.dumps(error.get('data', {}), indent=2)}", "ERROR")

            # Special analysis for property validation errors
            if error.get('code') == -32602:  # Invalid params
                error_data = error.get('data', {})
                stack = error_data.get('stack', {})
                utils.log(f"Stack message: {stack.get('message', 'N/A')}", "ERROR")
                utils.log(f"Stack name: {stack.get('name', 'N/A')}", "ERROR")
                utils.log(f"Stack type: {stack.get('type', 'N/A')}", "ERROR")

                # Try to identify which property failed
                if 'index' in stack.get('message', ''):
                    import re
                    match = re.search(r'index\s+(\d+)', stack.get('message', ''))
                    if match:
                        failed_index = int(match.group(1))
                        properties = params.get("properties", [])
                        if failed_index < len(properties):
                            utils.log(f"FAILED PROPERTY at index {failed_index}: {properties[failed_index]}", "ERROR")
                        else:
                            utils.log(f"Failed index {failed_index} is out of range for {len(properties)} properties", "ERROR")

            utils.log("=== END ERROR ANALYSIS ===", "ERROR")
            raise RuntimeError(data["error"])
        else:
            utils.log("=== SHORTLIST JSON-RPC SUCCESS ===", "INFO")
            result = data.get("result", {})
            if isinstance(result, dict):
                utils.log(f"Result keys: {list(result.keys())}", "INFO")
                if "files" in result:
                    utils.log(f"Files returned: {len(result['files'])}", "INFO")
            utils.log("=== END SUCCESS RESPONSE ===", "INFO")

        return data.get("result", {})

    def get_dir(self, url, start=0, end=200, props=None):
        """Get directory contents with pagination using valid List.Fields.Files properties"""
        utils.log(f"Getting directory: {url} (start={start}, end={end})", "DEBUG")

        # Use the most comprehensive valid property set for Files.GetDirectory
        # Based on List.Fields.Files from Kodi JSON-RPC API
        if props is None:
            props = [
                "title",
                "file", 
                "thumbnail",
                "fanart",
                "art",
                "plot",
                "plotoutline", 
                "genre",
                "director",
                "cast",
                "year",
                "rating",
                "duration",
                "runtime",
                "dateadded",
                "resume",
                "streamdetails",
                "trailer",
                "originaltitle",
                "writer", 
                "studio",
                "mpaa",
                "country",
                "imdbnumber"
            ]

        utils.log(f"Using {len(props)} valid List.Fields.Files properties", "DEBUG")
        utils.log(f"Properties: {props}", "DEBUG")

        result = self._rpc("Files.GetDirectory", {
            "directory": url,
            "media": "files",  # Use "files" media type as recommended
            "properties": props,
            "limits": {"start": start, "end": end}
        })

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
                "media": "files",
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
                    # Note: filetype is automatically included in response, poster is in art.poster
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
                        # poster is extracted from art.poster below, not a direct field
                        "poster": it.get("art", {}).get("poster", "") if isinstance(it.get("art"), dict) else ""
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

                    # DEBUG: Log the complete raw item data
                    utils.log(f"=== RAW ITEM DATA DEBUG for '{item_data['title']}' ===", "INFO")
                    for key, value in non_empty_fields.items():
                        utils.log(f"  {key}: {repr(value)[:200]}{'...' if len(repr(value)) > 200 else ''}", "INFO")
                    utils.log("=== END RAW ITEM DATA DEBUG ===", "INFO")

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
        """Try to find movie in Kodi library using comprehensive JSONRPC search"""
        utils.log(f"=== KODI LIBRARY LOOKUP START: '{title}' ({year}) ===", "INFO")

        try:
            # Strategy 1: Direct title search using JSONRPC search capabilities
            utils.log(f"JSONRPC LOOKUP: Attempting direct title search for '{title}'", "INFO")

            search_response = self.jsonrpc.execute("VideoLibrary.GetMovies", {
                "filter": {
                    "field": "title",
                    "operator": "is",
                    "value": title
                },
                "properties": [
                    "title", "year", "plot", "rating", "runtime", "genre", "director", 
                    "cast", "studio", "mpaa", "tagline", "writer", "country", "premiered",
                    "dateadded", "votes", "trailer", "file", "art", "imdbnumber", "uniqueid"
                ]
            })

            utils.log(f"JSONRPC RESPONSE: Direct title search returned: {search_response}", "INFO")

            if 'result' in search_response and 'movies' in search_response['result']:
                movies = search_response['result']['movies']
                utils.log(f"JSONRPC ANALYSIS: Found {len(movies)} exact title matches", "INFO")

                # Look for year match in exact title matches
                for movie in movies:
                    movie_year = movie.get('year', 0)
                    if not year or abs(movie_year - year) <= 1:
                        utils.log(f"JSONRPC SUCCESS: Exact match found - '{movie.get('title')}' ({movie_year})", "INFO")
                        utils.log("JSONRPC DECISION: Using library data instead of shortlist data", "INFO")
                        return movie

            # Strategy 2: Fuzzy title search if exact match fails
            utils.log(f"JSONRPC LOOKUP: Attempting fuzzy title search (contains) for '{title}'", "INFO")

            fuzzy_response = self.jsonrpc.execute("VideoLibrary.GetMovies", {
                "filter": {
                    "field": "title",
                    "operator": "contains",
                    "value": title
                },
                "properties": [
                    "title", "year", "plot", "rating", "runtime", "genre", "director", 
                    "cast", "studio", "mpaa", "tagline", "writer", "country", "premiered",
                    "dateadded", "votes", "trailer", "file", "art", "imdbnumber", "uniqueid"
                ]
            })

            utils.log(f"JSONRPC RESPONSE: Fuzzy search returned: {fuzzy_response}", "INFO")

            if 'result' in fuzzy_response and 'movies' in fuzzy_response['result']:
                movies = fuzzy_response['result']['movies']
                utils.log(f"JSONRPC ANALYSIS: Found {len(movies)} fuzzy title matches", "INFO")

                # Score matches by title similarity and year closeness
                best_match = None
                best_score = 0

                for movie in movies:
                    movie_title = movie.get('title', '').lower()
                    movie_year = movie.get('year', 0)

                    # Title similarity score (simple containment check)
                    title_score = 0
                    if title.lower() in movie_title:
                        title_score = 0.8
                    elif movie_title in title.lower():
                        title_score = 0.6

                    # Year score
                    year_score = 0
                    if year and movie_year:
                        year_diff = abs(movie_year - year)
                        if year_diff == 0:
                            year_score = 0.3
                        elif year_diff == 1:
                            year_score = 0.2
                        elif year_diff <= 2:
                            year_score = 0.1

                    total_score = title_score + year_score

                    utils.log(f"JSONRPC SCORING: '{movie_title}' ({movie_year}) - Title: {title_score}, Year: {year_score}, Total: {total_score}", "INFO")

                    if total_score > best_score and total_score >= 0.6:  # Minimum threshold
                        best_match = movie
                        best_score = total_score

                if best_match:
                    utils.log(f"JSONRPC SUCCESS: Best fuzzy match found - '{best_match.get('title')}' ({best_match.get('year')}) with score {best_score}", "INFO")
                    utils.log("JSONRPC DECISION: Using library data instead of shortlist data", "INFO")
                    return best_match

            # Strategy 3: Fallback to getting all movies and manual search (for older Kodi versions)
            utils.log("JSONRPC LOOKUP: Fallback to manual search through all movies", "INFO")

            all_movies_response = self.jsonrpc.get_movies(0, 100, properties=[
                "title", "year", "plot", "rating", "runtime", "genre", "director", 
                "cast", "studio", "mpaa", "tagline", "writer", "country", "premiered",
                "dateadded", "votes", "trailer", "file", "art", "imdbnumber", "uniqueid"
            ])

            if 'result' in all_movies_response and 'movies' in all_movies_response['result']:
                movies = all_movies_response['result']['movies']
                utils.log(f"JSONRPC ANALYSIS: Searching through {len(movies)} movies manually", "INFO")

                for movie in movies:
                    if isinstance(movie, dict):
                        movie_title = movie.get('title', '').lower()
                        movie_year = movie.get('year', 0)

                        # Manual title matching with year verification
                        if (title.lower() in movie_title or movie_title in title.lower()) and \
                           (not year or abs(movie_year - year) <= 1):
                            utils.log(f"JSONRPC SUCCESS: Manual match found - '{movie.get('title')}' ({movie_year})", "INFO")
                            utils.log("JSONRPC DECISION: Using library data instead of shortlist data", "INFO")
                            return movie

        except Exception as e:
            utils.log(f"JSONRPC ERROR: Library lookup failed: {str(e)}", "ERROR")
            utils.log("JSONRPC DECISION: Will use shortlist data due to lookup error", "INFO")

        utils.log("JSONRPC RESULT: No library match found for '{title}' ({year})", "INFO")
        utils.log("JSONRPC DECISION: Will use shortlist data as no library match exists", "INFO")
        utils.log("=== KODI LIBRARY LOOKUP END ===", "INFO")
        return None

    def safe_convert_int(self, value, default=0):
        """Safely convert value to integer with fallback"""
        if value is None:
            return default
        try:
            if isinstance(value, str):
                # Handle empty strings
                if not value.strip():
                    return default
                # Handle numeric strings
                return int(float(value))  # float first to handle "2.0" -> 2
            elif isinstance(value, (int, float)):
                return int(value)
            else:
                utils.log(f"DATA_CONVERSION: Unexpected type for int conversion: {type(value)} = {value}", "DEBUG")
                return default
        except (ValueError, TypeError):
            utils.log(f"DATA_CONVERSION: Failed to convert '{value}' to int, using default {default}", "DEBUG")
            return default

    def safe_convert_float(self, value, default=0.0):
        """Safely convert value to float with fallback"""
        if value is None:
            return default
        try:
            if isinstance(value, str):
                if not value.strip():
                    return default
                return float(value)
            elif isinstance(value, (int, float)):
                return float(value)
            else:
                utils.log(f"DATA_CONVERSION: Unexpected type for float conversion: {type(value)} = {value}", "DEBUG")
                return default
        except (ValueError, TypeError):
            utils.log(f"DATA_CONVERSION: Failed to convert '{value}' to float, using default {default}", "DEBUG")
            return default

    def safe_convert_string(self, value, default=''):
        """Safely convert value to string with fallback"""
        if value is None:
            return default
        try:
            if isinstance(value, str):
                return value.strip()
            else:
                return str(value).strip()
        except:
            utils.log(f"DATA_CONVERSION: Failed to convert '{value}' to string, using default '{default}'", "DEBUG")
            return default

    def safe_list_to_string(self, value, default=''):
        """Safely convert list or other value to comma-separated string"""
        if value is None:
            return default
        try:
            if isinstance(value, list):
                # Filter out empty/None values and convert to strings
                clean_items = [str(item).strip() for item in value if item is not None and str(item).strip()]
                return ', '.join(clean_items) if clean_items else default
            elif isinstance(value, str):
                return value.strip() if value.strip() else default
            else:
                converted = str(value).strip()
                return converted if converted else default
        except:
            utils.log(f"DATA_CONVERSION: Failed to convert list '{value}' to string, using default '{default}'", "DEBUG")
            return default

    def convert_shortlist_item_to_media_dict(self, item, kodi_movie=None):
        """Convert Shortlist item to LibraryGenie media dictionary format with enhanced data conversion"""
        if kodi_movie:
            # Use Kodi library data - this is preferred when available
            utils.log(f"=== DATA_CONVERSION: Using KODI LIBRARY data for '{kodi_movie.get('title')}' ===", "INFO")

            # Runtime conversion: Kodi stores in minutes, we need seconds
            runtime_minutes = self.safe_convert_int(kodi_movie.get('runtime', 0))
            duration_seconds = runtime_minutes * 60 if runtime_minutes > 0 else 0

            # Cast processing: Extract actor names from cast array
            cast_data = kodi_movie.get('cast', [])
            cast_string = ''
            if isinstance(cast_data, list):
                actor_names = []
                for actor in cast_data[:10]:  # Limit to 10 actors
                    if isinstance(actor, dict):
                        name = actor.get('name', '')
                        if name:
                            actor_names.append(name)
                    elif isinstance(actor, str):
                        actor_names.append(actor)
                cast_string = ', '.join(actor_names) if actor_names else ''

            media_dict = {
                'title': self.safe_convert_string(kodi_movie.get('title'), 'Unknown Title'),
                'year': self.safe_convert_int(kodi_movie.get('year')),
                'plot': self.safe_convert_string(kodi_movie.get('plot')),
                'rating': self.safe_convert_float(kodi_movie.get('rating')),
                'duration': duration_seconds,
                'genre': self.safe_list_to_string(kodi_movie.get('genre')),
                'director': self.safe_list_to_string(kodi_movie.get('director')),
                'cast': cast_string,
                'studio': self.safe_list_to_string(kodi_movie.get('studio')),
                'mpaa': self.safe_convert_string(kodi_movie.get('mpaa')),
                'tagline': self.safe_convert_string(kodi_movie.get('tagline')),
                'writer': self.safe_list_to_string(kodi_movie.get('writer')),
                'country': self.safe_list_to_string(kodi_movie.get('country')),
                'premiered': self.safe_convert_string(kodi_movie.get('premiered')),
                'dateadded': self.safe_convert_string(kodi_movie.get('dateadded')),
                'votes': self.safe_convert_int(kodi_movie.get('votes')),
                'trailer': self.safe_convert_string(kodi_movie.get('trailer')),
                'path': self.safe_convert_string(kodi_movie.get('file')),
                'play': self.safe_convert_string(kodi_movie.get('file')),
                'kodi_id': self.safe_convert_int(kodi_movie.get('movieid')),
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

            # Extract and process art data
            art = kodi_movie.get('art', {})
            if isinstance(art, dict):
                media_dict['thumbnail'] = self.safe_convert_string(art.get('thumb'))
                media_dict['poster'] = self.safe_convert_string(art.get('poster'))
                media_dict['fanart'] = self.safe_convert_string(art.get('fanart'))
                media_dict['art'] = json.dumps(art) if art else ''

            # Extract IMDb ID and other unique identifiers
            uniqueid = kodi_movie.get('uniqueid', {})
            imdbnumber_direct = kodi_movie.get('imdbnumber', '')

            # Prefer uniqueid.imdb over direct imdbnumber
            if isinstance(uniqueid, dict) and uniqueid.get('imdb'):
                media_dict['imdbnumber'] = self.safe_convert_string(uniqueid['imdb'])
            elif imdbnumber_direct:
                media_dict['imdbnumber'] = self.safe_convert_string(imdbnumber_direct)

            media_dict['uniqueid'] = json.dumps(uniqueid) if uniqueid else ''

            utils.log(f"DATA_CONVERSION: Library data processed - IMDb: {media_dict['imdbnumber']}, Runtime: {runtime_minutes}min -> {duration_seconds}s", "INFO")

        else:
            # Use Shortlist data with enhanced validation and conversion
            utils.log(f"=== DATA_CONVERSION: Using SHORTLIST data for '{item.get('title') or item.get('label')}' ===", "INFO")

            # Title processing with fallbacks
            title = self.safe_convert_string(item.get('title')) or \
                   self.safe_convert_string(item.get('label')) or 'Unknown'

            # Duration processing: handle both 'duration' and 'runtime' fields
            duration_value = item.get('duration') or item.get('runtime', 0)
            duration_seconds = self.safe_convert_int(duration_value)

            # If duration seems to be in minutes (common in some sources), check if conversion needed
            if 0 < duration_seconds < 500:  # Likely minutes if between 0-500
                utils.log(f"DATA_CONVERSION: Duration {duration_seconds} seems to be in minutes, converting to seconds", "DEBUG")
                duration_seconds = duration_seconds * 60

            # Rating processing - handle different rating scales
            rating_value = self.safe_convert_float(item.get('rating'))
            if rating_value > 10:  # Rating might be on 100-point scale
                rating_value = rating_value / 10.0
                utils.log(f"DATA_CONVERSION: Rating appears to be on 100-point scale, converted to {rating_value}", "DEBUG")

            media_dict = {
                'title': title,
                'year': self.safe_convert_int(item.get('year')),
                'plot': self.safe_convert_string(item.get('plot')) or self.safe_convert_string(item.get('plotoutline')),
                'rating': rating_value,
                'duration': duration_seconds,
                'genre': self.safe_list_to_string(item.get('genre')),
                'director': self.safe_list_to_string(item.get('director')),
                'cast': self.safe_list_to_string(item.get('cast')),
                'studio': self.safe_list_to_string(item.get('studio')),
                'mpaa': self.safe_convert_string(item.get('mpaa')),
                'tagline': self.safe_convert_string(item.get('tagline')),
                'writer': self.safe_list_to_string(item.get('writer')),
                'country': self.safe_list_to_string(item.get('country')),
                'premiered': self.safe_convert_string(item.get('premiered')),
                'dateadded': self.safe_convert_string(item.get('dateadded')),
                'votes': self.safe_convert_int(item.get('votes')),
                'trailer': self.safe_convert_string(item.get('trailer')),
                'path': self.safe_convert_string(item.get('file')),
                'play': self.safe_convert_string(item.get('file')),
                'kodi_id': 0,  # No Kodi ID for shortlist imports
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

            # Extract art from Shortlist with improved handling
            art = item.get('art', {})
            if art and isinstance(art, dict):
                media_dict['thumbnail'] = self.safe_convert_string(art.get('thumb')) or \
                                         self.safe_convert_string(art.get('icon')) or \
                                         self.safe_convert_string(item.get('thumbnail'))
                media_dict['poster'] = self.safe_convert_string(art.get('poster'))
                media_dict['fanart'] = self.safe_convert_string(art.get('fanart')) or \
                                      self.safe_convert_string(item.get('fanart'))
                media_dict['art'] = json.dumps(art)
            else:
                # Fallback to direct properties
                media_dict['thumbnail'] = self.safe_convert_string(item.get('thumbnail'))
                media_dict['poster'] = self.safe_convert_string(item.get('poster'))
                media_dict['fanart'] = self.safe_convert_string(item.get('fanart'))

            utils.log(f"DATA_CONVERSION: Shortlist data processed - Duration: {duration_value} -> {duration_seconds}s, Rating: {item.get('rating')} -> {rating_value}", "INFO")

        utils.log(f"=== DATA_CONVERSION COMPLETE: '{media_dict['title']}' ({media_dict['year']}) from {media_dict['source']} ===", "INFO")
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
            imported_folder_result = self.db_manager.ensure_folder_exists("Imported Lists", None)

            # Extract the actual ID from the result
            if isinstance(imported_folder_result, dict):
                imported_folder_id = imported_folder_result['id']
            else:
                imported_folder_id = imported_folder_result

            utils.log(f"Imported Lists folder ID: {imported_folder_id}", "DEBUG")

            # Ensure "Shortlist" subfolder exists under "Imported Lists"
            shortlist_folder_result = self.db_manager.ensure_folder_exists("Shortlist", imported_folder_id)

            # Extract the actual ID from the result
            if isinstance(shortlist_folder_result, dict):
                shortlist_folder_id = shortlist_folder_result['id']
            else:
                shortlist_folder_id = shortlist_folder_result

            utils.log(f"Shortlist subfolder ID: {shortlist_folder_id}", "DEBUG")

            # Clear existing data in the shortlist folder only
            progress.update(40, "Clearing existing shortlist imports...")
            self.clear_imported_lists_folder(shortlist_folder_id)

            # Process each list
            total_lists = len(lists)
            for i, shortlist_list in enumerate(lists):
                list_name = shortlist_list['name']
                items = shortlist_list['items']

                # Create dated list name first
                from datetime import datetime
                dated_list_name = f"{list_name} ({datetime.now().strftime('%Y-%m-%d')})"

                progress_percent = 50 + int((i / total_lists) * 40)
                progress.update(progress_percent, f"Processing list: {list_name}")

                utils.log(f"Processing list {i+1}/{total_lists}: {dated_list_name} ({len(items)} items)", "INFO")

                if progress.iscanceled():
                    break

                # Create list in LibraryGenie under Shortlist subfolder with date suffix
                list_result = self.db_manager.create_list(dated_list_name, shortlist_folder_id)

                # Handle both dictionary and integer return values
                if isinstance(list_result, dict):
                    list_id = list_result['id']
                else:
                    list_id = list_result

                utils.log(f"Created LibraryGenie list: {dated_list_name} (ID: {list_id})", "INFO")

                # Process all items in the list and collect media dicts
                media_items_to_add = []
                for j, item in enumerate(items):
                    item_title = item.get('title') or item.get('label', 'Unknown')
                    item_year = self.safe_convert_int(item.get('year'))

                    utils.log(f"=== PROCESSING ITEM {j+1}/{len(items)}: '{item_title}' ({item_year}) ===", "INFO")

                    # Enhanced library lookup with better validation
                    kodi_movie = None
                    if item_title and item_title.strip() and item_title != 'Unknown':
                        # Clean title for better matching
                        clean_title = item_title.strip()
                        if len(clean_title) > 2:  # Only search for titles with meaningful length
                            utils.log(f"IMPORT_PROCESS: Attempting library lookup for '{clean_title}' ({item_year})", "INFO")
                            kodi_movie = self.lookup_in_kodi_library(clean_title, item_year)

                            if kodi_movie:
                                utils.log("IMPORT_SUCCESS: Library match found - will use Kodi data", "INFO")
                            else:
                                utils.log("IMPORT_INFO: No library match - will use Shortlist data", "INFO")
                        else:
                            utils.log(f"IMPORT_SKIP: Title too short for reliable matching: '{clean_title}'", "INFO")
                    else:
                        utils.log(f"IMPORT_SKIP: Invalid title for library lookup: '{item_title}'", "INFO")

                    # Convert to media dict with enhanced data processing
                    try:
                        media_dict = self.convert_shortlist_item_to_media_dict(item, kodi_movie)

                        # Validation of converted data
                        validation_issues = []
                        if not media_dict.get('title') or media_dict['title'] in ['Unknown', '']:
                            validation_issues.append("Missing or invalid title")
                        if media_dict.get('year', 0) < 1900 or media_dict.get('year', 0) > 2030:
                            validation_issues.append(f"Suspicious year: {media_dict.get('year')}")
                        if media_dict.get('duration', 0) < 0:
                            validation_issues.append(f"Invalid duration: {media_dict.get('duration')}")

                        if validation_issues:
                            utils.log(f"DATA_VALIDATION: Issues found for '{media_dict['title']}': {'; '.join(validation_issues)}", "WARNING")

                        # Enhanced logging of final media dict
                        utils.log(f"=== FINAL MEDIA_DICT for '{media_dict['title']}' ===", "INFO")
                        important_fields = ['title', 'year', 'source', 'duration', 'rating', 'genre', 'director', 'plot', 'imdbnumber']
                        for field in important_fields:
                            value = media_dict.get(field, '')
                            if value:
                                utils.log(f"  {field}: {value}", "INFO")
                        utils.log("=== END FINAL MEDIA_DICT ===", "INFO")

                        media_items_to_add.append(media_dict)

                    except Exception as e:
                        utils.log(f"CONVERSION_ERROR: Failed to convert item '{item_title}': {str(e)}", "ERROR")
                        # Create minimal fallback media dict
                        media_dict = {
                            'title': item_title or 'Unknown',
                            'year': item_year or 0,
                            'source': 'shortlist_import',
                            'media_type': 'movie',
                            'kodi_id': 0,
                            'rating': 0.0,
                            'duration': 0,
                            'votes': 0,
                            'plot': f"Failed to process shortlist item: {str(e)}",
                            'play': item.get('file', ''),
                            'path': item.get('file', ''),
                            'status': 'available'
                        }
                        utils.log(f"CONVERSION_FALLBACK: Using minimal data for '{media_dict['title']}'", "WARNING")
                        media_items_to_add.append(media_dict)

                # Add all items to list using batch transaction method
                if media_items_to_add:
                    try:
                        success = self.db_manager.add_shortlist_items(list_id, media_items_to_add)
                        if success:
                            utils.log(f"IMPORT_SUCCESS: Added {len(media_items_to_add)} items to list '{dated_list_name}' in batch", "INFO")
                        else:
                            utils.log(f"DATABASE_ERROR: Failed to add items to list '{dated_list_name}' in batch", "ERROR")
                    except Exception as e:
                        utils.log(f"DATABASE_ERROR: Failed to add items to list '{dated_list_name}': {str(e)}", "ERROR")
                        import traceback
                        utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

            progress.update(100, "Import complete!")
            progress.close()

            if not progress.iscanceled():
                message = f"Successfully imported {total_lists} lists from Shortlist to 'Imported Lists/Shortlist' folder"
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