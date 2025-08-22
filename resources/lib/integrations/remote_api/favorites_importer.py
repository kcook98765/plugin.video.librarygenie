
import json
import xbmc
import xbmcgui
from datetime import datetime
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC
from resources.lib.data.query_manager import QueryManager

# Video file extensions for playability detection
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts', '.mpg', '.mpeg')


class FavoritesImporter:
    def __init__(self):
        self.config = Config()
        self.query_manager = QueryManager(self.config.db_path)
        self.jsonrpc = JSONRPC()
        self._parent_cache = {}

    def _rpc(self, method, params):
        """Execute JSON-RPC call with error handling and detailed logging"""
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        # Log detailed request information
        utils.log("=== FAVORITES JSON-RPC REQUEST ===", "INFO")
        utils.log(f"Method: {method}", "INFO")
        utils.log(f"Raw params: {json.dumps(params, indent=2)}", "INFO")
        utils.log(f"Full request JSON: {json.dumps(req, indent=2)}", "INFO")

        resp = xbmc.executeJSONRPC(json.dumps(req))

        # Log raw response
        utils.log("=== FAVORITES JSON-RPC RESPONSE ===", "INFO")
        utils.log(f"Raw response length: {len(resp)} characters", "INFO")
        utils.log(f"Raw response preview: {resp[:500]}{'...' if len(resp) > 500 else ''}", "INFO")

        data = json.loads(resp)

        # Log parsed response details
        if "error" in data:
            utils.log("=== FAVORITES JSON-RPC ERROR ANALYSIS ===", "ERROR")
            error = data["error"]
            utils.log(f"Error code: {error.get('code')}", "ERROR")
            utils.log(f"Error message: {error.get('message')}", "ERROR")
            utils.log(f"Error data: {json.dumps(error.get('data', {}), indent=2)}", "ERROR")

            utils.log("=== END ERROR ANALYSIS ===", "ERROR")
            raise RuntimeError(data["error"])
        else:
            utils.log("=== FAVORITES JSON-RPC SUCCESS ===", "INFO")
            result = data.get("result", {})
            if isinstance(result, dict):
                utils.log(f"Result keys: {list(result.keys())}", "INFO")
                if "favourites" in result:
                    utils.log(f"Favourites returned: {len(result['favourites'])}", "INFO")
            utils.log("=== END SUCCESS RESPONSE ===", "INFO")

        return data.get("result", {})

    def _fetch_favourites_media(self):
        """Pull media favourites only"""
        result = self._rpc("Favourites.GetFavourites", {
            "type": "media",
            "properties": ["path", "thumbnail", "window", "windowparameter"]
        })
        favs = result.get("favourites", []) or []
        utils.log(f"Fetched {len(favs)} favourites (type=media)", "INFO")
        return favs

    def _get_file_details(self, path):
        """Query Files.GetFileDetails for a path"""
        try:
            result = self._rpc("Files.GetFileDetails", {
                "file": path,
                "media": "video",
                "properties": [
                    "file", "title", "thumbnail", "fanart", "art",
                    "runtime", "streamdetails", "resume",
                    "dateadded", "imdbnumber", "uniqueid"
                ]
            })
            return result.get("filedetails") or {}
        except Exception as e:
            utils.log(f"Files.GetFileDetails failed for path={path}: {e}", "DEBUG")
            return {}

    def _get_dir_probe(self, path):
        """Fallback probe: Files.GetDirectory when GetFileDetails doesn't answer"""
        try:
            result = self._rpc("Files.GetDirectory", {
                "directory": path,
                "media": "files",
                "properties": ["file", "title", "thumbnail", "art", "duration", "streamdetails"],
                "limits": {"start": 0, "end": 200}
            })
            return result.get("files", []) or []
        except Exception as e:
            utils.log(f"Files.GetDirectory probe failed for path={path}: {e}", "DEBUG")
            return []

    def _is_playable_video(self, path):
        """
        Accept if:
          - plugin://plugin.video.* URLs (always playable)
          - videodb:// URLs (always playable)
          - path has video file extension (cheap check first)
          - streamdetails.video is present (strongest signal)
          - OR directory probe finds matching filename with video extension
        """
        if not path:
            return False

        # Plugin video URLs are always playable
        if path.startswith("plugin://plugin.video."):
            utils.log(f"Playable confirmed by plugin URL for: {path}", "DEBUG")
            return True

        # videodb:// URLs are always playable
        if path.startswith("videodb://"):
            utils.log(f"Playable confirmed by videodb URL for: {path}", "DEBUG")
            return True

        # Strip pipe options for probing but keep original path
        base_path = path.split('|')[0] if '|' in path else path

        # Check file extension first (cheap operation) for real file URLs
        if base_path and any(base_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
            utils.log(f"Playable confirmed by file extension for: {path}", "DEBUG")
            return True

        # Only call expensive RPC if extension check failed
        fd = self._get_file_details(base_path)
        
        # Check for streamdetails.video as strongest playable indicator
        streamdetails = fd.get("streamdetails", {})
        if isinstance(streamdetails, dict) and streamdetails.get("video"):
            utils.log(f"Playable confirmed by streamdetails for: {path}", "DEBUG")
            return True

        # For directories or unclear paths, probe parent directory
        if "/" in base_path and not base_path.startswith(("plugin://", "videodb://", "pvr://")):
            parent, filename = self._split_parent_and_filename(base_path)
            if parent and filename:
                listing = self._get_dir_probe(parent)
                for item in listing:
                    item_file = item.get("file", "")
                    if item_file.lower().endswith(filename.lower()):
                        # Check if this item has streamdetails or video extension
                        item_streamdetails = item.get("streamdetails", {})
                        if isinstance(item_streamdetails, dict) and item_streamdetails.get("video"):
                            return True
                        if any(item_file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                            return True

        utils.log(f"Could not confirm playability for: {path}", "DEBUG")
        return False

    def _split_parent_and_filename(self, path):
        """Return (parent, filename) for URL-like paths (smb, nfs, file)"""
        if not path:
            return "", ""
        # Kodi uses forward slashes in URLs
        idx = path.rfind("/")
        if idx <= 0:
            return "", path
        return path[:idx + 1], path[idx + 1:]

    def _library_match_from_path(self, path):
        """
        Use parent folder 'startswith' and then match filename in-memory.
        Only meaningful for real file URLs (smb://, nfs://, file://).
        """
        if not path or path.startswith("plugin://") or path.startswith("videodb://") or path.startswith("pvr://"):
            return None

        parent, filename = self._split_parent_and_filename(path)
        if not parent or not filename:
            return None

        utils.log(f"LIB_LOOKUP: Attempting path+filename match: parent={parent} filename={filename}", "INFO")

        props = [
            "title", "year", "plot", "rating", "runtime", "genre", "director",
            "cast", "studio", "mpaa", "tagline", "writer", "country", "premiered",
            "dateadded", "votes", "trailer", "file", "art", "imdbnumber", "uniqueid", "streamdetails"
        ]

        # Check cache first
        cache_key = parent
        if cache_key in self._parent_cache:
            utils.log(f"LIB_LOOKUP: Using cached results for parent: {parent}", "DEBUG")
            movies = self._parent_cache[cache_key]
        else:
            # Use precise server-side filter with AND condition
            try:
                resp = self.jsonrpc.execute("VideoLibrary.GetMovies", {
                    "filter": {
                        "and": [
                            {"field": "path", "operator": "startswith", "value": parent},
                            {"field": "filename", "operator": "is", "value": filename}
                        ]
                    },
                    "properties": props,
                    "limits": {"start": 0, "end": 10000}
                })
                movies = resp.get("result", {}).get("movies", []) or []
                
                # If precise filter fails, fall back to broad parent query and cache it
                if not movies:
                    utils.log(f"LIB_LOOKUP: Precise filter failed, falling back to broad parent query", "DEBUG")
                    resp = self.jsonrpc.execute("VideoLibrary.GetMovies", {
                        "filter": {
                            "field": "path", "operator": "startswith", "value": parent
                        },
                        "properties": props,
                        "limits": {"start": 0, "end": 10000}
                    })
                    movies = resp.get("result", {}).get("movies", []) or []
                    self._parent_cache[cache_key] = movies
                    
            except Exception as e:
                utils.log(f"LIB_LOOKUP error (path match): {e}", "DEBUG")
                return None

        # Match filename in results
        filename_lower = filename.lower()
        for m in movies:
            mf = (m.get("file") or "").lower()
            if mf.endswith("/" + filename_lower) or mf.endswith("\\" + filename_lower) or mf.endswith(filename_lower):
                utils.log(f"LIB_MATCH: Found by path/filename -> {m.get('title')} ({m.get('year')})", "INFO")
                return m

        return None

    def lookup_in_kodi_library(self, title, year=None):
        """Try to find movie in Kodi library using comprehensive JSONRPC search"""
        if not title or not title.strip():
            return None
        title = title.strip()

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
                        utils.log("JSONRPC DECISION: Using library data instead of favorites data", "INFO")
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
                    utils.log("JSONRPC DECISION: Using library data instead of favorites data", "INFO")
                    return best_match

        except Exception as e:
            utils.log(f"JSONRPC ERROR: Library lookup failed: {str(e)}", "ERROR")
            utils.log("JSONRPC DECISION: Will use favorites data due to lookup error", "INFO")

        utils.log("JSONRPC RESULT: No library match found for '{title}' ({year})", "INFO")
        utils.log("JSONRPC DECISION: Will use favorites data as no library match exists", "INFO")
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

    def convert_favorite_item_to_media_dict(self, fav, filedetails=None, kodi_movie=None):
        """Convert Favorite item to LibraryGenie media dictionary format with enhanced data conversion"""
        if kodi_movie:
            # Use Kodi library data - this is preferred when available
            utils.log(f"=== DATA_CONVERSION: Using KODI LIBRARY data for '{kodi_movie.get('title')}' ===", "INFO")

            # Duration calculation with streamdetails preference
            duration_seconds = 0
            runtime_minutes = 0
            streamdetails = kodi_movie.get('streamdetails', {})
            if isinstance(streamdetails, dict) and streamdetails.get('video'):
                video_streams = streamdetails['video']
                if isinstance(video_streams, list) and len(video_streams) > 0:
                    stream_duration = self.safe_convert_int(video_streams[0].get('duration', 0))
                    if 60 <= stream_duration <= 21600:  # 1 minute to 6 hours range
                        duration_seconds = stream_duration
                        utils.log(f"Duration from streamdetails: {duration_seconds}s", "DEBUG")
            
            if duration_seconds == 0:
                # Fallback to runtime in minutes
                runtime_minutes = self.safe_convert_int(kodi_movie.get('runtime', 0))
                duration_seconds = runtime_minutes * 60 if runtime_minutes > 0 else 0
                utils.log(f"Duration from runtime: {runtime_minutes}min -> {duration_seconds}s", "DEBUG")

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
                'source': 'favorites_import',
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

            utils.log(f"DATA_CONVERSION: Library data processed - IMDb: {media_dict['imdbnumber']}, Duration: {duration_seconds}s", "INFO")

        else:
            # Use Favorites data with enhanced validation and conversion
            utils.log(f"=== DATA_CONVERSION: Using FAVORITES data for '{fav.get('title')}' ===", "INFO")

            # Title processing with fallbacks
            title = self.safe_convert_string(fav.get('title')) or \
                   self.safe_convert_string((filedetails or {}).get('title')) or 'Unknown'

            # Duration calculation with streamdetails preference
            duration_seconds = 0
            runtime_minutes = 0
            if filedetails:
                streamdetails = filedetails.get('streamdetails', {})
                if isinstance(streamdetails, dict) and streamdetails.get('video'):
                    video_streams = streamdetails['video']
                    if isinstance(video_streams, list) and len(video_streams) > 0:
                        stream_duration = self.safe_convert_int(video_streams[0].get('duration', 0))
                        if 60 <= stream_duration <= 21600:  # 1 minute to 6 hours range
                            duration_seconds = stream_duration
                            utils.log(f"Duration from filedetails streamdetails: {duration_seconds}s", "DEBUG")
            
            if duration_seconds == 0:
                # Fallback to runtime in minutes or duration in seconds
                runtime_minutes = self.safe_convert_int((filedetails or {}).get('runtime', 0))
                duration_from_field = self.safe_convert_int((filedetails or {}).get('duration', 0))
                
                if duration_from_field > 0:
                    # If duration field is present, use it (already in seconds)
                    duration_seconds = duration_from_field
                    utils.log(f"Duration from duration field: {duration_seconds}s", "DEBUG")
                elif runtime_minutes > 0:
                    # Otherwise use runtime and convert to seconds
                    duration_seconds = runtime_minutes * 60
                    utils.log(f"Duration from runtime: {runtime_minutes}min -> {duration_seconds}s", "DEBUG")

            art = (filedetails or {}).get('art', {})
            thumb = (filedetails or {}).get('thumbnail') or self.safe_convert_string(fav.get('thumbnail'))
            fan = (filedetails or {}).get('fanart')

            media_dict = {
                'title': title,
                'year': 0,
                'plot': '',
                'rating': 0.0,
                'duration': duration_seconds,
                'genre': '',
                'director': '',
                'cast': '',
                'studio': '',
                'mpaa': '',
                'tagline': '',
                'writer': '',
                'country': '',
                'premiered': '',
                'dateadded': self.safe_convert_string((filedetails or {}).get('dateadded')),
                'votes': 0,
                'trailer': '',
                'path': self.safe_convert_string(fav.get('path')),
                'play': self.safe_convert_string(fav.get('path')),
                'kodi_id': 0,  # No Kodi ID for favorites imports
                'media_type': 'movie',
                'source': 'favorites_import',
                'imdbnumber': self.safe_convert_string((filedetails or {}).get('imdbnumber')),
                'thumbnail': self.safe_convert_string(thumb),
                'poster': self.safe_convert_string(art.get('poster')) if isinstance(art, dict) else '',
                'fanart': self.safe_convert_string(fan),
                'art': json.dumps(art) if isinstance(art, dict) and art else '',
                'uniqueid': '',
                'stream_url': '',
                'status': 'available'
            }

            utils.log(f"DATA_CONVERSION: Favorites data processed - Duration: {duration_seconds}s", "INFO")

        utils.log(f"=== DATA_CONVERSION COMPLETE: '{media_dict['title']}' from {media_dict['source']} ===", "INFO")
        return media_dict

    def clear_imported_favorites_folder(self, imported_folder_id):
        """Clear all contents of the Imported Favorites folder"""
        utils.log(f"Clearing contents of Imported Favorites folder (ID: {imported_folder_id})", "INFO")

        # Get all subfolders and lists in the imported folder
        subfolders = self.query_manager.fetch_folders(imported_folder_id)
        lists = self.query_manager.fetch_lists(imported_folder_id)

        # Delete all lists first
        for list_item in lists:
            utils.log(f"Deleting list: {list_item['name']} (ID: {list_item['id']})", "DEBUG")
            self.query_manager.delete_list_and_contents(list_item['id'])

        # Delete all subfolders (this will cascade to their contents)
        for folder in subfolders:
            utils.log(f"Deleting folder: {folder['name']} (ID: {folder['id']})", "DEBUG")
            self.query_manager.delete_folder(folder['id'])

        utils.log("Imported Favorites folder cleared", "INFO")

    def import_from_favorites(self):
        """Main import function"""
        utils.log("=== Starting Favorites import process ===", "INFO")

        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("Importing from Favorites", "Scanning Kodi favorites...")
        progress.update(10)

        try:
            # Fetch favorites data
            favourites = self._fetch_favourites_media()
            if not favourites:
                progress.close()
                xbmcgui.Dialog().notification("LibraryGenie", "No media favorites found", xbmcgui.NOTIFICATION_WARNING)
                return False

            progress.update(30, "Filtering playable items...")

            # Filter for playable video items
            playable = []
            for fav in favourites:
                if progress.iscanceled():
                    break

                path = fav.get("path")
                ftype = fav.get("type")
                if not path or ftype != "media":
                    continue

                if self._is_playable_video(path):
                    playable.append(fav)
                else:
                    utils.log(f"Skipped non-playable favorite: {fav.get('title')} [{path}]", "DEBUG")

            utils.log(f"Playable favorites: {len(playable)} / {len(favourites)}", "INFO")
            
            if progress.iscanceled():
                progress.close()
                utils.log("Favorites import cancelled (during filtering)", "INFO")
                return False

            if not playable:
                progress.close()
                xbmcgui.Dialog().notification("LibraryGenie", "No playable video items in Favorites", xbmcgui.NOTIFICATION_WARNING)
                return False

            progress.update(40, "Preparing import folder...")

            # Ensure "Imported Lists" folder exists
            imported_folder_id = self.query_manager.get_folder_id_by_name("Imported Lists")
            if not imported_folder_id:
                imported_folder_result = self.query_manager.create_folder("Imported Lists", None)
                imported_folder_id = imported_folder_result['id']

            utils.log(f"Imported Lists folder ID: {imported_folder_id}", "DEBUG")

            # Clear existing data in the imported lists folder
            progress.update(42, "Clearing existing favorites imports...")
            self.clear_imported_favorites_folder(imported_folder_id)

            # Create a dated list under Imported Lists folder
            list_name = f"Favorites ({datetime.now().strftime('%Y-%m-%d')})"
            list_result = self.query_manager.create_list(list_name, imported_folder_id)
            list_id = list_result['id']

            utils.log(f"Created LibraryGenie list: {list_name} (ID: {list_id})", "INFO")

            # Process all items in the list and collect media dicts
            media_items_to_add = []
            upgraded_count = 0
            total_items = len(playable)

            for i, fav in enumerate(playable):
                if progress.iscanceled():
                    break

                progress_percent = 50 + int((i / total_items) * 40)
                fav_title = fav.get('title') or 'Untitled'
                progress.update(progress_percent, f"Processing: {fav_title}")

                utils.log(f"=== PROCESSING ITEM {i+1}/{total_items}: '{fav_title}' ===", "INFO")

                path = fav.get("path") or ""
                title = self.safe_convert_string(fav.get("title"))
                year = None  # Favorites rarely include year

                # Try strongest library mapping first: path+filename (non-plugin / non-videodb)
                kodi_movie = self._library_match_from_path(path)

                # If videodb:// favourite or plugin:// with no path match: try title lookup
                if not kodi_movie:
                    if path.startswith("videodb://"):
                        kodi_movie = self.lookup_in_kodi_library(title, year)
                    elif not path.startswith(("smb://", "nfs://", "file://")):
                        # plugin://, pvr:// etc. -> title-based lookup might still succeed
                        kodi_movie = self.lookup_in_kodi_library(title, year)

                if kodi_movie:
                    utils.log("IMPORT_SUCCESS: Library match found - will use Kodi data", "INFO")
                    upgraded_count += 1
                    filedetails = None  # Skip file details when we have library data
                else:
                    utils.log("IMPORT_INFO: No library match - will use Favorites data", "INFO")
                    # Pull filedetails only when we don't have library data
                    filedetails = self._get_file_details(path)

                # Convert to media dict with enhanced data processing
                try:
                    media_dict = self.convert_favorite_item_to_media_dict(
                        fav=fav,
                        filedetails=filedetails,
                        kodi_movie=kodi_movie
                    )

                    # Validation of converted data
                    validation_issues = []
                    if not media_dict.get('title') or media_dict['title'] in ['Unknown', '']:
                        validation_issues.append("Missing or invalid title")
                        media_dict['title'] = 'Unknown'
                    if media_dict.get('duration', 0) < 0:
                        validation_issues.append(f"Invalid duration: {media_dict.get('duration')}")
                        media_dict['duration'] = 0

                    if validation_issues:
                        utils.log(f"DATA_VALIDATION: Issues found for '{media_dict['title']}': {'; '.join(validation_issues)}", "WARNING")

                    # Enhanced logging of final media dict
                    utils.log(f"=== FINAL MEDIA_DICT for '{media_dict['title']}' ===", "INFO")
                    important_fields = ['title', 'source', 'duration', 'rating', 'genre', 'director', 'plot', 'imdbnumber']
                    for field in important_fields:
                        value = media_dict.get(field, '')
                        if value:
                            utils.log(f"  {field}: {value}", "INFO")
                    utils.log("=== END FINAL MEDIA_DICT ===", "INFO")

                    media_items_to_add.append(media_dict)

                except Exception as e:
                    utils.log(f"CONVERSION_ERROR: Failed to convert item '{fav_title}': {str(e)}", "ERROR")
                    # Create minimal fallback media dict
                    media_dict = {
                        'title': fav_title or 'Unknown',
                        'year': 0,
                        'source': 'favorites_import',
                        'media_type': 'movie',
                        'kodi_id': 0,
                        'rating': 0.0,
                        'duration': 0,
                        'votes': 0,
                        'plot': f"Failed to process favorite item: {str(e)}",
                        'play': fav.get('path', ''),
                        'path': fav.get('path', ''),
                        'status': 'available'
                    }
                    utils.log(f"CONVERSION_FALLBACK: Using minimal data for '{media_dict['title']}'", "WARNING")
                    media_items_to_add.append(media_dict)

            if progress.iscanceled():
                progress.close()
                utils.log("Favorites import cancelled (during processing)", "INFO")
                return False

            # Add all items to list using batch transaction method
            if media_items_to_add:
                try:
                    # Use QueryManager method directly for each item
                    success_count = 0
                    for media_item in media_items_to_add:
                        if self.query_manager.insert_media_item_and_add_to_list(list_id, media_item):
                            success_count += 1
                    
                    if success_count == len(media_items_to_add):
                        utils.log(f"IMPORT_SUCCESS: Added {len(media_items_to_add)} items to list '{list_name}' in batch", "INFO")
                    else:
                        utils.log(f"DATABASE_PARTIAL: Added {success_count}/{len(media_items_to_add)} items to list '{list_name}'", "WARNING")
                except Exception as e:
                    utils.log(f"DATABASE_ERROR: Failed to add items to list '{list_name}': {str(e)}", "ERROR")
                    import traceback
                    utils.log(f"Full traceback: {traceback.format_exc()}", "ERROR")

            progress.update(100, "Import complete!")
            progress.close()

            if not progress.iscanceled():
                message = f"Imported {len(media_items_to_add)} favorites to 'Imported Lists' ({upgraded_count} upgraded from library)"
                xbmcgui.Dialog().notification("LibraryGenie", message, xbmcgui.NOTIFICATION_INFO, 5000)
                utils.log(f"=== Favorites import complete: {message} ===", "INFO")
                return True
            else:
                utils.log("Favorites import cancelled by user", "INFO")
                return False

        except Exception as e:
            progress.close()
            error_msg = f"Import failed: {str(e)}"
            utils.log(f"Favorites import error: {error_msg}", "ERROR")
            import traceback
            utils.log(f"Favorites import traceback: {traceback.format_exc()}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", error_msg, xbmcgui.NOTIFICATION_ERROR, 5000)
            return False


def import_from_favorites():
    """Standalone function for settings action"""
    importer = FavoritesImporter()
    return importer.import_from_favorites()
